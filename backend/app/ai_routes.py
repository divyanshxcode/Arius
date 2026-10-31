"""AI endpoints (Gemini) — plan, guardrail, spend explanation.

Kept separate from api.py so the marketplace surface stays readable.
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func

from . import db, gemini, service
from .models import Host, Org, Transaction

router = APIRouter()


@router.get("/ai/status")
def ai_status():
    return gemini.status()


class PlanIn(BaseModel):
    text: str


@router.post("/ai/plan")
def ai_plan(body: PlanIn):
    s = db.session_factory()()
    try:
        hosts = [service.host_dict(s, h) for h in s.query(Host).all()]
        prices = {
            "queue_pressure": round(service.current_pressure(s), 3),
            "tier_multiplier": {"confidential": 1.8, "vgpu": 1.2, "plain": 1.0},
        }
        return gemini.plan_capacity(body.text, hosts, prices)
    finally:
        s.close()


class CheckIn(BaseModel):
    text: str
    tier: str = "plain"


@router.post("/ai/compliance")
def ai_compliance(body: CheckIn):
    return gemini.compliance_check(body.text, body.tier)


class SpendIn(BaseModel):
    question: str = "Where is our GPU spend going?"


@router.post("/ai/spend")
def ai_spend(body: SpendIn):
    s = db.session_factory()()
    try:
        rows = (
            s.query(
                Transaction.from_org,
                Transaction.to_org,
                func.sum(Transaction.amount).label("amount"),
                func.count(Transaction.id).label("n"),
            )
            .group_by(Transaction.from_org, Transaction.to_org)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(12)
            .all()
        )
        names = {o.id: o.name for o in s.query(Org).all()}
        aggregates = [
            {
                "from_org": names.get(r[0], str(r[0])),
                "to_org": names.get(r[1], str(r[1])),
                "amount": round(float(r[2] or 0), 6),
                "settlements": int(r[3] or 0),
            }
            for r in rows
        ]
        total = round(sum(a["amount"] for a in aggregates), 6)
        result = gemini.explain_spend(body.question, aggregates, {"total": total,
                                                                  "pairs": len(aggregates)})
        result["data"] = {"rows": aggregates[:5], "total": total}
        return result
    finally:
        s.close()


@router.get("/ai/cache")
def ai_cache():
    return {"entries": gemini.status()["cache_entries"]}


__all__ = ["router", "json"]
