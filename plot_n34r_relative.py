#!/usr/bin/env python
"""Spaghetti plot: scaled relative Niño 3.4 index, historical+ssp585, one member per model.

Reads n34r_data/ (see cmip6_n34r.py / specs/cmip6_n34r.md) for every model with
both historical and ssp585 present. For each model, picks one member present in
both experiments (preferring r1i1p1f1), concatenates the two, removes a
1985-2014 monthly climatology computed from the historical segment, then
rescales by a per-calendar-month variance-matching factor std(n34)/std(n34r)
(same 1985-2014 base period, same model) — the RONI-style rescaling step that
cmip6_n34r.py deliberately leaves out of its raw output. No legend (31 models).
"""

import re
from pathlib import Path

import cftime
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

N34R_DIR = Path(__file__).parent / "n34r_data"
OUT = Path(__file__).parent / "n34r_relative_spaghetti.pdf"
OUT_PNG = OUT.with_suffix(".png")

CLIM_START, CLIM_END = 1985, 2014
PLOT_START_YEAR = 1850
PLOT_END_YEAR = 2100
HIST_END_YEAR = 2014     # last year of the historical segment
SSP_START_YEAR = 2015    # first year of the ssp585 segment

BAND_WINDOW_YEARS = 10   # centered rolling-mean window smoothing the cross-model spread curve
BAND_LOW, BAND_HIGH = 0.10, 0.90  # percentile band, across models

FILENAME_RE = re.compile(r"n34r_(.+)_(.+)_(historical|ssp585)\.nc")
MEMBER_RE = re.compile(r"r(\d+)i(\d+)p(\d+)f(\d+)")


def member_key(member_id):
    m = MEMBER_RE.match(member_id)
    return tuple(int(g) for g in m.groups())


def pick_member(hist_members, ssp_members):
    common = set(hist_members) & set(ssp_members)
    if not common:
        return None
    if "r1i1p1f1" in common:
        return "r1i1p1f1"
    return min(common, key=member_key)


def find_pairs(n34r_dir):
    """(institution_id, source_id) pairs with both a historical and ssp585 file."""
    hist, ssp = {}, {}
    for path in n34r_dir.glob("*.nc"):
        m = FILENAME_RE.match(path.name)
        if not m:
            continue
        institution_id, source_id, experiment_id = m.groups()
        (hist if experiment_id == "historical" else ssp)[source_id] = (institution_id, path)
    common_sources = sorted(set(hist) & set(ssp))
    return [(hist[s][0], s, hist[s][1], ssp[s][1]) for s in common_sources]


def cross_model_band(segment, window_years):
    """Cross-model 10th/90th-percentile spread, computed at each month, then
    smoothed with a centered rolling mean over `window_years` in time.

    Computing the percentile across models first (not pooled with time) keeps
    this a measure of model disagreement, not a blend with each model's own
    ENSO-phase variability. `segment` must already be confined to one side of
    the 2014/2015 join, and the rolling mean uses min_periods=1 so it only
    shrinks near the segment's true endpoints — it never reaches past them.
    """
    q = segment.quantile([BAND_LOW, BAND_HIGH], dim="model", skipna=True)
    window_months = round(window_years * 12)
    smoothed = q.rolling(time=window_months, center=True, min_periods=1).mean()
    decimal_year = smoothed.time.dt.year + (smoothed.time.dt.month - 1) / 12
    return decimal_year, smoothed.sel(quantile=BAND_LOW), smoothed.sel(quantile=BAND_HIGH)


pairs = find_pairs(N34R_DIR)
LINE_COLOR = "0.4"

fig, ax = plt.subplots(figsize=(11, 6), layout="constrained")

clim_start = cftime.DatetimeNoLeap(CLIM_START, 1, 1)
clim_end = cftime.DatetimeNoLeap(CLIM_END, 12, 31)
hist_cutoff = cftime.DatetimeNoLeap(HIST_END_YEAR, 12, 31)
plot_end = cftime.DatetimeNoLeap(PLOT_END_YEAR, 12, 31)

plotted, missing_data, scaled_list = [], [], []
coder = xr.coders.CFDatetimeCoder(use_cftime=True)

