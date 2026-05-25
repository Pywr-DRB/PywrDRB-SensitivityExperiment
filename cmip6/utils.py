import os
import numpy as np
import pandas as pd
import glob
from config import HUC_CODES, DATA_DIR

def calculate_iqr_scenarios(df, outlier_threshold=1.5):
    """
    Calculate high/medium/low scenarios using IQR outlier removal.
    
    Returns dict with 'high', 'medium', 'low' scenarios for each month
    """
    n_months = len(df.index)
    scenarios = {
        'high': np.zeros(n_months),
        'medium': np.zeros(n_months),
        'low': np.zeros(n_months)
    }
    
    # Process each month independently
    for month_idx in range(n_months):
        month_data = df.iloc[month_idx].values
        
        # Remove NaN values
        valid_data = month_data[~np.isnan(month_data)]
        
        if len(valid_data) > 0:
            # Calculate IQR
            q1 = np.percentile(valid_data, 25)
            q3 = np.percentile(valid_data, 75)
            iqr = q3 - q1
            
            # Define outlier bounds
            lower = q1 - outlier_threshold * iqr
            upper = q3 + outlier_threshold * iqr
            
            # Filter out outliers
            cleaned_data = valid_data[(valid_data >= lower) & (valid_data <= upper)]
            
            if len(cleaned_data) > 0:
                # Calculate scenarios from cleaned data
                scenarios['low'][month_idx] = np.percentile(cleaned_data, 10)
                scenarios['medium'][month_idx] = np.median(cleaned_data)
                scenarios['high'][month_idx] = np.percentile(cleaned_data, 90)
            else:
                # Fallback if all data removed (unlikely)
                scenarios['low'][month_idx] = np.nan
                scenarios['medium'][month_idx] = np.nan
                scenarios['high'][month_idx] = np.nan
    
    return scenarios


def parse_dataset_settings_from_name(dataset):
    """
    Each dataset has the format of either:
    - <hydrology_model>_RAPID_<gcm>_<ssp_scenario>_<run_id>_<downscaling_method>_<forcing>_<start_year>_<end_year>
    - <hydrology_model>_RAPID_<forcing>_<start_year>_<end_year>
    - <hydrology_model>_RAPID_<forcing>_<forcing_version>_<start_year>_<end_year>
    
    The cases are:
    - first case is for future projections
    - second case is for historical datasets
    - third case is for historical datasets with specific forcing versions (outlier names, only a few)
    
    Parameters
    ----------
    dataset : str
        The name of the dataset to parse.
    
    Returns
    -------
    dict
        A dictionary containing the parsed settings.
    """
    
    parts = dataset.split('_')
    
    if len(parts) == 5:
        # Historical dataset format
        settings = {
            'hydrology_model': parts[0],
            'gcm': None,  # No GCM for historical datasets
            'ssp': None,  # No SSP for historical datasets
            'run_id': None,  # No run_id for historical datasets
            'downscaling_method': None,  # No downscaling method for historical datasets
            'forcing': parts[2],
            'start_year': int(parts[3]),
            'end_year': int(parts[4])
        }
    elif len(parts) == 6:
        # Historical dataset with forcing version format
        settings = {
            'hydrology_model': parts[0],
            'gcm': None,  # No GCM for historical datasets
            'ssp': None,  # No SSP for historical datasets
            'run_id': None,  # No run_id for historical datasets
            'downscaling_method': None,  # No downscaling method for historical datasets
            'forcing': parts[2],
            'start_year': int(parts[4]),
            'end_year': int(parts[5])
        }
        
    elif len(parts) == 9:
        # Future projection dataset format            
        settings = {
            'hydrology_model': parts[0],
            'gcm': parts[2],
            'ssp': parts[3],
            'run_id': parts[4],
            'downscaling_method': parts[5],
            'forcing': parts[6],
            'start_year': int(parts[7]),
            'end_year': int(parts[8])
        }
    
    else:
        raise ValueError(f"Dataset name '{dataset}' does not match expected format.")
    
    return settings


def verify_dataset_has_necessary_files(dataset):
    """
    Each dataset must have files for each HUC code.
    
    These files should be:
    - <dataset_name>/*<huc_code>*.nc
    
    Parameters
    ----------
    dataset : str
        The name of the dataset to verify.
    
    Returns
    -------
    bool
        True if all necessary files are present, False otherwise.
    """
    for huc_code in HUC_CODES:
        # Check if the file exists for this HUC code
        file_path = os.path.join(DATA_DIR, dataset, f"*{huc_code}*.nc")
        if not any(os.path.exists(file) for file in glob.glob(file_path)):
            print(f"Missing file for HUC {huc_code} in dataset {dataset}.")
            return False
    
    return True


def get_dataset_baseline(dataset):
    """
    Get the baseline dataset for a given dataset.
    
    The baseline is determined by the hydrology model and forcing.
    
    Parameters
    ----------
    dataset : str
        The name of the dataset to get the baseline for.
    
    Returns
    -------
    str
        The name of the baseline dataset.
    """
    settings = parse_dataset_settings_from_name(dataset)
    
    if settings['hydrology_model'] == 'PRMS':
        if 'Livneh' in settings['forcing']:
            return 'PRMS_RAPID_Livneh2018_1950_2013'
        elif 'Daymet' in settings['forcing']:
            return 'PRMS_RAPID_Daymet2019_1980_2019'
        else:
            raise ValueError(f"Unknown forcing for PRMS hydrology model: {settings['forcing']}")

    elif settings['hydrology_model'] == 'VIC5':
        if 'Livneh' in settings['forcing']:
            return 'VIC5_RAPID_Livneh2018_v20200704L_1950_2013'
        elif 'Daymet' in settings['forcing']:
            return 'VIC5_RAPID_Daymet2019_v20200704D_1980_2019'
        else:
            raise ValueError(f"Unknown forcing for VIC5 hydrology model: {settings['forcing']}")

    return None



from config import DATASET_NAMES
dataset_settings = {}
for dataset in DATASET_NAMES:
    dataset_settings[dataset] = parse_dataset_settings_from_name(dataset)

dataset_baselines = {}
for dataset in DATASET_NAMES:
    try:
        dataset_baselines[dataset] = get_dataset_baseline(dataset)
    except ValueError as e:
        print(f"Error getting baseline for dataset {dataset}: {e}")
        dataset_baselines[dataset] = None