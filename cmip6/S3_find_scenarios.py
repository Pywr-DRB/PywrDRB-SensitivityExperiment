"""
Simplified GCM scenario selection approach.

This script selects 3 representative GCM scenarios (high, medium, low) based on 
weighted average streamflow changes, without using anchor scenarios or quantile interpolation.

Approach:
1. Filter CMIP scenarios using IQR - reject any scenario that has outlier values in ANY month
2. Calculate weighted average streamflow change for each remaining scenario
3. Select scenarios with highest, median, and lowest weighted average changes

This provides a straightforward way to identify representative climate futures without 
the complexity of quantile space interpolation.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from scenario_utils import filter_scenarios_by_annual_change, calculate_flow_weights



def filter_scenarios_by_iqr(df, outlier_threshold=1.5, verbose=True):
    """
    Filter GCM scenarios by removing those with outlier values in ANY month using IQR method.
    
    A scenario is rejected if it has an outlier value in any single month.
    This ensures selected scenarios represent plausible futures across all months.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Rows = months (1-12), Columns = GCM scenarios, Values = flow change (%)
    outlier_threshold : float
        IQR multiplier for outlier bounds (default 1.5 = standard IQR method)
    verbose : bool
        Print filtering details
        
    Returns:
    --------
    pd.DataFrame: Filtered scenarios (only those without any outlier months)
    list: Names of rejected scenarios
    """
    outlier_scenarios = set()
    outlier_details = {}  # Track which months caused rejection
    
    # Check each month independently
    for month in df.index:
        month_data = df.loc[month].values
        
        # Calculate IQR bounds
        q1 = np.percentile(month_data, 25)
        q3 = np.percentile(month_data, 75)
        iqr = q3 - q1
        lower_bound = q1 - outlier_threshold * iqr
        upper_bound = q3 + outlier_threshold * iqr
        
        # Identify outliers in this month
        for scenario_name in df.columns:
            value = df.loc[month, scenario_name]
            if value < lower_bound or value > upper_bound:
                outlier_scenarios.add(scenario_name)
                if scenario_name not in outlier_details:
                    outlier_details[scenario_name] = []
                outlier_details[scenario_name].append(f"Month {month}: {value:.1f}% (bounds: {lower_bound:.1f} to {upper_bound:.1f})")
    
    # Create filtered dataframe
    valid_scenarios = [col for col in df.columns if col not in outlier_scenarios]
    df_filtered = df[valid_scenarios].copy()
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"IQR FILTERING RESULTS (threshold = {outlier_threshold})")
        print(f"{'='*80}")
        print(f"Total scenarios:     {len(df.columns)}")
        print(f"Outliers removed:    {len(outlier_scenarios)}")
        print(f"Remaining scenarios: {len(valid_scenarios)}")
        print(f"{'='*80}")
        
        if len(outlier_scenarios) > 0 and len(outlier_scenarios) <= 10:
            print("\nRejected scenarios and reasons:")
            for scenario in sorted(outlier_scenarios):
                print(f"\n  {scenario}:")
                for detail in outlier_details[scenario][:3]:  # Show first 3 months
                    print(f"    - {detail}")
                if len(outlier_details[scenario]) > 3:
                    print(f"    ... and {len(outlier_details[scenario]) - 3} more months")
    
    return df_filtered, list(outlier_scenarios)


def calculate_weighted_average_change(df, weights=None):
    """
    Calculate weighted average streamflow change for each scenario.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Rows = months, Columns = scenarios, Values = flow change (%)
    weights : np.ndarray or None
        Monthly weights (length = number of rows). If None, equal weights used.
        
    Returns:
    --------
    pd.Series: Weighted average change for each scenario, sorted
    """
    if weights is None:
        # Equal weights for all months
        weights = np.ones(len(df))
    else:
        weights = np.array(weights)
    
    # Normalize weights to sum to 1
    weights = weights / weights.sum()
    
    # Calculate weighted average for each scenario
    weighted_avg = {}
    for scenario in df.columns:
        values = df[scenario].values
        weighted_avg[scenario] = np.sum(values * weights)
    
    
    
    # Return as sorted Series
    weighted_avg_series = pd.Series(weighted_avg).sort_values()
    
    return weighted_avg_series


def select_representative_scenarios(weighted_averages, n_scenarios=3):
    """
    Select representative scenarios: lowest, median, and highest.
    
    Parameters:
    -----------
    weighted_averages : pd.Series
        Weighted average changes for each scenario (sorted)
    n_scenarios : int
        Number of scenarios to select (default 3: low, medium, high)
        
    Returns:
    --------
    dict: Selected scenarios with keys 'low', 'medium', 'high'
    """
    n_total = len(weighted_averages)
    
    if n_scenarios == 3:
        # Select lowest, median, highest
        low_idx = 0
        med_idx = n_total // 2
        high_idx = n_total - 1
        
        selected = {
            'low': {
                'name': weighted_averages.index[low_idx],
                'weighted_avg': weighted_averages.iloc[low_idx],
                'rank': 1,
                'percentile': 0
            },
            'medium': {
                'name': weighted_averages.index[med_idx],
                'weighted_avg': weighted_averages.iloc[med_idx],
                'rank': med_idx + 1,
                'percentile': 50
            },
            'high': {
                'name': weighted_averages.index[high_idx],
                'weighted_avg': weighted_averages.iloc[high_idx],
                'rank': n_total,
                'percentile': 100
            }
        }
    else:
        # Generalized selection for n scenarios
        selected = {}
        for i in range(n_scenarios):
            idx = int(i * (n_total - 1) / (n_scenarios - 1))
            selected[f'scenario_{i+1}'] = {
                'name': weighted_averages.index[idx],
                'weighted_avg': weighted_averages.iloc[idx],
                'rank': idx + 1,
                'percentile': (idx / (n_total - 1)) * 100
            }
    
    return selected


def plot_scenario_selection(df_filtered, weighted_averages, selected_scenarios,
                            node, output_dir, hydro_model, ssp_period):
    """
    Create two-panel visualization of scenario selection process.

    Creates a figure showing:
    - Panel 1: Distribution of weighted averages with selected scenarios highlighted
    - Panel 2: Selected scenarios in context of full ensemble range
    """
    fig = plt.figure(figsize=(16, 6))
    gs = fig.add_gridspec(1, 2, hspace=0.3, wspace=0.3)

    colors = {'low': '#2166ac', 'medium': '#fee090', 'high': '#b2182b'}
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Panel 1: Histogram of weighted averages
    ax1 = fig.add_subplot(gs[0])
    ax1.hist(weighted_averages.values, bins=30, alpha=0.7, color='gray', edgecolor='black')

    # Mark selected scenarios
    for scenario_type, info in selected_scenarios.items():
        ax1.axvline(info['weighted_avg'], color=colors[scenario_type],
                   linewidth=2.5, linestyle='--',
                   label=f"{scenario_type.capitalize()}: {info['weighted_avg']:.1f}%")

    ax1.set_xlabel('Weighted Average Flow Change (%)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Number of Scenarios', fontsize=12, fontweight='bold')
    ax1.set_title(f'(a) Distribution of Weighted Average Changes\n{len(weighted_averages)} Scenarios',
                  fontsize=13, fontweight='bold', loc='left')
    ax1.legend(fontsize=10, loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Panel 2: All scenarios envelope with selected overlaid
    ax2 = fig.add_subplot(gs[1])

    # Plot envelope of all filtered scenarios
    all_min = df_filtered.min(axis=1)
    all_max = df_filtered.max(axis=1)
    all_mean = df_filtered.mean(axis=1)

    ax2.fill_between(range(1, 13), all_min.values, all_max.values,
                     alpha=0.3, color='gray', label='Full range (all filtered scenarios)')
    ax2.plot(range(1, 13), all_mean.values, 'k--', linewidth=2,
            label='Mean of all scenarios', alpha=0.7)

    # Overlay selected scenarios
    for scenario_type, info in selected_scenarios.items():
        scenario_name = info['name']
        values = df_filtered[scenario_name].values
        ax2.plot(range(1, 13), values, marker='o', linewidth=3,
                markersize=9, label=f"{scenario_type.capitalize()} (selected)",
                color=colors[scenario_type])

    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax2.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Flow Change (%)', fontsize=12, fontweight='bold')
    ax2.set_title('(b) Selected Scenarios in Context of Full Ensemble',
                  fontsize=13, fontweight='bold', loc='left')
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(month_names)
    ax2.legend(fontsize=9, loc='best', ncol=2)
    ax2.grid(True, alpha=0.3)

    fig.suptitle(f'Scenario Selection: {node} | {hydro_model} | {ssp_period}',
                 fontsize=15, fontweight='bold', y=1.02)

    # Save figure
    fname = f'{output_dir}/{node}_scenario_selection_{hydro_model}_{ssp_period}.png'
    plt.savefig(fname, dpi=300, bbox_inches='tight')
    print(f"\nFigure saved: {fname}")
    plt.close()


def plot_rank_distribution(weighted_averages, selected_scenarios, node, 
                           output_dir, hydro_model, ssp_period):
    """
    Create a rank-ordered plot showing where selected scenarios fall.
    """
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Plot all scenarios as bars
    ranks = np.arange(1, len(weighted_averages) + 1)
    colors_bar = ['lightgray'] * len(weighted_averages)
    
    # Color selected scenarios
    color_map = {'low': '#2166ac', 'medium': '#fee090', 'high': '#b2182b'}
    for scenario_type, info in selected_scenarios.items():
        idx = info['rank'] - 1
        colors_bar[idx] = color_map[scenario_type]
    
    ax.bar(ranks, weighted_averages.values, color=colors_bar, edgecolor='black', linewidth=0.5)
    
    # Add horizontal line at zero
    ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.7)
    
    # Annotate selected scenarios
    for scenario_type, info in selected_scenarios.items():
        rank = info['rank']
        value = info['weighted_avg']
        ax.annotate(f"{scenario_type.capitalize()}\n{info['name']}\n{value:.1f}%",
                   xy=(rank, value), xytext=(0, 20 if value > 0 else -20),
                   textcoords='offset points', ha='center',
                   fontsize=8, fontweight='bold',
                   bbox=dict(boxstyle='round,pad=0.5', facecolor=color_map[scenario_type], alpha=0.7),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', lw=1.5))
    
    ax.set_xlabel('Scenario Rank (sorted by weighted average)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Weighted Average Flow Change (%)', fontsize=12, fontweight='bold')
    ax.set_title(f'Rank Distribution of Scenarios: {node} | {hydro_model} | {ssp_period}', 
                fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Save
    fname = f'{output_dir}/{node}_rank_distribution_{hydro_model}_{ssp_period}.png'
    plt.savefig(fname, dpi=300, bbox_inches='tight')
    print(f"Figure saved: {fname}")
    plt.close()


def main():
    """
    Main execution function.
    """
    # Configuration
    node = 'nyc_inflow'
    use_dataset_baseline = True
    hydro_model_source = 'PRMS'  # 'PRMS' or 'VIC' - based on S1 analysis, PRMS is better
    ssp_period = '2020_2059'  # or '2060_2099'

    # Weighting scheme: 'equal', 'flow_weighted', or 'log_flow_weighted'
    # 'equal': All months weighted equally
    # 'flow_weighted': Months weighted by their percentage of annual flow
    # 'log_flow_weighted': Log-transformed flow percentages (reduces dominance of high-flow months)
    weight_scheme = 'equal'  # 'flow_weighted' or 'log_flow_weighted' 

    # Filter out scenarios with negative annual flow changes
    # True: Only include scenarios with positive annual flow changes (consistent with climate projection literature)
    # False: Include all scenarios regardless of annual flow change direction
    require_positive_annual_change = True

    # Load data
    fdir = './stats/diff_relative_to_dataset_baseline' if use_dataset_baseline else './stats/diff_relative_to_reconstruction'
    monthly_prc_change = pd.read_csv(f'{fdir}/{node}_monthly_mean_prc_change_by_dataset_ssp_and_period.csv', index_col=0)
    
    # Filter datasets for specified hydro model and period
    # Include both SSP245 and SSP370 for broader ensemble
    filtered_datasets = [d for d in monthly_prc_change.columns 
                        if hydro_model_source in d 
                        and ('ssp245' in d or 'ssp370' in d) 
                        and ssp_period in d]
    
    df = monthly_prc_change[filtered_datasets]
    
    print(f"\n{'='*80}")
    print(f"SCENARIO SELECTION ANALYSIS")
    print(f"{'='*80}")
    print(f"Node:            {node}")
    print(f"Hydro Model:     {hydro_model_source}")
    print(f"Period:          {ssp_period}")
    print(f"SSP Scenarios:   245 & 370 (combined)")
    print(f"Total datasets:  {len(filtered_datasets)}")
    print(f"{'='*80}")
    
    # Step 1: Filter using IQR
    df_filtered, rejected = filter_scenarios_by_iqr(df, outlier_threshold=1.5, verbose=True)

    # Step 1b: Filter scenarios with negative annual flow changes (if enabled)
    if require_positive_annual_change:
        print(f"\n{'='*80}")
        print(f"FILTERING BY ANNUAL FLOW CHANGE DIRECTION")
        print(f"{'='*80}")

        # Load monthly means to calculate annual changes
        monthly_means_file = f'./stats/datasets_{node}_monthly_means.csv'
        monthly_means = pd.read_csv(monthly_means_file, index_col=0)

        # Use utility function to filter by annual change
        df_filtered, scenarios_rejected_annual = filter_scenarios_by_annual_change(
            df_filtered, monthly_means, require_positive=True, verbose=True
        )

        print(f"{'='*80}")

    # Step 2: Calculate weighted averages
    print(f"\n{'='*80}")
    print(f"CALCULATING WEIGHTED AVERAGES")
    print(f"{'='*80}")

    if weight_scheme in ['flow_weighted', 'log_flow_weighted']:
        # Load monthly means if not already loaded
        if 'monthly_means' not in locals():
            monthly_means_file = f'./stats/datasets_{node}_monthly_means.csv'
            monthly_means = pd.read_csv(monthly_means_file, index_col=0)

        # Use utility function to calculate flow weights
        use_log_transform = (weight_scheme == 'log_flow_weighted')
        weights, baseline_col = calculate_flow_weights(
            monthly_means,
            baseline_col='pub_nhmv10_BC_withObsScaled',
            log_transform=use_log_transform
        )

        scheme_name = 'Log-flow-weighted' if use_log_transform else 'Flow-weighted'
        print(f"Weight scheme: {scheme_name} (based on {baseline_col})")
        print(f"\nMonthly weights:")
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for month, weight in zip(month_names, weights):
            print(f"  {month}: {weight:6.4f} ({weight*100:5.2f}%)")
    else:
        # Equal weights
        weights = None
        print(f"Weight scheme: Equal weights for all 12 months")

    weighted_averages = calculate_weighted_average_change(df_filtered, weights=weights)
    
    print(f"\nWeighted average statistics:")
    print(f"  Minimum:  {weighted_averages.min():6.2f}%")
    print(f"  25th pct: {weighted_averages.quantile(0.25):6.2f}%")
    print(f"  Median:   {weighted_averages.median():6.2f}%")
    print(f"  75th pct: {weighted_averages.quantile(0.75):6.2f}%")
    print(f"  Maximum:  {weighted_averages.max():6.2f}%")
    
    # Step 3: Select representative scenarios
    selected_scenarios = select_representative_scenarios(weighted_averages, n_scenarios=3)
    
    print(f"\n{'='*80}")
    print(f"SELECTED REPRESENTATIVE SCENARIOS")
    print(f"{'='*80}")
    for scenario_type, info in selected_scenarios.items():
        print(f"\n{scenario_type.upper()}:")
        print(f"  GCM Scenario:    {info['name']}")
        print(f"  Weighted Avg:    {info['weighted_avg']:6.2f}%")
        print(f"  Rank:            {info['rank']} of {len(weighted_averages)}")
        print(f"  Percentile:      {info['percentile']:.0f}th")
    
    # Step 4: Save results
    # CSV outputs go to stats folder
    stats_output_dir = f'{fdir}/selected_scenarios'
    os.makedirs(stats_output_dir, exist_ok=True)

    # Figure outputs go to figures folder
    figures_output_dir = './figures/diff_relative_to_dataset_baseline/selected_scenarios' if use_dataset_baseline else './figures/diff_relative_to_reconstruction/selected_scenarios'
    os.makedirs(figures_output_dir, exist_ok=True)
    
    # Save selected scenario traces
    selected_traces = {}
    for scenario_type, info in selected_scenarios.items():
        selected_traces[scenario_type] = df_filtered[info['name']]
    
    selected_traces_df = pd.DataFrame(selected_traces)
    selected_traces_df.index.name = 'month'

    fname = f'{stats_output_dir}/{node}_selected_scenarios_{hydro_model_source}_{ssp_period}.csv'
    selected_traces_df.to_csv(fname)
    print(f"\n{'='*80}")
    print(f"Selected scenario traces saved: {fname}")

    # Save summary info
    summary_data = []
    for scenario_type, info in selected_scenarios.items():
        summary_data.append({
            'scenario_type': scenario_type,
            'gcm_name': info['name'],
            'weighted_avg_change': info['weighted_avg'],
            'rank': info['rank'],
            'total_scenarios': len(weighted_averages),
            'percentile': info['percentile']
        })

    summary_df = pd.DataFrame(summary_data)
    fname = f'{stats_output_dir}/{node}_selection_summary_{hydro_model_source}_{ssp_period}.csv'
    summary_df.to_csv(fname, index=False)
    print(f"Selection summary saved: {fname}")

    # Save all weighted averages for reference
    fname = f'{stats_output_dir}/{node}_all_weighted_averages_{hydro_model_source}_{ssp_period}.csv'
    weighted_averages.to_csv(fname, header=['weighted_avg_change'])
    print(f"All weighted averages saved: {fname}")

    # Step 5: Create visualizations
    print(f"\n{'='*80}")
    print(f"CREATING VISUALIZATIONS")
    print(f"{'='*80}")

    plot_scenario_selection(df_filtered, weighted_averages, selected_scenarios,
                           node, figures_output_dir, hydro_model_source, ssp_period)

    plot_rank_distribution(weighted_averages, selected_scenarios,
                          node, figures_output_dir, hydro_model_source, ssp_period)
    
    print(f"\n{'='*80}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