for institution_id, source_id, hist_path, ssp_path in pairs:
    ds_hist = xr.open_dataset(hist_path, decode_times=coder)
    ds_ssp = xr.open_dataset(ssp_path, decode_times=coder)

    member = pick_member(ds_hist.member_id.values, ds_ssp.member_id.values)
    if member is None:
        missing_data.append(source_id)
        continue

    n34_hist = ds_hist["n34"].sel(member_id=member)
    n34r_hist = ds_hist["n34r"].sel(member_id=member)
    n34r_ssp = ds_ssp["n34r"].sel(member_id=member)

    base_n34 = n34_hist.sel(time=slice(clim_start, clim_end))
    base_n34r = n34r_hist.sel(time=slice(clim_start, clim_end))

    clim = base_n34r.groupby("time.month").mean("time")
    scale = base_n34.groupby("time.month").std("time") / base_n34r.groupby("time.month").std("time")

    # Some models' historical archives run past 2014 (e.g. FGOALS-g3 to
    # 2016-12), overlapping ssp585 — truncate at the segment boundary so the
    # concatenated series has no duplicate/overlapping time values.
    n34r_hist_trimmed = n34r_hist.sel(time=slice(None, hist_cutoff))
    full = xr.concat([n34r_hist_trimmed, n34r_ssp], dim="time").sortby("time")
    full = full.sel(time=slice(None, plot_end))
    anom = full.groupby("time.month") - clim
    scaled = anom.groupby("time.month") * scale

    decimal_year = full.time.dt.year + (full.time.dt.month - 1) / 12
    ax.plot(decimal_year, scaled.values, lw=0.8, alpha=0.5, color=LINE_COLOR, zorder=2)
    plotted.append(source_id)
    scaled_list.append(scaled)

if scaled_list:
    combined = xr.concat(scaled_list, dim="model")
    for year_start, year_end in [(PLOT_START_YEAR, HIST_END_YEAR), (SSP_START_YEAR, PLOT_END_YEAR)]:
        segment = combined.sel(time=slice(
            cftime.DatetimeNoLeap(year_start, 1, 1), cftime.DatetimeNoLeap(year_end, 12, 31)
        ))
        decimal_year, low, high = cross_model_band(segment, BAND_WINDOW_YEARS)
        # Drawn on top of the spaghetti lines (zorder=3): 31 overlapping gray
        # lines at alpha 0.5 fully hide a fill sitting underneath them, so the
        # band has to paint over, not behind.
        ax.fill_between(decimal_year, low, high, color="steelblue", alpha=0.3, lw=0, zorder=3)
        ax.plot(decimal_year, low, color="steelblue", lw=1.3, zorder=4)
        ax.plot(decimal_year, high, color="steelblue", lw=1.3, zorder=4)

ax.axhline(0, color="k", lw=0.5, ls="--", zorder=5)
ax.axvline(2015, color="k", lw=1.2, ls="--", zorder=5)
ax.set_xlim(1850, PLOT_END_YEAR)
ax.set_xlabel("Year")
ax.set_ylabel("Scaled relative Niño 3.4 anomaly (K)")
ax.set_title(
    f"Relative Niño 3.4, rescaled to n34 variance, CMIP6 historical+ssp585, "
    f"one member per model (n={len(plotted)})\n"
    f"Anomaly and scale factor (std(n34)/std(n34r), per calendar month) both from "
    f"{CLIM_START}-{CLIM_END}\n"
    f"Shading: {int(BAND_LOW*100)}th-{int(BAND_HIGH*100)}th percentile across models each "
    f"month, {BAND_WINDOW_YEARS}-yr centered rolling mean in time\n"
    f"(smoothed separately either side of the historical/ssp585 join, dashed line)",
    fontsize=10,
)

fig.savefig(OUT, dpi=150)
fig.savefig(OUT_PNG, dpi=150)
print(f"Saved {OUT}")
print(f"Saved {OUT_PNG}")
print(f"Plotted ({len(plotted)}): {', '.join(plotted)}")
if missing_data:
    print(f"No common member in hist+ssp585 ({len(missing_data)}): {', '.join(missing_data)}")
