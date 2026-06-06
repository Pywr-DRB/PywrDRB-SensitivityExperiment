"""
Shared helpers for D4 opening figure set (A–D).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from _paths import D4, PARTY_COLORS, OBLIGATION_WEIGHTS

DRB_SPATIAL = D4 / "scripts" / "figures" / "DRB_spatial" / "DRB_spatial"
SHP_DIR = DRB_SPATIAL / "DRB_shapefiles"
NODES_CSV = DRB_SPATIAL / "model_components" / "drb_model_major_nodes.csv"
EDGES_CSV = DRB_SPATIAL / "model_components" / "drb_model_edges.csv"
ALL_NODES_CSV = DRB_SPATIAL / "model_components" / "drb_nodes.csv"

# Party-first asset registry (visual unit = decree party, not reservoir)
PARTY_ASSETS: dict[str, dict] = {
    "NYC": {
        "title": "New York City",
        "subtitle": "Art. VII diversions · IERQ/ERQ banking",
        "reservoirs": ["cannonsville", "pepacton", "neversink"],
        "control": None,
        "diversion": "≤ 800 MGD to NYC supply",
        "obligation": "Releases for Montague/Trenton; IERQ 6.09 BG/yr",
        "pywr": "IERQRelease_step1 · ERQRelease · NYC drought level",
        "lane": "Releases + banking",
    },
    "NY": {
        "title": "New York State",
        "subtitle": "Art. III Montague flow objective",
        "reservoirs": [],
        "control": "link_delMontague",
        "diversion": None,
        "obligation": "1,131 MGD (1,750 cfs) non-drought target",
        "pywr": "mrf_target_delMontague",
        "lane": "Flow target",
    },
    "PA": {
        "title": "Pennsylvania",
        "subtitle": "Art. IV · LB USACE storage",
        "reservoirs": ["beltzvilleCombined", "blueMarsh", "fewalter"],
        "control": None,
        "diversion": None,
        "obligation": "LB conservation pool 15,082 MG combined",
        "pywr": "drought_level_agg_lb · res_storage",
        "lane": "LB storage triggers",
    },
    "NJ": {
        "title": "New Jersey",
        "subtitle": "Art. IV · Delaware & Raritan Canal",
        "reservoirs": [],
        "control": "link_delDRCanal",
        "diversion": "≤ 100 MGD (70/65 under LB drought)",
        "obligation": "Delivery cap tied to LB drought stage",
        "pywr": "delivery_nj · combined_drought_factor_delivery_nj",
        "lane": "Diversions",
    },
    "DE": {
        "title": "Delaware",
        "subtitle": "Art. III Trenton flow · salt front",
        "reservoirs": [],
        "control": "link_delTrenton",
        "diversion": None,
        "obligation": "1,939 MGD (3,000 cfs) non-drought target",
        "pywr": "mrf_target_delTrenton",
        "lane": "Flow target + shortage",
    },
}

PARTY_ORDER_MAP = ["NYC", "NY", "PA", "NJ", "DE"]  # upstream → downstream on overlay

# DRBC “Sources of Water” display names
RESERVOIR_LABELS: dict[str, str] = {
    "cannonsville": "Cannonsville",
    "pepacton": "Pepacton",
    "neversink": "Neversink",
    "beltzvilleCombined": "Beltzville",
    "blueMarsh": "Blue Marsh",
    "fewalter": "F.E. Walter",
    "wallenpaupack": "Wallenpaupack",
    "mongaupeCombined": "Mongaup",
    "prompton": "Prompton",
    "merrillCreek": "Merrill Creek",
    "nockamixon": "Nockamixon",
}

# DRBC map extent (lon/lat)
MAP_XLIM = (-76.55, -73.85)
MAP_YLIM = (39.45, 42.35)
DRB_STATEFPS = {"34", "10", "24", "42", "36"}  # NJ, DE, MD, PA, NY

# FFMP phased reductions (DRBC drought management plan)
PHASED_REDUCTIONS = {
    "stage": ["Normal", "Watch (L3)", "Warning (L4)", "Emergency (L5)"],
    "nyc_mgd": [800, 680, 560, 520],
    "nj_mgd": [100, 100, 90, 80],
    "montague_cfs": [1750, 1650, 1550, 1650],
    "trenton_cfs": [3000, 2700, 2700, 2900],
}

AMESTOY_HDF5_CANDIDATES = (
    Path.home() / "data/amestoy_2026/pywrdrb_inputs/historic_ensembles"
    / "catchment_inflow_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5",
    D4.parent / "data/amestoy_2026/pywrdrb_inputs/historic_ensembles"
    / "catchment_inflow_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5",
)


def load_nodes() -> pd.DataFrame:
    df = pd.read_csv(NODES_CSV)
    df["key"] = df["name"].str.replace("^reservoir_", "", regex=True)
    df["key"] = df["key"].str.replace("^link_", "", regex=True)
    return df


def load_model_edges() -> pd.DataFrame:
    return pd.read_csv(EDGES_CSV)


def load_all_node_coords() -> dict[str, tuple[float, float]]:
    """lon, lat keyed by short node name (strip reservoir_/link_ prefixes)."""
    df = pd.read_csv(ALL_NODES_CSV)
    out: dict[str, tuple[float, float]] = {}
    for _, row in df.iterrows():
        name = str(row["name"])
        lon, lat = float(row["long"]), float(row["lat"])
        out[name] = (lon, lat)
        for prefix in ("reservoir_", "link_", "outflow_", "catchment_"):
            out[f"{prefix}{name}"] = (lon, lat)
    return out


def river_line_segments() -> tuple[list[tuple], list[tuple]]:
    """
    Return (mainstem_segments, tributary_segments) as lists of ((lon0,lat0),(lon1,lat1)).
    Uses Pywr-DRB model topology in geographic coordinates.
    """
    edges = load_model_edges()
    coords = load_all_node_coords()
    mainstem: list[tuple] = []
    trib: list[tuple] = []
    for _, e in edges.iterrows():
        n1, n2, etype = str(e["node1"]), str(e["node2"]), str(e["type"])
        if etype not in ("mainstem", "tributary"):
            continue
        c1 = coords.get(n1) or coords.get(n1.replace("reservoir_", "").replace("link_", ""))
        c2 = coords.get(n2) or coords.get(n2.replace("reservoir_", "").replace("link_", ""))
        if c1 is None or c2 is None:
            continue
        seg = (c1, c2)
        (mainstem if etype == "mainstem" else trib).append(seg)
    return mainstem, trib


def node_lookup(nodes: pd.DataFrame, *keys: str) -> pd.DataFrame:
    mask = nodes["key"].isin(keys) | nodes["name"].isin(keys)
    return nodes.loc[mask].copy()


def synthetic_flows_dir() -> Path:
    for sub in ("sobol_sweep3", "sobol"):
        p = D4 / "results" / sub / "synthetic_flows"
        if p.exists() and any(p.glob("realization_*.parquet")):
            return p
    raise FileNotFoundError("No synthetic_flows directory with realization_*.parquet")


def load_ensemble_inflow(
    flows_dir: Path | None = None,
    inflow_cols: tuple[str, ...] = ("delLordville",),
    max_realizations: int | None = None,
) -> tuple[pd.DatetimeIndex, np.ndarray, pd.DataFrame]:
    """
    Load daily inflow traces for all realizations.

    Returns
    -------
    dates : DatetimeIndex
    cube  : (n_realizations, n_days) basin inflow [MGD]
    log   : generation_log DataFrame
    """
    flows_dir = flows_dir or synthetic_flows_dir()
    log_path = flows_dir / "generation_log.csv"
    log = pd.read_csv(log_path) if log_path.exists() else pd.DataFrame()

    files = sorted(flows_dir.glob("realization_*.parquet"))
    if max_realizations:
        files = files[:max_realizations]

    traces: list[np.ndarray] = []
    dates: pd.DatetimeIndex | None = None
    for f in files:
        df = pd.read_parquet(f)
        if dates is None:
            dates = pd.DatetimeIndex(df.index)
        cols = [c for c in inflow_cols if c in df.columns]
        if not cols:
            cols = [c for c in df.columns if c not in ("datetime",)]
            y = df[cols].sum(axis=1).values
        else:
            y = df[cols].sum(axis=1).values
        traces.append(y)

    cube = np.vstack(traces)
    return dates, cube, log


def load_state_boundaries(
    xlim: tuple[float, float] = MAP_XLIM,
    ylim: tuple[float, float] = MAP_YLIM,
) -> list[tuple[np.ndarray, str]]:
    """Return (Nx2 lon/lat polygon, state name) for DRB states."""
    import shapefile

    shp = DRB_SPATIAL / "states" / "tl_2010_us_state10"
    reader = shapefile.Reader(str(shp))
    field_names = [f[0] for f in reader.fields[1:]]
    name_idx = field_names.index("NAME10") if "NAME10" in field_names else field_names.index("NAME")
    fips_idx = field_names.index("STATEFP10") if "STATEFP10" in field_names else field_names.index("STATEFP")
    polys: list[tuple[np.ndarray, str]] = []
    xmin, xmax = xlim
    ymin, ymax = ylim
    for shape, rec in zip(reader.shapes(), reader.records()):
        if str(rec[fips_idx]).zfill(2) not in DRB_STATEFPS:
            continue
        pts = np.asarray(shape.points)
        if pts.size == 0:
            continue
        if not (
            (pts[:, 0].max() >= xmin and pts[:, 0].min() <= xmax)
            and (pts[:, 1].max() >= ymin and pts[:, 1].min() <= ymax)
        ):
            continue
        parts = list(shape.parts) + [len(pts)]
        for i in range(len(parts) - 1):
            seg = pts[parts[i]: parts[i + 1]]
            if len(seg) >= 3:
                polys.append((seg, str(rec[name_idx])))
    return polys


def resolve_amestoy_hdf5() -> Path:
    for p in AMESTOY_HDF5_CANDIDATES:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Amestoy inputs HDF5 not found. Expected under ~/data/amestoy_2026/"
    )


def load_amestoy_ensemble_inflow(
    nodes: tuple[str, ...] = ("delLordville", "cannonsville", "pepacton", "neversink"),
    hdf5_path: Path | None = None,
) -> tuple[pd.DatetimeIndex, np.ndarray]:
    """Fast bulk load of all 1000 Amestoy members (basin inflow sum, MGD)."""
    import h5py

    path = hdf5_path or resolve_amestoy_hdf5()
    with h5py.File(path, "r") as f:
        sample_grp = f[nodes[0]]
        keys = sorted([k for k in sample_grp.keys() if k.isdigit()], key=int)
        n_days = int(sample_grp[keys[0]].shape[0])
        cube = np.zeros((len(keys), n_days))
        for i, k in enumerate(keys):
            for node in nodes:
                if node in f and k in f[node]:
                    cube[i] += np.asarray(f[node][k])
    dates = pd.date_range("1945-01-01", periods=n_days, freq="D")
    return dates, cube


def amestoy_highlight_ids(cube: np.ndarray) -> dict[str, int]:
    """Dry / normal / wet members by mean annual basin inflow."""
    annual = cube.sum(axis=1)
    order = np.argsort(annual)
    return {
        "dry": int(order[0]),
        "normal": int(order[len(order) // 2]),
        "wet": int(order[-1]),
    }


def load_baseline_storage_envelope(
    max_members: int = 100,
    baseline_dir: Path | None = None,
) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray] | None:
    """
    NYC combined + LB combined storage across baseline rerun members.

    Returns (dates, nyc_cube, lb_cube) or None if outputs unavailable.
    """
    import h5py

    base = baseline_dir or (D4 / "results" / "baseline")
    member_dirs = sorted(base.glob("member_*"))
    if not member_dirs:
        return None
    if len(member_dirs) > max_members:
        idx = np.linspace(0, len(member_dirs) - 1, max_members, dtype=int)
        member_dirs = [member_dirs[i] for i in idx]

    nyc_traces: list[np.ndarray] = []
    lb_traces: list[np.ndarray] = []
    dates: pd.DatetimeIndex | None = None
    for mdir in member_dirs:
        h5_files = list(mdir.glob("obs_pub_*.hdf5"))
        if not h5_files:
            continue
        with h5py.File(h5_files[0], "r") as f:
            if "volume_agg_nyc" not in f:
                continue
            nyc = np.asarray(f["volume_agg_nyc"]).ravel()
            lb = (
                np.asarray(f["reservoir_beltzvilleCombined"]).ravel()
                + np.asarray(f["reservoir_blueMarsh"]).ravel()
            )
        if dates is None:
            dates = pd.date_range("1945-01-01", periods=len(nyc), freq="D")
        nyc_traces.append(nyc)
        lb_traces.append(lb)

    if not nyc_traces:
        return None
    return dates, np.vstack(nyc_traces), np.vstack(lb_traces)


def drought_highlight_ids(log: pd.DataFrame) -> dict[str, int]:
    """Pick one realization per SOW level for overlay in Fig D."""
    out: dict[str, int] = {}
    if log.empty or "pct_change" not in log.columns:
        return {k: i for i, k in enumerate(["dry", "normal", "wet"])}
    for label, target in [("dry", -0.2), ("normal", 0.0), ("wet", 0.2)]:
        sub = log.loc[np.isclose(log["pct_change"], target)]
        if not sub.empty:
            out[label] = int(sub.iloc[0]["realization"])
    return out
