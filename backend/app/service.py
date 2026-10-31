"""Marketplace service layer: fitting jobs to slices, serialisation helpers.

Everything here is real logic against real rows — the scheduler decides, the
database records. Nothing is pre-scripted.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import Event, Host, Job, Org, Slice, Transaction
from .pricing import per_second_rate, queue_pressure, tier_allows


def counts(session: Session) -> dict:
    queued = session.query(func.count(Job.id)).filter(Job.status == "queued").scalar() or 0
    running = session.query(func.count(Job.id)).filter(Job.status == "running").scalar() or 0
    free = session.query(func.count(Slice.id)).filter(Slice.status == "free").scalar() or 0
    total = session.query(func.count(Slice.id)).scalar() or 0
    return {"queued": queued, "running": running, "free_slices": free, "total_slices": total}


def current_pressure(session: Session) -> float:
    c = counts(session)
    return queue_pressure(c["queued"], c["free_slices"])


def pick_slices(
    session: Session,
    vram_req: int,
    isolation_req: str,
    exclude_hosts: set[int] | None = None,
):
    """Find the cheapest eligible host with enough free VRAM to host the job.

    Returns (host, [slices]) or None. A job may span several MIG slices on the
    same physical GPU — that is how a 24 GB job fits on an H100 split into
    11 GB slices.
    """
    exclude_hosts = exclude_hosts or set()
    hosts = session.query(Host).filter(Host.status == "online").all()
    best = None
    for h in hosts:
        if h.id in exclude_hosts or not tier_allows(h.isolation_tier, isolation_req):
            continue
        free = (
            session.query(Slice)
            .filter(Slice.host_id == h.id, Slice.status == "free")
            .all()
        )
        if not free:
            continue
        chosen: list[Slice] = []
        acc = 0
        for sl in sorted(free, key=lambda s: -s.vram_gb):
            chosen.append(sl)
            acc += sl.vram_gb
            if acc >= vram_req:
                break
        if acc < vram_req:
            continue
        key = (h.price_per_hour, -h.trust_score)
        if best is None or key < best[0]:
            best = (key, h, chosen)
    if best is None:
        return None
    return best[1], best[2]


def allocate(session: Session, job: Job):
    """Reserve slices for a queued job. Returns (host, [slices]) on success."""
    picked = pick_slices(session, job.vram_req, job.isolation_req)
    if picked is None:
        return None
    host, slices = picked
    for sl in slices:
        sl.status = "rented"
        sl.current_tenant = f"org:{job.org_id}"
        sl.job_id = job.id
    job.host_id = host.id
    job.status = "scheduled"
    rate = per_second_rate(host.price_per_hour, host.isolation_tier, current_pressure(session))
    rate *= min(1.0, job.vram_req / max(host.vram_gb, 1))
    job.cost_expected = round(rate * job.duration_s, 6)
    session.add(
        Event(
            kind="job.scheduled",
            payload_json=f'{{"job":{job.id},"host":"{host.name}","tier":"{host.isolation_tier}"}}',
        )
    )
    return host, slices


def release_slice(session: Session, job: Job) -> None:
    if job.host_id is None:
        return
    sl = (
        session.query(Slice)
        .filter(Slice.host_id == job.host_id, Slice.current_tenant == f"org:{job.org_id}")
        .first()
    )
    if sl:
        sl.status = "free"
        sl.current_tenant = None


def pool_summary(session: Session) -> dict:
    hosts = session.query(Host).all()
    c = counts(session)
    pressure = current_pressure(session)
    capacity = 0.0
    in_use = 0.0
    for h in hosts:
        capacity += h.price_per_hour
        rented = sum(1 for s in h_slices(session, h.id) if s.status == "rented")
        in_use += h.price_per_hour * (rented / max(h.total_slices, 1))
    return {
        "hosts": len(hosts),
        "hosts_online": sum(1 for h in hosts if h.status == "online"),
        "slices_total": c["total_slices"],
        "slices_free": c["free_slices"],
        "slices_rented": c["total_slices"] - c["free_slices"],
        "jobs_queued": c["queued"],
        "jobs_running": c["running"],
        "queue_pressure": round(pressure, 3),
        "list_value_per_hour": round(capacity, 2),
        "in_use_value_per_hour": round(in_use, 2),
        "utilization_pct": round(100.0 * (c["total_slices"] - c["free_slices"]) / max(c["total_slices"], 1), 1),
    }


def h_slices(session: Session, host_id: int):
    return session.query(Slice).filter(Slice.host_id == host_id).all()


def host_dict(session: Session, h: Host) -> dict:
    sl = h_slices(session, h.id)
    rented = sum(1 for s in sl if s.status == "rented")
    owner = session.get(Org, h.org_id)
    return {
        "id": h.id,
        "name": h.name,
        "region": h.region,
        "org": owner.name if owner else None,
        "gpu_model": h.gpu_model,
        "vram_gb": h.vram_gb,
        "isolation_tier": h.isolation_tier,
        "trust_score": h.trust_score,
        "status": h.status,
        "price_per_hour": h.price_per_hour,
        "slices_total": h.total_slices,
        "slices_free": sum(1 for s in sl if s.status == "free"),
        "slices_rented": rented,
        "utilization_pct": round(100.0 * rented / max(h.total_slices, 1), 1),
    }


def job_dict(session: Session, j: Job, live: dict | None = None) -> dict:
    org = session.get(Org, j.org_id)
    host = session.get(Host, j.host_id) if j.host_id else None
    out = {
        "id": j.id,
        "org": org.name if org else None,
        "org_id": j.org_id,
        "name": j.name,
        "vram_req": j.vram_req,
        "isolation_req": j.isolation_req,
        "duration_s": j.duration_s,
        "status": j.status,
        "host_id": j.host_id,
        "host": host.name if host else None,
        "gpu_model": host.gpu_model if host else None,
        "isolation_tier": host.isolation_tier if host else None,
        "cost_expected": round(j.cost_expected or 0.0, 6),
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }
    if live:
        out.update({k: live[k] for k in ("phase", "remaining_s", "charged", "loss", "util_pct") if k in live})
    return out


def txn_dict(session: Session, t: Transaction) -> dict:
    src = session.get(Org, t.from_org)
    dst = session.get(Org, t.to_org)
    return {
        "id": t.id,
        "from_org": src.name if src else t.from_org,
        "to_org": dst.name if dst else t.to_org,
        "job_id": t.job_id,
        "amount": round(t.amount, 6),
        "per_second": t.per_second,
        "ts": t.ts.isoformat() if t.ts else None,
    }


def now() -> datetime:
    return datetime.utcnow()
