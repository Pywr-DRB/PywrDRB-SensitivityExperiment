
Information about the folder/file naming convention and the contents of the files can be found in the [HydroShare README here](https://hydrosource2.ornl.gov/files/SWA9505V3Flow/README_9505V3Flow.txt).

This dataset can be accessed through one of the following approaches:
- [HydroSource Download](https://hydrosource2.ornl.gov/files/SWA9505V3Flow/)
- [Globus (Recommended) Download](https://doi.org/10.13139/OLCF/2318650)


## Workflow

```
cd CMPI6_multimodel_streamflow/
module load python/3.11.5
python -m virtualenv venv
source venv/bin/activate
pip install git+https://github.com/Pywr-DRB/Pywr-DRB.git
```
This workflow requires pywrdrb>=2.1.0.


`00_preprocessing.py`
    Extracts streamflow at Pywr-DRB nodes from the NetCDF files downloaded from Globus. 
    If you are cloning this repo from GitHub, then this script does _not_ need to be used.  This is only used when new NetCDFs are being processed. 
    After this script is run, `gage_flow_mgd.csv` files will be saved in the `pywrdrb/inputs/<dataset_name>` folder. 


`01_prep_pywrdrb_inputs.py`
    Based on the `gage_flow_mgd.csv` files from each dataset (`pywrdrb/inputs/<dataset_name>`) this script will generate all of the supplemental inputs needed for a Pywr-DRB run, including:
        - catchment inflows
        - predicted inflows
        - extrapolated diversions
        - predicted diversions


`02_run_pywrdrb_simulations.py`
    This script will run Pywr-DRB simulations using all of the processed inputs.  



> All of the scripts titled `S*_` are being used by Trevor to determine a subset of climate scenarios and should be considered under development.


## Climate Scenario Selection Scripts

The following scripts are used to analyze CMIP6 climate projections and select representative scenarios for Pywr-DRB simulations:

`S1_compare_historic_data.py`
    Compares historic streamflow from PRMS and VIC hydrologic models against observed data (pub_nhmv10_BC_withObsScaled) using statistical metrics including Nash-Sutcliffe Efficiency, percent bias, monthly correlation coefficients, and seasonal timing analysis. This analysis determines which hydrologic model better reproduces historic flow patterns for NYC aggregate inflows.

`S2_calculate_annual_monthly_stats.py`
    Calculates annual and monthly statistics (means, standard deviations) for all CMIP6 datasets at specified nodes. Computes percentage changes relative to both dataset-specific baselines and the reconstruction baseline. Outputs are saved to CSV files in the `stats/` directory for use in downstream analysis and scenario selection.

`S3_find_scenarios.py`
    Simplified approach to select representative climate scenarios. Filters CMIP6 scenarios using IQR method to remove outliers, calculates weighted average streamflow changes across all months, and selects three representative scenarios (low, medium, high) based on ranked weighted averages. Provides a straightforward alternative to the quantile interpolation approach in S3.


