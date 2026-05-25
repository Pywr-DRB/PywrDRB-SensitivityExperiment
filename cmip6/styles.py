import matplotlib.cm as cm

from config import DATASET_NAMES
from utils import parse_dataset_settings_from_name

def make_colordict(datasets, 
                   colorby='start_year',
                   cmap='viridis'):
    """
    Create a dictionary of colors, based on different dataset settings.
    
    Parameters
    ----------
    datasets : list of str
        List of dataset names.
    colorby : str
        The setting to color by. Options are:
        - 'start_year'
        - 'hydrology_model'
        - 'gcm'
        - 'ssp'
        - 'downscaling_method'
        - 'forcing'
    cmap : str
        The colormap to use. Default is 'viridis'.

    Returns
    -------
    colordict : dict
        A dictionary where keys are dataset names and values are colors.

    """
    
    # Get the dataset settings
    dataset_settings = {}
    for dataset in datasets:
        settings = parse_dataset_settings_from_name(dataset)
        dataset_settings[dataset] = settings[colorby]
    
    # Create a colormap
    unique_settings = list(set(dataset_settings.values()))
    cmap = cm.get_cmap(cmap, len(unique_settings))
    
    colordict = {}
    for i, setting in enumerate(unique_settings):
        color = cmap(i)
        for dataset, setting_value in dataset_settings.items():
            if setting_value == setting:
                colordict[dataset] = color

    return colordict

def make_markerdict(datasets,
                    markerby='hydrology_model'):
    """
    Create a dictionary of markers, based on different dataset settings.
    Parameters
    ----------
    datasets : list of str
        List of dataset names.
    markerby : str
        The setting to use for markers. Options are:
        - 'hydrology_model'
        - 'gcm'
        - 'ssp'
        - 'downscaling_method'
        - 'forcing'
    Returns
    -------
    markerdict : dict
        A dictionary where keys are dataset names and values are markers.
    """
    # Get the dataset settings
    dataset_settings = {}
    for dataset in datasets:
        settings = parse_dataset_settings_from_name(dataset)
        dataset_settings[dataset] = settings[markerby]
    
    # Create a set of unique settings
    unique_settings = list(set(dataset_settings.values()))
    assert len(unique_settings) <= 9, "Too many unique settings for markers. Please reduce the number of unique settings or use a different marker strategy."
    
    markers = ['o', 's', 'D', '^', 'v', 'x', 'p', '*', 'h']
    markerdict = {}
    for i, setting in enumerate(unique_settings):
        marker = markers[i % len(markers)]
        for dataset, setting_value in dataset_settings.items():
            if setting_value == setting:
                markerdict[dataset] = marker
    return markerdict


colordict_by_start_year = make_colordict(DATASET_NAMES, colorby='start_year')
colordict_by_gcm = make_colordict(DATASET_NAMES, colorby='gcm')

markerdict_by_gcm = make_markerdict(DATASET_NAMES, markerby='gcm')
markerdict_by_hydrology_model = make_markerdict(DATASET_NAMES, markerby='hydrology_model')