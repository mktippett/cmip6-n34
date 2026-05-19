# CMIP6 Niño 3.4 and AR6 Regional Averages

Downloads CMIP6 surface temperature from Google Cloud Storage and computes two sets of diagnostics:

- **Niño 3.4 index** (`ts`, Amon) — latitude-weighted mean over 190–240°E, 5°S–5°N
- **IPCC AR6 regional averages** (`tas`, Amon) — latitude-weighted means over all 46 AR6 WGI reference regions

One NetCDF per model/experiment, retaining all available ensemble members.

## Requirements

Models must have all eight experiments: `historical`, `ssp126`, `ssp245`, `ssp370`, `ssp585`, `abrupt-4xCO2`, `piControl`, `1pctCO2`. NIMS-KMA is excluded (time format incompatibility).

`cmip6_utils.py` must be in the same directory — it is shared by both download scripts.

## Usage

```bash
# Download all models (long-running — pipe to log)
python cmip6_n34.py > run_n34.log 2>&1
python cmip6_ar6.py > run_ar6.log 2>&1

# Restrict to one institution or model (useful for restarts or testing)
python cmip6_n34.py --institution NCAR
python cmip6_ar6.py --institution EC-Earth-Consortium --source EC-Earth3

# QC check on n34 files after download
python qc_n34.py

# Validate ar6 output against ATLAS precomputed data (requires ar6_data/)
python test_ar6.py

# Compare two output directories (e.g. after a code change)
python compare_outputs.py n34_data/ /tmp/n34_revised/
```

Both download scripts support **restarts**: if an output file already exists it is skipped. Files are written atomically via a `.tmp` intermediate to avoid corrupt outputs on failure.

## Output

**Niño 3.4:** `n34_data/n34_{institution_id}_{source_id}_{experiment_id}.nc`
- `n34 (member_id, time)` — Niño 3.4 index in K

**AR6 regional averages:** `ar6_data/ar6_{institution_id}_{source_id}_{experiment_id}.nc`
- `tas (member_id, time, region)` — 2m temperature in K; region coordinate carries `abbrevs` and `names`

Both file types include scalar coordinates `experiment_id`, `source_id`, `institution_id`. Members with any NaN values are dropped and listed in the run log. `qc_n34.py` additionally flags members with values outside 250–315 K or standard deviation below 0.1 K.
