"""
D1 — Failure surface sweep: run Pywr-DRB across scenario cells.

Usage
-----
    python run_failure_surface_sweep.py --cell-index 0
    python run_failure_surface_sweep.py --all
    python run_failure_surface_sweep.py --cell-index 3 --lb-level LB1 --realizations 1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

import numpy as np
import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "shared"))
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    CONFIG_NAME,
    REALIZATIONS_PER_CELL,
    SIM_END,
    SIM_START,
    iter_cells,
    pilot_lb1_indices,
)
from pywrdrb_utils.run_model import run_single
from pywrdrb_utils.attribution import attribute_regime, LB_TOTAL_CAPACITY_MG

_PERF = Path(__file__).parent.parent / "lib" / "performance"
sys.path.insert(0, str(_PERF))
from criteria import evaluate_cell
from salinity_paths import resolve_salinity_for_run
from salinity_posthoc import predict_salt_front_series

FLOWS_DIR = Path(__file__).parent.parent / "generator" / "synthetic_flows"
PREDICTED_INFLOWS_CACHE = FLOWS_DIR / "predicted_inflows_cache"
RESULTS_DIR = Path(__file__).parent.parent / "results" / "failure_surface" / CONFIG_NAME


def _json_safe(obj: Any) -> Any:
    """Recursively convert numpy types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    return obj


def run_cell(
    cell: dict,
    n_realizations: int | None = None,
    *,
    enable_salinity: bool = True,
    posthoc_salinity: bool = False,
    skip_existing: bool = True,
    require_salinity: bool = False,
    flow_prediction_mode: str | None = "gage_flow",
) -> dict:
    """Run synthetic flow traces for one scenario cell."""
    n_realizations = n_realizations or REALIZATIONS_PER_CELL
    cell_id = cell["cell_id"]
    bin_id = cell["flow_bin"]["id"]
    slr_id = cell["slr_level"]["id"]
    tfo_mgd = cell["tfo_mgd"]
    lb_mult = cell["lb_multiplier"]

    want_salinity = enable_salinity or posthoc_salinity
    enable_salinity, salinity_options, sal_warn = resolve_salinity_for_run(
        want_salinity, SIM_START, SIM_END
    )
    run_salinity_inline = enable_salinity and not posthoc_salinity
    run_salinity_posthoc = posthoc_salinity and enable_salinity
    if require_salinity and not enable_salinity:
        raise FileNotFoundError(
            sal_warn or "PywrDRB-ML plugin required (--require-salinity) but not found."
        )
    if sal_warn:
        logger.warning(sal_warn)

    bin_dir = FLOWS_DIR / bin_id
    if not bin_dir.exists():
        raise FileNotFoundError(
            f"No synthetic flows for bin {bin_id} at {bin_dir}. "
            "Run generator/kirsch_generate.py first."
        )

    cell_outdir = RESULTS_DIR / f"cell_{cell_id}"
    cell_outdir.mkdir(parents=True, exist_ok=True)

    realization_results = []
    for r in range(n_realizations):
        out_path = cell_outdir / f"realization_{r:03d}_metrics.json"
        if skip_existing and out_path.exists():
            with open(out_path) as f:
                realization_results.append(json.load(f))
            continue

        flow_path = bin_dir / f"realization_{r:03d}.parquet"
        if not flow_path.exists():
            raise FileNotFoundError(f"Missing realization file: {flow_path}")

        flow_df = pd.read_parquet(flow_path)
        # Shared across SLR/LB cells — same synthetic flow for a (bin, realization)
        inflow_type = f"d1_{bin_id}_r{r:03d}"

        outputs = run_single(
            flow_df=flow_df,
            inflow_type=inflow_type,
            tfo_override=tfo_mgd,
            lb_cap_multiplier=lb_mult,
            enable_salinity=run_salinity_inline,
            salinity_model_options=salinity_options if run_salinity_inline else None,
            predicted_inflows_cache=PREDICTED_INFLOWS_CACHE,
            flow_prediction_mode=flow_prediction_mode,
        )

        salt_front = outputs.get("salt_front_rm")
        if run_salinity_posthoc:
            trenton = outputs.get("del_trenton_flow", pd.Series(dtype=float))
            schuylkill = outputs.get("schuylkill_flow", pd.Series(dtype=float))
            if len(trenton) and len(schuylkill):
                salt_front = predict_salt_front_series(
                    trenton, schuylkill, SIM_START, SIM_END
                )

        lb_storage = (
            outputs.get("beltzville_volume", pd.Series(dtype=float))
            + outputs.get("blueMarsh_volume", pd.Series(dtype=float))
        )
        ierq = outputs.get("ierq_bank_remaining", pd.Series(dtype=float))

        cell_result = evaluate_cell(
            trenton_flow=outputs.get("del_trenton_flow", pd.Series(dtype=float)),
            tfo_level=tfo_mgd,
            lb_storage=lb_storage,
            lb_capacity_mg=LB_TOTAL_CAPACITY_MG,
            ierq_balance=ierq,
            slr_id=slr_id,
            salt_front_mu=salt_front,
            salinity_enabled=run_salinity_inline or run_salinity_posthoc,
        )
        cell_result["regime"] = attribute_regime(
            ierq_balance=ierq,
            lb_storage=lb_storage,
        )
        cell_result["realization"] = r
        cell_result["failure_mode"] = cell_result["regime"]

        with open(out_path, "w") as f:
            json.dump(_json_safe(cell_result), f, indent=2)

        realization_results.append(cell_result)

    fails_count = sum(1 for res in realization_results if res["cell_fails"])
    sal_fails = sum(
        1 for res in realization_results
        if res.get("salinity", {}).get("fails")
    )
    regimes = [res["regime"] for res in realization_results]

    return {
        "cell_id": cell_id,
        "flow_bin_id": bin_id,
        "slr_id": slr_id,
        "salinity_enabled": run_salinity_inline or run_salinity_posthoc,
        "salinity_posthoc": run_salinity_posthoc,
        "salinity_failure_fraction": sal_fails / n_realizations if n_realizations else 0.0,
        "slr_m": cell["slr_level"]["slr_m"],
        "lb_level_id": cell["lb_level"]["id"],
        "lb_multiplier": lb_mult,
        "tfo_mgd": tfo_mgd,
        "cell_fails": fails_count > 0,
        "failure_fraction": fails_count / n_realizations,
        "dominant_regime": max(set(regimes), key=regimes.count) if regimes else "none",
        "n_realizations": n_realizations,
    }


