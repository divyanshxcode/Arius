"""Dual-engine database layer.

Two logical stores, one code path:

  * transactional state  -> YugabyteDB  (orgs, hosts, slices, jobs, ledger)
  * time-series telemetry-> Tiger Data  (metrics + continuous aggregates)

If Yugabyte is unreachable and DB_MODE=auto, we transparently fall back to a
local SQLite file so the UI can be developed without Docker. The health
endpoint always reports which mode is actually live — never pretend.

Pitfall baked in: Yugabyte's yugabyted SQL port is **5433**, not 5432.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

log = logging.getLogger("arius.db")


class Base(DeclarativeBase):
    """Transactional metadata (YugabyteDB)."""


class TDBase(DeclarativeBase):
    """Telemetry metadata (Tiger Data)."""


class DBState:
    def __init__(self) -> None:
        self.yb_engine: Engine | None = None
        self.td_engine: Engine | None = None
        self.yb_ok = False
        self.td_ok = False
        self.yb_fallback = False          # True => running on SQLite
        self.yb_error = ""
        self.td_error = ""
        self.yb_label = ""
        self.td_label = ""


state = DBState()


def _engine(url: str) -> Engine:
    kwargs: dict = {"pool_pre_ping": True, "future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # connect_timeout is critical on Windows: a filtered/closed port makes
        # psycopg wait forever, which would hang boot and /health.
        kwargs.update(
            pool_size=5,
            max_overflow=10,
            pool_recycle=1800,
            connect_args={"connect_timeout": 5},
        )
    return create_engine(url, **kwargs)


def _mask(url: str) -> str:
    """postgresql+psycopg://user:pass@host:port/db -> user:***@host:port/db"""
    try:
        u = urlparse(url)
        host = u.hostname or "?"
        port = f":{u.port}" if u.port else ""
        db = (u.path or "").lstrip("/")
        return f"{u.scheme}://{u.username or '?'}:***@{host}{port}/{db}"
    except Exception:
        return url


def _sqlite_url() -> str:
    return f"sqlite:///{settings.sqlite_path}"


def _attach_sqlite(reason: str) -> None:
    eng = _engine(_sqlite_url())
    state.yb_engine = eng
    state.td_engine = eng
    state.yb_ok = True
    state.td_ok = True
    state.yb_fallback = True
    state.yb_label = _sqlite_url()
    state.td_label = "fallback: metrics share the SQLite file"
    log.warning("Using SQLite dev fallback (%s)", reason)


def init() -> None:
    mode = settings.db_mode.lower().strip()

    if mode == "sqlite":
        _attach_sqlite("DB_MODE=sqlite")
        return

    # --- transactional store -------------------------------------------------
    try:
        yb = _engine(settings.yb_url)
        with yb.connect() as conn:
            conn.execute(text("SELECT 1"))
        state.yb_engine = yb
        state.yb_ok = True
        state.yb_label = _mask(settings.yb_url)
        log.info("YugabyteDB connected: %s", state.yb_label)
    except Exception as exc:  # noqa: BLE001 - report, never crash in auto mode
        state.yb_error = str(exc).splitlines()[0][:300]
        if mode == "yugabyte":
            raise
        _attach_sqlite("YugabyteDB unreachable")
        return

    # --- telemetry store -----------------------------------------------------
    try:
        td = _engine(settings.td_url)
        with td.connect() as conn:
            conn.execute(text("SELECT 1"))
        state.td_engine = td
        state.td_ok = True
        state.td_label = _mask(settings.td_url)
        log.info("Tiger Data connected: %s", state.td_label)
    except Exception as exc:  # noqa: BLE001
        state.td_error = str(exc).splitlines()[0][:300]
        # degrade gracefully: keep telemetry in the transactional store
        state.td_engine = state.yb_engine
        state.td_label = "fallback: metrics share the transactional DB"
        log.warning("Tiger Data unreachable, metrics fall back: %s", state.td_error)


def get_engine() -> Engine:
    if state.yb_engine is None:
        init()
    assert state.yb_engine is not None
    return state.yb_engine


def get_td_engine() -> Engine:
    if state.td_engine is None:
        init()
    return state.td_engine or get_engine()


def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


RETRYABLE_SQLSTATES = {"40001", "40P01"}   # serialization failure / deadlock


def _retryable(err: Exception) -> bool:
    orig = getattr(err, "orig", None)
    state = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None) or ""
    return state in RETRYABLE_SQLSTATES


def run_txn(fn, attempts: int = 6, base_delay: float = 0.05):
    """Run fn(session) in a transaction, retrying on distributed-DB conflicts.

    YugabyteDB (like any serializable store) can abort one of two concurrent
    writers with SQLSTATE 40001. The correct client behaviour is to restart the
    transaction — this is what makes the pump + API safe to run side by side.
    """
    import time

    last: Exception | None = None
    for i in range(attempts):
        s = session_factory()()
        try:
            result = fn(s)
            s.commit()
            return result
        except Exception as err:  # noqa: BLE001
            s.rollback()
            last = err
            if _retryable(err) and i < attempts - 1:
                time.sleep(base_delay * (2 ** i))
                continue
            raise
        finally:
            s.close()
    if last:
        raise last
    return None


def td_session_factory() -> sessionmaker[Session]:
    """Sessions bound to the telemetry store (Tiger Data)."""
    return sessionmaker(bind=get_td_engine(), expire_on_commit=False, future=True)


def get_session():
    """FastAPI dependency."""
    session = session_factory()()
    try:
        yield session
    finally:
        session.close()


def health() -> dict:
    """Live status of both stores, with honest fallback reporting."""
    out: dict = {
        "ok": bool(state.yb_ok and state.td_ok),
        "mode": settings.db_mode,
        "databases": {
            "yugabyte": {
                "connected": state.yb_ok,
                "fallback_sqlite": state.yb_fallback,
                "target": state.yb_label,
                "error": state.yb_error or None,
            },
            "tiger": {
                "connected": state.td_ok,
                "target": state.td_label,
                "error": state.td_error or None,
            },
        },
    }
    # cheap live pings so the widget reflects the moment, not boot time
    for key, eng in (("yugabyte", state.yb_engine), ("tiger", state.td_engine)):
        if eng is None:
            continue
        try:
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            out["databases"][key]["ping"] = "ok"
        except Exception as exc:  # noqa: BLE001
            out["databases"][key]["ping"] = f"error: {str(exc).splitlines()[0][:160]}"
            out["ok"] = False
    return out
