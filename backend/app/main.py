"""Arius broker — Phase 0 skeleton.

Endpoints so far:
    GET /            service banner
    GET /health      live status of BOTH stores (YugabyteDB + Tiger Data)

Phase 1 adds /hosts, /jobs, /allocate, /ledger, /events (SSE).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("arius")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    log.info("Arius broker starting (db_mode=%s)", settings.db_mode)
    db.init()
    if db.state.yb_fallback:
        log.warning("Running on SQLite fallback — fine for UI dev, not for the demo.")
    yield
    log.info("Arius broker stopped")


app = FastAPI(title="Arius Broker", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    return {
        "service": "arius-broker",
        "version": "0.1.0",
        "tagline": "B2B GPU time-slicing fabric",
        "phase": "0 — skeleton",
        "docs": "/docs",
    }


@app.get("/health")
@app.get("/api/health", include_in_schema=False)
def health() -> dict:
    return db.health()
