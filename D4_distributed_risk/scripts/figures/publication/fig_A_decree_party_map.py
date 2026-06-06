"""
Figure A — Decree party map

Basin map with party-colored assets plus a legal-operational overlay
that makes the five decree parties the primary visual unit.

Output
------
figures/publication/fig_A_decree_party_map.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

from _paths import FIGS, PARTY_COLORS, OBLIGATION_WEIGHTS, set_style
from _opening_figures import (
    PARTY_ASSETS,
    PARTY_ORDER_MAP,
    RESERVOIR_LABELS,
    MAP_XLIM,
    MAP_YLIM,
    load_nodes,
    load_state_boundaries,
    node_lookup,
    river_line_segments,
)

set_style()
FIGS.mkdir(parents=True, exist_ok=True)


def _plot_basin_map(ax, nodes):
    """Left panel: DRB geography with party-colored assets (DRBC styling)."""
    # State boundaries (light grey underlay)
    for poly, name in load_state_boundaries():
        ax.plot(poly[:, 0], poly[:, 1], color="#cccccc", lw=0.6, alpha=0.9, zorder=0)
        cx, cy = poly.mean(axis=0)
        if MAP_XLIM[0] < cx < MAP_XLIM[1] and MAP_YLIM[0] < cy < MAP_YLIM[1]:
            if name in ("New York", "Pennsylvania", "New Jersey", "Delaware", "Maryland"):
                ax.text(cx, cy, name, fontsize=7, color="#aaaaaa", ha="center", va="center")

    mainstem, trib = river_line_segments()
    for (c0, c1) in trib:
        ax.plot([c0[0], c1[0]], [c0[1], c1[1]], color="#9fc5e8", lw=1.1, alpha=0.75, zorder=1)
    for (c0, c1) in mainstem:
        ax.plot([c0[0], c1[0]], [c0[1], c1[1]], color="#2b6a9b", lw=2.4, alpha=0.95, zorder=2)

    # Control points (stars) — DRBC flow-target gages
    for party in ("NY", "DE"):
        info = PARTY_ASSETS[party]
        row = node_lookup(nodes, info["control"])
        if row.empty:
            continue
        lon, lat = float(row.iloc[0]["long"]), float(row.iloc[0]["lat"])
        label = "Montague" if party == "NY" else "Trenton"
        cfs = "1,750 cfs" if party == "NY" else "3,000 cfs"
        ax.scatter(
            lon, lat, s=280, marker="*", c="#c0392b", edgecolors="white", linewidths=1.2, zorder=6,
        )
        ax.annotate(
            f"{label}\n{cfs}", (lon, lat), xytext=(10, 8), textcoords="offset points",
            fontsize=7.5, fontweight="bold", color="#922b21",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.85, edgecolor="none"),
        )

    # Reservoirs by party — DRBC color coding
    label_offsets = {
        "cannonsville": (-12, 10), "pepacton": (10, 8), "neversink": (8, -10),
        "beltzvilleCombined": (-14, 0), "blueMarsh": (10, 0), "fewalter": (-12, -8),
    }
    for party, info in PARTY_ASSETS.items():
        if not info["reservoirs"]:
            continue
        rows = node_lookup(nodes, *info["reservoirs"])
        sizes = []
        for _, r in rows.iterrows():
            cap = r.get("capacity", np.nan)
            sizes.append(55 if pd.isna(cap) else np.clip(cap / 600, 45, 140))
        ax.scatter(
            rows["long"], rows["lat"], s=sizes, c=PARTY_COLORS[party],
            alpha=0.92, edgecolors="white", linewidths=1.0, zorder=4,
        )
        for _, r in rows.iterrows():
            key = r["key"]
            disp = RESERVOIR_LABELS.get(key, key)
            ox, oy = label_offsets.get(key, (0, -12))
            ax.annotate(
                disp, (r["long"], r["lat"]),
                xytext=(ox, oy), textcoords="offset points",
                ha="center", fontsize=7, fontweight="bold", color="#333333",
            )

    nj = node_lookup(nodes, "delDRCanal")
    if not nj.empty:
        ax.scatter(
            nj.iloc[0]["long"], nj.iloc[0]["lat"], s=100,
            marker=">", c=PARTY_COLORS["NJ"], edgecolors="white", linewidths=1, zorder=5,
        )
        ax.annotate(
            "NJ diversion\n≤ 100 MGD", (nj.iloc[0]["long"], nj.iloc[0]["lat"]),
            xytext=(12, -14), textcoords="offset points", fontsize=7, color=PARTY_COLORS["NJ"],
            fontweight="bold",
        )

    ax.set_xlim(*MAP_XLIM)
    ax.set_ylim(*MAP_YLIM)
    ax.set_aspect("equal")
    ax.set_title("Delaware River Basin — sources of water by decree party", fontsize=11, pad=8)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.grid(False)


def _plot_party_overlay(ax):
    """Right panel: upstream→downstream party lanes."""
    row_h = 1.55
    n = len(PARTY_ORDER_MAP)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, n * row_h + 0.3)
    ax.axis("off")
    ax.set_title("Legal–operational overlay", fontsize=11, pad=8)

    for i, party in enumerate(PARTY_ORDER_MAP):
        y_top = (n - i) * row_h
        y = y_top - row_h / 2
        info = PARTY_ASSETS[party]
        color = PARTY_COLORS[party]

        ax.add_patch(FancyBboxPatch(
            (0.15, y_top - row_h + 0.08), 9.7, row_h - 0.16,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=color, alpha=0.15, edgecolor=color, linewidth=1.5,
        ))
        ax.text(0.35, y + 0.42, info["title"], fontsize=10, fontweight="bold", va="center")
        ax.text(0.35, y + 0.18, info["subtitle"], fontsize=7.5, va="center", color="#444444")
        w = OBLIGATION_WEIGHTS.get(party, 0)
        ax.text(9.55, y + 0.42, f"{w:.0%} obligation", ha="right", va="center", fontsize=7.5)

        assets = ", ".join(RESERVOIR_LABELS.get(r, r) for r in info["reservoirs"]) if info["reservoirs"] else (
            info["control"].replace("link_del", "").title() if info["control"] else "—"
        )
        lines = [f"Assets / control: {assets}", f"Obligation: {info['obligation']}", f"Lane: {info['lane']}"]
        if info["diversion"]:
            lines.insert(1, f"Diversion: {info['diversion']}")
        for j, line in enumerate(lines):
            ax.text(0.35, y - 0.05 - j * 0.22, line, fontsize=7, va="top")
        ax.text(0.35, y - 0.05 - len(lines) * 0.22, f"Pywr-DRB: {info['pywr']}",
                fontsize=6.5, va="top", color="#666666")

        if i < n - 1:
            ax.add_patch(FancyArrowPatch(
                (5, y_top - row_h + 0.05), (5, y_top - row_h - 0.05),
                arrowstyle="-|>", mutation_scale=10, color="#bbbbbb", lw=1.2,
            ))

    ax.text(5, 0.12, "Upstream (NYC reservoirs)  →  downstream (Trenton / estuary)",
            ha="center", fontsize=8, style="italic", color="#666666")


def make_figure():
    nodes = load_nodes()
    fig = plt.figure(figsize=(15, 8.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.35, 1], wspace=0.08)
    ax_map = fig.add_subplot(gs[0])
    ax_overlay = fig.add_subplot(gs[1])

    _plot_basin_map(ax_map, nodes)
    _plot_party_overlay(ax_overlay)

    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=PARTY_COLORS[p],
               markersize=9, label=f"{p} reservoirs / assets")
        for p in PARTY_ORDER_MAP if p in ("NYC", "PA")
    ]
    handles += [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=PARTY_COLORS[p],
               markersize=9, label=p) for p in ("NY", "NJ", "DE")
    ]
    handles.append(Line2D([0], [0], marker="*", color="w", markerfacecolor="#c0392b",
                          markersize=12, label="Flow target gage"))
    ax_map.legend(handles=handles, loc="lower left", frameon=True, fontsize=7, ncol=2)

    fig.suptitle(
        "Figure A — Five decree parties, control points, and delivery obligations",
        fontsize=12, fontweight="bold", y=0.98,
    )
    return fig


def main():
    fig = make_figure()
    out = FIGS / "fig_A_decree_party_map.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
