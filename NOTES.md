# Project Notes

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

