# Spec: plot_n34r_relative.py

## 1. Purpose

Visualize the **scaled relative Niño 3.4 index** across every CMIP6 model that
has both `historical` and `ssp585` in `n34r_data/` (see `specs/cmip6_n34r.md`),
as a 4-panel figure: (1) a spaghetti plot spanning 1850-2100 with a shaded band
quantifying cross-model disagreement and how it evolves under ssp585 warming,
(2) per-model, per-period ENSO variability (std of the scaled index) in the
historical and end-of-century base periods, (3) the ratio of the two,
i.e. how much each model's simulated ENSO variability changes under warming,
and (4) per-model linear trend (OLS slope) of the scaled index in two 40-yr
periods (1975-2014, 2031-2070), i.e. how much each model's ENSO-relative
background state is drifting.

## 2. Inputs

| File / source | Relevant columns | Filters applied |
|----------------|-------------------|------------------|
| `n34r_data/n34r_{institution_id}_{source_id}_historical.nc` | `n34(member_id, time)`, `n34r(member_id, time)` | one file per model; `find_pairs` keeps only `source_id`s that have **both** a `historical` and an `ssp585` file present on disk |
| `n34r_data/n34r_{institution_id}_{source_id}_ssp585.nc` | `n34r(member_id, time)` | same |

No catalog query and no CLI args — this script only reads what `cmip6_n34r.py`
has already written locally.

## 3. Outputs

