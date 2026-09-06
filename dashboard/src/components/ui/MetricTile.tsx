"use client";

import React, { ReactNode } from "react";

interface MetricTileProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon: ReactNode;
  accent?: "default" | "emerald" | "amber" | "rose" | "cyan" | "purple";
  badge?: string;
}

export const MetricTile: React.FC<MetricTileProps> = ({
  label,
  value,
  subtext,
  icon,
  accent = "default",
  badge,
}) => {
  let accentBorder = "border-white/[0.08] hover:border-white/[0.16]";
  let iconBg = "bg-white/[0.05] text-slate-300";

  switch (accent) {
    case "emerald":
      accentBorder = "border-emerald-500/20 hover:border-emerald-500/40";
      iconBg = "bg-emerald-500/10 text-emerald-400";
      break;
    case "amber":
      accentBorder = "border-amber-500/20 hover:border-amber-500/40";
      iconBg = "bg-amber-500/10 text-amber-400";
      break;
    case "rose":
      accentBorder = "border-rose-500/20 hover:border-rose-500/40";
      iconBg = "bg-rose-500/10 text-rose-400";
      break;
    case "cyan":
      accentBorder = "border-cyan-500/20 hover:border-cyan-500/40";
      iconBg = "bg-cyan-500/10 text-cyan-400";
      break;
    case "purple":
      accentBorder = "border-purple-500/20 hover:border-purple-500/40";
      iconBg = "bg-purple-500/10 text-purple-400";
      break;
  }

  return (
    <div
      className={`rounded-xl bg-[#11131c] border p-4 transition-all duration-200 ${accentBorder}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 font-mono">
            {label}
          </p>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold tracking-tight text-white font-mono">
              {value}
            </span>
            {badge && (
              <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-white/[0.06] text-slate-300 border border-white/10">
                {badge}
              </span>
            )}
          </div>
          {subtext && <p className="text-xs text-slate-400">{subtext}</p>}
        </div>
        <div className={`rounded-lg p-2.5 shrink-0 ${iconBg}`}>{icon}</div>
      </div>
    </div>
  );
};
