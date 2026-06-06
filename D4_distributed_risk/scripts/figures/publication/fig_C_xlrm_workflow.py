"""
Figure C — XLRM experimental design and workflow architecture

Tier 1 (Amestoy baseline) and Tier 2 (Sobol sensitivity) paths shown
explicitly within the XLRM frame.

Output
------
figures/publication/fig_C_xlrm_workflow.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

from _paths import FIGS, PARTY_COLORS, set_style

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

TIER1_X = ("Amestoy 1000-member\nreconstruction", "Historical climate · drought clustering\nFixed FFMP rules · Tier 1")
TIER2_X = ("Kirsch–Nowak 50\nsynthetic traces", "SOW mean-shift −20%…+20%\nPolicy-space exploration · Tier 2")

LEVERS = [
    (r"$\alpha_{BW}$, $\alpha_{BM}$", "LB warning thresholds"),
    (r"$m_{LB}$", "LB MRF multiplier"),
    (r"$I_{max}$, $C_{ERQ}$", "IERQ / ERQ caps"),
    (r"$Q_{NJ,W}$", "NJ warning delivery"),
]

TIER1_CHAIN = [
    ("Party mapping", "notes/party_mapping/"),
    ("Baseline ensemble", "experiments/run_d4_baseline.py\n1000 members"),
    ("Per-party RRV", "lib/rrv_metrics/metrics.py"),
    ("Regime attribution", "NYC- vs LB-limited"),
]

TIER2_CHAIN = [
    ("Sobol design", "lib/sensitivity/sobol_design.py\nN=1024 · k=6"),
    ("Sensitivity sweep", "experiments/run_sobol_sweep.py\n14,336 samples"),
    ("RQ3 analysis", "scripts/analysis/rq3_*.py"),
]

METRICS = [
    ("RQ1", "Per-party RRV asymmetry", "Tier 1", PARTY_COLORS["DE"]),
    ("RQ2", "Regime-conditioned risk", "Tier 1", PARTY_COLORS["NYC"]),
    ("RQ3", "Sobol S₁ / Sₜ tradeoffs", "Tier 2", PARTY_COLORS["PA"]),
]


def _region(ax, x, y, w, h, title, color):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=color, alpha=0.10, edgecolor=color, linewidth=2,
    ))
    ax.text(x + w / 2, y + h - 0.25, title, ha="center", va="top",
            fontsize=10, fontweight="bold", color=color)


def _box(ax, x, y, w, h, title, sub, edge, tier_bg=None):
    fc = tier_bg if tier_bg else "white"
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor=fc, edgecolor=edge, linewidth=1.2,
    ))
    ax.text(x + w / 2, y + h * 0.65, title, ha="center", va="center", fontsize=7.5, fontweight="bold")
    ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=6, color="#555555")


def make_figure():
    fig, ax = plt.subplots(figsize=(15, 9))
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 10)
    ax.axis("off")

    _region(ax, 0.2, 0.4, 3.0, 9.0, "X — Uncertainties", "#5e3c99")
    _region(ax, 3.4, 0.4, 3.2, 9.0, "L — Levers\n(Tier 2 only)", "#e66101")
    _region(ax, 6.8, 0.4, 4.8, 9.0, "R — Relationships (model chain)", "#4dac26")
    _region(ax, 11.8, 0.4, 2.8, 9.0, "M — Metrics & RQs", "#2166ac")

    # Tier 1 / Tier 2 uncertainty boxes
    _box(ax, 0.35, 6.8, 2.7, 1.8, TIER1_X[0], TIER1_X[1], "#5e3c99", "#f0ebf7")
    _box(ax, 0.35, 4.2, 2.7, 1.8, TIER2_X[0], TIER2_X[1], "#5e3c99", "#ede7f6")
    ax.text(1.7, 3.85, "Tier 1 → RQ1–2", ha="center", fontsize=7, style="italic", color="#5e3c99")
    ax.text(1.7, 3.55, "Tier 2 → RQ3", ha="center", fontsize=7, style="italic", color="#5e3c99")

    for i, (t, s) in enumerate(LEVERS):
        _box(ax, 3.55, 7.6 - i * 1.7, 2.9, 1.4, t, s, "#e66101")

    # Tier 1 track (green tint)
    ax.add_patch(FancyBboxPatch(
        (6.95, 5.5), 4.5, 3.7, boxstyle="round,pad=0.02",
        facecolor="#e8f5e9", alpha=0.5, edgecolor="#4dac26", linewidth=1.5, linestyle="--",
    ))
    ax.text(9.2, 9.0, "TIER 1 — Amestoy baseline", ha="center", fontsize=8,
            fontweight="bold", color="#2e7d32")
    for i, (t, s) in enumerate(TIER1_CHAIN):
        _box(ax, 7.1, 7.8 - i * 0.95, 4.2, 0.82, t, s, "#4dac26", "#f1f8e9")

    # Tier 2 track (amber tint)
    ax.add_patch(FancyBboxPatch(
        (6.95, 1.0), 4.5, 4.2, boxstyle="round,pad=0.02",
        facecolor="#fff8e1", alpha=0.5, edgecolor="#f39c12", linewidth=1.5, linestyle="--",
    ))
    ax.text(9.2, 4.95, "TIER 2 — Sobol sensitivity", ha="center", fontsize=8,
            fontweight="bold", color="#e65100")
    for i, (t, s) in enumerate(TIER2_CHAIN):
        _box(ax, 7.1, 3.9 - i * 1.05, 4.2, 0.88, t, s, "#e65100", "#fffde7")

    for i, (rq, desc, tier, c) in enumerate(METRICS):
        _box(ax, 11.95, 7.5 - i * 2.2, 2.5, 1.7, rq, f"{desc}\n({tier})", c)

    # Flow arrows
    ax.add_patch(FancyArrowPatch((3.2, 7.5), (6.8, 7.8), arrowstyle="-|>", color="#888888", lw=1.2))
    ax.add_patch(FancyArrowPatch((3.2, 5.0), (6.8, 3.2), arrowstyle="-|>", color="#888888", lw=1.2))
    ax.add_patch(FancyArrowPatch((6.5, 5.5), (3.55, 6.0), arrowstyle="-|>", color="#e66101", lw=1.0, ls="--"))
    ax.add_patch(FancyArrowPatch((11.6, 6.5), (11.8, 6.5), arrowstyle="-|>", color="#888888", lw=1.2))
    ax.add_patch(FancyArrowPatch((11.6, 3.5), (11.8, 4.0), arrowstyle="-|>", color="#888888", lw=1.2))

    ax.set_title("Figure C — XLRM framing with Tier 1 / Tier 2 experimental paths",
                 fontsize=12, fontweight="bold", y=0.98)
    ax.text(7.5, 0.15,
            "Tier 1: who bears risk under current rules (Amestoy)  ·  "
            "Tier 2: which levers redistribute risk (Sobol on Kirsch–Nowak forcing)",
            ha="center", fontsize=8, color="#666666")
    return fig


def main():
    fig = make_figure()
    out = FIGS / "fig_C_xlrm_workflow.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
