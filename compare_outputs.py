"""Compare two directories of NetCDF files for structural and numerical agreement."""

import sys
from pathlib import Path
import numpy as np
import xarray as xr

def compare_dirs(ref_dir, new_dir, tol=1e-6):
    ref_dir = Path(ref_dir)
    new_dir = Path(new_dir)

    ref_files = {f.name for f in ref_dir.glob("*.nc")}
    new_files = {f.name for f in new_dir.glob("*.nc")}

    missing  = ref_files - new_files
    extra    = new_files - ref_files
    common   = ref_files & new_files

    print(f"Reference : {len(ref_files)} files  ({ref_dir})")
    print(f"New       : {len(new_files)} files  ({new_dir})")
    print(f"Common    : {len(common)}   Missing: {len(missing)}   Extra: {len(extra)}")
    if missing:
        print(f"  MISSING: {sorted(missing)}")
    if extra:
        print(f"  EXTRA:   {sorted(extra)}")

    failures = []
    for name in sorted(common):
        ref = xr.open_dataset(ref_dir / name, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
        new = xr.open_dataset(new_dir / name, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))

        # check dims match
        for var in ref.data_vars:
            if var not in new.data_vars:
                failures.append(f"{name}: variable '{var}' missing from new")
                continue
            if ref[var].dims != new[var].dims:
                failures.append(f"{name}/{var}: dims {ref[var].dims} vs {new[var].dims}")
                continue
            if ref[var].shape != new[var].shape:
                failures.append(f"{name}/{var}: shape {ref[var].shape} vs {new[var].shape}")
                continue
            if np.issubdtype(ref[var].dtype, np.floating):
                diff = float(np.abs(ref[var].values - new[var].values).max())
                if diff > tol:
                    failures.append(f"{name}/{var}: max diff {diff:.2e} > tol {tol:.2e}")

    print()
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures:
            print(f"  {f}")
    else:
        print(f"All {len(common)} common files match within tol={tol:.0e}.")

    return len(failures) == 0 and not missing

if __name__ == "__main__":
    ref_dir = sys.argv[1]
    new_dir = sys.argv[2]
    ok = compare_dirs(ref_dir, new_dir)
    sys.exit(0 if ok else 1)
