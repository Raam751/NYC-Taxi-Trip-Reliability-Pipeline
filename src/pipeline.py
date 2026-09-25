"""Stage 5 - Dependable pipeline orchestrator.

Runs the full path from raw client inputs to trustworthy metrics:

    ingest -> validate -> model -> metrics

Design goals (Class 8):
  * Repeatable   - one command reproduces every output from raw inputs.
  * Idempotent   - reruns reuse cached raw files (SHA-256 checked) and overwrite
                   outputs deterministically; `--force` re-downloads.
  * Observable   - every stage is timed and logged to console + logs/.
  * Fails safe   - each stage is guarded; a failure is logged with context and
                   returns a non-zero exit code so schedulers/CI notice.
  * Guardrails   - if a run yields zero valid rows, or the valid rate falls below
                   a floor, the pipeline exits non-zero rather than publishing
                   metrics nobody should trust.

Usage:
    python -m src.pipeline --period 2024-01
    python -m src.pipeline --period 2024-01 --force
    python -m src.pipeline --period 2024-01 --min-valid-rate 0.85
"""
from __future__ import annotations

import argparse
import sys
import time
from contextlib import contextmanager

from . import config, ingest, metrics, model, validate
from .utils import get_logger


@contextmanager
def stage(name: str, logger):
    """Time a stage and turn any exception into a clearly-labelled failure."""
    logger.info("[%s] start", name)
    t0 = time.perf_counter()
    try:
        yield
    except Exception as err:  # noqa: BLE001 - top-level stage boundary
        logger.error("[%s] FAILED after %.1fs: %s", name, time.perf_counter() - t0, err)
        raise
    logger.info("[%s] done in %.1fs", name, time.perf_counter() - t0)


def run(period: str, force: bool = False, min_valid_rate: float = 0.80) -> dict:
    """Execute the whole pipeline for one period; return a run summary."""
    logger = get_logger(period)
    logger.info("=" * 68)
    logger.info("NYC TLC pipeline | period=%s | force=%s", period, force)
    logger.info("=" * 68)
    t_start = time.perf_counter()

    with stage("ingest", logger):
        ing = ingest.ingest(period, logger, force=force)

    with stage("validate", logger):
        val = validate.validate(ing["trip_path"], period, logger)

    # Guardrail: never publish metrics from an empty or untrustworthy month.
    if val["rows_valid"] == 0:
        raise RuntimeError("No valid rows after validation - refusing to publish metrics.")
    if val["valid_rate"] < min_valid_rate:
        raise RuntimeError(
            f"Valid rate {val['valid_rate']:.2%} is below the floor "
            f"{min_valid_rate:.2%}. Investigate the source before trusting metrics."
        )

    with stage("model", logger):
        mod = model.build_model(val["clean_path"], ing["zone_path"], period, logger)

    with stage("metrics", logger):
        met = metrics.compute_metrics(
            mod["fact_path"], period,
            valid_rate=val["valid_rate"],
            rows_in=val["rows_in"],
            rows_valid=val["rows_valid"],
            logger=logger,
        )

    elapsed = time.perf_counter() - t_start
    logger.info("-" * 68)
    logger.info("SUCCESS in %.1fs | raw=%s valid=%s (%.2f%%) | outputs in %s/",
                elapsed, f"{val['rows_in']:,}", f"{val['rows_valid']:,}",
                100 * val["valid_rate"], config.OUTPUT_DIR.name)
    logger.info("-" * 68)

    return {"period": period, "ingest": ing, "validate": val,
            "model": mod, "metrics": met, "elapsed_s": round(elapsed, 1)}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="NYC TLC yellow-taxi metric pipeline")
    p.add_argument("--period", required=True,
                   help="Target month formatted YYYY-MM, e.g. 2024-01")
    p.add_argument("--force", action="store_true",
                   help="Re-download raw inputs even if a valid cache exists")
    p.add_argument("--min-valid-rate", type=float, default=0.80,
                   help="Fail the run if the valid-trip rate is below this (0-1)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    # Basic period sanity check before doing any work.
    try:
        y, m = args.period.split("-")
        assert len(y) == 4 and 1 <= int(m) <= 12
    except (ValueError, AssertionError):
        print(f"Invalid --period '{args.period}'; expected YYYY-MM.", file=sys.stderr)
        return 2

    try:
        run(args.period, force=args.force, min_valid_rate=args.min_valid_rate)
        return 0
    except Exception as err:  # noqa: BLE001 - convert to process exit code
        print(f"PIPELINE FAILED: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
