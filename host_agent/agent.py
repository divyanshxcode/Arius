#!/usr/bin/env python3
"""Arius host agent — runs on the GPU owner's machine (org B).

It registers itself with the broker, receives a job, executes it locally
(Docker + PyTorch when a GPU is available, plain Python otherwise) and streams
stdout plus a JSON result back to the broker. Nothing else on the network can
run code on this machine.

    python agent.py --broker http://127.0.0.1:8000 --name "AtlasBank-H03" --port 9001
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
WORKER = HERE.parent / "worker" / "worker.py"

app = FastAPI(title="Arius Host Agent", version="0.1.0")

STATE = {
    "broker": "http://127.0.0.1:8000",
    "name": "AtlasBank-H03",
    "public_url": "http://127.0.0.1:9001",
    "actor_id": None,
    "gpu_model": "NVIDIA GPU",
    "vram_gb": 24,
    "has_gpu": False,
    "has_docker": False,
    "docker_gpu": False,
    "busy": False,
    "last_job": None,
}


# --------------------------------------------------------------------------- #
# capability detection
# --------------------------------------------------------------------------- #
def detect_gpu() -> tuple[bool, str, int]:
    if not shutil.which("nvidia-smi"):
        return False, "CPU (no nvidia-smi)", 0
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        line = (out.stdout or "").strip().splitlines()[0]
        name, mem = [p.strip() for p in line.split(",")[:2]]
        gb = int(float(mem.replace("MiB", "").strip()) / 1024)
        return True, name, gb
    except Exception:  # noqa: BLE001
        return False, "CPU (nvidia-smi failed)", 0


def detect_docker_gpu() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        out = subprocess.run(
            ["docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:12.4.0-base-ubuntu22.04",
             "nvidia-smi", "-L"],
            capture_output=True, text=True, timeout=90,
        )
        return out.returncode == 0 and "GPU" in (out.stdout or "")
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
# broker helpers
# --------------------------------------------------------------------------- #
def post(path: str, payload: dict) -> dict | None:
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.post(f"{STATE['broker']}{path}", json=payload)
            r.raise_for_status()
            return r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[agent] POST {path} failed: {exc}", flush=True)
        return None


LOG_Q: "queue.Queue[tuple[int, str]]" = queue.Queue(maxsize=5000)


def _log_sender() -> None:
    """Ship log lines off-thread in batches so a slow broker never throttles the worker."""
    while True:
        job_id, line = LOG_Q.get()
        if job_id is None:
            return
        batch = [line]
        deadline = time.time() + 0.35
        while len(batch) < 60 and time.time() < deadline:
            try:
                nxt_job, nxt_line = LOG_Q.get(timeout=max(0.01, deadline - time.time()))
            except queue.Empty:
                break
            if nxt_job is None:
                break
            if nxt_job != job_id:
                LOG_Q.put((nxt_job, nxt_line))
                break
            batch.append(nxt_line)
        if STATE["actor_id"]:
            post(f"/actors/{STATE['actor_id']}/logs", {"job_id": job_id, "lines": batch})


def push_log(job_id: int, line: str) -> None:
    print(line, flush=True)
    try:
        LOG_Q.put_nowait((job_id, line))
    except queue.Full:
        pass  # drop rather than block the demo


def register() -> None:
    body = {
        "name": STATE["name"],
        "url": STATE["public_url"],
        "gpu_model": STATE["gpu_model"],
        "vram_gb": STATE["vram_gb"] or 8,
        "isolation_tier": "confidential" if STATE["has_gpu"] else "vgpu",
        "org_id": 1,
        "agent_version": "0.1.0",
        "gpu_info": {
            "has_gpu": STATE["has_gpu"],
            "docker_gpu": STATE["docker_gpu"],
            "hostname": os.environ.get("COMPUTERNAME") or "host",
        },
    }
    for attempt in range(30):
        res = post("/actors/register", body)
        if res:
            STATE["actor_id"] = res["id"]
            print(f"[agent] registered as {res['id']} ({STATE['gpu_model']})", flush=True)
            return
        time.sleep(2)
    print("[agent] could not register with broker", flush=True)


# --------------------------------------------------------------------------- #
# job execution
# --------------------------------------------------------------------------- #
class RunIn(BaseModel):
    job_id: int
    broker_url: str = "http://127.0.0.1:8000"
    actor_id: str | None = None
    units: int = 80000
    seconds: float = 12.0
    rate_per_second: float = 0.0015


def _run_docker(job_id: int, units: int, seconds: float) -> dict:
    cmd = [
        "docker", "run", "--rm", "--gpus", "all",
        "-v", f"{WORKER.as_posix()}:/work/worker.py:ro",
        "pytorch/pytorch:latest",
        "python", "/work/worker.py", "--units", str(units), "--seconds", str(seconds),
    ]
    return _stream(cmd, job_id, timeout_s=seconds + 180)


def _run_local(job_id: int, units: int, seconds: float) -> dict:
    cmd = [sys.executable, str(WORKER), "--units", str(units), "--seconds", str(seconds), "--no-gpu"]
    # hard backstop: even if the worker ignores its budget, the demo moves on
    return _stream(cmd, job_id, timeout_s=seconds + 10)


def _stream(cmd: list[str], job_id: int, timeout_s: float = 120.0) -> dict:
    started = time.time()
    push_log(job_id, "[agent] exec: " + " ".join(str(c) for c in cmd[-4:]))
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    result_line = None
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("ARIUS_RESULT "):
            result_line = line[len("ARIUS_RESULT "):]
            continue
        if line:
            push_log(job_id, line)
        if time.time() - started > timeout_s:
            proc.kill()
            push_log(job_id, "[agent] timeout — killing worker")
            break
    try:
        proc.wait(timeout=max(5.0, timeout_s))
    except subprocess.TimeoutExpired:
        proc.kill()
    elapsed = time.time() - started
    if result_line:
        try:
            res = json.loads(result_line)
        except json.JSONDecodeError:
            res = {"ok": False, "error": "bad result line"}
    else:
        res = {"ok": False, "error": f"worker exited {proc.returncode}"}
    res.setdefault("elapsed_s", round(elapsed, 2))
    res["exit_code"] = proc.returncode
    return res


def execute(job_id: int, units: int, rate: float, seconds: float = 12.0) -> None:
    STATE["busy"] = True
    STATE["last_job"] = job_id
    try:
        push_log(job_id, f"[agent] job {job_id} accepted on {STATE['name']} ({STATE['gpu_model']})")
        if STATE["docker_gpu"]:
            push_log(job_id, "[agent] launching container with --gpus all (pytorch/pytorch)")
            res = _run_docker(job_id, units, seconds)
        else:
            mode = "local python (cpu)" if not STATE["has_gpu"] else "local python (gpu)"
            push_log(job_id, f"[agent] launching worker — {mode}")
            res = _run_local(job_id, units, seconds)
        res["rate_per_second"] = rate
        post(f"/actors/{STATE['actor_id']}/results", {"job_id": job_id, "result": res})
    except Exception as exc:  # noqa: BLE001
        push_log(job_id, f"[agent] execution failed: {exc}")
        post(f"/actors/{STATE['actor_id']}/results",
             {"job_id": job_id, "result": {"ok": False, "error": str(exc)}})
    finally:
        STATE["busy"] = False


@app.post("/run")
def run(body: RunIn):
    t = threading.Thread(
        target=execute,
        args=(body.job_id, body.units, body.rate_per_second, body.seconds),
        daemon=True,
    )
    t.start()
    return {"accepted": True, "job_id": body.job_id}


@app.get("/status")
def status():
    return {
        "name": STATE["name"],
        "actor_id": STATE["actor_id"],
        "gpu_model": STATE["gpu_model"],
        "has_gpu": STATE["has_gpu"],
        "docker_gpu": STATE["docker_gpu"],
        "busy": STATE["busy"],
        "last_job": STATE["last_job"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", default=os.environ.get("BROKER_URL", "http://127.0.0.1:8000"))
    ap.add_argument("--name", default=os.environ.get("AGENT_NAME", "AtlasBank-H03"))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=9001)
    ap.add_argument("--public-url", default="")
    ap.add_argument("--skip-docker-check", action="store_true")
    args = ap.parse_args()

    STATE["broker"] = args.broker.rstrip("/")
    STATE["name"] = args.name
    if args.public_url:
        STATE["public_url"] = args.public_url
    else:
        parsed = urlparse(STATE["broker"])
        STATE["public_url"] = f"http://{parsed.hostname}:{args.port}"

    has_gpu, model, vram = detect_gpu()
    STATE["has_gpu"] = has_gpu
    STATE["gpu_model"] = model
    STATE["vram_gb"] = vram or 8
    STATE["has_docker"] = bool(shutil.which("docker"))
    STATE["docker_gpu"] = False if args.skip_docker_check else detect_docker_gpu()

    print(f"[agent] gpu={has_gpu} model={model} vram={STATE['vram_gb']}GB "
          f"docker={STATE['has_docker']} docker_gpu={STATE['docker_gpu']}", flush=True)

    threading.Thread(target=_log_sender, daemon=True).start()
    threading.Thread(target=register, daemon=True).start()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
