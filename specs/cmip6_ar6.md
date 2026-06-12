# Spec: cmip6_ar6.py

## 1. Purpose

Extract IPCC AR6 WGI regional-average 2 m air temperature (`tas`) from CMIP6
monthly output, for every model that provides `tas`/Amon for the full
8-experiment suite, retaining all available ensemble members. Computes
latitude-weighted means over all 58 AR6 reference regions (46 land + 12
ocean) and writes one multi-member NetCDF per model/experiment, for regional
climate-change diagnostics and for validation against ATLAS precomputed
aggregates (`test_ar6.py`, `specs/test_ar6.md`).

## 2. Inputs

| File / source | Relevant columns | Filters applied |
|----------------|-------------------|------------------|
| `https://cmip6.storage.googleapis.com/pangeo-cmip6.csv` (remote catalog) | `institution_id`, `source_id`, `experiment_id`, `member_id`, `variable_id`, `table_id`, `zstore` | `variable_id == "tas"`, `table_id == "Amon"`; then `get_valid_pairs` keeps only `(institution_id, source_id)` pairs with **all** `REQUIRED_EXPERIMENTS` for `tas`/Amon, excluding `EXCLUDED_INSTITUTIONS` |
| Per-member zarr store at `row["zstore"]` (GCS, anonymous) | `tas(time, lat, lon)`, `lon`, `lat` | opened via `open_member` (same as `cmip6_n34.py`, see `specs/cmip6_n34.md` §4) |
| `regionmask.defined_regions.ar6.all` | region polygons, `abbrevs`, `names` | all 58 regions (46 land + 12 ocean) |
| CLI args `--institution`, `--source` | — | optionally restrict `valid_pairs` to one institution/source for targeted reruns |

## 3. Outputs

| File | Contents | Format |
|------|----------|--------|
| `ar6_data/ar6_{institution_id}_{source_id}_{experiment_id}.nc` | `tas(member_id, time, region)` — K; `region` coord (58, int index) carries non-dimension coords `abbrevs` (4-letter codes) and `names` (full names); scalar coords `experiment_id`, `source_id`, `institution_id` | NetCDF, `zlib=True` compression (`COMP`) |
| `NOTES.md` (prepended entry) | Run summary: git hash, files written/skipped, dropped members, experiments with no members | markdown, via `append_run_summary` |
| stdout (typically piped to `run_ar6.log`) | Progress (`institution/source/experiment`, member ids), dropped-member list | text |

## 4. Algorithm

1. Load the pangeo-cmip6 catalog; filter to `variable_id == "tas"`, `table_id == "Amon"`.
2. `get_valid_pairs(df_tas)`: same logic as `cmip6_n34.py` but evaluated against `tas`/Amon availability (see `specs/cmip6_n34.md` §4 step 2).
3. If `--institution`/`--source` given, restrict `valid_pairs` accordingly.
4. `ar6 = regionmask.defined_regions.ar6.all` — 58 regions, ordered land-first (indices 0-45, the original `ar6.land` set) then ocean (indices 46-57: ARO, NPO, EPO, SPO, NAO, EAO, SAO, ARS, BOB, EIO, SIO, SOO).
5. For each `(institution_id, source_id)` pair:
   - Reset `mask3d = None`, `lat_weights = None` (computed once per model, reused across all experiments/members — **assumes every member/experiment of a model shares the same `lon`/`lat` grid**, true under CMIP6 conventions).
   - For each `experiment_id` in `REQUIRED_EXPERIMENTS` (fixed order):
     - For each catalog row (= ensemble member) matching that experiment:
       1. `open_member(zstore)` — see `specs/cmip6_n34.md` §4 step 4a.
       2. If `mask3d` is still `None` (first member of this model):
          - `mask3d = ar6.mask_3D(ds.lon, ds.lat)` → boolean `(region, lat, lon)`, 58 regions.
          - `lat_weights = cos(deg2rad(lat))`, dims `(lat,)`.
       3. **`ar6_averages(ds.tas, mask3d, lat_weights)`**:
          - `mask_f = mask3d.astype(float).chunk({"region": -1, "lat": -1, "lon": -1})` — explicit single-chunk over region/lat/lon (see §5, EC-Earth3 fix).
          - `numerator = xr.dot(tas * lat_weights, mask_f, dims=["lat", "lon"])` → `(time, region)`.
          - `denominator = (lat_weights * mask_f).sum(["lat", "lon"])` → `(region,)`.
          - return `numerator / denominator` → `(time, region)`.
       4. `.compute()`. If the resulting `(time, region)` array has any NaN, drop this member entirely and record `(institution_id, source_id, experiment_id, member_id)` in `dropped_members`.
       5. Otherwise assign `member_id` as a new scalar coord and `expand_dims("member_id")`; append to `member_list`.
     - If `member_list` is empty, record `(institution_id, source_id, experiment_id)` in `skipped_experiments` and continue (no output file).
     - `xr.concat(member_list, dim="member_id").to_dataset(name="tas")`.
     - Attach scalar coords `experiment_id`, `source_id`, `institution_id`.
     - `ds_out.encoding.update(COMP)` (`zlib=True`).
     - **Restart check**: skip (count in `n_existed`) if `ar6_data/ar6_{institution_id}_{source_id}_{experiment_id}.nc` already exists.
     - Otherwise write to `<filename>.tmp`, then `rename` to the final filename (atomic write).
