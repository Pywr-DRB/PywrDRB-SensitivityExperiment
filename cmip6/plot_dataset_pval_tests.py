import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

# Load annual statistics
df_annual = pd.read_csv('historic_annual_flow_stats_robust.txt', sep=',')
df_annual['hydrologic_model'] = df_annual['dataset'].str.split('_').str[0]

# Load monthly statistics
df_monthly = pd.read_csv('historic_monthly_flow_stats_robust.txt', sep=',')
df_monthly['hydrologic_model'] = df_monthly['dataset'].str.split('_').str[0]

# Create month names for better labeling
month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
df_monthly['month_name'] = df_monthly['month'].map(dict(zip(range(1, 13), month_names)))

# Set up the figure with 4 panels (2x2 grid)
fig, axes = plt.subplots(2, 2, figsize=(18, 14))

# Annual plots (top row)
# Panel 1: Annual Rank P-Values
sns.barplot(data=df_annual, x='hydrologic_model', y='rank_p_value', ax=axes[0, 0])
axes[0, 0].set_xticklabels(axes[0, 0].get_xticklabels(), rotation=45)
axes[0, 0].set_title('Annual Rank P-Value by Hydrologic Model')
axes[0, 0].set_ylabel('Rank P-Value')
axes[0, 0].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')
axes[0, 0].legend()

# Panel 2: Annual Levene P-Values
sns.barplot(data=df_annual, x='hydrologic_model', y='levene_p_value', ax=axes[0, 1])
axes[0, 1].set_xticklabels(axes[0, 1].get_xticklabels(), rotation=45)
axes[0, 1].set_title('Annual Levene P-Value by Hydrologic Model')
axes[0, 1].set_ylabel('Levene P-Value')
axes[0, 1].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')
axes[0, 1].legend()

# Monthly plots (bottom row) - showing ALL individual points
# Panel 3: Monthly Rank P-Values - Strip plot showing all datasets
sns.stripplot(data=df_monthly, x='month_name', y='rank_p_value', hue='hydrologic_model',
              ax=axes[1, 0], size=6, alpha=0.8, dodge=True)
axes[1, 0].set_title('Monthly Rank P-Values by Hydrologic Model (All Datasets)')
axes[1, 0].set_xlabel('Month')
axes[1, 0].set_ylabel('Rank P-Value')
axes[1, 0].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')
axes[1, 0].tick_params(axis='x', rotation=45)
axes[1, 0].legend(bbox_to_anchor=(1.05, 1), loc='upper left')

# Panel 4: Monthly Levene P-Values - Strip plot showing all datasets
sns.stripplot(data=df_monthly, x='month_name', y='levene_p_value', hue='hydrologic_model',
              ax=axes[1, 1], size=6, alpha=0.8, dodge=True)
axes[1, 1].set_title('Monthly Levene P-Values by Hydrologic Model (All Datasets)')
axes[1, 1].set_xlabel('Month')
axes[1, 1].set_ylabel('Levene P-Value')
axes[1, 1].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')
axes[1, 1].tick_params(axis='x', rotation=45)
axes[1, 1].legend(bbox_to_anchor=(1.05, 1), loc='upper left')

plt.tight_layout()
plt.savefig('hydrologic_model_p_values_annual_monthly.png', dpi=300, bbox_inches='tight')
plt.show()

# Additional detailed monthly plots: Box plots showing distributions
fig, axes = plt.subplots(2, 1, figsize=(20, 12))

# Monthly Rank P-Values as box plot
sns.boxplot(data=df_monthly, x='month_name', y='rank_p_value', hue='hydrologic_model', ax=axes[0])
axes[0].set_xlabel('Month')
axes[0].set_ylabel('Rank P-Value')
axes[0].set_title('Monthly Rank P-Values Distribution by Hydrologic Model')
axes[0].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')
axes[0].tick_params(axis='x', rotation=45)
axes[0].legend(bbox_to_anchor=(1.05, 1), loc='upper left')

# Monthly Levene P-Values as box plot
sns.boxplot(data=df_monthly, x='month_name', y='levene_p_value', hue='hydrologic_model', ax=axes[1])
axes[1].set_xlabel('Month')
axes[1].set_ylabel('Levene P-Value')
axes[1].set_title('Monthly Levene P-Values Distribution by Hydrologic Model')
axes[1].axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='p=0.05')
axes[1].tick_params(axis='x', rotation=45)
axes[1].legend(bbox_to_anchor=(1.05, 1), loc='upper left')

plt.tight_layout()
plt.savefig('hydrologic_model_monthly_distributions.png', dpi=300, bbox_inches='tight')
plt.show()

# Create summary plots for each hydrologic model separately
models = df_monthly['hydrologic_model'].unique()
n_models = len(models)
fig, axes = plt.subplots(n_models, 2, figsize=(16, 4*n_models))

if n_models == 1:
    axes = axes.reshape(1, -1)

for i, model in enumerate(models):
    model_data = df_monthly[df_monthly['hydrologic_model'] == model]
    
    # Rank p-values for this model
    sns.stripplot(data=model_data, x='month_name', y='rank_p_value', 
                  ax=axes[i, 0], size=8, alpha=0.8)
    axes[i, 0].set_title(f'{model} - Monthly Rank P-Values')
    axes[i, 0].set_xlabel('Month')
    axes[i, 0].set_ylabel('Rank P-Value')
    axes[i, 0].axhline(y=0.05, color='red', linestyle='--', alpha=0.7)
    axes[i, 0].tick_params(axis='x', rotation=45)
    
    # Levene p-values for this model
    sns.stripplot(data=model_data, x='month_name', y='levene_p_value', 
                  ax=axes[i, 1], size=8, alpha=0.8)
    axes[i, 1].set_title(f'{model} - Monthly Levene P-Values')
    axes[i, 1].set_xlabel('Month')
    axes[i, 1].set_ylabel('Levene P-Value')
    axes[i, 1].axhline(y=0.05, color='red', linestyle='--', alpha=0.7)
    axes[i, 1].tick_params(axis='x', rotation=45)

plt.tight_layout()
plt.savefig('hydrologic_model_individual_monthly.png', dpi=300, bbox_inches='tight')
plt.show()

# Print detailed summary statistics
print("Annual Statistics Summary:")
print("=" * 50)
print(df_annual.groupby('hydrologic_model')[['rank_p_value', 'levene_p_value']].describe())

print("\n\nMonthly Statistics Summary:")
print("=" * 50)
print("Summary across all datasets by hydrologic model and month:")
monthly_summary = df_monthly.groupby(['hydrologic_model', 'month_name'])[['rank_p_value', 'levene_p_value']].describe()
print(monthly_summary)

print(f"\nDataset Details:")
print(f"Total monthly data points: {df_monthly.shape[0]}")
print(f"Number of hydrologic models: {df_monthly['hydrologic_model'].nunique()}")
print(f"Number of datasets per model:")
print(df_monthly.groupby('hydrologic_model')['dataset'].nunique().sort_values(ascending=False))
print(f"\nHydrologic models: {sorted(df_monthly['hydrologic_model'].unique())}")

# Summary of performance (p-values > 0.05 = good performance)
print("\n\nPerformance Summary (% of datasets with p > 0.05):")
print("=" * 60)
performance_summary = df_monthly.groupby(['hydrologic_model']).apply(
    lambda x: pd.Series({
        'rank_good_pct': (x['rank_p_value'] > 0.05).mean() * 100,
        'levene_good_pct': (x['levene_p_value'] > 0.05).mean() * 100
    })
).round(1)
print(performance_summary)