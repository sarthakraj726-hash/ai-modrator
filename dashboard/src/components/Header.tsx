"use client";

import React from "react";
import { Activity, ShieldAlert, Cpu, Server, Database, Radio, Sparkles } from "lucide-react";

interface HeaderProps {
  overview: any;
  onOpenConnect: () => void;
}

export const Header: React.FC<HeaderProps> = ({ overview, onOpenConnect }) => {
  const subsystems = overview?.subsystems || {};

  const getBadgeColor = (status?: string) => {
    switch (status) {
      case "HEALTHY":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "DEGRADED":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "CRITICAL":
      case "UNHEALTHY":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      default:
        return "bg-slate-800 text-slate-400 border-slate-700";
    }
  };

  return (
    <header className="border-b border-surface-border bg-surface/80 backdrop-blur-md sticky top-0 z-40 px-6 py-4">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        {/* Brand & Subtitle */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-purple-600 to-cyan-500 flex items-center justify-center shadow-glow-purple">
            <Radio className="w-5 h-5 text-white animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-purple-400 via-cyan-300 to-emerald-400 bg-clip-text text-transparent">
                GODDESS AI
              </h1>
              <span className="text-xs px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40 font-mono">
                CONTROL CENTER
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Honney AI Co-Host • 7-Stream Multi-Channel Operations Engine
            </p>
          </div>
        </div>

        {/* Subsystem Health Pills */}
        <div className="flex flex-wrap items-center gap-2">
          <div className={`px-2.5 py-1 rounded-md text-xs font-mono border flex items-center gap-1.5 ${getBadgeColor(subsystems?.database?.status)}`}>
            <Database className="w-3.5 h-3.5" />
            <span>DB</span>
          </div>
          <div className={`px-2.5 py-1 rounded-md text-xs font-mono border flex items-center gap-1.5 ${getBadgeColor(subsystems?.redis?.status)}`}>
            <Server className="w-3.5 h-3.5" />
            <span>REDIS</span>
          </div>
          <div className={`px-2.5 py-1 rounded-md text-xs font-mono border flex items-center gap-1.5 ${getBadgeColor(subsystems?.youtube?.status)}`}>
            <Activity className="w-3.5 h-3.5" />
            <span>YOUTUBE</span>
          </div>
          <div className={`px-2.5 py-1 rounded-md text-xs font-mono border flex items-center gap-1.5 ${getBadgeColor(subsystems?.workers?.status)}`}>
            <Cpu className="w-3.5 h-3.5" />
            <span>WORKERS</span>
          </div>
          <div className="px-2.5 py-1 rounded-md text-xs font-mono border border-purple-500/30 bg-purple-500/10 text-purple-300 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>HONNEY AI</span>
          </div>

          <button
            onClick={onOpenConnect}
            className="ml-2 px-3 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-glow-purple transition-all active:scale-95 flex items-center gap-1.5"
          >
            <span>+ CONNECT STREAM</span>
          </button>
        </div>
      </div>
    </header>
  );
};