def _filter_cells(cells: list[dict], lb_level: str | None) -> list[dict]:
    if lb_level is None:
        return cells
    return [c for c in cells if c["lb_level"]["id"] == lb_level]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--cell-index", type=int, help="0-based index into filtered cell list")
    group.add_argument("--all", action="store_true", help="Run all filtered cells sequentially")
    ap.add_argument("--lb-level", default=None, help="Filter to LB0, LB1, or LB2 (pilot: LB1)")
    ap.add_argument("--realizations", type=int, default=None, help="Override REALIZATIONS_PER_CELL")
    ap.add_argument(
        "--no-salinity",
        action="store_true",
        help="Disable SalinityLSTM (Trenton/LB criteria only)",
    )
    ap.add_argument(
        "--require-salinity",
        action="store_true",
        help="Fail if PywrDRB-ML plugin missing (no fallback)",
    )
    ap.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Re-run all realizations even if metrics JSON exists",
    )
    ap.add_argument(
        "--posthoc-salinity",
        action="store_true",
        help="Run SalinityLSTM after Pywr-DRB (faster than in-model coupling)",
    )
    ap.add_argument(
        "--flow-prediction-mode",
        default="gage_flow",
        choices=["regression_disagg", "perfect_foresight", "gage_flow"],
        help="FFMP forecast mode (default gage_flow for speed)",
    )
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    enable_salinity = not args.no_salinity
    skip_existing = not args.no_skip_existing
    flow_mode = None if args.flow_prediction_mode == "regression_disagg" else args.flow_prediction_mode

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    all_cells = list(iter_cells())
    cells = _filter_cells(all_cells, args.lb_level)

    if args.all:
        results = []
        for i, cell in enumerate(cells):
            print(f"[{i + 1}/{len(cells)}] {cell['cell_id']}")
            results.append(
                run_cell(
                    cell,
                    n_realizations=args.realizations,
                    enable_salinity=enable_salinity,
                    posthoc_salinity=args.posthoc_salinity,
                    skip_existing=skip_existing,
                    require_salinity=args.require_salinity,
                    flow_prediction_mode=flow_mode,
                )
            )
        summary_path = RESULTS_DIR / "failure_surface_summary.parquet"
        pd.DataFrame(results).to_parquet(summary_path)
        print(f"Summary: {summary_path}")
        print(f"Failed: {sum(r['cell_fails'] for r in results)} / {len(results)}")
    else:
        idx = args.cell_index
        if idx < 0 or idx >= len(cells):
            raise ValueError(f"--cell-index must be 0–{len(cells) - 1}; got {idx}")
        cell = cells[idx]
        print(f"Running cell {idx} (global may differ): {cell['cell_id']}")
        result = run_cell(
            cell,
            n_realizations=args.realizations,
            enable_salinity=enable_salinity,
            posthoc_salinity=args.posthoc_salinity,
            skip_existing=skip_existing,
            require_salinity=args.require_salinity,
            flow_prediction_mode=flow_mode,
        )
        out = RESULTS_DIR / f"cell_summary_{cell['cell_id']}.json"
        with open(out, "w") as f:
            json.dump(result, f, indent=2)
        print(
            f"Result: fails={result['cell_fails']}, "
            f"failure_fraction={result['failure_fraction']:.2f}, "
            f"regime={result['dominant_regime']}"
        )
