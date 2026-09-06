"use client";

import React, { useState } from "react";
import {
  Check,
  CheckCircle2,
  Clock,
  Filter,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  X,
} from "lucide-react";
import { StatusBadge } from "../ui/StatusBadge";
import type { ReviewItem } from "@/lib/api";

interface ModerationViewProps {
  reviews: ReviewItem[];
  isLoading: boolean;
  onResolve: (reviewId: string, action: string) => void;
}

export const ModerationView: React.FC<ModerationViewProps> = ({
  reviews,
  isLoading,
  onResolve,
}) => {
  const [filter, setFilter] = useState<string>("PENDING");
  const [search, setSearch] = useState<string>("");
  const [actionNotes, setActionNotes] = useState<Record<string, string>>({});

  const filteredReviews = reviews.filter((r) => {
    const matchesFilter =
      filter === "ALL" || (r.status || "PENDING").toUpperCase() === filter;
    const matchesSearch =
      r.author_display_name.toLowerCase().includes(search.toLowerCase()) ||
      r.message_text.toLowerCase().includes(search.toLowerCase()) ||
      r.reason.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const pendingCount = reviews.filter(
    (r) => (r.status || "PENDING").toUpperCase() === "PENDING"
  ).length;
  const approvedCount = reviews.filter(
    (r) => (r.status || "").toUpperCase() === "APPROVED"
  ).length;
  const rejectedCount = reviews.filter(
    (r) => (r.status || "").toUpperCase() === "REJECTED"
  ).length;

  const getConfidenceColor = (conf: number) => {
    if (conf >= 85) return "text-rose-400 bg-rose-500/10 border-rose-500/30";
    if (conf >= 60) return "text-amber-400 bg-amber-500/10 border-amber-500/30";
    return "text-cyan-400 bg-cyan-500/10 border-cyan-500/30";
  };

  return (
    <div className="space-y-6">
      {/* Header & Filter Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white sm:text-2xl flex items-center gap-2">
            <Shield className="w-5 h-5 text-violet-400" />
            HITL Moderation Queue
          </h2>
          <p className="mt-0.5 text-xs font-mono text-slate-400">
            Fail-safe review queue: ambiguous content is held for human confirmation
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search content or author..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 rounded-xl bg-white/[0.04] border border-white/10 text-xs font-mono text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-400"
            />
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-white/[0.08] pb-3">
        {[
          { id: "PENDING", label: "Pending Reviews", count: pendingCount },
          { id: "APPROVED", label: "Approved (Kept)", count: approvedCount },
          { id: "REJECTED", label: "Enforced / Timeout", count: rejectedCount },
          { id: "ALL", label: "All Items", count: reviews.length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilter(tab.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-colors inline-flex items-center gap-1.5 ${
              filter === tab.id
                ? "bg-violet-400/15 text-violet-300 font-semibold border border-violet-400/30"
                : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.04]"
            }`}
          >
            <span>{tab.label}</span>
            <span
              className={`px-1.5 py-0.2 rounded text-[10px] ${
                filter === tab.id
                  ? "bg-violet-400/30 text-white"
                  : "bg-white/[0.06] text-slate-400"
              }`}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Review Queue Items */}
      {filteredReviews.length === 0 ? (
        <div className="rounded-2xl border border-white/[0.08] bg-[#11131c] p-12 text-center space-y-3">
          <ShieldCheck className="w-10 h-10 mx-auto text-emerald-400 opacity-60" />
          <p className="text-sm font-semibold text-slate-300">
            {filter === "PENDING"
              ? "All clean! Zero pending moderation tickets."
              : "No tickets match this filter."}
          </p>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Live stream chat messages are evaluated by the safety classifier. Flagged messages appear here for rapid 1-click human verification.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredReviews.map((r) => {
            const conf = r.confidence ?? 85;
            return (
              <div
                key={r.id}
                className="rounded-xl border border-white/[0.08] bg-[#11131c] p-4 sm:p-5 space-y-3 hover:border-white/[0.14] transition-all"
              >
                {/* Header row */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-white">
                      @{r.author_display_name}
                    </span>
                    {r.viewer_name && r.viewer_name !== r.author_display_name && (
                      <span className="text-xs font-mono text-slate-400">
                        ({r.viewer_name})
                      </span>
                    )}
                    <span className="text-slate-600">•</span>
                    <span className="text-xs font-mono text-slate-400">
                      Reason: <strong className="text-slate-300">{r.reason}</strong>
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[11px] font-mono px-2 py-0.5 rounded border ${getConfidenceColor(
                        conf
                      )}`}
                    >
                      AI Confidence: {conf}%
                    </span>
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-white/[0.06] text-slate-300 border border-white/10">
                      Action: {r.recommended_action || "TIMEOUT"}
                    </span>
                    <StatusBadge status={r.status || "PENDING"} size="sm" />
                  </div>
                </div>

                {/* Flagged Message Container */}
                <div className="rounded-lg bg-black/40 border border-white/[0.06] p-3 text-sm text-slate-200 font-mono italic">
                  &ldquo;{r.message_text}&rdquo;
                </div>

                {/* Action Controls */}
                {r.status === "PENDING" && (
                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2 border-t border-white/[0.06]">
                    <span className="text-xs font-mono text-slate-400 flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-slate-400" />
                      Detected {new Date(r.created_at).toLocaleTimeString()}
                    </span>

                    <div className="flex items-center gap-2 justify-end">
                      <button
                        onClick={() => onResolve(r.id, "DENY")}
                        className="px-3.5 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 text-xs font-semibold font-mono transition-colors inline-flex items-center gap-1.5"
                        title="Enforce timeout/deletion"
                      >
                        <X className="w-3.5 h-3.5" />
                        <span>Enforce ({r.recommended_action || "Timeout"})</span>
                      </button>
                      <button
                        onClick={() => onResolve(r.id, "APPROVE")}
                        className="px-3.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 text-xs font-semibold font-mono transition-colors inline-flex items-center gap-1.5"
                        title="Dismiss violation and allow message"
                      >
                        <Check className="w-3.5 h-3.5" />
                        <span>Approve (Allow Message)</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
