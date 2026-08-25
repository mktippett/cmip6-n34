"""Shared utilities for CESM2 Large Ensemble (LENS2) download scripts.

Data lives on AWS S3 (us-west-2) as anonymous-read Zarr stores:
  s3://ncar-cesm2-lens/atm/monthly/cesm2LE-{experiment}-{forcing_variant}-{variable}.zarr

Two forcing variants (separate stores, 50 members each):
  cmip6 — standard CMIP6 biomass burning emissions (members 1–50)
  smbb  — smoothed biomass burning, 11-yr running mean 1990–2020 (members 51–100)

Two experiments:
  historical — 1850-01 to 2014-12  (1980 monthly steps)
  ssp370     — 2015-01 to 2100-12  (1032 monthly steps)

Calendar: noleap (already the native CESM2 calendar; no conversion needed).
Grid: 192 lat × 288 lon, lat −90 to 90, lon 0 to 358.75°E (0–360 convention).
"""

import xarray as xr

# Re-export from cmip6_utils to keep the lens2 scripts self-contained
from cmip6_utils import (  # noqa: F401
    COMP, append_run_summary,
    N34_LAT, N34_LON, TROP_LAT,
    n34_average, ocean_mask, trop_average,
)

S3_BUCKET        = "ncar-cesm2-lens"
S3_STORAGE_OPTIONS = {"anon": True}

EXPERIMENTS      = ["historical", "ssp370"]
FORCING_VARIANTS = ["cmip6", "smbb"]


def store_url(variable: str, experiment: str, variant: str) -> str:
    """Return the S3 zarr URL for a given variable/experiment/forcing_variant."""
    return (
        f"s3://{S3_BUCKET}/atm/monthly/"
        f"cesm2LE-{experiment}-{variant}-{variable}.zarr"
    )


def open_lens2(variable: str, experiment: str, variant: str) -> xr.Dataset:
    """Open a CESM2-LE zarr store from S3 anonymously.

    Returns a lazy Dataset with dimensions (member_id, time, lat, lon).
    The noleap calendar is kept as-is (no conversion applied).
    """
    url = store_url(variable, experiment, variant)
    ds = xr.open_zarr(url, storage_options=S3_STORAGE_OPTIONS, consolidated=True)
    if not ds.indexes["time"].is_monotonic_increasing:
        ds = ds.sortby("time")
    return ds
