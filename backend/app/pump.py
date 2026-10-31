"""The pump — one async loop that makes the fabric feel alive.

Every second it:
  * promotes queued jobs onto free slices (real scheduling),
  * walks each running job through scheduled -> provisioning -> running -> completed,
  * writes host telemetry into Tiger Data,
  * settles money into the ledger every 10s,
  * publishes everything to the SSE bus.

All state transitions are persisted in YugabyteDB; only the *telemetry values*
(util %, temperature, loss) are generated, because the GPUs are simulated.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from . import db, service
from .events import bus
from .models import Host, Job, Metric, Org, Slice, Transaction
from .pricing import per_second_rate

log = logging.getLogger("arius.pump")

from .actors import REAL_JOBS  # noqa: E402  (import after models to avoid cycles)

RUNTIME: dict[int, dict] = {}
DRAIN_SINCE: dict[int, datetime] = {}
DRAIN_RECOVER_S = 45.0
SETTLE_EVERY_S = 10.0

PHASE_ENTER = {"scheduled": 1.0, "provisioning": 2.0}   # seconds spent in each phase


def _now() -> datetime:
    return datetime.utcnow()


def _publish(event: dict) -> None:
    bus.publish(event)


def runtime_for(job: Job, host: Host, slices: list[Slice]) -> dict:
    rate = per_second_rate(host.price_per_hour, host.isolation_tier, 1.0)
    rate *= min(1.0, job.vram_req / max(host.vram_gb, 1))
    return {
        "phase": "scheduled",
        "phase_ts": _now(),
        "remaining_s": float(job.duration_s),
        "rate": rate,
        "charged": 0.0,
        "loss": round(random.uniform(0.9, 1.6), 4),
        "util_pct": 0.0,
        "last_settle": _now(),
        "last_tick": _now(),
        "slice_ids": [s.id for s in slices],
        "host_id": host.id,
    }


def _ensure_runtime(session) -> None:
    """Attach live state to any job that is mid-flight but has no entry yet."""
    live = (
        session.query(Job)
        .filter(Job.status.in_(("scheduled", "provisioning", "running")))
        .all()
    )
    for job in live:
        if job.id in RUNTIME or job.host_id is None:
            continue
        if job.id in REAL_JOBS:
            continue
        host = session.get(Host, job.host_id)
        slices = (
            session.query(Slice)
            .filter(Slice.job_id == job.id)
            .all()
        )
        if not slices:
            # legacy rows created before slice ownership was tracked
            slices = (
                session.query(Slice)
                .filter(Slice.host_id == job.host_id,
                        Slice.current_tenant == f"org:{job.org_id}")
                .all()
            )
        if not host or not slices:
            continue
        st = runtime_for(job, host, slices)
        st["rate"] = per_second_rate(
            host.price_per_hour, host.isolation_tier, service.current_pressure(session)
        ) * min(1.0, job.vram_req / max(host.vram_gb, 1))
        RUNTIME[job.id] = st


def tick() -> None:
    def _work(session):
        _ensure_runtime(session)
        _schedule_queued(session)
        _advance_jobs(session)
        _hosts_lifecycle(session)
        _telemetry(session)

    try:
        db.run_txn(_work)
    except Exception:  # noqa: BLE001 - a broken tick must not kill the pump
        log.exception("tick failed")


def _hosts_lifecycle(session) -> None:
    """A draining host comes back online after its maintenance window."""
    now = _now()
    for h in session.query(Host).filter(Host.status == "draining").all():
        since = DRAIN_SINCE.setdefault(h.id, now)
        if (now - since).total_seconds() >= DRAIN_RECOVER_S:
            h.status = "online"
            DRAIN_SINCE.pop(h.id, None)
            _publish({"type": "host.online", "host_id": h.id, "host": h.name,
                      "ts": now.isoformat()})


def _schedule_queued(session, limit: int = 3) -> None:
    """Match up to `limit` queued jobs per tick (paced, not a stampede)."""
    queued = session.query(Job).filter(Job.status == "queued").order_by(Job.created_at).limit(limit).all()
    if not queued:
        return
    for job in queued:
        picked = service.pick_slices(session, job.vram_req, job.isolation_req)
        if picked is None:
            continue
        host, slices = picked
        for sl in slices:
            sl.status = "rented"
            sl.current_tenant = f"org:{job.org_id}"
            sl.job_id = job.id
        job.host_id = host.id
        job.status = "scheduled"
        pressure = service.current_pressure(session)
        rate = per_second_rate(host.price_per_hour, host.isolation_tier, pressure)
        rate *= min(1.0, job.vram_req / max(host.vram_gb, 1))
        job.cost_expected = round(rate * job.duration_s, 6)
        st = runtime_for(job, host, slices)
        st["rate"] = rate
        RUNTIME[job.id] = st
        _publish(
            {
                "type": "job.scheduled",
                "job_id": job.id,
                "name": job.name,
                "host": host.name,
                "tier": host.isolation_tier,
                "rate_per_second": rate,
                "ts": _now().isoformat(),
            }
        )


def _advance_jobs(session) -> None:
    for jid, st in list(RUNTIME.items()):
        job = session.get(Job, jid)
        if job is None or job.status in ("completed", "failed"):
            RUNTIME.pop(jid, None)
            continue

        age = (_now() - st["phase_ts"]).total_seconds()

        if st["phase"] == "scheduled" and age >= PHASE_ENTER["scheduled"]:
            st["phase"] = "provisioning"
            st["phase_ts"] = _now()
            job.status = "provisioning"
            _publish({"type": "job.provisioning", "job_id": jid, "ts": _now().isoformat()})
            continue

        if st["phase"] == "provisioning" and age >= PHASE_ENTER["provisioning"]:
            st["phase"] = "running"
            st["phase_ts"] = _now()
            job.status = "running"
            job.started_at = _now()
            _publish(
                {
                    "type": "job.started",
                    "job_id": jid,
                    "name": job.name,
                    "host_id": st["host_id"],
                    "ts": _now().isoformat(),
                }
            )
            continue

        if st["phase"] != "running":
            continue

        # --- running: consume budget, accrue cost, evolve the loss curve -----
        # Wall-clock based, so a slow/retried tick never stretches the job.
        now = _now()
        elapsed = max(0.0, (now - st.get("last_tick", now)).total_seconds())
        st["last_tick"] = now
        st["remaining_s"] = max(0.0, st["remaining_s"] - elapsed)
        st["charged"] = round(st["charged"] + st["rate"] * elapsed, 8)
        st["loss"] = max(0.05, round(st["loss"] * 0.9988 - random.uniform(0.0, 0.0025), 5))
        st["util_pct"] = round(min(97.0, 62 + random.uniform(0, 33)), 1)

        if st["remaining_s"] <= 0:
            _complete(session, job, st)
            continue

        if (_now() - st["last_settle"]).total_seconds() >= SETTLE_EVERY_S:
            _settle(session, job, st, SETTLE_EVERY_S)

        _publish(
            {
                "type": "job.tick",
                "job_id": jid,
                "remaining_s": round(st["remaining_s"], 1),
                "charged": round(st["charged"], 6),
                "loss": st["loss"],
                "util_pct": st["util_pct"],
                "ts": _now().isoformat(),
            }
        )


def _settle(session, job: Job, st: dict, seconds: float) -> None:
    host = session.get(Host, st["host_id"])
    if host is None:
        return
    amount = round(st["rate"] * seconds, 8)
    session.add(
        Transaction(
            from_org=job.org_id,
            to_org=host.org_id,
            job_id=job.id,
            amount=amount,
            per_second=st["rate"],
            ts=_now(),
        )
    )
    renter = session.get(Org, job.org_id)
    owner = session.get(Org, host.org_id)
    if renter and renter.id != owner.id:
        renter.balance_usd = round((renter.balance_usd or 0) - amount, 6)
    if owner:
        owner.balance_usd = round((owner.balance_usd or 0) + amount, 6)
    st["last_settle"] = _now()
    _publish(
        {
            "type": "ledger.settlement",
            "job_id": job.id,
            "amount": amount,
            "from_org": renter.name if renter else None,
            "to_org": owner.name if owner else None,
            "ts": _now().isoformat(),
        }
    )


def _complete(session, job: Job, st: dict) -> None:
    for sid in st.get("slice_ids", []):
        sl = session.get(Slice, sid)
        if sl is not None and (sl.job_id == job.id or sl.job_id is None):
            sl.status = "free"
            sl.current_tenant = None
            sl.job_id = None
    _settle(session, job, st, max(0.0, (_now() - st["last_settle"]).total_seconds()))
    job.status = "completed"
    job.finished_at = _now()
    job.cost_expected = round(st["charged"], 6)   # what it actually cost
    RUNTIME.pop(job.id, None)
    _publish(
        {
            "type": "job.completed",
            "job_id": job.id,
            "name": job.name,
            "charged": round(st["charged"], 6),
            "ts": _now().isoformat(),
        }
    )


def _telemetry(session) -> None:
    """One telemetry row per online host per tick -> Tiger Data.

    The transactional `session` is only used to read host/slice state; the
    write goes to the telemetry store through its own session, because the
    `metrics` table does not exist in YugabyteDB.
    """
    hosts = session.query(Host).filter(Host.status != "offline").all()
    now = _now()
    rows = []
    payload = []
    for h in hosts:
        rented = (
            session.query(Slice).filter(Slice.host_id == h.id, Slice.status == "rented").count()
        )
        frac = rented / max(h.total_slices, 1)
        util = max(3.0, min(97.0, 12 + 78 * frac + random.uniform(-5, 5)))
        temp = round(34 + util * 0.42, 1)
        power = round(70 + util * 3.4, 1)
        rows.append({"host_id": h.id, "ts": now, "util_pct": round(util, 1),
                     "power_w": power, "temp_c": temp})
        payload.append(
            {"id": h.id, "util": round(util, 1), "temp": temp, "power": power, "rented": rented,
             "status": h.status}
        )

    if rows:
        td = db.td_session_factory()()
        try:
            td.bulk_insert_mappings(Metric, rows)
            td.commit()
        except Exception:  # noqa: BLE001 - telemetry loss must not stop the demo
            td.rollback()
            log.exception("telemetry write failed")
        finally:
            td.close()

    _publish({"type": "metrics", "ts": now.isoformat(), "hosts": payload})


async def run_pump(interval: float = 1.0) -> None:
    log.info("pump started (interval=%.1fs)", interval)
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:  # noqa: BLE001
            log.exception("pump iteration failed")
        await asyncio.sleep(interval)
