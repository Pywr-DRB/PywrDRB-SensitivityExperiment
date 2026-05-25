import os
import pandas as pd
import matplotlib.pyplot as plt
import pywrdrb

DATASET_NAMES = [
    'PRMS_RAPID_Livneh2018_1950_2013',
    'VIC5_RAPID_Livneh2018_v20200704L_1950_2013'
]

output_fnames = [
    f"pywrdrb/outputs/{dataset}.hdf5" for dataset in DATASET_NAMES
]

# Load simulation outputs
data = pywrdrb.Data(results_sets=['major_flow', 'res_storage'])
data.load_output(output_filenames=output_fnames)


# Plot of NYC aggregate storage
nyc_reservoirs = ['cannonsville', 'pepacton', 'neversink']

fig, ax = plt.subplots(figsize=(12, 6))
for dataset in DATASET_NAMES:
    df = data.res_storage[dataset][0]
    nyc_storages = df[nyc_reservoirs].copy()
    
    agg_nyc_storage = nyc_storages.sum(axis=1)
    ax.plot(agg_nyc_storage.index, agg_nyc_storage, label=dataset, alpha=0.3)


ax.set_title("NYC Reservoir Storages Over Time")
ax.set_xlabel("Date")
ax.set_ylabel("Storage (MGD)")
ax.legend()
plt.tight_layout()
plt.savefig('nyc_reservoir_storages.png')
