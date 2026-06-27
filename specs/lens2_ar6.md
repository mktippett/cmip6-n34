# Spec: lens2_ar6.py

## 1. Purpose

Compute IPCC AR6 WGI reference region averages of surface air temperature
(`TREFHT`, 2 m) from the CESM2 Large Ensemble (LENS2) on AWS S3, for both
forcing variants (`cmip6`, `smbb`) and both experiments (`historical`,
`ssp370`). Covers all 58 AR6 reference regions (46 land + 12 ocean). One
multi-member NetCDF per (variant, experiment) is written for downstream
regional diagnostics.

Directly analogous to `cmip6_ar6.py` for CMIP6; the AR6 averaging math is
identical (same `ar6_averages` logic, same `mask_3D` approach, same dask
rechunk fix). Only the data-access layer differs.

## 2. Inputs

| Source | Content | Selection |
|--------|---------|-----------|
| `s3://ncar-cesm2-lens/atm/monthly/cesm2LE-{experiment}-{variant}-TREFHT.zarr` | `TREFHT(member_id, time, lat, lon)` — 2 m reference-height temperature, K | One store per (variant, experiment); opened via `open_lens2("TREFHT", experiment, variant)` |
| `regionmask.defined_regions.ar6.all` | 58 AR6 WGI reference regions (46 land + 12 ocean) | Built into regionmask; `mask_3D` computed once and reused |
| CLI args `--variant`, `--experiment` | — | Optionally restrict to one variant or experiment for targeted reruns |

## 3. Outputs

| File | Contents | Format |
|------|----------|--------|
| `lens2_ar6_data/ar6_CESM2-LE_{variant}_{experiment}.nc` | `tas(member_id, time, region)` — AR6 regional mean temperature, K; non-dim coords: `abbrevs` (4-letter codes), `names` (full region names, carried from `mask_3D`); attrs: `long_name`, `units`, `source_variable="TREFHT"`, `regions`, `weighting`; scalar vars `forcing_variant`, `experiment`, `source_id="CESM2-LE"` | NetCDF, `zlib=True` |
| `NOTES.md` (prepended entry) | Run summary | markdown, via `append_run_summary` |
| stdout | Progress: variant/experiment, member ids, NaN drops | text |

**File count:** 4 files total (2 variants × 2 experiments).
**Output variable name:** `tas` (matching the CMIP6 pipeline convention, even though the source variable is `TREFHT`).

## 4. Algorithm

1. Parse CLI args; build `variants` and `experiments` lists.
2. Initialize `mask3d = None`, `lat_weights = None` (built once, reused across all stores — all CESM2-LE stores share the same 192×288 FV grid).
3. For each `(variant, experiment)`:
   a. **Restart check**: if output file exists, skip.
   b. `open_lens2("TREFHT", experiment, variant)` → lazy Dataset, 50 members.
   c. If `mask3d is None`:
      - `ar6.mask_3D(ds.lon, ds.lat)` → boolean `(region=58, lat=192, lon=288)`.
      - `lat_weights = DataArray(cos(deg2rad(ds.lat)), dims=["lat"])`.
   d. For each `member_id`:
      1. `ar6_averages(ds.TREFHT.sel(member_id=member_id), mask3d, lat_weights)`:
         - `mask_f = mask3d.astype(float).chunk({"region": -1, "lat": -1, "lon": -1})` — explicit rechunk (see §6).
         - `numerator = xr.dot(trefht * lat_weights, mask_f, dims=["lat", "lon"])`.
         - `denominator = (lat_weights * mask_f).sum(["lat", "lon"])`.
         - Returns `(time, region)` DataArray.
      2. `.compute()`. If any NaN, drop the member.
      3. Otherwise assign `member_id` coord, `expand_dims("member_id")`, append.
   e. If no valid members, record in `skipped_stores`, skip file write.
   f. `xr.concat(member_list, dim="member_id").to_dataset(name="tas")`.
   g. Attach metadata attrs and scalar variables.
   h. Apply `COMP` encoding.
   i. **Atomic write**: `.tmp` → rename.
