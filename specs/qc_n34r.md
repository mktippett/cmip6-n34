# Spec: qc_n34r.py

## 1. Purpose

Post-download sanity check on `n34r_data/*.nc`: flag any ensemble member
whose `n34` or `trop` time series falls outside a physically plausible SST
range, and separately flag `n34r` (a temperature *difference*, not an
absolute temperature) against its own narrower bounds. Read-only — reports
flags, takes no corrective action. Extends `qc_n34.py`'s two-check pattern
(range + near-zero-variance) to all three stored variables.

## 2. Inputs

| File | Relevant columns | Filters applied |
|------|-------------------|------------------|
| `n34r_data/*.nc` (all files, sorted) | `n34(member_id, time)`, `trop(member_id, time)`, `n34r(member_id, time)`, all K | none — every file and every `member_id` is checked |

## 3. Outputs

| Output | Contents | Format |
|--------|----------|--------|
| stdout | One `FLAG` line per failed check (file/member/variable + reason), followed by a summary: total flagged-member count and per-member reason list, or "No flags — all members passed." | text |
| `NOTES.md` | Not auto-appended (same as `qc_n34.py`) — record QC run summaries by hand if desired | — |

## 4. Algorithm

1. List all `n34r_data/*.nc` files, sorted.
2. For each file, open with cftime decoding; for each `member_id`:
   - For each of `("n34", RANGE_MIN, RANGE_MAX, STD_MIN)`, `("trop", RANGE_MIN, RANGE_MAX, STD_MIN)`, `("n34r", N34R_MIN, N34R_MAX, N34R_STD_MIN)`:
     - Compute `mn, mx, std` for that variable at that member.
     - **Range check**: flag if `mn < lo or mx > hi`.
     - **Variance check**: flag if `std < std_min`.
   - A member can fail multiple checks across multiple variables; each produces its own reason string and `FLAG` print line, but the member is recorded once in `flags` with all of its reasons.
3. After all files: print a separator, then either the total flagged-member count + per-member reason list, or "No flags — all members passed."

## 5. Constants & Scientific Rationale

| Name | Value | Why |
|------|-------|-----|
| `RANGE_MIN`, `RANGE_MAX` (n34, trop) | 250.0, 315.0 K | Identical rationale to `qc_n34.py` §5 — both `n34` and `trop` are absolute surface temperatures over the tropical Pacific/tropics, so the same wide sanity bounds apply. |
| `STD_MIN` (n34, trop) | 0.1 K | Same as `qc_n34.py` §5. |
| `N34R_MIN`, `N34R_MAX` | -8.0, 6.0 K | `n34r` is a small temperature *difference* (Niño 3.4 minus tropical mean), not an absolute temperature — the 250-315 K absolute bounds would flag every member. Set from the observed distribution across the full 248-file, 1437-member CMIP6 production run: `n34r` ranged [-5.89, 3.93] K across all members (see Synchronization Log). ±8/+6 K keeps roughly a 2 K margin beyond the observed extremes for model diversity not represented in this run, while being informative enough to catch gross processing errors. |
| `N34R_STD_MIN` | 0.2 K | Observed per-member std across the full run ranged [0.51, 1.78] K (mean 0.98 K); 0.2 K is ~2.5x below the observed minimum, wide enough to avoid false positives while still distinguishing a genuinely degenerate/near-constant series from real variability. |

## 6. Edge Cases & Error Handling

- **Both checks, three variables**: up to 6 independent flags per member (2 checks × 3 variables); all are reported together for that member.
- **No remediation**: this script only reports; flagged members are not dropped from `n34r_data/`.
- **`n34r` bounds were set from the full production run** (248 files, 1437 members, all 31 CMIP6 models) — see §5. If a future run (e.g. after adding more models or experiments) flags many members on `n34r` bounds specifically, widen `N34R_MIN`/`N34R_MAX` rather than treating it as a data error, and update this spec's Synchronization Log with the new observed range.
- **Operates on whatever exists in `n34r_data/` at run time**, same as `qc_n34.py`.

## 7. Synchronization Log

| Date | Code change | Spec updated |
|------|-------------|---------------|
| 2026-08-24 | `qc_n34r.py` created; `N34R_MIN`/`N34R_MAX`/`N34R_STD_MIN` set provisionally from a single-model smoke test | Spec created (initial) |
| 2026-08-24 | Bounds tightened to `N34R_MIN=-8.0`, `N34R_MAX=6.0`, `N34R_STD_MIN=0.2` after the full 248-file, 1437-member CMIP6 production run confirmed the observed range ([-5.89, 3.93] K) and std range ([0.51, 1.78] K) | §5 updated with observed values; provisional caveat removed from §6 |

## Verification Snippet

```python
import subprocess
from pathlib import Path

N34R_DIR = Path("n34r_data")
n_files = len(list(N34R_DIR.glob("*.nc")))
assert n_files > 0, "no n34r files found"

result = subprocess.run(
    ["/Users/tippett/miniforge3/envs/pangeo-2025/bin/python", "qc_n34r.py"],
    capture_output=True, text=True, cwd=Path(".").resolve(),
)
assert result.returncode == 0, result.stderr
assert f"Checking {n_files} files" in result.stdout
assert ("No flags — all members passed." in result.stdout
        or "Total flagged members:" in result.stdout)

print(result.stdout.splitlines()[0])
print(result.stdout.strip().splitlines()[-1])
```
