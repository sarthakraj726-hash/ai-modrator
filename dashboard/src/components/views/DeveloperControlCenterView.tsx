"use client";

import React, { useState } from "react";
import {
  Server,
  Activity,
  Key,
  ShieldAlert,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Database,
  Cpu,
  Layers,
  Terminal,
  Zap,
  Clock,
  Radio,
  FileCheck,
  AlertOctagon,
} from "lucide-react";
import {
  WorkersData,
  KeyItem,
  IncidentItem,
  EndpointDiagnostic,
  IntegrityAuditData,
  sendResetKeyCooldown,
  sendResolveIncident,
  sendRunIntegrityAudit,
} from "@/lib/api";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface DeveloperControlCenterViewProps {
  workersData: WorkersData | null;
  keys: KeyItem[];
  incidents: IncidentItem[];
  diagnostics: Record<string, EndpointDiagnostic>;
  onRefresh?: () => void;
  showToast: (msg: string, type: "success" | "error" | "info") => void;
}

export function DeveloperControlCenterView({
  workersData,
  keys,
  incidents,
  diagnostics,
  onRefresh,
  showToast,
}: DeveloperControlCenterViewProps) {
  const [resettingKey, setResettingKey] = useState<number | null>(null);
  const [resolvingIncident, setResolvingIncident] = useState<string | null>(null);
  const [isRunningAudit, setIsRunningAudit] = useState<boolean>(false);
  const [auditResult, setAuditResult] = useState<IntegrityAuditData | null>(null);

  const workers = workersData?.workers || [];
  const activeWorkers = workersData?.active_workers || 0;
  const staleWorkers = workersData?.stale_workers || 0;
  const errorWorkers = workersData?.error_workers || 0;
  const totalThroughput = workersData?.total_messages_per_minute || 0;

  const handleResetKey = async (keyIndex: number) => {
    setResettingKey(keyIndex);
    try {
      const ok = await sendResetKeyCooldown(keyIndex);
      if (ok) {
        showToast(`Reset cooldown for YouTube Key #${keyIndex}`, "success");
        onRefresh?.();
      } else {
        showToast(`Failed to reset cooldown for Key #${keyIndex}`, "error");
      }
    } catch {
      showToast(`Error resetting Key #${keyIndex}`, "error");
    } finally {
      setResettingKey(null);
    }
  };

  const handleResolveIncident = async (incidentId: string) => {
    setResolvingIncident(incidentId);
    try {
      const ok = await sendResolveIncident(incidentId);
      if (ok) {
        showToast(`Incident ${incidentId} marked as RESOLVED`, "success");
        onRefresh?.();
      } else {
        showToast(`Failed to resolve incident ${incidentId}`, "error");
      }
    } catch {
      showToast(`Error resolving incident ${incidentId}`, "error");
    } finally {
      setResolvingIncident(null);
    }
  };

  const handleRunAudit = async () => {
    setIsRunningAudit(true);
    try {
      const result = await sendRunIntegrityAudit();
      setAuditResult(result);
      if (result.is_valid) {
        showToast("Integrity audit PASSED: All ledgers balanced, zero violations", "success");
      } else {
        showToast(`Integrity audit flagged ${result.violations.length} violations`, "error");
      }
      onRefresh?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to run ledger audit";
      showToast(msg, "error");
    } finally {
      setIsRunningAudit(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Banner & Quick Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/80 p-6 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-3">
            <Server className="h-6 w-6 text-cyan-400" />
            <h2 className="text-xl font-bold tracking-tight text-white">
              Developer Operations & Reliability Center
            </h2>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Real-time supervised worker diagnostics, YouTube quota rotation pool, double-entry ledger audits, and system incidents.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleRunAudit}
            disabled={isRunningAudit}
            className="flex items-center gap-2 rounded-lg border border-cyan-500/40 bg-cyan-950/40 px-4 py-2 text-xs font-semibold text-cyan-300 shadow-lg shadow-cyan-950/50 hover:bg-cyan-900/60 transition-all disabled:opacity-50"
          >
            {isRunningAudit ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Auditing Ledgers...
              </>
            ) : (
              <>
                <FileCheck className="h-3.5 w-3.5 text-cyan-400" />
                Run On-Demand Ledger Audit
              </>
            )}
          </button>
        </div>
      </div>

      {/* SECTION 1: Supervised Worker Diagnostics */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-indigo-400" />
            <h3 className="text-base font-bold text-white">
              Supervised Live Chat Workers
            </h3>
            <span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs font-mono text-slate-400">
              {activeWorkers} active
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs font-mono text-slate-400">
            <span>Throughput: <strong className="text-cyan-400">{totalThroughput.toFixed(1)} msg/min</strong></span>
            {staleWorkers > 0 && (
              <span className="text-amber-400 font-bold flex items-center gap-1">
                <AlertTriangle className="h-3.5 w-3.5" />
                {staleWorkers} Stale Workers
              </span>
            )}
            {errorWorkers > 0 && (
              <span className="text-rose-400 font-bold flex items-center gap-1">
                <AlertOctagon className="h-3.5 w-3.5" />
                {errorWorkers} Error States
              </span>
            )}
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/60 shadow-xl backdrop-blur-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 bg-slate-950/60 font-mono uppercase text-slate-400">
                <tr>
                  <th className="px-4 py-3">Worker / Session ID</th>
                  <th className="px-4 py-3">Stream Target</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Throughput</th>
                  <th className="px-4 py-3 text-right">Processed</th>
                  <th className="px-4 py-3 text-right">Errors</th>
                  <th className="px-4 py-3 text-right">Heartbeat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {workers.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                      <div className="flex flex-col items-center justify-center gap-2">
                        <Radio className="h-6 w-6 text-slate-400 animate-pulse" />
                        <span>No active supervised workers in pool. Workers spawn automatically when streams go live.</span>
                      </div>
                    </td>
                  </tr>
                ) : (
                  workers.map((w) => (
                    <tr key={w.session_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3 font-mono font-medium text-slate-200">
                        <div className="flex items-center gap-2">
                          <span className="truncate max-w-[150px]">{w.session_id}</span>
                          {w.is_stale && (
                            <span className="rounded bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold text-amber-400">
                              STALE
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-400 font-sans">
                          Creator: {w.creator_id || "System"}
                        </div>
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-300">
                        {w.video_id ? (
                          <a
                            href={`https://youtube.com/watch?v=${w.video_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-cyan-400 hover:underline"
                          >
                            {w.video_id}
                          </a>
                        ) : (
                          "Direct Chat"
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          status={w.is_stale ? "STALE" : w.state}
                          size="sm"
                        />
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-cyan-400">
                        {w.messages_per_minute?.toFixed(1) || "0.0"} msg/m
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-slate-200">
                        {w.messages_processed.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right font-mono">
                        {w.consecutive_errors > 0 ? (
                          <span className="text-rose-400 font-bold">{w.consecutive_errors}</span>
                        ) : (
                          <span className="text-slate-400">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-slate-400">
                        {w.last_heartbeat_ago_seconds < 5 ? (
                          <span className="text-emerald-400">&lt; 5s ago</span>
                        ) : (
                          <span>{w.last_heartbeat_ago_seconds}s ago</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* SECTION 2: Double-Entry Ledger Integrity Suite */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-emerald-400" />
            <h3 className="text-base font-bold text-white">
              Double-Entry Ledger & Financial Invariant Audit
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Strict Zero-Sum Conservation Policy
          </span>
        </div>

        {auditResult ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 space-y-4 shadow-xl backdrop-blur-sm">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-3">
                {auditResult.is_valid ? (
                  <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm">
                    <CheckCircle2 className="h-5 w-5" />
                    Ledger Status: 100% BALANCED & INVARIANT VERIFIED
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
                    <AlertTriangle className="h-5 w-5" />
                    Ledger Status: INTEGRITY VIOLATION DETECTED
                  </div>
                )}
              </div>
              <div className="text-xs font-mono text-slate-400">
                Audited: {new Date(auditResult.timestamp).toLocaleTimeString()}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <div className="text-slate-400 uppercase tracking-wider text-[10px] font-bold">
                  Audited Transactions
                </div>
                <div className="mt-1 text-lg font-mono font-bold text-white">
                  {auditResult.stats?.ledger?.total_transactions_audited ?? 0}
                </div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <div className="text-slate-400 uppercase tracking-wider text-[10px] font-bold">
                  Imbalanced Tx
                </div>
                <div className={`mt-1 text-lg font-mono font-bold ${
                  (auditResult.stats?.ledger?.imbalanced_transactions ?? 0) > 0 ? "text-rose-400" : "text-emerald-400"
                }`}>
                  {auditResult.stats?.ledger?.imbalanced_transactions ?? 0}
                </div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <div className="text-slate-400 uppercase tracking-wider text-[10px] font-bold">
                  Global Debits / Credits
                </div>
                <div className="mt-1 text-sm font-mono text-slate-300">
                  {auditResult.stats?.ledger?.total_debits_global ?? 0} / {auditResult.stats?.ledger?.total_credits_global ?? 0}
                </div>
              </div>
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <div className="text-slate-400 uppercase tracking-wider text-[10px] font-bold">
                  Negative Balances
                </div>
                <div className={`mt-1 text-lg font-mono font-bold ${
                  (auditResult.stats?.balances?.negative_accounts_count ?? 0) > 0 ? "text-rose-400" : "text-emerald-400"
                }`}>
                  {auditResult.stats?.balances?.negative_accounts_count ?? 0}
                </div>
              </div>
            </div>

            {auditResult.violations.length > 0 && (
              <div className="mt-3 space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-rose-400">
                  Detected Discrepancies ({auditResult.violations.length})
                </h4>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {auditResult.violations.map((v, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between rounded border border-rose-500/30 bg-rose-950/20 px-3 py-2 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-rose-300">[{v.category}]</span>
                        <span className="text-slate-200">{v.details}</span>
                      </div>
                      <span className="font-mono text-[10px] text-rose-400 uppercase">{v.severity}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 text-center text-xs text-slate-400">
            Click <strong className="text-cyan-400">&ldquo;Run On-Demand Ledger Audit&rdquo;</strong> to perform a real-time cryptographic and invariant check across all ledger entries, account balances, and store inventory records.
          </div>
        )}
      </div>

      {/* SECTION 3: YouTube Key Pool & Failover Rotation */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Key className="h-5 w-5 text-amber-400" />
            <h3 className="text-base font-bold text-white">
              YouTube Data API Key Pool & Rotation
            </h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            Round-robin rotation with backoff cooldown
          </span>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-800/80 bg-slate-900/60 shadow-xl backdrop-blur-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-slate-800 bg-slate-950/60 font-mono uppercase text-slate-400">
                <tr>
                  <th className="px-4 py-3">Slot / Index</th>
                  <th className="px-4 py-3">Masked API Key</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Requests Made</th>
                  <th className="px-4 py-3 text-right">Quota Units</th>
                  <th className="px-4 py-3 text-right">Cooldown Status</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {keys.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-6 text-center text-slate-400">
                      No API keys configured or loaded.
                    </td>
                  </tr>
                ) : (
                  keys.map((k) => (
                    <tr key={k.key_index} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3 font-mono font-bold text-slate-300">
                        {k.slot || `KEY_${k.key_index}`}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-200">
                        {k.masked_key}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          status={k.in_cooldown ? "COOLDOWN" : k.status}
                          size="sm"
                        />
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-slate-300">
                        {k.requests_made.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-amber-400">
                        {k.quota_units.toLocaleString()} pts
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-slate-400">
                        {k.in_cooldown ? (
                          <span className="text-rose-400 font-bold">
                            Cooldown until {k.cooldown_until ? new Date(k.cooldown_until).toLocaleTimeString() : "active"}
                          </span>
                        ) : (
                          <span className="text-emerald-400">Ready</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {k.in_cooldown && (
                          <button
                            type="button"
                            onClick={() => handleResetKey(k.key_index)}
                            disabled={resettingKey === k.key_index}
                            className="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-[11px] font-semibold text-slate-200 hover:bg-slate-700 transition-colors disabled:opacity-50"
                          >
                            {resettingKey === k.key_index ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <RotateCcw className="h-3 w-3 text-slate-400" />
                            )}
                            Reset Cooldown
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* SECTION 4: Active Incidents & Triage */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-rose-400" />
            <h3 className="text-base font-bold text-white">
              System Incidents & SRE Triage Log
            </h3>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            {incidents.filter((i) => i.status !== "RESOLVED").length} unresolved
          </span>
        </div>

        {incidents.length === 0 ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 text-center text-xs text-slate-400">
            <CheckCircle2 className="h-6 w-6 text-emerald-400 mx-auto mb-2" />
            Zero active incidents. All background services and workers are nominal.
          </div>
        ) : (
          <div className="space-y-3">
            {incidents.map((inc) => (
              <div
                key={inc.incident_id}
                className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border p-4 backdrop-blur-sm transition-all ${
                  inc.status === "RESOLVED"
                    ? "border-slate-800 bg-slate-950/40 text-slate-400"
                    : "border-rose-500/30 bg-rose-950/20 text-slate-200 shadow-lg shadow-rose-950/20"
                }`}
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs font-bold text-white">
                      {inc.incident_id}
                    </span>
                    <StatusBadge status={inc.severity} size="sm" />
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-slate-300">
                      {inc.service}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {new Date(inc.detected_at).toLocaleTimeString()}
                    </span>
                  </div>
                  <p className="text-xs font-medium text-slate-300">
                    {inc.summary}
                  </p>
                </div>

                {inc.status !== "RESOLVED" && (
                  <button
                    type="button"
                    onClick={() => handleResolveIncident(inc.incident_id)}
                    disabled={resolvingIncident === inc.incident_id}
                    className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-950/40 px-3 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-900/60 transition-colors disabled:opacity-50"
                  >
                    {resolvingIncident === inc.incident_id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    )}
                    Mark Resolved
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* SECTION 5: Subsystem Diagnostics Matrix */}
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Terminal className="h-5 w-5 text-cyan-400" />
          <h3 className="text-base font-bold text-white">
            Backend Endpoint Diagnostic Matrix
          </h3>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {Object.entries(diagnostics).map(([endpoint, diag]) => (
            <div
              key={endpoint}
              className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-xs backdrop-blur-sm"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="font-mono font-bold text-slate-200 capitalize">
                  {endpoint}
                </span>
                <span
                  className={`rounded px-1.5 py-0.2 text-[10px] font-mono font-bold ${
                    diag.state === "success"
                      ? "bg-emerald-500/10 text-emerald-400"
                      : diag.state === "error"
                      ? "bg-rose-500/10 text-rose-400"
                      : diag.state === "unauthorized"
                      ? "bg-amber-500/10 text-amber-400"
                      : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {diag.httpStatus ? `HTTP ${diag.httpStatus}` : diag.state.toUpperCase()}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 truncate">
                {diag.error ? (
                  <span className="text-rose-400 font-semibold">{diag.error}</span>
                ) : (
                  <span className="text-emerald-400/80 font-mono">200 OK • Healthy</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
