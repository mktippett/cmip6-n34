# Spec: cmip6_n34r.py

## 1. Purpose

Extract the **relative Niño 3.4 index** — the Niño 3.4 box average of surface
temperature (`ts`) minus the tropical-mean (20°S-20°N, ocean-only) surface
temperature — from CMIP6 monthly output, for every model that provides
`ts`/Amon for the full 8-experiment suite. Removing the tropical-mean
temperature isolates ENSO variability from the tropics-wide background
warming trend (van Oldenborgh et al. 2021; L'Heureux, Tippett et al. 2024,
*J. Climate*). Output is written in raw K with **no climatology removed and
no variance rescaling applied** — see §5 for why the rescaling step in the
published (RONI) recipe is deliberately omitted here.

## 2. Inputs

| File / source | Relevant columns | Filters applied |
|----------------|-------------------|------------------|
| `https://cmip6.storage.googleapis.com/pangeo-cmip6.csv` (remote catalog) | `institution_id`, `source_id`, `experiment_id`, `member_id`, `variable_id`, `table_id`, `zstore` | `variable_id == "ts"`, `table_id == "Amon"`; then `get_valid_pairs` keeps only `(institution_id, source_id)` pairs that have **all** `REQUIRED_EXPERIMENTS` for `ts`/Amon, excluding `EXCLUDED_INSTITUTIONS` — identical selection to `cmip6_n34.py` |
| Per-member zarr store at `row["zstore"]` (GCS, anonymous) | `ts(time, lat, lon)` | opened via `open_member` |
| CLI args `--institution`, `--source` | — | optionally restrict to one institution/source for targeted reruns |

## 3. Outputs

| File | Contents | Format |
|------|----------|--------|
| `n34r_data/n34r_{institution_id}_{source_id}_{experiment_id}.nc` | `n34(member_id, time)`, `trop(member_id, time)`, `n34r(member_id, time)` — all raw K, no anomaly/climatology removal; scalar coords `experiment_id`, `source_id`, `institution_id` | NetCDF, `zlib=True` per-variable compression |
| `NOTES.md` (prepended entry) | Run summary: git hash, files written/skipped, dropped members, experiments with no members | markdown, via `append_run_summary` |
| stdout (typically piped to `run_n34r.log`) | Progress (`institution/source/experiment`, member ids), dropped-member list | text |

`n34` in this output is numerically identical to `n34` in `n34_data/` (same
box, same weighting, same source field) — see §4 step 4a and the
regression check in the Verification Snippet.

## 4. Algorithm

1. Load the pangeo-cmip6 catalog; filter to `variable_id == "ts"`, `table_id == "Amon"`; `get_valid_pairs` as in `cmip6_n34.py`.
2. If `--institution`/`--source` given, restrict `valid_pairs` to matching rows.
3. For each `(institution_id, source_id)` pair:
   - For each `experiment_id` in `REQUIRED_EXPERIMENTS`, for each catalog row (= member):
     1. `open_member(zstore)`, then `sortby("lat")`.
     2. `ocean = ocean_mask(ds.lon, ds.lat)` (`cmip6_utils.ocean_mask`, §5) — rebuilt **fresh for every member**, not cached across the model. See §6 for why.
     3. `n34 = n34_average(ds.ts)` — **unmasked** cosine-weighted mean, box lon∈[190,240]°E, lat∈[-5,5]° (`cmip6_utils.n34_average`, byte-identical logic to `cmip6_n34.py`).
     4. `trop = trop_average(ds.ts, ocean)` — cosine-weighted, ocean-masked mean, lat∈[-20,20]°, **all longitudes** (`cmip6_utils.trop_average`).
     5. **Single `.compute()` call** on a `Dataset({"n34": n34, "trop": trop})`: both averages are lazy views onto the same zarr store, so computing them separately would re-stream the full store per member. Splitting the computed Dataset back into two DataArrays afterward.
     6. If either `n34` or `trop` has any NaN, drop the member (extends the existing all-or-nothing rule to cover both source quantities) and record `(institution_id, source_id, experiment_id, member_id)` in `dropped_members`.
     7. Otherwise `n34r = n34 - trop`; merge `n34`, `trop`, `n34r` into one member-level Dataset; assign `member_id` coord, `expand_dims("member_id")`; append to `n34r_list`.
   - If `n34r_list` is empty, record `(institution_id, source_id, experiment_id)` in `skipped_experiments`; no file written.
   - `xr.merge(n34r_list)`; drop `height` coordinate if present; attach `long_name`/`units`/`region`/`weighting` attrs per variable (§5) and scalar coords `experiment_id`, `source_id`, `institution_id`.
   - Per-variable compression: `for v in ds_out.data_vars: ds_out[v].encoding.update(COMP)` (not dataset-level, which is a no-op — a difference from `cmip6_n34.py`, matching the more careful `lens2_n34.py` pattern).
   - **Restart check**: skip if `n34r_data/n34r_{institution_id}_{source_id}_{experiment_id}.nc` already exists.
   - Atomic write: `.tmp` then `rename`.
