#!/usr/bin/env python
"""QC check for CESM2-LE Niño 3.4 NetCDF files.

Checks per member:
  1. Physical range: min < 250 K or max > 315 K
  2. Near-zero variance: std < 0.1 K

Same thresholds as qc_n34.py; adapted for lens2_n34_data/.
"""

from pathlib import Path
import xarray as xr

N34_DIR   = Path(__file__).parent / "lens2_n34_data"
RANGE_MIN = 250.0   # K
RANGE_MAX = 315.0   # K
STD_MIN   = 0.1     # K

flags = []

files = sorted(N34_DIR.glob("*.nc"))
print(f"Checking {len(files)} files in {N34_DIR}\n")

for path in files:
    ds = xr.open_dataset(path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    for member_id in ds.member_id.values:
        ts = ds.n34.sel(member_id=member_id)
        label = f"{path.stem}  {member_id}"

        mn, mx, std = float(ts.min()), float(ts.max()), float(ts.std())

        reasons = []
        if mn < RANGE_MIN or mx > RANGE_MAX:
            reasons.append(f"range [{mn:.1f}, {mx:.1f}] K outside [{RANGE_MIN}, {RANGE_MAX}]")
        if std < STD_MIN:
            reasons.append(f"std {std:.4f} K < {STD_MIN}")

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
