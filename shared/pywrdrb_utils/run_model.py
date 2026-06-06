"""
Single Pywr-DRB run wrapper — shared by D1 (per scenario cell) and D4 (per ensemble member).

pywrdrb run pattern (from cmip6/02_run_pywrdrb_simulations.py):
    mb = pywrdrb.ModelBuilder(inflow_type=dataset_name, start_date=..., end_date=...)
    mb.make_model()
    mb.write_model(json_path)
    model = pywrdrb.Model.load(json_path)
    recorder = pywrdrb.OutputRecorder(model, output_filename=hdf5_path, parameters=[...])
    model.run()
    # Results in hdf5_path; read back with h5py or pywrdrb.Data.load_from_export()

For synthetic inputs (D1 Kirsch flows), pywrdrb.ModelBuilder expects an inflow_type
that corresponds to a folder under pywrdrb/data/ or a custom inputs directory.
The caller must write flow CSVs to the right location before calling run_single().

Usage
-----
    from shared.pywrdrb_utils.run_model import run_single, OUTPUT_VARS

    outputs = run_single(
        flow_df=flow_df,           # DataFrame: DatetimeIndex × node-name columns (MGD)
        inflow_type="synthetic_d1_Q04_S2_LB1_r012",  # unique name for this run
        tfo_override=1900.0,       # MGD — D1 only; None → model default
        lb_cap_multiplier=1.0,     # D1 only; 1.0 = current FFMP
        workdir=Path("/tmp/pywrdrb_run_xyz"),
    )

Output variables
----------------
See OUTPUT_VARS dict — keyed by short name, valued by pywrdrb recorder name.
"""

from __future__ import annotations

import shutil
import tempfile
import h5py
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Output variable names to extract from HDF5
# Key  = short name used by D1/D4 scripts
# Value = pywrdrb recorder name (parameter or node name as registered in model)
#
# Recorder names confirmed against actual HDF5 output 2026-06-01 (member 0 run).
# ---------------------------------------------------------------------------
OUTPUT_VARS: dict[str, str] = {
    # Node flows — NumpyArrayNodeRecorder, key = node name (link_* prefix in pywrdrb).
    # link_delTrenton range [607, 88439 MGD]; link_delMontague range [452, 75763 MGD].
    "del_trenton_flow":    "link_delTrenton",
    "del_montague_flow":   "link_delMontague",
    # IERQ daily release — IERQRelease_step1 instance is named "nyc_mrf_trenton_step1"
    # in model JSON (confirmed from model JSON 2026-06-01). Records daily IERQ draw
    # (MG released per day), NOT the bank balance. metrics.py calls
    # reconstruct_ierq_balance() to back-calculate balance (6090 MG max, May 31 reset).
    "ierq_bank_remaining": "nyc_mrf_trenton_step1",
    # ERQ daily release — ERQRelease parameter (aggregate across all 3 NYC reservoirs).
    # 1954 Decree Art. III-B-1(c)-(d): cooperative excess release, June 15 – March 15.
    # Units: MGD (total NYC contribution). Zero outside seasonal period.
    "erq_release_nyc":     "erq_release_nyc",
    # Reservoir storage — NumpyArrayStorageRecorder (MG). Confirmed ✅
    "beltzville_volume":   "reservoir_beltzvilleCombined",
    "blueMarsh_volume":    "reservoir_blueMarsh",
    # Drought stage — IndexParameter (0–2 LB, 0–6 NYC). Confirmed ✅
    "lb_drought_stage":    "drought_level_agg_lb",
    "nyc_drought_stage":   "drought_level_agg_nyc",
    # NJ delivery — node recorder (MGD). Confirmed ✅
    "nj_delivery":         "delivery_nj",
    # Salinity LSTM (requires PywrDRB-ML + enable_salinity=True in run_single)
    "salt_front_rm":       "salt_front_location_mu",
    "schuylkill_flow":     "link_outletSchuylkill",
}

# Required inflow CSV filename — must match pywrdrb input loader expectation
INFLOW_CSV_NAME = "gage_flow_mgd.csv"


# ---------------------------------------------------------------------------
# Flow input preparation
# ---------------------------------------------------------------------------

