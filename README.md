# CMIP6 Niño 3.4 and AR6 Regional Averages

Two parallel pipelines compute the same two diagnostics — the Niño 3.4 index and IPCC AR6 regional temperature averages — from different model archives:

- **CMIP6 pipeline** (`cmip6_*.py`): multi-model archive on Google Cloud Storage, ~34 models × 8 experiments
- **CESM2-LE pipeline** (`lens2_*.py`): NCAR Large Ensemble (LENS2) on AWS S3, 100 members × 2 experiments, split into two 50-member forcing variants

Both pipelines compute:
- **Niño 3.4 index** — latitude-weighted mean of surface temperature over 190–240°E, 5°S–5°N
- **Relative Niño 3.4 index** — Niño 3.4 minus the tropical-mean (20°S–20°N, ocean-only) surface temperature, raw and unscaled (no climatology removed, no variance rescaling)
- **IPCC AR6 regional averages** — latitude-weighted means over all 58 AR6 WGI reference regions (46 land + 12 ocean)

---

## CMIP6 pipeline

Source: Pangeo CMIP6 catalog on Google Cloud (`gs://cmip6-pds`), anonymous access.

Variables: `ts` (Amon) for Niño 3.4; `tas` (Amon) for AR6 regions.

Models must provide all eight experiments: `historical`, `ssp126`, `ssp245`, `ssp370`, `ssp585`, `abrupt-4xCO2`, `piControl`, `1pctCO2`. NIMS-KMA excluded (time format incompatibility). `cmip6_utils.py` must be co-located with the download scripts.

### Usage

```bash
python cmip6_n34.py > run_n34.log 2>&1
python cmip6_n34r.py > run_n34r.log 2>&1
python cmip6_ar6.py > run_ar6.log 2>&1

# Restrict to one institution or model (restarts / testing)
python cmip6_n34.py --institution NCAR
python cmip6_n34r.py --institution NCAR
python cmip6_ar6.py --institution EC-Earth-Consortium --source EC-Earth3

python qc_n34.py                          # QC check on n34 files
python qc_n34r.py                         # QC check on n34r files
python test_ar6.py                        # validate AR6 output against ATLAS
python compare_outputs.py n34_data/ /tmp/ # diff two output directories
```

### Output

`n34_data/n34_{institution_id}_{source_id}_{experiment_id}.nc`
- `n34 (member_id, time)` — Niño 3.4 index, K

`n34r_data/n34r_{institution_id}_{source_id}_{experiment_id}.nc`
- `n34 (member_id, time)`, `trop (member_id, time)`, `n34r (member_id, time)` — all K, raw (no anomaly/climatology removed, no rescaling); `n34` here is identical to `n34_data/`'s `n34`; `trop` is the ocean-masked tropical-mean (20°S–20°N, all lon); `n34r = n34 − trop`

`ar6_data/ar6_{institution_id}_{source_id}_{experiment_id}.nc`
- `tas (member_id, time, region)` — 2 m temperature, K; `abbrevs` and `names` non-dim coords

Scalar coords on each file: `experiment_id`, `source_id`, `institution_id`.

---

## CESM2-LE (LENS2) pipeline

Source: AWS S3 `s3://ncar-cesm2-lens` (us-west-2, anonymous), Zarr format. Requires `s3fs` in the Python environment.

Two forcing variants in separate zarr stores, 50 members each:
- **`cmip6`** — standard CMIP6 biomass burning emissions (member IDs: `r*p1f1`)
- **`smbb`** — smoothed biomass burning, 11-yr running mean applied to 1990–2020 fluxes (member IDs: `r*p1f2`)

Two experiments: `historical` (1850–2014) and `ssp370` (2015–2100). ssp370 is the only available future scenario.

Variables: `TS` for Niño 3.4; `TREFHT` (2 m reference-height temperature) for AR6 regions.

`lens2_utils.py` must be co-located with the download scripts.

### Usage

```bash
python lens2_n34.py > run_lens2_n34.log 2>&1
python lens2_n34r.py > run_lens2_n34r.log 2>&1
python lens2_ar6.py > run_lens2_ar6.log 2>&1

# Restrict to one variant or experiment (restarts / testing)
python lens2_n34.py --variant cmip6 --experiment historical
python lens2_n34r.py --variant cmip6 --experiment historical
python lens2_ar6.py --variant smbb

python qc_lens2.py   # QC check on lens2 n34 files
python qc_lens2r.py  # QC check on lens2 n34r files
```

### Output

`lens2_n34_data/n34_CESM2-LE_{variant}_{experiment}.nc`
- `n34 (member_id, time)` — Niño 3.4 index, K; source variable `TS`

`lens2_n34r_data/n34r_CESM2-LE_{variant}_{experiment}.nc`
- `n34 (member_id, time)`, `trop (member_id, time)`, `n34r (member_id, time)` — all K, raw (no anomaly/climatology removed, no rescaling); source variable `TS`

`lens2_ar6_data/ar6_CESM2-LE_{variant}_{experiment}.nc`
- `tas (member_id, time, region)` — 2 m temperature, K; `abbrevs` and `names` non-dim coords; source variable `TREFHT`

Scalar vars on each file: `forcing_variant`, `experiment`, `source_id="CESM2-LE"`.

---

## Common conventions

Both pipelines share these design conventions (see `specs/` for full details):

- **Variable split:** surface temperature (`ts`/`TS`) for Niño 3.4; 2 m air temperature (`tas`/`TREFHT`) for AR6 regions — to match the ATLAS precomputed reference dataset.
- **Relative Niño 3.4 index (`n34r`):** Niño 3.4 minus the tropical-mean (20°S–20°N, all longitudes, ocean-only via `regionmask` land mask) surface temperature — removes the tropics-wide warming trend to isolate ENSO variability (van Oldenborgh et al. 2021; L'Heureux, Tippett et al. 2024). Output is **raw and unscaled**: no climatology/anomaly removal, no variance-matching rescaling — deliberately, so downstream work can explore alternative base periods and scalings from the same raw quantities. See `specs/cmip6_n34r.md` for the full derivation, including measured evidence for using `ts` + an ocean mask instead of `tos`.
- **AR6 regions:** `regionmask.defined_regions.ar6.all` — 58 WGI reference regions (46 land + 12 ocean), latitude-weighted.
- **NaN handling:** any NaN in a member's output drops that member entirely (no partial output); dropped members are listed in the run log and `NOTES.md`.
- **Restarts:** existing output files are skipped; re-run with `--institution`/`--source` (CMIP6) or `--variant`/`--experiment` (LENS2) after deleting the target file.
- **Atomic writes:** output is written to `<filename>.tmp` first, then renamed — no corrupt partial files on failure.
- **QC thresholds:** range 250–315 K, standard deviation ≥ 0.1 K.