| File | Contents | Format |
|------|----------|--------|
| `n34r_relative_spaghetti.pdf` | 4x1 figure. **Panel 1**: one gray line per model (scaled relative Niño 3.4 anomaly, 1850-2100, no legend) + a steelblue shaded spread band + dashed reference lines at y=0 and the 2014/2015 join. **Panel 2**: per model, two paired error-bar points (std of the scaled index in 1985-2014 vs. 2071-2100, gray vs. firebrick), models ordered by ascending 1985-2014 std. **Panel 3**: per model, one error-bar point (ratio std(2071-2100)/std(1985-2014)) + dashed y=1 reference line, models ordered by ascending ratio (independent of panel 2's order). **Panel 4**: per model, two paired error-bar points (OLS trend of the scaled index in 1975-2014 vs. 2031-2070, K/decade, gray vs. firebrick) + dashed y=0 reference line, models ordered by ascending 1975-2014 trend | matplotlib, 150 dpi |
| `n34r_relative_spaghetti.png` | Identical figure, raster | matplotlib, 150 dpi |
| stdout | List of plotted `source_id`s; any models dropped for lacking a common member between historical/ssp585 | text |

## 4. Algorithm

1. `find_pairs`: regex-scan `n34r_data/*.nc` filenames, keep `source_id`s with
   both a `historical` and an `ssp585` file. No fixed model list — whatever is
   on disk is plotted (see §5, "Model set").
2. For each `(institution_id, source_id, hist_path, ssp_path)`:
   1. `pick_member`: intersect `member_id`s present in both files; prefer
      `r1i1p1f1` if present, else the lowest-numbered common member
      (`r`,`i`,`p`,`f` compared numerically). A model with no common member is
      skipped and recorded in `missing_data`. Picking a member common to both
      experiments (rather than an arbitrary member per experiment) keeps the
      concatenated series one continuous single-realization trajectory.
   2. Base period `1985-2014` (`CLIM_START`-`CLIM_END`), taken from the
      historical segment only:
      - `clim = n34r_hist_base.groupby("time.month").mean("time")` — monthly
        climatology of the raw (unscaled) `n34r`.
      - `scale = std(n34_base, per month) / std(n34r_base, per month)` — the
        RONI-style variance-matching factor, per calendar month, per model.
   3. Truncate the historical segment at `HIST_END_YEAR` (2014-12) before
      concatenating with ssp585 — see §6, FGOALS-g3.
   4. `full = concat(n34r_hist_trimmed, n34r_ssp)`, trimmed to `PLOT_END_YEAR`
      (2100) at the far end.
   5. `anom = full.groupby("time.month") - clim`; `scaled = anom.groupby("time.month") * scale`.
   6. Plot `scaled` vs. decimal year as one gray line (`LINE_COLOR = "0.4"`,
      `alpha=0.5`, `lw=0.8`); append `scaled` to `scaled_list` for the band.
   7. **Panel 2/3 statistics**, computed per model from this same `scaled`
      series (the per-model variance-matching `scale` factor is common to
      both periods, so it cancels in any std ratio — the panel-3 ratio would
      be identical if computed from raw, unscaled `n34r`):
      - `hist_vals = scaled.sel(time=slice(CLIM_START, CLIM_END))`,
        `future_vals = scaled.sel(time=slice(FUTURE_START, FUTURE_END))`
        (360 monthly values each).
      - `std_hist = hist_vals.std(ddof=0)`, `std_future = future_vals.std(ddof=0)`.
      - `boot_hist = block_bootstrap_std_draws(hist_vals, ...)`,
        `boot_future = block_bootstrap_std_draws(future_vals, ...)` — see
        §4a below. `ci_hist`/`ci_future` are the `BOOT_CI` percentiles of
        each draw array.
      - `ratio = std_future / std_hist`; `boot_ratio = boot_future / boot_hist`
        (element-by-element pairing of the two periods' independent draw
        arrays, not a fresh bootstrap); `ci_ratio` is the `BOOT_CI`
        percentile of `boot_ratio`.
      - All values stored in `std_records` (one dict per model) for panels
        2 and 3 to consume after the main loop.
      - **Panel 4 statistics**, computed per model from the same `scaled`
        series:
        - `trend_hist_da = scaled.sel(time=slice(TREND_HIST_START, TREND_HIST_END))`,
          `trend_future_da = scaled.sel(time=slice(TREND_FUTURE_START, TREND_FUTURE_END))`
          (480 monthly values each, 1975-2014 and 2031-2070).
        - `slope_hist = np.polyfit(trend_hist_x, trend_hist_y, 1)[0] * 10`
          (K/decade; `trend_hist_x` is decimal year), same for `slope_future`.
        - `boot_slope_hist = block_bootstrap_trend_draws(trend_hist_x, trend_hist_y, ...) * 10`,
          same for `boot_slope_future` — see §4b. `ci_trend_hist`/`ci_trend_future`
          are the `BOOT_CI` percentiles of each draw array.
        - All values stored in `trend_records` (one dict per model) for
          panel 4 to consume after the main loop.

### 4a. Moving-block bootstrap (`block_bootstrap_std_draws`)

For a 30-yr monthly series `values` (length `n=360`, no missing months):
block length `block_len = BOOT_BLOCK_YEARS * 12` (24 months);
`n_blocks = ceil(n / block_len)`. For each of `N_BOOT` draws: sample
`n_blocks` start indices uniformly from `[0, n - block_len]` with
replacement (`rng.integers`), concatenate the corresponding 24-month
contiguous blocks, trim to length `n`, compute `std(ddof=0)`. Returns the
array of `N_BOOT` bootstrap std values (not yet reduced to a CI) so panel 3
can reuse the same draws to build the ratio's CI. Blocks (rather than iid
monthly resampling) preserve the ENSO-driven month-to-month autocorrelation
in the series; destroying that would bias the bootstrap std distribution.
One shared `rng = np.random.default_rng(BOOT_SEED)` stream is used across
every model and both periods, drawn in the order `find_pairs` iterates
models, historical before future per model — reran with the same seed
reproduces the exact same CIs.

### 4b. Paired moving-block bootstrap for the trend (`block_bootstrap_trend_draws`)