def write_synthetic_inputs(
    flow_df: pd.DataFrame,
    inputs_dir: Path,
) -> None:
    """
    Write a synthetic flow DataFrame as pywrdrb-compatible input CSVs.

    Creates a directory containing:
      - gage_flow_mgd.csv         : flow_df (DatetimeIndex × node names, MGD)
      - catchment_inflow_mgd.csv  : same data (pywrdrb ModelBuilder reads this for catchment routing)

    Note: predicted_inflows_mgd.csv is NOT written here.  It is generated
    by PredictedInflowPreprocessor in run_single() after path navigator registration,
    since it requires regression models and a registered pn path.

    Parameters
    ----------
    flow_df : pd.DataFrame
        Synthetic flows.  Index: DatetimeIndex.  Columns: pywrdrb node names (MGD).
    inputs_dir : Path
        Target directory; will be created if it doesn't exist.
    """
    inputs_dir.mkdir(parents=True, exist_ok=True)
    flow_df.index.name = "datetime"
    flow_df.to_csv(inputs_dir / INFLOW_CSV_NAME)
    # catchment_inflow_mgd.csv — ModelBuilder reads this for catchment routing.
    # For Amestoy obs_pub_nhmv10_BC_ObsScaled, gage flows and catchment inflows
    # are the same data (bias-corrected to observations).
    flow_df.to_csv(inputs_dir / "catchment_inflow_mgd.csv")


# ---------------------------------------------------------------------------
# Core run function
# ---------------------------------------------------------------------------

def _generate_predicted_inflows(
    inflow_type: str,
    inputs_dir: Path,
    *,
    flow_prediction_mode: str | None = None,
) -> None:
    """
    Run PredictedInflowPreprocessor to generate predicted_inflows_mgd.csv.

    Called by run_single() when the file doesn't exist and no cache is available.
    Saves to inputs_dir / "predicted_inflows_mgd.csv".

    WARNING: This takes ~5–10 minutes for a 28,854-day time series.
    For batch Sobol runs, pre-generate once and use predicted_inflows_cache.
    """
    from pywrdrb.pre import PredictedInflowPreprocessor
    if flow_prediction_mode == "gage_flow":
        modes = ("gage_flow",)
    else:
        modes = ("regression_disagg", "gage_flow")
    predictor = PredictedInflowPreprocessor(
        flow_type=inflow_type,
        modes=modes,
    )
    # Call load() explicitly before process():
    # process() checks `self.gage_data is None` but the base class __init__
    # never sets gage_data → AttributeError.  load() initializes it to None.
    predictor.load()
    predictor.process()
    predictor.save()


# ---------------------------------------------------------------------------
# LB cap multiplier injection (D1 axis 3 / D4 Sobol m_lb)
# ---------------------------------------------------------------------------

def _inject_lb_cap_multiplier(model_dict: dict, multiplier: float) -> None:
    """Set cap_multiplier on all LowerBasinMaxMRFContribution parameters."""
    if multiplier == 1.0:
        return
    for key, spec in model_dict.get("parameters", {}).items():
        if (
            key.startswith("max_mrf_trenton_step")
            and spec.get("type") == "LowerBasinMaxMRFContribution"
        ):
            spec["cap_multiplier"] = float(multiplier)


