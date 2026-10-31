import { useEffect, useMemo, useState } from "react";
import { getJSON, fmtMoney, fmtTime } from "../lib/api";

export default function LedgerPanel() {
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const data = await getJSON("/ledger?limit=40");
        if (alive) {
          setRows(data);
          setErr(null);
        }
      } catch (e) {
        if (alive) setErr(e.message);
      }
    };
    load();
    const id = setInterval(load, 4000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const totals = useMemo(() => {
    const byPair = new Map();
    let sum = 0;
    for (const r of rows) {
      const k = `${r.from_org} → ${r.to_org}`;
      byPair.set(k, (byPair.get(k) || 0) + r.amount);
      sum += r.amount;
    }
    return { sum, pairs: [...byPair.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3) };
  }, [rows]);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center justify-between text-[10.5px] text-muted">
        <span>
          settled <span className="font-mono text-amber">{fmtMoney(totals.sum, 4)}</span> across{" "}
          {new Set(rows.map((r) => r.from_org)).size} orgs
        </span>
        <span className="font-mono">per-second metering</span>
      </div>

      {err && <div className="text-[11px] text-rose">{err}</div>}

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <table className="w-full text-left text-[11px]">
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-b border-line/50 last:border-0">
                <td className="py-1 pr-2 font-mono text-[10px] text-muted">{fmtTime(r.ts)}</td>
                <td className="truncate py-1 text-slate-300">
                  {r.from_org} <span className="text-muted">→</span> {r.to_org}
                </td>
                <td className="py-1 text-right font-mono text-[10.5px] text-amber">
                  {fmtMoney(r.amount, 5)}
                </td>
                <td className="py-1 pl-2 text-right font-mono text-[10px] text-muted">#{r.job_id}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td className="py-4 text-center text-[12px] text-muted" colSpan={4}>
                  no settlements yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