6. Print the full `dropped_members` list and total count.
7. `append_run_summary("cmip6_ar6.py", n_written, n_existed, dropped_members, skipped_experiments)`.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| Region set | `regionmask.defined_regions.ar6.all` — 58 regions (46 land + 12 ocean) | As of 2026-06-11, switched from `ar6.land` (46 regions) to cover ocean regions too; `tas` is global (2 m air temp over both land and ocean), so ocean regions are fully populated with no new NaN drops (NOTES.md, 2026-06-11). |
| Latitude weighting | `cos(deg2rad(lat))` | Standard area weighting for a regular lat-lon grid. |
| Variable: `tas` (not `ts`) | — | Chosen to match ATLAS's precomputed `CMIP6_tas_landsea` regional aggregates, used as the validation reference in `test_ar6.py` (mean \|diff\| 0.097 °C across all 58 regions). (`cmip6_n34.py` uses `ts` instead — see `specs/cmip6_n34.md`.) |
| `mask_f` rechunk: `{"region": -1, "lat": -1, "lon": -1}` before `xr.dot` | — | Fixes a dask `ZeroDivisionError` in the auto-chunker when `tas` has many time chunks (e.g. EC-Earth3, 16 time chunks). Forcing `mask_f` to a single chunk over region/lat/lon avoids the mismatched-chunking path. |
| `REQUIRED_EXPERIMENTS`, `EXCLUDED_INSTITUTIONS`, calendar standardization, `COMP` | shared with `cmip6_n34.py` | See `specs/cmip6_n34.md` §5 — identical rationale, defined once in `cmip6_utils.py`. |

## 6. Edge Cases & Error Handling

- **Mask/weights computed once per model**: if a model's experiments/members were ever on different grids, the reused `mask3d`/`lat_weights` from the first member would silently misalign with later members' `tas`. Not observed in practice (CMIP6 models use one grid per source).
- **All-or-nothing NaN drop**: any NaN anywhere in a member's `(time, region)` array drops the *entire member* (no partial/per-region masking), logged in `dropped_members`.
- **Zero-member experiments**: recorded in `skipped_experiments`; no output file written — restart logic will re-attempt these on a future run (only existing-file experiments are skipped).
- **Restart granularity is per-(institution, source, experiment) file**, atomic via `.tmp` + `rename` — identical to `cmip6_n34.py` (see `specs/cmip6_n34.md` §6).
- **`region` is an integer index (0-57)**, not a label; `abbrevs`/`names` are non-dimension coordinates carried along so downstream code (e.g. `test_ar6.py`) can map index → AR6 region abbrev/name without a separate lookup table (confirmed sufficient — project memory, 2026-06-11).
- **A model's grid might not cover all 58 regions** (e.g., a model missing polar gridpoints) — `mask_3D` would still return 58 masks, some possibly all-`False`, giving `denominator = 0` and a NaN/inf for that region, which would trigger the all-or-nothing NaN drop for the member. Not observed for `tas` (global variable) as of the 2026-06-11 58-region run (0 dropped, 272 files written).

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|--------------|
| 2026-06-12 | — | Spec created (initial); reflects code as of commit `2538d4c` |

## Verification Snippet

```python
import xarray as xr
from pathlib import Path

AR6_DIR = Path("ar6_data")
files = sorted(AR6_DIR.glob("*.nc"))
assert len(files) > 0, "no ar6 output files found"

ds = xr.open_dataset(files[0], decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))

assert "tas" in ds.data_vars
assert set(ds.tas.dims) == {"member_id", "time", "region"}
assert ds.sizes["region"] == 58, f"expected 58 regions, got {ds.sizes['region']}"
assert not bool(ds.tas.isnull().any()), "unexpected NaN in tas"

for c in ("abbrevs", "names", "experiment_id", "source_id", "institution_id"):
    assert c in ds.coords or c in ds, f"missing coord/var {c}"

lo, hi = float(ds.tas.min()), float(ds.tas.max())
assert 150.0 < lo and hi < 340.0, f"tas range [{lo}, {hi}] K implausible"

print(f"OK: {files[0].name}  regions={ds.sizes['region']}  "
      f"members={ds.member_id.values.tolist()}  tas range=[{lo:.1f}, {hi:.1f}] K")
```
