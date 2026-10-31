# Arius — B2B GPU Time-Slicing Fabric

![hackCBS 9.0](https://img.shields.io/badge/hackCBS-9.0-3ddc97) ![track](https://img.shields.io/badge/track-Cloud-4cc9f0) ![MLH](https://img.shields.io/badge/MLH-2027%20Season-7d90a4)

> Enterprise GPU fleets idle at <20% utilization while teams queue months for capacity.
> **Arius turns that idle silicon into a verified, tiered, per-second marketplace — and proves it by running your workload on someone else's GPU.**

**One real keystone:** org A books a slice on org B's machine, B's GPU physically executes A's job, A downloads the real artifact. Everything around it — scheduling, tier enforcement, metering, ledger — is real code on a distributed database. Fleet breadth is simulated.

Full plan: [`PROJECT.md`](./PROJECT.md).

---

## Quickstart (3 modes)

### Mode 1 — SQLite dev fallback (no Docker needed)

```bash
cd backend
py -3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m seeds.init_db --seed
./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --reload
# → http://localhost:8000/health
```

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

### Mode 2 — Full stack (YugabyteDB 3 nodes + Tiger Data)

Requires Docker Desktop (WSL2 engine).

```bash
docker compose up -d          # 3-node Yugabyte on 5433 + Timescale/Tiger on 5434
# one-time: create the application database (containers start with the default db)
docker exec arius-yb1 bin/ysqlsh -h 172.28.0.2 -U yugabyte -c 'CREATE DATABASE arius'
cd backend
./.venv/Scripts/python.exe -m seeds.init_db --seed --force
./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000 --reload
```

### Mode 3 — Lite (single-node DBs, low RAM)

```bash
docker compose -f docker-compose.lite.yml up -d
```

Helper scripts: `scripts/check-env.sh`, `scripts/start-db.sh [lite]`, `scripts/dev-backend.sh`, `scripts/dev-frontend.sh`, `scripts/check-gpu.sh`.

---

## Layout

```
Arius/
├── PROJECT.md              full implementation plan (source of truth)
├── docker-compose.yml      3-node YugabyteDB + Tiger Data
├── docker-compose.lite.yml single-node fallback
├── backend/
│   ├── app/                FastAPI broker: config, dual-engine db layer, models, main
│   └── seeds/              init_db.py (schema + timescale DDL) + seed_data.py (universe)
├── frontend/               Vite + React + Tailwind dashboard shell
└── scripts/                env/db/dev/gpu checks
```

## Stack

| Layer | Choice |
|---|---|
| Broker | FastAPI + SQLAlchemy |
| Transactional state | **YugabyteDB** (3-node Raft cluster, YSQL port **5433**) |
| Telemetry | **Tiger Data** / TimescaleDB (hypertable + continuous aggregate `util_1m`) |
| AI | **Gemini** `gemini-2.0-flash` (Phase 5: capacity broker, compliance guardrail, fleet analyst) |
| Frontend | Vite + React + Tailwind + Recharts |
| Real compute | host agent + Docker + PyTorch worker (Phase 4) |

## API (Phase 1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | live status of both stores |
| GET | `/orgs` `/hosts` `/pool` `/jobs` `/prices` `/ledger` | read models |
| GET | `/history?minutes=60` | chart series from Tiger's `util_1m` aggregate |
| GET | `/events` | SSE: metrics, job ticks, settlements, host events |
| POST | `/allocate` | real scheduling: reserves slices, returns host+tier+rate |
| POST | `/reclaim` | drain a host, migrate its jobs elsewhere |
| POST | `/demo/burst` | queue a load spike (demo trigger) |
| POST | `/demo/reclaim` | drain the busiest host (demo trigger) |

Scheduling rule: cheapest eligible host that can honour the isolation tier and
supply enough free VRAM (a job may span several MIG slices on one GPU).
Billing: `rate = list_price/3600 × (1 + queue_pressure) × tier_multiplier × vram_share`,
settled into the ledger every 10 seconds.

## Build status

- [x] **Phase 0** — skeleton: dual-engine layer, live `/health`, schema + seed, dashboard shell
- [x] **Phase 1** — REST surface, SSE pump, pricing/billing, ledger, tier enforcement, demo triggers
- [x] **Phase 2** — fleet grid, telemetry charts from Tiger continuous aggregates, job queue, event log
- [x] **Phase 3** — org switcher, booking modal with tier enforcement, chargeback ledger UI
- [x] **Phase 4** — host agent + PyTorch/numpy worker + real artifact download (`/exec`, `/actors`, `/results`)
- [x] **Phase 5** — Gemini capacity broker + compliance guardrail + spend explainer (offline rule fallback)
- [x] **Phase 6** — demo triggers wired to the UI; runbook in [`DEMO.md`](./DEMO.md)
- [x] **Phase 7** — hardening: serialization retries, drain recovery, offline AI cache, 3 run modes

## Host agent (the real-compute beat)

```bash
cd host_agent
../backend/.venv/Scripts/python.exe agent.py --broker http://127.0.0.1:8000 \
    --name "AtlasBank-H03" --port 9001
```

It registers as a sellable host, executes jobs with `--gpus all` when Docker+GPU are
available, otherwise runs `worker/worker.py` locally (CUDA → CPU auto-fallback), and
streams logs plus a downloadable JSON artifact to the broker. The broker never runs
customer code.

## Note on Docker

Docker is **not required** for development: `DB_MODE=auto` (default) tries Yugabyte on 5433 and transparently falls back to a local SQLite file, and `/health` reports honestly which mode is live. The demo must run on the real cluster (`DB_MODE=yugabyte`) so the Raft node-kill beat is genuine.

Verified locally on Docker Desktop 29.9.2 (12 CPUs / 8 GB): 3 masters + 3 tservers, RF=3 with one replica per zone, `util_1m` continuous aggregate live, and a node-stop test that kept serving reads (`12 hosts / 25 jobs`) with one node down.

Ports are non-default on purpose: **5433** YSQL (Yugabyte's yugabyted default) and **5434** for Tiger, because 5432 is usually taken by a local PostgreSQL install.
