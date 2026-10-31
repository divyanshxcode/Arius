import { Dot, Pill, TierBadge, Bar } from "./ui.jsx";

function Stat({ label, value, sub, tone = "mint" }) {
  const toneClass = { mint: "text-mint", cyan: "text-cyan", amber: "text-amber" }[tone] || "text-mint";
  return (
    <div className="rounded-lg border border-line/70 bg-ink/40 px-3 py-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-muted">{label}</div>
      <div className={`mt-0.5 font-mono text-[19px] leading-tight ${toneClass}`}>{value}</div>
      {sub && <div className="text-[10.5px] text-muted">{sub}</div>}
    </div>
  );
}

export default function StatStrip({ pool, dbHealthy }) {
  const p = pool || {};
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
      <Stat label="hosts online" value={`${p.hosts_online ?? "—"}/${p.hosts ?? "—"}`} sub="fleet" />
      <Stat
        label="slices rented"
        value={`${p.slices_rented ?? 0}/${p.slices_total ?? 0}`}
        sub={`${p.utilization_pct ?? 0}% utilized`}
        tone="cyan"
      />
      <Stat label="jobs running" value={p.jobs_running ?? 0} sub={`${p.jobs_queued ?? 0} queued`} />
      <Stat label="queue pressure" value={(p.queue_pressure ?? 0).toFixed(2)} sub="× price multiplier" tone="amber" />
      <Stat label="in-use value" value={`$${(p.in_use_value_per_hour ?? 0).toFixed(2)}`} sub={`of $${(p.list_value_per_hour ?? 0).toFixed(2)}/hr`} />
      <div className="flex flex-col justify-center rounded-lg border border-line/70 bg-ink/40 px-3 py-2">
        <div className="text-[10px] uppercase tracking-[0.14em] text-muted">stores</div>
        <div className="mt-1 flex items-center gap-2">
          <Dot tone={dbHealthy ? "mint" : "rose"} />
          <span className="font-mono text-[12px] text-slate-300">{dbHealthy ? "3/3 nodes" : "degraded"}</span>
        </div>
        <div className="mt-1 flex gap-1">
          <Pill tone="mint">YUGABYTE</Pill>
          <Pill tone="cyan">TIGER</Pill>
        </div>
      </div>
    </div>
  );
}

export function HostCard({ host, live }) {
  const util = live?.util ?? host.utilization_pct ?? 0;
  const rented = host.slices_rented ?? 0;
  const total = host.slices_total ?? 1;
  const tierTone = host.isolation_tier === "confidential" ? "mint" : host.isolation_tier === "vgpu" ? "cyan" : "muted";
  const statusTone = host.status === "online" ? "mint" : host.status === "draining" ? "amber" : "rose";

  return (
    <div className="rounded-lg border border-line/80 bg-ink/40 p-3 transition-colors hover:border-line">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <Dot tone={statusTone} />
            <span className="truncate text-[12.5px] font-medium text-slate-200">{host.name}</span>
          </div>
          <div className="mt-0.5 truncate font-mono text-[10.5px] text-muted">
            {host.gpu_model} · {host.vram_gb}GB · {host.region}
          </div>
        </div>
        <TierBadge tier={host.isolation_tier} />
      </div>

      <div className="mt-2.5 flex items-end justify-between">
        <div>
          <div className="font-mono text-[20px] leading-none text-slate-100">{util.toFixed(0)}<span className="text-[11px] text-muted">%</span></div>
          <div className="mt-0.5 text-[10px] text-muted">utilization</div>
        </div>
        <div className="text-right">
          <div className="font-mono text-[12px] text-slate-300">{rented}/{total} slices</div>
          <div className="text-[10px] text-muted">${host.price_per_hour?.toFixed(2)}/hr list</div>
        </div>
      </div>

      <Bar value={util} tone={tierTone === "muted" ? "amber" : tierTone} className="mt-2" />

      <div className="mt-2 flex items-center justify-between text-[10px] text-muted">
        <span>trust {host.trust_score}</span>
        <span className="font-mono">
          {live ? `${live.temp?.toFixed(0)}°C · ${live.power?.toFixed(0)}W` : `${host.slices_free} free`}
        </span>
      </div>
    </div>
  );
}
