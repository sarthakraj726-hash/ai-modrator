"use client";

import React, { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { StreamGrid } from "@/components/StreamGrid";
import { QuotaCard } from "@/components/QuotaCard";
import { ModerationQueue } from "@/components/ModerationQueue";
import { IncidentPanel } from "@/components/IncidentPanel";
import { ManualConnectModal } from "@/components/ManualConnectModal";
import { Coins, Zap, Activity, RefreshCw } from "lucide-react";

export default function DashboardPage() {
  const [overview, setOverview] = useState<any>(null);
  const [streams, setStreams] = useState<any[]>([]);
  const [quota, setQuota] = useState<any>(null);
  const [keys, setKeys] = useState<any[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);
  const [incidents, setIncidents] = useState<any[]>([]);
  const [isConnectOpen, setIsConnectOpen] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string>("");
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Headers with admin authorization
  const getAuthHeaders = () => {
    return {
      "Content-Type": "application/json",
      "X-Admin-Secret": "change-this-to-a-secure-random-secret-in-production",
    };
  };

  const fetchDashboardData = async () => {
    setIsRefreshing(true);
    try {
      const headers = getAuthHeaders();

      // Fetch Overview
      const ovRes = await fetch("/api/v1/dashboard/overview", { headers });
      if (ovRes.ok) setOverview(await ovRes.json());

      // Fetch Streams
      const stRes = await fetch("/api/v1/dashboard/streams", { headers });
      if (stRes.ok) setStreams(await stRes.json());

      // Fetch Quota
      const qRes = await fetch("/api/v1/dashboard/quota", { headers });
      if (qRes.ok) setQuota(await qRes.json());

      // Fetch Keys
      const kRes = await fetch("/api/v1/dashboard/youtube-keys", { headers });
      if (kRes.ok) setKeys(await kRes.json());

      // Fetch Moderation Queue
      const mRes = await fetch("/api/v1/dashboard/moderation?status_filter=PENDING", { headers });
      if (mRes.ok) setReviews(await mRes.json());

      // Fetch Incidents
      const iRes = await fetch("/api/v1/dashboard/incidents", { headers });
      if (iRes.ok) setIncidents(await iRes.json());

      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (e) {
      console.error("Dashboard fetch error:", e);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 10000); // 10s fallback poll
    return () => clearInterval(interval);
  }, []);

  // Stream Control Action
  const handleStreamControl = async (streamId: string, action: string) => {
    try {
      const res = await fetch(`/api/v1/dashboard/streams/${streamId}/control`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        await fetchDashboardData();
      }
    } catch (e) {
      console.error("Control action error:", e);
    }
  };

  // Manual Connect
  const handleManualConnect = async (urlOrId: string) => {
    const res = await fetch("/api/v1/dashboard/streams/manual-connect", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ url_or_video_id: urlOrId }),
    });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData?.detail || "Connection failed");
    }
    await fetchDashboardData();
  };

  // Reset Key Cooldown
  const handleResetKey = async (index: number) => {
    await fetch(`/api/v1/dashboard/youtube-keys/${index}/reset`, {
      method: "POST",
      headers: getAuthHeaders(),
    });
    await fetchDashboardData();
  };

  // Resolve Review
  const handleResolveReview = async (reviewId: string, action: string) => {
    await fetch(`/api/v1/dashboard/moderation/reviews/${reviewId}/resolve`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ action }),
    });
    await fetchDashboardData();
  };

  // Resolve Incident
  const handleResolveIncident = async (incidentId: string) => {
    await fetch(`/api/v1/dashboard/incidents/${incidentId}/resolve`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ status: "RESOLVED", resolution: "Resolved via Control Center" }),
    });
    await fetchDashboardData();
  };

  return (
    <div className="min-h-screen bg-[#08090f] text-slate-200">
      <Header overview={overview} onOpenConnect={() => setIsConnectOpen(true)} />

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Top Operational Metrics Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="cyber-panel p-4 flex items-center justify-between">
            <div>
              <p className="text-[11px] font-mono text-slate-400 uppercase">Active Streams</p>
              <p className="text-xl font-bold font-mono text-slate-100">
                {overview?.active_streams || 0} <span className="text-xs text-slate-500 font-normal">/ 7 max</span>
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
                {overview?.quota?.quota_remaining || 4000} <span className="text-xs text-slate-500 font-normal">pts</span>
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
                {overview?.pending_moderation_reviews || 0}
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
                {overview?.ledger_balanced ? "BALANCED" : "AUDIT REQ"}
              </p>
            </div>
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Coins className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Refresh & Status bar */}
        <div className="flex items-center justify-between text-xs text-slate-500 font-mono">
          <span>Target Architecture: Railway Production • 6–7 Streams Concurrent</span>
          <button
            onClick={fetchDashboardData}
            className="flex items-center gap-1.5 hover:text-slate-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
            <span>Updated: {lastRefreshed || "Just now"}</span>
          </button>
        </div>

        {/* Section 1: Live Stream Grid */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 font-mono flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-rose-500"></span>
              Active Live Stream Grid (Up to 7 Concurrent Sessions)
            </h2>
          </div>
          <StreamGrid streams={streams} onControlAction={handleStreamControl} />
        </section>

        {/* Section 2: Quota & Incidents 2-Column Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <QuotaCard quota={quota} keys={keys} onResetKey={handleResetKey} />
          <IncidentPanel incidents={incidents} onResolve={handleResolveIncident} />
        </div>

        {/* Section 3: Moderation & HITL Queue */}
        <section className="space-y-3">
          <ModerationQueue reviews={reviews} onResolve={handleResolveReview} />
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
