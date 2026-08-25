#!/usr/bin/env python
"""Compute the relative Niño 3.4 index from CESM2 Large Ensemble (LENS2) on AWS S3.

Variable: TS (surface radiative temperature), Amon, same role as CMIP6 ts.
Relative Niño 3.4 = Niño 3.4 minus the tropical-mean (20°S-20°N, all
longitudes, ocean-only) surface temperature. Output is raw, unscaled K with
no climatology removed — see specs/lens2_n34r.md and specs/cmip6_n34r.md for
the full derivation. Directly analogous to lens2_n34.py; only the box-average
step is extended with a tropical-mean term.

Output: one NetCDF per (forcing_variant, experiment) with
n34, trop, n34r(member_id, time).

Output directory: lens2_n34r_data/
File naming: n34r_CESM2-LE_{variant}_{experiment}.nc

Forcing variants:
  cmip6 — standard CMIP6 biomass burning (50 members, p1f1)
  smbb  — smoothed biomass burning (50 members, p1f2)

Experiments: historical (1850-2014), ssp370 (2015-2100).
"""

from pathlib import Path
import argparse
import xarray as xr

from lens2_utils import (
    EXPERIMENTS, FORCING_VARIANTS, COMP,
    open_lens2, append_run_summary,
    n34_average, ocean_mask, trop_average,
)

N34R_DIR = Path(__file__).parent / "lens2_n34r_data"
N34R_DIR.mkdir(exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Compute LENS2 relative Niño 3.4 index.")
    parser.add_argument("--variant",    choices=FORCING_VARIANTS,
                        help="Restrict to one forcing variant (cmip6 or smbb)")
    parser.add_argument("--experiment", choices=EXPERIMENTS,
                        help="Restrict to one experiment (historical or ssp370)")
    args = parser.parse_args()

    variants    = [args.variant]    if args.variant    else FORCING_VARIANTS
    experiments = [args.experiment] if args.experiment else EXPERIMENTS

    # Grid is identical across all four LENS2 stores; build the ocean mask once.
    ocean = None

    dropped_members = []   # (variant, experiment, member_id) — NaN drops
    skipped_stores  = []   # (variant, experiment) — zero valid members
    n_written  = 0
    n_existed  = 0

    for variant in variants:
        for experiment in experiments:
            print(f"\n=== variant={variant}  experiment={experiment} ===")

            filename = N34R_DIR / f"n34r_CESM2-LE_{variant}_{experiment}.nc"
            if filename.exists():
                print(f"  [SKIP: {filename.name} exists]")
                n_existed += 1
                continue

            ds = open_lens2("TS", experiment, variant).sortby("lat")
            member_ids = list(ds.member_id.values)
            print(f"  {len(member_ids)} members  |  time: {ds.sizes['time']} steps")

            if ocean is None:
                ocean = ocean_mask(ds.lon, ds.lat)
                print(f"  Built ocean mask: {ocean.sizes}")

            n34r_list = []
            for member_id in member_ids:
                print(f"    {member_id}", end=" ", flush=True)

                ts_mem = ds.TS.sel(member_id=member_id)
                n34  = n34_average(ts_mem)
                trop = trop_average(ts_mem, ocean)
                n34.name, trop.name = "n34", "trop"

                # Single compute() call: both averages read the same lazy
                # zarr store, so computing separately would stream it twice.
                computed = xr.Dataset({"n34": n34, "trop": trop}).compute()
                n34, trop = computed["n34"], computed["trop"]

                if n34.isnull().any() or trop.isnull().any():
                    print("[DROPPED: missing data]", end="")
                    dropped_members.append((variant, experiment, member_id))
                    print()
                    continue

                n34r = n34 - trop
                n34r.name = "n34r"

                member = xr.merge([n34, trop, n34r])
                member = member.assign_coords(member_id=member_id).expand_dims("member_id")
                n34r_list.append(member)
                print()

            if not n34r_list:
                print("  [SKIPPED: no valid members]")
                skipped_stores.append((variant, experiment))
                continue

            ds_out = xr.merge(n34r_list)

            ds_out["n34"].attrs["long_name"]  = "Niño 3.4 index"
            ds_out["n34"].attrs["units"]      = "K"
            ds_out["n34"].attrs["source_variable"] = "TS"
            ds_out["n34"].attrs["region"]     = "lon 190-240°E, lat 5°S-5°N"
            ds_out["n34"].attrs["weighting"]  = "cosine latitude"

            ds_out["trop"].attrs["long_name"] = "Tropical-mean surface temperature"
            ds_out["trop"].attrs["units"]     = "K"
            ds_out["trop"].attrs["source_variable"] = "TS"
            ds_out["trop"].attrs["region"]    = "lat 20°S-20°N, all longitudes, ocean only"
            ds_out["trop"].attrs["weighting"] = "cosine latitude, ocean mask"

            ds_out["n34r"].attrs["long_name"] = "Relative Niño 3.4 index (unscaled)"
            ds_out["n34r"].attrs["units"]     = "K"
            ds_out["n34r"].attrs["comment"]   = (
                "n34 - trop, raw temperatures, no climatology removed, no "
                "variance rescaling applied (see specs/lens2_n34r.md)"
            )

            ds_out["forcing_variant"] = variant
            ds_out["experiment"]      = experiment
            ds_out["source_id"]       = "CESM2-LE"

            for v in ds_out.data_vars:
                ds_out[v].encoding.update(COMP)

            print(f"  → writing {filename.name}")
            ds_out.to_netcdf(filename.with_suffix(".tmp"))
            filename.with_suffix(".tmp").rename(filename)
            n_written += 1

    print("\n--- Dropped members (missing data) ---")
    for item in dropped_members:
        print("  variant=%s  experiment=%s  member=%s" % item)
    print(f"Total dropped: {len(dropped_members)}")

    dropped_4 = [("CESM2-LE", v, e, m) for v, e, m in dropped_members]
    skipped_3 = [("CESM2-LE", v, e) for v, e in skipped_stores]
    append_run_summary("lens2_n34r.py", n_written, n_existed, dropped_4, skipped_3)


if __name__ == "__main__":
    main()