4. Print dropped-member list.
5. `append_run_summary("lens2_ar6.py", ...)` → prepend to `NOTES.md`.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| AR6 regions | `regionmask.defined_regions.ar6.all` | 58 WGI reference regions (46 land + 12 ocean), matching the CMIP6 pipeline. Land-first ordering (indices 0–45 = land, 46–57 = ocean). |
| Variable: `TREFHT` (not `TS`) | — | TREFHT = 2 m reference-height temperature ≈ `tas` in CMIP6 terminology. `TS` (surface radiative) ≈ SST over ocean and is used for Niño 3.4. ATLAS regional averages validate against `tas`, so `TREFHT` is the correct choice here — mirrors the `ts`/`tas` split in the CMIP6 pipeline. |
| Output variable name | `tas` | Named `tas` (not `TREFHT`) to match the CMIP6 pipeline convention and ATLAS comparison code; the source variable is recorded in `attrs["source_variable"] = "TREFHT"`. |
| Latitude weighting | `cos(deg2rad(lat))` | Standard area weighting. |
| Mask reuse | built once per process | All CESM2-LE stores share the same 192×288 FV grid; `mask3d` and `lat_weights` are computed on the first store and reused for all subsequent ones. |
| Dask rechunk | `.chunk({"region": -1, "lat": -1, "lon": -1})` | Prevents a `ZeroDivisionError` in the dask auto-chunker when the store has many time chunks (inherited fix from `cmip6_ar6.py`, where it was required for EC-Earth3). Harmless otherwise. |
| `COMP` | `{"zlib": True}` | Standard NetCDF compression. |

## 6. Edge Cases & Error Handling

- **All-or-nothing NaN drop**: any NaN anywhere in a member's `regional(time, region)` array drops the entire member. NaN in an AR6 region average indicates either a missing-data cell or a region entirely outside the model domain (unlikely for CESM2 which is global). Logged in `dropped_members`.
- **Dask rechunk fix**: `mask_f.chunk({"region": -1, "lat": -1, "lon": -1})` is required to avoid a `ZeroDivisionError` in dask's auto-chunker when the source zarr has small per-chunk time windows (e.g. 6 months). CESM2-LE chunking is unknown at spec-write time; the fix is defensive and harmless if not needed.
- **`abbrevs`/`names` coords**: these 2D non-dimension coordinates on the `region` axis are automatically produced by `ar6.mask_3D` and survive through `xr.concat` and `to_dataset`. They appear in the output NetCDF as auxiliary variables.
- **Calendar**: CESM2 `noleap` is kept as-is; `open_lens2` does not convert.
- **Restart granularity**: per (variant, experiment) file; existing files are skipped entirely.
- **Atomic write**: `.tmp` approach guards against corrupt partial writes on crash.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|--------------|
| 2026-06-26 | Script created | Spec created (reflects initial code) |
| 2026-06-26 | First run completed (all 4 stores, 0 dropped) | Confirmed: `abbrevs`/`names` coords present; cmip6 `p1f1`, smbb `p1f2`; historical range ~[229, 310] K, ssp370 ~[231, 314] K; 0 NaN |

## Verification Snippet

```python
import xarray as xr
from pathlib import Path
import regionmask

AR6_DIR = Path("lens2_ar6_data")
files = sorted(AR6_DIR.glob("*.nc"))
assert len(files) > 0, "no lens2 ar6 output files found"

ar6 = regionmask.defined_regions.ar6.all
expected_abbrevs = set(ar6.abbrevs)

for path in files:
    ds = xr.open_dataset(path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    assert "tas" in ds.data_vars, f"missing tas in {path.name}"
    assert set(ds.tas.dims) == {"member_id", "time", "region"}, f"wrong dims in {path.name}"
    assert ds.sizes["member_id"] == 50, f"expected 50 members in {path.name}"
    assert ds.sizes["region"] == 58, f"expected 58 regions in {path.name}"
    assert not bool(ds.tas.isnull().any()), f"unexpected NaN in {path.name}"
    assert "abbrevs" in ds.coords, f"missing abbrevs coord in {path.name}"
    assert "names" in ds.coords, f"missing names coord in {path.name}"
    lo, hi = float(ds.tas.min()), float(ds.tas.max())
    assert 150.0 < lo and hi < 350.0, f"tas range [{lo}, {hi}] K implausible in {path.name}"
    for c in ("forcing_variant", "experiment", "source_id"):
        assert c in ds, f"missing scalar coord {c} in {path.name}"
    print(f"OK: {path.name}  members={ds.sizes['member_id']}  regions={ds.sizes['region']}  range=[{lo:.2f}, {hi:.2f}] K")
```
