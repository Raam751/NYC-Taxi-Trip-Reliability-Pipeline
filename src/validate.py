"""Stage 2 - Profile & validate.

Philosophy (Class 6): we do NOT silently clean data. Every row that fails a
business rule is moved to a quarantine table tagged with the *first* rule it
failed, and every rule's independent failure count is written to a data-quality
report. Downstream metrics run only on rows that pass all rules, but nothing is
thrown away invisibly - the quarantine Parquet keeps the rejected rows for audit.

Each rule is a business statement about what a trustworthy metered trip looks
like, expressed as a SQL predicate that is TRUE when the row is INVALID.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from . import config

# --------------------------------------------------------------------------- #
# Derived columns shared by rules and later stages.
# duration_min: trip length in minutes; speed_mph: average speed over the trip.
# --------------------------------------------------------------------------- #
_DERIVE_SQL = f"""
CREATE OR REPLACE TABLE trips_derived AS
SELECT
    *,
    date_diff('second', {config.PICKUP_TS}, {config.DROPOFF_TS}) / 60.0 AS duration_min,
    CASE
        WHEN date_diff('second', {config.PICKUP_TS}, {config.DROPOFF_TS}) > 0
        THEN trip_distance
             / (date_diff('second', {config.PICKUP_TS}, {config.DROPOFF_TS}) / 3600.0)
    END AS speed_mph,
    hour({config.PICKUP_TS}) AS pickup_hour,
    date_trunc('month', {config.PICKUP_TS}) AS pickup_month
