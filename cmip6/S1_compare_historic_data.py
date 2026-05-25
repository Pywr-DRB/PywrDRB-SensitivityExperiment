"""
This script is used to compare historic streamflow datasets from the CMIP downscaled, 
to determine which model configurations match historic monthly patterns sufficiently well. 

In this comparison, we want to ignore all of the ssp<x> scenarios and focus only on historic data. 
The goal is to figure out which hydrologic model (PRMS vs VIC5) is better and reproducing historic seasonal flow patterns. 

Specifically, I want to consider the following datasets:
- PRMS_RAPID_Daymet2019_1980_2019
- VIC5_RAPID_Daymet2019_v20200704D_1980_2019

With historic flows from:
- pub_nhmv10_BC_withObsScaled

The analysis will be based on aggregate NYC inflows, since those are well gauged in the historic record 
and relevant for the model. 

Statistical comparisons include:
1. Monthly mean flow patterns (climatology)
2. Seasonal timing analysis (peak flow timing)
3. Monthly coefficient of variation (interannual variability)
4. Nash-Sutcliffe Efficiency (NSE) - overall fit
5. Percent Bias (PBIAS) - systematic errors
6. Monthly correlation coefficients - temporal pattern matching
7. Root Mean Square Error (RMSE) by month

"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pywrdrb
from config import DATASET_NAMES


if __name__ == "__main__":
    ### Load data through pywrdrb API    
    # Setup pathnavigator
    pn_config = pywrdrb.get_pn_config()
    for dataset in DATASET_NAMES:
        f = f"pywrdrb/inputs/{dataset}"
        pn_config[f"flows/{dataset}"] = os.path.abspath(f)

    pywrdrb.load_pn_config(pn_config)

    pn = pywrdrb.get_pn_object()
    sc_flows = list(pn.sc.to_dict().keys())
    flowtype_opts = [i.replace("flows/", "") for i in sc_flows]


    flowtypes = [
        'PRMS_RAPID_Daymet2019_1980_2019',
        'VIC5_RAPID_Daymet2019_v20200704D_1980_2019',
        'pub_nhmv10_BC_withObsScaled'
    ]
    
    data = pywrdrb.Data(results_sets=['major_flow'],)
    data.load_hydrologic_model_flow(flowtypes)
    
    # The data object will contain the gage_flow_mgd DataFrames for each flowtype
    loaded_datasets = data.major_flow.keys()
    pywrdrb_nodes = data.major_flow[flowtypes[0]][0].columns.tolist()
    print(f"Loaded flows at {len(pywrdrb_nodes)} nodes for {len(loaded_datasets)} datasets.")

    # For each of the loaded datasets, calculate NYC aggregate inflow
    # this is the sum of flows for:
    nyc_inflow_gages = ["01425000", "01417000", "01436000"]

    # save in data object for later
    for dataset in loaded_datasets:
        df = data.major_flow[dataset][0]
        nyc_inflow = df[nyc_inflow_gages].sum(axis=1)
        data.major_flow[dataset][0]['nyc_inflow'] = nyc_inflow
    
    
    ### Extract NYC inflow timeseries for analysis
    obs_data = data.major_flow['pub_nhmv10_BC_withObsScaled'][0]['nyc_inflow']
    prms_data = data.major_flow['PRMS_RAPID_Daymet2019_1980_2019'][0]['nyc_inflow']
    vic_data = data.major_flow['VIC5_RAPID_Daymet2019_v20200704D_1980_2019'][0]['nyc_inflow']
    
    # Find common date range for fair comparison
    common_dates = obs_data.index.intersection(prms_data.index).intersection(vic_data.index)
    
    # If common dates are <1983-10-01, then restrict to after that due to model warmup
    common_dates = common_dates[common_dates >= pd.Timestamp('1983-10-01')]
    
    obs = obs_data.loc[common_dates]
    prms = prms_data.loc[common_dates]
    vic = vic_data.loc[common_dates]
    
    print(f"\nAnalyzing {len(common_dates)} days from {common_dates[0]} to {common_dates[-1]}")
    
    
    ### ANALYSIS 1: Monthly Mean Climatology
    obs_monthly = obs.groupby(obs.index.month).mean()
    prms_monthly = prms.groupby(prms.index.month).mean()
    vic_monthly = vic.groupby(vic.index.month).mean()
    
    # Calculate errors
    prms_monthly_error = ((prms_monthly - obs_monthly) / obs_monthly * 100)
    vic_monthly_error = ((vic_monthly - obs_monthly) / obs_monthly * 100)
    
    print("\n=== MONTHLY MEAN FLOW ANALYSIS ===")
    print("Month | Observed | PRMS | VIC | PRMS Error% | VIC Error%")
    for month in range(1, 13):
        print(f"{month:5d} | {obs_monthly[month]:8.1f} | {prms_monthly[month]:8.1f} | "
              f"{vic_monthly[month]:8.1f} | {prms_monthly_error[month]:11.1f} | {vic_monthly_error[month]:10.1f}")
    
    
    ### ANALYSIS 2: Coefficient of Variation by Month
    obs_cv = obs.groupby(obs.index.month).std() / obs.groupby(obs.index.month).mean()
    prms_cv = prms.groupby(prms.index.month).std() / prms.groupby(prms.index.month).mean()
    vic_cv = vic.groupby(vic.index.month).std() / vic.groupby(vic.index.month).mean()
    
    cv_prms_error = np.abs(prms_cv - obs_cv)
    cv_vic_error = np.abs(vic_cv - obs_cv)
    
    print("\n=== MONTHLY COEFFICIENT OF VARIATION ===")
    print("Month | Observed | PRMS | VIC | PRMS AbsErr | VIC AbsErr")
    for month in range(1, 13):
        print(f"{month:5d} | {obs_cv[month]:8.3f} | {prms_cv[month]:8.3f} | "
              f"{vic_cv[month]:8.3f} | {cv_prms_error[month]:11.3f} | {cv_vic_error[month]:10.3f}")
    
    
    ### ANALYSIS 3: Nash-Sutcliffe Efficiency (NSE)
    def calculate_nse(observed, modeled):
        numerator = np.sum((observed - modeled) ** 2)
        denominator = np.sum((observed - np.mean(observed)) ** 2)
        return 1 - (numerator / denominator)
    
    nse_prms = calculate_nse(obs.values, prms.values)
    nse_vic = calculate_nse(obs.values, vic.values)
    
    print("\n=== NASH-SUTCLIFFE EFFICIENCY (NSE) ===")
    print(f"PRMS NSE: {nse_prms:.4f}")
    print(f"VIC NSE:  {nse_vic:.4f}")
    print(f"Better model: {'PRMS' if nse_prms > nse_vic else 'VIC'}")
    
    
    ### ANALYSIS 4: Percent Bias (PBIAS)
    pbias_prms = np.sum(prms.values - obs.values) / np.sum(obs.values) * 100
    pbias_vic = np.sum(vic.values - obs.values) / np.sum(obs.values) * 100
    
    print("\n=== PERCENT BIAS (PBIAS) ===")
    print(f"PRMS PBIAS: {pbias_prms:6.2f}%")
    print(f"VIC PBIAS:  {pbias_vic:6.2f}%")
    print(f"Lower absolute bias: {'PRMS' if abs(pbias_prms) < abs(pbias_vic) else 'VIC'}")
    
    
    ### ANALYSIS 5: Monthly Correlation Coefficients
    monthly_corr_prms = []
    monthly_corr_vic = []
    
    for month in range(1, 13):
        obs_month = obs[obs.index.month == month]
        prms_month = prms[prms.index.month == month]
        vic_month = vic[vic.index.month == month]
        
        monthly_corr_prms.append(np.corrcoef(obs_month, prms_month)[0, 1])
        monthly_corr_vic.append(np.corrcoef(obs_month, vic_month)[0, 1])
    
    print("\n=== MONTHLY CORRELATION COEFFICIENTS ===")
    print("Month | PRMS r | VIC r")
    for month in range(1, 13):
        print(f"{month:5d} | {monthly_corr_prms[month-1]:6.3f} | {monthly_corr_vic[month-1]:6.3f}")
    print(f"Average: {np.mean(monthly_corr_prms):.3f} | {np.mean(monthly_corr_vic):.3f}")
    
    
    ### ANALYSIS 6: RMSE by Month
    monthly_rmse_prms = []
    monthly_rmse_vic = []
    
    for month in range(1, 13):
        obs_month = obs[obs.index.month == month]
        prms_month = prms[prms.index.month == month]
        vic_month = vic[vic.index.month == month]
        
        monthly_rmse_prms.append(np.sqrt(np.mean((obs_month - prms_month) ** 2)))
        monthly_rmse_vic.append(np.sqrt(np.mean((obs_month - vic_month) ** 2)))
    
    print("\n=== ROOT MEAN SQUARE ERROR (RMSE) BY MONTH ===")
    print("Month | PRMS RMSE | VIC RMSE")
    for month in range(1, 13):
        print(f"{month:5d} | {monthly_rmse_prms[month-1]:9.1f} | {monthly_rmse_vic[month-1]:9.1f}")
    
    
    ### ANALYSIS 7: Peak Flow Timing
    obs_annual_peaks = obs.groupby(obs.index.year).idxmax()
    prms_annual_peaks = prms.groupby(prms.index.year).idxmax()
    vic_annual_peaks = vic.groupby(vic.index.year).idxmax()
    
    obs_peak_month = obs_annual_peaks.dt.month.mean()
    prms_peak_month = prms_annual_peaks.dt.month.mean()
    vic_peak_month = vic_annual_peaks.dt.month.mean()
    
    print("\n=== AVERAGE PEAK FLOW TIMING ===")
    print(f"Observed average peak month: {obs_peak_month:.1f}")
    print(f"PRMS average peak month:     {prms_peak_month:.1f}")
    print(f"VIC average peak month:      {vic_peak_month:.1f}")
    print(f"PRMS timing error: {abs(prms_peak_month - obs_peak_month):.1f} months")
    print(f"VIC timing error:  {abs(vic_peak_month - obs_peak_month):.1f} months")
    
    
    ### ANALYSIS 8: Mean Monthly Fraction of Annual Flow
    # Calculate monthly flow as % of annual total for each year, then average across years
    obs_monthly_frac = []
    prms_monthly_frac = []
    vic_monthly_frac = []
    
    for month in range(1, 13):
        # For each year, calculate what fraction of that year's total flow occurred in this month
        obs_annual_totals = obs.groupby(obs.index.year).sum()
        prms_annual_totals = prms.groupby(prms.index.year).sum()
        vic_annual_totals = vic.groupby(vic.index.year).sum()
        
        obs_month_totals = obs[obs.index.month == month].groupby(obs[obs.index.month == month].index.year).sum()
        prms_month_totals = prms[prms.index.month == month].groupby(prms[prms.index.month == month].index.year).sum()
        vic_month_totals = vic[vic.index.month == month].groupby(vic[vic.index.month == month].index.year).sum()
        
        obs_monthly_frac.append((obs_month_totals / obs_annual_totals * 100).mean())
        prms_monthly_frac.append((prms_month_totals / prms_annual_totals * 100).mean())
        vic_monthly_frac.append((vic_month_totals / vic_annual_totals * 100).mean())
    
    obs_monthly_frac = np.array(obs_monthly_frac)
    prms_monthly_frac = np.array(prms_monthly_frac)
    vic_monthly_frac = np.array(vic_monthly_frac)
    
    prms_frac_error = np.abs(prms_monthly_frac - obs_monthly_frac)
    vic_frac_error = np.abs(vic_monthly_frac - obs_monthly_frac)
    
    print("\n=== MEAN MONTHLY FRACTION OF ANNUAL FLOW (%) ===")
    print("Month | Observed | PRMS | VIC | PRMS AbsErr | VIC AbsErr")
    for month in range(1, 13):
        idx = month - 1
        print(f"{month:5d} | {obs_monthly_frac[idx]:8.2f} | {prms_monthly_frac[idx]:8.2f} | "
              f"{vic_monthly_frac[idx]:8.2f} | {prms_frac_error[idx]:11.2f} | {vic_frac_error[idx]:10.2f}")
    
    print(f"\nMean Absolute Error: {prms_frac_error.mean():.2f} | {vic_frac_error.mean():.2f}")
    print(f"Better seasonal distribution: {'PRMS' if prms_frac_error.mean() < vic_frac_error.mean() else 'VIC'}")
    
    # Calculate RMSE for monthly fractions
    prms_frac_rmse = np.sqrt(np.mean((prms_monthly_frac - obs_monthly_frac) ** 2))
    vic_frac_rmse = np.sqrt(np.mean((vic_monthly_frac - obs_monthly_frac) ** 2))
    print(f"RMSE: {prms_frac_rmse:.2f} | {vic_frac_rmse:.2f}")
    
    
    ### SUMMARY METRICS
    print("\n" + "="*60)
    print("OVERALL PERFORMANCE SUMMARY")
    print("="*60)
    
    # Count which model performs better in each metric
    metrics_summary = {
        'NSE': ('PRMS', nse_prms) if nse_prms > nse_vic else ('VIC', nse_vic),
        'PBIAS (lower abs)': ('PRMS', abs(pbias_prms)) if abs(pbias_prms) < abs(pbias_vic) else ('VIC', abs(pbias_vic)),
        'Avg Correlation': ('PRMS', np.mean(monthly_corr_prms)) if np.mean(monthly_corr_prms) > np.mean(monthly_corr_vic) else ('VIC', np.mean(monthly_corr_vic)),
        'Avg RMSE (lower)': ('PRMS', np.mean(monthly_rmse_prms)) if np.mean(monthly_rmse_prms) < np.mean(monthly_rmse_vic) else ('VIC', np.mean(monthly_rmse_vic)),
        'Peak Timing (lower error)': ('PRMS', abs(prms_peak_month - obs_peak_month)) if abs(prms_peak_month - obs_peak_month) < abs(vic_peak_month - obs_peak_month) else ('VIC', abs(vic_peak_month - obs_peak_month)),
        'Monthly CV (lower error)': ('PRMS', cv_prms_error.mean()) if cv_prms_error.mean() < cv_vic_error.mean() else ('VIC', cv_vic_error.mean()),
        'Seasonal Distribution (lower error)': ('PRMS', prms_frac_error.mean()) if prms_frac_error.mean() < vic_frac_error.mean() else ('VIC', vic_frac_error.mean()),
    }
    
    prms_wins = sum(1 for model, _ in metrics_summary.values() if model == 'PRMS')
    vic_wins = sum(1 for model, _ in metrics_summary.values() if model == 'VIC')
    
    for metric, (winner, value) in metrics_summary.items():
        print(f"{metric:30s}: {winner:4s} ({value:.3f})")
    
    print(f"\nPRMS wins {prms_wins}/{len(metrics_summary)} metrics")
    print(f"VIC wins {vic_wins}/{len(metrics_summary)} metrics")
    print(f"\nRecommended model: {'PRMS' if prms_wins > vic_wins else 'VIC'}")
    
    
    ### CREATE COMPREHENSIVE VISUALIZATION
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.35)
    
    month_names = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
    colors = {'Observed': 'black', 'PRMS': '#2E86AB', 'VIC': '#A23B72'}
    
    # Plot 1: Monthly Mean Climatology
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(range(1, 13), obs_monthly, 'o-', label='Observed', color=colors['Observed'], linewidth=2.5, markersize=8)
    ax1.plot(range(1, 13), prms_monthly, 's--', label='PRMS', color=colors['PRMS'], linewidth=2, markersize=7)
    ax1.plot(range(1, 13), vic_monthly, '^--', label='VIC', color=colors['VIC'], linewidth=2, markersize=7)
    ax1.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Mean Flow (MGD)', fontsize=11, fontweight='bold')
    ax1.set_title('(a) Monthly Mean Flow Climatology', fontsize=12, fontweight='bold', loc='left')
    ax1.set_xticks(range(1, 13))
    ax1.set_xticklabels(month_names)
    ax1.legend(frameon=True, fontsize=10)
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Monthly Fraction of Annual Flow
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.plot(range(1, 13), obs_monthly_frac, 'o-', label='Observed', color=colors['Observed'], linewidth=2.5, markersize=8)
    ax2.plot(range(1, 13), prms_monthly_frac, 's--', label='PRMS', color=colors['PRMS'], linewidth=2, markersize=7)
    ax2.plot(range(1, 13), vic_monthly_frac, '^--', label='VIC', color=colors['VIC'], linewidth=2, markersize=7)
    ax2.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax2.set_ylabel('% of Annual Flow', fontsize=11, fontweight='bold')
    ax2.set_title('(b) Seasonal Water Distribution', fontsize=12, fontweight='bold', loc='left')
    ax2.set_xticks(range(1, 13))
    ax2.set_xticklabels(month_names)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Coefficient of Variation
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(range(1, 13), obs_cv, 'o-', label='Observed', color=colors['Observed'], linewidth=2.5, markersize=8)
    ax3.plot(range(1, 13), prms_cv, 's--', label='PRMS', color=colors['PRMS'], linewidth=2, markersize=7)
    ax3.plot(range(1, 13), vic_cv, '^--', label='VIC', color=colors['VIC'], linewidth=2, markersize=7)
    ax3.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Coefficient of Variation', fontsize=11, fontweight='bold')
    ax3.set_title('(c) Monthly Interannual Variability', fontsize=12, fontweight='bold', loc='left')
    ax3.set_xticks(range(1, 13))
    ax3.set_xticklabels(month_names)
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Monthly Correlation
    ax4 = fig.add_subplot(gs[1, 1])
    x = np.arange(12)
    width = 0.35
    ax4.bar(x - width/2, monthly_corr_prms, width, label='PRMS', color=colors['PRMS'], alpha=0.7)
    ax4.bar(x + width/2, monthly_corr_vic, width, label='VIC', color=colors['VIC'], alpha=0.7)
    ax4.axhline(y=0.8, color='green', linestyle='--', linewidth=1, alpha=0.5, label='Good (r>0.8)')
    ax4.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Correlation Coefficient', fontsize=11, fontweight='bold')
    ax4.set_title('(d) Monthly Temporal Correlation', fontsize=12, fontweight='bold', loc='left')
    ax4.set_xticks(x)
    ax4.set_xticklabels(month_names)
    ax4.set_ylim([0, 1])
    ax4.legend(fontsize=9)
    ax4.grid(True, alpha=0.3, axis='y')
    
    # Plot 5: RMSE by Month
    ax5 = fig.add_subplot(gs[1, 2])
    x = np.arange(12)
    ax5.bar(x - width/2, monthly_rmse_prms, width, label='PRMS', color=colors['PRMS'], alpha=0.7)
    ax5.bar(x + width/2, monthly_rmse_vic, width, label='VIC', color=colors['VIC'], alpha=0.7)
    ax5.set_xlabel('Month', fontsize=11, fontweight='bold')
    ax5.set_ylabel('RMSE (MGD)', fontsize=11, fontweight='bold')
    ax5.set_title('(e) Monthly Root Mean Square Error', fontsize=12, fontweight='bold', loc='left')
    ax5.set_xticks(x)
    ax5.set_xticklabels(month_names)
    ax5.legend(fontsize=9)
    ax5.grid(True, alpha=0.3, axis='y')
    
    # Plot 6: Scatter Plot - Annual Mean
    ax6 = fig.add_subplot(gs[2, 0])
    obs_annual = obs.groupby(obs.index.year).mean()
    prms_annual = prms.groupby(prms.index.year).mean()
    vic_annual = vic.groupby(vic.index.year).mean()
    
    ax6.scatter(obs_annual, prms_annual, alpha=0.6, s=50, color=colors['PRMS'], label=f'PRMS (r={np.corrcoef(obs_annual, prms_annual)[0,1]:.3f})')
    ax6.scatter(obs_annual, vic_annual, alpha=0.6, s=50, color=colors['VIC'], label=f'VIC (r={np.corrcoef(obs_annual, vic_annual)[0,1]:.3f})')
    lims = [min(obs_annual.min(), prms_annual.min(), vic_annual.min()),
            max(obs_annual.max(), prms_annual.max(), vic_annual.max())]
    ax6.plot(lims, lims, 'k--', alpha=0.5, linewidth=1)
    ax6.set_xlabel('Observed Annual Mean (MGD)', fontsize=11, fontweight='bold')
    ax6.set_ylabel('Modeled Annual Mean (MGD)', fontsize=11, fontweight='bold')
    ax6.set_title('(f) Annual Mean Flow Agreement', fontsize=12, fontweight='bold', loc='left')
    ax6.legend(fontsize=9)
    ax6.grid(True, alpha=0.3)
    
    # Plot 7: Performance Metrics Summary
    ax7 = fig.add_subplot(gs[2, 1:])
    metrics_names = ['NSE', 'PBIAS\n(|%|)', 'Avg\nCorr', 'Avg\nRMSE', 'Peak\nTiming', 'CV\nError', 'Seasonal\nDistrib']
    prms_values = [nse_prms, abs(pbias_prms), np.mean(monthly_corr_prms), 
                   np.mean(monthly_rmse_prms), abs(prms_peak_month - obs_peak_month), cv_prms_error.mean(), prms_frac_error.mean()]
    vic_values = [nse_vic, abs(pbias_vic), np.mean(monthly_corr_vic), 
                  np.mean(monthly_rmse_vic), abs(vic_peak_month - obs_peak_month), cv_vic_error.mean(), vic_frac_error.mean()]
    
    # Normalize metrics (higher is better for first 3, lower is better for last 4)
    prms_norm = []
    vic_norm = []
    for i in range(len(prms_values)):
        if i < 3:  # Higher is better
            max_val = max(prms_values[i], vic_values[i])
            prms_norm.append(prms_values[i] / max_val * 100)
            vic_norm.append(vic_values[i] / max_val * 100)
        else:  # Lower is better
            max_val = max(prms_values[i], vic_values[i])
            prms_norm.append((1 - prms_values[i] / max_val) * 100)
            vic_norm.append((1 - vic_values[i] / max_val) * 100)
    
    x = np.arange(len(metrics_names))
    width = 0.35
    bars1 = ax7.bar(x - width/2, prms_norm, width, label='PRMS', color=colors['PRMS'], alpha=0.7)
    bars2 = ax7.bar(x + width/2, vic_norm, width, label='VIC', color=colors['VIC'], alpha=0.7)
    
    ax7.set_ylabel('Normalized Performance (%)', fontsize=11, fontweight='bold')
    ax7.set_title('(g) Overall Model Performance Comparison (Higher is Better)', fontsize=12, fontweight='bold', loc='left')
    ax7.set_xticks(x)
    ax7.set_xticklabels(metrics_names, fontsize=10)
    ax7.set_ylim([0, 105])
    ax7.legend(fontsize=10)
    ax7.grid(True, alpha=0.3, axis='y')
    ax7.axhline(y=100, color='green', linestyle='--', linewidth=1, alpha=0.3)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax7.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.0f}', ha='center', va='bottom', fontsize=8)
    
    fig.suptitle('PRMS vs VIC Hydrologic Model Comparison: NYC Aggregate Inflows', 
                 fontsize=14, fontweight='bold', y=0.995)
    
    # Save figure
    output_dir = 'figures'
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'S1_model_comparison_summary.png')
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\n\nFigure saved to: {output_path}")
    
    plt.show()
    
