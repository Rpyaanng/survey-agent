"use client";

/*
 * Hand-built charts for survey analytics.
 *
 * Colors (validated with the dataviz skill's palette validator against the
 * #0e1420 card surface, dark mode):
 *   --viz-series  #3987e5  single-hue magnitude (bars, columns, timeline)
 *   NPS diverging pair: promoters #3987e5 / passives #5c5c58 (neutral) / detractors #e66767
 *   Blue<->red passes CVD (ΔE 19.2) and normal-vision floors; the neutral sits at
 *   2.74:1 contrast, so every NPS segment carries a visible direct label + legend.
 * Mark specs: bars <=24px thick, 4px rounded data-end, square at the baseline;
 * 2px lines; 2px surface gaps between touching segments; hairline grid.
 * Text always wears text tokens, never the series color.
 */
import { useId, useMemo, useState } from "react";
import { cn, formatDate } from "@/lib/utils";

const SERIES = "#3987e5";
const NPS_COLORS = { promoters: "#3987e5", passives: "#5c5c58", detractors: "#e66767" };
const GRID = "rgba(255,255,255,0.07)";

function pct(n: number, total: number) {
  return total ? Math.round((n / total) * 100) : 0;
}

/* Horizontal bars: one per category, value + share at the tip. */
export function BarList({ items, total, className }: { items: { label: string; count: number }[]; total: number; className?: string }) {
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <ul className={cn("space-y-3", className)}>
      {items.map((item) => {
        const width = (item.count / max) * 100;
        return (
          <li
            key={item.label}
            tabIndex={0}
            aria-label={`${item.label}: ${item.count} (${pct(item.count, total)}%)`}
            className="group rounded-md outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/40"
          >
            <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
              <span className="truncate text-ink-muted group-hover:text-ink" title={item.label}>
                {item.label}
              </span>
              <span className="shrink-0 tabular-nums text-ink">
                {item.count.toLocaleString()} <span className="text-ink-faint">· {pct(item.count, total)}%</span>
              </span>
            </div>
            <div className="h-3 rounded-r-[4px] bg-white/[0.04]">
              <div
                className="h-full rounded-r-[4px] transition-[filter] group-hover:brightness-125 group-focus-visible:brightness-125"
                style={{ width: `${Math.max(width, item.count ? 1.5 : 0)}%`, background: SERIES }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/* Vertical columns for ordered scales (rating, NPS 0-10). */
export function ColumnChart({ items, height = 140 }: { items: { label: string; count: number }[]; height?: number }) {
  const max = Math.max(1, ...items.map((i) => i.count));
  const [hover, setHover] = useState<number | null>(null);
  return (
    <div>
      <div className="flex items-end gap-1.5" style={{ height }} onPointerLeave={() => setHover(null)}>
        {items.map((item, i) => {
          const h = (item.count / max) * (height - 22);
          return (
            <div
              key={item.label}
              className="relative flex h-full flex-1 flex-col items-center justify-end"
              onPointerEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
              tabIndex={0}
              aria-label={`${item.label}: ${item.count}`}
            >
              <span className={cn("mb-1 text-xs tabular-nums", hover === i ? "text-ink" : item.count ? "text-ink-muted" : "text-transparent")}>
                {item.count}
              </span>
              <div
                className="w-full max-w-6 rounded-t-[4px] transition-[filter]"
                style={{ height: Math.max(h, item.count ? 3 : 0), background: SERIES, filter: hover === i ? "brightness(1.25)" : undefined }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-1.5 border-t pt-1.5" style={{ borderColor: "rgba(255,255,255,0.12)" }}>
        {items.map((item) => (
          <span key={item.label} className="flex-1 text-center text-xs tabular-nums text-ink-faint">
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/* NPS breakdown: diverging stacked bar, detractors | passives | promoters. */
export function NpsBreakdown({ nps }: { nps: { score: number; promoters: number; passives: number; detractors: number } }) {
  const total = nps.promoters + nps.passives + nps.detractors;
  const segments = [
    { key: "detractors", label: "Detractors (0-6)", count: nps.detractors },
    { key: "passives", label: "Passives (7-8)", count: nps.passives },
    { key: "promoters", label: "Promoters (9-10)", count: nps.promoters },
  ] as const;
  return (
    <div>
      <div className="flex items-baseline gap-3">
        <span className="text-4xl font-semibold text-ink">{nps.score > 0 ? `+${nps.score}` : nps.score}</span>
        <span className="text-sm text-ink-muted">Net Promoter Score · {total.toLocaleString()} ratings</span>
      </div>
      {/* 2px surface gaps separate the touching segments. */}
      <div className="mt-4 flex h-6 gap-[2px] overflow-hidden rounded-[4px]" role="img" aria-label={segments.map((s) => `${s.label}: ${s.count}`).join(", ")}>
        {segments.map((s) =>
          s.count ? (
            <div
              key={s.key}
              className="flex items-center justify-center text-xs font-medium text-white"
              style={{ flexGrow: s.count, flexBasis: 0, background: NPS_COLORS[s.key] }}
              title={`${s.label}: ${s.count} (${pct(s.count, total)}%)`}
            >
              {pct(s.count, total) >= 12 && `${pct(s.count, total)}%`}
            </div>
          ) : null,
        )}
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs">
        {segments.map((s) => (
          <li key={s.key} className="flex items-center gap-1.5 text-ink-muted">
            <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: NPS_COLORS[s.key] }} />
            {s.label}
            <span className="tabular-nums text-ink">
              {s.count.toLocaleString()} ({pct(s.count, total)}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function niceMax(value: number) {
  // Four clean ticks: pick the smallest 1/2/2.5/5 x 10^n step that covers value/4.
  if (value <= 4) return 4;
  const raw = value / 4;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude >= raw)! * magnitude;
  return step * 4;
}

/* Single-series area over time with a snapping crosshair + tooltip. */
export function Timeline({ points, label = "responses" }: { points: { date: string; count: number }[]; label?: string }) {
  const gradientId = useId();
  const [hover, setHover] = useState<number | null>(null);
  const W = 640;
  const H = 180;
  const pad = { top: 12, right: 12, bottom: 24, left: 36 };
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;
  const yMax = niceMax(Math.max(0, ...points.map((p) => p.count)));
  const ticks = [0, yMax / 2, yMax];

  const coords = useMemo(
    () =>
      points.map((p, i) => ({
        x: pad.left + (points.length > 1 ? (i / (points.length - 1)) * innerW : innerW / 2),
        y: pad.top + innerH - (p.count / yMax) * innerH,
      })),
    [points, yMax, innerW, innerH, pad.left, pad.top],
  );
  if (!points.length) return null;

  const line = coords.map((c, i) => `${i ? "L" : "M"}${c.x},${c.y}`).join(" ");
  const area = `${line} L${coords[coords.length - 1].x},${pad.top + innerH} L${coords[0].x},${pad.top + innerH} Z`;

  function onMove(e: React.PointerEvent<SVGRectElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * innerW;
    setHover(Math.max(0, Math.min(points.length - 1, Math.round((x / innerW) * (points.length - 1)))));
  }

  const hovered = hover != null ? { ...points[hover], ...coords[hover] } : null;
  const labelIdx = [0, Math.floor((points.length - 1) / 2), points.length - 1];

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label={`${label} per day over the last ${points.length} days`}>
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={SERIES} stopOpacity="0.18" />
            <stop offset="100%" stopColor={SERIES} stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {ticks.map((t) => {
          const y = pad.top + innerH - (t / yMax) * innerH;
          return (
            <g key={t}>
              <line x1={pad.left} x2={W - pad.right} y1={y} y2={y} stroke={GRID} strokeWidth={1} />
              <text x={pad.left - 8} y={y + 4} textAnchor="end" className="fill-ink-faint text-[11px] tabular-nums">
                {t.toLocaleString()}
              </text>
            </g>
          );
        })}
        {labelIdx.map((i) => (
          <text key={i} x={coords[i].x} y={H - 6} textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"} className="fill-ink-faint text-[11px]">
            {formatDate(points[i].date + "T00:00:00", { month: "short", day: "numeric" })}
          </text>
        ))}
        <path d={area} fill={`url(#${gradientId})`} />
        <path d={line} fill="none" stroke={SERIES} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {hovered && (
          <>
            <line x1={hovered.x} x2={hovered.x} y1={pad.top} y2={pad.top + innerH} stroke="rgba(255,255,255,0.25)" strokeWidth={1} />
            <circle cx={hovered.x} cy={hovered.y} r={4.5} fill={SERIES} stroke="#0e1420" strokeWidth={2} />
          </>
        )}
        <rect
          x={pad.left}
          y={pad.top}
          width={innerW}
          height={innerH}
          fill="transparent"
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
        />
      </svg>
      {hovered && (
        <div
          className="pointer-events-none absolute top-0 -translate-x-1/2 rounded-lg border border-white/10 bg-popover px-3 py-2 text-xs shadow-xl"
          style={{ left: `${(hovered.x / W) * 100}%` }}
        >
          <div className="font-semibold tabular-nums text-ink">
            {hovered.count.toLocaleString()} {label}
          </div>
          <div className="text-ink-faint">{formatDate(hovered.date + "T00:00:00", { weekday: "short", month: "short", day: "numeric" })}</div>
        </div>
      )}
    </div>
  );
}
