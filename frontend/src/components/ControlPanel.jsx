import { useEffect, useRef, useState } from "react";
import { getJSON, money } from "../lib/api";

function post(path, body) {
  return fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => {
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    return data;
  });
}

export default function ControlPanel({ onBook, orgId }) {
  /* ---------- real GPU execution (Phase 4) ---------- */
  const [exec, setExec] = useState(null);      // {job_id, actor, host}
  const [state, setState] = useState(null);    // /exec/{id}
  const [execErr, setExecErr] = useState(null);
  const [starting, setStarting] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    if (!exec) return;
    let alive = true;
    const poll = async () => {
      try {
        const s = await getJSON(`/exec/${exec.job_id}`);
        if (!alive) return;
        setState(s);
        if (s.status !== "completed" && s.status !== "failed") timer.current = setTimeout(poll, 1500);
      } catch (e) {
        if (alive) setExecErr(e.message);
      }
    };
    poll();
    return () => {
      alive = false;
      clearTimeout(timer.current);
    };
  }, [exec]);

  const runReal = async () => {
    setStarting(true);
    setExecErr(null);
    setState(null);
    try {
      const res = await post("/exec", { org_id: Number(orgId), name: "real-gpu-run", units: 40000 });
      setExec(res);
    } catch (e) {
      setExecErr(e.message);
    } finally {
      setStarting(false);
    }
  };

  /* ---------- Gemini (Phase 5) ---------- */
  const [ask, setAsk] = useState("2 confidential H100 slices in ap-south for 3 hours under $2.10/hr");
  const [plan, setPlan] = useState(null);
  const [check, setCheck] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiErr, setAiErr] = useState(null);
  const [aiStatus, setAiStatus] = useState(null);

  useEffect(() => {
    getJSON("/ai/status").then(setAiStatus).catch(() => {});
  }, []);

  const askBroker = async () => {
    setAiBusy(true);
    setAiErr(null);
    setCheck(null);
    try {
      setPlan(await post("/ai/plan", { text: ask }));
    } catch (e) {
      setAiErr(e.message);
    } finally {
      setAiBusy(false);
    }
  };

  const policyCheck = async () => {
    setAiBusy(true);
    setAiErr(null);
    setPlan(null);
    try {
      setCheck(await post("/ai/compliance", { text: ask, tier: "vgpu" }));
    } catch (e) {
      setAiErr(e.message);
    } finally {
      setAiBusy(false);
    }
  };

  const logs = state?.logs || [];

  return (
    <div className="flex h-full flex-col gap-3">
      {/* demo triggers */}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] uppercase tracking-[0.14em] text-muted">demo</span>
        <button
          onClick={async () => {
            try {
              await post("/demo/burst?count=14", {});
            } catch (e) {
              setAiErr(e.message);
            }
          }}
          className="rounded border border-rose/40 bg-rose/10 px-2 py-0.5 text-[10px] text-rose"
        >
          load burst
        </button>
        <button
          onClick={async () => {
            try {
              await post("/demo/reclaim", {});
            } catch (e) {
              setAiErr(e.message);
            }
          }}
          className="rounded border border-amber/40 bg-amber/10 px-2 py-0.5 text-[10px] text-amber"
        >
          drain busiest host
        </button>
      </div>

      {/* Phase 4 */}
      <div>
        <div className="flex items-center justify-between">
          <div className="text-[10px] uppercase tracking-[0.14em] text-muted">
            real execution · org B&apos;s GPU
          </div>
          <button
            onClick={runReal}
            disabled={starting}
            className="rounded border border-cyan/40 bg-cyan/10 px-2.5 py-1 text-[10.5px] font-medium text-cyan disabled:opacity-50"
          >
            {starting ? "dispatching…" : "run on host agent"}
          </button>
        </div>

        {execErr && <div className="mt-1 text-[10.5px] text-rose">{execErr}</div>}

        {exec && (
          <div className="mt-1.5 rounded border border-line/70 bg-ink/60 p-2">
            <div className="flex items-center justify-between text-[10px]">
              <span className="font-mono text-slate-300">
                job #{exec.job_id} → {exec.actor}
              </span>
              <span
                className={`rounded border px-1.5 py-0.5 ${
                  state?.status === "completed"
                    ? "border-mint/40 bg-mint/10 text-mint"
                    : "border-cyan/40 bg-cyan/10 text-cyan"
                }`}
              >
                {state?.status || "dispatching"}
              </span>
            </div>

            <pre className="mt-1.5 max-h-[92px] overflow-auto whitespace-pre-wrap font-mono text-[9.5px] leading-snug text-muted">
              {logs.length ? logs.slice(-8).join("\n") : "waiting for agent logs…"}
            </pre>

            {state?.status === "completed" && (
              <div className="mt-1.5 flex items-center justify-between text-[10px]">
                <span className="text-mint">
                  device {state.device} · {state.elapsed_s}s · {money(state.cost, 5)}
                </span>
                <a
                  href={state.artifact}
                  className="rounded border border-mint/40 bg-mint/10 px-2 py-0.5 text-mint"
                  download
                >
                  download result
                </a>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="h-px bg-line" />

      {/* Phase 5 */}
      <div className="flex min-h-0 flex-1 flex-col">
        <div className="flex items-center justify-between">
          <div className="text-[10px] uppercase tracking-[0.14em] text-muted">gemini capacity broker</div>
          <span className="rounded border border-line bg-white/5 px-1.5 py-0.5 font-mono text-[9.5px] text-muted">
            {aiStatus?.configured ? aiStatus.model : "offline rules"}
          </span>
        </div>

        <textarea
          value={ask}
          onChange={(e) => setAsk(e.target.value)}
          rows={2}
          className="mt-1.5 w-full resize-none rounded border border-line bg-ink px-2 py-1.5 text-[11px] text-slate-200"
        />

        <div className="mt-1.5 flex gap-2">
          <button
            onClick={askBroker}
            disabled={aiBusy}
            className="rounded border border-mint/40 bg-mint/10 px-2.5 py-1 text-[10.5px] text-mint disabled:opacity-50"
          >
            ask broker
          </button>
          <button
            onClick={policyCheck}
            disabled={aiBusy}
            className="rounded border border-line px-2.5 py-1 text-[10.5px] text-slate-300 hover:border-rose/40 hover:text-rose disabled:opacity-50"
          >
            policy check
          </button>
          <button
            onClick={onBook}
            className="ml-auto rounded border border-cyan/40 bg-cyan/10 px-2.5 py-1 text-[10.5px] text-cyan"
          >
            book capacity
          </button>
        </div>

        {aiErr && <div className="mt-1 text-[10.5px] text-rose">{aiErr}</div>}

        {plan && (
          <div className="mt-2 rounded border border-line/70 bg-ink/60 p-2 text-[10.5px]">
            <div className="flex items-center justify-between">
              <span className="text-slate-300">
                {plan.tier} · {plan.vram_gb}GB · {plan.duration_h}h · {money(plan.total_cost)}
              </span>
              <span className="font-mono text-[9.5px] text-muted">{plan.source}</span>
            </div>
            <ul className="mt-1 space-y-0.5">
              {(plan.recommended || []).map((r) => (
                <li key={r.host} className="truncate text-muted">
                  · <span className="text-slate-200">{r.host}</span> — {r.why}
                </li>
              ))}
            </ul>
            <div className="mt-1 text-[10px] text-muted">{plan.reason}</div>
          </div>
        )}

        {check && (
          <div
            className={`mt-2 rounded border px-2 py-1.5 text-[10.5px] ${
              check.verdict === "block"
                ? "border-rose/40 bg-rose/10 text-rose"
                : "border-mint/40 bg-mint/10 text-mint"
            }`}
          >
            {check.verdict} — {check.rationale} <span className="text-muted">[{check.source}]</span>
          </div>
        )}
      </div>
    </div>
  );
}
