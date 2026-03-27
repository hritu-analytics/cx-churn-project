-- ============================================================================
-- NEXABANK: CUSTOMER CHURN REVENUE IMPACT ANALYSIS
-- SQL Analysis Layer | Hrituparna Das
-- ============================================================================
-- Tools: PostgreSQL-style syntax (executed via SQLite/DuckDB for portability)
-- Key techniques: CTEs, Window Functions, Cohort Analysis, Revenue Attribution
-- ============================================================================


-- ============================================================================
-- QUERY 1: REVENUE AT RISK — SEGMENTED BY PRODUCT & TENURE COHORT
-- Business Question: Where is the highest-value churn concentrated?
-- ============================================================================

WITH customer_cohorts AS (
    SELECT
        customer_id,
        segment,
        tenure_months,
        monthly_revenue_gbp,
        annual_revenue_gbp,
        churned,
        CASE
            WHEN tenure_months <= 3 THEN '0-3 months'
            WHEN tenure_months <= 6 THEN '3-6 months'
            WHEN tenure_months <= 12 THEN '6-12 months'
            WHEN tenure_months <= 24 THEN '12-24 months'
            ELSE '24+ months'
        END AS tenure_cohort
    FROM customers
),

revenue_at_risk AS (
    SELECT
        segment,
        tenure_cohort,
        COUNT(*) AS total_customers,
        SUM(churned) AS churned_customers,
        ROUND(AVG(churned) * 100, 1) AS churn_rate_pct,
        ROUND(SUM(CASE WHEN churned = 1 THEN annual_revenue_gbp ELSE 0 END), 0) AS revenue_at_risk_gbp,
        ROUND(AVG(CASE WHEN churned = 1 THEN monthly_revenue_gbp ELSE NULL END), 0) AS avg_monthly_rev_churned
    FROM customer_cohorts
    GROUP BY segment, tenure_cohort
)

SELECT
    segment,
    tenure_cohort,
    total_customers,
    churned_customers,
    churn_rate_pct,
    revenue_at_risk_gbp,
    avg_monthly_rev_churned,
    -- Window function: rank segments by revenue at risk within each cohort
    RANK() OVER (
        PARTITION BY tenure_cohort
        ORDER BY revenue_at_risk_gbp DESC
    ) AS risk_rank_in_cohort,
    -- Window function: cumulative revenue at risk across cohorts
    SUM(revenue_at_risk_gbp) OVER (
        PARTITION BY segment
        ORDER BY
            CASE tenure_cohort
                WHEN '0-3 months' THEN 1
                WHEN '3-6 months' THEN 2
                WHEN '6-12 months' THEN 3
                WHEN '12-24 months' THEN 4
                ELSE 5
            END
        ROWS UNBOUNDED PRECEDING
    ) AS cumulative_rev_at_risk
FROM revenue_at_risk
ORDER BY revenue_at_risk_gbp DESC;


-- ============================================================================
-- QUERY 2: CHURN PROBABILITY DRIVERS — ENGAGEMENT × SUPPORT INTERACTION
-- Business Question: Which behavioral signals best predict churn?
-- ============================================================================

WITH behavioral_signals AS (
    SELECT
        customer_id,
        segment,
        churned,
        digital_engagement_score,
        support_tickets_90d,
        products_held,
        avg_payment_delay_days,
        monthly_revenue_gbp,
        -- Bin engagement into actionable tiers
        CASE
            WHEN digital_engagement_score >= 70 THEN 'High Engagement'
            WHEN digital_engagement_score >= 40 THEN 'Medium Engagement'
            ELSE 'Low Engagement'
        END AS engagement_tier,
        -- Support intensity
        CASE
            WHEN support_tickets_90d >= 4 THEN 'High Contact'
            WHEN support_tickets_90d >= 2 THEN 'Medium Contact'
            ELSE 'Low Contact'
        END AS support_tier
    FROM customers
),

