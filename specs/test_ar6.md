# Spec: test_ar6.py

## 1. Purpose

Validate the AR6 regional-mean `tas` time series extracted by `cmip6_ar6.py`
(stored in `ar6_data/`) against the independent ATLAS precomputed regional
aggregates, for one reference model/member (AWI-CM-1-1-MR, historical,
r1i1p1f1), across all 58 AR6 WGI reference regions. Produces a per-region
table (bias, RMSE, correlation) and a 2-panel diagnostic figure.

## 2. Inputs

| File | Relevant columns / variables | Filters applied |
|------|------------------------------|------------------|
| ATLAS CSV (remote, `ATLAS_URL`): `CMIP6_AWI-CM-1-1-MR_historical_r1i1p1f1.csv` | one column per AR6 region abbrev (58 cols), monthly index | none — full record used (1850-01 to 2014-12, 1980 months, units degC) |
| `ar6_data/ar6_AWI_AWI-CM-1-1-MR_historical.nc` | `tas(member_id, time, region)`, coords `abbrevs`, `region` (int index) | `member_id == "r1i1p1f1"`; full time record (1851-01 to 2014-12, 1968 months, units K) |

`shared` = intersection of `ds.abbrevs` and ATLAS column names. Currently
58/58 (all AR6 regions present in both sources).

## 3. Outputs

| File | Contents | Format |
|------|----------|--------|
| stdout (captured to `run_test_ar6.log`) | Per-region table: Region, ATLAS (°C), Ours (°C), Diff, RMSE, Corr; summary lines (mean/max \|diff\|, mean/max RMSE, mean/min corr) | fixed-width text |
| `test_ar6_validation.pdf` | 2-panel figure: (left) scatter of climatological means, all shared regions, with 1:1 line and region labels; (right) 1980-1989 monthly anomaly time series for 4 example regions (ours solid colored vs ATLAS dashed black) | PDF, 150 dpi |
| `validation_ar6.md` | Hand-curated markdown copy of the table + summary + commentary | markdown — **not auto-generated; must be updated by hand from the stdout table after any code change** |

## 4. Algorithm

1. Load ATLAS CSV (`pd.read_csv`, comment lines stripped, date index parsed). Units already degC.
2. Load `ar6_AWI_AWI-CM-1-1-MR_historical.nc` with cftime decoding; select `member_id="r1i1p1f1"` → `our_r1(time, region)`, units K.
3. `shared` = AR6 abbrevs present as columns in the ATLAS CSV. `abbrev_to_region` maps abbrev → integer `region` index via `zip(ds.abbrevs, ds.region)`.
4. **Climatological means (bias / Diff):**
   - `atlas_means` = mean over ATLAS's full record (1850-2014, 1980 months).
   - `our_means` = mean over our full record (1851-2014, 1968 months) − 273.15 (K→°C).
   - `diffs = our_means − atlas_means` (this is the **bias**, reported as "Diff").
   - Note: the two means are computed over slightly different periods (ATLAS includes 1850, ours does not) — accepted as negligible (1 of ~165 years).
5. **RMSE and correlation (full monthly time series, aligned overlap):**
   - ATLAS starts 1850-01, ours starts 1851-01; both end 2014-12, monthly, continuous (verified: 1980 = 165×12 and 1968 = 164×12 rows — no gaps).
   - Take the **last `n_time = our_r1.sizes["time"]` (1968) rows** of `atlas[shared]` → aligns 1:1 with `our_r1`'s time axis (both now span 1851-01 to 2014-12).
   - Build two `(t, region)` xarray DataArrays (`atlas_ts`, `our_ts`) from the aligned arrays, with a synthetic integer `t` dim and shared `region` coord = `shared` abbrevs.
   - `RMSE = sqrt( mean_t( (our_ts − atlas_ts)^2 ) )`, per region.
   - `Corr = xr.corr(atlas_ts, our_ts, dim="t")` (Pearson), per region.
6. Print the per-region table and summary statistics (mean/max |diff|, mean/max RMSE, mean/min corr).
7. Build the 2-panel figure:
   - Left: scatter of `atlas_means` vs `our_means`, 1:1 line, per-region text labels, title shows N regions and mean |diff|.
   - Right: for `ts_regions = ["NEU","EAS","WAF","WNA"]`, plot 1980-1989 monthly anomalies (relative to the 10-yr mean) — ours as solid colored lines, ATLAS as dashed black lines overlaid.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| `ATLAS_URL` | AWI-CM-1-1-MR historical r1i1p1f1, `tas`, land-sea CSV (ATLAS `devel` branch) | Only ATLAS dataset matching the model/member/variable extracted by `cmip6_ar6.py`; the land-sea variant covers all 58 regions (land-only covers 46). |
