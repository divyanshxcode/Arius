"""Gemini integration — three features that do real work.

  plan_capacity()      natural-language booking against the live host catalogue
  compliance_check()   policy gate over free-text job descriptions
  explain_spend()      prose over real ledger aggregates

Design rules:
  * Gemini only ever sees (and only ever rephrases) data we computed in SQL.
  * Every call is cached by a hash of (mode, request, catalogue digest) so the
    demo survives a dead venue network — the UI badges "offline" when served
    from cache or the deterministic rule engine.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

log = logging.getLogger("arius.gemini")

MODEL = "gemini-2.0-flash"
CACHE_PATH = Path("gemini_cache.json")
_cache: dict[str, dict] = {}


def _load_cache() -> None:
    global _cache
    if CACHE_PATH.exists():
        try:
            _cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            _cache = {}


def _save_cache() -> None:
    try:
        CACHE_PATH.write_text(json.dumps(_cache, indent=2)[:400_000], encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


_load_cache()


def _key(mode: str, payload: dict) -> str:
    blob = json.dumps({"mode": mode, **payload}, sort_keys=True, default=str)
    return hashlib.sha1(blob.encode()).hexdigest()


def _client():
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from google import genai

        return genai.Client(api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini client unavailable: %s", exc)
        return None


def _ask(prompt: str, mode: str, payload: dict) -> tuple[dict | None, str]:
    """Return (parsed JSON, source) where source is 'gemini' | 'cache' | 'rules'."""
    key = _key(mode, payload)
    if key in _cache:
        return _cache[key], "cache"

    client = _client()
    if client is not None:
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json", "temperature": 0.2},
            )
            text = (resp.text or "").strip()
            data = json.loads(text[text.find("{"): text.rfind("}") + 1])
            _cache[key] = data
            _save_cache()
            return data, "gemini"
        except Exception as exc:  # noqa: BLE001
            log.warning("gemini call failed, falling back: %s", exc)

    return None, "rules"


# --------------------------------------------------------------------------- #
# Feature A — natural-language capacity broker
# --------------------------------------------------------------------------- #
def plan_capacity(request_text: str, hosts: list[dict], prices: dict) -> dict:
    catalogue = [
        {
            "host": h["name"],
            "tier": h["isolation_tier"],
            "vram_gb": h["vram_gb"],
            "free_slices": h["slices_free"],
            "region": h["region"],
            "price_per_hour": h["price_per_hour"],
            "trust": h["trust_score"],
        }
        for h in hosts
    ]
    payload = {"request": request_text, "catalogue": catalogue, "prices": prices}
    prompt = (
        "You are the capacity broker for Arius, a B2B GPU marketplace. "
        "Choose at most three hosts from the catalogue that satisfy the request. "
        "Respect isolation tiers strictly: a 'confidential' request may only use "
        "confidential hosts; 'vgpu' may use vgpu or confidential; 'plain' may use any. "
        "Reply with JSON only: "
        '{"tier":"confidential|vgpu|plain","vram_gb":int,"duration_h":number,'
        '"recommended":[{"host":str,"why":str}],"total_cost":number,"reason":str}\n\n'
        f"CATALOGUE:\n{json.dumps(catalogue, indent=1)}\n\nREQUEST:\n{request_text}"
    )
    data, source = _ask(prompt, "plan", payload)
    if data is None:
        data = _rule_plan(request_text, hosts, prices)
    data["source"] = source
    data["model"] = MODEL if source == "gemini" else "offline-rules"
    return data


def _rule_plan(text: str, hosts: list[dict], prices: dict) -> dict:
    """Deterministic fallback so the demo works with no key and no network."""
    low = text.lower()
    tier = "confidential" if "confidential" in low else "vgpu" if "vgpu" in low else "plain"
    vram_match = re.search(r"(\d+)\s*gb", low)
    vram = int(vram_match.group(1)) if vram_match else 11
    hours_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hour|hours)", low)
    hours = float(hours_match.group(1)) if hours_match else 1.0

    order = {"confidential": 2, "vgpu": 1, "plain": 0}
    eligible = [h for h in hosts if order.get(h["isolation_tier"], -1) >= order[tier] and h["slices_free"] > 0]
    eligible.sort(key=lambda h: (h["price_per_hour"], -h["trust_score"]))
    recs = [
        {"host": h["name"], "why": f"{h['isolation_tier']} · {h['slices_free']} free slices · ${h['price_per_hour']:.2f}/hr"}
        for h in eligible[:3]
    ]
    cost = round(sum(h["price_per_hour"] for h in eligible[:1]) * hours, 2) if eligible else 0.0
    return {
        "tier": tier,
        "vram_gb": vram,
        "duration_h": hours,
        "recommended": recs,
        "total_cost": cost,
        "reason": (
            f"Parsed request as {vram} GB on a {tier} tier for {hours}h; "
            f"{len(eligible)} hosts satisfy the tier, cheapest first."
            if eligible
            else f"No host currently satisfies a {tier}-tier, {vram} GB request."
        ),
    }


# --------------------------------------------------------------------------- #
# Feature B — compliance guardrail
# --------------------------------------------------------------------------- #
SENSITIVE = ("medical", "patient", "health record", "biometric", "aadhaar", "ssn",
             "passport", "credit card", "salary", "minor", "children")


def compliance_check(job_text: str, requested_tier: str) -> dict:
    payload = {"job": job_text, "tier": requested_tier}
    prompt = (
        "You are the data-protection guardrail for a GPU marketplace. Given a job "
        "description and the isolation tier the renter requested, decide whether the "
        "booking may proceed. Sensitive personal data (medical records, biometrics, "
        "government IDs, financial account data, minors' data) requires the "
        "'confidential' tier. Reply JSON only: "
        '{"verdict":"allow|block","required_tier":"confidential|vgpu|plain","rationale":str}'
        f"\n\nJOB:\n{job_text}\nREQUESTED TIER: {requested_tier}"
    )
    data, source = _ask(prompt, "compliance", payload)
    if data is None:
        hit = next((w for w in SENSITIVE if w in job_text.lower()), None)
        if hit and requested_tier != "confidential":
            data = {
                "verdict": "block",
                "required_tier": "confidential",
                "rationale": f"Job text mentions '{hit}', which requires the confidential tier.",
            }
        else:
            data = {
                "verdict": "allow",
                "required_tier": requested_tier if hit is None else "confidential",
                "rationale": "No sensitive categories detected for the requested tier." if hit is None
                else f"'{hit}' detected — confidential tier is required and requested.",
            }
    data["source"] = source
    data["model"] = MODEL if source == "gemini" else "offline-rules"
    return data


# --------------------------------------------------------------------------- #
# Feature C — plain-language spend analysis over REAL sql results
# --------------------------------------------------------------------------- #
def explain_spend(question: str, aggregate_rows: list[dict], totals: dict) -> dict:
    payload = {"q": question, "rows": aggregate_rows, "totals": totals}
    prompt = (
        "You explain billing data. Use ONLY the numbers in ROWS/TOTALS — never invent "
        "figures. Answer in 2-3 sentences and point at the biggest driver. Reply JSON "
        'only: {"answer":str,"top_driver":str,"confidence":"high|medium|low"}'
        f"\n\nQUESTION: {question}\nROWS: {json.dumps(aggregate_rows)}\nTOTALS: {json.dumps(totals)}"
    )
    data, source = _ask(prompt, "spend", payload)
    if data is None:
        if not aggregate_rows:
            data = {"answer": "No settlements recorded yet.", "top_driver": "—", "confidence": "high"}
        else:
            top = max(aggregate_rows, key=lambda r: r.get("amount", 0))
            data = {
                "answer": (
                    f"Spend totals {totals.get('total', 0):.4f} across "
                    f"{len(aggregate_rows)} org pairs; the largest is "
                    f"{top.get('from_org')} → {top.get('to_org')} at {top.get('amount', 0):.4f}."
                ),
                "top_driver": f"{top.get('from_org')} → {top.get('to_org')}",
                "confidence": "high",
            }
    data["source"] = source
    data["model"] = MODEL if source == "gemini" else "offline-rules"
    return data


def status() -> dict:
    return {
        "configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "model": MODEL,
        "cache_entries": len(_cache),
    }
