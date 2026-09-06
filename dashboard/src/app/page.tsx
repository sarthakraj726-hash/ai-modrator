"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";
import { Header, TabId } from "@/components/Header";
import { OverviewView } from "@/components/views/OverviewView";
import { StreamsView } from "@/components/views/StreamsView";
import { ModerationView } from "@/components/views/ModerationView";
import { CohostView } from "@/components/views/CohostView";
import { DeveloperControlCenterView } from "@/components/views/DeveloperControlCenterView";
import { ManualConnectModal } from "@/components/ManualConnectModal";
import {
  fetchAllDashboardData,
  sendManualConnect,
  sendResolveIncident,
  sendResolveReview,
  sendStreamControlAction,
  type DashboardFetchResult,
} from "@/lib/api";

type ConnectionState = "connecting" | "live" | "delayed" | "offline";

interface ToastState {
  id: number;
  message: string;
  type: "success" | "error" | "info";
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardFetchResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [activeTab, setActiveTab] = useState<TabId>("overview");
  const [connectOpen, setConnectOpen] = useState<boolean>(false);
  const [toast, setToast] = useState<ToastState | null>(null);

  const refreshRef = useRef<() => Promise<void>>(async () => undefined);
  const connectionRef = useRef<ConnectionState>("connecting");
  const toastTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback(
    (message: string, type: "success" | "error" | "info" = "info") => {
      if (toastTimeoutRef.current) {
        clearTimeout(toastTimeoutRef.current);
      }
      setToast({ id: Date.now(), message, type });
      toastTimeoutRef.current = setTimeout(() => {
        setToast(null);
      }, 4000);
    },
    []
  );

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const result = await fetchAllDashboardData(AbortSignal.timeout(8_000));
      setData(result);
    } catch {
      showToast("Could not reach backend services", "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showToast]);

  refreshRef.current = refresh;

  // Initial load
  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Real-time Server-Sent Events (SSE) listener
  useEffect(() => {
    let source: EventSource | undefined;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let stopped = false;

    const setRealtimeState = (state: ConnectionState) => {
      connectionRef.current = state;
      setConnection(state);
    };

    const openStream = () => {
      if (stopped) return;
      setRealtimeState(attempt > 0 ? "delayed" : "connecting");

      try {
        source = new EventSource("/api/v1/dashboard/events/stream");

        source.onopen = () => {
          attempt = 0;
          setRealtimeState("live");
        };

        source.onmessage = () => {
          void refreshRef.current();
        };

        source.addEventListener("connected", () => {
          setRealtimeState("live");
        });

        source.onerror = () => {
          source?.close();
          setRealtimeState("delayed");
          const delay = Math.min(30_000, 1_000 * Math.pow(2, attempt++));
          retryTimer = setTimeout(openStream, delay);
        };
      } catch {
        setRealtimeState("offline");
      }
    };

    openStream();

    // Safety fallback interval (every 60 seconds if stream is not live)
    const fallbackInterval = setInterval(() => {
      if (connectionRef.current !== "live") {
        void refreshRef.current();
      }
    }, 60_000);

    return () => {
      stopped = true;
      source?.close();
      if (retryTimer) clearTimeout(retryTimer);
      clearInterval(fallbackInterval);
    };
  }, []);

  // Action Handlers
  const handleControlAction = async (streamId: string, action: string) => {
    try {
      const ok = await sendStreamControlAction(streamId, action);
      if (ok) {
        showToast(`Action '${action}' dispatched to stream ${streamId.slice(0, 8)}`, "success");
        await refresh();
      } else {
        showToast(`Action '${action}' failed for stream`, "error");
      }
    } catch {
      showToast(`Error dispatching '${action}'`, "error");
    }
  };

  const handleResolveReview = async (reviewId: string, action: string) => {
    try {
      const ok = await sendResolveReview(reviewId, action);
      if (ok) {
        showToast(`Moderation review resolved with action: ${action}`, "success");
        await refresh();
      } else {
        showToast("Failed to resolve moderation item", "error");
      }
    } catch {
      showToast("Error updating moderation queue", "error");
    }
  };

  const handleResolveIncident = async (incidentId: string) => {
    try {
      const ok = await sendResolveIncident(incidentId);
      if (ok) {
        showToast(`Incident ${incidentId} resolved`, "success");
        await refresh();
      } else {
        showToast(`Failed to resolve incident ${incidentId}`, "error");
      }
    } catch {
      showToast(`Error resolving incident ${incidentId}`, "error");
    }
  };

  const handleManualConnect = async (urlOrId: string) => {
    try {
      const res = await sendManualConnect(urlOrId);
      showToast(`Connected to stream session: ${res.stream_session_id.slice(0, 8)}...`, "success");
      setConnectOpen(false);
      await refresh();
      setActiveTab("streams");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to connect broadcast";
      showToast(msg, "error");
      throw err;
    }
  };

  const pendingReviews =
    data?.reviews.filter((r) => (r.status || "PENDING").toUpperCase() === "PENDING").length || 0;
  const activeStreamsCount =
    data?.streams.filter((s) => s.status?.toUpperCase() === "LIVE").length ||
    data?.streams.length ||
    0;
  const openIncidentsCount =
    data?.incidents.filter((i) => i.status !== "RESOLVED").length || 0;
  const staleWorkersCount = data?.workers?.stale_workers || 0;

  return (
    <div className="min-h-screen bg-[#0c0d12] text-slate-100 flex flex-col selection:bg-violet-500/30">
      {/* Top Application Bar & Tab Navigation */}
      <Header
        overview={data?.overview ?? null}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        pendingReviewsCount={pendingReviews}
        activeStreamsCount={activeStreamsCount}
        incidentsCount={openIncidentsCount}
        staleWorkersCount={staleWorkersCount}
        onOpenConnect={() => setConnectOpen(true)}
        onRefresh={refresh}
        isRefreshing={refreshing}
        connectionState={connection}
      />

      {/* Main View Area */}
      <main className="mx-auto max-w-7xl flex-1 w-full px-4 py-6 sm:px-6 sm:py-8">
        {activeTab === "overview" && (
          <OverviewView
            data={data}
            isLoading={loading}
            onRestartStream={(id) => void handleControlAction(id, "restart")}
            onResolveIncident={handleResolveIncident}
            onSwitchTab={(tab) => setActiveTab(tab as TabId)}
          />
        )}

        {activeTab === "streams" && (
          <StreamsView
            streams={data?.streams ?? []}
            isLoading={loading}
            onControlAction={handleControlAction}
            onOpenConnect={() => setConnectOpen(true)}
          />
        )}

        {activeTab === "moderation" && (
          <ModerationView
            reviews={data?.reviews ?? []}
            isLoading={loading}
            onResolve={handleResolveReview}
          />
        )}

        {activeTab === "cohost" && (
          <CohostView
            data={data?.cohost ?? null}
            onRefresh={refresh}
            showToast={showToast}
          />
        )}

        {activeTab === "developer" && (
          <DeveloperControlCenterView
            workersData={data?.workers ?? null}
            keys={data?.keys ?? []}
            incidents={data?.incidents ?? []}
            diagnostics={data?.diagnostics ?? {}}
            onRefresh={refresh}
            showToast={showToast}
          />
        )}
      </main>

      {/* Manual Broadcast Connection Modal */}
      <ManualConnectModal
        isOpen={connectOpen}
        onClose={() => setConnectOpen(false)}
        onConnect={handleManualConnect}
      />

      {/* Floating System Notification Toast */}
      {toast && (
        <aside
          aria-live="polite"
          aria-atomic="true"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl border p-4 shadow-2xl backdrop-blur-xl transition-all duration-300 animate-in fade-in slide-in-from-bottom-5 border-slate-700/80 bg-slate-900/95"
        >
          {toast.type === "success" && (
            <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
          )}
          {toast.type === "error" && (
            <AlertCircle className="h-5 w-5 text-rose-400 shrink-0" />
          )}
          {toast.type === "info" && (
            <Info className="h-5 w-5 text-cyan-400 shrink-0" />
          )}

          <p className="text-xs font-medium text-slate-200 pr-2">
            {toast.message}
          </p>

          <button
            type="button"
            onClick={() => setToast(null)}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </aside>
      )}
    </div>
  );
}
