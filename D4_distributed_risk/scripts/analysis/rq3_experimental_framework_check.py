"""
D4 — Comprehensive experimental framework diagnostic.

Answers six empirical questions about whether the current Sobol design
can actually support RQ2 and RQ3 as framed:

  A. Partial dependence — does each active parameter affect parties
     in the same or opposite directions?
  B. Cross-party scatter (ΔPA vs ΔNYC) — is there redistribution signal?
  C. S2 interaction heatmap — which parameter pairs drive interactions,
     and for which parties?
  D. Regime-stratified partial dependence — do parameter effects flip
     sign across NYC-limited vs LB-limited regimes?
  E. Tradeoff occupancy — how much of parameter space is win-win vs
     redistribution vs lose-lose?
  F. Placeholder confirmation — verify m_lb / q_nj_warning / ierq_max_bg
     are flat (no-ops).

All outputs saved to:
    D4_distributed_risk/results/rq3/framework_check/

Usage
-----
    cd ~/dissertation
    module load python/3.11.5 && source venv/bin/activate
    python D4_distributed_risk/scripts/analysis/rq3_experimental_framework_check.py
"""

from __future__ import annotations
import sys, pathlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import TwoSlopeNorm
import warnings
warnings.filterwarnings("ignore")

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "shared"))
sys.path.insert(0, str(REPO))

SOBOL_DIR  = REPO / "D4_distributed_risk" / "results" / "sobol"
OUTDIR     = REPO / "D4_distributed_risk" / "results" / "rq3" / "framework_check"
FIGDIR     = REPO / "D4_distributed_risk" / "figures" / "framework_check"
OUTDIR.mkdir(parents=True, exist_ok=True)
FIGDIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Parameters and metrics of interest
# ---------------------------------------------------------------------------
ACTIVE_PARAMS = ["alpha_betz_warning", "alpha_bm_warning", "tau_recovery"]
PLACEHOLDER_PARAMS = ["m_lb", "q_nj_warning", "ierq_max_bg"]
ALL_PARAMS = ACTIVE_PARAMS + PLACEHOLDER_PARAMS

PARAM_LABELS = {
    "alpha_betz_warning": "α_BW\n(Beltzville warning)",
    "alpha_bm_warning":   "α_BMW\n(Blue Marsh warning)",
    "tau_recovery":       "τ_R\n(Recovery days)",
    "m_lb":               "m_LB\n(LB cap mult.)",
    "q_nj_warning":       "Q_NJ_W\n(NJ cap MGD)",
    "ierq_max_bg":        "I_max\n(IERQ ceiling)",
}

PARTY_METRICS = {
    "DE":  "de_reliability",
    "NYC": "nyc_ierq_exhaustion_reliability",
    "PA":  "pa_depletion_reliability",
    "NJ":  "nj_delivery_reliability",
    "NY":  "ny_reliability",
}

PARTY_COLORS = {
    "DE":  "#1f77b4",
    "NYC": "#ff7f0e",
    "PA":  "#2ca02c",
    "NJ":  "#d62728",
    "NY":  "#9467bd",
}

N_BINS = 10   # bins for partial dependence

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("Loading Sobol mean metrics ...")
df = pd.read_parquet(SOBOL_DIR / "sobol_mean_metrics.parquet")
print(f"  {len(df):,} samples × {len(df.columns)} columns")

print("Loading Sobol indices ...")
idx_df = pd.read_parquet(SOBOL_DIR / "sobol_indices.parquet")

print("Loading S2 interactions ...")
s2_df  = pd.read_parquet(SOBOL_DIR / "sobol_S2.parquet")

# Reference point: median of Sobol ensemble
# (approximates "current rules" since baseline is near center of param space)
ref = {col: df[col].median() for col in PARTY_METRICS.values()}
print(f"\nReference (median) reliability values:")
for party, col in PARTY_METRICS.items():
    print(f"  {party}: {ref[col]:.4f}")

# Delta from reference for each sample
for party, col in PARTY_METRICS.items():
    df[f"delta_{party}"] = df[col] - ref[col]

# ---------------------------------------------------------------------------
# A. Partial dependence plots
# ---------------------------------------------------------------------------
print("\n[A] Partial dependence ...")

