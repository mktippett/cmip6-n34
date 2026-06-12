# AR6 Validation vs ATLAS

**Date:** 2026-06-11  
**Reference:** ATLAS precomputed `tas` (land-sea), AWI-CM-1-1-MR historical r1i1p1f1  
**Source:** https://github.com/SantanderMetGroup/ATLAS/tree/devel/datasets-aggregated-regionally  
**Method:** ATLAS uses CDO conservative remapping to 1° before averaging; ours averages on the native atmospheric grid. Both use latitude-weighted means.

**Regions:** all 58 AR6 WGI reference regions (46 land + 12 ocean), via `regionmask.defined_regions.ar6.all`. ATLAS's land-sea CSV covers all 58 too, so all regions are validated here (previously only the 46 land regions).

**Columns:** Diff is the bias between climatological means (ours minus ATLAS; ATLAS 1850-2014, ours 1851-2014). RMSE and Corr are computed from the full monthly time series over the 1851-2014 overlap (1968 months).

**Summary:** Mean |diff| = 0.097 °C, max 0.618 °C (EAN)  |  Mean RMSE = 0.113 °C, max 0.631 °C (EAN)  |  Mean corr = 0.9999, min 0.9987 (SEAF)

| Region | ATLAS (°C) | Ours (°C) | Diff | RMSE | Corr |
|--------|----------:|----------:|-----:|-----:|-----:|
| GIC | -11.33 | -11.20 | 0.13 | 0.136 | 1.0000 |
| NWN | -4.49 | -4.38 | 0.11 | 0.114 | 1.0000 |
| NEN | -5.18 | -4.98 | 0.19 | 0.205 | 1.0000 |
| WNA | 8.59 | 8.86 | 0.27 | 0.277 | 1.0000 |
| CNA | 13.63 | 13.95 | 0.32 | 0.337 | 1.0000 |
| ENA | 12.57 | 12.63 | 0.07 | 0.080 | 1.0000 |
| NCA | 20.88 | 20.98 | 0.10 | 0.107 | 0.9999 |
| SCA | 26.10 | 26.08 | -0.03 | 0.031 | 1.0000 |
| CAR | 26.48 | 26.48 | -0.00 | 0.029 | 0.9999 |
| NWS | 21.30 | 21.31 | 0.01 | 0.017 | 0.9999 |
| NSA | 25.75 | 25.74 | -0.01 | 0.025 | 0.9998 |
| NES | 24.07 | 24.11 | 0.05 | 0.070 | 0.9990 |
| SAM | 21.82 | 21.69 | -0.13 | 0.133 | 0.9999 |
| SWS | 11.93 | 12.03 | 0.09 | 0.092 | 1.0000 |
| SES | 18.57 | 18.64 | 0.06 | 0.075 | 1.0000 |
| SSA | 6.86 | 6.74 | -0.12 | 0.129 | 1.0000 |
| NEU | 4.01 | 3.99 | -0.02 | 0.027 | 1.0000 |
| WCE | 8.44 | 8.50 | 0.06 | 0.072 | 1.0000 |
| EEU | 5.15 | 5.06 | -0.09 | 0.101 | 1.0000 |
| MED | 16.84 | 16.89 | 0.06 | 0.055 | 1.0000 |
| SAH | 25.29 | 25.30 | 0.01 | 0.027 | 1.0000 |
| WAF | 27.25 | 27.26 | 0.00 | 0.021 | 1.0000 |
| CAF | 25.30 | 25.24 | -0.06 | 0.071 | 0.9999 |
| NEAF | 26.04 | 26.08 | 0.04 | 0.039 | 0.9999 |
| SEAF | 24.15 | 24.05 | -0.10 | 0.117 | 0.9987 |
| WSAF | 19.52 | 19.42 | -0.10 | 0.111 | 0.9998 |
| ESAF | 21.92 | 21.86 | -0.07 | 0.081 | 1.0000 |
| MDG | 24.32 | 24.29 | -0.02 | 0.029 | 1.0000 |
| RAR | -10.35 | -10.48 | -0.13 | 0.162 | 1.0000 |
| WSB | 2.53 | 2.38 | -0.15 | 0.166 | 1.0000 |
| ESB | -2.81 | -2.87 | -0.06 | 0.090 | 1.0000 |
| RFE | -2.89 | -3.02 | -0.13 | 0.187 | 1.0000 |
| WCA | 15.81 | 15.81 | 0.00 | 0.047 | 1.0000 |
| ECA | 7.57 | 7.95 | 0.38 | 0.395 | 1.0000 |
| TIB | -0.92 | -1.10 | -0.19 | 0.203 | 1.0000 |
| EAS | 14.99 | 14.68 | -0.31 | 0.336 | 1.0000 |
| ARP | 25.78 | 25.79 | 0.02 | 0.050 | 1.0000 |
| SAS | 24.16 | 24.12 | -0.04 | 0.078 | 1.0000 |
| SEA | 26.57 | 26.59 | 0.02 | 0.036 | 0.9995 |
| NAU | 27.13 | 27.17 | 0.04 | 0.059 | 0.9999 |
| CAU | 23.55 | 23.72 | 0.17 | 0.170 | 1.0000 |
| EAU | 20.76 | 20.80 | 0.04 | 0.200 | 0.9998 |
| SAU | 14.79 | 14.81 | 0.02 | 0.021 | 1.0000 |
| NZ | 14.55 | 14.71 | 0.17 | 0.168 | 1.0000 |
| EAN | -29.75 | -29.14 | 0.62 | 0.631 | 1.0000 |
| WAN | -18.83 | -18.93 | -0.11 | 0.121 | 1.0000 |
| ARO | -13.62 | -13.60 | 0.02 | 0.029 | 1.0000 |
| NPO | 19.78 | 19.92 | 0.14 | 0.142 | 1.0000 |
| EPO | 26.05 | 26.02 | -0.03 | 0.039 | 0.9998 |
| SPO | 17.94 | 17.87 | -0.07 | 0.077 | 1.0000 |
| NAO | 19.01 | 19.08 | 0.07 | 0.067 | 1.0000 |
| EAO | 26.17 | 26.15 | -0.01 | 0.048 | 0.9997 |
| SAO | 17.78 | 17.75 | -0.03 | 0.034 | 1.0000 |
| ARS | 26.21 | 26.28 | 0.07 | 0.093 | 0.9993 |
| BOB | 27.41 | 27.41 | 0.00 | 0.052 | 0.9994 |
| EIO | 27.26 | 27.26 | -0.00 | 0.014 | 0.9998 |
| SIO | 22.04 | 21.87 | -0.17 | 0.172 | 1.0000 |
| SOO | 2.22 | 2.17 | -0.06 | 0.060 | 1.0000 |

The EAN outlier (0.62 °C diff, 0.631 °C RMSE) reflects different treatment of the Antarctic ice sheet boundary between conservative remapping and native-grid averaging. All other regions (land and ocean) are within 0.4 °C diff; the 12 ocean regions are all within 0.17 °C. Correlations are ≥0.999 everywhere except SEAF (0.9987), confirming the two time series track each other closely month-to-month — RMSE is dominated by the mean offset (bias) rather than timing or variability mismatches.
