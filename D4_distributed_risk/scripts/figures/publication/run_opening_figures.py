"""
Run D4 opening figure set (A–D).

Usage
-----
    cd ~/dissertation
    source venv/bin/activate
    python D4_distributed_risk/scripts/figures/publication/run_opening_figures.py
"""
import subprocess
import sys
from pathlib import Path

from _paths import FIGS as FIG_OUTDIR

SCRIPTDIR = Path(__file__).parent
OPENING = [
    ("fig_A_decree_party_map.py", "Figure A — Decree party map"),
    ("fig_B_institutional_rule_cascade.py", "Figure B — Rule cascade"),
    ("fig_C_xlrm_workflow.py", "Figure C — XLRM workflow"),
    ("fig_D_ensemble_drought_envelope.py", "Figure D — Drought envelope"),
]

print("\n=== D4 Opening Figure Set (A–D) ===\n")
results = []
for script, label in OPENING:
    path = SCRIPTDIR / script
    print(f"{label} ...")
    r = subprocess.run([sys.executable, str(path)], capture_output=True, text=True, timeout=180)
    if r.returncode == 0:
        saved = [ln for ln in r.stdout.splitlines() if "Saved:" in ln]
        print(f"  ✅ {saved[0] if saved else 'OK'}")
        results.append((script, "PASS"))
    else:
        err = (r.stderr or r.stdout).strip().splitlines()[-1]
        print(f"  ❌ {err}")
        results.append((script, "FAIL"))

n = sum(1 for _, s in results if s == "PASS")
print(f"\n{n}/{len(results)} opening figures saved to {FIG_OUTDIR}")
