"use client";

import React, { useEffect, useRef, useState } from "react";
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
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    inputRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape" && !isLoading) onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isOpen, isLoading, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = inputVal.trim();
    const valid = /^[\w-]{11}$/.test(value) || /^https?:\/\/(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)/i.test(value);
    if (!valid) { setError("Enter a valid YouTube watch link or 11-character video ID."); return; }

    setIsLoading(true);
    setError(null);
    try {
      await onConnect(inputVal.trim());
      setInputVal("");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to start the connection. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !isLoading) onClose(); }}>
      <div className="cyber-panel p-6 max-w-md w-full space-y-4" role="dialog" aria-modal="true" aria-labelledby="connect-title">
        <div className="flex items-center justify-between">
          <h3 id="connect-title" className="text-lg font-semibold text-white flex items-center gap-2">
            <Play className="w-4 h-4 text-violet-300" /> Connect live stream
          </h3>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
            aria-label="Close connect stream dialog"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <p className="text-xs text-slate-400">
          Paste a YouTube Live watch URL or a video ID. We’ll verify it before connecting.
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
              ref={inputRef}
              aria-label="YouTube watch URL or video ID"
              type="text"
              placeholder="https://youtube.com/watch?v=..."
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              className="w-full px-3 py-2.5 rounded-xl bg-black/20 border border-white/10 text-slate-100 placeholder-slate-500 text-sm focus:outline-none transition-colors"
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
