"""
Script for creating comprehensive visualizations of selected climate scenarios.

This script loads the scenarios selected by S3_find_scenarios.py and creates
multiple visualization types including:
1. Quantile space heatmaps with selected scenario traces
2. Monthly flow change comparisons
3. Scenario envelope plots

The quantile space visualization shows how the three selected scenarios
(low, medium, high) traverse through the distribution of all GCM projections.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from quantile_utils import create_quantile_matrix
from plotting_functions import plot_quantile_space_with_selected_scenarios
from scenario_utils import calculate_flow_weights, calculate_weighted_average_changes


def plot_scenario_monthly_comparison(selected_scenarios_df,
                                      all_scenarios_df,
                                      node,
                                      hydro_model,
                                      ssp_period,
                                      output_dir):
    """
    Create a plot comparing selected scenarios to the full ensemble.

    Parameters:
    -----------
    selected_scenarios_df : pd.DataFrame
        Selected scenarios (columns: low, medium, high)
    all_scenarios_df : pd.DataFrame
        All filtered scenarios from S3
    node : str
        Node name
    hydro_model : str
        Hydrologic model name (PRMS or VIC)
    ssp_period : str
        SSP period (e.g., '2020_2059')
    output_dir : str
        Output directory for figure
    """
    fig, ax = plt.subplots(figsize=(12, 7))

    # Plot envelope of all scenarios
    all_min = all_scenarios_df.min(axis=1)
    all_max = all_scenarios_df.max(axis=1)
    all_median = all_scenarios_df.median(axis=1)

    ax.fill_between(all_scenarios_df.index, all_min, all_max,
                    alpha=0.2, color='gray', label='Full ensemble range')
    ax.plot(all_scenarios_df.index, all_median, 'k--',
            linewidth=2, label='Ensemble median', alpha=0.7)

    # Plot selected scenarios
    scenario_colors = {
        'low': '#2166ac',
        'medium': '#fee090',
        'high': '#b2182b'
    }

    for scenario_type in selected_scenarios_df.columns:
        color = scenario_colors.get(scenario_type, 'gray')
        ax.plot(selected_scenarios_df.index,
                selected_scenarios_df[scenario_type],
                color=color, linewidth=3, marker='o', markersize=6,
                label=f'{scenario_type.capitalize()} scenario',
                zorder=10)

    # Styling
    ax.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax.set_xlabel('Month', fontsize=12, fontweight='bold')
    ax.set_ylabel('Flow Change (%) Relative to Baseline', fontsize=12, fontweight='bold')
    ax.set_title(f'{node.replace("_", " ").title()} - Selected Scenarios vs Full Ensemble\n' +
                 f'{hydro_model} | {ssp_period.replace("_", "-")}',
                 fontsize=14, fontweight='bold')

    # Month labels
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(month_labels)

    ax.legend(fontsize=10, loc='best')
    ax.grid(True, alpha=0.3)

    # Save
    fname = f'{output_dir}/{node}_selected_vs_ensemble_{hydro_model}_{ssp_period}.png'
    plt.tight_layout()
    plt.savefig(fname, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Saved: {fname}")


def plot_comprehensive_synthesis(selected_scenarios_df,
                                  all_scenarios_df,
                                  monthly_means_df,
                                  node,
                                  hydro_model,
                                  ssp_period,
                                  output_dir,
                                  weight_scheme='equal'):
    """
    Create a comprehensive three-panel synthesis figure showing:
    - Panel 1: Distribution of weighted average annual flow changes with selected scenarios
    - Panel 2: Selected scenarios in context of full ensemble (monthly % changes)
    - Panel 3: Absolute monthly flows (PUB baseline + climate-adjusted scenarios)

    Parameters:
    -----------
    selected_scenarios_df : pd.DataFrame
        Selected scenarios (columns: low, medium, high) with monthly % changes
    all_scenarios_df : pd.DataFrame
        All filtered scenarios from S3 with monthly % changes
    monthly_means_df : pd.DataFrame
        Monthly mean flows (rows=months, columns=datasets) for absolute values
    node : str
        Node name
    hydro_model : str
        Hydrologic model name (PRMS or VIC)
    ssp_period : str
        SSP period (e.g., '2020_2059')
    output_dir : str
        Output directory for figure
    weight_scheme : str
        Weighting scheme used in S3 ('equal', 'flow_weighted', or 'log_flow_weighted')
    """
    # Shared color scheme
    scenario_colors = {
        'low': '#2166ac',
        'medium': '#fee090',
        'high': '#b2182b'
    }
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # Calculate weights based on scheme
    if weight_scheme in ['flow_weighted', 'log_flow_weighted']:
        use_log = (weight_scheme == 'log_flow_weighted')
        weights, _ = calculate_flow_weights(monthly_means_df,
                                           baseline_col='pub_nhmv10_BC_withObsScaled',
                                           log_transform=use_log)
    else:
        weights = None

    # Calculate weighted average changes for all scenarios
    weighted_averages = calculate_weighted_average_changes(all_scenarios_df, weights=weights)

    # Get weighted averages for selected scenarios
    selected_weighted_avgs = {}
    for scenario_type in selected_scenarios_df.columns:
        # Find the GCM name from the selected scenarios
        scenario_monthly = selected_scenarios_df[scenario_type]
        # Match to the GCM in all_scenarios_df
        for gcm_name in all_scenarios_df.columns:
            if np.allclose(all_scenarios_df[gcm_name].values, scenario_monthly.values):
                selected_weighted_avgs[scenario_type] = weighted_averages[gcm_name]
                break

    # Create figure with 3 panels
    fig = plt.figure(figsize=(18, 6))
    gs = fig.add_gridspec(1, 3, wspace=0.3)

    # ===== PANEL 1: Distribution of weighted average changes =====
    ax1 = fig.add_subplot(gs[0])

    ax1.hist(weighted_averages.values, bins=30, alpha=0.7,
             color='gray', edgecolor='black', label='Ensemble')

    # Mark selected scenarios with vertical lines
    for scenario_type, weighted_avg in selected_weighted_avgs.items():
        ax1.axvline(weighted_avg, color=scenario_colors[scenario_type],
                   linewidth=2.5, linestyle='--',
                   label=f"{scenario_type.capitalize()}")

    ax1.set_xlabel('Weighted Average Flow Change (%)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Number of Scenarios', fontsize=11, fontweight='bold')
    ax1.set_title('(a) Distribution of Weighted Average Changes',
                  fontsize=12, fontweight='bold', loc='left')
    ax1.grid(True, alpha=0.3)

    # ===== PANEL 2: Monthly % changes (ensemble context) =====
    ax2 = fig.add_subplot(gs[1])

    # Plot envelope of all scenarios
    all_min = all_scenarios_df.min(axis=1)
    all_max = all_scenarios_df.max(axis=1)
    all_median = all_scenarios_df.median(axis=1)

    ax2.fill_between(range(1, 13), all_min.values, all_max.values,
                     alpha=0.2, color='gray', label='Ensemble range')
    ax2.plot(range(1, 13), all_median, 'k--',
            linewidth=2, label='Ensemble median', alpha=0.7)

    # Overlay selected scenarios
    for scenario_type in selected_scenarios_df.columns:
        ax2.plot(range(1, 13), selected_scenarios_df[scenario_type].values,
                marker='o', linewidth=3, markersize=6,
                color=scenario_colors[scenario_type],
                label=f"{scenario_type.capitalize()}")

    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax2.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Flow Change (%) vs Baseline', fontsize=11, fontweight='bold')
    ax2.set_title('(b) Monthly Flow Changes',
                  fontsize=12, fontweight='bold', loc='left')
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(month_labels, rotation=45, ha='right')
    ax2.grid(True, alpha=0.3)

    # ===== PANEL 3: Absolute monthly flows =====
    ax3 = fig.add_subplot(gs[2])

    # Get PUB baseline monthly flows
    pub_baseline = monthly_means_df['pub_nhmv10_BC_withObsScaled'].values

    # Plot PUB baseline
    ax3.plot(range(1, 13), pub_baseline, 'k-', linewidth=3,
            marker='s', markersize=7, label='Historic (PUB)', zorder=10)

    # Plot climate-adjusted scenarios (PUB baseline * (1 + % change / 100))
    for scenario_type in selected_scenarios_df.columns:
        pct_changes = selected_scenarios_df[scenario_type].values
        climate_adjusted = pub_baseline * (1 + pct_changes / 100)
        ax3.plot(range(1, 13), climate_adjusted,
                marker='o', linewidth=3, markersize=6,
                color=scenario_colors[scenario_type],
                label=f"{scenario_type.capitalize()} (future)")

    ax3.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Monthly Mean Flow (cfs)', fontsize=11, fontweight='bold')
    ax3.set_title('(c) Absolute Monthly Flows',
                  fontsize=12, fontweight='bold', loc='left')
    ax3.set_xticks(range(1, 13))
    ax3.set_xticklabels(month_labels, rotation=45, ha='right')
    ax3.grid(True, alpha=0.3)

    # yscale log
    ax3.set_yscale('log')

    # ===== Single unified legend =====
    # Collect all handles and labels from all three axes
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    handles3, labels3 = ax3.get_legend_handles_labels()

    # Create dictionary to deduplicate by label
    legend_dict = {}
    for h, l in zip(handles1 + handles2 + handles3, labels1 + labels2 + labels3):
        if l not in legend_dict:
            legend_dict[l] = h

    # Add legend to the figure (not individual axes)
    fig.legend(legend_dict.values(), legend_dict.keys(),
              loc='upper center', bbox_to_anchor=(0.5, -0.02),
              ncol=7, fontsize=10, frameon=True)

    # Overall title
    fig.suptitle(f'{node.replace("_", " ").title()} - Comprehensive Scenario Synthesis | ' +
                 f'{hydro_model} | {ssp_period.replace("_", "-")}',
                 fontsize=14, fontweight='bold', y=1.00)

    # Save
    fname = f'{output_dir}/{node}_comprehensive_synthesis_{hydro_model}_{ssp_period}.png'
    plt.savefig(fname, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Saved: {fname}")


def main():
    """
    Main execution function for scenario visualization.
    """
    # Configuration - should match S3_find_scenarios.py settings
    node = 'nyc_inflow'
    use_dataset_baseline = True
    hydro_model_source = 'PRMS'
    ssp_period = '2020_2059'
    weight_scheme = 'equal'  # Should match S3 setting: 'equal', 'flow_weighted', or 'log_flow_weighted'

    print(f"\n{'='*80}")
    print(f"CLIMATE SCENARIO VISUALIZATION")
    print(f"{'='*80}")
    print(f"Node:            {node}")
    print(f"Hydro Model:     {hydro_model_source}")
    print(f"Period:          {ssp_period}")
    print(f"Weight scheme:   {weight_scheme}")
    print(f"{'='*80}\n")

    # Set up paths
    fdir = './stats/diff_relative_to_dataset_baseline' if use_dataset_baseline else './stats/diff_relative_to_reconstruction'
    stats_dir = f'{fdir}/selected_scenarios'
    figures_dir = './figures/diff_relative_to_dataset_baseline/selected_scenarios' if use_dataset_baseline else './figures/diff_relative_to_reconstruction/selected_scenarios'
    os.makedirs(figures_dir, exist_ok=True)

    # Load selected scenarios from S3 output
    selected_scenarios_file = f'{stats_dir}/{node}_selected_scenarios_{hydro_model_source}_{ssp_period}.csv'

    if not os.path.exists(selected_scenarios_file):
        print(f"ERROR: Selected scenarios file not found: {selected_scenarios_file}")
        print(f"Please run S3_find_scenarios.py first.")
        return

    selected_scenarios_df = pd.read_csv(selected_scenarios_file, index_col=0)
    print(f"Loaded selected scenarios from: {selected_scenarios_file}")
    print(f"  Scenarios: {list(selected_scenarios_df.columns)}")

    # Load full monthly percentage change data
    monthly_prc_change_file = f'{fdir}/{node}_monthly_mean_prc_change_by_dataset_ssp_and_period.csv'
    monthly_prc_change = pd.read_csv(monthly_prc_change_file, index_col=0)

    # Filter for the same datasets used in S3
    filtered_datasets = [d for d in monthly_prc_change.columns
                        if hydro_model_source in d
                        and ('ssp245' in d or 'ssp370' in d)
                        and ssp_period in d]

    all_scenarios_df = monthly_prc_change[filtered_datasets]
    print(f"Loaded {len(filtered_datasets)} GCM scenarios for comparison")

    # Load monthly means for absolute flow values (Panel 3 of synthesis plot)
    monthly_means_file = f'./stats/datasets_{node}_monthly_means.csv'
    monthly_means_df = pd.read_csv(monthly_means_file, index_col=0)
    print(f"Loaded monthly means from: {monthly_means_file}")

    # Create quantile matrix from all filtered scenarios
    print(f"\nCreating quantile matrix...")
    quantile_matrix = create_quantile_matrix(all_scenarios_df)
    print(f"  Quantile matrix shape: {quantile_matrix.shape}")

    # Create visualizations
    print(f"\n{'='*80}")
    print(f"CREATING VISUALIZATIONS")
    print(f"{'='*80}\n")

    # 1. Quantile space visualization with selected scenarios
    print("1. Creating quantile space visualization...")
    quantile_fname = f'{figures_dir}/{node}_quantile_space_selected_{hydro_model_source}_{ssp_period}.png'
    plot_quantile_space_with_selected_scenarios(
        quantile_matrix,
        selected_scenarios_df,
        node,
        quantile_fname
    )
    print(f"   Saved: {quantile_fname}")

    # 2. Monthly comparison plot
    print("2. Creating monthly comparison plot...")
    plot_scenario_monthly_comparison(
        selected_scenarios_df,
        all_scenarios_df,
        node,
        hydro_model_source,
        ssp_period,
        figures_dir
    )

    # 3. Comprehensive synthesis figure (3 panels)
    print("3. Creating comprehensive synthesis figure...")
    plot_comprehensive_synthesis(
        selected_scenarios_df,
        all_scenarios_df,
        monthly_means_df,
        node,
        hydro_model_source,
        ssp_period,
        figures_dir,
        weight_scheme=weight_scheme
    )

    print(f"\n{'='*80}")
    print(f"VISUALIZATION COMPLETE")
    print(f"{'='*80}")
    print(f"\nAll figures saved to: {figures_dir}")


if __name__ == "__main__":
    main()