fig, axes = plt.subplots(2, 3, figsize=(15, 9))
fig.suptitle(
    "A. Partial Dependence — Mean Party Reliability vs Parameter Value\n"
    "Each curve averaged over all other parameters (marginal effect)",
    fontsize=11,
)

for ax, param in zip(axes.flat, ALL_PARAMS):
    bins = pd.qcut(df[param], q=N_BINS, duplicates="drop")
    bin_centers = df.groupby(bins, observed=True)[param].mean()

    for party, col in PARTY_METRICS.items():
        means = df.groupby(bins, observed=True)[col].mean()
        ax.plot(bin_centers, means, color=PARTY_COLORS[party],
                lw=2, marker="o", ms=4, label=party)

    ax.set_xlabel(PARAM_LABELS[param], fontsize=9)
    ax.set_ylabel("Mean reliability", fontsize=9)
    ax.set_title(
        PARAM_LABELS[param].replace("\n", " "),
        fontsize=9, pad=2,
        color="gray" if param in PLACEHOLDER_PARAMS else "black",
    )
    if param in PLACEHOLDER_PARAMS:
        ax.set_facecolor("#f8f8f8")
        ax.text(0.5, 0.5, "PLACEHOLDER\n(no injection)",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=9, color="gray", alpha=0.7)
    ax.legend(fontsize=7, loc="best", framealpha=0.8)
    ax.grid(alpha=0.25)
    ax.tick_params(labelsize=8)

plt.tight_layout()
fig.savefig(FIGDIR / "A_partial_dependence.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved A_partial_dependence.png")

# Also save table
pd_rows = []
for param in ACTIVE_PARAMS:
    bins = pd.qcut(df[param], q=N_BINS, duplicates="drop")
    for party, col in PARTY_METRICS.items():
        means = df.groupby(bins, observed=True)[col].mean()
        slope = np.polyfit(range(len(means)), means.values, 1)[0]
        pd_rows.append({"param": param, "party": party,
                        "slope_per_decile": round(slope, 6),
                        "range": round(means.max() - means.min(), 6)})
pd.DataFrame(pd_rows).to_csv(OUTDIR / "A_partial_dependence_slopes.csv", index=False)

# ---------------------------------------------------------------------------
# B. Cross-party scatter: ΔPA vs ΔNYC, colored by alpha_betz
# ---------------------------------------------------------------------------
print("[B] Cross-party scatter ...")

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle(
    "B. Cross-Party Scatter — ΔPA Reliability vs ΔNYC Reliability\n"
    "Redistribution = quadrants II and IV  |  Win-win = quadrant I  |  Lose-lose = quadrant III",
    fontsize=10,
)

scatter_params = ["alpha_betz_warning", "alpha_bm_warning", "tau_recovery"]
for ax, param in zip(axes, scatter_params):
    sc = ax.scatter(
        df["delta_NYC"], df["delta_PA"],
        c=df[param], cmap="RdYlBu", alpha=0.3, s=4,
        vmin=df[param].quantile(0.05), vmax=df[param].quantile(0.95),
    )
    plt.colorbar(sc, ax=ax, label=PARAM_LABELS[param].replace("\n", " "), pad=0.01)
    ax.axhline(0, color="black", lw=0.8, alpha=0.6)
    ax.axvline(0, color="black", lw=0.8, alpha=0.6)

    # Quadrant fractions
    ww = ((df["delta_NYC"] > 0) & (df["delta_PA"] > 0)).mean()
    ll = ((df["delta_NYC"] < 0) & (df["delta_PA"] < 0)).mean()
    rd = 1 - ww - ll
    ax.text(0.02, 0.97,
            f"Win-win: {ww*100:.0f}%\nRedistrib: {rd*100:.0f}%\nLose-lose: {ll*100:.0f}%",
            transform=ax.transAxes, fontsize=8, va="top",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.85))

    ax.set_xlabel("ΔNYC IERQ reliability", fontsize=9)
    ax.set_ylabel("ΔPA depletion reliability", fontsize=9)
    ax.set_title(f"Colored by {PARAM_LABELS[param].split(chr(10))[0]}", fontsize=9)
    ax.grid(alpha=0.2)
    ax.tick_params(labelsize=8)

plt.tight_layout()
fig.savefig(FIGDIR / "B_cross_party_scatter.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved B_cross_party_scatter.png")

