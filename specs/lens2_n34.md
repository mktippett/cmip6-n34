# Spec: lens2_n34.py

## 1. Purpose

Compute the Niño 3.4 index — the area-averaged surface temperature (`TS`) over
the standard Niño 3.4 box (5°S–5°N, 170°W–120°W) — from the CESM2 Large
Ensemble (LENS2) on AWS S3, for both forcing variants (`cmip6`, `smbb`) and
both experiments (`historical`, `ssp370`). One multi-member NetCDF per
(variant, experiment) is written for downstream ENSO diagnostics.

Directly analogous to `cmip6_n34.py` for CMIP6; the Niño 3.4 math is
identical. Only the data-access layer differs (AWS S3 zarr vs. GCS catalog).

## 2. Inputs

| Source | Content | Selection |
|--------|---------|-----------|
| `s3://ncar-cesm2-lens/atm/monthly/cesm2LE-{experiment}-{variant}-TS.zarr` | `TS(member_id, time, lat, lon)` — surface radiative temperature, K | One store per (variant, experiment); opened via `open_lens2("TS", experiment, variant)` |
| CLI args `--variant`, `--experiment` | — | Optionally restrict to one variant or one experiment for targeted reruns |

## 3. Outputs

| File | Contents | Format |
|------|----------|--------|
| `lens2_n34_data/n34_CESM2-LE_{variant}_{experiment}.nc` | `n34(member_id, time)` — Niño 3.4 index, K; attrs: `long_name`, `units`, `source_variable="TS"`, `region`, `weighting`; scalar vars `forcing_variant`, `experiment`, `source_id="CESM2-LE"` | NetCDF, `zlib=True` |
| `NOTES.md` (prepended entry) | Run summary: git hash, written/skipped/dropped counts | markdown, via `append_run_summary` |
| stdout | Progress: variant/experiment, member ids, NaN drops | text |

**File count:** 4 files total (2 variants × 2 experiments).

## 4. Algorithm

1. Parse CLI args; build `variants` and `experiments` lists (default: all 4 combinations).
2. For each `(variant, experiment)`:
   a. **Restart check**: if `lens2_n34_data/n34_CESM2-LE_{variant}_{experiment}.nc` exists, skip (count in `n_existed`) — do not overwrite.
   b. `open_lens2("TS", experiment, variant)` → lazy Dataset with 50 `member_id` values.
   c. For each `member_id`:
      1. `n34_average(ds.TS.sel(member_id=member_id))`:
         - `sortby("lat")` (ascending).
         - `weights = cos(deg2rad(lat))`.
         - `.sel(lon=slice(190, 240)).sel(lat=slice(-5, 5))` → `.weighted(weights).mean(["lon", "lat"])` → `(time,)` series.
         - Copies original attrs.
      2. `.compute()`. If any NaN, drop the member and record in `dropped_members`.
      3. Otherwise assign `member_id` coord, `expand_dims("member_id")`, append.
   d. If no valid members, record in `skipped_stores`, skip file write.
   e. `xr.merge(n34_list)` → `ds_out`.
   f. Attach metadata attrs and scalar variables.
   g. Apply `COMP = {"zlib": True}` encoding.
   h. **Atomic write**: `to_netcdf(<filename>.tmp)` → `rename` to final filename.
3. Print dropped-member list and total.
4. `append_run_summary("lens2_n34.py", ...)` → prepend to `NOTES.md`.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| Niño 3.4 box | lon ∈ [190°E, 240°E] (= 170°W–120°W), lat ∈ [−5°, 5°] | Standard Niño 3.4 region definition; identical to `cmip6_n34.py`. |
| Latitude weighting | `cos(deg2rad(lat))` | Standard area weighting for a regular lat-lon grid. |
| Variable: `TS` (not `TREFHT`) | — | `TS` is surface radiative temperature (≈ SST over ocean), matching the conventional SST-based Niño 3.4 definition. (`lens2_ar6.py` uses `TREFHT` to match the ATLAS reference dataset — see `specs/lens2_ar6.md`.) Mirrors the `ts`/`tas` split in the CMIP6 pipeline. |
| CESM2 grid | 192 lat × 288 lon, lon 0–360° | FV dynamical core at ~1° resolution. Niño 3.4 `sel(lon=slice(190,240))` applies directly. |
| Calendar | `noleap` (native) | No calendar conversion needed; CESM2 uses `noleap` natively. |
| Restart granularity | per (variant, experiment) file | One file per combination; existing files are skipped entirely. To regenerate, delete the file and re-run (or use `--variant`/`--experiment`). |
| `COMP` | `{"zlib": True}` | Standard NetCDF compression. |

## 6. Edge Cases & Error Handling

- **All-or-nothing NaN drop**: any NaN anywhere in a member's `n34(time)` series drops the entire member — no partial output. Logged in `dropped_members`.
- **Zero-member stores**: if all members are dropped, record in `skipped_stores`; no output file written.
- **Atomic write**: crash during `to_netcdf(.tmp)` leaves a stray `.tmp` but the final `.nc` is never partially written. A stray `.tmp` is safe to delete; it will be overwritten on the next run.
- **No calendar conversion**: CESM2's `noleap` calendar is kept as-is. The `open_lens2` opener does not call `convert_to_cftime_no_leap` — unnecessary for a single-model homogeneous dataset.
- **No `height` coordinate**: CESM2 `TS` does not carry a scalar `height` coordinate (unlike some CMIP6 `ts` variables), so the `height`-drop step from `cmip6_n34.py` is absent.
- **`lon` already 0–360°**: CESM2 uses 0–358.75°E; no lon rolling needed before `sel(lon=slice(190,240))`.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|--------------|
| 2026-06-26 | Script created | Spec created (reflects initial code) |
| 2026-06-26 | First run completed (all 4 stores, 0 dropped) | Confirmed: cmip6 members use `p1f1` suffix, smbb members use `p1f2`; historical=1980 steps, ssp370=1032 steps |

## Verification Snippet

```python
import xarray as xr
from pathlib import Path

N34_DIR = Path("lens2_n34_data")
files = sorted(N34_DIR.glob("*.nc"))
assert len(files) > 0, "no lens2 n34 output files found"

for path in files:
    ds = xr.open_dataset(path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    assert "n34" in ds.data_vars, f"missing n34 in {path.name}"
    assert set(ds.n34.dims) == {"member_id", "time"}, f"wrong dims in {path.name}"
    assert ds.sizes["member_id"] == 50, f"expected 50 members in {path.name}"
    assert not bool(ds.n34.isnull().any()), f"unexpected NaN in {path.name}"
    lo, hi = float(ds.n34.min()), float(ds.n34.max())
    assert 250.0 < lo and hi < 315.0, f"n34 range [{lo}, {hi}] K outside QC bounds in {path.name}"
    for c in ("forcing_variant", "experiment", "source_id"):
        assert c in ds, f"missing scalar coord {c} in {path.name}"
    print(f"OK: {path.name}  members={ds.sizes['member_id']}  range=[{lo:.2f}, {hi:.2f}] K")
```
