/** Shared dark-UI primitives. */

const TONES = {
  mint: "bg-mint/10 text-mint border-mint/30",
  cyan: "bg-cyan/10 text-cyan border-cyan/30",
  amber: "bg-amber/10 text-amber border-amber/30",
  rose: "bg-rose/10 text-rose border-rose/30",
  muted: "bg-white/5 text-muted border-line",
};

export function Pill({ tone = "muted", children, className = "" }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10.5px] font-medium tracking-wide ${TONES[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

const DOT_TONES = {
  mint: "bg-mint shadow-[0_0_6px_rgba(61,220,151,0.8)]",
  cyan: "bg-cyan",
  amber: "bg-amber",
  rose: "bg-rose",
  muted: "bg-slate-600",
};

export function Dot({ tone = "mint" }) {
  return <span className={`inline-block h-1.5 w-1.5 rounded-full ${DOT_TONES[tone]}`} />;
}

export function Card({ title, right, children, className = "", bodyClass = "p-4" }) {
  return (
    <section
      className={`flex min-h-0 flex-col rounded-xl border border-line bg-panel/80 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] ${className}`}
    >
      <header className="flex shrink-0 items-center justify-between border-b border-line px-4 py-2.5">
        <h2 className="text-[11.5px] font-semibold uppercase tracking-[0.14em] text-muted">
          {title}
        </h2>
        {right}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClass}`}>{children}</div>
    </section>
  );
}

export function TierBadge({ tier }) {
  const map = {
    confidential: { tone: "mint", label: "CC · hardware" },
    vgpu: { tone: "cyan", label: "vGPU · software" },
    plain: { tone: "muted", label: "plain" },
  };
  const t = map[tier] || map.plain;
  return (
    <Pill tone={t.tone}>
      <span className="text-[9px] leading-none">{tier === "confidential" ? "🛡" : tier === "vgpu" ? "◈" : "⊘"}</span>
      {t.label}
    </Pill>
  );
}

export function Bar({ value, max = 100, tone = "mint", className = "" }) {
  const pct = Math.max(0, Math.min(100, (value / Math.max(max, 1)) * 100));
  const colors = { mint: "bg-mint", cyan: "bg-cyan", amber: "bg-amber", rose: "bg-rose" };
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-line/70 ${className}`}>
      <div className={`h-full rounded-full ${colors[tone]} transition-all duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}
