"""
Drawing primitives for DRBC-style drought management flowcharts.
"""
from __future__ import annotations

import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

C_NORMAL = "#6CA6D9"
C_WATCH = "#A8D08D"
C_WARNING = "#FFC000"
C_EMERGENCY = "#C00000"

A_NORMAL = "#2E75B6"
A_WATCH = "#548235"
A_WARNING = "#C55A11"
A_EMERGENCY = "#C00000"


def _stage_box(ax, x, y, w, h, title: str, bullets: list[str], facecolor: str):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="square,pad=0",
        facecolor=facecolor, edgecolor="#2F2F2F", linewidth=1.4, zorder=2,
    ))
    tc = "white" if facecolor == C_EMERGENCY else "#1a1a1a"
    ax.text(x + w / 2, y + h - 0.025, title, ha="center", va="top",
            fontsize=8.5, fontweight="bold", color=tc, zorder=3)
    body = "\n".join(f"• {b}" for b in bullets)
    ax.text(x + 0.012, y + h - 0.075, body, ha="left", va="top",
            fontsize=5.7, color=tc, linespacing=1.2, zorder=3)


def _decision(ax, x, y, w, h, text: str):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
        facecolor="white", edgecolor="#666666", linewidth=1.0, zorder=2,
    ))
    ax.text(x + w / 2, y + h / 2, textwrap.fill(text, width=int(w * 95)),
            ha="center", va="center", fontsize=6.2, color="#222", zorder=3)


def _arr(ax, p0, p1, color, rad=0.0, lw=1.6):
    kw = dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=11, zorder=1)
    style = f"arc3,rad={rad}" if rad else "arc3"
    ax.add_patch(FancyArrowPatch(p0, p1, connectionstyle=style, **kw))


def _yes(ax, xy, color):
    ax.text(xy[0], xy[1], "YES", fontsize=6, fontweight="bold", color=color, zorder=5)


def draw_basin_wide(ax):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.50, 0.97, "Basin-Wide Drought Flow Management",
            ha="center", fontsize=10.5, fontweight="bold")
    ax.text(0.50, 0.935, "(Water Code Section 2.5.3.E and FFMP)",
            ha="center", fontsize=7.5, color="#444")

    sx, sw = 0.03, 0.21
    ys = [0.72, 0.52, 0.32, 0.10]
    hs = [0.17, 0.17, 0.17, 0.18]
    stages = [
        ("Normal", C_NORMAL, [
            "Table 1 — Normal Diversions and Targets",
            "FFMP Table 4 — L1 or L2 Releases",
        ]),
        ("Drought Watch", C_WATCH, [
            "Table 1 — L3 Diversions and Targets",
            "FFMP Table 3 — L3 Releases",
            "Monthly DP Meetings",
        ]),
        ("Drought Warning", C_WARNING, [
            "Table 1 — L4 Diversions and Targets",
            "FFMP Table 3 — L4 Releases",
            "Monthly DP Meetings",
        ]),
        ("Drought Emergency", C_EMERGENCY, [
            "Table 1 — L5 Diversions and Table 2 Targets (related to SF Location)",
            "FFMP Table 3 — L5 Releases",
            "Monthly DP Meetings",
        ]),
    ]
    cy = []
    for (title, color, bullets), y, h in zip(stages, ys, hs):
        _stage_box(ax, sx, y, sw, h, title, bullets, color)
        cy.append(y + h / 2)

    ax.text(sx + sw / 2, ys[0] + hs[0] + 0.02, "START", ha="center",
            fontsize=7, fontweight="bold", color="#333")

    # Down-arrows between stages (grey spine)
    for i in range(3):
        _arr(ax, (sx + sw / 2, ys[i]), (sx + sw / 2, ys[i + 1] + hs[i + 1]), "#999", lw=1.2)

    # Entry decisions (centre)
    dx, dw, dh = 0.28, 0.27, 0.085
    qs = [
        (cy[0], "Has NYC Storage < Drought Watch Line (L3) for 5 days?", A_NORMAL, 1),
        (cy[1], "Is NYC Storage < Drought Warning Line (L4)?", A_WATCH, 2),
        (cy[2], "Is NYC Storage < Drought Emergency (L5) for 5 days?", A_WARNING, 3),
    ]
    for yc, q, col, tgt in qs:
        _decision(ax, dx, yc - dh / 2, dw, dh, q)
        _arr(ax, (sx + sw, yc), (dx, yc), col)
        _arr(ax, (dx + dw / 2, yc - dh / 2), (sx + sw / 2, ys[tgt] + hs[tgt]), col, rad=0.0)
        _yes(ax, (dx + dw / 2 + 0.01, yc - dh / 2 - 0.015), col)

    # Recovery column (right)
    rx, rw = 0.60, 0.36
    _decision(ax, rx, 0.62, rw, 0.16,
              "Has NYC Storage + Snowpack* been > L3 + 15 BG for more than 5 consecutive days?")
    _decision(ax, rx, 0.42, rw, 0.12,
              "Table 1, Normal Diversions and Targets; FFMP Table 3 L3, L4 or L5 Releases**; FFMP Criterion")
    _decision(ax, rx, 0.22, rw, 0.14,
              "Has NYC Storage + Snowpack* been > L3 + 25 BG for more than 15 consecutive days? FFMP Criterion")

    _arr(ax, (sx + sw, cy[2]), (rx, 0.72), A_WARNING, rad=0.12)
    _arr(ax, (sx + sw, cy[3]), (rx, 0.68), A_EMERGENCY, rad=0.08)
    _arr(ax, (rx + rw / 2, 0.62), (rx + rw / 2, 0.54), A_WARNING)
    _yes(ax, (rx - 0.02, 0.66), A_WARNING)
    _arr(ax, (rx + rw / 2, 0.42), (rx + rw / 2, 0.36), A_WARNING)
    _arr(ax, (rx, 0.29), (sx + sw / 2, ys[0] + hs[0]), A_NORMAL, rad=-0.18)
    _yes(ax, (rx - 0.02, 0.32), A_NORMAL)


