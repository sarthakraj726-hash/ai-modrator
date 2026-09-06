"use client";

import React, { useState } from "react";
import {
  Clock,
  ExternalLink,
  Info,
  MessageSquare,
  Plus,
  Radio,
  RotateCcw,
  Square,
  Tv,
  X,
} from "lucide-react";
import { StatusBadge } from "../ui/StatusBadge";
import type { StreamItem } from "@/lib/api";

interface StreamsViewProps {
  streams: StreamItem[];
  isLoading: boolean;
  onControlAction: (streamId: string, action: string) => void;
  onOpenConnect: () => void;
}

export const StreamsView: React.FC<StreamsViewProps> = ({
  streams,
  isLoading,
  onControlAction,
  onOpenConnect,
}) => {
  const [selectedStream, setSelectedStream] = useState<StreamItem | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredStreams = streams.filter(
    (s) =>
      s.channel_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.youtube_video_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.session_id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const formatDuration = (secs: number) => {
    if (!secs || isNaN(secs)) return "0h 0m";
    const hours = Math.floor(secs / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    const s = secs % 60;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m ${s}s`;
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white sm:text-2xl flex items-center gap-2">
            <Radio className="w-5 h-5 text-rose-400" />
            Broadcast Operations
          </h2>
          <p className="mt-0.5 text-xs font-mono text-slate-400">
            {streams.length} total monitored stream sessions
          </p>
        </div>

        <div className="flex items-center gap-2.5 w-full sm:w-auto">
          <input
            type="text"
            placeholder="Filter streams..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="px-3 py-2 rounded-xl bg-white/[0.04] border border-white/10 text-xs font-mono text-white placeholder:text-slate-400 focus:outline-none focus:border-violet-400 w-full sm:w-48"
          />
          <button
            onClick={onOpenConnect}
            className="inline-flex items-center gap-1.5 rounded-xl bg-violet-400 hover:bg-violet-300 text-slate-950 px-3.5 py-2 text-xs font-semibold shrink-0 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Connect Stream
          </button>
        </div>
      </div>

      {/* Streams Grid / Cards */}
      {filteredStreams.length === 0 ? (
        <div className="rounded-2xl border border-white/[0.08] bg-[#11131c] p-12 text-center space-y-3">
          <Tv className="w-10 h-10 mx-auto text-slate-400 opacity-60" />
          <p className="text-sm font-semibold text-slate-300">
            {searchQuery ? "No matching streams found." : "No live streams connected."}
          </p>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            {searchQuery
              ? "Try adjusting your search query."
              : "Click 'Connect Stream' to attach Goddess AI to an active YouTube Live stream."}
          </p>
          {!searchQuery && (
            <button
              onClick={onOpenConnect}
              className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.10] text-slate-200 text-xs font-medium border border-white/10 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Connect Stream Now
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredStreams.map((s) => (
            <div
              key={s.session_id}
              className="rounded-xl border border-white/[0.08] bg-[#11131c] p-5 space-y-4 hover:border-white/[0.16] transition-all flex flex-col justify-between"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-base font-semibold text-white truncate max-w-[200px]">
                      {s.channel_name}
                    </h3>
                    {s.youtube_video_id && (
                      <a
                        href={`https://youtube.com/watch?v=${s.youtube_video_id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-violet-300 mt-0.5"
                      >
                        <span>{s.youtube_video_id}</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    )}
                  </div>
                  <StatusBadge status={s.status} size="sm" pulse />
                </div>

                <div className="space-y-2 pt-2 border-t border-white/[0.06] text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Worker Status:</span>
                    <span
                      className={
                        s.is_worker_alive ? "text-emerald-400" : "text-amber-400"
                      }
                    >
                      {s.is_worker_alive ? "Supervised Active" : "Awaiting Restart"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Messages Ingested:</span>
                    <span className="text-slate-200 font-bold">
                      {s.messages_processed ?? 0}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-400">Duration:</span>
                    <span className="text-slate-300 flex items-center gap-1">
                      <Clock className="w-3 h-3 text-slate-400" />
                      {formatDuration(s.duration_seconds)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="pt-3 border-t border-white/[0.06] flex items-center justify-between gap-2">
                <button
                  onClick={() => setSelectedStream(s)}
                  className="px-2.5 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-300 text-xs font-mono transition-colors border border-white/10 inline-flex items-center gap-1"
                  title="Inspect runtime stream telemetry"
                >
                  <Info className="w-3.5 h-3.5" />
                  <span>Inspect</span>
                </button>

                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => onControlAction(s.session_id, "restart")}
                    className="px-2.5 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-slate-200 text-xs font-mono transition-colors border border-white/10 inline-flex items-center gap-1"
                    title="Restart stream chat worker"
                  >
                    <RotateCcw className="w-3 h-3" />
                    <span>Restart</span>
                  </button>
                  <button
                    onClick={() => {
                      if (
                        window.confirm(
                          `Disconnect broadcast ${s.channel_name}? Worker will cleanly exit.`
                        )
                      ) {
                        onControlAction(s.session_id, "disconnect");
                      }
                    }}
                    className="px-2.5 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-mono transition-colors inline-flex items-center gap-1"
                    title="Disconnect live stream"
                  >
                    <Square className="w-3 h-3" />
                    <span>Stop</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stream Detail Inspector Modal */}
      {selectedStream && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm"
        >
          <div className="rounded-2xl border border-white/10 bg-[#12141f] max-w-lg w-full p-6 space-y-5 shadow-2xl relative">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">
                  {selectedStream.channel_name}
                </h3>
                <p className="text-xs font-mono text-slate-400">
                  Session: {selectedStream.session_id}
                </p>
              </div>
              <button
                onClick={() => setSelectedStream(null)}
                className="rounded-lg p-1 text-slate-400 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs font-mono bg-black/40 rounded-xl p-4 border border-white/[0.06]">
              <div className="flex justify-between py-1 border-b border-white/[0.06]">
                <span className="text-slate-400">YouTube Video ID:</span>
                <span className="text-slate-200">{selectedStream.youtube_video_id || "None"}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-white/[0.06]">
                <span className="text-slate-400">Live Chat ID:</span>
                <span className="text-slate-200 truncate max-w-[200px]">
                  {selectedStream.youtube_live_chat_id || "Resolved on join"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-white/[0.06]">
                <span className="text-slate-400">Creator ID:</span>
                <span className="text-slate-200">{selectedStream.creator_id}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-white/[0.06]">
                <span className="text-slate-400">Started At:</span>
                <span className="text-slate-200">
                  {selectedStream.started_at
                    ? new Date(selectedStream.started_at).toLocaleString()
                    : "Unknown"}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-white/[0.06]">
                <span className="text-slate-400">Session Status:</span>
                <StatusBadge status={selectedStream.status} size="sm" />
              </div>
              <div className="flex justify-between py-1">
                <span className="text-slate-400">Messages Processed:</span>
                <span className="text-emerald-400 font-bold">
                  {selectedStream.messages_processed}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => {
                  onControlAction(selectedStream.session_id, "reconcile");
                  setSelectedStream(null);
                }}
                className="px-3.5 py-2 rounded-xl bg-white/[0.06] hover:bg-white/[0.10] text-slate-200 text-xs font-semibold border border-white/10 transition-colors"
              >
                Reconcile Status
              </button>
              <button
                onClick={() => setSelectedStream(null)}
                className="px-4 py-2 rounded-xl bg-violet-400 hover:bg-violet-300 text-slate-950 text-xs font-semibold transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