# Tradeoff summary table
for party_a, party_b in [("NYC", "PA"), ("NYC", "NJ"), ("DE", "PA")]:
    ww = ((df[f"delta_{party_a}"] > 0) & (df[f"delta_{party_b}"] > 0)).mean()
    ll = ((df[f"delta_{party_a}"] < 0) & (df[f"delta_{party_b}"] < 0)).mean()
    print(f"  {party_a} vs {party_b}: win-win={ww*100:.1f}%  lose-lose={ll*100:.1f}%  redistrib={100*(1-ww-ll):.1f}%")

# ---------------------------------------------------------------------------
# C. S2 interaction heatmap
# ---------------------------------------------------------------------------
print("[C] S2 interaction heatmap ...")

focus_metrics = ["de_reliability", "nyc_ierq_exhaustion_reliability",
                 "pa_depletion_reliability", "nj_delivery_reliability", "ny_reliability"]

fig, axes = plt.subplots(1, len(focus_metrics), figsize=(18, 4))
fig.suptitle("C. Second-Order Sobol Indices (S2) — Parameter Interaction Strength per Party",
             fontsize=10)

params_ordered = ALL_PARAMS
n = len(params_ordered)

for ax, metric in zip(axes, focus_metrics):
    mat = np.zeros((n, n))
    sub = s2_df[s2_df["metric"] == metric]
    for _, row in sub.iterrows():
        i = params_ordered.index(row["param_i"]) if row["param_i"] in params_ordered else -1
        j = params_ordered.index(row["param_j"]) if row["param_j"] in params_ordered else -1
        if i >= 0 and j >= 0:
            mat[i, j] = row["S2"]
            mat[j, i] = row["S2"]

    vmax = max(abs(mat).max(), 0.01)
    im = ax.imshow(mat, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    plt.colorbar(im, ax=ax, shrink=0.8)

    short_labels = [PARAM_LABELS[p].split("\n")[0] for p in params_ordered]
    ax.set_xticks(range(n)); ax.set_xticklabels(short_labels, rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(n)); ax.set_yticklabels(short_labels, fontsize=7)

    party = [k for k, v in PARTY_METRICS.items() if v == metric]
    ax.set_title(party[0] if party else metric, fontsize=9)

    # Shade placeholder rows/cols
    for k, p in enumerate(params_ordered):
        if p in PLACEHOLDER_PARAMS:
            ax.axhline(k - 0.5, color="gray", lw=0.5, alpha=0.5)
            ax.axvline(k - 0.5, color="gray", lw=0.5, alpha=0.5)

plt.tight_layout()
fig.savefig(FIGDIR / "C_s2_interaction_heatmap.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved C_s2_interaction_heatmap.png")

# Top interactions table
top_s2 = (s2_df[s2_df["metric"].isin(focus_metrics)]
          .sort_values("S2", ascending=False)
          .head(20)[["metric","param_i","param_j","S2","S2_conf"]]
          .round(4))
top_s2.to_csv(OUTDIR / "C_top_s2_interactions.csv", index=False)
print(f"  Top S2 interactions:\n{top_s2.head(10).to_string(index=False)}")

# ---------------------------------------------------------------------------
# D. Regime-stratified partial dependence
# ---------------------------------------------------------------------------
print("[D] Regime-stratified partial dependence ...")

# Define regime proxy from Sobol data:
# NYC-dominated: NYC reliability < PA reliability (NYC is the binding constraint)
# LB-dominated:  PA reliability < NYC reliability
df["regime_proxy"] = np.where(
    df["nyc_ierq_exhaustion_reliability"] < df["pa_depletion_reliability"],
    "NYC-limited", "LB-limited"
)
regime_counts = df["regime_proxy"].value_counts()
print(f"  Regime split: {regime_counts.to_dict()}")

fig, axes = plt.subplots(2, 3, figsize=(15, 9))
fig.suptitle(
    "D. Regime-Stratified Partial Dependence\n"
    "Solid = NYC-limited regime  |  Dashed = LB-limited regime\n"
    "(regime defined by which party has lower reliability in each Sobol sample)",
    fontsize=10,
)

regime_styles = {"NYC-limited": "-", "LB-limited": "--"}
regime_alphas = {"NYC-limited": 0.9,  "LB-limited": 0.6}

for ax, param in zip(axes.flat, ALL_PARAMS):
    for regime, ls in regime_styles.items():
        sub = df[df["regime_proxy"] == regime]
        if len(sub) < 50:
            continue
        bins = pd.qcut(sub[param], q=N_BINS, duplicates="drop")
        bin_centers = sub.groupby(bins, observed=True)[param].mean()
        for party, col in PARTY_METRICS.items():
            means = sub.groupby(bins, observed=True)[col].mean()
            ax.plot(bin_centers, means,
                    color=PARTY_COLORS[party], lw=1.8, ls=ls,
                    alpha=regime_alphas[regime],
                    label=f"{party} ({regime})" if param == ALL_PARAMS[0] else "")

    ax.set_xlabel(PARAM_LABELS[param], fontsize=9)
    ax.set_ylabel("Mean reliability", fontsize=9)
    ax.set_title(PARAM_LABELS[param].replace("\n", " "), fontsize=9, pad=2,
                 color="gray" if param in PLACEHOLDER_PARAMS else "black")
    if param in PLACEHOLDER_PARAMS:
        ax.set_facecolor("#f8f8f8")
    ax.grid(alpha=0.2)
    ax.tick_params(labelsize=8)

# Single legend
handles, labels = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=5, fontsize=7,
           bbox_to_anchor=(0.5, -0.02), framealpha=0.9)