4. Print dropped-member list and total; `append_run_summary("cmip6_n34r.py", ...)`.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| Niño 3.4 box | lon ∈ [190°E, 240°E], lat ∈ [-5°, 5°] | Identical to `cmip6_n34.py`/`cmip6_utils.N34_LAT`/`N34_LON`. |
| Tropical-mean band | lat ∈ [-20°, 20°], all longitudes | Van Oldenborgh et al. (2021) and L'Heureux, Tippett et al. (2024) definition; identical band used for the NMME relative index in `../nmme_enso` (`config.TROPICS_LAT`). |
| `n34` unmasked | — | The Niño 3.4 box is 100% ocean at every model resolution checked (CESM2, GFDL-ESM4, MIROC6, IPSL-CM6A-LR, MCM-UA-1-0 — all measured `ocean_frac == 1.0000`), so a land mask is a no-op there; leaving `n34_average` unmasked keeps it byte-identical to `cmip6_n34.py`'s output (confirmed by direct comparison, `xr.testing.assert_allclose` on NCAR/CESM2/historical). |
| Ocean mask | `regionmask.defined_regions.natural_earth_v5_0_0.land_110`, binary (`.isnull()`) | Field is `ts` (defined over land and ocean), unlike NMME's SST field (land already NaN) — a mask is required for the tropical mean, which is ~24% land by area (measured ocean fraction over 20°S-20°N: 0.7610-0.7637 across five model grids, 80×96 to 192×288). |
| Binary vs. fractional (`sftlf`) land weighting | binary chosen | Measured against real `tos` on 7 CMIP6 models with rectilinear ocean grids (1980-2014, matched members): binary-mask relative-index RMSD vs. `tos`-based truth = 0.007-0.078 K (corr ≥ 0.9993); `sftlf`-fractional-weighted RMSD is numerically identical (differs by <0.001 K in every case tested — e.g. CESM2: 0.0196 vs. 0.0199 K). `sftlf` also isn't published for 5 of the 31 `ts`-valid models (BCC-CSM2-MR, FGOALS-f3-L, IITM-ESM, NorESM2-LM, MCM-UA-1-0), so it would cost coverage for no measured benefit. |
| `ts` (not `tos`) as the source field | — | `tos` is only published for 27 of the 31 `ts`-valid models, and 18 of those 27 are on curvilinear or unstructured ocean grids (including an 830,305-cell unstructured mesh, AWI-CM-1-1-MR), requiring a 2D-mask averager and per-model `areacello` weighting. Measured relative-index error from using `ts`+ocean-mask instead of real `tos` is 1.5-7% of the signal (RMSD/σ across the 7 testable models) — small relative to the cost of a curvilinear-safe pipeline. **Caveat**: only the 7 rectilinear-grid models could be validated this way; the remaining 24 models are assumed to behave similarly because the agreement rests on `ts` ≈ SST over ice-free open ocean, a model-formulation property rather than a grid property, not because those specific grids were tested. |
| No sea-ice concern | — | The tropical band (20°S-20°N) and the Niño 3.4 box have no sea ice, so the land-skin-temperature-vs-SST divergence that would matter at high latitudes (where `ts` becomes ice-surface temperature) does not apply here. |
| **No climatology removed, no rescaling applied** | — | Per explicit user request: the goal is the raw, unscaled relative index so alternative anomaly base periods and scaling choices can be explored downstream without re-deriving from the source archive. The published RONI recipe (`../nmme_enso/docs/relative_nino34.md`) multiplies the anomaly difference by σ(n34_anom)/σ(n34r_anom) to restore ±0.5°C-scale thresholds — that step is a plot/analysis-time transform in the sister project, not applied here. `n34r = n34 − trop` is stored in raw K; anomaly removal is linear, so any later choice of base period or scaling can be applied to `n34` and `trop` (or their difference) without loss of generality. |
| `REQUIRED_EXPERIMENTS`, `EXCLUDED_INSTITUTIONS`, `COMP` | as in `cmip6_utils.py` | Same as `cmip6_n34.py` — see `specs/cmip6_n34.md` §5. |

## 6. Edge Cases & Error Handling

