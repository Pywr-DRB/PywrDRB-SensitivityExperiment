"""
Utility functions for quantile space analysis of climate scenarios.

These functions support transformation of streamflow changes into quantile space,
enabling visualization and analysis of GCM scenario distributions.
"""

import numpy as np
import pandas as pd


def create_quantile_matrix(df, months_to_use=12):
    """
    Create a matrix of quantiles from flow change data.

    Parameters:
    -----------
    df : pd.DataFrame
        Rows = months (1-12), Columns = GCM scenarios, Values = flow change (%)
    months_to_use : int
        Number of months to process (default 12, excludes duplicate June if present)

    Returns:
    --------
    np.ndarray of shape (months_to_use, 100) containing quantile values for each month
    """
    quantile_matrix = np.zeros((months_to_use, 100))

    for i in range(months_to_use):
        month_data = df.iloc[i].values
        # Calculate quantiles 1-100
        quantile_matrix[i, :] = np.percentile(month_data, range(1, 101))

    return quantile_matrix


def transform_to_quantile_space(df, quantile_matrix):
    """
    Transform streamflow values to quantile space (0-100 percentile).

    Parameters:
    -----------
    df : pd.DataFrame
        Rows = months, Columns = scenarios, Values = flow change (%)
    quantile_matrix : np.ndarray
        Shape (12, 100) - quantile values for each month

    Returns:
    --------
    pd.DataFrame with same shape as df, containing quantile values (1-100)
    """
    df_quantiles = pd.DataFrame(index=df.index, columns=df.columns, dtype=float)

    for i, month_idx in enumerate(df.index):
        # Handle case where df might have more rows than quantile_matrix
        # (e.g., 13 rows with duplicate June)
        month_matrix_idx = i if i < len(quantile_matrix) else 0
        month_quantiles = quantile_matrix[month_matrix_idx, :]

        for col in df.columns:
            value = df.loc[month_idx, col]

            # Find which quantile this value corresponds to
            q_idx = np.searchsorted(month_quantiles, value)
            q_idx = np.clip(q_idx, 0, 99)

            # Convert to 1-100 scale
            df_quantiles.loc[month_idx, col] = q_idx + 1

    return df_quantiles


def get_scenario_quantile_trajectory(scenario_flow_values, quantile_matrix):
    """
    Convert a single scenario's flow values to quantile trajectory.

    Parameters:
    -----------
    scenario_flow_values : array-like
        Flow change values for each month (length 12)
    quantile_matrix : np.ndarray
        Shape (12, 100) - quantile values for each month

    Returns:
    --------
    np.ndarray of quantile values (1-100) for each month
    """
    quantile_trajectory = np.zeros(len(scenario_flow_values))

    for month_idx in range(len(scenario_flow_values)):
        flow_value = scenario_flow_values[month_idx]
        month_quantiles = quantile_matrix[month_idx, :]

        # Find which quantile this value corresponds to
        q_idx = np.searchsorted(month_quantiles, flow_value)
        q_idx = np.clip(q_idx, 0, 99)
        quantile_trajectory[month_idx] = q_idx + 1  # Convert to 1-100 scale

    return quantile_trajectory