driver_matrix AS (
    SELECT
        engagement_tier,
        support_tier,
        COUNT(*) AS customers,
        SUM(churned) AS churned_count,
        ROUND(AVG(churned) * 100, 1) AS churn_rate,
        ROUND(SUM(CASE WHEN churned = 1 THEN monthly_revenue_gbp * 12 ELSE 0 END), 0) AS annual_rev_at_risk,
        ROUND(AVG(monthly_revenue_gbp), 0) AS avg_monthly_rev,
        ROUND(AVG(products_held), 1) AS avg_products
    FROM behavioral_signals
    GROUP BY engagement_tier, support_tier
)

SELECT
    engagement_tier,
    support_tier,
    customers,
    churned_count,
    churn_rate,
    annual_rev_at_risk,
    avg_monthly_rev,
    avg_products,
    -- Window: percentage of total revenue at risk
    ROUND(
        annual_rev_at_risk * 100.0 /
        SUM(annual_rev_at_risk) OVER (), 1
    ) AS pct_of_total_risk
FROM driver_matrix
ORDER BY churn_rate DESC;


-- ============================================================================
-- QUERY 3: CUSTOMER LIFETIME VALUE SEGMENTATION WITH RETENTION PRIORITY
-- Business Question: Which customers should we prioritize for retention?
-- ============================================================================

WITH clv_segments AS (
    SELECT
        customer_id,
        segment,
        region,
        tenure_months,
        monthly_revenue_gbp,
        estimated_clv_gbp,
        churned,
        products_held,
        digital_engagement_score,
        support_tickets_90d,
        -- CLV tier
        NTILE(4) OVER (ORDER BY estimated_clv_gbp DESC) AS clv_quartile
    FROM customers
),

retention_priority AS (
    SELECT
        *,
        CASE
            WHEN clv_quartile = 1 AND churned = 1 THEN 'CRITICAL — High-Value Lost'
            WHEN clv_quartile = 1 AND churned = 0 AND digital_engagement_score < 40 THEN 'URGENT — High-Value At Risk'
            WHEN clv_quartile <= 2 AND churned = 0 AND support_tickets_90d >= 4 THEN 'WATCH — Elevated Support Activity'
            WHEN clv_quartile <= 2 AND churned = 0 THEN 'MAINTAIN — Stable High Value'
            ELSE 'MONITOR — Standard'
        END AS retention_action
    FROM clv_segments
)

SELECT
    retention_action,
    COUNT(*) AS customer_count,
    ROUND(AVG(estimated_clv_gbp), 0) AS avg_clv,
    ROUND(SUM(monthly_revenue_gbp * 12), 0) AS total_annual_revenue,
    ROUND(AVG(digital_engagement_score), 1) AS avg_engagement,
    ROUND(AVG(support_tickets_90d), 1) AS avg_support_tickets,
    ROUND(AVG(tenure_months), 0) AS avg_tenure
FROM retention_priority
GROUP BY retention_action
ORDER BY
    CASE retention_action
        WHEN 'CRITICAL — High-Value Lost' THEN 1
        WHEN 'URGENT — High-Value At Risk' THEN 2
        WHEN 'WATCH — Elevated Support Activity' THEN 3
        WHEN 'MAINTAIN — Stable High Value' THEN 4
        ELSE 5
    END;


-- ============================================================================
-- QUERY 4: ACQUISITION CHANNEL EFFICIENCY — COST OF CHURN BY SOURCE
-- Business Question: Which channels bring high-churn, low-value customers?
-- ============================================================================

WITH channel_performance AS (
    SELECT
        acquisition_channel,
        segment,
        COUNT(*) AS total_acquired,
        SUM(churned) AS churned_count,
        ROUND(AVG(churned) * 100, 1) AS churn_rate,
        ROUND(AVG(monthly_revenue_gbp), 0) AS avg_monthly_rev,
        ROUND(AVG(estimated_clv_gbp), 0) AS avg_clv,
        ROUND(AVG(tenure_months), 1) AS avg_tenure,
        ROUND(SUM(CASE WHEN churned = 1 THEN annual_revenue_gbp ELSE 0 END), 0) AS revenue_lost
    FROM customers
    GROUP BY acquisition_channel, segment
)