- **All-or-nothing NaN drop, extended**: a member is dropped if *either* `n34` or `trop` contains any NaN (not just `n34` as in `cmip6_n34.py`) — both source quantities must be complete for `n34r` to be meaningful.
- **Single-pass compute**: `n34` and `trop` are computed together from one `Dataset(...).compute()` call rather than two separate `.compute()`s, to avoid re-streaming the source zarr store once per average (see global CLAUDE.md guidance on avoiding repeated lazy re-reads).
- **Mask rebuilt per member, not cached across a model — this was a real bug during development, not a design choice made up front.** The first implementation cached `ocean = ocean_mask(ds.lon, ds.lat)` once per model (built from whichever member was opened first) and reused it for every subsequent member and experiment, on the assumption that all members of a model share one grid. That assumption is false at the bit level: different per-member zarr stores for the same CMIP6 model do not encode identical `lat`/`lon` coordinate arrays — measured ~8×10⁻⁶° drift between two EC-Earth3 members. `trop_average`'s `cos(lat) * ocean` multiplication aligns by coordinate label, so applying a mask built from one member's coordinates to a *different* member's data returns **all-NaN**, silently, with no error — verified directly: same mask + same data gives 0/1980 NaN when built from its own coordinates vs. 1980/1980 NaN when built from a different member's. This surfaced as 34 members (6 files, both EC-Earth-Consortium models) being dropped as "missing data" in the first full production run, none of which actually had missing data — confirmed by reprocessing each in isolation with its own freshly-built mask. Rebuilding the mask per member (`ocean_mask` costs ~50 ms on a 256×512 grid, negligible next to the network read) eliminates the whole bug class rather than relying on an unverified cross-member coordinate-identity assumption. `n34_average` was never affected — it does not use the cached mask.
- **`cmip6_ar6.py` uses the identical caching pattern** (`mask3d` built once per model from the first member opened, reused across all experiments/members) and was the pattern this script's first implementation copied. The mechanism is proven exploitable (same test as above, reproduced with real EC-Earth3 coordinates), but a spot-check of the 3 most-affected files in the existing `ar6_data/` archive (by NaN fraction) found no confirmed instance — every case checked was real per-member record-length heterogeneity, not this bug. Not a full audit; unfixed in `cmip6_ar6.py`. See project memory `ar6_mask_caching_fragility` for the complete writeup.
- **Coastal cells are all-or-nothing**: a grid cell that is mostly ocean but touches land is either fully included or fully excluded by the binary mask; measured to contribute <0.001 K of error relative to fractional (`sftlf`) weighting (§5), so not treated as a defect.
- **Restart granularity**: per-(institution, source, experiment) file, same as `cmip6_n34.py` — an existing file is skipped entirely even if it could now include more members; delete the file to regenerate.
- **`n34` values are bit-comparable to `n34_data/`, not the same file**: this script writes a separate `n34r_data/` tree; existing `n34_data/` is untouched, per explicit user request to keep the two directories independent.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|---------------|
| 2026-08-24 | `cmip6_n34r.py` created; `cmip6_utils.py` extended with `N34_LAT`, `N34_LON`, `TROP_LAT`, `n34_average`, `ocean_mask`, `trop_average` | Spec created (initial) |
| 2026-08-24 | Fixed a per-member coordinate-alignment bug: ocean mask was cached once per model and reused across members whose `lat`/`lon` arrays are not bit-identical, silently producing all-NaN `trop` for affected members (34 members / 6 files, all EC-Earth-Consortium, in the first production run). Changed to rebuild the mask fresh per member. Full 248-file archive regenerated and verified against `n34_data/` with zero mismatches (member sets and values) after the fix. | §4 and §6 updated to describe per-member mask rebuild and document the bug |

## Verification Snippet

```python
import xarray as xr
from pathlib import Path

N34R_DIR = Path("n34r_data")
files = sorted(N34R_DIR.glob("*.nc"))
assert len(files) > 0, "no n34r output files found"

ds = xr.open_dataset(files[0], decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
for v in ("n34", "trop", "n34r"):
    assert v in ds.data_vars, f"missing {v}"
    assert set(ds[v].dims) == {"member_id", "time"}
    assert not bool(ds[v].isnull().any()), f"unexpected NaN in {v}"

assert bool((abs(ds.n34r - (ds.n34 - ds.trop)) < 1e-9).all()), "n34r != n34 - trop"

lo, hi = float(ds.trop.min()), float(ds.trop.max())
assert 250.0 < lo and hi < 315.0, f"trop range [{lo}, {hi}] K outside plausible bounds"

# Regression check: n34 here should equal n34 in the original n34_data/ output
# for any model present in both trees (box/weighting/source field unchanged).
old_path = Path("n34_data") / files[0].name.replace("n34r_", "n34_")
if old_path.exists():
    old = xr.open_dataset(old_path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    common = sorted(set(ds.member_id.values) & set(old.member_id.values))
    xr.testing.assert_allclose(ds.n34.sel(member_id=common), old.n34.sel(member_id=common))
    print("Regression check passed: n34 matches n34_data/")

print(f"OK: {files[0].name}  members={ds.member_id.values.tolist()}  "
      f"trop range=[{lo:.2f}, {hi:.2f}] K")
```
