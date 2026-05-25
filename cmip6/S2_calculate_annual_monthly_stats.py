
import os
import numpy as np
import pandas as pd
import pywrdrb
from config import DATASET_NAMES 
from utils import dataset_baselines


# pywrdrb_nodes list or subset of nodes to plot
CONSIDER_NODES = [
    'nyc_inflow'
]

if __name__ == "__main__":
    ### Load data through pywrdrb API    
    # Setup pathnavigator
    pn_config = pywrdrb.get_pn_config()
    for dataset in DATASET_NAMES:
        f = f"pywrdrb/inputs/{dataset}"
        pn_config[f"flows/{dataset}"] = os.path.abspath(f)

    pywrdrb.load_pn_config(pn_config)

    pn = pywrdrb.get_pn_object()
    sc_flows = list(pn.sc.to_dict().keys())
    flowtype_opts = [i.replace("flows/", "") for i in sc_flows]

    # drop flowtyps that start with 'rev_'
    flowtype_opts = [ft for ft in flowtype_opts if not ft.startswith('rev_')]

    results_sets = ['major_flow']
    flowtypes = flowtype_opts
    data = pywrdrb.Data(results_sets=results_sets,)
    data.load_hydrologic_model_flow(flowtypes)
    
    # The data object will contain the gage_flow_mgd DataFrames for each flowtype
    loaded_datasets = data.major_flow.keys()
    pywrdrb_nodes = data.major_flow[flowtypes[0]][0].columns.tolist()
    print(f"Loaded flows at {len(pywrdrb_nodes)} nodes for {len(loaded_datasets)} datasets.")

    # For each of the loaded datasets, calculate NYC aggregate inflow
    # this is the sum of flows for:
    nyc_inflow_gages = ["01425000", "01417000", "01436000"]

    # save in data object for later
    for dataset in loaded_datasets:
        df = data.major_flow[dataset][0]
        nyc_inflow = df[nyc_inflow_gages].sum(axis=1)
        data.major_flow[dataset][0]['nyc_inflow'] = nyc_inflow

    # Make lists of dataset types including:
    # historic (name does not contain 'ssp')
    # ssp245_2020_2059 (name contains 'ssp245' and '2020')
    # ssp245_2060_2099 (name contains 'ssp245' and '2060')
    # ssp370_2020_2059 (name contains 'ssp370')
    # ssp370_2060_2099 (name contains 'ssp370' and '2060')
    dataset_types = {}
    dataset_types['historic'] = [d for d in loaded_datasets if ('2059' not in d) and ('2060' not in d)]
    historic_datasets = dataset_types['historic']
    print(f'Historic datasets: {historic_datasets}')
    
    dataset_types['ssp245_2020_2059'] = [d for d in loaded_datasets if 'ssp245' in d and '2020' in d]
    dataset_types['ssp245_2060_2099'] = [d for d in loaded_datasets if 'ssp245' in d and '2060' in d]
    dataset_types['ssp370_2020_2059'] = [d for d in loaded_datasets if 'ssp370' in d and '2020' in d]
    dataset_types['ssp370_2060_2099'] = [d for d in loaded_datasets if 'ssp370' in d and '2060' in d]    
    
    ### Loop through nodes and plot comparisons
    for node in CONSIDER_NODES:
        if node == 'delTrenton':
            continue

        # For each dataset, retrieve the flow at this node
        node_flows = {}
        for dataset in loaded_datasets:
            df = data.major_flow[dataset][0]
            node_flows[dataset] = df[node].copy()
        node_flows = pd.DataFrame(node_flows)
        node_flows.index = pd.to_datetime(node_flows.index)
        
        # Make monthly flow df
        monthly = node_flows.groupby([node_flows.index.year, node_flows.index.month]).sum()
        monthly.index = pd.MultiIndex.from_tuples(monthly.index, names=['year', 'month'])

        annual = node_flows.groupby(node_flows.index.year).sum()
        
        # Replace 0.0 with NaN after aggregations for statistics calculation
        monthly.replace(0.0, np.nan, inplace=True)
        annual.replace(0.0, np.nan, inplace=True)
        annual_median = np.nanmedian(annual, axis=0)
        annual_median = pd.Series(annual_median, index=annual.columns, name='median')
        annual_means = annual.mean()
        annual_stds = annual.std()

        # Calculate monthly mean and std
        monthly_means = monthly.groupby('month').mean()
        monthly_stds = monthly.groupby('month').std()
        
        # Save monthly means and std
        # make stats/ if not exists
        if not os.path.exists('stats'):
            os.makedirs('stats')
        annual_median.to_csv(f'stats/datasets_{node}_annual_median.csv')
        annual_means.to_csv(f'stats/datasets_{node}_annual_means.csv')
        annual_stds.to_csv(f'stats/datasets_{node}_annual_stds.csv')
        monthly_means.to_csv(f'stats/datasets_{node}_monthly_means.csv')
        monthly_stds.to_csv(f'stats/datasets_{node}_monthly_stds.csv')
        

        # Make a list of historic datasets
        all_datasets = monthly_means.columns.tolist()
                
        # For monthly mean differences:
        # Calculate relative to the 'baseline' for each dataset
        # In this case, the baseline depends on the hydrologic model and forcing

        # Use unique baselines for each
        monthly_means_diff = pd.DataFrame(index=monthly_means.index, columns=monthly_means.columns)
        monthly_means_frac = pd.DataFrame(index=monthly_means.index, columns=monthly_means.columns)
        monthly_means_prc_change = pd.DataFrame(index=monthly_means.index, columns=monthly_means.columns)
        
        monthly_stds_diff = pd.DataFrame(index=monthly_stds.index, columns=monthly_stds.columns)
        monthly_stds_frac = pd.DataFrame(index=monthly_stds.index, columns=monthly_stds.columns)
        monthly_stds_prc_change = pd.DataFrame(index=monthly_stds.index, columns=monthly_stds.columns)

        for use_dataset_baseline in [True, False]:
            
            for dataset in all_datasets:
                # Get the baseline for this dataset
                if use_dataset_baseline:
                    baseline = dataset_baselines.get(dataset, 'pub_nhmv10_BC_withObsScaled')
                else:
                    # Use the reconstruction as baseline
                    baseline = 'pub_nhmv10_BC_withObsScaled'
            
                # Check if baseline exists in the data
                if baseline not in monthly_means.columns:
                    print(f"Warning: Baseline '{baseline}' not found for dataset '{dataset}'. Skipping.")
                    continue
            
                baseline_means = monthly_means[baseline]
                baseline_stds = monthly_stds[baseline]
                    
                # Calculate the difference from the baseline
                monthly_means_diff[dataset] = monthly_means[dataset] - baseline_means
                monthly_means_frac[dataset] = monthly_means[dataset] / baseline_means
                monthly_means_prc_change[dataset] = (monthly_means_diff[dataset] / baseline_means) * 100
                
                monthly_stds_diff[dataset] = monthly_stds[dataset] - baseline_stds
                monthly_stds_frac[dataset] = monthly_stds[dataset] / baseline_stds
                monthly_stds_prc_change[dataset] = (monthly_stds_diff[dataset] / baseline_stds) * 100
            
            # Save monthly means diff
            fdir = './stats/diff_relative_to_dataset_baseline' if use_dataset_baseline else './stats/diff_relative_to_reconstruction'

            # make dir if not exists
            if not os.path.exists(fdir):
                os.makedirs(fdir)
            
            monthly_means_diff.to_csv(f'{fdir}/{node}_monthly_mean_diff_by_dataset_ssp_and_period.csv')
            monthly_means_frac.to_csv(f'{fdir}/{node}_monthly_mean_frac_by_dataset_ssp_and_period.csv')
            monthly_means_prc_change.to_csv(f'{fdir}/{node}_monthly_mean_prc_change_by_dataset_ssp_and_period.csv')
