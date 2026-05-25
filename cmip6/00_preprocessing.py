import os
import numpy as np
import pandas as pd
import netCDF4 as nc
from pywrdrb.utils.constants import cfs_to_mgd

from config import DATASET_NAMES, HUC_CODES, DATA_DIR
from utils import parse_dataset_settings_from_name, verify_dataset_has_necessary_files

def extract_pywrdrb_from_model_netcdfs(dataset_files, node_metadata):
    """
    Extracts the pywrdrb data from the model netCDF files.
    
    Parameters
    ----------
    dataset_name : str
        The name of the dataset to extract.
    node_metadata : pd.DataFrame
        The metadata for the nodes in the DRB.
        
    Returns
    -------
    flow_df : pd.DataFrame
        A DataFrame containing the flows for each node in the DRB.
    """
    
    flow_df = {}
    
    # Loop through files and extract flows 
    for fname in dataset_files:
        ds = nc.Dataset(fname)

        # Only a subset of comids will be present in each dataset
        all_huc_comids = ds.variables['COMID'][:].astype(int)

        # get nodes in the HUC
        node_metadata_huc = node_metadata[node_metadata.index.isin(all_huc_comids)]

        # Loop through nodes in the HUC and store flow in the flow_df
        for comid in node_metadata_huc.index:

            name = node_metadata_huc.loc[comid, 'name']  
            
            # Get the index for this comid in the dataset
            ds_comid_idx = np.where(ds.variables['COMID'][:] == comid)[0]
            
            comid_flow = ds.variables['RAPID_dy_cfs'][ds_comid_idx, :].data.flatten()
            
            # Handle cases where this is more than one name per comid
            if type(name) is pd.Series:
                for n in name:
                    flow_df[n] = comid_flow
            else:
                flow_df[name] = comid_flow
        
    # Convert to DataFrame
    datetime = ds.variables['Time_dy'][:]    
    datetime = pd.to_datetime(datetime, format='%Y%m%d')
    flow_df = pd.DataFrame(flow_df, index=datetime) * cfs_to_mgd
    flow_df.index.name = 'datetime'

    return flow_df


if __name__ == "__main__":
    
    # Load drb metadata
    node_metadata = pd.read_csv(f"drb_pywrdrb_node_metadata.csv")
    node_metadata.set_index('comid', inplace=True)


    # Loop through datasets and extract flows
    for dataset in DATASET_NAMES:
        
        # Make sure necessary files are present        
        verify_dataset_has_necessary_files(dataset)
        
        # Get the dataset files
        dataset_files = os.listdir(f"{DATA_DIR}/{dataset}/")
        # keep only files with one of the HUC codes in the name
        dataset_files = [
            f"{DATA_DIR}/{dataset}/{f}" for f in dataset_files if any(
                huc in f for huc in HUC_CODES
                )
        ]

        ### Extract the flows
        # If pywrdrb/inputs/<dataset>/gage_flow_mgd.csv already exists, skip extraction
        output_file = f"pywrdrb/inputs/{dataset}/gage_flow_mgd.csv"
        if os.path.exists(output_file):
            print(f"Skipping {dataset}, already processed.")
            continue
        
        print(f"Processing {dataset}...")
        flow_df = extract_pywrdrb_from_model_netcdfs(dataset_files, node_metadata)
                
        # Save the flow_df to a CSV file
        output_dir = f"pywrdrb/inputs/{dataset}"
        os.makedirs(output_dir, exist_ok=True)
        flow_df.to_csv(f"{output_dir}/gage_flow_mgd.csv")