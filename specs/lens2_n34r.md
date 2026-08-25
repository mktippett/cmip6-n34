# Spec: lens2_n34r.py

## 1. Purpose

Compute the **relative Niño 3.4 index** — Niño 3.4 (`TS`) minus the
tropical-mean (20°S-20°N, ocean-only) surface temperature — from the CESM2
Large Ensemble (LENS2) on AWS S3, for both forcing variants (`cmip6`,
`smbb`) and both experiments (`historical`, `ssp370`). Output is raw K, no
climatology removed, no variance rescaling applied.

Directly analogous to `cmip6_n34r.py` for CMIP6; the math (box definitions,
ocean masking, raw/unscaled output) is identical. Only the data-access layer
differs (AWS S3 zarr vs. GCS catalog), matching the existing
`lens2_n34.py`/`cmip6_n34.py` relationship. See `specs/cmip6_n34r.md` §5 for
the full rationale (ts-vs-tos evidence, ocean-mask choice, why rescaling is
omitted) — not repeated here.

## 2. Inputs

| Source | Content | Selection |
|--------|---------|-----------|
| `s3://ncar-cesm2-lens/atm/monthly/cesm2LE-{experiment}-{variant}-TS.zarr` | `TS(member_id, time, lat, lon)` — surface radiative temperature, K | One store per (variant, experiment); opened via `open_lens2("TS", experiment, variant)` |
| CLI args `--variant`, `--experiment` | — | Optionally restrict to one variant or one experiment for targeted reruns |

## 3. Outputs

| File | Contents | Format |
|------|----------|--------|
| `lens2_n34r_data/n34r_CESM2-LE_{variant}_{experiment}.nc` | `n34(member_id, time)`, `trop(member_id, time)`, `n34r(member_id, time)` — all raw K; attrs per variable: `long_name`, `units`, `source_variable="TS"`, `region`, `weighting`; scalar vars `forcing_variant`, `experiment`, `source_id="CESM2-LE"` | NetCDF, `zlib=True` per-variable |
| `NOTES.md` (prepended entry) | Run summary: git hash, written/skipped/dropped counts | markdown, via `append_run_summary` |
| stdout | Progress: variant/experiment, member ids, NaN drops | text |

**File count:** 4 files total (2 variants × 2 experiments).

## 4. Algorithm

1. Parse CLI args; build `variants` and `experiments` lists (default: all 4 combinations).
2. Ocean mask is built **once** for the whole run (grid is identical across all four LENS2 stores), on first store opened.
3. For each `(variant, experiment)`:
   a. **Restart check**: skip if `lens2_n34r_data/n34r_CESM2-LE_{variant}_{experiment}.nc` exists.
   b. `open_lens2("TS", experiment, variant)`, then `sortby("lat")` → lazy Dataset with 50 `member_id` values.
   c. On first store: `ocean = ocean_mask(ds.lon, ds.lat)`.
   d. For each `member_id`:
      1. `n34 = n34_average(ds.TS.sel(member_id=member_id))` — unmasked, box lon∈[190,240]°E lat∈[-5,5]°.
      2. `trop = trop_average(ds.TS.sel(member_id=member_id), ocean)` — ocean-masked, lat∈[-20,20]°, all longitudes.
      3. Single `.compute()` on `Dataset({"n34": n34, "trop": trop})` — avoids re-streaming the member's data twice.
      4. If either has NaN, drop the member, record in `dropped_members`.
      5. Otherwise `n34r = n34 - trop`; merge into a member-level Dataset; assign `member_id` coord, `expand_dims`; append.
   e. If no valid members, record in `skipped_stores`, skip file write.
   f. `xr.merge(n34r_list)` → `ds_out`; attach per-variable attrs and scalar vars.
   g. Per-variable `COMP` encoding.
   h. Atomic write: `.tmp` → `rename`.
