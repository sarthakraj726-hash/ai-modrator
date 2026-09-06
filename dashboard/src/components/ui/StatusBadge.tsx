"use client";

import React from "react";

interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md";
  pulse?: boolean;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = "md",
  pulse = false,
}) => {
  const clean = (status || "").toUpperCase();

  let colorClasses = "bg-slate-800/80 text-slate-300 border-slate-700/60";
  let dotColor = "bg-slate-400";
  let shouldPulse = pulse;

  switch (clean) {
    case "LIVE":
    case "RUNNING":
    case "ACTIVE":
    case "HEALTHY":
    case "AVAILABLE":
    case "READY":
    case "BALANCED":
      colorClasses = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      dotColor = "bg-emerald-400";
      if (clean === "LIVE" || clean === "RUNNING") shouldPulse = true;
      break;

    case "CONNECTING":
    case "RECONNECTING":
    case "STARTING":
    case "INVESTIGATING":
    case "WARNING":
    case "DEGRADED":
      colorClasses = "bg-amber-500/10 text-amber-400 border-amber-500/30";
      dotColor = "bg-amber-400";
      shouldPulse = true;
      break;

    case "ERROR":
    case "FAILED":
    case "CRITICAL":
    case "EXHAUSTED":
    case "IMBALANCED":
      colorClasses = "bg-rose-500/15 text-rose-300 border-rose-500/40";
      dotColor = "bg-rose-400";
      shouldPulse = true;
      break;

    case "COOLDOWN":
      colorClasses = "bg-purple-500/15 text-purple-300 border-purple-500/30";
      dotColor = "bg-purple-400";
      break;

    case "PENDING":
      colorClasses = "bg-cyan-500/10 text-cyan-300 border-cyan-500/30";
      dotColor = "bg-cyan-400";
      break;

    case "ENDED":
    case "STOPPED":
    case "CLOSED":
    case "RESOLVED":
      colorClasses = "bg-slate-800/60 text-slate-400 border-slate-700/50";
      dotColor = "bg-slate-500";
      shouldPulse = false;
      break;
  }

  const paddingClass = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md font-mono font-medium border ${paddingClass} ${colorClasses}`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${dotColor} ${
          shouldPulse ? "animate-pulse" : ""
        }`}
      />
      {clean}
    </span>
  );
};
