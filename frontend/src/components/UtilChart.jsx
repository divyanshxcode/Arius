import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

function buildSeries(history) {
  const pts = history?.points || [];
  if (!pts.length) return [];
  const buckets = new Map();
  for (const p of pts) {
    const key = p.ts.slice(0, 16);
    const cur = buckets.get(key) || { sum: 0, n: 0 };
    cur.sum += p.util;
    cur.n += 1;
    buckets.set(key, cur);
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([ts, v]) => ({
      t: ts.slice(11),
      util: Math.round((v.sum / v.n) * 10) / 10,
    }))
    .slice(-60);
}

export default function UtilChart({ history, height = 200 }) {
  const data = buildSeries(history);
  const source = history?.source || "—";

  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex items-center justify-between text-[10px] text-muted">
        <span>fleet-average GPU utilization · 1-min buckets</span>
        <span className="font-mono">{source}</span>
      </div>
      {data.length === 0 ? (
        <div className="grid flex-1 place-items-center text-[12px] text-muted">collecting telemetry…</div>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
            <defs>
              <linearGradient id="utilFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3ddc97" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#3ddc97" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1b2836" vertical={false} />
            <XAxis dataKey="t" tick={{ fill: "#7d90a4", fontSize: 9 }} minTickGap={28} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: "#7d90a4", fontSize: 9 }} axisLine={false} tickLine={false} width={46} />
            <Tooltip
              contentStyle={{ background: "#0d141c", border: "1px solid #1b2836", borderRadius: 8, fontSize: 11 }}
              labelStyle={{ color: "#7d90a4" }}
              formatter={(v) => [`${v}%`, "avg util"]}
            />
            <Area type="monotone" dataKey="util" stroke="#3ddc97" strokeWidth={1.6} fill="url(#utilFill)" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
