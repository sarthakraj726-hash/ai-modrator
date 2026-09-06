"use client";

import React from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  Layers,
  Radio,
  RotateCcw,
  ShieldCheck,
  Tv,
  Zap,
} from "lucide-react";
import { MetricTile } from "../ui/MetricTile";
import { StatusBadge } from "../ui/StatusBadge";
import type { DashboardFetchResult } from "@/lib/api";

interface OverviewViewProps {
  data: DashboardFetchResult | null;
  isLoading: boolean;
  onRestartStream: (streamId: string) => void;
  onResolveIncident: (incidentId: string) => void;
  onSwitchTab: (tab: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  data,
  isLoading,
  onRestartStream,
  onResolveIncident,
  onSwitchTab,
}) => {
  const overview = data?.overview;
  const subsystems = overview?.subsystems || {};
  const activeIncidents =
    data?.incidents.filter(
      (i) => i.status === "OPEN" || i.status === "INVESTIGATING"
    ) || [];

  return (
    <div className="space-y-6">
      {/* Top System Health Banner */}
      <div className="rounded-2xl border border-white/10 bg-[#0f121d] p-5 sm:p-6 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 -mt-8 -mr-8 w-64 h-64 bg-violet-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 relative z-10">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[10px] font-mono uppercase tracking-widest text-slate-400">
                Command Center
              </span>
              <span className="text-slate-600">•</span>
              <span className="text-[10px] font-mono text-slate-400">
                Environment: {overview?.environment || "production"}
              </span>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              Goddess AI Live Operations
            </h2>
            <p className="mt-1 text-sm text-slate-400 max-w-2xl">
              Real-time telemetry, continuous safety supervision, and multi-channel YouTube Live stream management.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <StatusBadge
              status={overview?.overall_status || "HEALTHY"}
              size="md"
              pulse
            />
          </div>
        </div>
      </div>

      {/* Primary KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricTile
          label="Active Streams"
          value={isLoading ? "—" : overview?.active_streams ?? data?.streams.length ?? 0}
          subtext="YouTube channels currently monitored"
          icon={<Activity className="w-5 h-5" />}
          accent="purple"
        />
        <MetricTile
          label="Needs Review"
          value={isLoading ? "—" : overview?.pending_moderation_reviews ?? data?.reviews.length ?? 0}
          subtext="Pending human moderator reviews"
          icon={<ShieldCheck className="w-5 h-5" />}
          accent={
            (overview?.pending_moderation_reviews ?? 0) > 0 ? "amber" : "emerald"
          }
        />
        <MetricTile
          label="Daily Quota Units"
          value={
            isLoading
              ? "—"
              : `${overview?.quota?.remaining ?? data?.quota?.remaining ?? "—"}`
          }
          subtext={`Budget: ${overview?.quota?.budget ?? 4000} units`}
          icon={<Zap className="w-5 h-5" />}
          accent="cyan"
          badge={`${overview?.quota?.percent_used ?? 0}% used`}
        />
        <MetricTile
          label="Ledger Health"
          value={overview?.ledger_balanced !== false ? "100% Balanced" : "Imbalanced"}
          subtext="Double-entry invariant verified"
          icon={<Database className="w-5 h-5" />}
          accent={overview?.ledger_balanced !== false ? "emerald" : "rose"}
        />
      </div>

      {/* Critical Incidents Banner (if any) */}
      {activeIncidents.length > 0 && (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-rose-400" />
              <h3 className="text-sm font-semibold text-rose-200">
                Active Operational Incidents ({activeIncidents.length})
              </h3>
            </div>
            <button
              onClick={() => onSwitchTab("developer")}
              className="text-xs font-mono text-rose-300 hover:text-rose-200 underline"
            >
              View in Control Center &rarr;
            </button>
          </div>
          <div className="space-y-2">
            {activeIncidents.slice(0, 3).map((inc) => (
              <div
                key={inc.incident_id}
                className="rounded-lg bg-black/40 border border-rose-500/20 p-3 flex items-center justify-between gap-4 text-xs font-mono"
              >
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={inc.severity} size="sm" />
                    <span className="font-bold text-slate-200">{inc.incident_id}</span>
                    <span className="text-slate-400">[{inc.service}]</span>
                  </div>
                  <p className="text-slate-300 font-sans text-xs">{inc.summary}</p>
                </div>
                <button
                  onClick={() => onResolveIncident(inc.incident_id)}
                  className="px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold shrink-0 transition-colors"
                >
                  Resolve
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Subsystems Matrix */}
      <div className="rounded-xl border border-white/[0.08] bg-[#11131c] p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-4 h-4 text-violet-400" />
            <h3 className="text-xs font-mono uppercase font-semibold text-slate-200 tracking-wider">
              Subsystem Connectivity Matrix
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            {Object.keys(subsystems).length} services monitored
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {Object.entries(subsystems).map(([name, info]) => {
            const sub = info as { status: string; latency_ms?: number };
            const status = sub?.status || "HEALTHY";
            return (
              <div
                key={name}
                className="rounded-lg bg-white/[0.03] border border-white/[0.06] p-3 space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono capitalize text-slate-300 font-medium">
                    {name}
                  </span>
                  <StatusBadge status={status} size="sm" />
                </div>
                {typeof sub?.latency_ms === "number" && (
                  <p className="text-[11px] font-mono text-slate-400">
                    {sub.latency_ms.toFixed(1)} ms
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Broadcast Quick View */}
      <div className="rounded-xl border border-white/[0.08] bg-[#11131c] p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-rose-400" />
            <h3 className="text-xs font-mono uppercase font-semibold text-slate-200 tracking-wider">
              Active Broadcasts ({data?.streams?.length || 0})
            </h3>
          </div>
          <button
            onClick={() => onSwitchTab("streams")}
            className="text-xs font-mono text-violet-400 hover:text-violet-300"
          >
            Manage Streams &rarr;
          </button>
        </div>

        {!data?.streams || data.streams.length === 0 ? (
          <div className="py-8 text-center text-slate-400 text-xs font-mono space-y-2">
            <Tv className="w-8 h-8 mx-auto text-slate-500 opacity-60" />
            <p>No active live broadcasts connected.</p>
            <p className="text-slate-400">
              Use the Connect Stream button in the header to join a YouTube Live stream.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.streams.slice(0, 6).map((s) => (
              <div
                key={s.session_id}
                className="rounded-lg bg-white/[0.03] border border-white/[0.06] p-4 space-y-3 hover:border-white/[0.12] transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm font-semibold text-white truncate">
                    {s.channel_name}
                  </span>
                  <StatusBadge status={s.status} size="sm" pulse />
                </div>

                <div className="space-y-1 text-xs font-mono text-slate-400">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Messages:</span>
                    <span className="text-slate-200">{s.messages_processed ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Worker:</span>
                    <span
                      className={
                        s.is_worker_alive ? "text-emerald-400" : "text-amber-400"
                      }
                    >
                      {s.is_worker_alive ? "Active" : "Awaiting worker"}
                    </span>
                  </div>
                </div>

                <div className="pt-2 border-t border-white/[0.06] flex items-center justify-end">
                  <button
                    onClick={() => onRestartStream(s.session_id)}
                    className="inline-flex items-center gap-1 text-xs font-mono text-slate-400 hover:text-slate-200 transition-colors"
                  >
                    <RotateCcw className="w-3 h-3" />
                    Restart
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
