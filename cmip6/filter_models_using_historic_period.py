"""
This script is used to identify datasets that do or do-not match historic observations.

Aggregate NYC reservoir inflow is used for this comparison, since they are unmanaged flows and 
relevant for this study. 

Metrics used for comparison are:
- Total annual inflow
- Monthly inflow distributions (by month of year) with +/- 7-day window robustness
"""

import os
import numpy as np
import pandas as pd
from scipy import stats
from datetime import datetime, timedelta
import calendar

import pywrdrb
from pywrdrb.pre.flows import _subtract_upstream_catchment_inflows

from config import DATASET_NAMES

historic_datasets = []
for dataset in DATASET_NAMES:
    # If this a 'future' dataset, then skip
    # future datasets contain '2059' or '2060' in name
    if ('2059' in dataset) or ('2060' in dataset):
        continue
    else:
        historic_datasets.append(dataset)


# Setup pathnavigator
pn_config = pywrdrb.get_pn_config()
for dataset in historic_datasets:
    f = f"pywrdrb/inputs/{dataset}"
    pn_config[f"flows/{dataset}"] = os.path.abspath(f)
pywrdrb.load_pn_config(pn_config)


nyc_reservoirs = ['cannonsville', 'pepacton', 'neversink']
start_date = "1980-01-01"
end_date = "2019-12-31"


def get_month_boundaries_with_windows(year, month, window_days=7):
    """
    Get start and end dates for a month with +/- window_days variations.
    Returns a list of (start_date, end_date) tuples for the window variations.
    """
    # Get the nominal start and end of the month
    nominal_start = datetime(year, month, 1)
    
    # Get last day of month
    last_day = calendar.monthrange(year, month)[1]
    nominal_end = datetime(year, month, last_day)
    
    boundaries = []
    
    # Create windows from -window_days to +window_days
    for offset in range(-window_days, window_days + 1):
        window_start = nominal_start + timedelta(days=offset)
        window_end = nominal_end + timedelta(days=offset)
        boundaries.append((window_start, window_end))
    
    return boundaries


def calculate_windowed_monthly_flows(flow_df, nyc_reservoirs, window_days=7):
    """
    Calculate monthly flows using +/- window_days approach.
    Returns a dictionary with month as key and array of flow values as value.
    """
    monthly_windowed_data = {}
    
    # Initialize storage for each month
    for month in range(1, 13):
        monthly_windowed_data[month] = []
    
    # Get unique years in the data
    years = sorted(flow_df.index.year.unique())
    
    for year in years:
        for month in range(1, 13):
            # Get all window boundaries for this year/month
            boundaries = get_month_boundaries_with_windows(year, month, window_days)
            
            for start_date, end_date in boundaries:
                # Extract flows for this window
                try:
                    # Make sure dates are within our data range
                    if start_date < flow_df.index.min() or end_date > flow_df.index.max():
                        continue
                    
                    window_flows = flow_df.loc[start_date:end_date, nyc_reservoirs]
                    
                    # Skip if window is too small (less than 20 days to ensure reasonable month representation)
                    if len(window_flows) < 20:
                        continue
                    
                    # Sum across reservoirs and time for this window
                    total_window_flow = window_flows.sum().sum()
                    monthly_windowed_data[month].append(total_window_flow)
                    
                except (KeyError, IndexError):
                    # Skip if there's an issue with this window
                    continue
    
    # Convert lists to numpy arrays
    for month in range(1, 13):
        monthly_windowed_data[month] = np.array(monthly_windowed_data[month])
    
    return monthly_windowed_data


