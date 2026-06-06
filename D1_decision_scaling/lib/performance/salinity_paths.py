"""
Resolve PywrDRB-ML plugin path and build ModelBuilder salinity_model options.

Requires PywrDRB-ML (SalinityLSTM). Default clone location:
    D1_decision_scaling/stochastic_experiment/PywrDRB-ML
    git clone https://github.com/Pywr-DRB/PywrDRB-ML.git <that path>
Override: export PYWRDRB_ML_PLUGIN_PATH=/path/to/PywrDRB-ML
"""

from __future__ import annotations

import os
from pathlib import Path


def resolve_pywrdrb_ml_plugin_path() -> Path:
    """
    Return absolute path to PywrDRB-ML plugin root.

    Search order:
      1. PYWRDRB_ML_PLUGIN_PATH environment variable
      2. D1_decision_scaling/stochastic_experiment/PywrDRB-ML
      3. ~/PywrDRB-ML, ~/dissertation/PywrDRB-ML
    """
    env = os.environ.get("PYWRDRB_ML_PLUGIN_PATH")
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "models" / "SalinityLSTM").exists():
            return p

    repo = Path(__file__).resolve().parents[2]
    candidates = [
        repo / "stochastic_experiment" / "PywrDRB-ML",
        Path.home() / "PywrDRB-ML",
        Path.home() / "dissertation" / "PywrDRB-ML",
    ]
    for p in candidates:
        p = p.resolve()
        if (p / "models" / "SalinityLSTM").exists():
            return p

    searched = [env or "(unset PYWRDRB_ML_PLUGIN_PATH)"] + [str(c) for c in candidates]
    raise FileNotFoundError(
        "PywrDRB-ML plugin not found. SalinityLSTM requires the private plugin.\n"
        "Set: export PYWRDRB_ML_PLUGIN_PATH=/path/to/PywrDRB-ML\n"
        f"Searched: {searched}"
    )


def try_resolve_pywrdrb_ml_plugin_path() -> Path | None:
    """Return plugin path if found, else None (no exception)."""
    try:
        return resolve_pywrdrb_ml_plugin_path()
    except FileNotFoundError:
        return None


def build_salinity_model_options(start_date: str, end_date: str) -> dict:
    """Options dict for ModelBuilder(options={'salinity_model': ...})."""
    plugin = resolve_pywrdrb_ml_plugin_path()
    model_yml = plugin / "models" / "SalinityLSTM" / "SalinityLSTM.yml"
    if not model_yml.exists():
        raise FileNotFoundError(f"SalinityLSTM config not found: {model_yml}")

    return {
        "ml_model_type": "lstm",
        "PywrDRB_ML_plugin_path": str(plugin),
        "model_salinity": str(model_yml),
        "start_date": start_date,
        "end_date": end_date,
        "Q_Trenton_lstm_var_name": "Q_Trenton_bc",
        "Q_Schuylkill_lstm_var_name": "Q_Schuylkill_bc",
        "asycronized_update": False,
        "debug": False,
    }


def resolve_salinity_for_run(
    requested: bool,
    start_date: str,
    end_date: str,
) -> tuple[bool, dict | None, str | None]:
    """
    Decide whether to enable SalinityLSTM for this run.

    Returns (enable_salinity, salinity_model_options, warning_message).
    If requested but plugin missing, disables salinity and returns a warning string.
    """
    if not requested:
        return False, None, None
    plugin = try_resolve_pywrdrb_ml_plugin_path()
    if plugin is None:
        return (
            False,
            None,
            "SalinityLSTM requested but PywrDRB-ML not found — "
            "set PYWRDRB_ML_PLUGIN_PATH. Running Trenton/LB criteria only.",
        )
    return True, build_salinity_model_options(start_date, end_date), None