4. Print dropped-member list and total; `append_run_summary("lens2_n34r.py", ...)`.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| Niño 3.4 box, tropical-mean band, ocean mask, no-rescaling decision | identical to `cmip6_n34r.py` | See `specs/cmip6_n34r.md` §5 for the full evidence and rationale — CESM2-LE shares the CMIP6 pipeline's `cmip6_utils.n34_average`/`ocean_mask`/`trop_average` via `lens2_utils.py`'s re-export, so the same code (and the same measured accuracy) applies. |
| CESM2 grid | 192 lat × 288 lon, lon 0-360° | FV dynamical core at ~1° resolution; same grid used for the ocean-mask evidence measurements in `specs/cmip6_n34r.md` (CESM2 RMSD vs. `tos`-based truth: 0.020 K on a relative-index σ of 1.13 K). |
| Calendar | `noleap` (native) | No calendar conversion needed, same as `lens2_n34.py`. |
| `COMP` | `{"zlib": True}` | Standard NetCDF compression. |

## 6. Edge Cases & Error Handling

- **All-or-nothing NaN drop, extended**: a member is dropped if either `n34` or `trop` has any NaN (matches `cmip6_n34r.py`, extends the single-variable rule in `lens2_n34.py`).
- **Ocean mask built once for the whole run, not per member**: unlike CMIP6 (§6 of `specs/cmip6_n34r.md` — mask must be rebuilt per member there, because different per-member zarr stores don't encode bit-identical `lat`/`lon`), LENS2 stores all 50 members of a store under one shared `lat`/`lon` coordinate array with no `member_id` dimension — verified directly (`'member_id' in ds.lat.dims` is `False`), so every member of a store is guaranteed to share exactly the same coordinates. Also verified `lat`/`lon` are bit-identical across all four LENS2 stores (`np.array_equal`), so caching across stores, not just within one, is safe too. Mirrors the `mask3d` caching pattern in `lens2_ar6.py`, which is safe for the same reason.
- **Single-pass compute**: as in `cmip6_n34r.py`, `n34` and `trop` are computed together to avoid streaming each member's `TS` data twice.
- **Atomic write, restart granularity**: identical to `lens2_n34.py`.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|---------------|
| 2026-08-24 | `lens2_n34r.py` created | Spec created (initial) |
| 2026-08-24 | Verified LENS2 is not affected by the coordinate-alignment mask-caching bug found and fixed in `cmip6_n34r.py` (see `specs/cmip6_n34r.md` §6 Synchronization Log) — confirmed `lat`/`lon` have no `member_id` dimension and are bit-identical across all four stores. No code change needed here. | §6 updated to record the verification |

## Verification Snippet

```python
import xarray as xr
from pathlib import Path

N34R_DIR = Path("lens2_n34r_data")
files = sorted(N34R_DIR.glob("*.nc"))
assert len(files) > 0, "no lens2 n34r output files found"

for path in files:
    ds = xr.open_dataset(path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    for v in ("n34", "trop", "n34r"):
        assert v in ds.data_vars, f"missing {v} in {path.name}"
        assert set(ds[v].dims) == {"member_id", "time"}, f"wrong dims in {path.name}"
        assert not bool(ds[v].isnull().any()), f"unexpected NaN in {path.name}"
    assert ds.sizes["member_id"] == 50, f"expected 50 members in {path.name}"
    assert bool((abs(ds.n34r - (ds.n34 - ds.trop)) < 1e-9).all()), f"n34r != n34 - trop in {path.name}"
    lo, hi = float(ds.trop.min()), float(ds.trop.max())
    assert 250.0 < lo and hi < 315.0, f"trop range [{lo}, {hi}] K outside plausible bounds in {path.name}"
    for c in ("forcing_variant", "experiment", "source_id"):
        assert c in ds, f"missing scalar coord {c} in {path.name}"
    print(f"OK: {path.name}  members={ds.sizes['member_id']}  trop range=[{lo:.2f}, {hi:.2f}] K")
```
