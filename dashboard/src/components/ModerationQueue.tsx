"use client";

import React from "react";
import { Shield, Check, X, AlertOctagon } from "lucide-react";
import { ReviewItem } from "@/lib/api";

interface ModerationQueueProps {
  reviews: ReviewItem[];
  onResolve: (reviewId: string, action: string) => void;
  isLoading?: boolean;
  error?: string | null;
}

export const ModerationQueue: React.FC<ModerationQueueProps> = ({ reviews, onResolve, isLoading, error }) => {
  return (
    <div className="cyber-panel p-5 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-purple-400" />
          <h2 className="font-semibold text-sm text-slate-100 uppercase tracking-wider">
            HITL Moderation Queue
          </h2>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30">
          {reviews?.length || 0} PENDING
        </span>
      </div>

      {error ? (
        <div className="text-center py-6 text-rose-400 text-xs border border-rose-500/30 rounded bg-rose-500/5">
          <p className="font-semibold">Moderation Queue Unavailable</p>
          <p className="text-slate-400 font-mono mt-1">{error}</p>
        </div>
      ) : (!reviews || reviews.length === 0) ? (
        <div className="text-center py-8 text-slate-500 text-xs">
          {isLoading ? "Fetching pending moderation tickets..." : "No pending moderation reviews. All stream chats are safe."}
        </div>
      ) : (
        <div className="space-y-2.5 max-h-[360px] overflow-y-auto pr-1">
          {reviews.map((r) => (
            <div
              key={r.id}
              className="p-3 rounded-lg bg-surface-raised/80 border border-surface-border hover:border-purple-500/40 transition-colors text-xs font-mono space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-rose-400">@{r.author_display_name}</span>
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30">
                    {r.recommended_action}
                  </span>
                  <span className="text-[10px] text-slate-500">Sev: {r.severity}%</span>
                </div>
              </div>

              <div className="p-2 rounded bg-black/40 text-slate-300 italic break-words border border-slate-900">
                &ldquo;{r.message_text}&rdquo;
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-[11px] text-slate-500 truncate max-w-[200px]">
                  Reason: {r.reason}
                </span>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => onResolve(r.id, "APPROVE")}
                    className="px-2.5 py-1 rounded bg-rose-600/30 hover:bg-rose-600/50 text-rose-300 font-bold flex items-center gap-1 border border-rose-500/40 transition-colors"
                    title="Enforce recommended punishment (Timeout / Delete)"
                  >
                    <Check className="w-3 h-3" />
                    <span>ENFORCE</span>
                  </button>
                  <button
                    onClick={() => onResolve(r.id, "DENY")}
                    className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 font-medium flex items-center gap-1 border border-slate-700 transition-colors"
                    title="Dismiss violation (Allow message)"
                  >
                    <X className="w-3 h-3" />
                    <span>DISMISS</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
