# CMIP6 Niño 3.4 Download

Downloads monthly surface temperature (`ts`, Amon) from CMIP6 models on Google Cloud Storage, computes the Niño 3.4 index (190–240°E, 5°S–5°N, latitude-weighted mean), and saves one NetCDF per model/experiment to `n34_data/`.

## Requirements

Models must have all eight experiments: `historical`, `ssp126`, `ssp245`, `ssp370`, `ssp585`, `abrupt-4xCO2`, `piControl`, `1pctCO2`. NIMS-KMA is excluded (time format incompatibility).

## Usage

```bash
# Download (long-running — pipe to log)
python cmip6_n34.py > run.log 2>&1

# QC check after download
python qc_n34.py
```

## Output

`n34_data/n34_{institution_id}_{source_id}_{experiment_id}.nc`

Each file contains:
- `n34 (member_id, time)` — Niño 3.4 index in K
- scalar coordinates: `experiment_id`, `source_id`, `institution_id`

Members with any NaN values are dropped and listed in the download log. `qc_n34.py` flags members with values outside 250–315 K or standard deviation below 0.1 K.
