"""Shared utilities for CMIP6 download scripts."""

import subprocess
from datetime import date
from pathlib import Path
import numpy as np
import xarray as xr
import cftime
import pandas as pd


REQUIRED_EXPERIMENTS = [
    "historical", "ssp245", "ssp585", "ssp370", "ssp126",
    "abrupt-4xCO2", "piControl", "1pctCO2",
]
EXCLUDED_INSTITUTIONS = ["NIMS-KMA"]
STORAGE_OPTIONS = {"token": "anon"}
COMP = dict(zlib=True)

# Niño 3.4 box: 190-240°E (170°W-120°W), 5°S-5°N.
N34_LAT = slice(-5, 5)
N34_LON = slice(190, 240)
# Tropical-mean band for the relative Niño 3.4 index: 20°S-20°N, all longitudes.
TROP_LAT = slice(-20, 20)


def convert_to_cftime_no_leap(ds):
    if "time" not in ds.coords:
        raise ValueError("Dataset does not have a 'time' coordinate.")
    time = ds.time.values
    if isinstance(time[0], (np.datetime64, pd.Timestamp)):
        converted = [cftime.DatetimeNoLeap(t.year, t.month, 15) for t in pd.to_datetime(time)]
    elif isinstance(time[0], cftime.datetime):
        converted = [cftime.DatetimeNoLeap(t.year, t.month, 15) for t in time]
    else:
        raise TypeError(f"Unsupported time format: {type(time[0])}")
    return ds.assign_coords(time=("time", converted))


def standardize_lonlat(ds):
    rename = {}
    if "latitude" in ds.dims:
        rename["latitude"] = "lat"
    if "longitude" in ds.dims:
        rename["longitude"] = "lon"
    return ds.rename(rename) if rename else ds


def get_valid_pairs(df_var):
    """Return (institution_id, source_id) pairs that have all required experiments in df_var."""
    filtered = df_var[df_var["experiment_id"].isin(REQUIRED_EXPERIMENTS)]
    valid = (
        filtered.groupby(["institution_id", "source_id"])["experiment_id"]
        .apply(lambda x: set(REQUIRED_EXPERIMENTS).issubset(set(x)))
        .reset_index()
    )
    valid = valid[valid["experiment_id"]].drop(columns=["experiment_id"])
    return valid[~valid["institution_id"].isin(EXCLUDED_INSTITUTIONS)]


def append_run_summary(script_name, n_written, n_existed,
                       dropped_members, skipped_experiments):
    """Prepend a run summary entry to NOTES.md (after the header)."""
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except (subprocess.CalledProcessError, OSError):
        git_hash = "unknown"

    lines = [
        f"## {date.today()} — {script_name}",
        f"- Git: {git_hash}  |  Written: {n_written}  |  Skipped (existed): {n_existed}",
        f"- Dropped (NaN): {', '.join(f'{i} {s} {e} {m}' for i,s,e,m in dropped_members) or '0'}",
        f"- No members: {', '.join(f'{i} {s} {e}' for i,s,e in skipped_experiments) or '0'}",
    ]

    entry = "\n".join(lines) + "\n\n"
    header = "# Project Notes\n\n"
    notes_path = Path(__file__).parent / "NOTES.md"
    if notes_path.exists():
        content = notes_path.read_text()
        if content.startswith(header):
            notes_path.write_text(header + entry + content[len(header):])
        else:
            notes_path.write_text(content + entry)
    else:
        notes_path.write_text(header + entry)


def open_member(zstore_path):
    """Open a CMIP6 zarr store with standard settings."""
    ds = xr.open_zarr(
        zstore_path, storage_options=STORAGE_OPTIONS, consolidated=True,
        decode_times=xr.coders.CFDatetimeCoder(use_cftime=True),
    )
    if not ds.indexes["time"].is_monotonic_increasing:
        ds = ds.sortby("time")
    ds = convert_to_cftime_no_leap(ds)
    return standardize_lonlat(ds)


def n34_average(x):
    """Cosine-latitude-weighted mean over the Niño 3.4 box (190-240°E, 5°S-5°N).

    Unmasked: the Niño 3.4 box is 100% ocean on every model grid checked, so a
    land mask would be a no-op here (unlike trop_average, which needs one).
    """
    x = x.sortby("lat")
    weights = np.cos(np.deg2rad(x.lat))
    y = x.sel(lon=N34_LON).sel(lat=N34_LAT).weighted(weights).mean(["lon", "lat"])
    y.attrs = x.attrs.copy()
    return y


def ocean_mask(lon, lat):
    """Boolean ocean mask (True = ocean) for a rectilinear lon/lat grid.

    Built from the Natural Earth 1:110m land polygons via regionmask. Coastal
    cells are assigned all-or-nothing (no fractional land weighting) — measured
    against sftlf-fractional weighting and real tos on 7 rectilinear-grid CMIP6
    models, the two differ by <0.001 K in the resulting relative index (see
    specs/cmip6_n34r.md §5), so the added complexity of fractional weighting
    is not justified.
    """
    import regionmask
    land = regionmask.defined_regions.natural_earth_v5_0_0.land_110
    return land.mask(lon, lat).isnull()


def trop_average(x, ocean):
    """Cosine-latitude-weighted, ocean-masked mean over 20°S-20°N, all longitudes.

    x:     DataArray (..., lat, lon), sorted ascending by lat.
    ocean: boolean DataArray (lat, lon), True = ocean (see ocean_mask), on the
           same grid as x, already sorted to match.
    """
    weights = np.cos(np.deg2rad(x.lat)) * ocean
    y = x.sel(lat=TROP_LAT).weighted(weights.sel(lat=TROP_LAT)).mean(["lon", "lat"])
    y.attrs = x.attrs.copy()
    return y
