"""Arius broker — Phase 1.

REST surface + SSE + the pump. Run with:
    uvicorn app.main:app --port 8000
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import actors, ai_routes, api, db, pump
from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("arius")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Arius broker starting (db_mode=%s)", settings.db_mode)
    db.init()
    if db.state.yb_fallback:
        log.warning("Running on SQLite fallback — fine for UI dev, not for the demo.")

    task = asyncio.create_task(pump.run_pump(1.0))
    app.state.pump_task = task
    log.info("pump task running")
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        log.info("Arius broker stopped")


app = FastAPI(title="Arius Broker", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(api.router)
app.include_router(actors.router)
app.include_router(ai_routes.router)


@app.get("/")
def root() -> dict:
    return {
        "service": "arius-broker",
        "version": "0.2.0",
        "tagline": "B2B GPU time-slicing fabric",
        "phase": "1 — marketplace core",
        "docs": "/docs",
        "endpoints": [
            "GET /health", "GET /orgs", "GET /hosts", "GET /pool", "GET /jobs",
            "GET /prices", "GET /ledger", "GET /history", "GET /events (SSE)",
            "POST /allocate", "POST /reclaim", "POST /demo/burst", "POST /demo/reclaim",
        ],
    }


@app.get("/health")
@app.get("/api/health", include_in_schema=False)
def health() -> dict:
    return db.health()