SELECT
    acquisition_channel,
    segment,
    total_acquired,
    churned_count,
    churn_rate,
    avg_monthly_rev,
    avg_clv,
    avg_tenure,
    revenue_lost,
    -- Window: rank channels by churn rate within each segment
    ROW_NUMBER() OVER (
        PARTITION BY segment
        ORDER BY churn_rate DESC
    ) AS worst_channel_rank,
    -- Window: channel's share of total segment revenue lost
    ROUND(
        revenue_lost * 100.0 /
        NULLIF(SUM(revenue_lost) OVER (PARTITION BY segment), 0), 1
    ) AS pct_segment_loss
FROM channel_performance
ORDER BY revenue_lost DESC;


-- ============================================================================
-- QUERY 5: RETENTION STRATEGY SIMULATION — ROI OF INTERVENTION SCENARIOS
-- Business Question: What's the expected ROI of targeted retention actions?
-- ============================================================================

WITH at_risk_customers AS (
    SELECT
        customer_id,
        segment,
        monthly_revenue_gbp,
        annual_revenue_gbp,
        estimated_clv_gbp,
        tenure_months,
        digital_engagement_score,
        support_tickets_90d,
        products_held
    FROM customers
    WHERE churned = 0
      AND (digital_engagement_score < 40 OR support_tickets_90d >= 4)
      AND estimated_clv_gbp > (SELECT AVG(estimated_clv_gbp) * 0.8 FROM customers)
),

intervention_scenarios AS (
    SELECT
        segment,
        COUNT(*) AS targetable_customers,
        ROUND(SUM(annual_revenue_gbp), 0) AS total_annual_rev_at_risk,
        ROUND(AVG(estimated_clv_gbp), 0) AS avg_clv,
        -- Scenario A: 10% discount offer (cost = 10% of annual rev, saves ~40% of at-risk)
        ROUND(SUM(annual_revenue_gbp) * 0.40, 0) AS scenario_a_recovered_rev,
        ROUND(SUM(annual_revenue_gbp) * 0.10, 0) AS scenario_a_cost,
        -- Scenario B: Dedicated support (cost = £200/customer, saves ~25% of at-risk)
        ROUND(SUM(annual_revenue_gbp) * 0.25, 0) AS scenario_b_recovered_rev,
        COUNT(*) * 200 AS scenario_b_cost,
        -- Scenario C: Product bundling (cost = £150/customer, saves ~55% via stickiness)
        ROUND(SUM(annual_revenue_gbp) * 0.55, 0) AS scenario_c_recovered_rev,
        COUNT(*) * 150 AS scenario_c_cost
    FROM at_risk_customers
    GROUP BY segment
)

SELECT
    segment,
    targetable_customers,
    total_annual_rev_at_risk,
    avg_clv,
    -- Scenario A ROI
    scenario_a_recovered_rev,
    scenario_a_cost,
    ROUND((scenario_a_recovered_rev - scenario_a_cost) * 100.0 /
        NULLIF(scenario_a_cost, 0), 0) AS scenario_a_roi_pct,
    -- Scenario B ROI
    scenario_b_recovered_rev,
    scenario_b_cost,
    ROUND((scenario_b_recovered_rev - scenario_b_cost) * 100.0 /
        NULLIF(scenario_b_cost, 0), 0) AS scenario_b_roi_pct,
    -- Scenario C ROI
    scenario_c_recovered_rev,
    scenario_c_cost,
    ROUND((scenario_c_recovered_rev - scenario_c_cost) * 100.0 /
        NULLIF(scenario_c_cost, 0), 0) AS scenario_c_roi_pct
FROM intervention_scenarios
ORDER BY total_annual_rev_at_risk DESC;
