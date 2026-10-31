"""REST surface for the Arius marketplace (Phase 1).

Read endpoints are cheap projections; writes (/allocate, /reclaim, /demo/*) are
real transactions against YugabyteDB. /events is the SSE firehose.
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from . import db, pump, service
from .events import bus
from .models import Event, Host, Job, Org, Slice, Transaction
from .pricing import TIER_MULTIPLIER, per_second_rate

router = APIRouter()


def _session():
    return db.session_factory()()


# --------------------------------------------------------------------------- #
# read models
# --------------------------------------------------------------------------- #
@router.get("/orgs")
def orgs():
    s = _session()
    try:
        return [
            {"id": o.id, "name": o.name, "type": o.type, "balance_usd": round(o.balance_usd or 0, 2)}
            for o in s.query(Org).order_by(Org.id).all()
        ]
    finally:
        s.close()


@router.get("/hosts")
def hosts():
    s = _session()
    try:
        return [service.host_dict(s, h) for h in s.query(Host).order_by(Host.id).all()]
    finally:
        s.close()


@router.get("/pool")
def pool():
    s = _session()
    try:
        return service.pool_summary(s)
    finally:
        s.close()


@router.get("/jobs")
def jobs(status: str | None = None, limit: int = 100):
    s = _session()
    try:
        q = s.query(Job)
        if status:
            q = q.filter(Job.status == status)
        rows = q.order_by(Job.id.desc()).limit(limit).all()
        return [service.job_dict(s, j, pump.RUNTIME.get(j.id)) for j in rows]
    finally:
        s.close()


@router.get("/prices")
def prices():
    s = _session()
    try:
        ref: dict[str, float] = {}
        for h in s.query(Host).all():
            ref[h.gpu_model] = min(ref.get(h.gpu_model, 1e9), h.price_per_hour)
        return {
            "reference_per_hour": ref,
            "tier_multiplier": TIER_MULTIPLIER,
            "queue_pressure": round(service.current_pressure(s), 3),
            "spot_discount": 0.5,
            "reserved_discount": 0.6,
        }
    finally:
        s.close()


@router.get("/ledger")
def ledger(limit: int = 60):
    s = _session()
    try:
        rows = s.query(Transaction).order_by(Transaction.id.desc()).limit(limit).all()
        return [service.txn_dict(s, t) for t in rows]
    finally:
        s.close()


@router.get("/history")
def history(minutes: int = 60, host_id: int | None = None):
    """Chart series — served from Tiger Data's continuous aggregate when live."""
    minutes = max(1, min(minutes, 24 * 60))
    eng = db.get_td_engine()
    where_host = f" and host_id = {int(host_id)}" if host_id else ""

    if eng.dialect.name == "postgresql":
        try:
            sql = text(
                "select host_id, bucket as ts, util, power, temp from util_1m "
                f"where bucket >= now() - interval '{minutes} minutes'{where_host} "
                "order by bucket"
            )
            with eng.connect() as conn:
                rows = conn.execute(sql).fetchall()
            return {
                "source": "tiger:util_1m",
                "points": [
                    {"host_id": r[0], "ts": r[1].isoformat(), "util": round(float(r[2]), 1)}
                    for r in rows
                ],
            }
        except Exception:  # noqa: BLE001 - fall through to raw aggregation
            pass
    sql = text(
        "select host_id, strftime('%Y-%m-%dT%H:%M:00', ts) as bucket, avg(util_pct) "
        "from metrics group by host_id, bucket order by bucket"
    )
    with eng.connect() as conn:
        rows = conn.execute(sql).fetchall()
    return {
        "source": "raw:metrics",
        "points": [{"host_id": r[0], "ts": r[1], "util": round(float(r[2]), 1)} for r in rows],
    }


# --------------------------------------------------------------------------- #
# writes
# --------------------------------------------------------------------------- #
class AllocateIn(BaseModel):
    org_id: int
    name: str = "job"
    vram_req: int = Field(8, ge=1, le=80)
    isolation_req: str = "plain"
    duration_s: int = Field(600, ge=30, le=86400)


@router.post("/allocate")
def allocate(body: AllocateIn):
    if body.isolation_req not in TIER_MULTIPLIER:
        raise HTTPException(400, f"unknown isolation tier '{body.isolation_req}'")

    def _work(s):
        job = Job(
            org_id=body.org_id,
            name=body.name,
            vram_req=body.vram_req,
            isolation_req=body.isolation_req,
            duration_s=body.duration_s,
            status="queued",
            created_at=datetime.utcnow(),
        )
        s.add(job)
        s.flush()

        picked = service.allocate(s, job)
        payload = service.job_dict(s, job)
        if picked:
            host, slices = picked
            st = pump.runtime_for(job, host, slices)
            st["rate"] = per_second_rate(
                host.price_per_hour, host.isolation_tier, service.current_pressure(s)
            ) * min(1.0, job.vram_req / max(host.vram_gb, 1))
            pump.RUNTIME[job.id] = st
            payload.update(
                {
                    "host": host.name,
                    "gpu_model": host.gpu_model,
                    "isolation_tier": host.isolation_tier,
                    "slices_used": len(slices),
                    "rate_per_second": st["rate"],
                }
            )
            s.add(Event(kind="job.requested", payload_json=json.dumps({"job": job.id})))
        return {"scheduled": picked is not None, "job": payload, "_job_id": job.id,
                "_name": job.name, "_org": job.org_id}

    result = db.run_txn(_work)
    bus.publish({"type": "job.requested", "job_id": result.pop("_job_id"),
                 "name": result.pop("_name"), "org_id": result.pop("_org"),
                 "ts": datetime.utcnow().isoformat()})
    return result


