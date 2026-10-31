import { useEffect, useRef, useState } from "react";

export async function getJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json();
}

/** Poll an endpoint on an interval; keeps the last good value on error. */
export function usePoll(fn, ms) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    let alive = true;
    const run = async () => {
      try {
        const d = await fnRef.current();
        if (alive) {
          setData(d);
          setError(null);
        }
      } catch (e) {
        if (alive) setError(e.message);
      }
    };
    run();
    const id = setInterval(run, ms);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [ms]);

  return { data, error };
}

/** Subscribe to the broker's SSE firehose. */
export function useSSE(onEvent) {
  const [connected, setConnected] = useState(false);
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    const es = new EventSource("/events");
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        cb.current(JSON.parse(e.data));
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => es.close();
  }, []);

  return connected;
}

export const fmtMoney = (v, digits = 4) =>
  v == null ? "—" : `$${Number(v).toFixed(digits)}`;

export const fmtDuration = (s) => {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
};

export const fmtTime = (iso) => {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  return d.toLocaleTimeString([], { hour12: false });
};

/* ---- presentation helpers ------------------------------------------- */

export const TIER_STYLE = {
  confidential: { label: "CC", cls: "border-mint/40 bg-mint/10 text-mint" },
  vgpu: { label: "vGPU", cls: "border-cyan/40 bg-cyan/10 text-cyan" },
  plain: { label: "plain", cls: "border-line bg-white/5 text-muted" },
};

export const STATUS_STYLE = {
  running: "border-mint/40 bg-mint/10 text-mint",
  provisioning: "border-cyan/40 bg-cyan/10 text-cyan",
  scheduled: "border-cyan/30 bg-cyan/5 text-cyan/80",
  queued: "border-amber/40 bg-amber/10 text-amber",
  completed: "border-line bg-white/5 text-muted",
  failed: "border-rose/40 bg-rose/10 text-rose",
};

export const money = (v, digits = 2) =>
  v == null ? "—" : `$${Number(v).toFixed(digits)}`;

export const pct = (v) => `${Number(v ?? 0).toFixed(1)}%`;

export const clock = (seconds) => {
  if (seconds == null) return "—";
  const s = Math.max(0, Math.round(seconds));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
};
