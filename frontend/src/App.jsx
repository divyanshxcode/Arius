import { useEffect, useState } from "react";

/* ------------------------------------------------------------------ */
/* Phase 0 shell: proves the broker is alive and BOTH stores answer.   */
/* Phase 1 fills the fleet grid, Phase 2 the charts, Phase 3 the       */
/* booking flow, Phase 4 the real host agent.                          */
/* ------------------------------------------------------------------ */

const PHASE = "Phase 0 · skeleton";

function Pill({ tone = "muted", children }) {
  const tones = {
    mint: "bg-mint/10 text-mint border-mint/30",
    amber: "bg-amber/10 text-amber border-amber/30",
    rose: "bg-rose/10 text-rose border-rose/30",
    cyan: "bg-cyan/10 text-cyan border-cyan/30",
    muted: "bg-white/5 text-muted border-line",
  };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

function Dot({ tone = "mint" }) {
  const map = {
    mint: "bg-mint",
    amber: "bg-amber",
    rose: "bg-rose",
    muted: "bg-slate-600",
  };
  return <span className={`h-1.5 w-1.5 rounded-full ${map[tone]}`} />;
}

function Card({ title, right, children, className = "" }) {
  return (
    <section
      className={`rounded-xl border border-line bg-panel/80 shadow-[0_1px_0_0_rgba(255,255,255,0.03)_inset] ${className}`}
    >
      <header className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-muted">
          {title}
        </h2>
        {right}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Placeholder({ label }) {
  return (
    <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-line/80 bg-white/[0.015] text-[12px] text-muted">
      {label}
    </div>
  );
}

function StoreRow({ name, info, fallbackLabel = "SQLite dev fallback", forceFallback = false }) {
  const down = !info || info.connected === false;
  const fallback = info?.fallback_sqlite || forceFallback;
  const tone = down ? "rose" : fallback ? "amber" : "mint";
  const label = down ? "DOWN" : fallback ? fallbackLabel.toUpperCase() : "CONNECTED";
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-line/70 bg-ink/40 px-3 py-2.5">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Dot tone={tone} />
          <span className="text-[13px] font-medium text-slate-200">{name}</span>
        </div>
        <p className="mt-1 truncate font-mono text-[11px] text-muted">
          {info?.target || "—"}
        </p>
        {info?.error && (
          <p className="mt-1 line-clamp-1 font-mono text-[10px] text-rose/80">
            {info.error}
          </p>
        )}
      </div>
      <Pill tone={tone}>{label}</Pill>
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [lastSync, setLastSync] = useState(null);

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const res = await fetch("/health", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (!alive) return;
        setHealth(data);
        setError(null);
        setLastSync(new Date());
      } catch (e) {
        if (!alive) return;
        setError(e.message);
      }
    }
    tick();
    const id = setInterval(tick, 5000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const dbs = health?.databases;
  const yb = dbs?.yugabyte;
  const tiger = dbs?.tiger;
  const tigerFallback = (tiger?.target || "").startsWith("fallback");
  const brokerUp = !!health && !error;

  return (
    <div className="mx-auto max-w-[1440px] px-5 py-5">
      {/* header */}
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-lg border border-mint/30 bg-mint/10">
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none">
              <path d="M12 3l7.5 4.5v9L12 21l-7.5-4.5v-9L12 3z" stroke="#3ddc97" strokeWidth="1.4" />
              <path d="M12 8.2l3.8 2.3v4.6L12 17.4l-3.8-2.3v-4.6L12 8.2z" stroke="#4cc9f0" strokeWidth="1.1" />
            </svg>
          </div>
          <div>
            <div className="flex items-baseline gap-2">
              <h1 className="text-[18px] font-semibold tracking-[0.22em] text-white">ARIUS</h1>
              <span className="text-[12px] text-muted">B2B GPU time-slicing fabric</span>
            </div>
            <p className="text-[11px] text-muted">
              hackCBS 9.0 · Cloud track · MLH 2027
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Pill tone="cyan">{PHASE}</Pill>
          <Pill tone="muted">
            viewing as <span className="text-slate-300">Atlas Bank</span>
          </Pill>
        </div>
      </header>

      {/* store status */}
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-line bg-panel/80 p-4">
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-semibold uppercase tracking-[0.14em] text-muted">
              Broker
            </span>
            <Pill tone={brokerUp ? "mint" : "rose"}>{brokerUp ? "UP" : "DOWN"}</Pill>
          </div>
          <p className="mt-2 font-mono text-[12px] text-slate-300">
            {brokerUp ? "arius-broker · v0.1.0" : `unreachable${error ? ` · ${error}` : ""}`}
          </p>
          <p className="mt-1 font-mono text-[11px] text-muted">
            {lastSync ? `last sync ${lastSync.toLocaleTimeString()}` : "waiting…"}
          </p>
        </div>

        <div className="rounded-xl border border-line bg-panel/80 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[12px] font-semibold uppercase tracking-[0.14em] text-muted">
              YugabyteDB
            </span>
            <Pill tone={yb?.connected ? (yb?.fallback_sqlite ? "amber" : "mint") : "rose"}>
              {yb?.connected ? (yb?.fallback_sqlite ? "FALLBACK" : "CONNECTED") : "DOWN"}
            </Pill>
          </div>
          <StoreRow name="transactional state" info={yb} />
        </div>

        <div className="rounded-xl border border-line bg-panel/80 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[12px] font-semibold uppercase tracking-[0.14em] text-muted">
              Tiger Data / Timescale
            </span>
            <Pill tone={!tiger?.connected ? "rose" : tigerFallback ? "amber" : "mint"}>
              {!tiger?.connected ? "DOWN" : tigerFallback ? "FALLBACK" : "CONNECTED"}
            </Pill>
          </div>
          <StoreRow name="time-series telemetry" info={tiger} forceFallback={tigerFallback} fallbackLabel="shared file fallback" />
        </div>
      </div>

      {/* body placeholders */}
      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <Card
          className="lg:col-span-2"
          title="Fleet & telemetry"
          right={<Pill tone="muted">Phase 2</Pill>}
        >
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 12 }).map((_, i) => (
              <div
                key={i}
                className="rounded-lg border border-dashed border-line/70 bg-white/[0.015] p-2.5"
              >
                <div className="flex items-center justify-between">
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-700" />
                  <span className="font-mono text-[10px] text-muted">slot {i + 1}</span>
                </div>
                <div className="mt-2 h-1.5 w-full rounded-full bg-line/60" />
                <div className="mt-1.5 h-1 w-2/3 rounded-full bg-line/40" />
              </div>
            ))}
          </div>
          <div className="mt-3">
            <Placeholder label="utilization chart — Tiger continuous aggregate (Phase 2)" />
          </div>
        </Card>

        <div className="grid gap-3">
          <Card title="Job queue" right={<Pill tone="muted">Phase 3</Pill>}>
            <Placeholder label="queued / running jobs (Phase 1 API → Phase 3 UI)" />
          </Card>
          <Card title="Event log" right={<Pill tone="muted">Phase 1 SSE</Pill>}>
            <Placeholder label="live SSE feed (Phase 1.4)" />
          </Card>
          <Card title="Real compute" right={<Pill tone="amber">Phase 4</Pill>}>
            <Placeholder label="host agent on org B's GPU" />
          </Card>
        </div>
      </div>

      {/* phase 0 checklist */}
      <Card
        className="mt-3"
        title="Phase 0 exit checklist"
        right={<Pill tone="mint">skeleton</Pill>}
      >
        <ul className="grid gap-2 text-[13px] sm:grid-cols-2 lg:grid-cols-4">
          {[
            "Broker runs (FastAPI + uvicorn)",
            "Dual-engine layer + live /health",
            "Schema script (Yugabyte / Tiger / SQLite)",
            "Seeded universe (12 hosts · 6 orgs · 25 jobs)",
          ].map((t) => (
            <li key={t} className="flex items-start gap-2 rounded-lg border border-line/60 bg-ink/40 px-3 py-2">
              <span className="mt-0.5 text-mint">✓</span>
              <span className="text-slate-300">{t}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[12px] text-muted">
          Next: <span className="text-slate-300">Phase 1 — REST surface, SSE pump, pricing &amp; ledger.</span>{" "}
          Run <code className="rounded bg-white/5 px-1.5 py-0.5 font-mono text-[11px] text-cyan">python -m seeds.init_db --seed --force</code> to reseed.
        </p>
      </Card>
    </div>
  );
}
