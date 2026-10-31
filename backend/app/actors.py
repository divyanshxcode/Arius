"""Host agents — the one genuinely real part of Arius.

An organisation that wants to rent out its GPU runs `host_agent/agent.py` on
that machine. The agent registers here, receives jobs, executes them (Docker +
PyTorch when a GPU is present, plain Python otherwise) and streams logs and a
real result artifact back.

Nothing inside this module executes customer code on the broker.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import db, service
from .events import bus
from .models import Host, Job, Org, Slice, Transaction
from .pricing import per_second_rate

router = APIRouter()

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)

EXEC_LOGS: dict[int, list[str]] = {}
EXEC_RESULTS: dict[int, dict] = {}
REAL_JOBS: set[int] = set()          # pump must never fake-tick these


@dataclass
class Actor:
    id: str
    name: str
    url: str
    gpu_model: str
    vram_gb: int
    isolation_tier: str
    org_id: int
    host_id: int | None = None
    gpu: dict = field(default_factory=dict)
    last_seen: float = field(default_factory=time.time)
    status: str = "online"


REGISTRY: dict[str, Actor] = {}


def _actor_public(a: Actor) -> dict:
    return {
        "id": a.id,
        "name": a.name,
        "url": a.url,
        "gpu_model": a.gpu_model,
        "vram_gb": a.vram_gb,
        "isolation_tier": a.isolation_tier,
        "host_id": a.host_id,
        "status": a.status,
        "gpu": a.gpu,
        "last_seen": a.last_seen,
    }


class RegisterIn(BaseModel):
    name: str
    url: str                      # e.g. http://192.168.1.7:9001
    gpu_model: str = "NVIDIA GPU"
    vram_gb: int = 24
    isolation_tier: str = "vgpu"
    org_id: int = 1
    agent_version: str = "0.1.0"
    gpu_info: dict = {}


@router.post("/actors/register")
def register(body: RegisterIn):
    """Register a real machine; it becomes a sellable host in the marketplace."""
    actor_id = str(uuid.uuid4())[:8]

    def _work(s):
        host = s.query(Host).filter(Host.name == body.name).first()
        if host is None:
            host = Host(
                name=body.name,
                region="ap-south",
                org_id=body.org_id,
                gpu_model=body.gpu_model,
                vram_gb=body.vram_gb,
                total_slices=1,
                isolation_tier=body.isolation_tier,
                trust_score=99,
                status="online",
                price_per_hour=6.0,
            )
            s.add(host)
            s.flush()
            s.add(Slice(host_id=host.id, slice_index=0, vram_gb=body.vram_gb, status="free"))
        else:
            host.status = "online"
            host.gpu_model = body.gpu_model
            host.vram_gb = body.vram_gb
        return host.id

    host_id = db.run_txn(_work)
    actor = Actor(
        id=actor_id,
        name=body.name,
        url=body.url.rstrip("/"),
        gpu_model=body.gpu_model,
        vram_gb=body.vram_gb,
        isolation_tier=body.isolation_tier,
        org_id=body.org_id,
        host_id=host_id,
        gpu=body.gpu_info or {},
        status="online",
    )
    REGISTRY[actor_id] = actor
    bus.publish({"type": "actor.registered", "actor_id": actor_id, "name": actor.name,
                 "gpu_model": actor.gpu_model, "ts": _now()})
    return _actor_public(actor)


@router.post("/actors/{actor_id}/heartbeat")
def heartbeat(actor_id: str, gpu_info: dict | None = None):
    a = REGISTRY.get(actor_id)
    if a is None:
        raise HTTPException(404, "actor not registered")
    a.last_seen = time.time()
    a.status = "online"
    if gpu_info:
        a.gpu = gpu_info
    return {"ok": True}


@router.get("/actors")
def list_actors():
    return [_actor_public(a) for a in REGISTRY.values()]


class LogIn(BaseModel):
    job_id: int
    line: str


@router.post("/actors/{actor_id}/logs")
def actor_log(actor_id: str, body: LogIn):
    if actor_id not in REGISTRY:
        raise HTTPException(404, "unknown actor")
    lines = EXEC_LOGS.setdefault(body.job_id, [])
    lines.append(body.line[:400])
    del lines[:-400]
    bus.publish({"type": "exec.log", "job_id": body.job_id, "line": body.line[:400], "ts": _now()})
    return {"ok": True}


class ResultIn(BaseModel):
    job_id: int
    result: dict[str, Any] = {}


@router.post("/actors/{actor_id}/results")
def actor_result(actor_id: str, body: ResultIn):
    a = REGISTRY.get(actor_id)
    if a is None:
        raise HTTPException(404, "unknown actor")
    job_id = body.job_id
    EXEC_RESULTS[job_id] = body.result
    (RESULTS_DIR / f"{job_id}.json").write_text(json.dumps(body.result, indent=2), encoding="utf-8")

    def _finish(s):
        job = s.get(Job, job_id)
        if job is None:
            return None
        job.status = "completed" if body.result.get("ok", True) else "failed"
        from datetime import datetime

        job.finished_at = datetime.utcnow()
        elapsed = float(body.result.get("elapsed_s") or 0)
        rate = float(body.result.get("rate_per_second") or 0.0015)
        job.cost_expected = round(rate * elapsed, 6)
        if job.status == "completed" and job.host_id:
            host = s.get(Host, job.host_id)
            if host:
                s.add(Transaction(from_org=job.org_id, to_org=host.org_id, job_id=job.id,
                                  amount=job.cost_expected, per_second=rate))
        sl = s.query(Slice).filter(Slice.job_id == job_id).first()
        if sl is None:
            sl = s.query(Slice).filter(Slice.host_id == job.host_id,
                                       Slice.current_tenant == f"org:{job.org_id}").first()
        if sl:
            sl.status = "free"
            sl.current_tenant = None
            sl.job_id = None
        REAL_JOBS.discard(job_id)
        return job.status

    status = db.run_txn(_finish)
    bus.publish({"type": "exec.done", "job_id": job_id, "status": status,
                 "device": body.result.get("device"), "elapsed_s": body.result.get("elapsed_s"),
                 "ts": _now()})
    return {"ok": True, "job_status": status}


class ExecIn(BaseModel):
    org_id: int = 2
    name: str = "real-gpu-job"
    units: int = 80000          # max matmul iterations
    seconds: float = 12.0       # time budget — keeps the demo beat predictable
    actor_id: str | None = None


@router.post("/exec")
def exec_real(body: ExecIn):
    """Dispatch a REAL job to a registered host agent and return its job row."""
    if not REGISTRY:
        raise HTTPException(409, "no host agent registered — start host_agent/agent.py first")

    actor = REGISTRY.get(body.actor_id) if body.actor_id else next(iter(REGISTRY.values()))
    if actor is None:
        raise HTTPException(404, "actor not found")

    def _work(s):
        host = s.get(Host, actor.host_id) if actor.host_id else None
        sl = None
        if host:
            sl = s.query(Slice).filter(Slice.host_id == host.id, Slice.status == "free").first()
            if sl is None:
                sl = s.query(Slice).filter(Slice.host_id == host.id).first()
        rate = per_second_rate(host.price_per_hour, host.isolation_tier, service.current_pressure(s)) if host else 0.0015
        job = Job(
            org_id=body.org_id,
            name=body.name,
            vram_req=min(actor.vram_gb, 24),
            isolation_req=actor.isolation_tier,
            duration_s=600,
            status="running",
            host_id=host.id if host else None,
            cost_expected=0.0,
        )
        s.add(job)
        s.flush()
        if sl is not None:
            sl.status = "rented"
            sl.current_tenant = f"org:{body.org_id}"
            sl.job_id = job.id
        REAL_JOBS.add(job.id)
        return {"job_id": job.id, "rate": rate, "host": host.name if host else actor.name}

    info = db.run_txn(_work)
    job_id = info["job_id"]

    payload = {
        "job_id": job_id,
        "broker_url": "http://127.0.0.1:8000",
        "actor_id": actor.id,
        "units": body.units,
        "seconds": body.seconds,
        "rate_per_second": info["rate"],
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(f"{actor.url}/run", json=payload)
    except Exception as exc:  # noqa: BLE001
        bus.publish({"type": "exec.error", "job_id": job_id, "error": str(exc)[:200], "ts": _now()})
        raise HTTPException(502, f"host agent unreachable at {actor.url}: {exc}") from exc

    bus.publish({"type": "exec.dispatched", "job_id": job_id, "actor": actor.name,
                 "host": info["host"], "ts": _now()})
    return {"job_id": job_id, "actor": actor.name, "host": info["host"], "rate_per_second": info["rate"]}


@router.get("/exec/{job_id}")
def exec_state(job_id: int):
    s = db.session_factory()()
    try:
        job = s.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "job not found")
        return {
            "job_id": job_id,
            "status": job.status,
            "name": job.name,
            "device": (EXEC_RESULTS.get(job_id) or {}).get("device"),
            "elapsed_s": (EXEC_RESULTS.get(job_id) or {}).get("elapsed_s"),
            "cost": job.cost_expected,
            "logs": EXEC_LOGS.get(job_id, [])[-60:],
            "result": EXEC_RESULTS.get(job_id),
            "artifact": f"/results/{job_id}" if (RESULTS_DIR / f"{job_id}.json").exists() else None,
        }
    finally:
        s.close()


@router.get("/results/{job_id}")
def get_result(job_id: int):
    path = RESULTS_DIR / f"{job_id}.json"
    if not path.exists():
        raise HTTPException(404, "no result for that job")
    return FileResponse(path, media_type="application/json", filename=f"arius-job-{job_id}.json")


def _now() -> str:
    from datetime import datetime

    return datetime.utcnow().isoformat()