For a 40-yr monthly series `values` paired with its `decimal_year` (length
`n=480`, no missing months): block length `block_len = BOOT_BLOCK_YEARS * 12`
(24 months, same block length as §4a); `n_blocks = ceil(n / block_len)`. For
each of `N_BOOT` draws: sample `n_blocks` start indices uniformly from
`[0, n - block_len]` with replacement, and for each start index concatenate
the corresponding 24-month contiguous block of **(decimal_year, value) pairs
together** (not values alone), trim both resampled arrays to length `n`,
refit `np.polyfit(x_resampled, y_resampled, 1)[0]` to get one bootstrap slope.
Returns the array of `N_BOOT` bootstrap slopes (K/yr, scaled to K/decade by
the caller). This differs from §4a's `block_bootstrap_std_draws` in one
essential way: std is order-invariant, so resampling raw values against a
fixed time grid is valid, but a trend slope is order-dependent — resampling
values alone and refitting against the *original* time grid would scramble
the temporal structure the slope depends on. Keeping each block's
(time, value) pairing intact preserves the local trend and autocorrelation
within the block, while the block-to-block resampling still generates CI
width from the series' block-scale variability. User-specified explicitly
after being asked to choose between this pairs-preserving approach and a
residual-based alternative (fit trend, block-resample residuals, add back,
refit) — the user's phrasing ("bootstrap the pairs of (y, x) where x is
time... that preserves the temporal structure") specifies the pairs approach.
Uses the same shared `rng` stream as §4a (continues drawing from it, not a
separate seed).

