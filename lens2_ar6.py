#!/usr/bin/env python
"""Compute IPCC AR6 regional averages from CESM2 Large Ensemble (LENS2) on AWS S3.

Variable: TREFHT (reference-height temperature, 2 m), Amon.
Same role as CMIP6 tas; used to match ATLAS precomputed regional averages.
Output: one NetCDF per (forcing_variant, experiment) with tas(member_id, time, region).

Output directory: lens2_ar6_data/
File naming: ar6_CESM2-LE_{variant}_{experiment}.nc

58 AR6 WGI reference regions: 46 land + 12 ocean
(regionmask.defined_regions.ar6.all)

Forcing variants:
  cmip6 — standard CMIP6 biomass burning (50 members, p1f1)
  smbb  — smoothed biomass burning (50 members, p1f2)

Experiments: historical (1850–2014), ssp370 (2015–2100).
"""

from pathlib import Path
import argparse
import numpy as np
import xarray as xr
import regionmask

from lens2_utils import (
    EXPERIMENTS, FORCING_VARIANTS, COMP,
    open_lens2, append_run_summary,
)

AR6_DIR = Path(__file__).parent / "lens2_ar6_data"
AR6_DIR.mkdir(exist_ok=True)

ar6 = regionmask.defined_regions.ar6.all  # 58 AR6 WGI reference regions


def ar6_averages(
    trefht: xr.DataArray,
    mask3d: xr.DataArray,
    lat_weights: xr.DataArray,
) -> xr.DataArray:
    """Latitude-weighted mean of TREFHT over each AR6 region.

    trefht:      DataArray (time, lat, lon)
    mask3d:      DataArray (region, lat, lon) boolean
    lat_weights: DataArray (lat,)
    Returns:     DataArray (time, region)

    The explicit rechunk on mask_f prevents a dask auto-chunk ZeroDivisionError
    on large time-chunked stores (identical fix as in cmip6_ar6.py).
    """
    mask_f = mask3d.astype(float).chunk({"region": -1, "lat": -1, "lon": -1})
    numerator   = xr.dot(trefht * lat_weights, mask_f, dims=["lat", "lon"])
    denominator = (lat_weights * mask_f).sum(["lat", "lon"])
    return numerator / denominator


def main():
    parser = argparse.ArgumentParser(description="Compute LENS2 AR6 regional averages.")
    parser.add_argument("--variant",    choices=FORCING_VARIANTS,
                        help="Restrict to one forcing variant (cmip6 or smbb)")
    parser.add_argument("--experiment", choices=EXPERIMENTS,
                        help="Restrict to one experiment (historical or ssp370)")
    args = parser.parse_args()

    variants    = [args.variant]    if args.variant    else FORCING_VARIANTS
    experiments = [args.experiment] if args.experiment else EXPERIMENTS

    # mask3d and lat_weights are identical for all CESM2-LE stores (same 192×288 grid).
    # Build once on first open, reuse for all subsequent stores.
    mask3d      = None
    lat_weights = None

    dropped_members = []   # (variant, experiment, member_id) — NaN drops
    skipped_stores  = []   # (variant, experiment) — zero valid members
    n_written  = 0
    n_existed  = 0

    for variant in variants:
        for experiment in experiments:
            print(f"\n=== variant={variant}  experiment={experiment} ===")

            filename = AR6_DIR / f"ar6_CESM2-LE_{variant}_{experiment}.nc"
            if filename.exists():
                print(f"  [SKIP: {filename.name} exists]")
                n_existed += 1
                continue

            ds = open_lens2("TREFHT", experiment, variant)
            member_ids = list(ds.member_id.values)
            print(f"  {len(member_ids)} members  |  time: {ds.sizes['time']} steps")

            if mask3d is None:
                mask3d      = ar6.mask_3D(ds.lon, ds.lat)
                lat_weights = xr.DataArray(np.cos(np.deg2rad(ds.lat)), dims=["lat"])
                print(f"  Built mask3d: {mask3d.sizes}")

            member_list = []
            for member_id in member_ids:
                print(f"    {member_id}", end=" ", flush=True)

                regional = ar6_averages(
                    ds.TREFHT.sel(member_id=member_id),
                    mask3d,
                    lat_weights,
                ).compute()

                if regional.isnull().any():
                    print("[DROPPED: missing data]", end="")
                    dropped_members.append((variant, experiment, member_id))
                    print()
                    continue

                regional = regional.assign_coords(member_id=member_id).expand_dims("member_id")
                member_list.append(regional)
                print()

            if not member_list:
                print("  [SKIPPED: no valid members]")
                skipped_stores.append((variant, experiment))
                continue

            ds_out = xr.concat(member_list, dim="member_id").to_dataset(name="tas")
            ds_out["tas"].attrs["long_name"] = "AR6 regional mean temperature"
            ds_out["tas"].attrs["units"]     = "K"
            ds_out["tas"].attrs["source_variable"] = "TREFHT"
            ds_out["tas"].attrs["regions"]   = "58 AR6 WGI reference regions (46 land + 12 ocean)"
            ds_out["tas"].attrs["weighting"] = "cosine latitude"
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
    append_run_summary("lens2_ar6.py", n_written, n_existed, dropped_4, skipped_3)


if __name__ == "__main__":
    main()