plt.tight_layout(rect=[0, 0.05, 1, 1])
fig.savefig(FIGDIR / "D_regime_stratified_pd.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved D_regime_stratified_pd.png")

# Check sign flips
sign_flip_rows = []
for param in ACTIVE_PARAMS:
    for party, col in PARTY_METRICS.items():
        slopes = {}
        for regime in ["NYC-limited", "LB-limited"]:
            sub = df[df["regime_proxy"] == regime]
            if len(sub) < 50:
                continue
            bins = pd.qcut(sub[param], q=N_BINS, duplicates="drop")
            means = sub.groupby(bins, observed=True)[col].mean()
            slopes[regime] = np.polyfit(range(len(means)), means.values, 1)[0]
        if len(slopes) == 2:
            flip = (slopes["NYC-limited"] * slopes["LB-limited"]) < 0
            sign_flip_rows.append({
                "param": param, "party": party,
                "slope_nyc_limited": round(slopes.get("NYC-limited", np.nan), 6),
                "slope_lb_limited":  round(slopes.get("LB-limited", np.nan), 6),
                "sign_flip": flip,
            })

sf_df = pd.DataFrame(sign_flip_rows)
sf_df.to_csv(OUTDIR / "D_sign_flips.csv", index=False)
print("  Sign flips across regimes:")
print(sf_df[sf_df["sign_flip"]].to_string(index=False))

# ---------------------------------------------------------------------------
# E. Tradeoff occupancy — all 5 parties simultaneously
# ---------------------------------------------------------------------------
print("[E] Tradeoff occupancy ...")

# Classify each sample
def classify_tradeoff(row):
    deltas = [row[f"delta_{p}"] for p in PARTY_METRICS.keys()]
    n_pos = sum(d > 0 for d in deltas)
    n_neg = sum(d < 0 for d in deltas)
    if n_neg == 0:
        return "win-win"
    elif n_pos == 0:
        return "lose-lose"
    else:
        return "redistribution"

df["tradeoff_class"] = df.apply(classify_tradeoff, axis=1)
tradeoff_counts = df["tradeoff_class"].value_counts(normalize=True) * 100
print(f"  Tradeoff occupancy:\n{tradeoff_counts.round(1)}")
tradeoff_counts.to_csv(OUTDIR / "E_tradeoff_occupancy.csv", header=["pct"])

# Plot: tradeoff class by parameter bin
fig, axes = plt.subplots(1, 3, figsize=(15, 5))
fig.suptitle(
    "E. Tradeoff Occupancy by Parameter Value\n"
    "Fraction of Sobol samples classified win-win / redistribution / lose-lose\n"
    "(5-party simultaneous: all parties improve = win-win)",
    fontsize=10,
)
tc_colors = {"win-win": "#2ca02c", "redistribution": "#ff7f0e", "lose-lose": "#d62728"}

