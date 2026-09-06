"use client";

import React from "react";
import { Plus, Radio } from "lucide-react";
import type { OverviewData } from "@/lib/api";

interface HeaderProps {
  overview: OverviewData | null;
  onOpenConnect: () => void;
}

export const Header: React.FC<HeaderProps> = ({ overview, onOpenConnect }) => {
  const status = overview?.overall_status?.toUpperCase() ?? "CONNECTING";
  const isHealthy = status === "HEALTHY";

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0c0d12]/80 px-4 py-3 backdrop-blur-xl sm:px-6">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-400 text-slate-950 shadow-lg shadow-violet-500/20">
            <Radio className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight text-white">Goddess AI</h1>
            <p className="hidden text-xs text-slate-400 sm:block">Broadcast operations</p>
          </div>
        </div>

        <div className="flex items-center gap-2 sm:gap-3">
          <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[.04] px-3 py-2 text-xs text-slate-300 sm:flex" aria-live="polite">
            <span className={`status-dot ${isHealthy ? "" : "status-dot--warning"}`} />
            {status.replaceAll("_", " ")}
          </div>
          <button
            onClick={onOpenConnect}
            className="inline-flex items-center gap-1.5 rounded-xl bg-violet-400 px-3 py-2 text-sm font-semibold text-slate-950 transition-colors hover:bg-violet-300"
          >
            <Plus className="h-4 w-4" /><span className="hidden sm:inline">Connect stream</span><span className="sm:hidden">Connect</span>
          </button>
        </div>
      </div>
    </header>
  );
};