3. Cross-model spread band (`cross_model_band`), computed **separately** for
   the historical segment (1850-2014) and the ssp585 segment (2015-2100) so
   the smoothing window never straddles the join:
   1. `combined = xr.concat(scaled_list, dim="model")` (outer join on `time`
      — models with different start dates, e.g. EC-Earth3 at 1849-12, are
      NaN-padded where they don't overlap).
   2. Per segment: `q = combined.quantile([0.10, 0.90], dim="model", skipna=True)`
      — the cross-model percentile **at each individual month**, computed
      before any time-averaging so the band measures model disagreement, not
      a blend of model disagreement with each model's own ENSO-phase noise.
   3. `q.rolling(time=120, center=True, min_periods=1).mean()` — a 10-year
      (120-month) centered rolling mean smooths the resulting spread curve in
      time. `min_periods=1` lets the window shrink near each segment's true
      endpoints (including right up to the 2014/2015 join) rather than
      reaching past them.
4. Plot the band: `fill_between` (steelblue, alpha=0.3) plus solid boundary
   lines (steelblue, lw=1.3) for the low/high edges, all drawn at a higher
   zorder than the spaghetti lines — see §6, band visibility.
5. Panel 1 title/subtitle carries the methodology (base period, scaling
   formula, band definition, window length) since there is no legend and no
   caption.
6. **Panel 2**: sort `std_records` by `std_hist` ascending; plot two
   `ax2.errorbar` series at integer x-positions `i - BAR_WIDTH/2` (historical,
   `COLOR_HIST`) and `i + BAR_WIDTH/2` (future, `COLOR_FUTURE`), asymmetric
   `yerr` from each point's `(std - ci_lo, ci_hi - std)`; x-tick labels are
   `source_id`, rotated 90°; legend distinguishes the two periods.
7. **Panel 3**: sort a *separate* copy of `std_records` by `ratio` ascending
   (independent of panel 2's order — panel 3 is its own model ordering); plot
   one `ax3.errorbar` series at integer x-positions with asymmetric `yerr`
   from `(ratio - ci_ratio_lo, ci_ratio_hi - ratio)`; dashed black line at
   y=1 (no-change reference); x-tick labels rotated 90°.
8. **Panel 4**: sort `trend_records` by `trend_hist` ascending; plot two
   `ax4.errorbar` series at integer x-positions `i - BAR_WIDTH/2` (1975-2014,
   `COLOR_HIST`) and `i + BAR_WIDTH/2` (2031-2070, `COLOR_FUTURE`), asymmetric
   `yerr` from each point's `(trend - ci_lo, ci_hi - trend)`; dashed black
   line at y=0 (no-trend reference); x-tick labels rotated 90°; legend
   distinguishes the two periods — same visual format as panel 2.
9. Save both `.pdf` and `.png` (all four panels, one figure, one file
   pair — filenames unchanged from the single-panel version).

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| `CLIM_START`, `CLIM_END` | 1985, 2014 | User-specified anomaly base period; also used (same period) as the base for the variance-matching scale factor — confirmed explicitly with the user rather than assumed, since the request separately said "1985-2015" for the scaling factor, which would have pulled one year from ssp585 instead of historical. |
| `PLOT_END_YEAR` | 2100 | ssp585 archives run to 2300 for some models (e.g. ACCESS-CM2, CanESM5) and stop at 2100 for most others; capped at 2100 so every model contributes over the same x-range. |
| `HIST_END_YEAR`, `SSP_START_YEAR` | 2014, 2015 | Standard CMIP6 historical/scenario split. |
| `FUTURE_START`, `FUTURE_END` | 2071, 2100 | User-specified end-of-century base period for panel 2/3, same length (30 yr) as the historical base period so the two std estimates are directly comparable. |
| Panel 2/3 std series | `scaled` (the same variance-matched series plotted in panel 1), not raw `n34r` | User-confirmed explicitly rather than assumed: keeps panel 2/3 describing the same curves panel 1 plots. For panel 3 the choice is moot — the per-model `scale` factor is common to both periods and cancels in the ratio, so std(future)/std(hist) is identical whether computed from `n34r` or `scaled`. |
| `BOOT_BLOCK_YEARS` | 2 | User-specified: a moving-block bootstrap with 24-month contiguous blocks (not an iid monthly resample, and not a block-mean-of-std scheme) — user-confirmed explicitly after an ambiguous initial request ("2-year bootstrap"). Preserves ENSO-driven month-to-month autocorrelation that iid resampling would destroy and bias the std estimate's spread. |
| `N_BOOT` | 1000 | User-specified resample count for the block bootstrap. |
| Std computed on monthly values, not annual means | — | User-confirmed explicitly: std uses the ~360 raw monthly values per 30-yr period, not a first pass to 30 annual means (which would remove intra-year/seasonal variance from the estimate). |
| `BOOT_CI` | (2.5, 97.5) | 95% percentile interval of the bootstrap draw distribution. |
| `BOOT_SEED` | 42 | Fixed seed for a reproducible figure — rerunning the script without changing the data reproduces identical error bars. |
| Panel 2 layout | paired bars per model (`BAR_WIDTH=0.35` offset), not one flat 62-bar sequence | User-specified explicitly between the two options. |
| `COLOR_HIST`, `COLOR_FUTURE` | `"0.4"`, `"firebrick"` | Historical matches panel 1's spaghetti-line gray (`LINE_COLOR`) for visual continuity; firebrick distinguishes the future period and avoids reusing panel 1's `steelblue` (already meaning "cross-model spread"). |
| Panel 3 ratio direction | `std(future) / std(hist)` | User-specified explicitly between the two directions: values above 1 read as "ENSO variability increases under warming," matching the intuitive sense of the y=1 reference line. |
| Panel 3 CI construction | pair the two periods' independent bootstrap draw arrays element-by-element (`boot_future / boot_hist`), not a fresh separate bootstrap | User-specified explicitly ("bootstrap the top and bottom separately") — reuses the draws already computed for panel 2, and treats the two 30-yr periods (non-overlapping in time) as independent so their bootstrap distributions can be divided pairwise to approximate the ratio's sampling distribution. |
| Panel 3 model order | ascending by `ratio`, independent of panel 2's order (ascending by `std_hist`) | User-specified explicitly: each panel's x-axis order is defined by that panel's own statistic. |
| Scale factor | `std(n34, per calendar month) / std(n34r, per calendar month)`, both over 1985-2014, both per model | User-specified formula: rescales the raw (unscaled) relative index back up to Niño-3.4-like variance, the RONI-recipe step `cmip6_n34r.py` deliberately omits from its raw output (see `specs/cmip6_n34r.md` §5). |
| Member selection | prefer `r1i1p1f1`, else lowest common member | Not a scientific choice — an implementation default to get one continuous, single-realization trajectory per model. Spot-checked on 2 models (ACCESS-CM2, UKESM1-0-LL): the 2014/2015 seam is smooth at the member level, confirming no artifact from switching physical realizations across the join. |
| Model set | all `source_id`s in `n34r_data/` with both historical+ssp585 (31 as of this session) | Changed mid-session from an initial fixed 20-model list (from a user-supplied model table) to "all models we have," per explicit user request — see Synchronization Log. |
| Band statistic | 10th-90th percentile across models, 10-yr centered rolling mean in time | Both explicitly chosen by the user (asked directly rather than assumed, since a percentile-vs-stdev and a window-length choice each materially change the figure). |
| Band computed cross-model-first, not pooled with time | — | User explicitly corrected an earlier version that pooled all months+models together within the rolling window before taking the percentile — that blends inter-model spread with each model's own ENSO-phase (interannual) variability. Computing the percentile across models at each month first, then smoothing that curve in time, isolates model disagreement. |
| Band drawn on top of the spaghetti lines (zorder above), with solid edge lines | — | An earlier version drew the band behind the lines; 31 overlapping gray lines at `alpha=0.5` fully occlude a fill sitting underneath, especially since the 10th-90th band sits exactly where line density is highest. Discovered when the user reported "I see no band" despite correct underlying values. |
| `LINE_COLOR = "0.4"` | uniform gray, no per-model color | User-specified, replacing an earlier `gist_rainbow` per-model palette — with 31 unlabeled lines a categorical palette adds no identifiable information; gray also keeps the colored band visually distinct from the model lines. |
| `TREND_HIST_START`, `TREND_HIST_END` | 1975, 2014 | User-specified period for panel 4's "historical" trend point; entirely within the historical segment. |
| `TREND_FUTURE_START`, `TREND_FUTURE_END` | 2031, 2070 | User-specified period for panel 4's "future" trend point; entirely within the ssp585 segment; same 40-yr length as the historical trend period so the two slopes are directly comparable. |
| Panel 4 trend series | `scaled` (same variance-matched series as panels 1-3), OLS slope in K/decade | User-specified: "use the rescaled n34r." Slope computed as `np.polyfit(decimal_year, scaled_values, 1)[0]`, in K/yr, then scaled ×10 to K/decade for readability given ~40-yr periods. |
| Panel 4 bootstrap method | paired block bootstrap (§4b), not the raw-value bootstrap of §4a and not a residual bootstrap | User-specified explicitly after being asked to choose between the pairs-preserving approach and a residual-based alternative — see §4b rationale. |
| Panel 4 bootstrap block length | `BOOT_BLOCK_YEARS = 2` (reused from §4a) | User-specified explicitly: reuse the same block length as panels 2/3 rather than introduce a separate trend-specific constant. |
| Panel 4 layout | paired points per model (`BAR_WIDTH` offset, `COLOR_HIST`/`COLOR_FUTURE`), same visual format as panel 2 | User-specified: "add a 4th panel... in the same format at panels 2 and 3." |
| Panel 4 model order | ascending by `trend_hist` (1975-2014 trend) | Mirrors panel 2's convention of ordering by the first-listed period's statistic. |

## 6. Edge Cases & Error Handling

- **FGOALS-g3 historical archive overlaps ssp585**: its `historical` file runs
  to 2016-12 (not 2014-12), duplicating 24 months already present in its
  `ssp585` file (2015-01 to 2016-12). Concatenating the two un-truncated
  produced duplicate `time` values, which crashed `xr.concat(..., dim="model")`
  during band construction (pandas index can't reindex with duplicates) —
  and, before that, would have silently drawn a "loop-back" artifact in that
  one model's line. Fixed generally (not as a special case for this model) by
  truncating every model's historical segment at `HIST_END_YEAR` before
  concatenation.
- **No common member**: a model with disjoint `member_id` sets between its
  historical and ssp585 files is skipped and listed in `missing_data`; not
  observed in the current 31-model set, but the archive can change.
- **Unequal model start dates**: `xr.concat(scaled_list, dim="model")` uses
  the default outer join, so models with a slightly earlier start (e.g.
  EC-Earth3 at 1849-12 vs. 1850-01 for most others) are NaN-padded for the
  months they don't have; `quantile(..., skipna=True)` ignores those NaNs.
- **Rolling window at segment edges**: `min_periods=1` means the very first
  and last few months of each segment are smoothed over a partial (shrinking)
  window rather than a full 10-year one — expected, not a bug; the window
  never reaches into the other segment.
- **Panel 2/3 assume no missing months**: `block_bootstrap_std_draws` treats
  `hist_vals`/`future_vals` as exactly 360 contiguous monthly values with no
  gaps; a model with missing months in either 30-yr base period would silently
  shrink `n` and change the effective block/CI width rather than raising an
  error. Not observed in the current 31-model set.
- **Panel 3's paired-draw ratio CI is an approximation, not an exact ratio
  bootstrap**: `boot_ratio = boot_future / boot_hist` pairs the two periods'
  bootstrap draws by array index (draw 0 with draw 0, etc.), which is
  arbitrary since the two periods are independently resampled — this is
  equivalent to treating the pairing as a random matching, valid because the
  two draw arrays are independent and identically ordered only by RNG-draw
  sequence, not by any shared structure.
- **Panel 4 assumes no missing months**: `block_bootstrap_trend_draws` treats
  `trend_hist_da`/`trend_future_da` as exactly 480 contiguous monthly values
  with no gaps, same assumption as §4a/panel 2-3; not observed in the current
  31-model set.
- **Panel 4's block bootstrap resamples x along with y**: unlike §4a, the
  resampled time values `x_resampled` are not sorted and contain repeats
  (some months drawn into multiple blocks, others never drawn) — this is
  expected and correct for OLS, which only depends on the `(x, y)`
  correspondence within a draw, not on `x` being sorted or unique.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|---------------|
| 2026-08-25 | `plot_n34r_relative.py` created and iterated over one session: fixed 20-model list → scan-all-available (31 models); added variance-matching scale factor (1985-2014 base, per calendar month); added cross-model spread band (10th-90th percentile, 10-yr centered rolling mean, computed separately either side of 2014/2015); fixed FGOALS-g3 historical/ssp585 time overlap; fixed band-hidden-behind-lines rendering bug; switched line color to uniform gray; added PNG output alongside PDF | Spec created (initial) |
| 2026-08-25 | Added panel 2 (per-model std of scaled index, 1985-2014 vs. 2071-2100, paired error bars, 2-yr moving-block bootstrap 95% CI, models ordered by ascending historical std) and panel 3 (ratio std(future)/std(hist), single error bar per model, paired-draw bootstrap CI reusing panel 2's draws, y=1 reference line, models ordered by ascending ratio) — figure is now 3x1; added `FUTURE_START`/`FUTURE_END`, `BOOT_BLOCK_YEARS`, `N_BOOT`, `BOOT_CI`, `BOOT_SEED`, `BAR_WIDTH`, `COLOR_HIST`, `COLOR_FUTURE`, `block_bootstrap_std_draws()` | Prior update (§1, §3, §4, §4a new, §5, §6) |
| 2026-08-25 | Added panel 4 (per-model OLS trend of scaled index, 1975-2014 vs. 2031-2070, K/decade, paired error bars in panel 2's visual format, paired moving-block bootstrap 95% CI, y=0 reference line, models ordered by ascending 1975-2014 trend) — figure is now 4x1; added `TREND_HIST_START`/`TREND_HIST_END`, `TREND_FUTURE_START`/`TREND_FUTURE_END`, `trend_records`, `block_bootstrap_trend_draws()` | This update (§1, §3, §4, §4b new, §5, §6) |

## Verification Snippet

```python
from pathlib import Path
import xarray as xr

pdf = Path("n34r_relative_spaghetti.pdf")
png = Path("n34r_relative_spaghetti.png")
assert pdf.exists() and pdf.stat().st_size > 10_000, "PDF missing or too small"
assert png.exists() and png.stat().st_size > 10_000, "PNG missing or too small"

# Re-derive the model set the script would find, and sanity check coverage.
import re
FILENAME_RE = re.compile(r"n34r_(.+)_(.+)_(historical|ssp585)\.nc")
hist, ssp = set(), set()
for p in Path("n34r_data").glob("*.nc"):
    m = FILENAME_RE.match(p.name)
    if not m:
        continue
    (hist if m.group(3) == "historical" else ssp).add(m.group(2))
both = hist & ssp
assert len(both) >= 20, f"expected at least ~20 models with both experiments, found {len(both)}"
print(f"OK: {len(both)} models with both historical+ssp585 available for plotting")
```
