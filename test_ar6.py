#!/usr/bin/env python
"""
Validate ar6 regional averages against ATLAS precomputed data.
Uses AWI-CM-1-1-MR historical r1i1p1f1 (tas, land-sea).
Prints a comparison table and saves a scatter plot.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib.pyplot as plt

AR6_DIR = Path(__file__).parent / "ar6_data"
OUT     = Path(__file__).parent / "test_ar6_validation.pdf"

ATLAS_URL = (
    "https://raw.githubusercontent.com/SantanderMetGroup/ATLAS/devel/"
    "datasets-aggregated-regionally/data/CMIP6/CMIP6_tas_landsea/"
    "CMIP6_AWI-CM-1-1-MR_historical_r1i1p1f1.csv"
)

# ── load data ─────────────────────────────────────────────────────────────
atlas = pd.read_csv(ATLAS_URL, comment="#", index_col=0, parse_dates=True)

ds = xr.open_dataset(
    AR6_DIR / "ar6_AWI_AWI-CM-1-1-MR_historical.nc",
    decode_times=xr.coders.CFDatetimeCoder(use_cftime=True),
)
our_r1 = ds.tas.sel(member_id="r1i1p1f1")  # (time, region)

# ── find shared regions ────────────────────────────────────────────────────
our_abbrevs = list(ds.abbrevs.values)
shared = [a for a in our_abbrevs if a in atlas.columns]
abbrev_to_region = dict(zip(ds.abbrevs.values, ds.region.values))

atlas_means = atlas[shared].mean().values
our_means   = our_r1.sel(region=[abbrev_to_region[a] for a in shared]).mean("time").values - 273.15
diffs = our_means - atlas_means

# ── RMSE and correlation (full monthly time series, aligned overlap) ──────
# ATLAS starts 1850-01, ours starts 1851-01; both end 2014-12, monthly, no gaps,
# so the last len(our_r1.time) rows of atlas line up 1:1 with our_r1's time axis.
n_time = our_r1.sizes["time"]
atlas_ts = xr.DataArray(
    atlas[shared].iloc[-n_time:].values,
    dims=("t", "region"),
    coords={"region": shared},
)
our_ts = xr.DataArray(
    (our_r1.sel(region=[abbrev_to_region[a] for a in shared]) - 273.15).values,
    dims=("t", "region"),
    coords={"region": shared},
)
rmse = np.sqrt(((our_ts - atlas_ts) ** 2).mean("t")).values
corr = xr.corr(atlas_ts, our_ts, dim="t").values

# ── print table ───────────────────────────────────────────────────────────
print(f"{'Region':6}  {'ATLAS (°C)':>12}  {'Ours (°C)':>12}  {'Diff':>8}  {'RMSE':>6}  {'Corr':>7}")
print("-" * 64)
for a, am, om, d, r, c in zip(shared, atlas_means, our_means, diffs, rmse, corr):
    print(f"{a:6}  {am:12.2f}  {om:12.2f}  {d:8.2f}  {r:6.3f}  {c:7.4f}")
print()
print(f"Mean |diff|: {np.abs(diffs).mean():.3f} °C   Max |diff|: {np.abs(diffs).max():.3f} °C")
print(f"Mean RMSE:   {rmse.mean():.3f} °C   Max RMSE: {rmse.max():.3f} °C")
print(f"Mean corr:   {corr.mean():.4f}      Min corr: {corr.min():.4f}")

# ── time series: 10 years, 4 regions, anomalies ───────────────────────────
ts_regions   = ["NEU", "EAS", "WAF", "WNA"]
ts_colors    = ["steelblue", "tomato", "goldenrod", "mediumpurple"]
YEAR0, YEAR1 = 1980, 1989

# ATLAS: subset to decade
atlas_decade = atlas.loc[str(YEAR0):str(YEAR1)]
atlas_t = np.arange(len(atlas_decade)) / 12  # fractional years from YEAR0

# Our data: label-based time selection, decimal-year axis via .dt accessor
our_decade = our_r1.isel(time=our_r1.time.dt.year.isin(range(YEAR0, YEAR1 + 1)))
our_t = our_decade.time.dt.year.values + (our_decade.time.dt.month.values - 1) / 12 - YEAR0

# ── figure: scatter (left) + time series (right) ─────────────────────────
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6), layout="constrained")

# --- scatter ---
ax1.scatter(atlas_means, our_means, s=30, zorder=3)
lims = [min(atlas_means.min(), our_means.min()) - 2,
        max(atlas_means.max(), our_means.max()) + 2]
ax1.plot(lims, lims, "k--", lw=0.8, label="1:1")
ax1.set_xlim(lims); ax1.set_ylim(lims)
for a, am, om in zip(shared, atlas_means, our_means):
    ax1.text(float(am), float(om), f" {a}", fontsize=6, va="center")
ax1.set_xlabel("ATLAS tas (°C)  —  AWI-CM-1-1-MR historical r1i1p1f1")
ax1.set_ylabel("This study tas (°C)")
ax1.set_title("Regional time-means: ATLAS vs computed\n"
              f"N={len(shared)} regions   mean |diff| = {np.abs(diffs).mean():.3f} °C")
ax1.legend()

# --- time series ---
for region, color in zip(ts_regions, ts_colors):
    # ours first (solid, wide)
    o_series = our_decade.sel(region=abbrev_to_region[region]).values - 273.15
    o_anom   = o_series - o_series.mean()
    ax2.plot(our_t, o_anom, "-", color=color, lw=2.5, label=region)

    # ATLAS on top (dashed, thinner, black so it reads over solid)
    a_series = atlas_decade[region].values
    a_anom   = a_series - a_series.mean()
    ax2.plot(atlas_t, a_anom, "--", color="k", lw=1.2, alpha=0.7)

ax2.axhline(0, color="k", lw=0.5, ls=":")
ax2.set_xlabel(f"Year (relative to {YEAR0})")
ax2.set_ylabel("tas anomaly (°C, re 10-yr mean)")
ax2.set_title(f"Time series {YEAR0}–{YEAR1}\nsolid (colored) = ours, dashed (black) = ATLAS")
ax2.legend(ncol=2, fontsize=9)

fig.savefig(OUT, dpi=150)
print(f"\nSaved {OUT}")
