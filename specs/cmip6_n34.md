# Spec: cmip6_n34.py

## 1. Purpose

Extract the Niño 3.4 index — the area-averaged surface temperature (`ts`,
used as a proxy for SST) over the standard Niño 3.4 box (5°S-5°N,
170°W-120°W) — from CMIP6 monthly output, for every model that provides
`ts`/Amon for the full 8-experiment suite, retaining all available ensemble
members. One multi-member NetCDF per model/experiment is written for
downstream ENSO diagnostics.

## 2. Inputs

| File / source | Relevant columns | Filters applied |
|----------------|-------------------|------------------|
| `https://cmip6.storage.googleapis.com/pangeo-cmip6.csv` (remote catalog) | `institution_id`, `source_id`, `experiment_id`, `member_id`, `variable_id`, `table_id`, `zstore` | `variable_id == "ts"`, `table_id == "Amon"`; then `get_valid_pairs` keeps only `(institution_id, source_id)` pairs that have **all** `REQUIRED_EXPERIMENTS` for `ts`/Amon, excluding `EXCLUDED_INSTITUTIONS` |
| Per-member zarr store at `row["zstore"]` (GCS, anonymous) | `ts(time, lat, lon)` | opened via `open_member` (see Algorithm step 4a) |
| CLI args `--institution`, `--source` | — | optionally restrict `valid_pairs` to one institution/source for targeted reruns |

## 3. Outputs

| File | Contents | Format |
|------|----------|--------|
| `n34_data/n34_{institution_id}_{source_id}_{experiment_id}.nc` | `n34(member_id, time)` — Niño 3.4 index, K; scalar coords `experiment_id`, `source_id`, `institution_id` | NetCDF, `zlib=True` compression (`COMP`) |
| `NOTES.md` (prepended entry) | Run summary: git hash, files written/skipped, dropped members, experiments with no members | markdown, via `append_run_summary` |
| stdout (typically piped to `run_n34.log`) | Progress (`institution/source/experiment`, member ids), dropped-member list | text |

## 4. Algorithm

1. Load the pangeo-cmip6 catalog; filter to `variable_id == "ts"`, `table_id == "Amon"`.
2. `get_valid_pairs(df_ts)`: for each `(institution_id, source_id)`, require that the set of `experiment_id`s present for `ts`/Amon is a superset of `REQUIRED_EXPERIMENTS` (8 experiments, see §5); drop any pair whose `institution_id` is in `EXCLUDED_INSTITUTIONS`.
3. If `--institution`/`--source` given, further restrict `valid_pairs` to matching rows.
4. For each `(institution_id, source_id)` pair, for each `experiment_id` in `REQUIRED_EXPERIMENTS` (fixed order):
   - For each catalog row (= ensemble member) matching that experiment:
     1. **`open_member(zstore)`** (in `cmip6_utils.py`):
        - `xr.open_zarr(zstore, storage_options={"token": "anon"}, consolidated=True, decode_times=cftime)`.
        - If `time` index is not monotonically increasing, `sortby("time")`.
        - `convert_to_cftime_no_leap`: replace the time coordinate with `cftime.DatetimeNoLeap(year, month, 15)` for every step — standardizes heterogeneous source calendars to a common no-leap monthly axis (day fixed at 15 regardless of source day-of-month).
        - `standardize_lonlat`: rename `latitude→lat`, `longitude→lon` if present.
     2. **`n34_average(ds.ts)`**:
        - `sortby("lat")` (ascending).
        - `weights = cos(deg2rad(lat))`.
        - `.sel(lon=slice(190, 240)).sel(lat=slice(-5, 5))` → `.weighted(weights).mean(["lon", "lat"])` → `(time,)`.
        - copy original attrs onto the result.
     3. `.compute()`. If the resulting series has any NaN, drop this member entirely and record `(institution_id, source_id, experiment_id, member_id)` in `dropped_members`.
     4. Otherwise assign `member_id` as a new scalar coord and `expand_dims("member_id")`; append to `n34_list`.
   - If `n34_list` is empty after all members, record `(institution_id, source_id, experiment_id)` in `skipped_experiments` and continue (no output file for this experiment).
   - `xr.merge(n34_list)` along `member_id`. Drop the `height` coordinate if present (not all source models carry it).
   - Attach scalar coords `experiment_id`, `source_id`, `institution_id`.
   - `ds_out.encoding.update(COMP)` (`zlib=True`).
   - **Restart check**: if `n34_data/n34_{institution_id}_{source_id}_{experiment_id}.nc` already exists, skip (count in `n_existed`) — do not overwrite or merge.
   - Otherwise write to `<filename>.tmp` via `to_netcdf`, then `rename` to the final filename (atomic write).
