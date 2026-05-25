import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from styles import colordict_by_gcm
from utils import dataset_settings


def plot_quantile_space_visualization(quantile_matrix, 
                                      scenario_definitions, 
                                      node, 
                                      fname):
    """
    Create a visualization showing the quantile space matrix with scenario paths.
    
    Parameters:
    -----------
    quantile_matrix : np.ndarray
        Shape (12, 100) - quantile values for each month
    scenario_definitions : dict
        Dictionary of scenario names and (jun_q, dec_q) tuples
    node : str
        Node name for title
    fdir : str
        Output directory
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create heatmap background showing flow change values
    # Use the quantile matrix transposed so quantiles are on y-axis
    heatmap_data = quantile_matrix.T  # Shape: (100, 12)
    
    # Plot heatmap
    # Create a DivergingNorm centered at 0
    norm = TwoSlopeNorm(vmin=heatmap_data.min(), vcenter=0, vmax=heatmap_data.max())

    im = ax.imshow(heatmap_data, aspect='auto', origin='lower', 
                   cmap='RdBu', norm=norm,
                   interpolation='bilinear',
                   extent=[0, 12, 0, 100])
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Flow Change (%)', pad=0.02)
    
    # Define colors for different scenario groups
    jun_colors = {
        10: '#2ca02c',   # green (Low)
        50: '#ff7f0e',   # orange (Med)
        90: '#d62728',   # red (High)
    }
    
    dec_linestyles = {
        10: ':',    # dotted (Low)
        50: '--',   # dashed (Med)
        90: '-',    # solid (High)
    }
    
    # Plot scenario paths
    for scenario_name, (jun_q, dec_q) in scenario_definitions.items():
        # Create path through quantile space
        months = np.arange(0, 13)
        quantiles = np.zeros(13)
        
        for month_idx in range(13):
            if month_idx <= 6:  # Jun through Dec
                weight = month_idx / 6
                quantiles[month_idx] = jun_q + weight * (dec_q - jun_q)
            else:  # Jan through Jun (wrapping back)
                weight = (month_idx - 6) / 6
                quantiles[month_idx] = dec_q + weight * (jun_q - dec_q)
        
        # Adjust months for plotting (0-12 for Jun-Jun)
        plot_months = months.copy()
        
        # Plot the path
        color = jun_colors[jun_q]
        linestyle = dec_linestyles[dec_q]
        linewidth = 2.5
        
        ax.plot(plot_months, quantiles, 
                color=color, linestyle=linestyle, linewidth=linewidth,
                alpha=0.9, zorder=10)
        
        # Add anchor points
        ax.scatter([0, 6], [jun_q, dec_q], 
                  color=color, s=100, zorder=11, 
                  edgecolors='white', linewidths=1.5)
    
    # Customize axes
    ax.set_xlabel('Month', fontsize=13, fontweight='bold')
    ax.set_ylabel('Quantile (%)', fontsize=13, fontweight='bold')
    ax.set_title(f'{node.replace("_", " ").title()} - Scenario Paths in Quantile Space\n' + 
                 'Linear Interpolation Between June and December Anchors',
                 fontsize=14, fontweight='bold', pad=20)
    
    # Set x-axis ticks and labels
    month_labels = ['Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 
                    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    ax.set_xticks(range(13))
    ax.set_xticklabels(month_labels, fontsize=10)
    
    # Set y-axis ticks
    ax.set_yticks([0, 10, 25, 50, 75, 90, 100])
    ax.set_ylim(0, 100)
    ax.set_xlim(0, 12)
    
    # Add grid
    ax.grid(True, alpha=0.3, linestyle=':', color='white', linewidth=0.5, zorder=5)
    
    # Create custom legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='#2ca02c', linewidth=2.5, label='June: Low (10th %ile)'),
        Line2D([0], [0], color='#ff7f0e', linewidth=2.5, label='June: Med (50th %ile)'),
        Line2D([0], [0], color='#d62728', linewidth=2.5, label='June: High (90th %ile)'),
        Line2D([0], [0], color='gray', linewidth=2.5, linestyle=':', label='Dec: Low (10th %ile)'),
        Line2D([0], [0], color='gray', linewidth=2.5, linestyle='--', label='Dec: Med (50th %ile)'),
        Line2D([0], [0], color='gray', linewidth=2.5, linestyle='-', label='Dec: High (90th %ile)'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9, 
             framealpha=0.95, edgecolor='black')
    
    # Save figure
    plt.tight_layout()
    plt.savefig(fname, dpi=300, bbox_inches='tight')


def plot_quantile_space_with_gcm_traces(quantile_matrix, 
                                        df_reordered_quantiles,
                                        node, 
                                        fname):
    """
    Create visualization showing quantile space matrix with individual GCM traces.
    
    Parameters:
    -----------
    quantile_matrix : np.ndarray
        Shape (12, 100) - quantile values for each month
    df_reordered_quantiles : pd.DataFrame
        13 rows × N columns, with quantile values (0-100) for each GCM
    node : str
        Node name for title
    fdir : str
        Output directory
    """
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Create heatmap background
    heatmap_data = quantile_matrix.T  # Shape: (100, 12)
    
    # Plot heatmap with diverging colormap centered at 0
    norm = TwoSlopeNorm(vmin=heatmap_data.min(), vcenter=0, vmax=heatmap_data.max())
    im = ax.imshow(heatmap_data, aspect='auto', origin='lower', 
                   cmap='RdBu', norm=norm,
                   interpolation='bilinear',
                   extent=[0, 12, 0, 100])
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Flow Change (%)', pad=0.02)
    
    # Plot individual GCM traces (use len(df_reordered_quantiles) for x-coords)
    for col in df_reordered_quantiles.columns:
        ax.plot(range(len(df_reordered_quantiles)), df_reordered_quantiles[col].values,
                color='black', linewidth=0.8, alpha=0.3, zorder=10)
    
    # Customize axes
    ax.set_xlabel('Month', fontsize=13, fontweight='bold')
    ax.set_ylabel('Quantile (%)', fontsize=13, fontweight='bold')
    ax.set_title(f'{node.replace("_", " ").title()} - GCM Traces in Quantile Space\n' + 
                 'Individual Model Trajectories Through Quantile Matrix',
                 fontsize=14, fontweight='bold', pad=20)
    
    # Set x-axis ticks and labels
    month_labels = ['Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 
                    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
    ax.set_xticks(range(13))
    ax.set_xticklabels(month_labels, fontsize=10)
    
    # Set y-axis ticks
    ax.set_yticks([0, 10, 25, 50, 75, 90, 100])
    ax.set_ylim(0, 100)
    ax.set_xlim(0, 12)
    
    # Add grid
    ax.grid(True, alpha=0.3, linestyle=':', color='white', linewidth=0.5, zorder=5)
    
    # Add text annotation
    ax.text(0.02, 0.98, f'N = {len(df_reordered_quantiles.columns)} models', 
            transform=ax.transAxes, fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Save figure
    plt.tight_layout()
    plt.savefig(fname, dpi=300, bbox_inches='tight')


def plot_monthly_stat_lines(df, 
                            ax=None, 
                            title=None, 
                            labelby=None,
                            fill_between=False,
                            fill_color='grey',
                            colordict={}, 
                            markerdict={},
                            linestyledict={}):
    """
    Given a dataframe of monthly data, create a line plot, 
    where the x-axis is the month and the y-axis is the value.
    """
    
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 6))
    
    if not fill_between:
        
        for dataset in df.columns:

            color = colordict.get(dataset, 'lightgrey')
            marker = markerdict.get(dataset, 'o')
            ls = linestyledict.get(dataset, '-')

            if labelby and dataset in dataset_settings:
                label = dataset_settings[dataset][labelby]
            else:
                label = dataset

            ax.plot(df.index, df[dataset], label=label, 
                    color=color, marker=marker, linestyle=ls)
    else:
        all_data = df.values

        max_vals = all_data.max(axis=1)
        min_vals = all_data.min(axis=1)
        median_vals = np.median(all_data, axis=1)

        ax.fill_between(df.index, min_vals, max_vals, color=fill_color, alpha=0.2)
        ax.plot(df.index, median_vals, color=fill_color, label='Median')

    ax.set_title(title)
    return ax


def plot_monthly_stat_panel_by_ssp_and_start_year(df, datasets,
                                                  hist_datasets,
                                                  colorby='gcm',
                                                  labelby='gcm',
                                                  markerdict={},
                                                  fill_between=False,
                                                  add_horz_at=None,
                                                  ylabel='Difference in Monthly Mean Flow (%)\nRelative to Reconstruction',
                                                  fname=None):
    """
    Creates 6-panel plot:
    - 3 rows: historic, ssp245, ssp370
    - 2 columns: one for each start year (2020 and 2060)
    
    The ax in position (0, 0) is the historic data.
    The ax in position (0, 1) will house the legend
    
    
    """
    # Drop nan, inf, and -inf values
    df = df.dropna(how='all')
    df = df[~df.isin([np.inf, -np.inf]).any(axis=1)]
    
    
    fig, axs = plt.subplots(3, 2, figsize=(12, 16), sharex=True)

    for i, ssp in enumerate(['historic', 'ssp245', 'ssp370']):
        
        for j, start_year in enumerate([2020, 2060]):
            ax = axs[i, j]
            
            # If (0,0), use historic datasets
            if i == 0 and j == 0:
                
                filtered_datasets = hist_datasets
                
                # We want to keep these out:
                # - wrf1960s*
                # - wrf2050*
                # - obs
                # - pub_*
                filtered_datasets = [d for d in filtered_datasets if
                                        not d.startswith('wrf1960s') and
                                        not d.startswith('wrf2050') and
                                        not d.startswith('obs') and
                                        not d.startswith('pub_')]
            
            # If (0,1), use the legend ax
            elif i == 0 and j == 1:
                ax.axis('off')
                continue
            
            else:            
                # Filter datasets for this SSP and start year
                filtered_datasets = [
                    ds for ds in datasets if
                    dataset_settings[ds]['ssp'] == ssp and
                    dataset_settings[ds]['start_year'] == start_year
                ]
            # Plot each dataset
            plot_monthly_stat_lines(
                df[filtered_datasets],
                ax=ax,
                labelby=labelby,
                fill_between=fill_between,
                colordict=colordict_by_gcm,
                markerdict=markerdict,
                linestyledict={}
            )
            
            # Set x and y limits
            ax.set_xlim(df.index.min(), df.index.max())
            ax.set_ylim(df.min().min()*1.1, 
                        df.max().max() * 1.1)

            # add horizontal line if specified
            if add_horz_at is not None:
                ax.axhline(y=add_horz_at, color='grey', linestyle='--')
                
            # Add subplot title
            if start_year == 2020 and i == 0:
                period = '1983-2016'
            elif start_year == 2020 and i > 0:
                period = '2020-2059'
            elif start_year == 2060:
                period = '2060-2099'
            ax.set_title(f"{ssp} ({period})", fontsize=14)
            
            # Add x and y labels
            if i == 2:
                ax.set_xlabel('Month', fontsize=12)
            if j == 0:
                ax.set_ylabel(ylabel, fontsize=12)

    # Make a single legend for all datasets
    all_handles, all_labels = [], []
    for ax in axs.flat:
        handles, labels = ax.get_legend_handles_labels()
        all_handles.extend(handles)
        all_labels.extend(labels)
    
    # Remove duplicates
    unique_labels = list(dict.fromkeys(all_labels))
    unique_handles = [h for h, l in zip(all_handles, all_labels) if
                        l in unique_labels]
    
    # Make the legend cover the (0,1) ax
    axs[0, 1].legend(unique_handles, unique_labels,
                     loc='center', bbox_to_anchor=(0.5, 0.5),
                     ncol=1, fontsize='small', title='Dataset')
    
            
    plt.tight_layout()
    if fname:
        plt.savefig(fname)
    plt.close()
    return axs

def plot_quantile_space_with_selected_scenarios(quantile_matrix,
                                                 selected_scenarios_df,
                                                 node,
                                                 fname):
    """
    Create quantile space heatmap with selected GCM scenarios overlaid.

    This visualization shows:
    1. Background: Heatmap of quantile matrix showing flow changes across quantile space
    2. Overlay: Three selected scenarios (low, medium, high) as traces through quantile space

    Parameters:
    -----------
    quantile_matrix : np.ndarray
        Shape (12, 100) - quantile values for each month
    selected_scenarios_df : pd.DataFrame
        Rows = months (1-12), Columns = scenario types (low, medium, high), Values = flow change (%)
    node : str
        Node name for labeling
    fname : str
        Output filename for the plot
    """
    from quantile_utils import get_scenario_quantile_trajectory

    fig, ax = plt.subplots(figsize=(12, 8))

    # Create heatmap background showing flow change values
    heatmap_data = quantile_matrix.T  # Shape: (100, 12)

    # Plot heatmap with diverging colormap centered at 0
    norm = TwoSlopeNorm(vmin=heatmap_data.min(), vcenter=0, vmax=heatmap_data.max())
    im = ax.imshow(heatmap_data, aspect='auto', origin='lower',
                   cmap='RdBu', norm=norm,
                   interpolation='bilinear',
                   extent=[0, 12, 0, 100])

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, label='Flow Change (%)', pad=0.02)

    # Define colors for scenario types
    scenario_colors = {
        'low': '#2166ac',      # blue
        'medium': '#fee090',   # yellow
        'high': '#b2182b'      # red
    }

    # Plot each selected scenario
    for scenario_type in selected_scenarios_df.columns:
        # Get flow values for this scenario
        flow_values = selected_scenarios_df[scenario_type].values

        # Convert to quantile trajectory
        quantile_trajectory = get_scenario_quantile_trajectory(flow_values, quantile_matrix)

        # Plot the trajectory
        months_plot = np.arange(0, 12)
        color = scenario_colors.get(scenario_type, 'gray')

        ax.plot(months_plot, quantile_trajectory,
                color=color, linewidth=3.5,
                alpha=0.9, zorder=10,
                label=f'{scenario_type.capitalize()} scenario')

        # Add markers at key months (Jan, Jun, Dec)
        key_months_indices = [0, 5, 11]  # Jan, Jun, Dec
        ax.scatter([months_plot[m] for m in key_months_indices],
                  [quantile_trajectory[m] for m in key_months_indices],
                  color=color, s=150, zorder=11,
                  edgecolors='white', linewidths=2)

    # Customize axes
    ax.set_xlabel('Month', fontsize=13, fontweight='bold')
    ax.set_ylabel('Quantile (%)', fontsize=13, fontweight='bold')
    ax.set_title(f'{node.replace("_", " ").title()} - Selected Climate Scenarios in Quantile Space\n' +
                 'Representative GCM Projections Spanning Low, Medium, and High Futures',
                 fontsize=14, fontweight='bold', pad=20)

    # Set x-axis ticks and labels
    month_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    ax.set_xticks(range(12))
    ax.set_xticklabels(month_labels, fontsize=10)

    # Set y-axis ticks
    ax.set_yticks([0, 10, 25, 50, 75, 90, 100])
    ax.set_ylim(0, 100)
    ax.set_xlim(0, 11)

    # Add grid
    ax.grid(True, alpha=0.3, linestyle=':', color='white', linewidth=0.5, zorder=5)

    # Legend
    ax.legend(loc='upper left', fontsize=11,
             framealpha=0.95, edgecolor='black')

    # Save figure
    plt.tight_layout()
    plt.savefig(fname, dpi=300, bbox_inches='tight')
    plt.close()