FROM trips_raw;
"""


def _rules(period: str) -> list[tuple[str, str, str]]:
    """Return (rule_id, human_description, invalid_predicate) ordered by priority.

    Order matters: the first predicate a row matches becomes its quarantine
    reason, so structural problems (missing/nonsensical timestamps) are listed
    before the derived checks that depend on them.
    """
    period_start = f"DATE '{period}-01'"
    return [
        ("missing_timestamps",
         "Pickup or dropoff timestamp is NULL",
         f"{config.PICKUP_TS} IS NULL OR {config.DROPOFF_TS} IS NULL"),
        ("non_positive_duration",
         "Dropoff is not after pickup (zero/negative duration)",
         "duration_min <= 0"),
        ("duration_too_long",
         f"Duration exceeds {config.MAX_DURATION_MIN:.0f} min",
         f"duration_min > {config.MAX_DURATION_MIN}"),
        ("duration_too_short",
         f"Duration under {config.MIN_DURATION_MIN:.0f} min",
         f"duration_min < {config.MIN_DURATION_MIN}"),
        ("non_positive_distance",
         "Trip distance is zero or negative",
         f"trip_distance <= {config.MIN_DISTANCE_MI}"),
        ("distance_too_long",
         f"Trip distance exceeds {config.MAX_DISTANCE_MI:.0f} mi",
         f"trip_distance > {config.MAX_DISTANCE_MI}"),
        ("implausible_speed",
         f"Average speed outside {config.MIN_SPEED_MPH:.0f}-{config.MAX_SPEED_MPH:.0f} mph",
         f"speed_mph IS NULL OR speed_mph < {config.MIN_SPEED_MPH} "
         f"OR speed_mph > {config.MAX_SPEED_MPH}"),
        ("bad_passenger_count",
         f"Passenger count NULL or outside {config.MIN_PASSENGERS}-{config.MAX_PASSENGERS}",
         f"passenger_count IS NULL OR passenger_count < {config.MIN_PASSENGERS} "
         f"OR passenger_count > {config.MAX_PASSENGERS}"),
        ("negative_amounts",
         "Fare or total amount is negative",
         "fare_amount < 0 OR total_amount < 0"),
        ("unknown_zone",
         "Pickup/dropoff LocationID is not a real zone (1-263)",
         f"PULocationID NOT BETWEEN {config.VALID_ZONE_MIN} AND {config.VALID_ZONE_MAX} "
         f"OR DOLocationID NOT BETWEEN {config.VALID_ZONE_MIN} AND {config.VALID_ZONE_MAX}"),
        ("out_of_period",
         "Pickup date falls outside the target month",
         f"pickup_month <> {period_start}"),
    ]


def validate(trip_path: Path, period: str, logger) -> dict:
    """Split raw trips into clean + quarantine sets and write a DQ report.

    Returns a summary dict used by the pipeline and the metrics stage.
    """
    config.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        # Mode B (SQL): read the immutable raw Parquet directly.
        con.execute(
            "CREATE OR REPLACE TABLE trips_raw AS SELECT * FROM read_parquet(?)",
            [str(trip_path)],
        )
        con.execute(_DERIVE_SQL)
        rows_in = con.execute("SELECT COUNT(*) FROM trips_derived").fetchone()[0]
        logger.info("Profiling %s raw rows against %d business rules",
                    f"{rows_in:,}", len(_rules(period)))

        rules = _rules(period)

        # Independent per-rule failure counts (a row may fail several rules).
        count_exprs = ",\n    ".join(
            f"SUM(CASE WHEN {pred} THEN 1 ELSE 0 END) AS {rid}"
            for rid, _desc, pred in rules
        )
        counts = con.execute(
            f"SELECT {count_exprs} FROM trips_derived"
        ).fetchdf().iloc[0].to_dict()

        # First-failing-rule assignment -> quarantine reason ('valid' if none).
        reason_case = "\n".join(
            f"        WHEN {pred} THEN '{rid}'" for rid, _desc, pred in rules
        )
        con.execute(f"""
            CREATE OR REPLACE TABLE trips_flagged AS
            SELECT *, CASE
{reason_case}
                ELSE 'valid'
            END AS reject_reason
            FROM trips_derived;
        """)

        rows_valid = con.execute(
            "SELECT COUNT(*) FROM trips_flagged WHERE reject_reason = 'valid'"
        ).fetchone()[0]
        rows_quarantined = rows_in - rows_valid

        # Persist clean + quarantine partitions as build artifacts.
        clean_path = config.BUILD_DIR / f"clean_{period}.parquet"
        quarantine_path = config.BUILD_DIR / f"quarantine_{period}.parquet"
        con.execute(
            "COPY (SELECT * FROM trips_flagged WHERE reject_reason = 'valid') "
            f"TO '{clean_path}' (FORMAT PARQUET)"
        )
        con.execute(
            "COPY (SELECT * FROM trips_flagged WHERE reject_reason <> 'valid') "
            f"TO '{quarantine_path}' (FORMAT PARQUET)"
        )

        # Data-quality report: one row per rule + a summary row.
        valid_rate = rows_valid / rows_in if rows_in else 0.0
        report_rows = []
        for rid, desc, _pred in rules:
            n_failed = int(counts.get(rid, 0) or 0)
            report_rows.append({
                "rule_id": rid,
                "description": desc,
                "rows_failed": n_failed,
                "pct_of_total": round(100 * n_failed / rows_in, 4) if rows_in else 0.0,
            })
        report_rows.append({
            "rule_id": "_SUMMARY_valid",
            "description": "Rows passing ALL rules (used for metrics)",
            "rows_failed": rows_valid,
            "pct_of_total": round(100 * valid_rate, 4),
        })

        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        report_path = config.OUTPUT_DIR / f"data_quality_report_{period}.csv"
        con.register("report_df", _to_df(report_rows))
        con.execute(f"COPY report_df TO '{report_path}' (HEADER, DELIMITER ',')")

        logger.info(
            "Validation done: %s valid (%.2f%%), %s quarantined",
            f"{rows_valid:,}", 100 * valid_rate, f"{rows_quarantined:,}",
        )
        logger.info("Wrote DQ report -> %s", report_path.name)

        return {
            "rows_in": rows_in,
            "rows_valid": rows_valid,
            "rows_quarantined": rows_quarantined,
            "valid_rate": valid_rate,
            "clean_path": clean_path,
            "quarantine_path": quarantine_path,
            "report_path": report_path,
        }
    finally:
        con.close()


def _to_df(rows: list[dict]):
    """Small helper so pandas stays an implementation detail of this stage."""
    import pandas as pd

    return pd.DataFrame(rows)
