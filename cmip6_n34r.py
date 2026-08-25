#!/usr/bin/env python
"""Compute the relative Niño 3.4 index from CMIP6 on Google Cloud.

Relative Niño 3.4 = Niño 3.4 minus the tropical-mean (20°S-20°N, all
longitudes, ocean-only) surface temperature (van Oldenborgh et al. 2021;
L'Heureux, Tippett et al. 2024). Output is raw, unscaled K with no
climatology removed — the rescaling step in the published (RONI) recipe is
deliberately omitted so alternative scalings can be explored downstream.
See specs/cmip6_n34r.md for the full derivation and evidence.

Output: one NetCDF per model/experiment with n34, trop, n34r (member_id, time).
"""

from pathlib import Path
import argparse
import xarray as xr
import pandas as pd

from cmip6_utils import (
    REQUIRED_EXPERIMENTS, COMP,
    get_valid_pairs, open_member, append_run_summary,
    n34_average, ocean_mask, trop_average,
)

N34R_DIR = Path(__file__).parent / "n34r_data"
N34R_DIR.mkdir(exist_ok=True)


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
skipped_experiments = []
n_written = 0
n_existed = 0

for institution_id, source_id in zip(valid_pairs["institution_id"], valid_pairs["source_id"]):
    print()
    df_wrk = df_ts.query("institution_id == @institution_id & source_id == @source_id")
    exp_groups = {exp: grp for exp, grp in df_wrk.groupby("experiment_id")}

    for experiment_id in REQUIRED_EXPERIMENTS:
        print(f"Institution: {institution_id}, Source: {source_id}, Exp: {experiment_id}")
        n34r_list = []

        for _, row in exp_groups.get(experiment_id, df_wrk.iloc[0:0]).iterrows():
            member_id = row["member_id"]
            print(member_id, end=" ")

            ds = open_member(row["zstore"]).sortby("lat")

            # Built fresh per member, not cached across the model: different
            # members' zarr stores encode lat/lon independently and are not
            # bit-identical (observed ~1e-5 deg drift on EC-Earth3), so a
            # mask built from one member's coordinates silently misaligns
            # against another's when multiplied in trop_average, producing
            # all-NaN output rather than an error. Rebuilding costs ~50ms,
            # negligible next to the network read.
            ocean = ocean_mask(ds.lon, ds.lat)

            n34  = n34_average(ds.ts)
            trop = trop_average(ds.ts, ocean)
            n34.name, trop.name = "n34", "trop"

            # Single compute() call: both averages read the same lazy zarr
            # store, so computing them separately would stream it twice.
            computed = xr.Dataset({"n34": n34, "trop": trop}).compute()
            n34, trop = computed["n34"], computed["trop"]

            if n34.isnull().any() or trop.isnull().any():
                print("[DROPPED: missing data]", end=" ")
                dropped_members.append((institution_id, source_id, experiment_id, member_id))
                continue

            n34r = n34 - trop
            n34r.name = "n34r"

            member = xr.merge([n34, trop, n34r])
            member = member.assign_coords(member_id=member_id).expand_dims("member_id")
            n34r_list.append(member)

        if not n34r_list:
            print("\n  [SKIPPED: no members]")
            skipped_experiments.append((institution_id, source_id, experiment_id))
            continue

        ds_out = xr.merge(n34r_list)
        if "height" in ds_out.coords:
            ds_out = ds_out.drop_vars("height")

        ds_out["n34"].attrs["long_name"]  = "Niño 3.4 index"
        ds_out["n34"].attrs["units"]      = "K"
        ds_out["n34"].attrs["region"]     = "lon 190-240°E, lat 5°S-5°N"
        ds_out["n34"].attrs["weighting"]  = "cosine latitude"

        ds_out["trop"].attrs["long_name"] = "Tropical-mean surface temperature"
        ds_out["trop"].attrs["units"]     = "K"
        ds_out["trop"].attrs["region"]    = "lat 20°S-20°N, all longitudes, ocean only"
        ds_out["trop"].attrs["weighting"] = "cosine latitude, ocean mask"

        ds_out["n34r"].attrs["long_name"] = "Relative Niño 3.4 index (unscaled)"
        ds_out["n34r"].attrs["units"]     = "K"
        ds_out["n34r"].attrs["comment"]   = (
            "n34 - trop, raw temperatures, no climatology removed, no "
            "variance rescaling applied (see specs/cmip6_n34r.md)"
        )

        ds_out["experiment_id"]  = experiment_id
        ds_out["source_id"]      = source_id
        ds_out["institution_id"] = institution_id

        for v in ds_out.data_vars:
            ds_out[v].encoding.update(COMP)

        filename = N34R_DIR / f"n34r_{institution_id}_{source_id}_{experiment_id}.nc"
        if filename.exists():
            print("\n  [SKIP: file exists]")
            n_existed += 1
            continue
        print()
        print(filename)
        ds_out.to_netcdf(filename.with_suffix(".tmp"))
        filename.with_suffix(".tmp").rename(filename)
        n_written += 1

print("\n--- Dropped members (missing data) ---")
for item in dropped_members:
    print("  %s  %s  %s  %s" % item)
print(f"Total dropped: {len(dropped_members)}")

append_run_summary("cmip6_n34r.py", n_written, n_existed, dropped_members, skipped_experiments)
