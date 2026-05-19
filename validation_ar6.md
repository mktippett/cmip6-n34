# AR6 Validation vs ATLAS

**Date:** 2026-05-19  
**Reference:** ATLAS precomputed `tas` (land-sea), AWI-CM-1-1-MR historical r1i1p1f1  
**Source:** https://github.com/SantanderMetGroup/ATLAS/tree/devel/datasets-aggregated-regionally  
**Method:** ATLAS uses CDO conservative remapping to 1° before averaging; ours averages on the native atmospheric grid. Both use latitude-weighted means.

**Summary:** Mean |diff| = 0.107 °C  |  Max |diff| = 0.618 °C (EAN)

| Region | ATLAS (°C) | Ours (°C) | Diff |
|--------|----------:|----------:|-----:|
| GIC | -11.33 | -11.20 | 0.13 |
| NWN | -4.49 | -4.38 | 0.11 |
| NEN | -5.18 | -4.98 | 0.19 |
| WNA | 8.59 | 8.86 | 0.27 |
| CNA | 13.63 | 13.95 | 0.32 |
| ENA | 12.57 | 12.63 | 0.07 |
| NCA | 20.88 | 20.98 | 0.10 |
| SCA | 26.10 | 26.08 | -0.03 |
| CAR | 26.48 | 26.47 | -0.01 |
| NWS | 21.30 | 21.31 | 0.01 |
| NSA | 25.75 | 25.74 | -0.01 |
| NES | 24.07 | 24.11 | 0.05 |
| SAM | 21.82 | 21.69 | -0.13 |
| SWS | 11.93 | 12.03 | 0.09 |
| SES | 18.57 | 18.64 | 0.06 |
| SSA | 6.86 | 6.74 | -0.12 |
| NEU | 4.01 | 3.99 | -0.02 |
| WCE | 8.44 | 8.50 | 0.06 |
| EEU | 5.15 | 5.06 | -0.09 |
| MED | 16.84 | 16.89 | 0.06 |
| SAH | 25.29 | 25.30 | 0.01 |
| WAF | 27.25 | 27.26 | 0.00 |
| CAF | 25.30 | 25.24 | -0.06 |
| NEAF | 26.04 | 26.08 | 0.04 |
| SEAF | 24.15 | 24.05 | -0.10 |
| WSAF | 19.52 | 19.42 | -0.10 |
| ESAF | 21.92 | 21.86 | -0.07 |
| MDG | 24.32 | 24.29 | -0.02 |
| RAR | -10.35 | -10.48 | -0.13 |
| WSB | 2.53 | 2.38 | -0.15 |
| ESB | -2.81 | -2.87 | -0.06 |
| RFE | -2.89 | -3.02 | -0.13 |
| WCA | 15.81 | 15.81 | 0.00 |
| ECA | 7.57 | 7.95 | 0.38 |
| TIB | -0.92 | -1.10 | -0.19 |
| EAS | 14.99 | 14.68 | -0.31 |
| ARP | 25.78 | 25.79 | 0.02 |
| SAS | 24.16 | 24.12 | -0.04 |
| SEA | 26.57 | 26.59 | 0.02 |
| NAU | 27.13 | 27.17 | 0.04 |
| CAU | 23.55 | 23.72 | 0.17 |
| EAU | 20.76 | 20.80 | 0.04 |
| SAU | 14.79 | 14.81 | 0.02 |
| NZ | 14.55 | 14.71 | 0.17 |
| EAN | -29.75 | -29.14 | 0.62 |
| WAN | -18.83 | -18.93 | -0.11 |

The EAN outlier (0.62 °C) reflects different treatment of the Antarctic ice sheet boundary between conservative remapping and native-grid averaging. All other regions are within 0.4 °C.
