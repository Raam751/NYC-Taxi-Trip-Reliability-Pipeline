# Demo notes (3–5 minutes)

A tight script for the recorded walkthrough. Screen-share the repo + one live run.

## 0. One-line framing (15s)
"This pipeline turns messy NYC taxi data into metrics leadership can trust — and,
just as important, tells them when *not* to trust a month."

## 1. The problem & KPI (30s)
- Client = taxi fleet ops. Data is self-reported by meters, so it's messy.
- KPI: **fleet efficiency & data trust** — can we rely on this month, and where/
  when is the fleet slow or unreliable?

## 2. Sources & retrieval (45s) — open `docs/source_map.md`
- Two sources: monthly trip **Parquet** + zone-lookup **CSV**.
- Two retrieval modes: **files over HTTP** and **DuckDB SQL** over those files.
- Completeness isn't assumed: I compare the Parquet footer row count to what
  DuckDB actually reads; a mismatch fails the run. Provenance in `raw/manifest.json`.

## 3. Live run (60s) — terminal
```bash
.venv/bin/python -m src.pipeline --period 2024-01
```
- Point out the timed stages and the "90.61% valid" line.
- Then show the guardrail: `--min-valid-rate 0.99` fails the run on purpose.

## 4. Validation, not silent cleaning (45s) — open the DQ report
- 11 business rules; rejected rows are **quarantined with a reason**, not deleted.
- `outputs/data_quality_report_2024-01.csv`: biggest reason is bad passenger
  count (5.8%), then implausible speed (2.2%).

## 5. THE JUDGEMENT CALL (60s) — the part they're grading
- Headline median speed ≈ **9.6 mph**. On its own that's misleading.
- Open `outputs/trips_by_borough_2024-01.csv`: **Manhattan 10.8 min @ 9.2 mph**
  (congestion) vs **Queens 30.9 min @ 24.0 mph** (airport runs).
- "A single citywide speed hides two different operating regimes, so I always
  pair the headline with the borough breakdown. That's the FDE call: I chose to
  report a number *with the context that makes it safe to act on*, instead of a
  clean-looking average that would misdirect where to add supply."

## 6. Dependability & close (30s)
- Rerun reuses the cached raw file (SHA-256 match); `--force` re-downloads.
- Ran for both 2024-01 and 2024-02 — same code, one flag, monthly repeatable.
- "From messy client files to a trustworthy, repeatable path to a decision."

## The single judgement call to name if asked
Reporting median trip speed **only alongside the pickup-borough breakdown**,
because the citywide median conflates congested Manhattan trips with fast Queens
airport runs — acting on the blended number would put supply in the wrong place.