if __name__ == "__main__":

    annual_nyc_inflows = {}
    monthly_nyc_inflows_windowed = {}  # New dictionary for windowed monthly data
    window_days = 7  # +/- 7 day window

    ### Load reconstruction data
    data = pywrdrb.Data()
    data.load_observations(results_sets=['all'])
    data.load_hydrologic_model_flow(flowtypes=['pub_nhmv10_BC_withObsScaled'], 
                                    results_sets=['all'])
    
    for dataset in ['pub_nhmv10_BC_withObsScaled', 'obs']:
        flow_df = data.all[dataset][0]
        nyc_inflows = flow_df.loc[start_date:end_date, nyc_reservoirs]
        
        name = 'obs' if dataset == 'obs' else 'reconstruction'
        
        # Annual statistics (existing)
        annual_nyc_inflows[name] = nyc_inflows.resample("YE").sum().values.flatten()
        
        # Windowed monthly statistics (new robust approach)
        monthly_windowed_data = calculate_windowed_monthly_flows(nyc_inflows, nyc_reservoirs, window_days)
        monthly_nyc_inflows_windowed[name] = monthly_windowed_data

    for dataset in historic_datasets:
        
        ## Calculate catchment inflows
        f = f"pywrdrb/inputs/{dataset}/gage_flow_mgd.csv"
        flow_df = pd.read_csv(
            f, index_col=0,
            parse_dates=True,
        )

        nyc_inflows = flow_df.loc[start_date:end_date, nyc_reservoirs]

        # Annual statistics (existing)
        annual_nyc_inflows[dataset] = nyc_inflows.resample("YE").sum().values.flatten()
        
        # Windowed monthly statistics (new robust approach)
        monthly_windowed_data = calculate_windowed_monthly_flows(nyc_inflows, nyc_reservoirs, window_days)
        monthly_nyc_inflows_windowed[dataset] = monthly_windowed_data
        
        # Print sample sizes for verification
        print(f"\n{dataset} - Windowed monthly sample sizes:")
        for month in range(1, 13):
            print(f"  Month {month}: {len(monthly_windowed_data[month])} samples")
    
    
    ### Calculate distribution comparisons
    
    ## Annual statistics (existing code)
    n_datasets = len(annual_nyc_inflows)
    hist_data = annual_nyc_inflows['reconstruction']
    stats_pvals_annual = []
    
    for i, dataset in enumerate(historic_datasets):
        x1 = np.log(hist_data)
        x2 = np.log(annual_nyc_inflows[dataset])
        
        dataset_stats = [
            dataset,
            stats.ranksums(x1, x2)[1],
            stats.levene(x1, x2)[1],
        ]
        
        stats_pvals_annual.append(dataset_stats)
    
    # Save annual stats to txt file
    fname_annual = 'historic_annual_flow_stats_robust.txt'
    stats_df_annual = pd.DataFrame(stats_pvals_annual, columns=['dataset', 'rank_p_value', 'levene_p_value'])
    stats_df_annual.to_csv(fname_annual, index=False)
    
    
    ## Windowed Monthly statistics (new robust code)
    hist_monthly_windowed_data = monthly_nyc_inflows_windowed['obs']
    stats_pvals_monthly_robust = []
    
    for dataset in historic_datasets:
        dataset_monthly_windowed_data = monthly_nyc_inflows_windowed[dataset]
        
        for month in range(1, 13):
            # Get historical and dataset monthly flows for this month (windowed)
            x1_monthly = hist_monthly_windowed_data[month]
            x2_monthly = dataset_monthly_windowed_data[month]
            
            # Skip if either dataset has insufficient data
            if len(x1_monthly) < 10 or len(x2_monthly) < 10:
                print(f"Warning: Insufficient data for {dataset}, month {month}")
                continue
            
            # Apply log transformation
            x1_log = np.log(x1_monthly + 1e-6)  # Add small constant to avoid log(0)
            x2_log = np.log(x2_monthly + 1e-6)
            
            # Calculate statistics for this month
            try:
                rank_pval = stats.ranksums(x1_log, x2_log)[1]
                levene_pval = stats.levene(x1_log, x2_log)[1]
            except (ValueError, ZeroDivisionError) as e:
                print(f"Warning: Statistical test failed for {dataset}, month {month}: {e}")
                rank_pval = np.nan
                levene_pval = np.nan
            
            dataset_month_stats = [
                dataset,
                month,
                len(x1_monthly),  # Sample size for reference data
                len(x2_monthly),  # Sample size for dataset
                rank_pval,
                levene_pval,
            ]
            
            stats_pvals_monthly_robust.append(dataset_month_stats)
    
    # Save windowed monthly stats to txt file
    fname_monthly_robust = 'historic_monthly_flow_stats_robust.txt'
    stats_df_monthly_robust = pd.DataFrame(stats_pvals_monthly_robust, 
                                          columns=['dataset', 'month', 'n_reference', 'n_dataset', 
                                                  'rank_p_value', 'levene_p_value'])
    stats_df_monthly_robust.to_csv(fname_monthly_robust, index=False)
    
    print(f"\n\nResults saved:")
    print(f"Annual statistics: {fname_annual}")
    print(f"Robust monthly statistics: {fname_monthly_robust}")
    print(f"Robust monthly stats shape: {stats_df_monthly_robust.shape}")
    
    # Print summary of sample sizes
    print(f"\nSample size summary (windowed approach with +/- {window_days} days):")
    print("Expected samples per month: ~", (2019-1980+1) * (2*window_days + 1))
    print("Actual sample size ranges:")
    sample_sizes = stats_df_monthly_robust.groupby('month')['n_reference'].first()
    print(sample_sizes.describe())