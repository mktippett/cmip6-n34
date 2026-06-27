#!/usr/bin/env python
"""Compute Niño 3.4 index from CESM2 Large Ensemble (LENS2) on AWS S3.

Variable: TS (surface radiative temperature), Amon, same role as CMIP6 ts.
Output: one NetCDF per (forcing_variant, experiment) with n34(member_id, time).

Output directory: lens2_n34_data/
File naming: n34_CESM2-LE_{variant}_{experiment}.nc

Forcing variants:
  cmip6 — standard CMIP6 biomass burning (50 members, p1f1)
  smbb  — smoothed biomass burning (50 members, p1f2)

Experiments: historical (1850–2014), ssp370 (2015–2100).
"""

from pathlib import Path
import argparse
import numpy as np
import xarray as xr

from lens2_utils import (
    EXPERIMENTS, FORCING_VARIANTS, COMP,
    open_lens2, append_run_summary,
)

N34_DIR = Path(__file__).parent / "lens2_n34_data"
N34_DIR.mkdir(exist_ok=True)


def n34_average(x: xr.DataArray) -> xr.DataArray:
    """Cosine-latitude-weighted mean over the Niño 3.4 box (190–240°E, 5°S–5°N).

    Identical to cmip6_n34.py:n34_average; lon in 0–360 convention.
    """
    x = x.sortby("lat")
    weights = np.cos(np.deg2rad(x.lat))
    y = (
        x.sel(lon=slice(190, 240))
         .sel(lat=slice(-5, 5))
         .weighted(weights)
         .mean(["lon", "lat"])
    )
    y.attrs = x.attrs.copy()
    return y


def main():
    parser = argparse.ArgumentParser(description="Compute LENS2 Niño 3.4 index.")
    parser.add_argument("--variant",    choices=FORCING_VARIANTS,
                        help="Restrict to one forcing variant (cmip6 or smbb)")
    parser.add_argument("--experiment", choices=EXPERIMENTS,
                        help="Restrict to one experiment (historical or ssp370)")
    args = parser.parse_args()

    variants    = [args.variant]    if args.variant    else FORCING_VARIANTS
    experiments = [args.experiment] if args.experiment else EXPERIMENTS

    dropped_members = []   # (variant, experiment, member_id) — NaN drops
    skipped_stores  = []   # (variant, experiment) — zero valid members
    n_written  = 0
    n_existed  = 0

    for variant in variants:
        for experiment in experiments:
            print(f"\n=== variant={variant}  experiment={experiment} ===")

            filename = N34_DIR / f"n34_CESM2-LE_{variant}_{experiment}.nc"
            if filename.exists():
                print(f"  [SKIP: {filename.name} exists]")
                n_existed += 1
                continue

            ds = open_lens2("TS", experiment, variant)
            member_ids = list(ds.member_id.values)
            print(f"  {len(member_ids)} members  |  time: {ds.sizes['time']} steps")

            n34_list = []
            for member_id in member_ids:
                print(f"    {member_id}", end=" ", flush=True)

                n34 = n34_average(ds.TS.sel(member_id=member_id))
                n34.name = "n34"
                n34 = n34.compute()

                if n34.isnull().any():
                    print("[DROPPED: missing data]", end="")
                    dropped_members.append((variant, experiment, member_id))
                    print()
                    continue

                n34 = n34.assign_coords(member_id=member_id).expand_dims("member_id")
                n34_list.append(n34)
                print()

            if not n34_list:
                print("  [SKIPPED: no valid members]")
                skipped_stores.append((variant, experiment))
                continue

            ds_out = xr.merge(n34_list)
            ds_out["n34"].attrs["long_name"] = "Niño 3.4 index"
            ds_out["n34"].attrs["units"]     = "K"
            ds_out["n34"].attrs["source_variable"] = "TS"
            ds_out["n34"].attrs["region"]    = "lon 190–240°E, lat 5°S–5°N"
            ds_out["n34"].attrs["weighting"] = "cosine latitude"
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

    # Pack into 4-tuple / 3-tuple format expected by append_run_summary
    dropped_4 = [("CESM2-LE", v, e, m) for v, e, m in dropped_members]
    skipped_3 = [("CESM2-LE", v, e) for v, e in skipped_stores]
    append_run_summary("lens2_n34.py", n_written, n_existed, dropped_4, skipped_3)


if __name__ == "__main__":
    main()
