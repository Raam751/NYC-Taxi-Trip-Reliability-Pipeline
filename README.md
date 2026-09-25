# NYC Yellow Taxi — Trip Reliability Pipeline (FDE Assignment 2, Track B)

A small, explainable, **dependable** pipeline that turns messy NYC TLC yellow-taxi
data into trustworthy operational metrics. It goes from raw client files to a
business decision, not just "I analysed a dataset."

```
raw inputs  ──▶  ingest  ──▶  validate  ──▶  model  ──▶  metrics  ──▶  outputs/
(Parquet+CSV)   (2 modes,     (11 rules,     (star      (5 KPI       (CSV + evidence
                completeness)  quarantine)    schema)    metrics)      + DQ report)
```

## The problem (who / why)

**Client:** a yellow-taxi fleet operations team.
**Users/stakeholders:** operations planners (where/when to position cars),
a data lead (can we trust the numbers), and finance (fare integrity).
**Situation:** trip data is fragmented and self-reported by meters, so leadership
does not know whether the monthly numbers can be trusted or what they say.

**Project KPI — Fleet efficiency & data trust:** *Can we rely on this month's
trip data, and where/when is the fleet running slowly or unreliably?*

## What the output supports (the decision)

The pipeline answers three operational questions each month:
1. **Is the data trustworthy?** — valid trip rate + a per-rule quality report.
2. **How efficient/reliable are trips?** — median & P90 duration, median speed.
3. **Where/when should supply go?** — peak-hour share + a borough breakdown.

## Latest run — Yellow Taxi 2024-01

| Metric | Value | Unit | Decision it supports |
|---|---:|---|---|
| M1 Valid trip rate | 90.61 | % | Data trust: is the month usable |
| M2 Median trip duration | 11.62 | min | Baseline trip length |
| M3 Median trip speed | 9.63 | mph | Congestion / efficiency |
| M4 P90 trip duration | 28.78 | min | Reliability tail |
| M5 Peak-hour trip share | 38.04 | % | Staffing / supply timing |

Ingested **2,964,624** raw trips; **2,686,243 (90.6%)** passed all rules and were
used for metrics; **278,381** were quarantined with reasons.

**Headline insight (the FDE judgement call):** the median trip speed of ~9.6 mph
is a Manhattan story. The borough breakdown shows Manhattan trips are short and
slow (10.8 min @ 9.2 mph — congestion) while Queens trips are long and fast
(30.9 min @ 24.0 mph — airport runs). Reporting a single citywide "speed" would
hide two completely different operating regimes, so the metric is always paired
with the borough breakdown.

## Two retrieval modes (Class 5)

- **Mode A — Files over HTTP:** the monthly trip **Parquet** and the taxi-zone
  **CSV** are downloaded into `raw/` and treated as immutable.
- **Mode B — SQL:** every downstream stage reads those raw files through
  **DuckDB SQL** (`read_parquet` / `read_csv_auto`) rather than re-parsing them.

**Completeness check:** the trip file's row count from its Parquet footer metadata
is compared against the count DuckDB actually reads; a mismatch fails the run.
Each input's size + SHA-256 is recorded in `raw/manifest.json`.

## Validation, not silent cleaning (Class 6)

Eleven business rules define a trustworthy metered trip. Each rejected row is
**quarantined with the first rule it failed** (`build/quarantine_*.parquet`), and
every rule's independent failure count is written to
`outputs/data_quality_report_*.csv`. Nothing is dropped invisibly.

Top rejection reasons for 2024-01: bad passenger count (5.8%), implausible average
speed (2.2%), non-positive distance (2.0%), negative amounts (1.3%). Thresholds
live in `src/config.py` and are documented there.

## How to run

```bash
# 1. Create the environment
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 2. Run the pipeline for a month (downloads raw inputs on first run)
.venv/bin/python -m src.pipeline --period 2024-01

# Useful flags
.venv/bin/python -m src.pipeline --period 2024-02 --force            # re-download raw
.venv/bin/python -m src.pipeline --period 2024-01 --min-valid-rate 0.85  # trust floor
```

Outputs appear in `outputs/`; logs in `logs/pipeline_<period>.log`.

### Optional demo dashboard

A lightweight Streamlit app gives a visual view of the results. It is **read-only
over `outputs/`** — it never recomputes metrics or touches raw data, so the
pipeline stays the single source of truth.

```bash
.venv/bin/streamlit run app.py
```

It shows the five KPI cards, a data-trust banner, a bar chart of why rows were
quarantined, and the borough scatter that carries the judgement call (speed vs
duration, sized by trips). Rerun the pipeline for another month and reload to
switch periods.

## Dependability (Class 8)

- **Repeatable:** one command reproduces every output from raw inputs.
- **Idempotent reruns:** cached raw files are reused when their SHA-256 matches
  the manifest; outputs are overwritten deterministically. `--force` re-downloads.
- **Observable:** each stage is timed and logged to console + `logs/`.
- **Fails safe:** any stage error is logged with context and the process exits
  non-zero. Guardrails also fail the run if there are **zero valid rows** or the
  **valid rate falls below `--min-valid-rate`** (default 0.80) — the pipeline
  refuses to publish metrics nobody should trust.

## Repository layout

```
nyc-tlc-pipeline/
├── README.md
├── requirements.txt
├── src/
│   ├── config.py      # paths, source URLs, validation thresholds
│   ├── ingest.py      # download + completeness + manifest (Modes A & B)
│   ├── validate.py    # 11 rules → clean + quarantine + DQ report
│   ├── model.py       # fact_trips ⋈ dim_zone (star schema)
│   ├── metrics.py     # 5 KPI metrics + borough breakdown + evidence table
│   ├── pipeline.py    # orchestrator: logging, reruns, guardrails
│   └── utils.py       # logging, hashing
├── docs/
│   ├── source_map.md  # business questions → sources (Class 4)
│   ├── data_model.md  # workflow + star-schema diagrams (Class 7)
│   └── known_unknown_assumption_limitation.md
├── raw/               # immutable inputs + manifest.json (parquet gitignored)
├── build/             # intermediate artifacts (gitignored)
├── outputs/           # metrics, DQ report, evidence, breakdown
└── logs/
```

## Data source & attribution

NYC Taxi & Limousine Commission (TLC) Trip Record Data, distributed publicly by
the City of New York. Trip records: `yellow_tripdata_YYYY-MM.parquet`; zone
lookup: `taxi_zone_lookup.csv`.

See [`docs/known_unknown_assumption_limitation.md`](docs/known_unknown_assumption_limitation.md)
for what is known, unknown, assumed, and out of scope.
