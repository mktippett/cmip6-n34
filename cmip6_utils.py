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


def append_run_summary(notes_path, script_name, n_written, n_existed,
                       dropped_members, skipped_experiments):
    """Prepend a run summary entry to NOTES.md (after the header)."""
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).parent, stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        git_hash = "unknown"

    lines = [
        f"## {date.today()} — {script_name}",
        f"- Git: {git_hash}  |  Written: {n_written}  |  Skipped (existed): {n_existed}",
    ]
    if dropped_members:
        lines.append(f"- Dropped (NaN): " + ", ".join(
            f"{inst} {src} {exp} {mem}" for inst, src, exp, mem in dropped_members
        ))
    else:
        lines.append("- Dropped (NaN): 0")
    if skipped_experiments:
        lines.append(f"- No members: " + ", ".join(
            f"{inst} {src} {exp}" for inst, src, exp in skipped_experiments
        ))
    else:
        lines.append("- No members: 0")

    entry = "\n".join(lines) + "\n\n"
    header = "# Project Notes\n\n"
    notes_path = Path(notes_path)
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
