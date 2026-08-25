# Spec: qc_lens2r.py

## 1. Purpose

Post-download sanity check on `lens2_n34r_data/*.nc`, identical checks and
thresholds to `qc_n34r.py`, adapted for the CESM2-LE relative-index output.
See `specs/qc_n34r.md` for the full rationale — not repeated here.

## 2. Inputs

| File | Relevant columns | Filters applied |
|------|-------------------|------------------|
| `lens2_n34r_data/*.nc` (all 4 files, sorted) | `n34(member_id, time)`, `trop(member_id, time)`, `n34r(member_id, time)`, all K | none |

## 3. Outputs

| Output | Contents | Format |
|--------|----------|--------|
| stdout | Same format as `qc_n34r.py` | text |

## 4. Algorithm

Identical to `qc_n34r.py` §4, operating on `lens2_n34r_data/` instead of
`n34r_data/`.

## 5. Constants & Scientific Rationale

Identical to `qc_n34r.py` §5 (`RANGE_MIN`/`RANGE_MAX`/`STD_MIN` for `n34`,
`trop`; `N34R_MIN`/`N34R_MAX`/`N34R_STD_MIN` for `n34r`, provisional pending
the full production run).

## 6. Edge Cases & Error Handling

Identical to `qc_n34r.py` §6.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|---------------|
| 2026-08-24 | `qc_lens2r.py` created | Spec created (initial) |

## Verification Snippet

```python
import subprocess
from pathlib import Path

N34R_DIR = Path("lens2_n34r_data")
n_files = len(list(N34R_DIR.glob("*.nc")))
assert n_files > 0, "no lens2 n34r files found"

result = subprocess.run(
    ["/Users/tippett/miniforge3/envs/pangeo-2025/bin/python", "qc_lens2r.py"],
    capture_output=True, text=True, cwd=Path(".").resolve(),
)
assert result.returncode == 0, result.stderr
assert f"Checking {n_files} files" in result.stdout
assert ("No flags — all members passed." in result.stdout
        or "Total flagged members:" in result.stdout)

print(result.stdout.splitlines()[0])
print(result.stdout.strip().splitlines()[-1])
```
