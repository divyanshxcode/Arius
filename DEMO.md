# Arius — 2-Minute Demo Runbook

Everything below runs on one laptop. Two laptops is better (see "Two-machine mode").

## 0. Bring the stack up (5 minutes before judging)

```bash
# 1) databases (3-node Yugabyte + Tiger)
docker compose up -d
docker exec arius-yb1 bin/ysqlsh -h 172.28.0.2 -U yugabyte -c 'CREATE DATABASE arius'   # once
docker exec arius-tiger psql -U arius -d arius -c 'ALTER MATERIALIZED VIEW util_1m SET (timescaledb.materialized_only=false); CALL refresh_continuous_aggregate(\x27util_1m\x27, NULL, NULL);'

# 2) reset the universe to a clean, deterministic state
cd backend
./.venv/Scripts/python.exe -m seeds.init_db --seed --force

# 3) broker
DB_MODE=yugabyte ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000

# 4) dashboard
cd ../frontend && npm run dev        # http://localhost:5173

# 5) host agent (org B's machine) — the real-compute demo
cd ../host_agent
../backend/.venv/Scripts/python.exe agent.py --broker http://127.0.0.1:8000 \
    --name "AtlasBank-H03" --port 9001
```

Open the dashboard **before** walking on stage so the fleet is already warm.

---

## 1. The script (2:00)

| t | Do | Say | What lands |
|---|---|---|---|
| 0:00 | Point at the fleet + stat strip | "Enterprise GPU fleets run at four to fifteen percent utilisation at night while teams queue months for capacity. Arius sells that idle silicon." | Problem |
| 0:15 | Point at the **Telemetry** chart badge | "Every chart here comes from Tiger Data — a continuous aggregate, not a mocked array. Live." | Tiger Data |
| 0:25 | Click **book capacity** → pick *QuantEdge*, 11 GB, **confidential**, 120 s → **policy check** → **book slice** | "The isolation tier is a hard constraint, not a badge: confidential jobs are refused on plain hosts." | Tier enforcement |
| 0:45 | In the modal type *"train on patient medical records"*, tier **vgpu**, **policy check** | "The guardrail blocks it: sensitive data can't ride a vGPU tier. This is Gemini reading free text." | Gemini prize |
| 1:00 | Close modal → **Controls → run on host agent** | "Now the real part. This job is executing on another machine's GPU — watch its stdout." | Phase 4 keystone |
| 1:20 | Point at the log lines + **download result** | "That artifact was produced by org B's silicon. Here's the machine-readable proof." | Verifiable |
| 1:35 | **Controls → ask broker** | "Natural language booking: it parsed the request, priced it against live supply and picked the cheapest eligible hosts." | Gemini prize |
| 1:50 | Point at **Chargeback ledger** (bottom left) | "Every second is metered, every settlement is a row in YugabyteDB — cross-org chargeback, automatically." | FinTech angle |
| 1:55 | **Terminal:** `docker stop arius-yb2` → dashboard keeps ticking → `docker start arius-yb2` | "Killed a database node. The cluster re-elected, zero bookings lost." | Yugabyte sponsor |

Then close on the ledger total.

---

## 2. Two-machine mode (best)

Laptop A runs broker + frontend. Laptop B runs the host agent:

```bash
python agent.py --broker http://<A-ip>:8000 --name "AtlasBank-H03" \
    --public-url http://<B-ip>:9001 --port 9001
```

The fleet grid gains a `trust 99` host; **run on host agent** now crosses the network. Open a terminal on B and show `nvidia-smi` spiking (if the GPU is present) while A streams the loss curve.

---

## 3. Fallback chain (if something dies)

| Failure | Move |
|---|---|
| No GPU on the demo machine | Worker auto-selects CPU; UI says `device: cpu`. Story: "hardware-agnostic fabric." |
| Docker GPU passthrough unavailable | Agent runs `worker.py` directly (same result schema). |
| Gemini key missing / Wi-Fi dead | `/ai/*` falls back to the deterministic rule engine; the badge reads `offline rules`. Demo unchanged. |
| Cluster too heavy | `docker compose -f docker-compose.lite.yml up -d` (single node) — drop the node-kill beat. |
| Whole cluster dies | `DB_MODE=sqlite` and reseed: everything except the Raft beat still demos. |

---

## 4. Sponsor evidence (what to have on screen)

- **Gemini** — `/ai/plan` and `/ai/compliance` results visible in the Controls panel (`source: gemini` or `offline rules`).
- **Tiger Data** — Telemetry card badge `Tiger Data` + `/history` returning `source: tiger:util_1m`.
- **YugabyteDB** — StatStrip "3/3 nodes" + the node-kill beat.
- **Cloud track** — the whole control plane.

---

## 5. Honest boundaries (say them if asked)

- Fleet breadth and telemetry values are simulated (12 seeded hosts + one live pump).
- Marketplace mechanics are real: scheduling, tier gating, metering, ledger, retries on serialization failure.
- The compute is real: a genuine matmul workload on the agent's hardware; its output artifact is downloadable.
- Confidential-tier claims are product rules today; hardware isolation (MIG/CC) is the roadmap slide.
