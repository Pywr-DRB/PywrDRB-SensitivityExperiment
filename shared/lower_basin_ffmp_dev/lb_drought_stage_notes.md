# Lower Basin Drought-Stage Switching — Implementation Notes

## Status: IMPLEMENTED ✓ — 2026-05-25

Three changes merged into `dissertation/pywrdrb/`:
1. `parameters/ffmp.py` — `LowerBasinDroughtLevel` class added + registered
2. `model_builder.py` — `drought_level_agg_lb` registered in `add_parameter_nyc_reservoirs_operational_regimes`
3. `parameters/lower_basin_ffmp.py` — `LowerBasinMaxMRFContribution` updated:
   - Loads `drought_level_agg_lb` in `__init__` + `load()` (graceful KeyError fallback)
   - `get_current_usable_reservoirs()` checks both NYC and LB drought levels
   - `value()` computes R_min dynamically from `conservation_releases_normal` vs `conservation_releases_drought`

Next step: run July–Dec 2004 validation run and confirm LB Trenton contributions are non-zero in Oct–Dec 2004.

---


## Problem Statement

`lower_basin_ffmp.py` currently only responds to NYC drought level (`drought_level_agg_nyc`).
The lower basin has its own independent drought staging defined in Water Code §2.5.5.
The `lower_basin_drought_conservation_releases` dict exists in the file but is never activated.

This is the Gap 1 fix. Gap 2 (F.E. Walter / Prompton) is separate and not needed for D1/D4.

---

## What needs to change in lower_basin_ffmp.py

### Change 1: Add LB drought level parameter load

In `LowerBasinMaxMRFContribution.__init__()`, after loading `drought_level_agg_nyc`:
```python
# Add alongside drought_level_agg_nyc
self.drought_level_agg_lb = self.parameters.get("drought_level_agg_lb", None)
if self.drought_level_agg_lb is not None:
    self.children.add(self.drought_level_agg_lb)
```

In `LowerBasinMaxMRFContribution.load()`, add to the parameters dict:
```python
# Load LB drought level if it exists in the model
try:
    parameters["drought_level_agg_lb"] = load_parameter(model, "drought_level_agg_lb")
except KeyError:
    parameters["drought_level_agg_lb"] = None  # graceful fallback until implemented
```

### Change 2: Update get_current_usable_reservoirs()

Current (checks only NYC drought):
```python
def get_current_usable_reservoirs(self, scenario_index):
    current_nyc_drought_level = self.drought_level_agg_nyc.get_value(scenario_index)
    is_nyc_drought_emergency = True if current_nyc_drought_level in [6] else False
    if is_nyc_drought_emergency:
        usable_reservoirs = reservoirs_used_during_drought_conditions
    else:
        usable_reservoirs = reservoirs_used_during_normal_conditions
    return usable_reservoirs
```

Updated (also checks LB drought):
```python
def get_current_usable_reservoirs(self, scenario_index):
    current_nyc_drought_level = self.drought_level_agg_nyc.get_value(scenario_index)
    is_nyc_drought_emergency = current_nyc_drought_level >= 6

    is_lb_drought = False
    if self.drought_level_agg_lb is not None:
        current_lb_drought_level = self.drought_level_agg_lb.get_value(scenario_index)
        is_lb_drought = current_lb_drought_level >= 1  # any LB drought stage active

    if is_nyc_drought_emergency or is_lb_drought:
        usable_reservoirs = reservoirs_used_during_drought_conditions
    else:
        usable_reservoirs = reservoirs_used_during_normal_conditions
    return usable_reservoirs
```

### Change 3: Switch conservation releases based on LB drought stage

In `LowerBasinMaxMRFContribution.__init__()`, `self.R_min` is set once from `conservation_releases`.
This needs to become dynamic — evaluated per timestep based on LB drought state.

