
import os
import numpy as np
import pandas as pd
import pywrdrb
from mpi4py import MPI
from config import DATASET_NAMES


USE_MPI = True
if USE_MPI:
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()
    print(f"MPI enabled: rank {rank} of {size}")
else:
    comm = None
    rank = 0
    size = 1
    print("MPI not enabled.")


# Setup pathnavigator
pn_config = pywrdrb.get_pn_config()
for dataset in DATASET_NAMES:
    f = f"pywrdrb/inputs/{dataset}"
    pn_config[f"flows/{dataset}"] = os.path.abspath(f)
pywrdrb.load_pn_config(pn_config)


# Split the dataset names across ranks
if USE_MPI:
    local_rank_datasets = [
        dataset for i, dataset in enumerate(DATASET_NAMES) if i % size == rank
    ]
else:
    local_rank_datasets = DATASET_NAMES


if __name__ == "__main__":

    print(f"Rank {rank} running {len(local_rank_datasets)} datasets through Pywr-DRB...")

    for dataset in local_rank_datasets:

        ## Filenames
        model_json_file = f"pywrdrb/json/{dataset}.json"
        model_output_file = f"pywrdrb/outputs/{dataset}.hdf5"
        
        # Make the json and output directories if they don't exist
        os.makedirs(os.path.dirname(model_json_file), exist_ok=True)
        os.makedirs(os.path.dirname(model_output_file), exist_ok=True)
        
        # Get the start and end dates
        f = f"pywrdrb/inputs/{dataset}/gage_flow_mgd.csv"
        flow_df = pd.read_csv(
            f, index_col=0,
            parse_dates=True,
        )
        start_date = flow_df.index.min().strftime("%Y-%m-%d")
        end_date = flow_df.index.max().strftime("%Y-%m-%d")


        print("#" * 50)
        print(f"Running Pywr-DRB simulation for {dataset}...")
        print(f"  Start date: {start_date}"
              f" | End date: {end_date}")
        print("#" * 50)

        ### Make the model
        mb = pywrdrb.ModelBuilder(
            inflow_type=dataset,
            start_date=start_date,
            end_date=end_date,
            options = {
                'nyc_nj_demand_source':'custom' # [historic, custom, constant]
            }
        )
        
        mb.make_model()
        mb.write_model(model_json_file)
        
        print(f"Saved model JSON to pywrdrb/json/{dataset}.json")
        
        ### Load the model
        model = pywrdrb.Model.load(model_json_file)
        
        ## Setup recorder
        recorder = pywrdrb.OutputRecorder(
            model=model,
            output_filename=model_output_file,
            parameters=[p for p in model.parameters if p.name]
        )
        
        ### Run
        model.run()


    print(f"Rank {rank} done running Pywr-DRB simulations.")