class ReclaimIn(BaseModel):
    host_id: int


@router.post("/reclaim")
def reclaim(body: ReclaimIn):
    def _work(s):
        host = s.get(Host, body.host_id)
        if host is None:
            raise HTTPException(404, "host not found")
        host.status = "draining"
        pump.DRAIN_SINCE[host.id] = datetime.utcnow()
        moved, requeued = [], []
        jobs = (
            s.query(Job)
            .filter(Job.host_id == host.id, Job.status.in_(("scheduled", "provisioning", "running")))
            .all()
        )
        for job in jobs:
            for sl in (
                s.query(Slice)
                .filter(Slice.host_id == host.id, Slice.current_tenant == f"org:{job.org_id}")
                .all()
            ):
                sl.status = "free"
                sl.current_tenant = None
            job.host_id = None
            job.status = "queued"

            picked = service.pick_slices(s, job.vram_req, job.isolation_req, {host.id})
            if picked is None:
                pump.RUNTIME.pop(job.id, None)
                requeued.append(job.id)
                continue

            host2, slices2 = picked
            for sl2 in slices2:
                sl2.status = "rented"
                sl2.current_tenant = f"org:{job.org_id}"
            job.host_id = host2.id
            job.status = "scheduled"
            rate = per_second_rate(host2.price_per_hour, host2.isolation_tier, service.current_pressure(s))
            rate *= min(1.0, job.vram_req / max(host2.vram_gb, 1))
            st = pump.RUNTIME.get(job.id)
            if st:
                st.update({"host_id": host2.id, "slice_ids": [x.id for x in slices2], "rate": rate,
                           "phase": "scheduled", "phase_ts": datetime.utcnow()})
            moved.append({"job_id": job.id, "to": host2.name})

        return {"host": host.name, "status": "draining", "migrated": moved,
                "requeued": requeued, "_host_id": host.id}

    result = db.run_txn(_work)
    bus.publish({"type": "host.draining", "host_id": result.pop("_host_id"),
                 "host": result["host"], "moved": len(result["migrated"]),
                 "requeued": len(result["requeued"]), "ts": datetime.utcnow().isoformat()})
    return result


# --------------------------------------------------------------------------- #
# demo triggers (two buttons the presenter never explains)
# --------------------------------------------------------------------------- #
@router.post("/demo/burst")
def demo_burst(count: int = 20):
    def _work(s):
        renters = [o.id for o in s.query(Org).filter(Org.type.in_(("startup", "academia"))).all()]
        names = ["spike-finetune", "spike-embed", "spike-eval", "spike-lora", "spike-recsys"]
        tiers = ["confidential"] * 6 + ["vgpu"] * 6 + ["plain"] * 4
        n = max(1, min(count, 60))
        for i in range(n):
            s.add(Job(
                org_id=random.choice(renters),
                name=f"{random.choice(names)}-{i + 1:02d}",
                vram_req=random.choice([6, 8, 8, 11]),
                isolation_req=random.choice(tiers),
                duration_s=random.choice([60, 90, 120]),
                status="queued",
                created_at=datetime.utcnow(),
            ))
        s.flush()
        return {"queued": n, "queue_pressure": round(service.current_pressure(s), 3)}

    result = db.run_txn(_work)
    bus.publish({"type": "demo.burst", **result, "ts": datetime.utcnow().isoformat()})
    return result


@router.post("/demo/reclaim")
def demo_reclaim():
    """Drain the host currently carrying the most work — the on-stage chaos beat."""
    s = _session()
    try:
        from sqlalchemy import func

        row = (
            s.query(Job.host_id, func.count(Job.id).label("n"))
            .filter(Job.status.in_(("scheduled", "provisioning", "running")), Job.host_id.isnot(None))
            .group_by(Job.host_id)
            .order_by(func.count(Job.id).desc())
            .first()
        )
        if row is not None:
            host_id = row[0]
        else:
            busy = s.query(Host).filter(Host.status == "online").order_by(Host.trust_score.desc()).first()
            if busy is None:
                raise HTTPException(404, "no online host")
            host_id = busy.id
    finally:
        s.close()
    return reclaim(ReclaimIn(host_id=host_id))


# --------------------------------------------------------------------------- #
# SSE
# --------------------------------------------------------------------------- #
@router.get("/events")
async def events(request: Request):
    async def gen():
        yield "retry: 3000\n\n"
        for ev in bus.backlog[-25:]:
            yield f"data: {json.dumps(ev)}\n\n"
        q = bus.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"data: {json.dumps(ev)}\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