def draw_lower_basin(ax):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.50, 0.97, "Lower-Basin Drought Flow Management",
            ha="center", fontsize=10.5, fontweight="bold")
    ax.text(0.50, 0.935, "(Water Code Section 2.5.6)",
            ha="center", fontsize=7.5, color="#444")

    sx, sw = 0.03, 0.23
    ys = [0.62, 0.32, 0.06]
    hs = [0.14, 0.26, 0.26]
    stages = [
        ("Normal", C_NORMAL, [
            "Normal Diversions, Flow Targets, and Conservation Releases",
        ]),
        ("Drought Warning", C_WARNING, [
            "NJ D&R Canal diversion rate: 70 mgd",
            "Trenton target: Table 2 (salt-front Vernier)",
            "Reservoir releases priority: Sect. 2.5.6.C.3",
            "Conservation releases: Table 4 (Sect. 2.5.5)",
            "Water conservation measures: voluntary",
        ]),
        ("Drought", C_EMERGENCY, [
            "NJ D&R Canal diversion rate: 65 mgd",
            "Trenton target: Table 2 (salt-front Vernier)",
            "Reservoir releases priority: Sect. 2.5.6.D.3",
            "Conservation releases: Table 4 (Sect. 2.5.5)",
            "Water conservation measures: mandatory",
        ]),
    ]
    cy = []
    for (title, color, bullets), y, h in zip(stages, ys, hs):
        _stage_box(ax, sx, y, sw, h, title, bullets, color)
        cy.append(y + h / 2)

    ax.text(sx + sw / 2, ys[0] + hs[0] + 0.02, "START", ha="center",
            fontsize=7, fontweight="bold", color="#333")

    _arr(ax, (sx + sw / 2, ys[0]), (sx + sw / 2, ys[1] + hs[1]), "#999", lw=1.2)
    _arr(ax, (sx + sw / 2, ys[1]), (sx + sw / 2, ys[2] + hs[2]), "#999", lw=1.2)

    dx, dw = 0.30, 0.30
    _decision(ax, dx, 0.68, dw, 0.12,
              "Are both lake elevations BELOW the thresholds below? "
              "(1) Beltzville elev < 615′  (2) Blue Marsh elev < 283′")
    _decision(ax, dx, 0.40, dw, 0.14,
              "Have both lake elevations been BELOW the thresholds for three days? "
              "(1) Beltzville elev < 590′  (2) Blue Marsh elev < 273′")

    _arr(ax, (sx + sw, cy[0]), (dx, 0.74), A_NORMAL)
    _arr(ax, (dx + dw / 2, 0.68), (sx + sw / 2, ys[1] + hs[1]), A_WARNING)
    _yes(ax, (dx + dw / 2 + 0.01, 0.67), A_WARNING)

    _arr(ax, (sx + sw, cy[1]), (dx, 0.48), A_WARNING)
    _arr(ax, (dx + dw / 2, 0.40), (sx + sw / 2, ys[2] + hs[2]), A_EMERGENCY)
    _yes(ax, (dx + dw / 2 + 0.01, 0.39), A_EMERGENCY)

    rx, rw = 0.64, 0.33
    _decision(ax, rx, 0.52, rw, 0.16,
              "Have both lake elevations been ABOVE the thresholds below for 30 consecutive days? "
              "(1) Beltzville elev > 590′  (2) Blue Marsh elev > 273′. "
              "Or has one of the two reservoirs spilled?")
    _decision(ax, rx, 0.26, rw, 0.16,
              "Have both lake elevations been ABOVE the thresholds below for 30 consecutive days? "
              "(1) Beltzville elev > 615′  (2) Blue Marsh elev > 283′. "
              "Or has one of the two reservoirs spilled?")

    _arr(ax, (sx + sw, cy[2]), (rx, 0.60), A_EMERGENCY, rad=0.1)
    _arr(ax, (rx + rw / 2, 0.52), (sx + sw / 2, ys[1] + hs[1]), A_WARNING, rad=-0.12)
    _yes(ax, (rx - 0.02, 0.55), A_WARNING)

    _arr(ax, (sx + sw, cy[1]), (rx, 0.34), A_WARNING, rad=0.08)
    _arr(ax, (rx + rw / 2, 0.26), (sx + sw / 2, ys[0] + hs[0]), A_NORMAL, rad=-0.15)
    _yes(ax, (rx - 0.02, 0.29), A_NORMAL)
