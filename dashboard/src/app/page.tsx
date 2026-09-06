"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { Activity, AlertTriangle, CheckCircle2, RefreshCw, ShieldCheck, Zap } from "lucide-react";
import { Header } from "@/components/Header";
import { StreamGrid } from "@/components/StreamGrid";
import { QuotaCard } from "@/components/QuotaCard";
import { ModerationQueue } from "@/components/ModerationQueue";
import { IncidentPanel } from "@/components/IncidentPanel";
import { ManualConnectModal } from "@/components/ManualConnectModal";
import { fetchAllDashboardData, sendManualConnect, sendResetKeyCooldown, sendResolveIncident, sendResolveReview, sendStreamControlAction } from "@/lib/api";
import type { DashboardFetchResult, EndpointDiagnostic } from "@/lib/api";

type ConnectionState = "connecting" | "live" | "delayed" | "offline";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardFetchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [connection, setConnection] = useState<ConnectionState>("connecting");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [connectOpen, setConnectOpen] = useState(false);
  const refreshRef = useRef<() => Promise<void>>(async () => undefined);
  const connectionRef = useRef<ConnectionState>("connecting");

  const refresh = useCallback(async () => {
    setConnecting(true);
    const result = await fetchAllDashboardData(AbortSignal.timeout(8_000));
    setData(result);
    setLastUpdated(new Date());
    setLoading(false);
    setConnecting(false);
  }, []);
  refreshRef.current = refresh;

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    let source: EventSource | undefined;
    let retryTimer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;
    let stopped = false;
    const setRealtimeState = (state: ConnectionState) => { connectionRef.current = state; setConnection(state); };
    const open = () => {
      if (stopped) return;
      setRealtimeState(attempt ? "delayed" : "connecting");
      source = new EventSource("/api/v1/dashboard/events/stream");
      source.onopen = () => { attempt = 0; setRealtimeState("live"); };
      source.onmessage = () => { void refreshRef.current(); };
      source.addEventListener("connected", () => { setRealtimeState("live"); });
      source.onerror = () => {
        source?.close();
        setRealtimeState("delayed");
        const delay = Math.min(30_000, 1_000 * 2 ** attempt++);
        retryTimer = setTimeout(open, delay);
      };
    };
    open();
    // Polling is intentionally a safety net only. It is much slower than the SSE
    // reconnect cycle and covers deployments where event streaming is disabled.
    const fallback = setInterval(() => { if (connectionRef.current !== "live") void refreshRef.current(); }, 60_000);
    return () => { stopped = true; source?.close(); if (retryTimer) clearTimeout(retryTimer); clearInterval(fallback); };
  }, []);

  const mutate = async (operation: () => Promise<boolean | unknown>) => { await operation(); await refresh(); };
  const diagnostics = data?.diagnostics ?? {};
  const hasIssue = Object.values(diagnostics).some((item) => item.state === "error" || item.state === "unauthorized");
  const overview = data?.overview;
  const metric = (label: string, value: string | number, detail: string, icon: ReactNode) => (
    <article className="cyber-panel p-4 sm:p-5"><div className="flex items-start justify-between"><div><p className="eyebrow">{label}</p><p className="mt-2 text-2xl font-semibold tracking-tight text-white">{loading ? "—" : value}</p><p className="mt-1 text-xs text-slate-400">{detail}</p></div><div className="rounded-xl bg-white/[.06] p-2.5 text-violet-300">{icon}</div></div></article>
  );

  return <div className="min-h-screen"><Header overview={overview ?? null} onOpenConnect={() => setConnectOpen(true)} />
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
      <section className="glass-panel rounded-2xl p-5 sm:p-7"><div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between"><div><p className="eyebrow">Operations overview</p><h2 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">Everything in view. Nothing in the way.</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">Monitor live broadcasts, review safety decisions, and keep YouTube capacity healthy from one calm operational workspace.</p></div><div className="flex items-center gap-3"><span className="flex items-center gap-2 text-xs text-slate-400" aria-live="polite"><span className={`status-dot ${connection === "offline" ? "status-dot--danger" : connection === "delayed" ? "status-dot--warning" : ""}`} />{connection === "live" ? "Live updates" : connection === "delayed" ? "Reconnecting" : "Connecting"}</span><button onClick={() => void refresh()} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[.05] px-3 py-2 text-sm text-slate-200 hover:bg-white/[.09]"><RefreshCw className={`h-4 w-4 ${connecting ? "animate-spin" : ""}`} />Refresh</button></div></div></section>
      {hasIssue && <div role="status" className="flex items-start gap-3 rounded-xl border border-amber-300/20 bg-amber-300/[.07] p-4 text-sm text-amber-100"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>Some operational data is temporarily unavailable. Your actions and data remain protected; retrying will happen automatically.</span></div>}
      <section aria-label="System health" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{metric("System health", overview?.overall_status ?? "Checking", "Across connected services", <ShieldCheck className="h-5 w-5" />)}{metric("Active streams", overview?.active_streams ?? data?.streams.length ?? 0, "Currently monitored", <Activity className="h-5 w-5" />)}{metric("Needs review", overview?.pending_moderation_reviews ?? data?.reviews.length ?? 0, "Moderation decisions", <CheckCircle2 className="h-5 w-5" />)}{metric("Quota remaining", overview?.quota.remaining ?? data?.quota?.remaining ?? "—", "YouTube API units today", <Zap className="h-5 w-5" />)}</section>
      <section className="space-y-3"><div className="flex items-end justify-between"><div><p className="eyebrow">Live streams</p><h2 className="mt-1 text-lg font-semibold text-white">Broadcast workspace</h2></div><span className="text-xs text-slate-500">{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : "Waiting for data"}</span></div><StreamGrid streams={data?.streams ?? []} onControlAction={(id, action) => void mutate(() => sendStreamControlAction(id, action))} isLoading={loading} error={diagnostics.streams?.error} /></section>
      <section className="grid gap-6 lg:grid-cols-2"><QuotaCard quota={data?.quota ?? null} keys={data?.keys ?? []} onResetKey={(index) => void mutate(() => sendResetKeyCooldown(index))} isLoading={loading} error={diagnostics.quota?.error} /><IncidentPanel incidents={data?.incidents ?? []} onResolve={(id) => void mutate(() => sendResolveIncident(id))} isLoading={loading} error={diagnostics.incidents?.error} /></section>
      <ModerationQueue reviews={data?.reviews ?? []} onResolve={(id, action) => void mutate(() => sendResolveReview(id, action))} isLoading={loading} error={diagnostics.moderation?.error} />
      <details className="cyber-panel p-4 text-sm text-slate-400"><summary className="cursor-pointer font-medium text-slate-200">System diagnostics</summary><div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(diagnostics).map(([name, item]: [string, EndpointDiagnostic]) => <div key={name} className="rounded-lg bg-black/15 px-3 py-2"><span className="capitalize text-slate-200">{name}</span><span className="ml-2 text-xs">{item.httpStatus ? `HTTP ${item.httpStatus}` : item.state}</span></div>)}</div></details>
    </main><ManualConnectModal isOpen={connectOpen} onClose={() => setConnectOpen(false)} onConnect={async (value) => { await sendManualConnect(value); await refresh(); }} /></div>;
}
