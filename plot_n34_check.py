#!/usr/bin/env python
"""Visual check: 5 random n34 files, 20 years, monthly climatology removed."""

import random
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

N34_DIR = Path(__file__).parent / "n34_data"
N_YEARS = 20
OUT = Path(__file__).parent / "n34_visual_check.pdf"

random.seed(42)
files = sorted(N34_DIR.glob("*.nc"))
picks = random.sample(files, min(5, len(files)))

fig, axes = plt.subplots(5, 1, figsize=(11, 10), layout="constrained")

for ax, path in zip(axes, picks):
    ds = xr.open_dataset(path, decode_times=xr.coders.CFDatetimeCoder(use_cftime=True))
    member_id = str(ds.member_id.values[0])
    ts = ds.n34.sel(member_id=member_id)

    # monthly climatology removal
    clim = ts.groupby("time.month").mean("time")
    anom = ts.groupby("time.month") - clim

    # first N_YEARS * 12 months
    anom = anom.isel(time=slice(0, N_YEARS * 12))
    t = np.arange(len(anom)) / 12

    ax.plot(t, anom.values, lw=0.8, color="steelblue")
    ax.axhline(0, color="k", lw=0.5, ls="--")
    ax.set_xlim(0, N_YEARS)
    ax.set_ylabel("K")

    label = f"{ds.institution_id.values}  {ds.source_id.values}  {ds.experiment_id.values}  {member_id}"
    ax.set_title(label, fontsize=9, loc="left")

axes[-1].set_xlabel("Year (relative to start)")

fig.savefig(OUT, dpi=150)
print(f"Saved {OUT}")
