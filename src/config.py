"""Central configuration: paths, data sources, and business validation thresholds.

Everything the pipeline needs to be reproducible lives here so that a reader can
audit *why* a row is considered valid without hunting through the code.
"""
from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths (all relative to the repository root, i.e. the parent of src/)
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw"          # immutable source inputs (never modified in place)
BUILD_DIR = ROOT / "build"      # intermediate artifacts, safe to delete/regenerate
OUTPUT_DIR = ROOT / "outputs"   # committed metrics + evidence for reviewers
LOG_DIR = ROOT / "logs"

# --------------------------------------------------------------------------- #
# Data sources (official NYC TLC distribution on CloudFront)
# --------------------------------------------------------------------------- #
BASE_URL = "https://d37ci6vzurychx.cloudfront.net"


def trip_url(period: str) -> str:
    """URL of the yellow-taxi trip Parquet for a period formatted YYYY-MM."""
    return f"{BASE_URL}/trip-data/yellow_tripdata_{period}.parquet"


ZONE_LOOKUP_URL = f"{BASE_URL}/misc/taxi_zone_lookup.csv"

# Column names in the yellow-taxi schema that the pipeline depends on.
PICKUP_TS = "tpep_pickup_datetime"
DROPOFF_TS = "tpep_dropoff_datetime"

# --------------------------------------------------------------------------- #
# Business validation thresholds
#
# These are deliberate, defensible choices, not silent magic numbers. Each is
# referenced by a validation rule in validate.py and documented in the README.
# --------------------------------------------------------------------------- #
MIN_DURATION_MIN = 1.0     # trips under 1 min are almost always meter errors
MAX_DURATION_MIN = 180.0   # 3h: beyond this is implausible for a metered NYC trip
MIN_DISTANCE_MI = 0.0      # distance must be strictly positive
MAX_DISTANCE_MI = 100.0    # 100mi exceeds any realistic in-service NYC trip
MIN_SPEED_MPH = 1.0        # near-zero avg speed => stuck meter / bad timestamps
MAX_SPEED_MPH = 70.0       # sustained >70mph avg is not achievable on NYC streets
MIN_PASSENGERS = 1
MAX_PASSENGERS = 6         # standard yellow-cab seating limit
VALID_ZONE_MIN = 1         # TLC LocationIDs 1..263 are real zones
VALID_ZONE_MAX = 263       # 264 = "Unknown", 265 = "N/A" -> treated as unknown zone

# Operational windows used by the demand metric.
PEAK_HOURS = {7, 8, 9, 16, 17, 18, 19}  # weekday morning + evening rush
