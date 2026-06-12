# Spec: qc_n34.py

## 1. Purpose

Post-download sanity check on `n34_data/*.nc`: flag any ensemble member whose
Niño 3.4 time series falls outside a physically plausible SST range, or is
suspiciously near-constant (a likely sign of a processing error, degenerate
field, or unit mismatch) rather than real seasonal/interannual variability.
Read-only — reports flags, takes no corrective action.

## 2. Inputs

| File | Relevant columns | Filters applied |
|------|-------------------|------------------|
| `n34_data/*.nc` (all files, sorted) | `n34(member_id, time)`, K | none — every file and every `member_id` is checked |

## 3. Outputs

| Output | Contents | Format |
|--------|----------|--------|
| stdout | One `FLAG` line per failed check (file/member + reason), followed by a summary: total flagged-member count and per-member reason list, or "No flags — all members passed." | text |
| `NOTES.md` (manual entry) | QC run summaries are added by hand, e.g. "248 files, 0 flags" (2026-05-19) | markdown — **not auto-appended**, unlike `cmip6_n34.py`/`cmip6_ar6.py` |

## 4. Algorithm

1. List all `n34_data/*.nc` files, sorted.
2. For each file, open with cftime decoding; for each `member_id`:
   - Extract `ts = ds.n34.sel(member_id=member_id)`.
   - Compute `mn, mx, std = float(ts.min()), float(ts.max()), float(ts.std())`.
   - **Range check**: flag if `mn < RANGE_MIN or mx > RANGE_MAX`.
   - **Variance check**: flag if `std < STD_MIN`.
   - A member can fail both checks; each failed check produces its own reason string and its own `FLAG` print line, but the member is recorded once in `flags` with all of its reasons.
3. After all files: print a separator, then either the total flagged-member count + per-member reason list, or "No flags — all members passed." if `flags` is empty.

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| `RANGE_MIN` | 250.0 K (-23.15 °C) | Deliberately wide lower sanity bound — real Niño 3.4 SST is typically ~294-303 K (21-30 °C); 250 K is far below any plausible tropical Pacific SST and is meant to catch gross unit/processing errors (e.g. a Celsius value left unconverted, a fill value), not to bound real ENSO variability. |
| `RANGE_MAX` | 315.0 K (41.85 °C) | Symmetric wide upper sanity bound, same rationale as `RANGE_MIN`. |
| `STD_MIN` | 0.1 K | Flags a member whose full time series is essentially constant. Real Niño 3.4 series have seasonal-cycle + ENSO-driven std well above this (observed std across current `n34_data/` is O(1-3) K); a std below 0.1 K indicates a degenerate field (e.g. a coordinate or scalar broadcast in place of the actual SST field) rather than real variability. |

## 6. Edge Cases & Error Handling

- **Both checks can fire for one member**: range and variance failures are independent and both reported if both occur.
- **No remediation**: this script only reports; flagged members are not dropped or excluded from `n34_data/` — any follow-up (re-download, exclude from analysis) is a manual decision.
- **Operates on whatever exists in `n34_data/` at run time** — if run against a partial/in-progress download, it only checks the files written so far (no error for "incomplete" runs).
- **Per-member, not per-file**: a file with 5 members and 1 bad member produces 1 flag for that file, not a whole-file failure — the other 4 members are reported clean.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|--------------|
| 2026-06-12 | — | Spec created (initial); reflects code as of commit `53e4eea` (unchanged since initial commit) |

## Verification Snippet

```python
import subprocess
from pathlib import Path

N34_DIR = Path("n34_data")
n_files = len(list(N34_DIR.glob("*.nc")))
assert n_files > 0, "no n34 files found"

result = subprocess.run(
    ["/Users/tippett/miniforge3/envs/pangeo-2025/bin/python", "qc_n34.py"],
    capture_output=True, text=True, cwd=Path(".").resolve(),  # run from project root
)
assert result.returncode == 0, result.stderr
assert f"Checking {n_files} files" in result.stdout
assert ("No flags — all members passed." in result.stdout
        or "Total flagged members:" in result.stdout)

print(result.stdout.splitlines()[0])
print(result.stdout.strip().splitlines()[-1])
```