5. Print the full `dropped_members` list and total count.
6. `append_run_summary("cmip6_n34.py", n_written, n_existed, dropped_members, skipped_experiments)` — prepends a dated entry to `NOTES.md` (after its `# Project Notes` header) with the current short git hash.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| Niño 3.4 box | lon ∈ [190°E, 240°E] (= 170°W-120°W), lat ∈ [-5°, 5°] | Standard Niño 3.4 region definition used for ENSO SST monitoring. |
| Latitude weighting | `cos(deg2rad(lat))` | Standard area weighting for a regular lat-lon grid. |
| Variable: `ts` (not `tas`) | — | `ts` (surface temperature) ≈ SST over open ocean, matching the conventional SST-based Niño 3.4 definition. (`cmip6_ar6.py` uses `tas` instead, to match the ATLAS reference dataset — see `specs/cmip6_ar6.md`.) |
| `REQUIRED_EXPERIMENTS` (`cmip6_utils.py`) | `historical, ssp245, ssp585, ssp370, ssp126, abrupt-4xCO2, piControl, 1pctCO2` (8) | Project requires the full CMIP6 DECK + ScenarioMIP suite per model (historical + 4 SSPs + 3 idealized DECK experiments) so that downstream analyses can compare across all of them for the same model/member. |
| `EXCLUDED_INSTITUTIONS` (`cmip6_utils.py`) | `["NIMS-KMA"]` | NIMS-KMA's time format is incompatible with `convert_to_cftime_no_leap`/`open_member`. |
| Calendar standardization | `cftime.DatetimeNoLeap(year, month, 15)` | Normalizes the many source calendars (`gregorian`, `360_day`, etc.) to a common no-leap monthly axis with a fixed day-of-month, so multi-model time axes align exactly. |
| `COMP = {"zlib": True}` | — | Standard NetCDF compression for output files. |

## 6. Edge Cases & Error Handling

- **All-or-nothing NaN drop**: any NaN anywhere in a member's `n34(time)` series causes the *entire member* to be dropped (no partial/masked output) and logged in `dropped_members`.
- **Zero-member experiments**: if every member of an experiment is dropped (or none exist), the experiment is recorded in `skipped_experiments` and **no output file is written** for it — a later rerun targeting that model would re-attempt it (restart logic only skips experiments that already produced a file).
- **Restart granularity is per-(institution, source, experiment) file**: an existing file is skipped entirely, even if it could now include additional members. To regenerate, delete the file first (or use `--institution`/`--source` plus manual deletion).
- **Atomic write**: `to_netcdf` writes to `<filename>.tmp`; `rename` to the final name only happens on success, so a crash mid-write never leaves a corrupt `.nc` at the final path (it may leave a stray `.tmp`).
- **`height` coordinate**: present on `ts` for some models as a scalar "near-surface height" coordinate; dropped after merge only if present (existence-checked, not assumed).
- **Models excluded by `get_valid_pairs` (not `EXCLUDED_INSTITUTIONS`)**: a model with `ts`/Amon missing for one or more `REQUIRED_EXPERIMENTS` is silently absent from `valid_pairs` — no log entry. Observed cases (per project memory, as of 2026-06-11): CAS-ESM2-0, ACCESS-ESM1-5, GISS-E2-1-H.
- **Non-monotonic time axes**: sorted by `open_member` before calendar conversion, so out-of-order source chunks don't produce a misordered output time axis.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|--------------|
| 2026-06-12 | — | Spec created (initial); reflects code as of commit `2538d4c` |

## Verification Snippet

```python
import xarray as xr
from pathlib import Path

N34_DIR = Path("n34_data")
files = sorted(N34_DIR.glob("*.nc"))
assert len(files) > 0, "no n34 output files found"

ds = xr.open_dataset(files[0], decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))

assert "n34" in ds.data_vars
assert set(ds.n34.dims) == {"member_id", "time"}
assert not bool(ds.n34.isnull().any()), "unexpected NaN in n34"

lo, hi = float(ds.n34.min()), float(ds.n34.max())
assert 250.0 < lo and hi < 315.0, f"n34 range [{lo}, {hi}] K outside QC bounds"

for c in ("experiment_id", "source_id", "institution_id"):
    assert c in ds, f"missing scalar coord {c}"

print(f"OK: {files[0].name}  members={ds.member_id.values.tolist()}  "
      f"n34 range=[{lo:.2f}, {hi:.2f}] K")
```
