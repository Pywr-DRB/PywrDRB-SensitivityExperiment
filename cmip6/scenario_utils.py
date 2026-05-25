"""
Utility functions for climate scenario analysis and selection.

This module provides shared functions for calculating annual flow statistics,
filtering scenarios, and performing scenario selection operations.
"""

import numpy as np
import pandas as pd
from utils import dataset_baselines


def calculate_annual_pct_changes(monthly_means_df, filtered_scenarios):
    """
    Calculate percent change in annual flow for each GCM scenario relative to its own baseline.

    This function compares each climate scenario to its dataset-specific historic baseline
    (e.g., PRMS scenarios compare to PRMS historic, VIC to VIC historic).

    Parameters:
    -----------
    monthly_means_df : pd.DataFrame
        Monthly mean flows (rows=months 1-12, columns=datasets)
    filtered_scenarios : list
        List of GCM scenario names to analyze

    Returns:
    --------
    pd.Series: Percent change in annual flow for each scenario
    """
    annual_pct_changes = {}

    for scenario in filtered_scenarios:
        # Get the baseline for this scenario (from dataset_baselines mapping)
        baseline_name = dataset_baselines.get(scenario, 'pub_nhmv10_BC_withObsScaled')

        if baseline_name not in monthly_means_df.columns:
            print(f"Warning: Baseline '{baseline_name}' not found for '{scenario}'")
            continue

        # Calculate annual flows (sum of monthly means)
        scenario_annual = monthly_means_df[scenario].sum()
        baseline_annual = monthly_means_df[baseline_name].sum()

        # Calculate percent change
        pct_change = ((scenario_annual - baseline_annual) / baseline_annual) * 100
        annual_pct_changes[scenario] = pct_change

    return pd.Series(annual_pct_changes)


def filter_scenarios_by_annual_change(df, monthly_means_df, require_positive=True, verbose=True):
    """
    Filter GCM scenarios based on annual flow change direction.

    Parameters:
    -----------
    df : pd.DataFrame
        Scenario data (rows=months, columns=scenarios)
    monthly_means_df : pd.DataFrame
        Monthly mean flows for calculating annual changes
    require_positive : bool
        If True, only keep scenarios with positive annual flow changes
    verbose : bool
        Print filtering details

    Returns:
    --------
    pd.DataFrame: Filtered scenarios
    list: Names of rejected scenarios with their annual % changes
    """
    scenarios_to_keep = []
    scenarios_rejected = []

    # Calculate annual changes for all scenarios
    annual_changes = calculate_annual_pct_changes(monthly_means_df, df.columns.tolist())

    for scenario in df.columns:
        if scenario not in annual_changes.index:
            # If we couldn't calculate annual change, keep the scenario
            scenarios_to_keep.append(scenario)
            continue

        annual_pct_change = annual_changes[scenario]

        if require_positive:
            if annual_pct_change >= 0:
                scenarios_to_keep.append(scenario)
            else:
                scenarios_rejected.append((scenario, annual_pct_change))
        else:
            scenarios_to_keep.append(scenario)

    # Apply filter
    df_filtered = df[scenarios_to_keep]

    if verbose:
        print(f"\nAnnual flow change filter (require_positive={require_positive}):")
        print(f"  Scenarios rejected: {len(scenarios_rejected)}")
        if len(scenarios_rejected) > 0:
            print(f"  Rejected scenarios:")
            for scenario, pct_change in scenarios_rejected:
                print(f"    - {scenario}: {pct_change:.2f}%")
        print(f"  Remaining scenarios: {len(scenarios_to_keep)}")

    return df_filtered, scenarios_rejected


def calculate_flow_weights(monthly_means_df, baseline_col='pub_nhmv10_BC_withObsScaled', log_transform=False):
    """
    Calculate monthly flow weights based on percentage of annual flow.

    Parameters:
    -----------
    monthly_means_df : pd.DataFrame
        Monthly mean flows (rows=months 1-12, columns=datasets)
    baseline_col : str
        Name of baseline dataset to use for weights
    log_transform : bool
        If True, apply logarithmic transformation to flow percentages before normalizing.
        This reduces the dominance of high-flow months while still weighting by importance.

    Returns:
    --------
    tuple: (np.ndarray of weights for each month, str baseline_col used)
    """
    if baseline_col not in monthly_means_df.columns:
        print(f"Warning: Baseline '{baseline_col}' not found. Using first available dataset.")
        baseline_col = monthly_means_df.columns[0]

    baseline_monthly = monthly_means_df[baseline_col]
    annual_total = baseline_monthly.sum()

    # Calculate percentage of annual flow for each month
    flow_percentages = (baseline_monthly / annual_total).values

    if log_transform:
        # Apply log transformation to compress the range
        # Use log(1 + x) to avoid issues with very small values
        weights = np.log1p(flow_percentages)
    else:
        weights = flow_percentages

    # Normalize weights to sum to 1
    weights = weights / weights.sum()

    return weights, baseline_col


def calculate_weighted_average_changes(monthly_pct_change_df, weights=None):
    """
    Calculate weighted average streamflow change for each scenario.

    Parameters:
    -----------
    monthly_pct_change_df : pd.DataFrame
        Rows = months, Columns = scenarios, Values = flow change (%)
    weights : np.ndarray or None
        Monthly weights (length = number of rows). If None, equal weights used.

    Returns:
    --------
    pd.Series: Weighted average change for each scenario
    """
    if weights is None:
        # Equal weights for all months
        weights = np.ones(len(monthly_pct_change_df))
    else:
        weights = np.array(weights)

    # Normalize weights to sum to 1
    weights = weights / weights.sum()

    # Calculate weighted average for each scenario
    weighted_avg = {}
    for scenario in monthly_pct_change_df.columns:
        values = monthly_pct_change_df[scenario].values
        weighted_avg[scenario] = np.sum(values * weights)

    return pd.Series(weighted_avg)