for ax, param in zip(axes, ACTIVE_PARAMS):
    bins = pd.qcut(df[param], q=N_BINS, duplicates="drop")
    bin_centers = df.groupby(bins, observed=True)[param].mean()
    fracs = (df.groupby(bins, observed=True)["tradeoff_class"]
             .value_counts(normalize=True)
             .unstack(fill_value=0))

    bottom = np.zeros(len(bin_centers))
    for tc in ["win-win", "redistribution", "lose-lose"]:
        if tc in fracs.columns:
            vals = fracs[tc].values
            ax.bar(range(len(bin_centers)), vals, bottom=bottom,
                   color=tc_colors[tc], label=tc, alpha=0.85, width=0.8)
            bottom += vals

    ax.set_xticks(range(len(bin_centers)))
    ax.set_xticklabels([f"{v:.3f}" for v in bin_centers.values],
                       rotation=45, ha="right", fontsize=7)
    ax.set_xlabel(PARAM_LABELS[param].replace("\n", " "), fontsize=9)
    ax.set_ylabel("Fraction of samples", fontsize=9)
    ax.set_title(PARAM_LABELS[param].replace("\n", " "), fontsize=9)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(labelsize=8)

plt.tight_layout()
fig.savefig(FIGDIR / "E_tradeoff_occupancy.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved E_tradeoff_occupancy.png")

# ---------------------------------------------------------------------------
# F. Placeholder confirmation
# ---------------------------------------------------------------------------
print("[F] Placeholder confirmation ...")

fig, axes = plt.subplots(1, 3, figsize=(14, 4))
fig.suptitle(
    "F. Placeholder Parameter Flat Response Confirmation\n"
    "m_lb / q_nj_warning / ierq_max_bg — no injection in sweep 1, expect flat lines",
    fontsize=10,
)

for ax, param in zip(axes, PLACEHOLDER_PARAMS):
    bins = pd.qcut(df[param], q=N_BINS, duplicates="drop")
    bin_centers = df.groupby(bins, observed=True)[param].mean()
    for party, col in PARTY_METRICS.items():
        means = df.groupby(bins, observed=True)[col].mean()
        rng = means.max() - means.min()
        ax.plot(bin_centers, means, color=PARTY_COLORS[party],
                lw=1.5, marker="o", ms=3,
                label=f"{party} (range={rng:.5f})")
    ax.set_xlabel(PARAM_LABELS[param].replace("\n", " "), fontsize=9)
    ax.set_ylabel("Mean reliability", fontsize=9)
    ax.set_title(f"{param}\n(PLACEHOLDER — expected flat)", fontsize=9, color="gray")
    ax.set_facecolor("#f8f8f8")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.25)
    ax.tick_params(labelsize=8)

plt.tight_layout()
fig.savefig(FIGDIR / "F_placeholder_confirmation.png", dpi=150, bbox_inches="tight")
plt.close(fig)
print("  Saved F_placeholder_confirmation.png")

# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
print("\n=== FRAMEWORK CHECK SUMMARY ===")

print("\n[A] Active parameter effects (slope direction per party):")
slopes_df = pd.read_csv(OUTDIR / "A_partial_dependence_slopes.csv")
pivot = slopes_df.pivot(index="param", columns="party", values="slope_per_decile").round(6)
print(pivot.to_string())

print("\n[B] Cross-party tradeoff fractions (NYC vs PA):")
for party_a, party_b in [("NYC", "PA"), ("NYC", "NJ"), ("DE", "PA")]:
    ww = ((df[f"delta_{party_a}"] > 0) & (df[f"delta_{party_b}"] > 0)).mean()
    ll = ((df[f"delta_{party_a}"] < 0) & (df[f"delta_{party_b}"] < 0)).mean()
    rd = 1 - ww - ll
    print(f"  {party_a} vs {party_b}: win-win={ww*100:.1f}%  redistrib={rd*100:.1f}%  lose-lose={ll*100:.1f}%")

print("\n[D] Sign flips across regimes (parameters that flip direction):")
sf = pd.read_csv(OUTDIR / "D_sign_flips.csv")
flipped = sf[sf["sign_flip"]]
if len(flipped):
    print(flipped[["param","party","slope_nyc_limited","slope_lb_limited"]].to_string(index=False))
else:
    print("  No sign flips detected.")

print("\n[E] Overall tradeoff occupancy:")
print(tradeoff_counts.round(1).to_string())

print(f"\nAll figures: {FIGDIR}")
print(f"All tables:  {OUTDIR}")
print("Done.")
