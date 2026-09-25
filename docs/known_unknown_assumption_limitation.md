# Known · Unknown · Assumption · Limitation

A deliberate statement of what this pipeline does and does not establish, so its
metrics are used with the right amount of confidence.

## Known (established from the data / checks)

- The 2024-01 yellow-taxi file contains **2,964,624** trip rows; the count is
  verified (Parquet footer == DuckDB read), so ingestion is complete.
- **90.6%** of rows pass all 11 business rules; the rest are quarantined with a
  recorded reason (see `outputs/data_quality_report_2024-01.csv`).
- Median validated trip: **11.6 min**, **9.6 mph**; P90 duration **28.8 min**.
- Trip speed varies sharply by borough (Manhattan ≈9 mph vs Queens ≈24 mph).

## Unknown (not answerable from these sources)

- **Root cause of slow trips** — congestion, weather, driver behaviour, and
  road works are not in the data.
- **Whether quarantined rows are truly bad** — some may be rare-but-real trips;
  we exclude them from metrics but preserve them for review.
- **Demand we never saw** — unmet demand (riders who gave up) is not recorded.
- **Trip identity** — with no trip ID, exact duplicates cannot be distinguished
  from genuinely similar trips.

## Assumptions (explicit, revisable)

- A trustworthy metered trip is **1–180 min**, **>0 and ≤100 mi**, average speed
  **1–70 mph**, **1–6 passengers**, non-negative amounts, real zone (1–263), and
  a pickup **inside the target month**. Thresholds are in `src/config.py`.
- Pickup-borough is the right grain for operational planning (where to position
  supply), so `fact_trips` joins `dim_zone` on the **pickup** location.
- Peak hours are weekday-style rush windows **07–09 and 16–19**.
- Timestamps are in the file's local time; no timezone conversion is applied.

## Limitations (scope boundaries)

- **One taxi type, one month at a time.** Yellow taxis only; green/FHV excluded.
  The pipeline is built to rerun per month, not to backfill history in one shot.
- **Structural explanation only.** Metrics describe *what* happened by borough
  and hour, not *why*; no external context is joined.
- **Raw Parquet is not committed** (≈48 MB). It is reproduced on demand via
  `ingest`; the committed `manifest.json` records size + SHA-256 for provenance.
- **Thresholds are judgement calls.** They are defensible and documented, but a
  domain expert could tune them; changing them changes the valid-trip rate.
