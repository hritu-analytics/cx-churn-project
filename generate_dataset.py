import numpy as np
import pandas as pd
from datetime import datetime, timedelta

np.random.seed(42)

N = 4800
start_date = datetime(2023, 1, 1)
end_date = datetime(2024, 12, 31)

# Customer IDs
customer_ids = [f"NX-{str(i).zfill(5)}" for i in range(1, N + 1)]

# Segments
segments = np.random.choice(
    ["Personal Loan", "Business Line of Credit", "Auto Finance", "Mortgage Refinance"],
    size=N, p=[0.35, 0.25, 0.22, 0.18]
)

# Tenure in months (how long they've been a customer)
tenure = np.random.exponential(scale=14, size=N).astype(int).clip(1, 60)

# Signup dates
signup_dates = [start_date + timedelta(days=np.random.randint(0, 500)) for _ in range(N)]

# Monthly revenue per customer (varies by segment)
revenue_map = {
    "Personal Loan": (180, 60),
    "Business Line of Credit": (420, 130),
    "Auto Finance": (290, 80),
    "Mortgage Refinance": (520, 150)
}
monthly_revenue = np.array([
    max(50, np.random.normal(revenue_map[s][0], revenue_map[s][1]))
    for s in segments
])

# Credit score
credit_scores = np.random.normal(680, 55, N).astype(int).clip(500, 850)

# Number of support tickets in last 90 days
support_tickets = np.random.poisson(1.8, N).clip(0, 12)

# Number of products held
products_held = np.random.choice([1, 2, 3, 4], N, p=[0.40, 0.30, 0.20, 0.10])

# Digital engagement score (0-100)
engagement_score = np.random.beta(2.5, 3, N) * 100

# Payment delay days (avg days late on payments)
payment_delay = np.random.exponential(3, N).clip(0, 45).round(1)

# Region
regions = np.random.choice(
    ["London", "South East", "North West", "Midlands", "Scotland", "Wales", "East Anglia"],
    N, p=[0.25, 0.18, 0.16, 0.15, 0.10, 0.08, 0.08]
)

# Channel
acquisition_channel = np.random.choice(
    ["Organic Search", "Paid Ads", "Referral", "Direct", "Partnership"],
    N, p=[0.28, 0.25, 0.20, 0.15, 0.12]
)

# --- CHURN LOGIC (realistic, multi-factor) ---
churn_prob = np.zeros(N)

# Tenure effect: new customers churn more (< 90 days = high risk)
churn_prob += np.where(tenure <= 3, 0.25, 0)
churn_prob += np.where((tenure > 3) & (tenure <= 6), 0.12, 0)
churn_prob += np.where(tenure > 24, -0.08, 0)

# Support tickets: more tickets = more churn
churn_prob += support_tickets * 0.04

# Products held: more products = stickier
churn_prob -= products_held * 0.06

# Engagement: low engagement = higher churn
churn_prob += np.where(engagement_score < 30, 0.15, 0)
churn_prob += np.where(engagement_score > 70, -0.10, 0)

# Payment delay
churn_prob += np.where(payment_delay > 10, 0.12, 0)
churn_prob += np.where(payment_delay > 25, 0.10, 0)

# Credit score effect
churn_prob += np.where(credit_scores < 600, 0.08, 0)

# Segment effect
segment_churn = {"Personal Loan": 0.05, "Business Line of Credit": 0.02, "Auto Finance": 0.07, "Mortgage Refinance": -0.03}
churn_prob += np.array([segment_churn[s] for s in segments])

# Channel effect
channel_churn = {"Organic Search": 0.0, "Paid Ads": 0.06, "Referral": -0.04, "Direct": 0.02, "Partnership": -0.02}
churn_prob += np.array([channel_churn[c] for c in acquisition_channel])

# Clip and add noise
churn_prob = np.clip(churn_prob + np.random.normal(0, 0.05, N), 0.03, 0.85)

# Generate churn label
churned = np.random.binomial(1, churn_prob)

# Churn date (only for churned customers)
churn_dates = []
for i in range(N):
    if churned[i]:
        days_after = np.random.randint(30, min(tenure[i] * 30, 600) + 1)
        churn_dates.append(signup_dates[i] + timedelta(days=days_after))
    else:
        churn_dates.append(pd.NaT)

# Annual revenue at risk
annual_revenue = monthly_revenue * 12

# CLV estimate (simplified: monthly_rev * expected_lifetime_months * margin)
margin = 0.35
expected_lifetime = np.where(churned == 1, tenure, tenure + np.random.randint(12, 48, N))
clv = monthly_revenue * expected_lifetime * margin

df = pd.DataFrame({
    "customer_id": customer_ids,
    "segment": segments,
    "region": regions,
    "acquisition_channel": acquisition_channel,
    "signup_date": signup_dates,
    "tenure_months": tenure,
    "monthly_revenue_gbp": monthly_revenue.round(2),
    "annual_revenue_gbp": annual_revenue.round(2),
    "credit_score": credit_scores,
    "products_held": products_held,
    "support_tickets_90d": support_tickets,
    "digital_engagement_score": engagement_score.round(1),
    "avg_payment_delay_days": payment_delay,
    "estimated_clv_gbp": clv.round(2),
    "churned": churned,
    "churn_date": churn_dates
})

df.to_csv("/home/claude/churn-project/data/nexabank_customers.csv", index=False)

# Print summary stats
print(f"Total customers: {len(df)}")
print(f"Churned: {churned.sum()} ({churned.mean()*100:.1f}%)")
print(f"\nChurn rate by segment:")
print(df.groupby("segment")["churned"].mean().round(3))
print(f"\nTotal annual revenue at risk: £{df[df['churned']==1]['annual_revenue_gbp'].sum():,.0f}")
print(f"Mean monthly revenue (churned): £{df[df['churned']==1]['monthly_revenue_gbp'].mean():,.0f}")
print(f"Mean monthly revenue (retained): £{df[df['churned']==0]['monthly_revenue_gbp'].mean():,.0f}")
print(f"\nChurn rate by tenure bucket:")
df['tenure_bucket'] = pd.cut(df['tenure_months'], bins=[0,3,6,12,24,60], labels=['0-3m','3-6m','6-12m','12-24m','24-60m'])
print(df.groupby("tenure_bucket", observed=True)["churned"].mean().round(3))
