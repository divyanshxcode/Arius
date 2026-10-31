import { useState } from "react";
import { TIER_STYLE, getJSON, money } from "../lib/api";

const ORGS = [
  { id: 2, name: "QuantEdge" },
  { id: 3, name: "MedAI Labs" },
  { id: 5, name: "IIT Delhi Lab" },
];

const TIERS = ["confidential", "vgpu", "plain"];

export default function BookingModal({ open, onClose, onBooked }) {
  const [orgId, setOrgId] = useState(2);
  const [name, setName] = useState("finetune-run");
  const [vram, setVram] = useState(11);
  const [tier, setTier] = useState("confidential");
  const [duration, setDuration] = useState(120);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [policy, setPolicy] = useState(null);

  if (!open) return null;

  const checkPolicy = async () => {
    setPolicy(null);
    try {
      const res = await fetch("/ai/compliance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: name, tier }),
      }).then((r) => r.json());
      setPolicy(res);
      if (res.verdict === "block") setError(`Blocked by guardrail: ${res.rationale}`);
    } catch (e) {
      setError(e.message);
    }
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/allocate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          org_id: Number(orgId),
          name,
          vram_req: Number(vram),
          isolation_req: tier,
          duration_s: Number(duration),
        }),
      }).then((r) => r.json());
      if (res.scheduled) {
        setResult(res.job);
        onBooked?.();
      } else {
        setError("No eligible capacity right now — the job stays queued (spot demand > supply).");
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
      <div className="w-full max-w-lg rounded-xl border border-line bg-panel p-4 shadow-2xl">
        <div className="flex items-center justify-between">
          <h3 className="text-[13px] font-semibold uppercase tracking-[0.16em] text-slate-200">
            book capacity
          </h3>
          <button onClick={onClose} className="text-[12px] text-muted hover:text-slate-200">
            esc ✕
          </button>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <label className="text-[11px] text-muted">
            renting org
            <select
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              className="mt-1 w-full rounded border border-line bg-ink px-2 py-1.5 text-[12px] text-slate-200"
            >
              {ORGS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name}
                </option>
              ))}
            </select>
          </label>

          <label className="text-[11px] text-muted">
            job name (free text → guardrail)
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full rounded border border-line bg-ink px-2 py-1.5 text-[12px] text-slate-200"
            />
          </label>

          <label className="text-[11px] text-muted">
            VRAM (GB)
            <input
              type="number"
              value={vram}
              min={1}
              max={80}
              onChange={(e) => setVram(e.target.value)}
              className="mt-1 w-full rounded border border-line bg-ink px-2 py-1.5 font-mono text-[12px] text-slate-200"
            />
          </label>

          <label className="text-[11px] text-muted">
            duration (seconds)
            <input
              type="number"
              value={duration}
              min={30}
              step={30}
              onChange={(e) => setDuration(e.target.value)}
              className="mt-1 w-full rounded border border-line bg-ink px-2 py-1.5 font-mono text-[12px] text-slate-200"
            />
          </label>
        </div>

        <div className="mt-3">
          <div className="text-[11px] text-muted">isolation tier (enforced, not cosmetic)</div>
          <div className="mt-1 flex gap-2">
            {TIERS.map((t) => (
              <button
                key={t}
                onClick={() => setTier(t)}
                className={`rounded-full border px-3 py-1 text-[11px] transition-colors ${
                  tier === t
                    ? TIER_STYLE[t].cls
                    : "border-line bg-white/5 text-muted hover:text-slate-200"
                }`}
              >
                {TIER_STYLE[t].label} · {t}
              </button>
            ))}
          </div>
        </div>

        {policy && (
          <div
            className={`mt-3 rounded border px-3 py-2 text-[11.5px] ${
              policy.verdict === "block"
                ? "border-rose/40 bg-rose/10 text-rose"
                : "border-mint/40 bg-mint/10 text-mint"
            }`}
          >
            guardrail [{policy.source}]: {policy.verdict} — {policy.rationale}
          </div>
        )}

        {error && (
          <div className="mt-3 rounded border border-rose/40 bg-rose/10 px-3 py-2 text-[11.5px] text-rose">
            {error}
          </div>
        )}

        {result && (
          <div className="mt-3 rounded border border-mint/40 bg-mint/10 px-3 py-2 text-[11.5px] text-mint">
            job #{result.id} scheduled on <b>{result.host}</b> ({result.gpu_model} ·{" "}
            {result.isolation_tier}) for {money(result.rate_per_second, 5)}/s
          </div>
        )}

        <div className="mt-4 flex items-center justify-between gap-2">
          <button
            onClick={checkPolicy}
            className="rounded border border-line px-3 py-1.5 text-[11.5px] text-slate-300 hover:border-cyan/40 hover:text-cyan"
          >
            policy check
          </button>
          <div className="flex gap-2">
            <button onClick={onClose} className="rounded border border-line px-3 py-1.5 text-[11.5px] text-muted">
              cancel
            </button>
            <button
              onClick={submit}
              disabled={busy}
              className="rounded border border-mint/40 bg-mint/10 px-4 py-1.5 text-[11.5px] font-medium text-mint disabled:opacity-50"
            >
              {busy ? "booking…" : "book slice"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