| K→°C offset | 273.15 | Standard conversion; `our_r1` is in Kelvin, ATLAS is already in degC. |
| `n_time` alignment (drop ATLAS's first 12 months) | last 1968 of 1980 ATLAS rows | Both series are continuous monthly with no gaps and share the same end date (2014-12); dropping ATLAS's leading 1850 makes the two series the same length and 1:1 aligned by position. |
| `ts_regions = ["NEU","EAS","WAF","WNA"]` | — | Pre-existing choice for the example time-series panel; rationale not recorded. Illustrative only — does not feed into the quantitative Diff/RMSE/Corr table, which covers all 58 regions and the full record. |
| `YEAR0, YEAR1 = 1980, 1989` | example decade | Pre-existing choice; rationale not recorded. Illustrative only, same caveat as above. |

## 6. Edge Cases & Error Handling

- **Time alignment is positional, not label-based**: step 5 assumes both series are gap-free monthly records ending on the same month. This was verified by row-count arithmetic (165×12 and 164×12) for this specific model/member; it is **not re-checked at runtime**. If either source had missing months, the alignment would silently shift and RMSE/Corr would be wrong without any error.
- **`shared` could be < 58** if a different model/variable ATLAS CSV is substituted (e.g., land-only 46-region file). The stdout table and summary stats adapt automatically, but `validation_ar6.md` is hand-curated and must be re-synced manually.
- **Region ordering**: `atlas_ts`/`our_ts` columns are paired by construction — both are built by iterating `shared` in the same order, so no explicit join/sort is needed.
- **Correlation near-degenerate series**: `xr.corr` could be unstable for near-zero-variance series, but `tas` has a strong seasonal cycle in every region, so this does not arise in practice.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|--------------|
| 2026-06-12 | Added per-region RMSE and Pearson correlation (full monthly time series, 1851-2014 overlap); extended stdout table and `validation_ar6.md` with RMSE/Corr columns | Spec created (this file) |

## Verification Snippet

```python
import numpy as np, pandas as pd, xarray as xr
from pathlib import Path

AR6_DIR = Path("ar6_data")
ATLAS_URL = (
    "https://raw.githubusercontent.com/SantanderMetGroup/ATLAS/devel/"
    "datasets-aggregated-regionally/data/CMIP6/CMIP6_tas_landsea/"
    "CMIP6_AWI-CM-1-1-MR_historical_r1i1p1f1.csv"
)

atlas = pd.read_csv(ATLAS_URL, comment="#", index_col=0, parse_dates=True)
ds = xr.open_dataset(
    AR6_DIR / "ar6_AWI_AWI-CM-1-1-MR_historical.nc",
    decode_times=xr.coders.CFDatetimeCoder(use_cftime=True),
)
our_r1 = ds.tas.sel(member_id="r1i1p1f1")

our_abbrevs = list(ds.abbrevs.values)
shared = [a for a in our_abbrevs if a in atlas.columns]
abbrev_to_region = dict(zip(ds.abbrevs.values, ds.region.values))

assert len(shared) == 58, f"expected 58 shared regions, got {len(shared)}"

n_time = our_r1.sizes["time"]
assert n_time == 1968, f"expected 1968 months (164 yr), got {n_time}"
assert len(atlas) == 1980, f"expected 1980 ATLAS rows (165 yr), got {len(atlas)}"

atlas_ts = xr.DataArray(atlas[shared].iloc[-n_time:].values, dims=("t", "region"),
                         coords={"region": shared})
our_ts = xr.DataArray((our_r1.sel(region=[abbrev_to_region[a] for a in shared]) - 273.15).values,
                       dims=("t", "region"), coords={"region": shared})

rmse = np.sqrt(((our_ts - atlas_ts) ** 2).mean("t")).values
corr = xr.corr(atlas_ts, our_ts, dim="t").values

assert not np.isnan(rmse).any() and not np.isnan(corr).any()
assert (rmse >= 0).all()
assert ((corr >= -1) & (corr <= 1)).all()
assert corr.min() > 0.99, f"unexpectedly low correlation: {corr.min()}"
print("OK:", len(shared), "regions, mean RMSE", rmse.mean(), "min corr", corr.min())
```
