"""Stage 3 - Model the workflow.

We treat each taxi trip as a single business *event* with a lifecycle:

    [pickup @ PULocationID, t0]  --in service-->  [dropoff @ DOLocationID, t1]

The model is a small star schema:
  * fact_trips - one validated trip per row, plus the derived operational
    measures (duration, speed) and time attributes (hour, peak flag).
  * dim_zone   - the taxi-zone lookup (LocationID -> Borough, Zone, service_zone).

fact_trips is joined to dim_zone on the PICKUP location so that demand and
efficiency can be read by borough - the grain operations staff actually plan
around (where to position cars, when to add supply).
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from . import config

_PEAK_SET = "(" + ",".join(str(h) for h in sorted(config.PEAK_HOURS)) + ")"


def build_model(clean_path: Path, zone_path: Path, period: str, logger) -> dict:
    """Create fact_trips + dim_zone and persist fact_trips as a build artifact."""
    config.BUILD_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        # dim_zone from the CSV lookup (Mode B: SQL over a raw file).
        con.execute(
            "CREATE OR REPLACE TABLE dim_zone AS "
            "SELECT LocationID, Borough, Zone, service_zone "
            "FROM read_csv_auto(?, header=true)",
            [str(zone_path)],
        )
        n_zones = con.execute("SELECT COUNT(*) FROM dim_zone").fetchone()[0]

        # fact_trips: validated events enriched with pickup-zone attributes.
        con.execute(f"""
            CREATE OR REPLACE TABLE fact_trips AS
            SELECT
                t.VendorID,
                t.{config.PICKUP_TS}      AS pickup_ts,
                t.{config.DROPOFF_TS}     AS dropoff_ts,
                t.PULocationID,
                t.DOLocationID,
                z.Borough                 AS pickup_borough,
                z.Zone                    AS pickup_zone,
                t.passenger_count,
                t.trip_distance,
                t.fare_amount,
                t.total_amount,
                t.duration_min,
                t.speed_mph,
                t.pickup_hour,
                (t.pickup_hour IN {_PEAK_SET}) AS is_peak
            FROM read_parquet('{clean_path}') t
            LEFT JOIN dim_zone z ON t.PULocationID = z.LocationID;
        """)

        n_fact = con.execute("SELECT COUNT(*) FROM fact_trips").fetchone()[0]
        fact_path = config.BUILD_DIR / f"fact_trips_{period}.parquet"
        con.execute(f"COPY fact_trips TO '{fact_path}' (FORMAT PARQUET)")

        logger.info("Model built: fact_trips=%s rows, dim_zone=%d zones",
                    f"{n_fact:,}", n_zones)
        logger.info("Wrote fact table -> %s", fact_path.name)

        return {"fact_path": fact_path, "fact_rows": n_fact, "zones": n_zones}
    finally:
        con.close()
