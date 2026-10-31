# Arius — B2B GPU Time-Slicing Marketplace

> **hackCBS 9.0 · Shaheed Sukhdev College of Business Studies · 31 Oct – 1 Nov 2026 · 24-hour sprint · MLH Official 2027 Season**
>
> **One-liner:** A fault-tolerant B2B marketplace that rents enterprise GPU idle-time as hardware-isolated slices — with per-second settlement, enforced privacy tiers, and live cross-org computation, running on a distributed database.

---

## 1. Origin & Position

Arius is the evolution of a winning hackCBS pattern: a **systems-concept idea showcase** — an impressive, deeply-technical infrastructure story demonstrated through a convincing control-plane UI, where the marketplace mechanics are real code and only the breadth of the (simulated) fleet is generated. (The team's prior hackathon winner was a RAM-pooling project in exactly this style.)

Arius answers a real, monetizable problem: **enterprise GPU fleets sit at <20% utilization while orgs queue months for H100 capacity.** Arius turns that idle silicon into revenue for owners and cheap, verified capacity for renters — with isolation tier and data privacy as first-class booking constraints.

**The centerpiece is genuinely real:** when org A books a slice on org B's machine, B's GPU physically executes A's workload and A downloads the real artifact.

---

## 2. Product Concept

### 2.1 Supply side (GPU owners — enterprises)
- List idle GPUs / MIG slices; set unavailability windows (e.g., 22:00–06:00 local or weekends).
- Earn on idle capacity instead of depreciation.
- Tier badges + trust scores decide search rank and price.

### 2.2 Demand side (renters — startups, universities, other teams)
- Book by: GPU model → VRAM → **isolation requirement (mandatory)** → region → duration.
- Three product tiers, mirroring real providers:
  - **On-demand** — guaranteed while free (≈2× spot)
  - **Spot / interruptible** — host can reclaim with 30–60 s notice; renter must checkpoint (≈50% discount)
  - **Reserved** — commit N slices for M months (≈60% off)
- Per-second billing; cross-org chargeback ledger; spend visibility.

### 2.3 B2B differencer (vs consumer marketplaces)
- Data residency (region-pinned tenants → region-pinned DB tables)
- SSO/RBAC, spend caps, audit logs, invoice-ready ledger (roadmap)
- **Privacy enforcement in the product**, not the contract (see §7)

---

## 3. Track & Prize Strategy (hackCBS 9.0)

### 3.1 Theme eligibility

| Theme | Fit | Position | Priority |
|---|---|---|---|
| **Cloud** | Perfect | "Architect the backbone of modern infrastructure" — distributed compute fabric, tiered isolation, fleet telemetry | 🥇 Primary |
| **AI** | Strong | Gemini-powered capacity advisor + compliance guardrail = GenAI on real infra | 🥈 Secondary |
| **FinTech** | Good | Cross-org chargeback, per-second metering, SLA credits, settlement ledger | 🥉 Third claim |
| **Open Innovation** | Always | Fallback | Safety |
| GreenTech | Weak | One talking point: idling upcycles silicon vs manufacturing more | Skip |
| IoT / HealthTech / EdTech | No | — | Skip |

### 3.2 MLH sponsor prizes

| Prize | Verdict | How we win |
|---|---|---|
| **Best Use of Gemini API** (Kreo Keyboards) | ✅ Target | 3 real Gemini features (§8.3) — not a chatbot |
| **Best Use of Tiger Data** (Stream Decks) | ✅ Target | All dashboard telemetry served from continuous aggregates (§8.2) |
| Best Use of MongoDB Atlas (M5Stack) | ⚠️ Optional | Audit/event log collection, only if time remains |
| Best Use of DigitalOcean / Vultr | ❌ Dropped by choice | No deployment for this edition — everything runs locally/on laptops |
| Best Use of Solana (hardware wallets) | ❌ Skip | Roadmap slide only (escrow settlement) |

### 3.3 Special category insurance
**Best Social Innovation (₹5,000):** "GPU acquisition is a moat; Arius lets underfunded universities and startups buy verified idle capacity at spot prices from enterprises." One slide + one README paragraph = eligible.

---

## 4. Architecture

```
                ┌─────────────────────────────────────────┐
   Hosts ──►    │  FastAPI broker                          │
   (simulated  │                                         │
    + 1 real  │  ┌───────────────┐  ┌────────────────┐  │
    host B)    │  │ YugabyteDB    │  │ Tiger Data     │  │
                │  │ (transaction) │  │ (time-series)  │  │
                │  │  hosts/jobs/  │  │  telemetry via │  │
                │  │  ledger/slices│  │  continuous    │  │
                │  │  3-node Raft  │  │  aggregates    │  │
                │  └───────────────┘  └────────────────┘  │
                │                                         │
                │  ┌────────────────┐                     │
                │  │ Gemini API     │                     │
                │  │ advisor /      │                     │
                │  │ guardrail /    │                     │
                │  │ analyst        │                     │
                │  └────────────────┘                     │
                └──────────┬──────────────────────────────┘
                           │  SSE live feed (+ agent stdout relay)
        ┌──────────────────┴───────────────┐
        │  React dashboard (org A)          │
        │  + host agent (org B, real GPU)   │
        └──────────────────────────────────┘
```

**The narrative:** *"A distributed marketplace for distributed compute, running on a distributed database."*

### 4.1 Tech stack (locked)

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI + SQLAlchemy | PG-compatible drivers work for both DBs |
| Transactional DB | **YugabyteDB** — 3-node Docker cluster (port **5433**) | Sponsor; Raft node-kill demo; geo-partition story |
| Time-series DB | **Tiger Data** (PostgreSQL extension, port 5432) | MLH prize; continuous aggregates feed charts |
| AI | **Gemini API** (`gemini-2.0-flash`, `google-genai`) | MLH prize; 3 real features |
| Frontend | Vite + React + Tailwind + Recharts | Fast, familiar, dark control-plane UI |
| Real compute | Docker + PyTorch `worker.py` on B's machine | The "A uses B's GPU" proof |
| Optional | MongoDB Atlas (event log only) | If time remains |
| Deploy | **None — local / on-laptop only** | Decided for this edition |

### 4.2 Data model (YugabyteDB)

```sql
orgs(id, name, type, balance_usd)                -- Atlas Bank, QuantEdge, MedAI…
hosts(id, name, region, org_id, gpu_model, vram_gb, total_slices,
      isolation_tier,   -- 'confidential' | 'vgpu' | 'plain'
      trust_score, status)                       -- online / draining / offline
slices(id, host_id, slice_id, status, current_tenant)   -- free / rented / reserved
jobs(id, org_id, name, vram_req, isolation_req, duration_s, status,
     host_id, cost_expected, created_at)
transactions(id, from_org, to_org, job_id, amount, per_second, ts)  -- chargeback ledger
events(id, kind, payload_json, ts)               -- audit log, replayed on /events
```

### 4.3 REST surface

```
GET  /orgs                     GET  /prices
GET  /hosts                    GET  /ledger
GET  /jobs                     GET  /results/{job_id}        (real worker output)
POST /allocate {job}           POST /reclaim {host_id}       (real writes)
GET  /history?metric=util&window=5m                            (Tiger Data)
GET  /events  (SSE stream)
POST /actors/register          POST /actors/{id}/jobs         (host agent ↔ broker)
Demo triggers:  POST /demo/burst  ·  /demo/reclaim  ·  /demo/attest  ·  /demo/shred
```

---

## 5. What's Real vs Simulated (honesty boundary)

| Layer | Status |
|---|---|
| Scheduling, tier enforcement, metering, ledger, pricing, chargeback | ✅ **Real code, real data** (SQLAlchemy → Yugabyte) |
| Host fleet breadth (12 nodes), utilization telemetry, market prices | 🟡 Simulated — bounded random-walk pump + seeded history |
| **A's computation on B's GPU** | ✅ **Genuinely real** — Docker + PyTorch worker, real artifact |
| Attestation / confidential-Crypto claims | 🟡 Enforced as product rules; hardware-CC claims live on the architecture slide |
| Gemini decisions & explanations | ✅ Real API calls, grounded in real DB rows |

Pitch line: marketplace mechanics are real on a real distributed database; fleet breadth is a simulation; the centerpiece computation is verifiably real.

---

## 6. GPU Processing — How It Works

### 6.1 Job lifecycle (demo machinery)

```
submit → 1. SCHEDULED   fit-check vs `slices`: VRAM / tier / region → real row
        → 2. PROVISIONING  "pulling image", "initializing CUDA context" (2–4 s)
        → 3. RUNNING       1/s ticks: util%, loss↓, tokens/s, ETA, cost meter
        → 4. CHECKPOINTING "saving weights…" (1–2 s, loss curve continues on resume)
        → 5. COMPLETED     release slice → ledger debit/credit (real row)
```

### 6.2 Scheduler (the real logic)

```python
def schedule(job):
    candidates = [s for s in free_slices
                  if s.vram_gb >= job.vram_gb
                  and TIER_PRIORITY[s.tier] >= TIER_PRIORITY[job.tier_req]
                  and s.region == job.region]
    if not candidates:
        return None                       # stays queued → queue-pressure pricing
    return min(candidates, key=lambda s: (s.price_per_sec, -s.trust_score))
```

### 6.3 Telemetry pump (what makes it look alive)

```python
# per running job, every second:
if job.phase == "compute":
    job.util = clamp(0.6 + random()*0.35 + burst(), 0, 0.97)   # "kernel phases"
    job.loss -= round(random()*0.02 + 0.005, 4)                # loss descending = training
    job.tokens += 9000 + randint(0, 3000)
emit_sse({"type":"job.tick", job_id, util, loss, tokens, cost: rate*elapsed})
```

**The descending loss curve is the single most convincing artifact** — judges' eyes go there before any number.

### 6.4 Real execution (host agent on B)

```
A (browser) → broker → host agent on B → docker run --rm --gpus all pytorch/pytorch:latest python /work/worker.py
```
- Agent registers with broker on boot → host appears in the fleet grid.
- `worker.py` (part of the repo) auto-selects `cuda` → `cpu` fallback; dense matmul+softmax loop prints live loss; writes `/out/output.json` containing `{"device": "cuda", "elapsed": 41, "matmul_flops": 8.4e15}`.
- Agent streams stdout + `nvidia-smi --query-gpu=utilization.gpu` polls → broker relays via SSE → A's dashboard shows live loss stream **and B's real GPU gauge**, then a **Download result** button.
- Data plane: A uploads `input.pt` → broker → agent mounts as `/data` → results copied back → `GET /results/{job_id}`.

### 6.5 What "time-slicing" means in reality (pitch knowledge)

- **vGPU time-slicing:** GPU scheduler time-quantizes SMs across VMs — cheap, no guaranteed QoS.
- **MIG (Multi-Instance GPU):** hardware partitioning — each slice owns dedicated SMs, L2, memory controllers, VRAM. This is the "hardware isolation" badge. A's kernel physically cannot touch B's.
- **Honest constraint to say out loud:** hostile multi-tenancy on consumer GPUs isn't possible today — only MIG-backed vGPU on datacenter cards (H100/B200/RTX Pro) gives hardware isolation. Arius prices that into the tier model (this paragraph is a *strength* when said on stage).

---

## 7. Privacy & Data Protection

### 7.1 The threat model (asked & answered)

- **Default naive rental:** B (host root) CAN see A's VRAM, RAM, disk, and network. No

 technical guarantee with a plain VM.
- **Arius's answer — tier enforcement:**
  - `confidential` tier: CC-capable datacenter cards (H100+), attestation-gated booking, encrypted-at-rest client-side data, keys released only after attestation quote verifies, hardware-memory shred on teardown.
  - `vgpu` tier: software isolation — good for intra-org / low-sensitivity.
  - `plain` tier: contractual best-effort; UI labels it "non-sensitive workloads only".
- **What host B still learns (documented limitation):** timing, power, traffic volume — side channels. Say this; it's the mark of real understanding.

### 7.2 Enforced in product, not just UI

- Mandatory isolation requirement at booking; `schedule()` refuses mismatches (confidential job on plain host → red toast).
- Attestation panel (demo trigger `/demo/attest`): "CPU TEE ✓ → GPU CC attestation ✓ → firmware hash ✓ → ✅ keys released" then booking unlocks.
- Shred-on-teardown visual (`/demo/shred`) + "Data destroyed" cert toast.
- Region-residency: region-tagged tenants mapped to region-tagged DB placement (geo-partition slide).

---

## 8. Sponsor Integrations (real work, demoable)

### 8.1 YugabyteDB (project sponsor)

- **3-node Docker cluster** (compose in repo); SQLAlchemy points at `yb-tserver:5433` (**Yugabyte's Postgres port is 5433 — classic pitfall**).
- Schema (§4.2) lives in Yugabyte; `POST /allocate` and every ledger write are real Raft-committed rows.
- **Money demo (10 s):** `docker stop yb-2` → dashboard widget "DB: 3/3 → 2/3, Raft re-elected, 0 lost bookings" → jobs keep flowing.
- Geo-partitioning DDL (`PARTITION BY LIST (region)`, tablespace per region) on the architecture slide — cut candidate if time runs out (the node-kill carries 90% of the value).

### 8.2 Tiger Data (time-series)

- All telemetry (`metrics(host_id, ts, util, power, temp)`) lands in Tiger Data; a **continuous aggregate** `util_1m` powers every dashboard chart → "lag-free dashboards" is literally true.
- Retention + compression story: "millions of metric rows compressed to ~1 GB" → a believable slide number.
- PG wire protocol → same SQLAlchemy code, tiny delta.

### 8.3 Gemini API — 3 features that do real work

**A. Natural-language capacity broker (the showcase):**
```python
resp = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=f"Given these hosts: {host_json}\nFulfill: {user_text}\nReturn JSON: "
             "{recommended:[host_ids], tier, total_cost, reason}")
decision = json.loads(resp.text)   # then the app executes the real /allocate
```
Demo: *"Book 2 confidential H100 slices in EU-West for 3 hours under $2.10/hr"* → decision JSON → allocation executes with the Gemini reason shown on a side panel.

**B. Compliance guardrail:** before any booking, Gemini checks job description vs policy (e.g., "medical records" → require confidential + EU region) and blocks with a red card. The privacy story with teeth; protects against the "can B see A's data" concern.

**C. Fleet Analyst (optional):** "Why did Atlas Bank's spend spike 40% on 22 Oct?" → real group-by SQL on the ledger → actual rows → Gemini rewrites rows into prose + chart. **Rule: Gemini only renders real query results — zero hallucinated numbers.**

Offline insurance: cache ~10 canned responses keyed by request hash; on API failure serve cache + "⚠ offline mode" badge (venue Wi-Fi is the single point of failure for everything local).

---

## 9. Implementation Plan — 24-Hour Sprint

### Phase 0 — Infrastructure & Skeleton (Hour 0–1.5)

| Step | Task | Delivers |
|---|---|---|
| 0.1 | Prime Docker: pull `pytorch/pytorch` image + start both DBs on both laptops during registration | Warm image (6–9 GB) |
| 0.2 | Docker Compose: 3-node Yugabyte (5433) + Tiger Data (5432) | Both sponsor DBs up |
| 0.3 | FastAPI app: dual SQLAlchemy engines, `/health` checks both | Skeleton online |
| 0.4 | Vite + React + Tailwind shell, dark theme, Recharts installed | Shell renders |
| 0.5 | `init_db.py` schema-recreation script (clean rebuild < 60 s) | Reproducible |
| 0.6 | Discord check: sponsor-booth submission rules | Eligibility prepped |

**Exit:** 5 containers healthy, both /health green. *The only infra-risky hour — rehearse at home once.*

### Phase 1 — Backend Core + Seeded Universe (Hours 1.5–4)

| Step | Task | Delivers |
|---|---|---|
| 1.1 | Schema + seed: 12 hosts (H100 CC / A100 vGPU / RTX4090 plain), 6 orgs, 25 queued jobs | Believable world |
| 1.2 | REST surface §4.3; `/allocate` is a **real Yugabyte write** | API complete |
| 1.3 | Tiger Data: metrics table + continuous aggregate; seed 200 rows/host | Chart data path |
| 1.4 | SSE pump `/events` (1/s ticks + scripted events) | Live system |
| 1.5 | Pricing: `price = reference × (1 + queue_pressure) × tier_multiplier`; per-second meter → ledger | Money math real |
| 1.6 | Hidden demo triggers: `/demo/burst`, `/demo/reclaim` | Demo control |

**Exit:** `/hosts` → 12 hosts; `/allocate` survives restart; SSE alive.

### Phase 2 — Frontend Dashboard (Hours 4–7)

One screen, five regions: **top bar** (pool totals + live $/hr + "DB 3/3 healthy" widget) · **fleet grid** (12 host cards: model, VRAM bar, isolation badge 🛡/◈/⊘, trust score, util gauge, status dot) · **charts** (5-min utilization from Tiger continuous aggregate) · **job queue** (org, job, VRAM, tier, status pill, live cost) · **event log** (colored SSE feed).

Steps: 2.1 mock-data layout → 2.2 `/hosts` polling → 2.3 **SSE wiring early** (the "it's alive" moment) → 2.4 per-host sparklines → 2.5 load mix so the story reads (~3 hot / ~7 moderate / ~2 idle).

### Phase 3 — Marketplace & B2B Mechanics (Hours 7–10)

| Step | Feature | Story |
|---|---|---|
| 3.1 | Org switcher (Atlas Bank / QuantEdge / MedAI) | Multi-tenant B2B |
| 3.2 | Booking modal: GPU → VRAM → **mandatory isolation** → duration → real allocation, cost ticks | Core interaction |
| 3.3 | Chargeback ledger panel + weekly summary bars | Money narrative |
| 3.4 | Trust-tier filter chips (query the backend) | Product depth |
| 3.5 | **Enforcement:** confidential booking on plain host → red toast refusal | Privacy with teeth |

**Exit:** 3.5 works in both directions (plain → refused, CC → succeeds).

### Phase 4 — Real GPU Execution (Hours 9–12) — *the keystone*

| Step | Task | Time |
|---|---|---|
| 4.1 | `host_agent/` FastAPI daemon on B: register, run `docker run --rm --gpus all`, stream stdout | 2 h |
| 4.2 | `worker.py`: device auto-select, matmul+softmax loop with loss prints, writes `/out/output.json` | 30 min |
| 4.3 | Broker: actor API, uploads/results endpoints, agent stdout → existing SSE relay | 1 h |
| 4.4 | GPU poller: `nvidia-smi` → B's card as a live gauge on A's dashboard | 30 min |
| 4.5 | UI: "Run real computation", result card + **Download**, B's machine status card | 1 h |
| 4.6 | Rehearse 3 modes: two laptops on one Wi-Fi → single machine (`:8000` + `:9001`) → CPU fallback | 30 min |

**Exit: from A's screen — submit → live loss stream while B's nvidia-smi spikes → download real output.json.**

### Phase 5 — Gemini AI Layer (Hours 11–13)

5.1 NL Capacity Broker (executes a real allocation) · 5.2 Compliance Guardrail (blocks a bad one) · 5.3 *Optional* Fleet Analyst. Key in `.env`; live "Gemini: decision in 1.2 s" badge.

### Phase 6 — Demo Theater & Sponsor Evidence (Hours 13–15)

Prepare the 2-minute script (§10), wire the four demo triggers, run the sponsor-evidence checklist (§11).

### Phase 7 — Hardening & Pitch (Hours 15–18; 4–6 h buffer + sleep)

| Step | Task |
|---|---|
| 7.1 | Pre-seed 5 min metric history; tune pump baselines for the "before" shot |
| 7.2 | **Local-only hardening:** both DBs + Docker images primed on both laptops; verify venue Wi-Fi allows broker ↔ agent traffic (test early — fall back to single-machine mode if isolated) |
| 7.3 | README: architecture ASCII, API list, **3 run modes**, sponsor section with screenshots |
| 7.4 | Deck (8 slides): Problem → Market → Tier model → Privacy stance → Architecture (Yugabyte/Tiger/Gemini) → Live demo → Roadmap (Solana escrow, RDMA) → Team |
| 7.5 | Drills: kill backend → restart persists; refresh mid-demo; **venue Wi-Fi dies → Gemini offline cache + local-only demo**; downgrade to CPU mode |
| 7.6 | Rehearse arc 3× with stopwatch |

---

## 10. Demo Script — the 2-Minute Arc (memorize, don't read)

```
0:00  "Before": fleet at ~14% night util; 25-job queue (charts served by Tiger Data).
0:15  Frame: "Enterprise fleets idle at night… this is idle revenue."
0:20  REAL: QuantEdge books a slice on AtlasBank-H03 → B's machine runs the torch worker
      → live loss stream + nvidia-smi spike + cost meter.                 ← keystone
0:50  Gemini: "2 confidential H100 slices in EU-West under $2.10/hr" → decision JSON →
      executes; a second request blocked by the compliance guardrail.     ← AI prize
1:10  Spike: /demo/burst → queue pressure → prices climb animated.
1:25  Privacy: attestation panel → "keys released" → confidential booking unlocked.
1:40  Chaos: /demo/reclaim → 30 s warning → migration, loss curve continues;
      then Yugabyte node-kill → "Raft re-elected, 0 lost bookings".        ← sponsor
2:00  Close: ledger "+$38k/mo reclaimed", refresh page → state persists,
      result file still downloadable.                                     ← FinTech
```

---

## 11. Sponsor Evidence Tracker

| Prize | The 20-second proof | Where |
|---|---|---|
| Gemini | NL request → structured decision → real allocation + compliance block | Booking modal + side panel |
| Tiger Data | Charts update from a continuous aggregate; "12M rows compressed" stat | Charts pane + slide |
| Yugabyte (sponsor) | Node-kill → Raft re-elect → "0 lost bookings" toast | Chaos beat + top-bar widget |
| MongoDB Atlas (optional) | Event log tab backed by Atlas | Event log panel |

---

## 12. Submission Checklist (must all be in the repo at hand-in)

- [ ] 12-host fleet with tier badges + trust scores
- [ ] Booking with isolation-tier enforcement (backend rule, not UI-only)
- [ ] Live SSE pump + event log
- [ ] Per-second metering → real ledger rows
- [ ] **One real computation:** host agent + PyTorch worker + downloadable result
- [ ] Yugabyte 3-node cluster + kill-and-survive behavior
- [ ] Tiger Data continuous aggregates powering charts
- [ ] 3 Gemini features (broker, guardrail, analyst) + offline cache fallback
- [ ] Orgs + chargeback ledger UI
- [ ] Demo triggers (burst / reclaim / attestation / node-kill)
- [ ] Pre-seeded history (charts never open empty)
- [ ] README with sponsor badges, architecture, 3 run modes

## 13. Cut-If-Behind (in order) & Scope Shields

**Cut first:** 1. Gemini Feature C · 2. MongoDB Atlas event log · 3. Geo-partition DDL (keep node-kill) · 4. Trust-score animation depth.

**Never build:** auth/SSO (org switcher says it) · real payments (ledger says it) · K8s/vGPU/hypervisor (architecture slide says it) · multi-node RDMA (roadmap says it) · real confidential-computing crypto (attestation panel says it).
Deployment (DO/Vultr) — explicitly out of scope this edition.

---

## 14. Run Modes & Fallbacks

1. **Two laptops, one Wi-Fi** (preferred): A dashboard + broker on laptop 1; host agent on laptop 2 (needs Docker + NVIDIA Container Toolkit; verify `docker run --rm --gpus all nvidia/cuda:12.4.0-base nvidia-smi`).
2. **Single machine** (`:8000` broker, `:9001` agent) — the rehearsal/backup mode; host named "AtlasBank-H03".
3. **CPU fallback** — `worker.py` auto-switches to `cpu`; UI badge "compute: CPU fallback"; story intact: "the fabric is hardware-agnostic."

---

## 15. Target Repo Structure

```
Arius/
├── PROJECT.md            ← this file
├── README.md             ← badges, pitch, quickstart, 3 run modes
├── docker-compose.yml    ← 3-node Yugabyte + Tiger Data
├── backend/              ← FastAPI broker (SQLAlchemy ×2, SSE pump, scheduler,
│                            pricing/billing, demo triggers, Gemini client)
├── host_agent/           ← the daemon that runs on org B's machine
├── worker/               ← worker.py (torch matmul, device auto-select)
├── frontend/             ← Vite + React + Tailwind + Recharts dashboard
├── seeds/                ← init_db.py + seed data (hosts, orgs, jobs, history)
└── scripts/              ← run-modes, docker-prune, verify-gpu checks
```

---

## 16. Shot List — What Each Audience Takes Away

| Audience | Message |
|---|---|
| Main judges (Cloud) | A fault-tolerant B2B marketplace renting enterprise GPU idle-time as hardware-isolated slices, per-second settlement, privacy enforced end-to-end — including in the database |
| Gemini judges | 3 features doing real work: negotiating bookings against live supply, enforcing policy from free text, explaining actual billing data |
| Yugabyte sponsor booth | A distributed broker for distributed compute — kill a DB node live, nothing drops |
| Special-category judges | Underfunded orgs buy verified idle capacity at spot prices — democratizing AI compute |

---

*This document is the single source of truth for the hackCBS 9.0 build. Phases assume a 3–4 person team; hours are optimistic-but-sequenced — if the team slips, follow the cut list (§13) before compromising the keystone Phase 4.*
