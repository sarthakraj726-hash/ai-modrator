"use client";

import React from "react";
import { Key, Gauge, AlertTriangle, CheckCircle2 } from "lucide-react";

interface KeyItem {
  key_index: number;
  masked_key: string;
  requests_made: number;
  quota_units: number;
  in_cooldown: boolean;
  cooldown_until: string | null;
  last_used_at: string | null;
}

interface QuotaCardProps {
  quota: {
    budget: number;
    consumed: number;
    remaining: number;
    percent_used: number;
    threshold_status: string;
  };
  keys: KeyItem[];
  onResetKey: (index: number) => void;
}

export const QuotaCard: React.FC<QuotaCardProps> = ({ quota, keys, onResetKey }) => {
  const percent = quota?.percent_used || 0;

  const getProgressColor = () => {
    if (percent >= 90) return "bg-rose-500";
    if (percent >= 75) return "bg-amber-500";
    return "bg-gradient-to-r from-purple-500 to-cyan-400";
  };

  return (
    <div className="cyber-panel p-5 space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Gauge className="w-4 h-4 text-cyan-400" />
          <h2 className="font-semibold text-sm text-slate-100 uppercase tracking-wider">
            YouTube API Quota Governance
          </h2>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
          DAILY BUDGET: {quota?.budget || 4000} UNITS
        </span>
      </div>

      {/* Progress Bar & Stats */}
      <div className="space-y-2">
        <div className="flex justify-between items-baseline text-xs font-mono">
          <span className="text-slate-400">
            Consumed: <strong className="text-white">{quota?.consumed || 0}</strong> units
          </span>
          <span className="text-slate-400">
            Remaining: <strong className="text-emerald-400">{quota?.remaining || 0}</strong> ({100 - percent}%)
          </span>
        </div>
        <div className="w-full h-3 bg-slate-900 rounded-full overflow-hidden border border-surface-border p-0.5">
          <div
            className={`h-full rounded-full transition-all duration-500 ${getProgressColor()}`}
            style={{ width: `${Math.min(100, percent)}%` }}
          ></div>
        </div>
      </div>

      {/* Key Pool Monitor */}
      <div className="pt-3 border-t border-surface-border space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
          <div className="flex items-center gap-1.5">
            <Key className="w-3.5 h-3.5 text-purple-400" />
            <span>Multi-Key Pool Status ({keys?.length || 0} keys)</span>
          </div>
          <span>Tiered Rotation</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {keys && keys.map((k) => (
            <div
              key={k.key_index}
              className="p-2.5 rounded-lg bg-surface-raised/60 border border-surface-border flex items-center justify-between text-xs font-mono"
            >
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-slate-200 font-semibold">{k.masked_key}</span>
                  {k.in_cooldown ? (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-rose-500/20 text-rose-400 border border-rose-500/40">
                      COOLDOWN
                    </span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                      ACTIVE
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Reqs: {k.requests_made} • Est: {k.quota_units} pts
                </div>
              </div>

              {k.in_cooldown && (
                <button
                  onClick={() => onResetKey(k.key_index)}
                  className="px-2 py-1 rounded bg-purple-600/30 hover:bg-purple-600/50 text-purple-300 text-[11px] transition-colors border border-purple-500/40"
                >
                  Reset
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
