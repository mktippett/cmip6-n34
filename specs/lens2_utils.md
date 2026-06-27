# Spec: lens2_utils.py

## 1. Purpose

Shared constants and utilities for the CESM2 Large Ensemble (LENS2) download
scripts (`lens2_n34.py`, `lens2_ar6.py`). Provides the S3 data-access layer —
analogous to `cmip6_utils.py` for the CMIP6 pipeline — and re-exports `COMP`
and `append_run_summary` from `cmip6_utils` to keep the LENS2 scripts
self-contained.

## 2. Inputs

None (module-level constants and helpers only).

## 3. Outputs

None (module-level constants and helpers only).

## 4. API

| Symbol | Type | Description |
|--------|------|-------------|
| `S3_BUCKET` | `str` | `"ncar-cesm2-lens"` — AWS S3 bucket (us-west-2, anonymous read) |
| `S3_STORAGE_OPTIONS` | `dict` | `{"anon": True}` — passed to `xr.open_zarr(storage_options=...)` |
| `EXPERIMENTS` | `list[str]` | `["historical", "ssp370"]` — the only two experiments in LENS2 |
| `FORCING_VARIANTS` | `list[str]` | `["cmip6", "smbb"]` — standard vs. smoothed biomass burning |
| `store_url(variable, experiment, variant)` | `str` | Builds the S3 zarr URL; see §4 Algorithm |
| `open_lens2(variable, experiment, variant)` | `xr.Dataset` | Opens a LENS2 zarr store; see §4 Algorithm |
| `COMP` | `dict` | Re-exported from `cmip6_utils`; `{"zlib": True}` for NetCDF compression |
| `append_run_summary(...)` | fn | Re-exported from `cmip6_utils`; prepends a run entry to `NOTES.md` |

## 5. Algorithm

### `store_url(variable, experiment, variant)`

Returns:
```
s3://ncar-cesm2-lens/atm/monthly/cesm2LE-{experiment}-{variant}-{variable}.zarr
```

### `open_lens2(variable, experiment, variant)`

1. Calls `store_url` to build the S3 URL.
2. `xr.open_zarr(url, storage_options={"anon": True}, consolidated=True)` — anonymous
   S3 read; returns a lazy Dataset with dims `(member_id, time, lat, lon)`.
3. If `ds.indexes["time"].is_monotonic_increasing` is False, applies `sortby("time")`.
4. Returns the Dataset as-is (native `noleap` calendar, 0–360° lon — no
   calendar conversion or lon renaming needed for CESM2).

## 6. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| `S3_BUCKET` | `ncar-cesm2-lens` | AWS S3 bucket for CESM2-LE; us-west-2; openly accessible (CC-BY-4.0). |
| `S3_STORAGE_OPTIONS` | `{"anon": True}` | s3fs anonymous credential mode; no AWS keys required for this public dataset. |
| `EXPERIMENTS` | `["historical", "ssp370"]` | LENS2 has exactly these two experiments (1850–2014 and 2015–2100). ssp370 is the only future scenario; confirmed from the NCAR AWS catalog. |
| `FORCING_VARIANTS` | `["cmip6", "smbb"]` | Two 50-member sets in separate zarr stores. `cmip6` uses standard CMIP6 biomass burning; `smbb` applies an 11-year running mean to 1990–2020 fluxes (smoothed biomass burning). Separate stores → separate output files by design. |
| Calendar | native `noleap` | All CESM2 output uses the `noleap` calendar natively. Unlike CMIP6 (many source calendars), no conversion is needed here. |
| Lon convention | 0–360°E | CESM2 FV grid; Niño 3.4 `sel(lon=slice(190,240))` applies directly. |
| `COMP` / `append_run_summary` | imported from `cmip6_utils` | Avoids duplication; both scripts are co-located in the same directory. |

## 7. Edge Cases

- Requires `s3fs` to be installed in the active Python environment. `xr.open_zarr`
  dispatches to `s3fs` for `s3://` URLs via the `fsspec` registry. If `s3fs` is
  absent, an `ImportError` is raised at open time (not at import of this module).
- The `consolidated=True` flag requires that the zarr store has a consolidated
  `.zmetadata` file. CESM2-LE on AWS includes this; do not open without it
  (would scan all key prefixes individually, very slow on S3).
- `sortby("time")` is a safety check; CESM2-LE stores have monotonic time in
  practice, so this is a no-op.

## Synchronization Log

| Date | Change | Spec updated |
|------|--------|-------------|
| 2026-06-26 | Module created | Spec created (reflects initial code) |
