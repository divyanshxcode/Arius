import { Bar, Pill, TierBadge } from "./ui.jsx";
import { fmtDuration, fmtMoney } from "../lib/api.js";

function Row({ job, tick }) {
  const charged = tick?.charged ?? (job.status === "completed" ? job.cost_expected : null);
  const remaining = tick?.remaining_s ?? (job.status === "running" ? null : null);
  const pct = remaining != null && job.duration_s ? 100 * (1 - remaining / job.duration_s) : null;

  const tone =
    job.status === "running" ? "mint" : job.status === "queued" ? "amber" : job.status === "completed" ? "cyan" : "muted";

  return (
    <div className="border-b border-line/60 px-1 py-2 last:border-0">
      <div className="flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[12px] text-slate-200">{job.name}</div>
          <div className="truncate font-mono text-[10px] text-muted">
            {job.org} → {job.host || "unassigned"}
          </div>
        </div>
        <div className="shrink-0 text-right">
          <div className="font-mono text-[12px] text-mint">{charged != null ? fmtMoney(charged) : "—"}</div>
          <Pill tone={tone}>
            <span className="uppercase">{job.status}</span>
          </Pill>
        </div>
      </div>

      <div className="mt-1.5 flex items-center gap-2">
        <Bar value={pct ?? 0} tone={tone === "muted" ? "amber" : tone} className="flex-1" />
        <span className="w-[52px] shrink-0 text-right font-mono text-[10px] text-muted">
          {remaining != null ? fmtDuration(remaining) : job.status === "queued" ? "waiting" : "done"}
        </span>
      </div>

      <div className="mt-1 flex items-center justify-between text-[10px] text-muted">
        <div className="flex items-center gap-1.5">
          <TierBadge tier={job.isolation_tier} />
          <span className="font-mono">{job.vram_req}GB · {job.gpu_model || "any"}</span>
        </div>
        <span className="font-mono">loss {tick?.loss != null ? tick.loss.toFixed(4) : "—"}</span>
      </div>
    </div>
  );
}

export default function JobQueue({ jobs, ticks }) {
  const list = (jobs || []).filter((j) => j.status === "running" || j.status === "queued");
  const running = list.filter((j) => j.status === "running");
  const queued = list.filter((j) => j.status === "queued");
  const shown = [...running, ...queued].slice(0, 9);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-1 flex items-center justify-between text-[10px] text-muted">
        <span>{running.length} running · {queued.length} queued</span>
        <span className="font-mono">live</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {shown.length === 0 ? (
          <div className="grid h-full place-items-center text-[12px] text-muted">no active jobs</div>
        ) : (
          shown.map((j) => <Row key={j.id} job={j} tick={ticks?.[j.id]} />)
        )}
      </div>
    </div>
  );
}
