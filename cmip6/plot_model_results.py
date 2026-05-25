import os
import pandas as pd
import matplotlib.pyplot as plt
import pywrdrb

from config import DATASET_NAMES

### Keep only datasets with names that have:
# "2020" and (ssp245 or ssp370)
DATASET_NAMES = [d for d in DATASET_NAMES if ("2020" in d) and ("ssp245" in d or "ssp370" in d)]

output_fnames = [
    f"pywrdrb/outputs/{dataset}.hdf5" for dataset in DATASET_NAMES
]

# Load simulation outputs
data = pywrdrb.Data(results_sets=['res_storage'], print_status=True)
data.load_output(output_filenames=output_fnames)


# Plot of NYC aggregate storage
nyc_reservoirs = ['cannonsville', 'pepacton', 'neversink']

fig, ax = plt.subplots(figsize=(12, 6))
for dataset in DATASET_NAMES:
    df = data.res_storage[dataset][0]
    nyc_storages = df[nyc_reservoirs].copy()
    
    agg_nyc_storage = nyc_storages.sum(axis=1)
    ax.plot(agg_nyc_storage.index, agg_nyc_storage, 
            label=dataset, alpha=0.3)

# make x limit 2020-2060
# ax.set_xlim(pd.Timestamp("2020-01-01"), pd.Timestamp("2059-12-31"))

ax.set_title(f"NYC Reservoir Storages Accross {len(DATASET_NAMES)} CMIP6-Downscaled Models")
ax.set_xlabel("Date")
ax.set_ylabel("Storage (MGD)")

plt.tight_layout()
plt.savefig('nyc_reservoir_storages.png')
