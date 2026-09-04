"use client";

import React from "react";
import { Play, Square, RotateCcw, MessageSquare, Clock, Tv } from "lucide-react";
import { StreamItem } from "@/lib/api";

interface StreamGridProps {
  streams: StreamItem[];
  onControlAction: (streamId: string, action: string) => void;
  isLoading?: boolean;
  error?: string | null;
}

export const StreamGrid: React.FC<StreamGridProps> = ({ streams, onControlAction, isLoading, error }) => {
  const getStatusBadge = (status: string) => {
    switch ((status || "").toUpperCase()) {
      case "LIVE":
      case "ACTIVE":
      case "RUNNING":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40 animate-pulse">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500"></span> LIVE
          </span>
        );
      case "CONNECTING":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/20 text-amber-400 border border-amber-500/40">
            CONNECTING
          </span>
        );
      case "ENDED":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
            ENDED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-400 border border-slate-700">
            {status || "IDLE"}
          </span>
        );
    }
  };

  const formatDuration = (secs: number) => {
    if (!secs || isNaN(secs)) return "0h 0m";
    const hours = Math.floor(secs / 3600);
    const mins = Math.floor((secs % 3600) / 60);
    return `${hours}h ${mins}m`;
  };

  if (error) {
    return (
      <div className="cyber-panel p-6 text-center border border-rose-500/40 bg-rose-500/5">
        <Tv className="w-8 h-8 mx-auto mb-2 text-rose-400" />
        <p className="text-rose-300 text-sm font-semibold">Streams Telemetry Unavailable</p>
        <p className="text-xs text-slate-400 mt-1 font-mono">{error}</p>
      </div>
    );
  }

  if (isLoading && (!streams || streams.length === 0)) {
    return (
      <div className="cyber-panel p-8 text-center border-dashed border-slate-800">
        <Tv className="w-10 h-10 mx-auto mb-3 text-slate-600 animate-pulse" />
        <p className="text-slate-400 text-sm font-medium">Connecting to stream worker telemetry...</p>
      </div>
    );
  }

  if (!streams || streams.length === 0) {
    return (
      <div className="cyber-panel p-8 text-center border-dashed border-slate-800">
        <Tv className="w-10 h-10 mx-auto mb-3 text-slate-600" />
        <p className="text-slate-400 text-sm font-medium">No live streams active.</p>
        <p className="text-xs text-slate-500 mt-1">
          Click &ldquo;+ CONNECT STREAM&rdquo; in the top header to attach a YouTube Live broadcast.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {streams.map((s) => (
        <div
          key={s.session_id}
          className="cyber-panel p-4 hover:border-purple-500/40 transition-all group flex flex-col justify-between"
        >
          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="font-semibold text-sm text-slate-100 group-hover:text-purple-300 transition-colors truncate">
                {s.channel_name}
              </span>
              {getStatusBadge(s.status)}
            </div>

            <div className="space-y-1.5 text-xs text-slate-400 mb-4 font-mono">
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Video ID:</span>
                <span className="text-cyan-400">{s.youtube_video_id}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Duration:</span>
                <span className="flex items-center gap-1 text-slate-300">
                  <Clock className="w-3 h-3 text-slate-500" />
                  {formatDuration(s.duration_seconds)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500">Session ID:</span>
                <span className="text-slate-400 truncate max-w-[120px]">{s.session_id}</span>
              </div>
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-3 border-t border-surface-border/80 flex items-center justify-between gap-2">
            <button
              onClick={() => onControlAction(s.session_id, "restart")}
              className="flex-1 px-2.5 py-1.5 rounded bg-surface-raised hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-mono transition-colors flex items-center justify-center gap-1.5 border border-surface-border"
              title="Restart stream worker"
            >
              <RotateCcw className="w-3 h-3" />
              <span>RESTART</span>
            </button>
            <button
              onClick={() => onControlAction(s.session_id, "disconnect")}
              className="px-3 py-1.5 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-mono transition-colors flex items-center justify-center gap-1"
              title="Disconnect live chat worker"
            >
              <Square className="w-3 h-3" />
              <span>STOP</span>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};
