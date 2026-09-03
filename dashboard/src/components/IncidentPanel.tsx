"use client";

import React from "react";
import { AlertCircle, CheckCircle, ShieldAlert } from "lucide-react";

interface IncidentItem {
  incident_id: string;
  severity: string;
  status: string;
  service: string;
  summary: string;
  actions_taken: string[];
  detected_at: string;
  resolved_at: string | null;
}

interface IncidentPanelProps {
  incidents: IncidentItem[];
  onResolve: (incidentId: string) => void;
}

export const IncidentPanel: React.FC<IncidentPanelProps> = ({ incidents, onResolve }) => {
  const getSeverityBadge = (sev: string) => {
    switch (sev.toUpperCase()) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-400 border-rose-500/40";
      case "HIGH":
        return "bg-amber-500/20 text-amber-400 border-amber-500/40";
      case "MEDIUM":
        return "bg-purple-500/20 text-purple-400 border-purple-500/40";
      default:
        return "bg-slate-800 text-slate-400 border-slate-700";
    }
  };

  return (
    <div className="cyber-panel p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-rose-400" />
          <h2 className="font-semibold text-sm text-slate-100 uppercase tracking-wider">
            Operational Incidents & Outages
          </h2>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
          {incidents?.filter((i) => i.status === "OPEN" || i.status === "INVESTIGATING").length || 0} ACTIVE
        </span>
      </div>

      {(!incidents || incidents.length === 0) ? (
        <div className="text-center py-6 text-slate-500 text-xs flex items-center justify-center gap-1.5">
          <CheckCircle className="w-4 h-4 text-emerald-500" />
          <span>All services healthy. Zero active incidents reported.</span>
        </div>
      ) : (
        <div className="space-y-2.5 max-h-[320px] overflow-y-auto pr-1">
          {incidents.map((inc) => (
            <div
              key={inc.incident_id}
              className="p-3 rounded-lg bg-surface-raised/80 border border-surface-border text-xs font-mono space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getSeverityBadge(inc.severity)}`}>
                    {inc.severity}
                  </span>
                  <span className="text-slate-200 font-bold">{inc.incident_id}</span>
                  <span className="text-slate-500">[{inc.service}]</span>
                </div>
                <span className="text-[10px] text-slate-400">{inc.status}</span>
              </div>

              <div className="text-slate-300 font-sans text-xs">{inc.summary}</div>

              {inc.status !== "RESOLVED" && inc.status !== "CLOSED" && (
                <div className="flex justify-end pt-1">
                  <button
                    onClick={() => onResolve(inc.incident_id)}
                    className="px-2 py-1 rounded bg-emerald-600/30 hover:bg-emerald-600/50 text-emerald-300 text-[11px] font-semibold border border-emerald-500/40 transition-colors"
                  >
                    Mark Resolved
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
