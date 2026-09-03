"use client";

import React, { useState } from "react";
import { X, Play, AlertCircle } from "lucide-react";

interface ManualConnectModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConnect: (urlOrId: string) => Promise<void>;
}

export const ManualConnectModal: React.FC<ManualConnectModalProps> = ({
  isOpen,
  onClose,
  onConnect,
}) => {
  const [inputVal, setInputVal] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;

    setIsLoading(true);
    setError(null);
    try {
      await onConnect(inputVal.trim());
      setInputVal("");
      onClose();
    } catch (err: any) {
      setError(err?.message || "Failed to initiate stream connection.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="cyber-panel p-6 max-w-md w-full space-y-4 border-purple-500/50 shadow-glow-purple">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider flex items-center gap-2">
            <Play className="w-4 h-4 text-cyan-400" />
            Connect Live Stream
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-slate-400">
          Enter a YouTube Live Watch URL (e.g. <code>youtube.com/watch?v=...</code>) or direct 11-character Video ID to attach Honney.
        </p>

        {error && (
          <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              placeholder="https://youtube.com/watch?v=..."
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-surface-raised border border-surface-border text-slate-100 placeholder-slate-500 text-xs font-mono focus:outline-none focus:border-purple-500 transition-colors"
              disabled={isLoading}
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded text-xs text-slate-400 hover:text-white transition-colors"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || !inputVal.trim()}
              className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-glow-purple transition-all active:scale-95 disabled:opacity-50"
            >
              {isLoading ? "Connecting..." : "Initiate Connection"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
