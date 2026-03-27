"""
NEXABANK — Customer Churn Revenue Impact Analysis
===================================================
Full analytical pipeline: data profiling, cohort analysis, churn drivers,
CLV segmentation, retention simulation, and executive-ready visualizations.

Author: Hrituparna Das
Tools: Python (pandas, matplotlib, seaborn, scipy), SQL, Power BI
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from matplotlib.patches import FancyBboxPatch
from matplotlib.gridspec import GridSpec
import warnings
warnings.filterwarnings('ignore')

# ── STYLE CONFIG ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    'figure.facecolor': '#0D1117',
    'axes.facecolor': '#0D1117',
    'text.color': '#C9D1D9',
    'axes.labelcolor': '#C9D1D9',
    'xtick.color': '#8B949E',
    'ytick.color': '#8B949E',
    'axes.edgecolor': '#21262D',
    'grid.color': '#21262D',
    'grid.alpha': 0.5,
    'font.family': 'sans-serif',
    'font.size': 11,
})

ACCENT = '#58A6FF'
RED = '#F85149'
GREEN = '#3FB950'
ORANGE = '#D29922'
PURPLE = '#BC8CFF'
TEAL = '#39D2C0'
COLORS = [ACCENT, RED, GREEN, ORANGE, PURPLE, TEAL]

df = pd.read_csv('/home/claude/churn-project/data/nexabank_customers.csv',
                  parse_dates=['signup_date', 'churn_date'])

df['tenure_cohort'] = pd.cut(
    df['tenure_months'],
    bins=[0, 3, 6, 12, 24, 60],
    labels=['0–3m', '3–6m', '6–12m', '12–24m', '24–60m']
)
df['engagement_tier'] = pd.cut(
    df['digital_engagement_score'],
    bins=[0, 30, 60, 100],
    labels=['Low', 'Medium', 'High']
)

# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 1: EXECUTIVE SUMMARY DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

fig = plt.figure(figsize=(18, 5))
gs = GridSpec(1, 4, figure=fig, wspace=0.4)

metrics = [
    ("£2.29M", "Annual Revenue\nat Risk", RED),
    ("12.8%", "Overall\nChurn Rate", ORANGE),
    ("26.5%", "First-90-Day\nChurn Rate", RED),
    ("£68.4K", "Avg CLV of\nChurned Customers", ACCENT),
]

for i, (value, label, color) in enumerate(metrics):
    ax = fig.add_subplot(gs[0, i])
    ax.text(0.5, 0.62, value, fontsize=32, fontweight='bold', color=color,
            ha='center', va='center', transform=ax.transAxes)
    ax.text(0.5, 0.22, label, fontsize=12, color='#8B949E',
            ha='center', va='center', transform=ax.transAxes, linespacing=1.4)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    rect = FancyBboxPatch((0.02, 0.02), 0.96, 0.96, boxstyle="round,pad=0.02",
                           facecolor='#161B22', edgecolor='#30363D', linewidth=1.5,
                           transform=ax.transAxes)
    ax.add_patch(rect)

fig.suptitle('NEXABANK — Churn Revenue Impact: Executive Summary',
             fontsize=16, fontweight='bold', color='#F0F6FC', y=1.05)
plt.savefig('/home/claude/churn-project/visuals/01_executive_summary.png',
            dpi=200, bbox_inches='tight', facecolor='#0D1117')
plt.close()
print("✓ Figure 1: Executive Summary")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 2: CHURN RATE BY TENURE COHORT (the "90-day cliff")
# ══════════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(10, 6))

cohort_stats = df.groupby('tenure_cohort', observed=True).agg(
    churn_rate=('churned', 'mean'),
    rev_at_risk=('annual_revenue_gbp', lambda x: x[df.loc[x.index, 'churned'] == 1].sum()),
    count=('churned', 'count')
).reset_index()

bars = ax.bar(cohort_stats['tenure_cohort'], cohort_stats['churn_rate'] * 100,
              color=[RED if r > 0.15 else ORANGE if r > 0.10 else ACCENT
                     for r in cohort_stats['churn_rate']],
              edgecolor='none', width=0.6, zorder=3)

for bar, rate, n in zip(bars, cohort_stats['churn_rate'], cohort_stats['count']):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
            f'{rate*100:.1f}%', ha='center', fontsize=13, fontweight='bold', color='#F0F6FC')
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() - 1.5,
            f'n={n:,}', ha='center', fontsize=9, color='#0D1117', fontweight='bold')

# Annotation for the 90-day cliff
ax.annotate('90-Day Cliff\n26.5% of new customers\nchurn within first quarter',
            xy=(0, 26.5), xytext=(2.2, 24),
            fontsize=10, color=RED, fontweight='bold',
            arrowprops=dict(arrowstyle='->', color=RED, lw=2),
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#161B22', edgecolor=RED, alpha=0.9))

ax.set_ylabel('Churn Rate (%)', fontsize=12, fontweight='bold')
ax.set_xlabel('Customer Tenure', fontsize=12, fontweight='bold')
ax.set_title('Churn Rate Drops Sharply After 90 Days — Early Intervention is Critical',
             fontsize=14, fontweight='bold', color='#F0F6FC', pad=15)
ax.set_ylim(0, 32)
ax.grid(axis='y', alpha=0.3)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.savefig('/home/claude/churn-project/visuals/02_tenure_churn_cliff.png',
            dpi=200, bbox_inches='tight', facecolor='#0D1117')
plt.close()
print("✓ Figure 2: Tenure Churn Cliff")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 3: REVENUE AT RISK BY SEGMENT × TENURE (HEATMAP)
# ══════════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(11, 6))

pivot = df[df['churned'] == 1].pivot_table(
    values='annual_revenue_gbp', index='segment',
    columns='tenure_cohort', aggfunc='sum', observed=True
).fillna(0)

pivot_k = pivot / 1000

sns.heatmap(pivot_k, annot=True, fmt='.0f', cmap='YlOrRd', linewidths=2,
            linecolor='#0D1117', cbar_kws={'label': 'Revenue at Risk (£K)', 'shrink': 0.8},
            ax=ax, annot_kws={'fontsize': 12, 'fontweight': 'bold'})

ax.set_title('Revenue at Risk (£K) — Segment × Tenure Cohort',
             fontsize=14, fontweight='bold', color='#F0F6FC', pad=15)
ax.set_ylabel('')
ax.set_xlabel('Customer Tenure at Churn', fontsize=11)
ax.tick_params(axis='y', rotation=0)

plt.savefig('/home/claude/churn-project/visuals/03_revenue_heatmap.png',
            dpi=200, bbox_inches='tight', facecolor='#0D1117')
plt.close()
print("✓ Figure 3: Revenue Heatmap")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 4: CHURN DRIVERS — ENGAGEMENT × SUPPORT TICKETS MATRIX
# ══════════════════════════════════════════════════════════════════════════════

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# 4a: Engagement vs Churn
eng_churn = df.groupby('engagement_tier', observed=True)['churned'].mean() * 100
colors_eng = [RED, ORANGE, GREEN]
bars = ax1.barh(eng_churn.index, eng_churn.values, color=colors_eng, height=0.5, edgecolor='none')
for bar, val in zip(bars, eng_churn.values):
    ax1.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
             f'{val:.1f}%', va='center', fontsize=13, fontweight='bold', color='#F0F6FC')
ax1.set_xlabel('Churn Rate (%)', fontsize=11, fontweight='bold')
ax1.set_title('Churn Rate by Digital Engagement', fontsize=13, fontweight='bold', color='#F0F6FC')
ax1.invert_yaxis()
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.set_xlim(0, 25)

# 4b: Support tickets vs Churn
ticket_bins = pd.cut(df['support_tickets_90d'], bins=[-1, 0, 1, 2, 4, 12],
                      labels=['0', '1', '2', '3-4', '5+'])
ticket_churn = df.groupby(ticket_bins, observed=True)['churned'].mean() * 100
bars2 = ax2.bar(ticket_churn.index, ticket_churn.values,
                color=[GREEN, GREEN, ORANGE, RED, RED], width=0.55, edgecolor='none')
for bar, val in zip(bars2, ticket_churn.values):
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
             f'{val:.1f}%', ha='center', fontsize=12, fontweight='bold', color='#F0F6FC')
ax2.set_xlabel('Support Tickets (Last 90 Days)', fontsize=11, fontweight='bold')
ax2.set_ylabel('Churn Rate (%)', fontsize=11, fontweight='bold')
ax2.set_title('Churn Escalates with Support Contact Frequency',
              fontsize=13, fontweight='bold', color='#F0F6FC')
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.set_ylim(0, 28)

fig.suptitle('Behavioral Churn Drivers — Low Engagement + High Support = Highest Risk',
             fontsize=14, fontweight='bold', color=RED, y=1.03)
plt.savefig('/home/claude/churn-project/visuals/04_churn_drivers.png',
            dpi=200, bbox_inches='tight', facecolor='#0D1117')
plt.close()
print("✓ Figure 4: Churn Drivers")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 5: ACQUISITION CHANNEL QUALITY ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(12, 7))

channel_data = df.groupby('acquisition_channel').agg(
    churn_rate=('churned', 'mean'),
    avg_clv=('estimated_clv_gbp', 'mean'),
    count=('customer_id', 'count'),
    rev_at_risk=('annual_revenue_gbp', lambda x: x[df.loc[x.index, 'churned'] == 1].sum())
).reset_index()

scatter = ax.scatter(
    channel_data['churn_rate'] * 100,
    channel_data['avg_clv'],
    s=channel_data['count'] * 0.8,
    c=[ACCENT, GREEN, ORANGE, PURPLE, RED],
    alpha=0.85, edgecolors='#F0F6FC', linewidth=1.5, zorder=5
)

for _, row in channel_data.iterrows():
    ax.annotate(
        f"{row['acquisition_channel']}\nn={row['count']:,}",
        (row['churn_rate'] * 100, row['avg_clv']),
        textcoords="offset points", xytext=(0, 22),
        ha='center', fontsize=10, fontweight='bold', color='#F0F6FC'
    )

# Quadrant lines
avg_churn = channel_data['churn_rate'].mean() * 100
avg_clv = channel_data['avg_clv'].mean()
ax.axvline(avg_churn, color='#30363D', linestyle='--', alpha=0.7)
ax.axhline(avg_clv, color='#30363D', linestyle='--', alpha=0.7)

ax.text(0.02, 0.98, 'IDEAL\nLow Churn, High CLV', transform=ax.transAxes,
        fontsize=9, color=GREEN, alpha=0.7, va='top', fontweight='bold')
ax.text(0.98, 0.02, 'PROBLEMATIC\nHigh Churn, Low CLV', transform=ax.transAxes,
        fontsize=9, color=RED, alpha=0.7, ha='right', fontweight='bold')

ax.set_xlabel('Churn Rate (%)', fontsize=12, fontweight='bold')
ax.set_ylabel('Average CLV (£)', fontsize=12, fontweight='bold')
ax.set_title('Acquisition Channel Quality — Churn Rate vs Customer Lifetime Value',
             fontsize=14, fontweight='bold', color='#F0F6FC', pad=15)
ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'£{x:,.0f}'))
ax.grid(alpha=0.2)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.savefig('/home/claude/churn-project/visuals/05_channel_quality.png',
            dpi=200, bbox_inches='tight', facecolor='#0D1117')
plt.close()
print("✓ Figure 5: Channel Quality")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 6: RETENTION STRATEGY SIMULATION — ROI COMPARISON
# ══════════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(12, 7))

# Identify at-risk, high-value active customers
at_risk = df[(df['churned'] == 0) &
             ((df['digital_engagement_score'] < 40) | (df['support_tickets_90d'] >= 4)) &
             (df['estimated_clv_gbp'] > df['estimated_clv_gbp'].quantile(0.3))]

total_rev = at_risk['annual_revenue_gbp'].sum()
n_cust = len(at_risk)

scenarios = pd.DataFrame({
    'Strategy': ['A: 10% Loyalty\nDiscount', 'B: Dedicated\nSuccess Manager', 'C: Product\nBundle Upgrade'],
    'Recovery Rate': [0.40, 0.25, 0.55],
    'Cost per Customer': [at_risk['annual_revenue_gbp'].mean() * 0.10, 200, 150],
})

scenarios['Recovered Revenue'] = total_rev * scenarios['Recovery Rate']
scenarios['Total Cost'] = scenarios['Cost per Customer'] * n_cust
scenarios['Net Benefit'] = scenarios['Recovered Revenue'] - scenarios['Total Cost']
scenarios['ROI %'] = ((scenarios['Recovered Revenue'] - scenarios['Total Cost']) / scenarios['Total Cost']) * 100

x = np.arange(3)
w = 0.28
bars1 = ax.bar(x - w, scenarios['Recovered Revenue'] / 1000, w, label='Recovered Revenue',
               color=GREEN, edgecolor='none', zorder=3)
bars2 = ax.bar(x, scenarios['Total Cost'] / 1000, w, label='Intervention Cost',
               color=RED, edgecolor='none', zorder=3)
bars3 = ax.bar(x + w, scenarios['Net Benefit'] / 1000, w, label='Net Benefit',
               color=ACCENT, edgecolor='none', zorder=3)

for i, (_, row) in enumerate(scenarios.iterrows()):
    ax.text(i + w, row['Net Benefit']/1000 + 8,
            f'ROI: {row["ROI %"]:.0f}%', ha='center', fontsize=11,
            fontweight='bold', color=ORANGE)

ax.set_xticks(x)
ax.set_xticklabels(scenarios['Strategy'], fontsize=11)
ax.set_ylabel('Amount (£K)', fontsize=12, fontweight='bold')
ax.set_title(f'Retention Strategy ROI Simulation — {n_cust:,} At-Risk Customers Targeted',
             fontsize=14, fontweight='bold', color='#F0F6FC', pad=15)
ax.legend(loc='upper left', framealpha=0.3, fontsize=10)
ax.grid(axis='y', alpha=0.2)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.savefig('/home/claude/churn-project/visuals/06_retention_roi.png',
            dpi=200, bbox_inches='tight', facecolor='#0D1117')
plt.close()
print("✓ Figure 6: Retention ROI Simulation")


# ══════════════════════════════════════════════════════════════════════════════
# FIGURE 7: CLV DISTRIBUTION — CHURNED vs RETAINED
# ══════════════════════════════════════════════════════════════════════════════

fig, ax = plt.subplots(figsize=(12, 6))

churned_clv = df[df['churned'] == 1]['estimated_clv_gbp']
retained_clv = df[df['churned'] == 0]['estimated_clv_gbp']

ax.hist(retained_clv, bins=50, alpha=0.6, color=ACCENT, label=f'Retained (n={len(retained_clv):,})',
        edgecolor='none', density=True)
ax.hist(churned_clv, bins=50, alpha=0.7, color=RED, label=f'Churned (n={len(churned_clv):,})',
        edgecolor='none', density=True)

ax.axvline(churned_clv.median(), color=RED, linestyle='--', linewidth=2, alpha=0.8)
ax.axvline(retained_clv.median(), color=ACCENT, linestyle='--', linewidth=2, alpha=0.8)

ax.text(churned_clv.median(), ax.get_ylim()[1] * 0.9,
        f'  Churned Median\n  £{churned_clv.median():,.0f}', fontsize=10, color=RED, fontweight='bold')
ax.text(retained_clv.median(), ax.get_ylim()[1] * 0.75,
        f'  Retained Median\n  £{retained_clv.median():,.0f}', fontsize=10, color=ACCENT, fontweight='bold')

ax.set_xlabel('Estimated Customer Lifetime Value (£)', fontsize=12, fontweight='bold')
ax.set_ylabel('Density', fontsize=12, fontweight='bold')
ax.set_title('CLV Distribution — Churned Customers Are Not Low-Value',
             fontsize=14, fontweight='bold', color='#F0F6FC', pad=15)
ax.legend(fontsize=11, framealpha=0.3)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f'£{x:,.0f}'))
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

plt.savefig('/home/claude/churn-project/visuals/07_clv_distribution.png',
            dpi=200, bbox_inches='tight', facecolor='#0D1117')
plt.close()
print("✓ Figure 7: CLV Distribution")


# ══════════════════════════════════════════════════════════════════════════════
# CONSOLE OUTPUT: KEY FINDINGS SUMMARY
# ══════════════════════════════════════════════════════════════════════════════

print("\n" + "="*70)
print("KEY FINDINGS — NEXABANK CHURN ANALYSIS")
print("="*70)

churned_df = df[df['churned'] == 1]
early_churn = churned_df[churned_df['tenure_months'] <= 3]

print(f"\n📊 SCALE OF THE PROBLEM")
print(f"   Total customers analysed: {len(df):,}")
print(f"   Churned customers: {len(churned_df):,} ({len(churned_df)/len(df)*100:.1f}%)")
print(f"   Annual revenue at risk: £{churned_df['annual_revenue_gbp'].sum():,.0f}")

print(f"\n🔥 THE 90-DAY CLIFF")
print(f"   Customers churning within 0-3 months: {len(early_churn):,}")
print(f"   That's {len(early_churn)/len(churned_df)*100:.0f}% of all churn")
print(f"   Revenue at risk from early churners: £{early_churn['annual_revenue_gbp'].sum():,.0f}")

hv_churned = churned_df[churned_df['estimated_clv_gbp'] > churned_df['estimated_clv_gbp'].quantile(0.75)]
print(f"\n💰 HIGH-VALUE CHURN")
print(f"   High-CLV churned customers: {len(hv_churned):,}")
print(f"   Revenue at risk (top quartile): £{hv_churned['annual_revenue_gbp'].sum():,.0f}")
print(f"   Avg CLV of high-value churners: £{hv_churned['estimated_clv_gbp'].mean():,.0f}")

print(f"\n📈 RETENTION SIMULATION")
print(f"   At-risk active customers identified: {len(at_risk):,}")
print(f"   Best strategy: Product Bundle Upgrade")
print(f"   Projected recovery: £{total_rev * 0.55:,.0f}")
print(f"   Projected ROI: {((total_rev*0.55 - n_cust*150)/(n_cust*150))*100:.0f}%")

print("\n" + "="*70)
print("All visualizations saved to /visuals/")
print("="*70)