def run_single(
    flow_df: pd.DataFrame,
    inflow_type: str,
    tfo_override: Optional[float] = None,
    lb_cap_multiplier: float = 1.0,
    sensitivity_params: Optional[dict] = None,
    nyc_nj_demand_source: Optional[str] = None,
    predicted_inflows_cache: Optional[Path] = None,
    enable_salinity: bool = False,
    salinity_model_options: Optional[dict] = None,
    flow_prediction_mode: Optional[str] = None,
    workdir: Optional[Path] = None,
    cleanup: bool = True,
) -> dict[str, pd.Series]:
    """
    Run a single Pywr-DRB simulation and return output time series.

    Parameters
    ----------
    flow_df : pd.DataFrame
        Streamflow inputs.  DatetimeIndex, columns = pywrdrb inflow node names (MGD).
        For D1: one Kirsch-Nowak realization for a given streamflow percentile bin.
        For D4: one member from the Amestoy 1000-member ensemble.
    inflow_type : str
        Unique identifier for this run's input dataset.  Also used as:
        - Subfolder name under pywrdrb path navigator's input root
        - Stem of JSON model file and HDF5 output file
    tfo_override : float or None
        If provided, overrides the Trenton Flow Objective (MGD).
        Implemented by patching ``mrf_baseline_delTrenton`` constant in constants.csv
        before building the model.  Used in D1 for SLR-driven TFO elevation.
    lb_cap_multiplier : float
        Multiplier on LB Max MRF daily contribution cap (1.0 = current FFMP).
        Injected as ``cap_multiplier`` on LowerBasinMaxMRFContribution parameters.
    sensitivity_params : dict or None
        Optional dict of Sobol/sensitivity parameter overrides.  Supported keys:

        * ``alpha_betz_warning`` (float) — LB Beltzville warning fraction (default 0.737)
          Injected as ``betz_warning_frac`` into the drought_level_agg_lb model_dict entry.
        * ``alpha_bm_warning`` (float) — LB Blue Marsh warning fraction (default 0.689)
          Injected as ``bm_warning_frac`` into the drought_level_agg_lb model_dict entry.
        * ``tau_recovery`` (float/int) — LB exit hysteresis days (default 30)
          Injected as ``recovery_persist_days`` into drought_level_agg_lb.
        * ``m_lb`` (float) — LB max MRF contribution multiplier (same as lb_cap_multiplier).
        * ``q_nj_warning`` (float) — NJ warning stage delivery cap (MGD).
          Injected into constants.csv or model_dict NJ parameter (TODO: confirm key).
        * ``ierq_max_bg`` (float) — IERQ annual ceiling (BG/yr).
          Injected into model_dict IERQ bank parameter (TODO: confirm key).
        * ``erq_fraction`` (float) — ERQ release fraction (Decree default: 0.83).
          1954 Decree Art. III-B-1(c): "83 per cent" of consumption-below-safe-yield.
          NOTE: at typical pywrdrb NYC consumption (~545 MGD avg), the 70 BG cap
          always binds so this parameter has near-zero Sobol sensitivity.
        * ``erq_cap_mg`` (float) — ERQ seasonal release cap (Decree: 70,000 MG = 70 BG).
          1954 Decree Art. III-B-1(d): "shall in no event exceed 70 billion gallons."
          This is the operationally meaningful ERQ Sobol parameter.
          Sobol range: [50,000, 100,000] MG (50–100 BG).

    nyc_nj_demand_source : str or None
        Controls how pywrdrb sources NYC/NJ diversion demands.
        None (default) → use pywrdrb's standard historical demand files.
        'custom' → expect custom CSV files (diversion_nyc_extrapolated_mgd.csv etc.)
        in the inputs_dir.  Use 'custom' only for D1 synthetic runs where
        custom demand files are provided alongside Kirsch/Gosney flows.
        D4 rerun always uses None (standard historical demands).
    enable_salinity : bool
        If True, enable SalinityModelLSTM in ModelBuilder (requires PywrDRB-ML plugin).
    salinity_model_options : dict or None
        ModelBuilder salinity_model options. If None and enable_salinity is True,
        caller must set options via D1 performance.salinity_paths.build_salinity_model_options().
    flow_prediction_mode : str or None
        FFMP flow forecast mode: ``regression_disagg`` (default), ``perfect_foresight``,
        or ``gage_flow``. D1 fast path often uses ``gage_flow`` when pre-warmed.
    predicted_inflows_cache : Path or None
        Optional cache directory for predicted_inflows_mgd.csv files.
        If provided, run_single() checks {predicted_inflows_cache}/{inflow_type}/
        predicted_inflows_mgd.csv before generating.  If the cached file doesn't
        exist, generates it and stores in the cache for future use.
        STRONGLY RECOMMENDED for Sobol sweeps: predictions are a function of
        streamflow only (not policy params), so the same file can be reused for
        all 14,336 Sobol samples of the same ensemble member.
        Set to a stable path like ~/data/amestoy_2026/predicted_inflows_cache/.
    workdir : Path or None
        Working directory for JSON, HDF5, and temporary input files.
        If None, a temp directory is used and cleaned up after the run.
    cleanup : bool
        If True and workdir was auto-created, delete it after extracting outputs.

    Returns
    -------
    dict[str, pd.Series]
        Keys from OUTPUT_VARS.  Each value is a daily pd.Series with DatetimeIndex.
        Missing recorders return an empty Series rather than raising.

    Notes
    -----
    tfo_override : Patches mb.model_dict["parameters"]["mrf_baseline_delTrenton"]
    after make_model() and before write_model().  Pywr reads this constant at model load time.

    lb_cap_multiplier : Injected via cap_multiplier on max_mrf_trenton_step*_* parameters.
    """
    try:
        import pywrdrb
    except ImportError as e:
        raise ImportError(
            "pywrdrb not found.  Activate the dissertation venv:\n"
            "  module load python/3.11.5 && source ~/dissertation/venv/bin/activate"
        ) from e

    if sensitivity_params and "m_lb" in sensitivity_params:
        lb_cap_multiplier = float(sensitivity_params["m_lb"])

    # Set up working directory
    auto_workdir = workdir is None
    if auto_workdir:
        workdir = Path(tempfile.mkdtemp(prefix=f"pywrdrb_{inflow_type}_"))

    json_path   = workdir / f"{inflow_type}.json"
    hdf5_path   = workdir / f"{inflow_type}.hdf5"

    try:
        # --- Write synthetic inputs to pywrdrb-expected location ---
        # pywrdrb.ModelBuilder looks for inputs relative to the path navigator's root.
        # We write to a local workdir subfolder and register the path before building.
        inputs_dir = workdir / "inputs" / inflow_type
        write_synthetic_inputs(flow_df, inputs_dir)

        # --- Register path with pywrdrb path navigator ---
        # Pattern from cmip6/02_run_pywrdrb_simulations.py:
        #   pn_config[f"flows/{dataset}"] = os.path.abspath(inputs_folder)
        # This tells ModelBuilder (and PredictedInflowPreprocessor) where to find
        # the input CSVs for this inflow_type.
        pn_config = pywrdrb.get_pn_config()
        pn_config[f"flows/{inflow_type}"] = str(inputs_dir.resolve())
        pywrdrb.load_pn_config(pn_config)

        # --- Generate predicted_inflows_mgd.csv (required by ModelBuilder) ---
        # PredictedInflowPreprocessor uses AR regression on catchment inflows to produce
        # 1–4 day ahead flow forecasts at Montague and Trenton, used for drought outlook.
        # Saves to pn.sc.get(f"flows/{inflow_type}") / "predicted_inflows_mgd.csv"
        # = inputs_dir / "predicted_inflows_mgd.csv" (after pn registration above).
        #
        # PERFORMANCE NOTE: The prediction loop (28,854 timesteps × 14 node-lag pairs)
        # takes ~5–10 minutes in pure Python.  For Sobol sweeps (50 members × 14,336
        # samples), the predictions are IDENTICAL across samples for the same member —
        # they depend only on streamflow, not on policy parameters.
        # Cache them by copying from a stable path keyed by inflow_type:
        #   {predicted_inflows_cache} / {inflow_type} / predicted_inflows_mgd.csv
        # Pass predicted_inflows_cache=<path> to run_single() to enable caching.
        predicted_inflows_path = inputs_dir / "predicted_inflows_mgd.csv"
        if not predicted_inflows_path.exists():
            if predicted_inflows_cache is not None:
                # Check if cached version exists; copy it if so
                cache_src = (
                    Path(predicted_inflows_cache)
                    / inflow_type
                    / "predicted_inflows_mgd.csv"
                )
                if cache_src.exists():
                    shutil.copy2(cache_src, predicted_inflows_path)
                else:
                    # Generate and store in cache for future use
                    _generate_predicted_inflows(
                        inflow_type, inputs_dir, flow_prediction_mode=flow_prediction_mode
                    )
                    cache_src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(predicted_inflows_path, cache_src)
            else:
                # No cache — generate directly (slow; fine for single runs + smoke tests)
                _generate_predicted_inflows(
                    inflow_type, inputs_dir, flow_prediction_mode=flow_prediction_mode
                )

        start_date = flow_df.index.min().strftime("%Y-%m-%d")
        end_date   = flow_df.index.max().strftime("%Y-%m-%d")

        # --- Build model JSON ---
        # nyc_nj_demand_source:
        #   None     → use pywrdrb standard historical demand files (D4 rerun)
        #   'custom' → expect custom CSVs alongside Kirsch/Gosney inputs (D1)
        mb_options = {}
        if nyc_nj_demand_source is not None:
            mb_options["nyc_nj_demand_source"] = nyc_nj_demand_source
        if enable_salinity:
            if salinity_model_options is None:
                raise ValueError(
                    "enable_salinity=True requires salinity_model_options "
                    "(use D1 performance.salinity_paths.build_salinity_model_options)."
                )
            mb_options["salinity_model"] = salinity_model_options
        if flow_prediction_mode is not None:
            mb_options["flow_prediction_mode"] = flow_prediction_mode

        mb = pywrdrb.ModelBuilder(
            inflow_type=inflow_type,
            start_date=start_date,
            end_date=end_date,
            options=mb_options,   # {} when no overrides; never None (Options(**None) fails)
        )
        mb.make_model()

        # --- Inject TFO override (D1 only) ---
        # After make_model(), patch mrf_baseline_delTrenton from CSV-lookup to fixed value.
        # pywrdrb uses this constant × monthly drought factor = mrf_target_delTrenton.
        # mb.model_dict is a plain dict — safe to mutate before write_model().
        if tfo_override is not None:
            mb.model_dict["parameters"]["mrf_baseline_delTrenton"] = {
                "type": "constant",
                "value": float(tfo_override),
            }

        _inject_lb_cap_multiplier(mb.model_dict, lb_cap_multiplier)

        # --- Inject sensitivity / Sobol parameter overrides ---
        # LowerBasinDroughtLevel now accepts betz_warning_frac, bm_warning_frac,
        # recovery_persist_days as optional kwargs (added 2026-05-31).  They are
        # passed through load() via **data, so we add them to the model_dict entry.
        # The JSON key for LowerBasinDroughtLevel is "drought_level_agg_lb".
        if sensitivity_params:
            sp = sensitivity_params

            # LB drought threshold overrides — injected into LowerBasinDroughtLevel
            lb_drought_key = "drought_level_agg_lb"
            if lb_drought_key in mb.model_dict.get("parameters", {}):
                if "alpha_betz_warning" in sp:
                    mb.model_dict["parameters"][lb_drought_key]["betz_warning_frac"] = \
                        float(sp["alpha_betz_warning"])
                if "alpha_bm_warning" in sp:
                    mb.model_dict["parameters"][lb_drought_key]["bm_warning_frac"] = \
                        float(sp["alpha_bm_warning"])
                if "tau_recovery" in sp:
                    mb.model_dict["parameters"][lb_drought_key]["recovery_persist_days"] = \
                        int(round(sp["tau_recovery"]))

            # m_lb handled via lb_cap_multiplier above (also set from sp at run start)

            # NJ warning cap injection — §2.5.6.C.1, FFMP §2.5.6.C.1
            # lb_level1_factor_delivery_nj is loaded from constants.csv as a fraction
            # of NJ normal cap (100 MGD).  q_nj_warning is in MGD; convert to fraction.
            # lb_level0 = normal (1.0), lb_level1 = warning, lb_level2 = drought.
            # We patch lb_level1 only; lb_level2 (drought, 65 MGD) is kept at baseline.
            if "q_nj_warning" in sp:
                nj_warning_frac = float(sp["q_nj_warning"]) / 100.0  # 100 MGD = normal cap
                nj_level1_key = "lb_level1_factor_delivery_nj"
                if nj_level1_key in mb.model_dict.get("parameters", {}):
                    # Replace CSV-backed constant with inline value
                    mb.model_dict["parameters"][nj_level1_key] = {
                        "type": "constant",
                        "value": nj_warning_frac,
                    }

            # IERQ annual ceiling injection — 1954 Decree Art. VII; FFMP §2.c.i
            # ierq_max_bg is in BG/yr; convert to MG (1 BG = 1000 MG).
            # Patches max_bank_volumes["trenton"] in banks.py via model_dict override:
            # IERQRelease_step1 reads max_bank_volumes at __init__ time, so we inject
            # a "max_bank_volume" kwarg into the model_dict entry before model load.
            if "ierq_max_bg" in sp:
                ierq_max_mg = float(sp["ierq_max_bg"]) * 1000.0  # BG → MG
                ierq_key_bank = "nyc_mrf_trenton_step1"
                if ierq_key_bank in mb.model_dict.get("parameters", {}):
                    mb.model_dict["parameters"][ierq_key_bank]["max_bank_volume"] = ierq_max_mg

            # ERQ parameters — 1954 Decree Art. III-B-1(c)-(d).
            # Note: at typical pywrdrb NYC consumption (~545 MGD avg), the raw ERQ
            # always exceeds the 70 BG seasonal cap, so erq_fraction has near-zero
            # Sobol sensitivity.  The operationally meaningful parameter is erq_cap_mg
            # (the Art. III-B-1(d) cap), which determines how much NYC must release.
            erq_key = "erq_release_nyc"
            if erq_key in mb.model_dict.get("parameters", {}):
                if "erq_fraction" in sp:
                    mb.model_dict["parameters"][erq_key]["erq_fraction"] = \
                        float(sp["erq_fraction"])
                if "erq_cap_mg" in sp:
                    # Sobol range [50000, 100000] MG (= 50–100 BG)
                    mb.model_dict["parameters"][erq_key]["erq_cap_mg"] = \
                        float(sp["erq_cap_mg"])
            elif "erq_fraction" in sp or "erq_cap_mg" in sp:
                import warnings
                warnings.warn(
                    "erq_fraction/erq_cap_mg injection skipped — 'erq_release_nyc' "
                    "parameter not found in model_dict. Ensure pywrdrb ERQRelease is wired.",
                    UserWarning,
                    stacklevel=2,
                )

        mb.write_model(str(json_path))

        # --- Load and run ---
        model = pywrdrb.Model.load(str(json_path))
        recorder = pywrdrb.OutputRecorder(
            model=model,
            output_filename=str(hdf5_path),
            parameters=[p for p in model.parameters if p.name],
        )
        model.run()

        # --- Extract outputs from HDF5 ---
        outputs = _read_hdf5_outputs(hdf5_path)

    finally:
        if auto_workdir and cleanup:
            shutil.rmtree(workdir, ignore_errors=True)

    return outputs


