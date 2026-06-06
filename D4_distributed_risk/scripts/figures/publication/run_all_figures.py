"""
Run all D4 publication figures.

Reports which figures succeeded, which need additional data,
and which are pending sweep 3 completion.

Usage
-----
    cd ~/dissertation
    module load python/3.11.5 && source venv/bin/activate
    python D4_distributed_risk/scripts/figures/publication/run_all_figures.py
"""
import subprocess, sys
from pathlib import Path

from _paths import FIGS as FIG_OUTDIR

SCRIPTDIR = Path(__file__).parent
FIGURES = [
    ("fig_E_obligations_vs_exposure.py",  "Part II",  "rrv_summary.parquet"),
    ("fig_F_rrv_fingerprints.py",          "Part II",  "rrv_summary.parquet"),
    ("fig_G_shortfall_sequence.py",        "Part II",  "rrv_summary.parquet"),
    ("fig_H_regime_phase_diagram.py",      "Part III", "rrv_summary.parquet + regime cols"),
    ("fig_I_regime_conditioned_rrv.py",    "Part III", "rrv_summary.parquet + rcrrv cols"),
    ("fig_J_regime_boundary_trace_atlas.py","Part III", "rrv_summary.parquet + member HDF5"),
    ("fig_K_sobol_sensitivity.py",         "Part IV",  "sobol_indices.parquet (sweep 3)"),
    ("fig_L_conditional_sensitivity.py",   "Part IV",  "sobol_mean_metrics.parquet + generation_log"),
    ("fig_M_no_new_loser_frontier.py",     "Part V",   "sobol_mean_metrics.parquet (sweep 3)"),
]

print("\n=== D4 Publication Figure Runner ===\n")
results = []
for script, part, data_needed in FIGURES:
    path = SCRIPTDIR / script
    print(f"[{part}] {script} ...")
    try:
        r = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True, text=True, timeout=300,
        )
        if r.returncode == 0:
            saved = [l for l in r.stdout.splitlines() if "Saved:" in l]
            print(f"  ✅ {saved[0] if saved else 'OK'}")
            results.append((script, "PASS", ""))
        else:
            err = r.stderr.splitlines()[-1] if r.stderr else "unknown error"
            print(f"  ❌ {err}")
            results.append((script, "FAIL", err))
    except subprocess.TimeoutExpired:
        print(f"  ⏱ TIMEOUT")
        results.append((script, "TIMEOUT", ""))
    except Exception as e:
        print(f"  ❌ {e}")
        results.append((script, "ERROR", str(e)))

print("\n" + "="*60)
print(f"{'Script':<45} {'Status':<10} Notes")
print("-"*60)
for script, status, note in results:
    icon = "✅" if status == "PASS" else "❌"
    print(f"{icon} {script:<43} {status:<10} {note[:40] if note else ''}")

n_pass = sum(1 for _, s, _ in results if s == "PASS")
print(f"\n{n_pass}/{len(results)} figures generated successfully.")
print(f"Figures saved to: {FIG_OUTDIR}")
