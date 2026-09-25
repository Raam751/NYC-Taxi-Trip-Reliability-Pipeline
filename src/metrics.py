"""Stage 4 - Metrics.

Project KPI: **Fleet efficiency & data trust** - can leadership rely on this
month's trip data, and where/when is the fleet running slowly or unreliably?

Five metrics, each tied to that KPI and to a concrete operational decision:

  M1 Valid trip rate (%)      -> Can we trust this month at all? (data guardrail)
  M2 Median trip duration     -> Typical trip length (baseline for planning)
  M3 Median trip speed (mph)  -> Efficiency; low speed => congestion
  M4 P90 trip duration (min)  -> Reliability tail; how bad are the slow trips
  M5 Peak-hour trip share (%) -> Demand concentration for staffing/supply

A supporting breakdown (trips + median speed by pickup borough) is also written
so the headline speed number can be acted on geographically.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from . import config


def compute_metrics(fact_path: Path, period: str, valid_rate: float,
                    rows_in: int, rows_valid: int, logger) -> dict:
    """Compute the KPI metric set and write outputs/metrics + evidence + breakdown."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        agg = con.execute(f"""
            SELECT
                median(duration_min)                       AS median_duration_min,
                median(speed_mph)                          AS median_speed_mph,
                quantile_cont(duration_min, 0.90)          AS p90_duration_min,
                100.0 * SUM(CASE WHEN is_peak THEN 1 ELSE 0 END) / COUNT(*)
                                                           AS peak_share_pct,
                COUNT(*)                                   AS n
            FROM read_parquet('{fact_path}');
        """).fetchdf().iloc[0]

        metrics = [
            ("M1", "Valid trip rate", round(100 * valid_rate, 2), "%",
             "Share of raw trips passing all validation rules",
             "Data trust: is this month usable for decisions?"),
            ("M2", "Median trip duration", round(float(agg.median_duration_min), 2), "min",
             "Median of validated trip durations",
             "Baseline trip length for planning"),
            ("M3", "Median trip speed", round(float(agg.median_speed_mph), 2), "mph",
             "Median of validated average trip speeds",
             "Efficiency; low speed signals congestion"),
            ("M4", "P90 trip duration", round(float(agg.p90_duration_min), 2), "min",
             "90th percentile validated trip duration",
             "Reliability tail: how long are the slow trips"),
            ("M5", "Peak-hour trip share", round(float(agg.peak_share_pct), 2), "%",
             f"Share of trips in peak hours {sorted(config.PEAK_HOURS)}",
             "Demand concentration for staffing/supply"),
        ]

        # Headline metrics table.
        metrics_path = config.OUTPUT_DIR / f"metrics_{period}.csv"
        con.register("m_df", _metrics_df(metrics, period))
        con.execute(f"COPY m_df TO '{metrics_path}' (HEADER, DELIMITER ',')")

        # Supporting breakdown by pickup borough.
        breakdown_path = config.OUTPUT_DIR / f"trips_by_borough_{period}.csv"
        con.execute(f"""
            COPY (
                SELECT
                    COALESCE(pickup_borough, 'Unknown') AS pickup_borough,
                    COUNT(*)                            AS trips,
                    round(median(duration_min), 2)      AS median_duration_min,
                    round(median(speed_mph), 2)         AS median_speed_mph
                FROM read_parquet('{fact_path}')
                GROUP BY 1
                ORDER BY trips DESC
            ) TO '{breakdown_path}' (HEADER, DELIMITER ',');
        """)

        # Human-readable evidence table (Markdown) combining KPI + metrics.
        evidence_path = config.OUTPUT_DIR / f"evidence_table_{period}.md"
        evidence_path.write_text(_evidence_md(period, metrics, rows_in, rows_valid))

        for mid, name, value, unit, *_ in metrics:
            logger.info("  %s %s = %s %s", mid, name, value, unit)
        logger.info("Wrote metrics -> %s, breakdown -> %s, evidence -> %s",
                    metrics_path.name, breakdown_path.name, evidence_path.name)

        return {
            "metrics_path": metrics_path,
            "breakdown_path": breakdown_path,
            "evidence_path": evidence_path,
            "metrics": {m[0]: m[2] for m in metrics},
        }
    finally:
        con.close()


def _metrics_df(metrics: list[tuple], period: str):
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "period": period,
                "metric_id": mid,
                "metric_name": name,
                "value": value,
                "unit": unit,
                "definition": definition,
                "supports_decision": decision,
            }
            for (mid, name, value, unit, definition, decision) in metrics
        ]
    )


def _evidence_md(period: str, metrics: list[tuple], rows_in: int, rows_valid: int) -> str:
    lines = [
        f"# Evidence table - Yellow Taxi {period}",
        "",
        "**Project KPI:** Fleet efficiency & data trust.",
        "",
        f"- Raw trips ingested: **{rows_in:,}**",
        f"- Validated trips used for metrics: **{rows_valid:,}**",
        "",
        "| Metric | Value | Unit | Supports decision |",
        "|---|---:|---|---|",
    ]
    for (mid, name, value, unit, _definition, decision) in metrics:
        lines.append(f"| {mid} {name} | {value} | {unit} | {decision} |")
    lines += [
        "",
        "See `data_quality_report_" + period + ".csv` for per-rule rejections and "
        "`trips_by_borough_" + period + ".csv` for the geographic breakdown.",
        "",
    ]
    return "\n".join(lines)
