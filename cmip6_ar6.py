#!/usr/bin/env python
"""Compute IPCC AR6 regional averages of tas (Amon) from CMIP6 on Google Cloud.

Output: one NetCDF per model/experiment with tas(member_id, region, time).
"""

from pathlib import Path
import argparse
import numpy as np
import xarray as xr
import regionmask
import pandas as pd

from cmip6_utils import (
    REQUIRED_EXPERIMENTS, COMP,
    get_valid_pairs, open_member,
)

AR6_DIR = Path(__file__).parent / "ar6_data"
AR6_DIR.mkdir(exist_ok=True)

ar6 = regionmask.defined_regions.ar6.land  # 46 AR6 WGI reference regions


def ar6_averages(tas, mask3d, lat_weights):
    """Latitude-weighted mean of tas over each AR6 region.

    tas:         DataArray (time, lat, lon)
    mask3d:      DataArray (region, lat, lon) boolean
    lat_weights: DataArray (lat,)
    Returns:     DataArray (time, region)
    """
    # Explicit chunks prevent dask auto-chunk failures on models with many time chunks
    mask_f = mask3d.astype(float).chunk({"region": -1, "lat": -1, "lon": -1})
    numerator   = xr.dot(tas * lat_weights, mask_f, dims=["lat", "lon"])
    denominator = (lat_weights * mask_f).sum(["lat", "lon"])
    return numerator / denominator


parser = argparse.ArgumentParser()
parser.add_argument("--institution", help="Restrict to one institution_id")
parser.add_argument("--source",      help="Restrict to one source_id")
args = parser.parse_args()

df = pd.read_csv("https://cmip6.storage.googleapis.com/pangeo-cmip6.csv")
print(f"Catalog rows: {len(df)}")

df_tas = df.query("variable_id == 'tas' & table_id == 'Amon'").copy()
valid_pairs = get_valid_pairs(df_tas)
if args.institution:
    valid_pairs = valid_pairs[valid_pairs["institution_id"] == args.institution]
if args.source:
    valid_pairs = valid_pairs[valid_pairs["source_id"] == args.source]
print(f"Models: {len(valid_pairs)}")

dropped_members = []

for institution_id, source_id in zip(valid_pairs["institution_id"], valid_pairs["source_id"]):
    print()
    df_wrk = df_tas.query("institution_id == @institution_id & source_id == @source_id")
    exp_groups = {exp: grp for exp, grp in df_wrk.groupby("experiment_id")}

    # mask and weights are the same for all members/experiments of a model
    mask3d      = None
    lat_weights = None

    for experiment_id in REQUIRED_EXPERIMENTS:
        print(f"Institution: {institution_id}, Source: {source_id}, Exp: {experiment_id}")
        member_list = []

        for _, row in exp_groups.get(experiment_id, df_wrk.iloc[0:0]).iterrows():
            member_id = row["member_id"]
            print(member_id, end=" ")

            ds = open_member(row["zstore"])

            if mask3d is None:
                mask3d      = ar6.mask_3D(ds.lon, ds.lat)
                lat_weights = xr.DataArray(np.cos(np.deg2rad(ds.lat)), dims=["lat"])

            ts_regional = ar6_averages(ds.tas, mask3d, lat_weights).compute()

            if ts_regional.isnull().any():
                print("[DROPPED: missing data]", end=" ")
                dropped_members.append((institution_id, source_id, experiment_id, member_id))
                continue

            ts_regional = ts_regional.assign_coords(member_id=member_id).expand_dims("member_id")
            member_list.append(ts_regional)

        if not member_list:
            print("\n  [SKIPPED: no members]")
            continue

        ds_out = xr.concat(member_list, dim="member_id").to_dataset(name="tas")
        ds_out["experiment_id"]  = experiment_id
        ds_out["source_id"]      = source_id
        ds_out["institution_id"] = institution_id

        ds_out.encoding.update(COMP)
        filename = AR6_DIR / f"ar6_{institution_id}_{source_id}_{experiment_id}.nc"
        if filename.exists():
            print("\n  [SKIP: file exists]")
            continue
        print()
        print(filename)
        ds_out.to_netcdf(filename.with_suffix(".tmp"))
        filename.with_suffix(".tmp").rename(filename)

print("\n--- Dropped members (missing data) ---")
for item in dropped_members:
    print("  %s  %s  %s  %s" % item)
print(f"Total dropped: {len(dropped_members)}")
