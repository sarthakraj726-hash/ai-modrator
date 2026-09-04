"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { StreamGrid } from "@/components/StreamGrid";
import { QuotaCard } from "@/components/QuotaCard";
import { ModerationQueue } from "@/components/ModerationQueue";
import { IncidentPanel } from "@/components/IncidentPanel";
import { ManualConnectModal } from "@/components/ManualConnectModal";
import {
  fetchAllDashboardData,
  sendStreamControlAction,
  sendManualConnect,
  sendResetKeyCooldown,
  sendResolveReview,
  sendResolveIncident,
  OverviewData,
  StreamItem,
  QuotaData,
  KeyItem,
  ReviewItem,
  IncidentItem,
  EndpointDiagnostic,
} from "@/lib/api";
import { Coins, Zap, Activity, RefreshCw, AlertTriangle, CheckCircle } from "lucide-react";

export default function DashboardPage() {
  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [streams, setStreams] = useState<StreamItem[]>([]);
  const [quota, setQuota] = useState<QuotaData | null>(null);
  const [keys, setKeys] = useState<KeyItem[]>([]);
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [diagnostics, setDiagnostics] = useState<Record<string, EndpointDiagnostic>>({});
  const [isConnectOpen, setIsConnectOpen] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string>("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);

  const fetchDashboardData = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const signal = AbortSignal.timeout(8000);
      const result = await fetchAllDashboardData(signal);

      if (result.overview) setOverview(result.overview);
      setStreams(result.streams);
      if (result.quota) setQuota(result.quota);
      setKeys(result.keys);
      setReviews(result.reviews);
      setIncidents(result.incidents);
      setDiagnostics(result.diagnostics);

      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    } finally {
      setIsRefreshing(false);
      setInitialLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 10000); // 10s fallback poll
    return () => clearInterval(interval);
  }, [fetchDashboardData]);

  // Stream Control Action
  const handleStreamControl = async (streamId: string, action: string) => {
    try {
      const ok = await sendStreamControlAction(streamId, action);
      if (ok) await fetchDashboardData();
    } catch (e) {
      console.error("Control action error:", e);
    }
  };

  // Manual Connect
  const handleManualConnect = async (urlOrId: string) => {
    await sendManualConnect(urlOrId);
    await fetchDashboardData();
  };

  // Reset Key Cooldown
  const handleResetKey = async (index: number) => {
    try {
      const ok = await sendResetKeyCooldown(index);
      if (ok) await fetchDashboardData();
    } catch (e) {
      console.error("Reset key error:", e);
    }
  };

  // Resolve Review
  const handleResolveReview = async (reviewId: string, action: string) => {
    try {
      const ok = await sendResolveReview(reviewId, action);
      if (ok) await fetchDashboardData();
    } catch (e) {
      console.error("Resolve review error:", e);
    }
  };

  // Resolve Incident
  const handleResolveIncident = async (incidentId: string) => {
    try {
      const ok = await sendResolveIncident(incidentId);
      if (ok) await fetchDashboardData();
    } catch (e) {
      console.error("Resolve incident error:", e);
    }
  };

  // Health / Error overview badges
  const hasAuthError = Object.values(diagnostics).some((d) => d.state === "unauthorized");
  const hasConnectionError = Object.values(diagnostics).some((d) => d.state === "error");

  return (
    <div className="min-h-screen bg-[#08090f] text-slate-200">
      <Header overview={overview} onOpenConnect={() => setIsConnectOpen(true)} />

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Production Diagnostics Banner when API errors exist */}
        {hasAuthError && (
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center justify-between text-xs font-mono text-rose-300">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-400" />
              <span>Authentication Error: Server-side ADMIN_SECRET rejected by backend (HTTP 401/403).</span>
            </div>
            <span className="text-[11px] text-rose-400/80">Check Railway ADMIN_SECRET</span>
          </div>
        )}

        {hasConnectionError && !hasAuthError && (
          <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-between text-xs font-mono text-amber-300">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span>Backend Connectivity Alert: One or more dashboard APIs unreachable (HTTP 502/503/504).</span>
            </div>
            <span className="text-[11px] text-amber-400/80">Check BACKEND_API_URL</span>
          </div>
        )}

        {/* Top Operational Metrics Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="cyber-panel p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-mono text-slate-400 uppercase">Active Streams</p>
              <p className="text-xl font-bold font-mono text-slate-100">
                {initialLoading ? (
                  <span className="text-sm text-slate-500 animate-pulse">LOADING...</span>
                ) : diagnostics.overview?.state === "error" || diagnostics.overview?.state === "unauthorized" ? (
                  <span className="text-xs text-rose-400">UNAVAILABLE</span>
                ) : (
                  <>
                    {overview?.active_streams ?? streams.length}{" "}
                    <span className="text-xs text-slate-500 font-normal">/ 7 max</span>
                  </>
                )}
              </p>
            </div>
            <div className="p-2.5 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <Activity className="w-5 h-5" />
            </div>
          </div>

          <div className="cyber-panel p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-mono text-slate-400 uppercase">Quota Remaining</p>
              <p className="text-xl font-bold font-mono text-cyan-400">
                {initialLoading ? (
                  <span className="text-sm text-slate-500 animate-pulse">LOADING...</span>
                ) : diagnostics.quota?.state === "error" || diagnostics.quota?.state === "unauthorized" ? (
                  <span className="text-xs text-rose-400">UNAVAILABLE</span>
                ) : (
                  <>
                    {quota?.remaining ?? overview?.quota?.remaining ?? overview?.quota?.quota_remaining ?? "N/A"}{" "}
                    <span className="text-xs text-slate-500 font-normal">pts</span>
                  </>
                )}
              </p>
            </div>
            <div className="p-2.5 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">
              <Zap className="w-5 h-5" />
            </div>
          </div>

          <div className="cyber-panel p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-mono text-slate-400 uppercase">HITL Pending</p>
              <p className="text-xl font-bold font-mono text-purple-400">
                {initialLoading ? (
                  <span className="text-sm text-slate-500 animate-pulse">LOADING...</span>
                ) : diagnostics.moderation?.state === "error" || diagnostics.moderation?.state === "unauthorized" ? (
                  <span className="text-xs text-rose-400">UNAVAILABLE</span>
                ) : (
                  overview?.pending_moderation_reviews ?? reviews.length
                )}
              </p>
            </div>
            <div className="p-2.5 rounded-lg bg-purple-500/10 text-purple-400 border border-purple-500/20">
              <span className="text-sm font-bold font-mono">🛡️</span>
            </div>
          </div>

          <div className="cyber-panel p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-mono text-slate-400 uppercase">Ledger Integrity</p>
              <p className="text-xl font-bold font-mono text-emerald-400">
                {initialLoading ? (
                  <span className="text-sm text-slate-500 animate-pulse">LOADING...</span>
                ) : diagnostics.overview?.state === "error" || diagnostics.overview?.state === "unauthorized" ? (
                  <span className="text-xs text-rose-400">UNAVAILABLE</span>
                ) : overview?.ledger_balanced ? (
                  "BALANCED"
                ) : (
                  "AUDIT REQ"
                )}
              </p>
            </div>
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Coins className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Structured Diagnostics Bar */}
        <div className="cyber-panel p-3 flex flex-wrap items-center justify-between gap-3 text-[11px] font-mono">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-500 font-semibold uppercase">API Diagnostics:</span>
            {["overview", "streams", "quota", "keys", "moderation", "incidents"].map((key) => {
              const diag = diagnostics[key];
              const isOk = diag?.state === "success";
              const isAuth = diag?.state === "unauthorized";
              return (
                <span
                  key={key}
                  className={`px-2 py-0.5 rounded border ${
                    isOk
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                      : isAuth
                      ? "bg-rose-500/20 text-rose-300 border-rose-500/40"
                      : "bg-amber-500/15 text-amber-300 border-amber-500/30"
                  }`}
                  title={diag?.error || "Endpoint responding normally"}
                >
                  {key}: {diag?.httpStatus ? `${diag.httpStatus}` : isOk ? "200" : "FAIL"}
                </span>
              );
            })}
          </div>

          <div className="flex items-center gap-3 text-slate-500">
            <span>Target: Railway Production • 6–7 Streams</span>
            <button
              onClick={fetchDashboardData}
              className="flex items-center gap-1.5 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-cyan-400" : ""}`} />
              <span>{lastRefreshed ? `Updated ${lastRefreshed}` : "Refreshing..."}</span>
            </button>
          </div>
        </div>

        {/* Section 1: Live Stream Grid */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 font-mono flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Active Live Stream Grid (Up to 7 Concurrent Sessions)
            </h2>
            {diagnostics.streams?.state === "success" && (
              <span className="text-xs font-mono text-slate-500 flex items-center gap-1">
                <CheckCircle className="w-3 h-3 text-emerald-400" />
                {streams.length} sessions active
              </span>
            )}
          </div>
          <StreamGrid
            streams={streams}
            onControlAction={handleStreamControl}
            isLoading={initialLoading}
            error={diagnostics.streams?.error}
          />
        </section>

        {/* Section 2: Quota & Incidents 2-Column Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <QuotaCard
            quota={quota}
            keys={keys}
            onResetKey={handleResetKey}
            isLoading={initialLoading}
            error={diagnostics.quota?.error}
          />
          <IncidentPanel
            incidents={incidents}
            onResolve={handleResolveIncident}
            isLoading={initialLoading}
            error={diagnostics.incidents?.error}
          />
        </div>

        {/* Section 3: Moderation & HITL Queue */}
        <section className="space-y-3">
          <ModerationQueue
            reviews={reviews}
            onResolve={handleResolveReview}
            isLoading={initialLoading}
            error={diagnostics.moderation?.error}
          />
        </section>
      </main>

      <ManualConnectModal
        isOpen={isConnectOpen}
        onClose={() => setIsConnectOpen(false)}
        onConnect={handleManualConnect}
      />
    </div>
  );
}
