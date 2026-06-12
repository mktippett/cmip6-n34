# Project Notes

## 2026-06-12 — AR6 validation: add RMSE and correlation
- `test_ar6.py` now computes RMSE and Pearson correlation per region from the full
  monthly time series (1851-2014 overlap), in addition to the climatological-mean
  Diff (bias)
- Mean RMSE = 0.113 °C (max 0.631 °C, EAN)  |  Mean corr = 0.9999 (min 0.9987, SEAF)
- RMSE tracks Diff closely everywhere — confirms differences are dominated by a
  steady mean offset, not timing/variability mismatches
- Updated `validation_ar6.md` and `run_test_ar6.log`

## 2026-06-11 — AR6 validation vs ATLAS (58 regions)
- Mean |diff|: 0.097 °C  |  Max |diff|: 0.618 °C (EAN — East Antarctica)
- All 58 AR6 regions (46 land + 12 ocean) now validated; ocean regions all within 0.17 °C
- `ar6_data_46region_backup/` no longer needed — can be removed once confirmed
- Full table and time series plot: `validation_ar6.md`, `test_ar6_validation.pdf`

## 2026-06-11 — cmip6_ar6.py
- Git: c79495d  |  Written: 264  |  Skipped (existed): 8
- Dropped (NaN): 0
- No members: 0

## 2026-06-11 — code changes
- AR6 regions: switched `cmip6_ar6.py` from `regionmask.defined_regions.ar6.land` (46 land regions) to `regionmask.defined_regions.ar6.all` (58 regions = 46 land + 12 ocean)
- `tas` is global (2m air temp), so ocean regions are fully populated — no new NaN drops
- Old 46-region `ar6_data/` (272 files) backed up to `ar6_data_46region_backup/`; spot-checked AWI-CM-1-1-MR (8 files, region size 58, ocean abbrevs present, 0 NaN); full 272-file regeneration in progress
- README updated to reflect 58 regions (46 land + 12 ocean)

## 2026-06-11 — cmip6_ar6.py
- Git: c79495d  |  Written: 0  |  Skipped (existed): 8
- Dropped (NaN): 0
- No members: 0

## 2026-06-11 — cmip6_ar6.py
- Git: c79495d  |  Written: 8  |  Skipped (existed): 0
- Dropped (NaN): 0
- No members: 0

## 2026-05-19 — AR6 validation vs ATLAS (AWI-CM-1-1-MR historical r1i1p1f1)
- Mean |diff|: 0.107 °C  |  Max |diff|: 0.618 °C (EAN — East Antarctica)
- Full table and time series plot: `validation_ar6.md`, `test_ar6_validation.pdf`

## 2026-05-19 — QC check (n34)
- 248 files, 0 flags (range 250–315 K, std > 0.1 K)

## 2026-05-19 — code changes
- Fixed EC-Earth3 dask ZeroDivisionError: explicitly chunk mask3d before xr.dot
- Added --institution/--source CLI args to both download scripts for targeted reruns
- Added restart logic: skip existing files, atomic write via .tmp rename
- Added NOTES.md auto-append at end of each run (written, skipped, dropped, no-members)
- Shared utilities extracted to cmip6_utils.py (convert_to_cftime_no_leap, standardize_lonlat, get_valid_pairs, open_member, append_run_summary)
- AR6: switched from ts → tas; validated against ATLAS (mean |diff| 0.107 °C)
- GitHub repo created: https://github.com/mktippett/cmip6-n34

## 2026-05-19 — cmip6_ar6.py
- Git: 149afd1  |  Written: 272  |  Skipped (existed): 0
- Dropped (NaN): 0
- No members: 0

## 2026-05-19 — cmip6_n34.py
- Git: 149afd1  |  Written: 248  |  Skipped (existed): 0
- Dropped (NaN): 0
- No members: 0

