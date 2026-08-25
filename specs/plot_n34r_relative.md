# Spec: plot_n34r_relative.py

## 1. Purpose

Visualize the **scaled relative Niño 3.4 index** across every CMIP6 model that
has both `historical` and `ssp585` in `n34r_data/` (see `specs/cmip6_n34r.md`),
as a single spaghetti plot spanning 1850-2100, with a shaded band quantifying
how much the models disagree and how that disagreement evolves under ssp585
warming.

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
| `n34r_relative_spaghetti.pdf` | One axes: one gray line per model (scaled relative Niño 3.4 anomaly, 1850-2100, no legend) + a steelblue shaded spread band + dashed reference lines at y=0 and the 2014/2015 join | matplotlib, 150 dpi |
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
5. Title/subtitle carries the methodology (base period, scaling formula,
   band definition, window length) since there is no legend and no caption.
6. Save both `.pdf` and `.png`.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| `CLIM_START`, `CLIM_END` | 1985, 2014 | User-specified anomaly base period; also used (same period) as the base for the variance-matching scale factor — confirmed explicitly with the user rather than assumed, since the request separately said "1985-2015" for the scaling factor, which would have pulled one year from ssp585 instead of historical. |
| `PLOT_END_YEAR` | 2100 | ssp585 archives run to 2300 for some models (e.g. ACCESS-CM2, CanESM5) and stop at 2100 for most others; capped at 2100 so every model contributes over the same x-range. |
| `HIST_END_YEAR`, `SSP_START_YEAR` | 2014, 2015 | Standard CMIP6 historical/scenario split. |
| Scale factor | `std(n34, per calendar month) / std(n34r, per calendar month)`, both over 1985-2014, both per model | User-specified formula: rescales the raw (unscaled) relative index back up to Niño-3.4-like variance, the RONI-recipe step `cmip6_n34r.py` deliberately omits from its raw output (see `specs/cmip6_n34r.md` §5). |
| Member selection | prefer `r1i1p1f1`, else lowest common member | Not a scientific choice — an implementation default to get one continuous, single-realization trajectory per model. Spot-checked on 2 models (ACCESS-CM2, UKESM1-0-LL): the 2014/2015 seam is smooth at the member level, confirming no artifact from switching physical realizations across the join. |
| Model set | all `source_id`s in `n34r_data/` with both historical+ssp585 (31 as of this session) | Changed mid-session from an initial fixed 20-model list (from a user-supplied model table) to "all models we have," per explicit user request — see Synchronization Log. |
| Band statistic | 10th-90th percentile across models, 10-yr centered rolling mean in time | Both explicitly chosen by the user (asked directly rather than assumed, since a percentile-vs-stdev and a window-length choice each materially change the figure). |
| Band computed cross-model-first, not pooled with time | — | User explicitly corrected an earlier version that pooled all months+models together within the rolling window before taking the percentile — that blends inter-model spread with each model's own ENSO-phase (interannual) variability. Computing the percentile across models at each month first, then smoothing that curve in time, isolates model disagreement. |
| Band drawn on top of the spaghetti lines (zorder above), with solid edge lines | — | An earlier version drew the band behind the lines; 31 overlapping gray lines at `alpha=0.5` fully occlude a fill sitting underneath, especially since the 10th-90th band sits exactly where line density is highest. Discovered when the user reported "I see no band" despite correct underlying values. |
| `LINE_COLOR = "0.4"` | uniform gray, no per-model color | User-specified, replacing an earlier `gist_rainbow` per-model palette — with 31 unlabeled lines a categorical palette adds no identifiable information; gray also keeps the colored band visually distinct from the model lines. |

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

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|---------------|
| 2026-08-25 | `plot_n34r_relative.py` created and iterated over one session: fixed 20-model list → scan-all-available (31 models); added variance-matching scale factor (1985-2014 base, per calendar month); added cross-model spread band (10th-90th percentile, 10-yr centered rolling mean, computed separately either side of 2014/2015); fixed FGOALS-g3 historical/ssp585 time overlap; fixed band-hidden-behind-lines rendering bug; switched line color to uniform gray; added PNG output alongside PDF | Spec created (initial) |

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
