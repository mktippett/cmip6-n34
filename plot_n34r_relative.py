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
FUTURE_START, FUTURE_END = 2071, 2100
PLOT_START_YEAR = 1850
PLOT_END_YEAR = 2100
HIST_END_YEAR = 2014     # last year of the historical segment
SSP_START_YEAR = 2015    # first year of the ssp585 segment

BAND_WINDOW_YEARS = 10   # centered rolling-mean window smoothing the cross-model spread curve
BAND_LOW, BAND_HIGH = 0.10, 0.90  # percentile band, across models

# Panel 2: per-model std(scaled n34r) in the historical and future base periods,
# with a moving-block bootstrap 95% CI (block length preserves month-to-month
# autocorrelation that an iid resample would destroy).
BOOT_BLOCK_YEARS = 2
N_BOOT = 1000
BOOT_CI = (2.5, 97.5)
BOOT_SEED = 42
BAR_WIDTH = 0.35
COLOR_HIST = "0.4"
COLOR_FUTURE = "firebrick"

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


def block_bootstrap_std_draws(values, block_years, n_boot, rng):
    """Moving-block bootstrap draws of std(values) (monthly series).

    Blocks of `block_years` (24 months) are drawn with replacement and
    concatenated to length >= len(values), then trimmed to match; this
    preserves intra-block autocorrelation that an iid monthly resample
    would destroy. `values` must have no missing months.
    """
    block_len = block_years * 12
    n = len(values)
    n_blocks = int(np.ceil(n / block_len))
    max_start = n - block_len
    boot_std = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        resampled = np.concatenate([values[s:s + block_len] for s in starts])[:n]
        boot_std[b] = resampled.std(ddof=0)
    return boot_std


pairs = find_pairs(N34R_DIR)
LINE_COLOR = "0.4"
rng = np.random.default_rng(BOOT_SEED)

fig, (ax, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 17), layout="constrained")

clim_start = cftime.DatetimeNoLeap(CLIM_START, 1, 1)
clim_end = cftime.DatetimeNoLeap(CLIM_END, 12, 31)
future_start = cftime.DatetimeNoLeap(FUTURE_START, 1, 1)
future_end = cftime.DatetimeNoLeap(FUTURE_END, 12, 31)
hist_cutoff = cftime.DatetimeNoLeap(HIST_END_YEAR, 12, 31)
plot_end = cftime.DatetimeNoLeap(PLOT_END_YEAR, 12, 31)

plotted, missing_data, scaled_list, std_records = [], [], [], []
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

    hist_vals = scaled.sel(time=slice(clim_start, clim_end)).values
    future_vals = scaled.sel(time=slice(future_start, future_end)).values
    std_hist = hist_vals.std(ddof=0)
    std_future = future_vals.std(ddof=0)
    boot_hist = block_bootstrap_std_draws(hist_vals, BOOT_BLOCK_YEARS, N_BOOT, rng)
    boot_future = block_bootstrap_std_draws(future_vals, BOOT_BLOCK_YEARS, N_BOOT, rng)
    ci_hist = np.percentile(boot_hist, BOOT_CI)
    ci_future = np.percentile(boot_future, BOOT_CI)

    # Ratio's CI: pair the two periods' independent block-bootstrap std draws
    # element-by-element into N_BOOT ratio draws, then take the percentile of
    # that ratio distribution (the per-model scaling factor cancels in the
    # ratio, so this is the same whether computed from n34r or scaled n34r).
    ratio = std_future / std_hist
    boot_ratio = boot_future / boot_hist
    ci_ratio = np.percentile(boot_ratio, BOOT_CI)

    std_records.append({
        "source_id": source_id,
        "std_hist": std_hist, "ci_hist": ci_hist,
        "std_future": std_future, "ci_future": ci_future,
        "ratio": ratio, "ci_ratio": ci_ratio,
    })

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

std_records.sort(key=lambda r: r["std_hist"])
x = np.arange(len(std_records))
labels = [r["source_id"] for r in std_records]

std_hist = np.array([r["std_hist"] for r in std_records])
std_future = np.array([r["std_future"] for r in std_records])
err_hist = np.array([[r["std_hist"] - r["ci_hist"][0], r["ci_hist"][1] - r["std_hist"]] for r in std_records]).T
err_future = np.array([[r["std_future"] - r["ci_future"][0], r["ci_future"][1] - r["std_future"]] for r in std_records]).T

ax2.errorbar(x - BAR_WIDTH / 2, std_hist, yerr=err_hist, fmt="o", ms=4, capsize=3,
             color=COLOR_HIST, label=f"{CLIM_START}-{CLIM_END}", zorder=2)
ax2.errorbar(x + BAR_WIDTH / 2, std_future, yerr=err_future, fmt="o", ms=4, capsize=3,
             color=COLOR_FUTURE, label=f"{FUTURE_START}-{FUTURE_END}", zorder=2)
ax2.set_xticks(x)
ax2.set_xticklabels(labels, rotation=90, fontsize=8)
ax2.set_xlim(-0.5, len(std_records) - 0.5)
ax2.set_xlabel("Model")
ax2.set_ylabel("std(scaled relative Niño 3.4) (K)")
ax2.legend(loc="upper left", fontsize=9)
ax2.set_title(
    f"Monthly std of the scaled relative Niño 3.4 index, by model and period "
    f"(n={len(std_records)})\n"
    f"Models ordered by {CLIM_START}-{CLIM_END} std, smallest to largest\n"
    f"Error bars: {BOOT_BLOCK_YEARS}-yr moving-block bootstrap {int(BOOT_CI[1] - BOOT_CI[0])}% CI "
    f"({N_BOOT} resamples)",
    fontsize=10,
)

records_by_ratio = sorted(std_records, key=lambda r: r["ratio"])
x3 = np.arange(len(records_by_ratio))
labels3 = [r["source_id"] for r in records_by_ratio]
ratio = np.array([r["ratio"] for r in records_by_ratio])
err_ratio = np.array([[r["ratio"] - r["ci_ratio"][0], r["ci_ratio"][1] - r["ratio"]] for r in records_by_ratio]).T

ax3.errorbar(x3, ratio, yerr=err_ratio, fmt="o", ms=4, capsize=3, color="0.2", zorder=2)
ax3.axhline(1, color="k", lw=1, ls="--", zorder=1)
ax3.set_xticks(x3)
ax3.set_xticklabels(labels3, rotation=90, fontsize=8)
ax3.set_xlim(-0.5, len(records_by_ratio) - 0.5)
ax3.set_xlabel("Model")
ax3.set_ylabel(f"std({FUTURE_START}-{FUTURE_END}) / std({CLIM_START}-{CLIM_END})")
ax3.set_title(
    f"Ratio of future to historical std of relative Niño 3.4 (n={len(records_by_ratio)})\n"
    f"Rescaling cancels in the ratio (same for n34r and scaled n34r); "
    f"models ordered by ratio, smallest to largest\n"
    f"Error bars: {int(BOOT_CI[1] - BOOT_CI[0])}% CI from {N_BOOT} paired "
    f"{BOOT_BLOCK_YEARS}-yr block-bootstrap draws of std(future)/std(hist)",
    fontsize=10,
)

fig.savefig(OUT, dpi=150)
fig.savefig(OUT_PNG, dpi=150)
print(f"Saved {OUT}")
print(f"Saved {OUT_PNG}")
print(f"Plotted ({len(plotted)}): {', '.join(plotted)}")
if missing_data:
    print(f"No common member in hist+ssp585 ({len(missing_data)}): {', '.join(missing_data)}")
