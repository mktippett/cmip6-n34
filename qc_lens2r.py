#!/usr/bin/env python
"""QC check for CESM2-LE relative Niño 3.4 NetCDF files.

Same checks and thresholds as qc_n34r.py; adapted for lens2_n34r_data/.
"""

from pathlib import Path
import xarray as xr

N34R_DIR  = Path(__file__).parent / "lens2_n34r_data"
RANGE_MIN = 250.0   # K — n34, trop
RANGE_MAX = 315.0   # K — n34, trop
STD_MIN   = 0.1     # K — n34, trop

N34R_MIN  = -10.0   # K — n34r
N34R_MAX  = 10.0    # K — n34r
N34R_STD_MIN = 0.05  # K — n34r

flags = []

files = sorted(N34R_DIR.glob("*.nc"))
print(f"Checking {len(files)} files in {N34R_DIR}\n")

for path in files:
    ds = xr.open_dataset(path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    for member_id in ds.member_id.values:
        label = f"{path.stem}  {member_id}"
        reasons = []

        for var, lo, hi, std_min in (
            ("n34",  RANGE_MIN, RANGE_MAX, STD_MIN),
            ("trop", RANGE_MIN, RANGE_MAX, STD_MIN),
            ("n34r", N34R_MIN,  N34R_MAX,  N34R_STD_MIN),
        ):
            x = ds[var].sel(member_id=member_id)
            mn, mx, std = float(x.min()), float(x.max()), float(x.std())
            if mn < lo or mx > hi:
                reasons.append(f"{var} range [{mn:.2f}, {mx:.2f}] K outside [{lo}, {hi}]")
            if std < std_min:
                reasons.append(f"{var} std {std:.4f} K < {std_min}")

        if reasons:
            for r in reasons:
                print(f"  FLAG  {label}  —  {r}")
            flags.append((label, reasons))

print(f"\n{'─'*60}")
if flags:
    print(f"Total flagged members: {len(flags)}")
    for label, reasons in flags:
        print(f"  {label}: {'; '.join(reasons)}")
else:
    print("No flags — all members passed.")
