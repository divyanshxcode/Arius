import { fmtTime } from "../lib/api.js";

const STYLES = {
  "job.scheduled": ["text-cyan", "scheduled"],
  "job.provisioning": ["text-muted", "provisioning"],
  "job.started": ["text-mint", "started"],
  "job.requested": ["text-slate-300", "requested"],
  "job.completed": ["text-mint", "completed"],
  "ledger.settlement": ["text-amber", "settled"],
  "host.draining": ["text-rose", "draining"],
  "host.online": ["text-mint", "online"],
  "demo.burst": ["text-amber", "burst"],
  "system.seeded": ["text-muted", "seeded"],
};

function describe(ev) {
  switch (ev.type) {
    case "job.scheduled":
      return `#${ev.job_id} ${ev.name || ""} → ${ev.host} (${ev.tier}) @ $${Number(ev.rate_per_second || 0).toFixed(5)}/s`;
    case "job.provisioning":
      return `#${ev.job_id} provisioning container`;
    case "job.started":
      return `#${ev.job_id} ${ev.name || ""} computing`;
    case "job.completed":
      return `#${ev.job_id} ${ev.name || ""} done · charged $${Number(ev.charged || 0).toFixed(4)}`;
    case "job.requested":
      return `request #${ev.job_id} ${ev.name || ""} from org ${ev.org_id}`;
    case "ledger.settlement":
      return `${ev.from_org} → ${ev.to_org} $${Number(ev.amount || 0).toFixed(6)} (job #${ev.job_id})`;
    case "host.draining":
      return `${ev.host} draining · ${ev.moved} migrated · ${ev.requeued} requeued`;
    case "host.online":
      return `${ev.host} back online`;
    case "demo.burst":
      return `load spike: ${ev.queued} jobs queued · pressure ${ev.queue_pressure}`;
    default:
      return JSON.stringify(ev).slice(0, 110);
  }
}

export default function EventLog({ events }) {
  const rows = (events || []).slice(-45).reverse();

  return (
    <div className="h-full overflow-y-auto pr-1 font-mono text-[10.5px] leading-relaxed">
      {rows.length === 0 ? (
        <div className="grid h-full place-items-center text-muted">waiting for events…</div>
      ) : (
        rows.map((ev, i) => {
          const [color, label] = STYLES[ev.type] || ["text-muted", ev.type];
          return (
            <div key={`${ev.ts}-${i}`} className="flex gap-2 border-b border-line/40 py-[3px] last:border-0">
              <span className="shrink-0 text-slate-600">{fmtTime(ev.ts)}</span>
              <span className={`w-[68px] shrink-0 ${color}`}>{label}</span>
              <span className="min-w-0 flex-1 truncate text-slate-400">{describe(ev)}</span>
            </div>
          );
        })
      )}
    </div>
  );
}
