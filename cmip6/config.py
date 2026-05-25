import os

HUC_CODES = [
    '02040101N', '02040102N', '02040103N',
    '02040104N', '02040105N', '02040106N',
    '02040201N', '02040202N', '02040203N',
    '02040204N', '02040205N', '02040206N', '02040207N',
]

# Get dataset names from the ./Data/ folder
DATA_DIR = os.path.join(os.path.dirname(__file__), 'pywrdrb/inputs')
if not os.path.exists(DATA_DIR):
    raise FileNotFoundError(f"Data directory does not exist: {DATA_DIR}")

DATASET_NAMES = [
    name for name in os.listdir(DATA_DIR)
    if os.path.isdir(os.path.join(DATA_DIR, name)) and not name.startswith('.')
]



DATASET_COLORS_BY_PERIOD = {
    'obs' : 'black'
}

# Colors are based on dataset periods
for dataset in DATASET_NAMES:
    if 'Daymet2019' in dataset:
        DATASET_COLORS_BY_PERIOD[dataset] = 'blue'
    elif 'Livneh2018' in dataset:
        DATASET_COLORS_BY_PERIOD[dataset] = 'blue'
    elif '2020_2059' in dataset:
        DATASET_COLORS_BY_PERIOD[dataset] = 'orange'
    elif '2060_2099' in dataset:
        DATASET_COLORS_BY_PERIOD[dataset] = 'red'


