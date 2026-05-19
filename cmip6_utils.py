"""Shared utilities for CMIP6 download scripts."""

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