Move R_min into `value()`:
```python
def value(self, timestep, scenario_index):
    # Dynamic R_min based on LB drought state
    if (self.drought_level_agg_lb is not None and
        self.drought_level_agg_lb.get_value(scenario_index) >= 1):
        R_min = lower_basin_drought_conservation_releases[self.reservoir]
    else:
        R_min = conservation_releases[self.reservoir]
    # ... use R_min instead of self.R_min in storage calculations below
```

---

## What needs to change in ffmp.py (or model_builder)

`drought_level_agg_lb` is a new parameter that doesn't exist yet. It needs to be defined.

### Option A: Define as a simple threshold parameter in model_builder
LB drought stage = f(combined blueMarsh + beltzville storage as % of max usable)

Thresholds from Water Code §2.5.5 (usable storage fractions):
- Stage 1: beltzville > 73.7% AND blueMarsh > 68.9% → Normal
- Stage 2: beltzville < 73.7% OR blueMarsh < 68.9% → LB Drought Stage 1
- Stage 3–6: lower thresholds per priority_use_during_drought table

Simplest implementation: a new `Parameter` subclass in `ffmp.py`:
```python
class LowerBasinDroughtLevel(Parameter):
    """
    Determines lower basin drought stage based on storage levels.
    Stage 0 = Normal; Stage 1+ = drought conditions from Water Code §2.5.5.
    Independent of NYC drought level.
    """
    def __init__(self, model, lb_nodes, lb_max_usable_storages, **kwargs):
        super().__init__(model, **kwargs)
        self.lb_nodes = lb_nodes  # {'blueMarsh': node, 'beltzvilleCombined': node}
        self.lb_max_usable = lb_max_usable_storages  # from lower_basin_ffmp.drbc_max_usable_storages

    def value(self, timestep, scenario_index):
        # Check each reservoir against §2.5.5 priority thresholds
        # Return highest active drought stage (0 = normal)
        belt_storage = self.lb_nodes['beltzvilleCombined'].volume[scenario_index.indices]
        blue_storage = self.lb_nodes['blueMarsh'].volume[scenario_index.indices]
        
        belt_frac = belt_storage / self.lb_max_usable['beltzvilleCombined']
        blue_frac = blue_storage / self.lb_max_usable['blueMarsh']
        
        # Priority staging from lower_basin_ffmp.priority_use_during_drought
        # Stage 1: primary reservoirs above 73.7% / 68.9%
        if belt_frac < 0.737 or blue_frac < 0.689:
            # Determine sub-stage
            if belt_frac < 0.034 or blue_frac < 0.130:
                return 5  # deepest drought
            elif belt_frac < 0.380 or blue_frac < 0.368:
                return 3
            else:
                return 1
        return 0  # Normal
```

### Option B: Simpler — add lb_drought_level as a computed column from storage

For D1/D4 where you want a quick working implementation:
Compute `drought_level_agg_lb` as a pre-computed array passed as a `ConstantScenarioParameter`
based on the initial storage conditions of each scenario. Less physically correct but faster to implement.

---

## Testing

After implementing, validate against Water Code §2.5.5 staging table:
```python
# Test: force beltzville storage to 30% of max usable (below 0.380 threshold)
# Expected: drought_level_agg_lb = 3
# Expected: conservation release switches to lower_basin_drought_conservation_releases['beltzvilleCombined'] = 15 cfs

# Test: both reservoirs above thresholds
# Expected: drought_level_agg_lb = 0
# Expected: conservation release = conservation_releases['beltzvilleCombined'] = 35 cfs
```

---

## Implementation Order

1. Read ffmp.py lines 540–750 to understand how `drought_level_agg_nyc` is constructed
   (it's likely a DroughtLevelNYC parameter in model_builder, built from aggregated NYC storage)
2. Implement `LowerBasinDroughtLevel` parameter (~60 lines) in ffmp.py
3. Register it: `LowerBasinDroughtLevel.register()`
4. Add to model_builder where `drought_level_agg_nyc` is built — add analogous `drought_level_agg_lb` construction
5. Update `lower_basin_ffmp.py` Changes 1–3 above
6. Run a short validation simulation (2001–2005) with `debugging=True` to confirm stage switching
