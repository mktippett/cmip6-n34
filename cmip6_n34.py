#!/usr/bin/env python
# coding: utf-8
# CMIP6 in cloud recipe — Nino 3.4
# From https://tutorial.xarray.dev/intermediate/remote_data/cmip6-cloud.html

from pathlib import Path
import argparse
import numpy as np
import xarray as xr
import pandas as pd

from cmip6_utils import (
    REQUIRED_EXPERIMENTS, COMP,
    get_valid_pairs, open_member,
)

N34_DIR = Path(__file__).parent / "n34_data"
N34_DIR.mkdir(exist_ok=True)


def n34_average(x):
    x = x.sortby("lat")
    weights = np.cos(np.deg2rad(x.lat))
    y = x.sel(lon=slice(190, 240)).sel(lat=slice(-5, 5)).weighted(weights).mean(["lon", "lat"])
    y.attrs = x.attrs.copy()
    return y


parser = argparse.ArgumentParser()
parser.add_argument("--institution", help="Restrict to one institution_id")
parser.add_argument("--source",      help="Restrict to one source_id")
args = parser.parse_args()

df = pd.read_csv("https://cmip6.storage.googleapis.com/pangeo-cmip6.csv")
print(f"Catalog rows: {len(df)}")

df_ts = df.query("variable_id == 'ts' & table_id == 'Amon'").copy()
valid_pairs = get_valid_pairs(df_ts)
if args.institution:
    valid_pairs = valid_pairs[valid_pairs["institution_id"] == args.institution]
if args.source:
    valid_pairs = valid_pairs[valid_pairs["source_id"] == args.source]
print(f"Models: {len(valid_pairs)}")

dropped_members = []

for institution_id, source_id in zip(valid_pairs["institution_id"], valid_pairs["source_id"]):
    print()
    df_wrk = df_ts.query("institution_id == @institution_id & source_id == @source_id")
    exp_groups = {exp: grp for exp, grp in df_wrk.groupby("experiment_id")}

    for experiment_id in REQUIRED_EXPERIMENTS:
        print(f"Institution: {institution_id}, Source: {source_id}, Exp: {experiment_id}")
        n34_list = []

        for _, row in exp_groups.get(experiment_id, df_wrk.iloc[0:0]).iterrows():
            member_id = row["member_id"]
            print(member_id, end=" ")

            ds = open_member(row["zstore"])

            n34 = n34_average(ds.ts)
            n34.name = "n34"
            n34 = n34.compute()

            if n34.isnull().any():
                print("[DROPPED: missing data]", end=" ")
                dropped_members.append((institution_id, source_id, experiment_id, member_id))
                continue

            n34 = n34.assign_coords(member_id=member_id).expand_dims("member_id")
            n34_list.append(n34)

        if not n34_list:
            print("\n  [SKIPPED: no members]")
            continue

        ds_out = xr.merge(n34_list)
        if "height" in ds_out.coords:
            ds_out = ds_out.drop_vars("height")
        ds_out["experiment_id"]  = experiment_id
        ds_out["source_id"]      = source_id
        ds_out["institution_id"] = institution_id

        ds_out.encoding.update(COMP)
        filename = N34_DIR / f"n34_{institution_id}_{source_id}_{experiment_id}.nc"
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
