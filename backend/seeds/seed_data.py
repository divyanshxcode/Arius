"""The Arius seeded universe — 6 orgs, 12 hosts, 25 queued jobs, telemetry.

Deterministic (seed=42) so screenshots, tests and the demo script always see
the same world. Numbers are chosen to make the story readable: ~3 hot hosts,
~7 mid, ~2 idle, and a queue that pressures spot pricing.

This is the ONLY simulated data in the system besides the live pump; hosts,
slices, jobs and the ledger are real rows in the transactional store.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Event, Host, Job, Metric, Org, Slice

ORGS = [
    # name, type, balance
    ("Atlas Bank", "enterprise", 48200.0),
    ("QuantEdge", "startup", 6100.0),
    ("MedAI Labs", "startup", 3400.0),
    ("Orbit Retail", "enterprise", 12750.0),
    ("IIT Delhi Lab", "academia", 900.0),
    ("Nova Compute", "partner", 22100.0),
]

# name, region, org_id, model, vram_gb, slices, tier, trust, price_per_hour
HOSTS = [
    ("AtlasBank-H100-01", "ap-south", 1, "H100", 80, 7, "confidential", 97, 6.50),
    ("AtlasBank-H100-02", "ap-south", 1, "H100", 80, 7, "confidential", 96, 6.50),
    ("AtlasBank-A100-01", "eu-west", 1, "A100", 40, 7, "vgpu", 91, 3.10),
    ("OrbitRetail-A100-01", "ap-south", 4, "A100", 40, 7, "vgpu", 84, 2.80),
    ("OrbitRetail-A100-02", "us-east", 4, "A100", 40, 7, "vgpu", 80, 2.80),
    ("OrbitRetail-4090-01", "ap-south", 4, "RTX4090", 24, 4, "plain", 72, 0.90),
    ("NovaCompute-H100-01", "eu-west", 6, "H100", 80, 7, "confidential", 95, 6.20),
    ("NovaCompute-H100-02", "us-east", 6, "H100", 80, 7, "confidential", 94, 6.10),
    ("NovaCompute-L40S-01", "us-east", 6, "L40S", 48, 4, "vgpu", 88, 2.20),
    ("IITD-4090-01", "ap-south", 5, "RTX4090", 24, 4, "plain", 66, 0.80),
    ("IITD-4090-02", "ap-south", 5, "RTX4090", 24, 4, "plain", 64, 0.80),
    ("IITD-A10G-01", "ap-south", 5, "A10G", 24, 4, "plain", 61, 0.70),
]

JOB_NAMES = [
    "finetune-llama3-8b", "embed-batch-3m", "rag-eval-run", "diffusion-lora",
    "risk-model-q4", "medical-ner-ft", "recsys-two-tower", "ocr-sweep",
    "speech-whisper-ft", "vision-clip-distill", "tabular-gbm-sweep",
    "translation-nllb-ft", "anomaly-autoencoder", "summarizer-peft",
    "code-completion-ft", "doc-parser-bench", "churn-forecast",
    "image-upscale-batch", "sentiment-rerun", "fraud-graph-gnn",
    "ner-span-eval", "tts-vits-ft", "embed-index-build", "rerank-lora",
    "safety-classifier-ft",
]


def _clear(yb: Session, td: Session) -> None:
    # metrics live ONLY in the telemetry store (Tiger Data / Timescale);
    # the transactional store never has that table.
    for model in (Slice, Job, Event, Host, Org):
        yb.query(model).delete()
    yb.commit()
    td.query(Metric).delete()
    td.commit()


def seed(yb: Session, td: Session, force: bool = False) -> dict:
    rng = random.Random(42)

    if yb.query(Host).count() and not force:
        return {"skipped": True, "reason": "hosts already exist (use --force)"}

    _clear(yb, td)

    orgs = [Org(name=n, type=t, balance_usd=b) for n, t, b in ORGS]
    yb.add_all(orgs)
    yb.flush()

    hosts: list[Host] = []
    for name, region, org_id, model, vram, slices, tier, trust, price in HOSTS:
        h = Host(
            name=name, region=region, org_id=org_id, gpu_model=model,
            vram_gb=vram, total_slices=slices, isolation_tier=tier,
            trust_score=trust, status="online", price_per_hour=price,
        )
        hosts.append(h)
    yb.add_all(hosts)
    yb.flush()

    for h in hosts:
        per = max(1, h.vram_gb // h.total_slices)
        for i in range(h.total_slices):
            yb.add(Slice(host_id=h.id, slice_index=i, vram_gb=per, status="free"))

    renters = [o.id for o in orgs if o.type in ("startup", "academia")]
    tiers = ["confidential"] * 8 + ["vgpu"] * 7 + ["plain"] * 5
    now = datetime.utcnow()
    for i in range(25):
        yb.add(Job(
            org_id=rng.choice(renters),
            name=f"{rng.choice(JOB_NAMES)}-{i + 1:02d}",
            vram_req=rng.choice([6, 8, 11, 16, 24, 40]),
            isolation_req=rng.choice(tiers),
            duration_s=rng.choice([600, 900, 1800, 3600, 5400, 7200]),
            status="queued",
            created_at=now - timedelta(minutes=rng.randint(1, 90)),
        ))

    # 200 telemetry points per host at 5-minute spacing, ending now
    for h in hosts:
        util = rng.uniform(10, 70)
        for k in range(200):
            util = min(94.0, max(6.0, util + rng.uniform(-6, 6.5)))
            td.add(Metric(
                host_id=h.id,
                ts=now - timedelta(minutes=5 * (200 - k)),
                util_pct=round(util, 1),
                power_w=round(70 + util * 3.4, 1),
                temp_c=round(34 + util * 0.42, 1),
            ))

    yb.add(Event(kind="system.seeded", payload_json='{"hosts":12,"jobs":25,"orgs":6}'))
    yb.commit()
    td.commit()

    return {
        "orgs": len(orgs),
        "hosts": len(hosts),
        "slices": sum(h.total_slices for h in hosts),
        "jobs": 25,
        "metrics": len(hosts) * 200,
    }
