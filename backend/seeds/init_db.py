"""Create the Arius schema (and optionally seed the demo universe).

Usage (from backend/):
    python -m seeds.init_db              # schema only
    python -m seeds.init_db --seed       # schema + demo universe
    python -m seeds.init_db --seed --force   # wipe and reseed

Works on YugabyteDB + Tiger Data, or on the SQLite dev fallback. On Tiger
Data it also builds the `util_1m` continuous aggregate that powers every
dashboard chart (plan Phase 1.3).
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import text

from app import db
from app.models import Base, TDBase

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s | %(message)s")
log = logging.getLogger("arius.init")

TIMESCALE_STEPS = [
    "CREATE EXTENSION IF NOT EXISTS timescaledb",
    (
        "SELECT create_hypertable('metrics', 'ts', "
        "if_not_exists => TRUE, migrate_data => TRUE)"
    ),
    """
    CREATE MATERIALIZED VIEW IF NOT EXISTS util_1m
    WITH (timescaledb.continuous) AS
    SELECT host_id,
           time_bucket('1 minute', ts) AS bucket,
           avg(util_pct) AS util,
           avg(power_w) AS power,
           avg(temp_c)  AS temp
    FROM metrics
    GROUP BY host_id, bucket
    """,
    # real-time aggregation + populate the view immediately so charts are never empty
    "ALTER MATERIALIZED VIEW util_1m SET (timescaledb.materialized_only = false)",
    "CALL refresh_continuous_aggregate('util_1m', NULL, NULL)",
]


def _enable_timescale(engine) -> str:
    """Try to turn the telemetry store into a real Tiger Data/Timescale store."""
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            for stmt in TIMESCALE_STEPS:
                conn.execute(text(stmt))
        return "timescale: hypertable + continuous aggregate util_1m ready"
    except Exception as exc:  # noqa: BLE001
        return f"timescale unavailable ({str(exc).splitlines()[0][:160]}) — charts will aggregate in Python"


def main() -> int:
    parser = argparse.ArgumentParser(description="Arius schema initializer")
    parser.add_argument("--seed", action="store_true", help="insert the demo universe")
    parser.add_argument("--force", action="store_true", help="wipe and reseed")
    args = parser.parse_args()

    db.init()
    yb = db.get_engine()
    td = db.get_td_engine()

    log.info("transactional store: %s", db.state.yb_label)
    log.info("telemetry store    : %s", db.state.td_label)

    Base.metadata.create_all(bind=yb)
    log.info("transactional tables created: %s", ", ".join(sorted(Base.metadata.tables)))

    TDBase.metadata.create_all(bind=td)
    log.info("telemetry table created: metrics")

    if td.dialect.name == "postgresql":
        log.info("%s", _enable_timescale(td))
    else:
        log.info("non-postgres telemetry store — skipping hypertable DDL (SQLite mode)")

    if args.seed:
        from seeds.seed_data import seed

        session_hint = db.session_factory()
        yb_s = session_hint()
        td_s = db.td_session_factory()()
        try:
            result = seed(yb_s, td_s, force=args.force)
        finally:
            yb_s.close()
            td_s.close()
        if result.get("skipped"):
            log.warning("seed skipped: %s", result["reason"])
        else:
            log.info("seeded: %s", result)

    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
