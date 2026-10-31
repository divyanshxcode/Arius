"""Arius schema.

Portability rule: only types that exist in SQLite, PostgreSQL, YugabyteDB and
TimescaleDB — Integer / String / Float / DateTime / Text. No PG-only types, so
the same models run in every mode (Docker cluster, single node, SQLite dev).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, TDBase


class Org(Base):
    __tablename__ = "orgs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(40), default="enterprise")  # enterprise|startup|academia
    balance_usd: Mapped[float] = mapped_column(Float, default=0.0)


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    region: Mapped[str] = mapped_column(String(24), nullable=False)      # ap-south|eu-west|us-east
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)          # owning org
    gpu_model: Mapped[str] = mapped_column(String(40), nullable=False)    # H100|A100|L40S|RTX4090|A10G
    vram_gb: Mapped[int] = mapped_column(Integer, default=80)
    total_slices: Mapped[int] = mapped_column(Integer, default=7)
    isolation_tier: Mapped[str] = mapped_column(String(16), default="plain")  # confidential|vgpu|plain
    trust_score: Mapped[int] = mapped_column(Integer, default=80)
    status: Mapped[str] = mapped_column(String(16), default="online")     # online|draining|offline
    price_per_hour: Mapped[float] = mapped_column(Float, default=0.0)


class Slice(Base):
    __tablename__ = "slices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_id: Mapped[int] = mapped_column(Integer, nullable=False)
    slice_index: Mapped[int] = mapped_column(Integer, nullable=False)
    vram_gb: Mapped[int] = mapped_column(Integer, default=8)
    status: Mapped[str] = mapped_column(String(16), default="free")       # free|rented|reserved
    current_tenant: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False)          # renter
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    vram_req: Mapped[int] = mapped_column(Integer, default=8)
    isolation_req: Mapped[str] = mapped_column(String(16), default="plain")
    duration_s: Mapped[int] = mapped_column(Integer, default=3600)
    status: Mapped[str] = mapped_column(String(16), default="queued")     # queued|scheduled|provisioning|running|checkpointing|completed|failed
    host_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_expected: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_org: Mapped[int] = mapped_column(Integer, nullable=False)        # renter
    to_org: Mapped[int] = mapped_column(Integer, nullable=False)          # host owner
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    per_second: Mapped[float] = mapped_column(Float, default=0.0)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Metric(TDBase):
    """Telemetry — lives in Tiger Data, hypertable on `ts`."""

    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    host_id: Mapped[int] = mapped_column(Integer, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    util_pct: Mapped[float] = mapped_column(Float, default=0.0)
    power_w: Mapped[float] = mapped_column(Float, default=0.0)
    temp_c: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (Index("ix_metrics_host_ts", "host_id", "ts"),)
