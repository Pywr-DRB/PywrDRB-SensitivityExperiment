"""
Script for visualizing annual flow changes across GCM scenarios.

This script creates visualizations showing how climate scenarios affect annual
streamflow volumes relative to their respective dataset baselines, emphasizing:
1. Overall increase in annual flows under climate change
2. Range of uncertainty across GCM ensemble
3. Position of selected scenarios within the ensemble

The visualization supports the narrative that despite increased annual flows,
seasonal changes create water supply challenges requiring careful scenario selection.
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scenario_utils import calculate_annual_pct_changes


def plot_annual_flow_comparison(all_scenarios_pct_change,
                                 selected_scenarios_pct_change,
                                 selected_scenario_names,
                                 node,
                                 hydro_model,
                                 ssp_period,
                                 output_dir):
    """
    Create two-panel visualization of annual flow percent changes.

    Panel 1: Box plot and swarm showing distribution of annual flow changes
    Panel 2: CDF showing distribution and percentile positions of selected scenarios

    Parameters:
    -----------
    all_scenarios_pct_change : pd.Series
        Percent changes for all filtered GCM scenarios
    selected_scenarios_pct_change : dict
        Percent changes for selected scenarios {scenario_type: value}
    selected_scenario_names : dict
        GCM names for selected scenarios {scenario_type: name}
    node : str
        Node name
    hydro_model : str
        Hydrologic model name
    ssp_period : str
        SSP period
    output_dir : str
        Output directory
    """
    fig = plt.figure(figsize=(14, 6))
    gs = fig.add_gridspec(1, 2, wspace=0.25)

    scenario_colors = {
        'low': '#2166ac',
        'medium': '#fee090',
        'high': '#b2182b'
    }

    # PANEL 1: Box plot with individual points
    ax1 = fig.add_subplot(gs[0])

    # Create box plot
    bp = ax1.boxplot(all_scenarios_pct_change.values, positions=[1], widths=0.5,
                      patch_artist=True,
                      boxprops=dict(facecolor='lightgray', alpha=0.6),
                      medianprops=dict(color='black', linewidth=2.5),
                      whiskerprops=dict(linewidth=1.5),
                      capprops=dict(linewidth=1.5))

    # Add scatter points for all scenarios
    x_jitter = np.random.normal(1, 0.04, size=len(all_scenarios_pct_change))
    ax1.scatter(x_jitter, all_scenarios_pct_change.values,
               alpha=0.3, s=30, color='gray', zorder=1)

    # Overlay selected scenarios
    for scenario_type, pct_change in selected_scenarios_pct_change.items():
        color = scenario_colors[scenario_type]
        ax1.scatter([1], [pct_change],
                   s=300, color=color, edgecolors='black', linewidth=2.5,
                   zorder=10, label=f'{scenario_type.capitalize()}',
                   marker='D')  # Diamond marker

    # Add reference line at 0%
    ax1.axhline(0, color='black', linestyle='--', linewidth=1.5, alpha=0.7, zorder=0)

    # Styling
    ax1.set_xlim(0.5, 1.5)
    ax1.set_xticks([])
    ax1.set_ylabel('Change in Annual Mean Flow (%)\nRelative to Dataset Baseline',
                   fontsize=12, fontweight='bold')
    ax1.set_title('(a) Distribution of Annual Flow Changes',
                  fontsize=13, fontweight='bold', loc='left')
    ax1.grid(True, alpha=0.3, axis='y')

    # Add summary statistics as text
    median_val = np.median(all_scenarios_pct_change.values)
    q25 = np.percentile(all_scenarios_pct_change.values, 25)
    q75 = np.percentile(all_scenarios_pct_change.values, 75)

    stats_text = f"N = {len(all_scenarios_pct_change)} GCM scenarios\n"
    stats_text += f"Median: {median_val:+.1f}%\n"
    stats_text += f"IQR: {q25:+.1f}% to {q75:+.1f}%\n"
    stats_text += f"Range: {all_scenarios_pct_change.min():+.1f}% to {all_scenarios_pct_change.max():+.1f}%"

    ax1.text(0.98, 0.02, stats_text, transform=ax1.transAxes,
            fontsize=9, verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='gray'))

    # PANEL 2: Cumulative Distribution Function
    ax2 = fig.add_subplot(gs[1])

    # Sort ensemble values for CDF
    sorted_ensemble = np.sort(all_scenarios_pct_change.values)
    cdf_y = np.arange(1, len(sorted_ensemble) + 1) / len(sorted_ensemble) * 100

    # Plot ensemble CDF
    ax2.plot(sorted_ensemble, cdf_y, linewidth=3, color='gray',
            label='GCM Ensemble', zorder=1)

    # Add reference line at 0%
    ax2.axvline(0, color='black', linestyle='--', linewidth=1.5,
               label='No change', alpha=0.7, zorder=2)

    # Add selected scenarios
    for scenario_type, pct_change in selected_scenarios_pct_change.items():
        color = scenario_colors[scenario_type]
        # Find percentile
        percentile = (sorted_ensemble < pct_change).sum() / len(sorted_ensemble) * 100

        ax2.axvline(pct_change, color=color, linewidth=2.5, alpha=0.8,
                   linestyle=':', zorder=3)
        ax2.scatter([pct_change], [percentile], s=300, color=color,
                   edgecolors='black', linewidth=2.5, zorder=10,
                   marker='D',
                   label=f'{scenario_type.capitalize()} ({percentile:.0f}th percentile)')

    ax2.set_xlabel('Change in Annual Mean Flow (%)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Cumulative Probability (%)', fontsize=12, fontweight='bold')
    ax2.set_title('(b) Cumulative Distribution of Annual Changes',
                  fontsize=13, fontweight='bold', loc='left')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 100)

    # Single unified legend at the bottom
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()

    # Combine handles and labels, removing duplicates by label
    # Use dict to maintain order while removing duplicates
    legend_dict = {}
    for h, l in zip(handles1 + handles2, labels1 + labels2):
        if l not in legend_dict:
            legend_dict[l] = h

    all_labels = list(legend_dict.keys())
    all_handles = list(legend_dict.values())

    # Create legend below the figure
    fig.legend(all_handles, all_labels, loc='lower center',
              bbox_to_anchor=(0.5, -0.05), ncol=5, fontsize=10,
              frameon=True, edgecolor='black')

    # Overall title
    fig.suptitle(f'{node.replace("_", " ").title()} - Annual Flow Changes Relative to Dataset Baselines | {hydro_model} | {ssp_period.replace("_", "-")}',
                fontsize=14, fontweight='bold', y=1.00)

    # Save
    fname = f'{output_dir}/{node}_annual_flow_comparison_{hydro_model}_{ssp_period}.png'
    plt.tight_layout()
    plt.savefig(fname, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"Saved: {fname}")


def main():
    """
    Main execution function.
    """
    # Configuration - should match S3_find_scenarios.py
    node = 'nyc_inflow'
    use_dataset_baseline = True
    hydro_model_source = 'PRMS'
    ssp_period = '2020_2059'

    print(f"\n{'='*80}")
    print(f"ANNUAL FLOW ANALYSIS")
    print(f"{'='*80}")
    print(f"Node:            {node}")
    print(f"Hydro Model:     {hydro_model_source}")
    print(f"Period:          {ssp_period}")
    print(f"{'='*80}\n")

    # Set up paths
    fdir = './stats/diff_relative_to_dataset_baseline' if use_dataset_baseline else './stats/diff_relative_to_reconstruction'
    stats_dir = f'{fdir}/selected_scenarios'
    figures_dir = './figures/diff_relative_to_dataset_baseline/selected_scenarios' if use_dataset_baseline else './figures/diff_relative_to_reconstruction/selected_scenarios'
    os.makedirs(figures_dir, exist_ok=True)

    # Load monthly means
    monthly_means_file = f'./stats/datasets_{node}_monthly_means.csv'
    monthly_means = pd.read_csv(monthly_means_file, index_col=0)

    print(f"Loaded monthly means: {monthly_means.shape}")

    # Filter for GCM scenarios matching S3 criteria
    filtered_scenarios = [d for d in monthly_means.columns
                         if hydro_model_source in d
                         and ('ssp245' in d or 'ssp370' in d)
                         and ssp_period in d]

    print(f"GCM ensemble size: {len(filtered_scenarios)}")

    # Calculate percent changes from dataset baselines
    all_scenarios_pct_change = calculate_annual_pct_changes(monthly_means, filtered_scenarios)

    print(f"\nAnnual flow changes relative to dataset baselines:")
    print(f"  Median: {all_scenarios_pct_change.median():+.1f}%")
    print(f"  Range: {all_scenarios_pct_change.min():+.1f}% to {all_scenarios_pct_change.max():+.1f}%")

    # Load selected scenarios
    selected_scenarios_file = f'{stats_dir}/{node}_selected_scenarios_{hydro_model_source}_{ssp_period}.csv'
    selection_summary_file = f'{stats_dir}/{node}_selection_summary_{hydro_model_source}_{ssp_period}.csv'

    if not os.path.exists(selected_scenarios_file):
        print(f"\nERROR: Selected scenarios not found. Please run S3_find_scenarios.py first.")
        return

    selection_summary = pd.read_csv(selection_summary_file)

    # Get GCM names for selected scenarios
    selected_scenario_names = {}
    for _, row in selection_summary.iterrows():
        selected_scenario_names[row['scenario_type']] = row['gcm_name']

    # Get percent changes for selected scenarios
    selected_scenarios_pct_change = {}
    for scenario_type, gcm_name in selected_scenario_names.items():
        if gcm_name in all_scenarios_pct_change.index:
            selected_scenarios_pct_change[scenario_type] = all_scenarios_pct_change[gcm_name]

    print(f"\nSelected scenario annual flow changes:")
    for scenario_type, pct_change in selected_scenarios_pct_change.items():
        print(f"  {scenario_type.capitalize():8s}: {pct_change:+.1f}%")

    # Create visualization
    print(f"\n{'='*80}")
    print(f"CREATING VISUALIZATION")
    print(f"{'='*80}\n")

    plot_annual_flow_comparison(
        all_scenarios_pct_change,
        selected_scenarios_pct_change,
        selected_scenario_names,
        node,
        hydro_model_source,
        ssp_period,
        figures_dir
    )

    print(f"\n{'='*80}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
