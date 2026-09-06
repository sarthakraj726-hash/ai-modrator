"use client";

import React from "react";
import {
  Radio,
  Plus,
  RefreshCw,
  LayoutDashboard,
  ShieldCheck,
  Sparkles,
  Cpu,
  AlertTriangle,
} from "lucide-react";
import type { OverviewData } from "@/lib/api";

export type TabId = "overview" | "streams" | "moderation" | "cohost" | "developer";

interface HeaderProps {
  overview: OverviewData | null;
  activeTab: TabId;
  onSelectTab: (tab: TabId) => void;
  pendingReviewsCount: number;
  activeStreamsCount: number;
  incidentsCount: number;
  staleWorkersCount: number;
  onOpenConnect: () => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  connectionState: "connecting" | "live" | "delayed" | "offline";
}

export const Header: React.FC<HeaderProps> = ({
  overview,
  activeTab,
  onSelectTab,
  pendingReviewsCount,
  activeStreamsCount,
  incidentsCount,
  staleWorkersCount,
  onOpenConnect,
  onRefresh,
  isRefreshing,
  connectionState,
}) => {
  const status = overview?.overall_status?.toUpperCase() ?? "NOMINAL";
  const isHealthy = status === "HEALTHY" || status === "NOMINAL";

  const tabs: { id: TabId; label: string; icon: React.FC<{ className?: string }>; badge?: number; hasAlert?: boolean }[] = [
    {
      id: "overview",
      label: "Command Center",
      icon: LayoutDashboard,
    },
    {
      id: "streams",
      label: "Live Broadcasts",
      icon: Radio,
      badge: activeStreamsCount,
    },
    {
      id: "moderation",
      label: "Moderation Queue",
      icon: ShieldCheck,
      badge: pendingReviewsCount > 0 ? pendingReviewsCount : undefined,
    },
    {
      id: "cohost",
      label: "Honney AI Co-Host",
      icon: Sparkles,
    },
    {
      id: "developer",
      label: "Developer Ops",
      icon: Cpu,
      badge: incidentsCount > 0 ? incidentsCount : undefined,
      hasAlert: staleWorkersCount > 0,
    },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0c0d12]/90 backdrop-blur-xl">
      {/* Top Header Bar */}
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        {/* Brand & System Status */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-violet-600 to-fuchsia-600 text-white shadow-lg shadow-violet-600/20">
            <Radio className="h-5 w-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-white font-mono">
                GODDESS AI
              </h1>
              <span className="hidden sm:inline-block rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-violet-300">
                v2.4 Prod
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              Live Operations & Co-Host Control Center
            </p>
          </div>
        </div>

        {/* Live SSE state & Global Actions */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          {/* Live SSE Stream Status */}
          <div
            className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-slate-300"
            title={`Realtime Stream: ${connectionState}`}
          >
            <span
              className={`status-dot ${
                connectionState === "offline"
                  ? "status-dot--danger"
                  : connectionState === "delayed"
                  ? "status-dot--warning"
                  : ""
              }`}
            />
            <span className="hidden md:inline font-mono">
              {connectionState === "live"
                ? "SSE Active"
                : connectionState === "delayed"
                ? "Reconnecting"
                : "Polling Safe"}
            </span>
          </div>

          {/* System Health Pill */}
          <div
            className="hidden lg:flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs text-slate-300"
          >
            <span className={`status-dot ${isHealthy ? "" : "status-dot--warning"}`} />
            <span className="font-mono">{status.replace(/_/g, " ")}</span>
          </div>

          {/* Refresh Action */}
          <button
            type="button"
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.05] p-2 text-slate-300 transition-colors hover:bg-white/[0.1] hover:text-white disabled:opacity-50"
            title="Refresh All Dashboard Metrics"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
          </button>

          {/* Connect Stream Action */}
          <button
            type="button"
            onClick={onOpenConnect}
            className="inline-flex items-center gap-1.5 rounded-xl bg-violet-500 px-3.5 py-2 text-xs sm:text-sm font-semibold text-white shadow-lg shadow-violet-500/25 transition-all hover:bg-violet-400 active:scale-[0.98]"
          >
            <Plus className="h-4 w-4" />
            <span>Connect Broadcast</span>
          </button>
        </div>
      </div>

      {/* Navigation Tab Bar */}
      <div className="border-t border-white/[0.06] bg-[#11131c]/60 px-4 sm:px-6">
        <div className="mx-auto flex max-w-7xl items-center gap-1 overflow-x-auto py-1 scrollbar-none">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onSelectTab(tab.id)}
                className={`relative flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-2 text-xs font-semibold transition-all ${
                  isActive
                    ? "bg-white/[0.08] text-white shadow-sm shadow-black/40"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-violet-400" : "text-slate-500"}`} />
                <span>{tab.label}</span>

                {typeof tab.badge === "number" && tab.badge > 0 && (
                  <span
                    className={`rounded-full px-1.5 py-0.2 text-[10px] font-mono font-bold ${
                      tab.id === "moderation"
                        ? "bg-amber-500/20 text-amber-300"
                        : tab.id === "developer"
                        ? "bg-rose-500/20 text-rose-300"
                        : "bg-violet-500/20 text-violet-300"
                    }`}
                  >
                    {tab.badge}
                  </span>
                )}

                {tab.hasAlert && (
                  <AlertTriangle className="h-3.5 w-3.5 text-amber-400 animate-pulse" />
                )}

                {isActive && (
                  <div className="absolute inset-x-2 -bottom-1 h-0.5 rounded-full bg-violet-400" />
                )}
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
};