# ---------------------------------------------------------------------------
# HDF5 reader
# ---------------------------------------------------------------------------

def _read_hdf5_outputs(hdf5_path: Path) -> dict[str, pd.Series]:
    """
    Read pywrdrb HDF5 output file and return dict of pd.Series for OUTPUT_VARS.

    The HDF5 structure written by OutputRecorder.to_hdf5():
      hdf["time"]        : list of datetime strings
      hdf[param_name]    : numpy array shape (n_timesteps,) for single scenario
    """
    outputs: dict[str, pd.Series] = {}

    with h5py.File(hdf5_path, "r") as hdf:
        # Parse datetime index
        try:
            datetimes = pd.to_datetime([d.decode() if isinstance(d, bytes) else d
                                        for d in hdf["time"]])
        except KeyError:
            datetimes = None

        available_keys = set(hdf.keys())

        for short_name, recorder_name in OUTPUT_VARS.items():
            if recorder_name in available_keys:
                arr = np.asarray(hdf[recorder_name])
                # Shape may be (n_timesteps,) or (n_timesteps, 1) for single scenario
                if arr.ndim > 1:
                    arr = arr[:, 0]
                series = pd.Series(
                    arr,
                    index=datetimes,
                    name=short_name,
                    dtype=float,
                )
                outputs[short_name] = series
            else:
                outputs[short_name] = pd.Series(dtype=float, name=short_name)

    return outputs
