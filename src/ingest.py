"""Stage 1 - Ingest.

Retrieves the two raw source inputs and proves the retrieval is complete before
anything downstream is allowed to run.

Two retrieval modes are exercised in this project (Class 5 requirement):
  * Mode A - Files over HTTP: the monthly trip Parquet and the zone-lookup CSV are
    downloaded into raw/ and treated as immutable.
  * Mode B - SQL: every later stage reads those raw files through DuckDB SQL
    (see validate.py / model.py), rather than re-parsing them by hand.

Completeness is not assumed. For the Parquet we compare the row count reported by
the file's own footer metadata against the row count DuckDB actually reads; if they
disagree the file is corrupt/truncated and the run fails fast. Every input is
recorded in raw/manifest.json with its size and SHA-256 so a cached file can be
trusted on later reruns.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from . import config
from .utils import human_bytes, sha256_of

MANIFEST_PATH = config.RAW_DIR / "manifest.json"
_USER_AGENT = "fde-tlc-pipeline/1.0 (+coursework)"


def _download(url: str, dest: Path, logger, max_retries: int = 3) -> None:
    """Stream a URL to disk with simple retry/backoff.

    Downloads to a .part file and only renames on success so an interrupted
    download can never masquerade as a complete raw input.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Downloading %s (attempt %d/%d)", url, attempt, max_retries)
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
                total = int(resp.headers.get("Content-Length", 0))
                read = 0
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    read += len(chunk)
            if total and read != total:
                raise IOError(
                    f"size mismatch: expected {total} bytes, got {read}"
                )
            tmp.replace(dest)
            logger.info("Saved %s (%s)", dest.name, human_bytes(dest.stat().st_size))
            return
        except (urllib.error.URLError, IOError, TimeoutError) as err:
            last_err = err
            logger.warning("Download failed: %s", err)
            tmp.unlink(missing_ok=True)
            if attempt < max_retries:
                time.sleep(2 * attempt)

    raise RuntimeError(f"Could not download {url} after {max_retries} attempts: {last_err}")


def _parquet_footer_rows(path: Path) -> int:
    """Row count from the Parquet footer metadata (does not read the data)."""
    return pq.ParquetFile(path).metadata.num_rows


def _duckdb_rows(path: Path) -> int:
    """Row count DuckDB actually reads back from the file (Mode B: SQL)."""
    con = duckdb.connect()
    try:
        return con.execute(
            "SELECT COUNT(*) FROM read_parquet(?)", [str(path)]
        ).fetchone()[0]
    finally:
        con.close()


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {}


def _record(manifest: dict, key: str, url: str, path: Path, extra: dict) -> None:
    manifest[key] = {
        "url": url,
        "file": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_of(path),
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **extra,
    }


def ingest(period: str, logger, force: bool = False) -> dict:
    """Ensure raw inputs exist and are complete; return the ingest summary.

    Rerun behaviour: if a raw file is already present and its SHA-256 matches the
    manifest, it is reused (no re-download) unless ``force`` is set.
    """
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest()

    trip_path = config.RAW_DIR / f"yellow_tripdata_{period}.parquet"
    zone_path = config.RAW_DIR / "taxi_zone_lookup.csv"

    # ---- Trip Parquet (Mode A: file over HTTP) -------------------------------
    trip_key = f"trips_{period}"
    if force or not _cached_ok(trip_path, manifest.get(trip_key)):
        _download(config.trip_url(period), trip_path, logger)
    else:
        logger.info("Reusing cached %s (sha256 matches manifest)", trip_path.name)

    # ---- Completeness check: footer metadata vs SQL read ---------------------
    footer_rows = _parquet_footer_rows(trip_path)
    sql_rows = _duckdb_rows(trip_path)
    if footer_rows != sql_rows:
        raise RuntimeError(
            f"Incomplete trip file: footer says {footer_rows:,} rows but DuckDB "
            f"read {sql_rows:,}. Refusing to continue on a truncated input."
        )
    logger.info("Completeness OK: %s rows (footer == SQL read)", f"{sql_rows:,}")

    # ---- Zone lookup CSV (Mode A: file over HTTP) ----------------------------
    if force or not _cached_ok(zone_path, manifest.get("zones")):
        _download(config.ZONE_LOOKUP_URL, zone_path, logger)
    else:
        logger.info("Reusing cached %s", zone_path.name)

    _record(manifest, trip_key, config.trip_url(period), trip_path,
             {"rows": sql_rows, "rows_source": "parquet_footer==duckdb_count"})
    _record(manifest, "zones", config.ZONE_LOOKUP_URL, zone_path, {})
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    logger.info("Manifest updated: %s", MANIFEST_PATH.name)

    return {
        "trip_path": trip_path,
        "zone_path": zone_path,
        "raw_rows": sql_rows,
    }


def _cached_ok(path: Path, entry: dict | None) -> bool:
    """A cached file is trustworthy only if it exists and its hash is unchanged."""
    if not path.exists() or not entry:
        return False
    return entry.get("sha256") == sha256_of(path)
