import { useMemo, useState } from "react";
import { getJSON, usePoll, useSSE } from "./lib/api.js";
import { Card, Pill, Dot } from "./components/ui.jsx";
import StatStrip, { HostCard } from "./components/StatStrip.jsx";
import UtilChart from "./components/UtilChart.jsx";
import JobQueue from "./components/JobQueue.jsx";
import EventLog from "./components/EventLog.jsx";
import LedgerPanel from "./components/LedgerPanel.jsx";
import ControlPanel from "./components/ControlPanel.jsx";
import BookingModal from "./components/BookingModal.jsx";

const PHASE = "Phase 5 · demo-ready";
const MAX_EVENTS = 80;
const RENTERS = [
  { id: 2, name: "QuantEdge" },
  { id: 3, name: "MedAI Labs" },
  { id: 5, name: "IIT Delhi Lab" },
];

export default function App() {
  const pool = usePoll(() => getJSON("/pool"), 4000);
  const hosts = usePoll(() => getJSON("/hosts"), 5000);
  const jobs = usePoll(() => getJSON("/jobs?limit=120"), 4000);
  const history = usePoll(() => getJSON("/history?minutes=60"), 20000);
  const health = usePoll(() => getJSON("/health"), 10000);

  const [live, setLive] = useState({});       // host_id -> metrics payload
  const [ticks, setTicks] = useState({});     // job_id -> live tick
  const [events, setEvents] = useState([]);
  const [tickFilter, setTickFilter] = useState("all"); // all | confidential | vgpu | plain
  const [orgId, setOrgId] = useState(2);
  const [booking, setBooking] = useState(false);

  const connected = useSSE((ev) => {
    if (ev.type === "metrics") {
      const map = {};
      for (const h of ev.hosts || []) map[h.id] = h;
      setLive(map);
      return;
    }
    if (ev.type === "job.tick") {
      setTicks((prev) => ({ ...prev, [ev.job_id]: ev }));
      return;
    }
    setEvents((prev) => [...prev.slice(-MAX_EVENTS), ev]);
  });

  const hostList = useMemo(() => {
    const list = hosts.data || [];
    return tickFilter === "all" ? list : list.filter((h) => h.isolation_tier === tickFilter);
  }, [hosts.data, tickFilter]);

  const dbHealthy =
    health.data?.databases?.yugabyte?.ping === "ok" && health.data?.databases?.tiger?.ping === "ok";

  return (
    <div className="mx-auto flex min-h-screen max-w-[1560px] flex-col gap-3 px-4 py-4">
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
            <p className="text-[11px] text-muted">hackCBS 9.0 · Cloud track · MLH 2027</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Pill tone={connected ? "mint" : "rose"}>
            <Dot tone={connected ? "mint" : "rose"} />
            {connected ? "live stream" : "stream offline"}
          </Pill>
          <Pill tone="cyan">{PHASE}</Pill>
          <label className="flex items-center gap-1.5 rounded-full border border-line bg-white/5 px-2 py-0.5 text-[11px] text-muted">
            viewing as
            <select
              value={orgId}
              onChange={(e) => setOrgId(Number(e.target.value))}
              className="bg-transparent text-[11px] text-slate-200 outline-none"
            >
              {RENTERS.map((o) => (
                <option key={o.id} value={o.id} className="bg-panel">
                  {o.name}
                </option>
              ))}
            </select>
          </label>
          <button
            onClick={() => setBooking(true)}
            className="rounded-full border border-mint/40 bg-mint/10 px-3 py-1 text-[11px] font-medium text-mint"
          >
            book capacity
          </button>
        </div>
      </header>

      <StatStrip pool={pool.data} dbHealthy={dbHealthy} />

      <div className="grid min-h-0 flex-1 gap-3 xl:grid-cols-[1.75fr_1fr]">
        {/* left: fleet + chart */}
        <div className="flex min-h-0 flex-col gap-3">
          <Card
            title="Fleet"
            right={
              <div className="flex gap-1">
                {["all", "confidential", "vgpu", "plain"].map((t) => (
                  <button
                    key={t}
                    onClick={() => setTickFilter(t)}
                    className={`rounded-full border px-2 py-0.5 text-[10px] transition-colors ${
                      tickFilter === t
                        ? "border-mint/40 bg-mint/10 text-mint"
                        : "border-line text-muted hover:text-slate-300"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            }
            bodyClass="p-3"
          >
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
              {hostList.map((h) => (
                <HostCard key={h.id} host={h} live={live[h.id]} />
              ))}
              {hostList.length === 0 && (
                <div className="col-span-full grid h-24 place-items-center text-[12px] text-muted">
                  {hosts.error ? `fleet unavailable — ${hosts.error}` : "loading fleet…"}
                </div>
              )}
            </div>
          </Card>

          <Card title="Telemetry" right={<Pill tone="cyan">Tiger Data</Pill>} bodyClass="p-3">
            <UtilChart history={history.data} height={190} />
          </Card>
        </div>

        {/* right: jobs + events */}
        <div className="grid min-h-0 grid-rows-[1.15fr_1fr] gap-3">
          <Card title="Job queue" right={<Pill tone="mint">live</Pill>} bodyClass="px-3 py-2">
            <JobQueue jobs={jobs.data} ticks={ticks} />
          </Card>
          <Card title="Event log" right={<Pill tone="muted">SSE</Pill>} bodyClass="px-3 py-2">
            <EventLog events={events} />
          </Card>
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1.75fr_1fr]">
        <Card title="Chargeback ledger" right={<Pill tone="amber">cross-org</Pill>} bodyClass="px-3 py-2">
          <LedgerPanel />
        </Card>
        <Card title="Controls" right={<Pill tone="cyan">live demo</Pill>} bodyClass="px-3 py-2">
          <ControlPanel orgId={orgId} onBook={() => setBooking(true)} />
        </Card>
      </div>

      <footer className="flex flex-wrap items-center justify-between gap-2 pb-1 text-[10px] text-muted">
        <span>
          scheduling: cheapest eligible host · tier-enforced · multi-slice ·
          billing settled every 10s
        </span>
        <span className="font-mono">
          {pool.error ? `pool: ${pool.error}` : `poll ${new Date().toLocaleTimeString()}`}
        </span>
      </footer>

      <BookingModal open={booking} onClose={() => setBooking(false)} onBooked={() => setBooking(false)} />
    </div>
  );
}
