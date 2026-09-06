"use client";

import React, { useState } from "react";
import {
  Sparkles,
  Bot,
  Zap,
  Clock,
  ShieldCheck,
  Send,
  Loader2,
  Copy,
  CheckCircle2,
  MessageSquare,
  Volume2,
  Cpu,
  AlertCircle,
} from "lucide-react";
import { CohostData, sendTestRemark } from "@/lib/api";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface CohostViewProps {
  data: CohostData | null;
  onRefresh?: () => void;
  showToast: (msg: string, type: "success" | "error" | "info") => void;
}

export function CohostView({ data, showToast }: CohostViewProps) {
  // Test generator state
  const [eventType, setEventType] = useState<string>("superchat");
  const [authorName, setAuthorName] = useState<string>("NeonRider_42");
  const [amount, setAmount] = useState<string>("$20.00");
  const [customMessage, setCustomMessage] = useState<string>(
    "Keep up the amazing content! Big fan since episode 1!"
  );
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generatedRemark, setGeneratedRemark] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  const personaName = data?.persona_name || "Honney";
  const personaType = data?.persona_type || "Autonomous Stream Co-Pilot";
  const style = data?.style || "Energetic, witty, supportive, creator-focused";
  const verbosity = data?.verbosity || "Concise (1-2 sentences)";
  const monthlyBudget = data?.monthly_token_budget || 500000;
  const maxReplyTokens = data?.max_reply_tokens || 150;
  const maxReplyChars = data?.max_reply_chars || 280;
  const cooldownSecs = data?.cooldown_seconds || 30;
  const supportedScenarios = data?.supported_scenarios || [
    "superchat_celebration",
    "subscriber_welcome",
    "milestone_announcement",
    "chat_highlight",
    "hype_trigger",
  ];

  const handleGenerateRemark = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsGenerating(true);
    setGeneratedRemark(null);

    try {
      const context: Record<string, unknown> = {
        author_name: authorName.trim() || "Viewer",
        channel_name: "Stream Host",
      };

      if (eventType === "superchat") {
        context.amount = amount;
        context.message = customMessage;
      } else if (eventType === "subscriber") {
        context.tier = "Gold Tier";
        context.months = 1;
      } else if (eventType === "milestone") {
        context.milestone = "100,000 Subscribers Reached";
      } else if (eventType === "chat_highlight") {
        context.highlighted_message = customMessage;
      }

      const res = await sendTestRemark(eventType, context);
      setGeneratedRemark(res.remark);
      showToast(`Generated Honney remark for ${eventType}`, "success");
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Failed to generate remark";
      showToast(errMsg, "error");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleCopyRemark = () => {
    if (!generatedRemark) return;
    navigator.clipboard.writeText(generatedRemark);
    setCopied(true);
    showToast("Remark copied to clipboard", "info");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Top Hero Card */}
      <div className="relative overflow-hidden rounded-xl border border-violet-500/30 bg-gradient-to-br from-violet-950/40 via-slate-900 to-slate-950 p-6 shadow-2xl backdrop-blur-md">
        <div className="absolute -right-12 -top-12 h-64 w-64 rounded-full bg-violet-600/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-violet-600 to-fuchsia-500 shadow-lg shadow-violet-500/25">
              <Sparkles className="h-7 w-7 text-white animate-pulse" />
              <div className="absolute -bottom-1 -right-1 h-4 w-4 rounded-full border-2 border-slate-950 bg-emerald-400" />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold tracking-tight text-white font-mono">
                  {personaName}
                </h2>
                <span className="rounded-md border border-violet-400/30 bg-violet-500/10 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-violet-300">
                  AI Co-Host Engine
                </span>
                <StatusBadge status="ACTIVE" size="sm" />
              </div>
              <p className="mt-1 text-sm text-slate-300">
                {personaType} • {style}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2 text-right">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Throttle Cooldown
              </div>
              <div className="text-base font-bold font-mono text-emerald-400">
                {cooldownSecs}s / event
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2 text-right">
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Verbosity Gate
              </div>
              <div className="text-base font-bold font-mono text-violet-300">
                {verbosity}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Persona Specs & Token Guardrails Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400">
            <Cpu className="h-4 w-4 text-violet-400" />
            Monthly Token Cap
          </div>
          <div className="mt-2 text-2xl font-extrabold font-mono text-white">
            {monthlyBudget.toLocaleString()}
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
            <div className="h-full bg-violet-500 rounded-full" style={{ width: "18%" }} />
          </div>
          <div className="mt-1.5 flex justify-between text-[11px] text-slate-400 font-mono">
            <span>Allocated</span>
            <span className="text-emerald-400">82% remaining</span>
          </div>
        </div>

        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400">
            <Zap className="h-4 w-4 text-amber-400" />
            Max Output Tokens
          </div>
          <div className="mt-2 text-2xl font-extrabold font-mono text-white">
            {maxReplyTokens} <span className="text-xs font-normal text-slate-400">tokens/msg</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Restricts long-winded outputs to keep chat streams readable.
          </div>
        </div>

        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400">
            <MessageSquare className="h-4 w-4 text-cyan-400" />
            Max Chat Length
          </div>
          <div className="mt-2 text-2xl font-extrabold font-mono text-white">
            {maxReplyChars} <span className="text-xs font-normal text-slate-400">chars</span>
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Fits neatly inside single YouTube live chat message bubble.
          </div>
        </div>

        <div className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4 backdrop-blur-sm">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            Guardrails Active
          </div>
          <div className="mt-2 text-2xl font-extrabold font-mono text-emerald-400">
            Level 4
          </div>
          <div className="mt-2 text-xs text-slate-400">
            Zero profanity, anti-flame, streamer alignment & VIP acknowledgment.
          </div>
        </div>
      </div>

      {/* Main Content Split: Simulator & Scenarios */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Interactive Remark Test Generator */}
        <div className="lg:col-span-7 rounded-xl border border-slate-800/80 bg-slate-900/70 p-6 backdrop-blur-sm shadow-xl">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-5">
            <div className="flex items-center gap-2.5">
              <Bot className="h-5 w-5 text-violet-400" />
              <h3 className="text-base font-bold text-white">
                Interactive Co-Host Speech Simulator
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              Live Prompt Generation
            </span>
          </div>

          <form onSubmit={handleGenerateRemark} className="space-y-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                Trigger Event Scenario
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { id: "superchat", label: "Super Chat" },
                  { id: "subscriber", label: "New Member" },
                  { id: "milestone", label: "Milestone" },
                  { id: "chat_highlight", label: "Highlight" },
                ].map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setEventType(s.id)}
                    className={`rounded-lg border px-3 py-2 text-xs font-semibold transition-all ${
                      eventType === s.id
                        ? "border-violet-500 bg-violet-600/20 text-violet-200 shadow-md shadow-violet-600/10"
                        : "border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700 hover:text-slate-200"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                  Viewer / VIP Name
                </label>
                <input
                  type="text"
                  value={authorName}
                  onChange={(e) => setAuthorName(e.target.value)}
                  className="w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                  placeholder="e.g. NeonRider_42"
                  required
                />
              </div>

              {eventType === "superchat" ? (
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                    Super Chat Amount
                  </label>
                  <input
                    type="text"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    className="w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                    placeholder="e.g. $20.00"
                  />
                </div>
              ) : (
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                    Scenario Target
                  </label>
                  <input
                    type="text"
                    disabled
                    value={
                      eventType === "subscriber"
                        ? "Membership Tier: Gold"
                        : eventType === "milestone"
                        ? "100k Subs Celebration"
                        : "Chat Activity Spike"
                    }
                    className="w-full rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2 text-sm text-slate-400"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                Viewer Comment / Stream Context
              </label>
              <textarea
                rows={2}
                value={customMessage}
                onChange={(e) => setCustomMessage(e.target.value)}
                className="w-full rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2 text-sm text-white focus:border-violet-500 focus:outline-none focus:ring-1 focus:ring-violet-500"
                placeholder="Message attached to the event..."
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={isGenerating}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-600/25 transition-all hover:bg-violet-500 disabled:opacity-50"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Synthesizing Co-Host Response...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4" />
                    Test Honney Response
                  </>
                )}
              </button>
            </div>
          </form>

          {/* Generated Result Output */}
          {generatedRemark && (
            <div className="mt-6 rounded-xl border border-violet-500/40 bg-violet-950/20 p-4 transition-all">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Volume2 className="h-4 w-4 text-violet-400" />
                  <span className="text-xs font-bold uppercase tracking-wider text-violet-300">
                    Honney Output
                  </span>
                  <span className="rounded bg-violet-500/20 px-1.5 py-0.5 text-[10px] font-mono text-violet-300">
                    {generatedRemark.length} chars
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleCopyRemark}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-white transition-colors"
                >
                  {copied ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-3.5 text-sm text-slate-100 leading-relaxed font-sans shadow-inner">
                &ldquo;{generatedRemark}&rdquo;
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Policy & Scenarios */}
        <div className="lg:col-span-5 space-y-6">
          {/* Supported Scenarios */}
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-5 backdrop-blur-sm shadow-xl">
            <h4 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <Clock className="h-4 w-4 text-violet-400" />
              Automated Response Triggers
            </h4>
            <div className="space-y-2.5">
              {supportedScenarios.map((sc, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-950/50 px-3 py-2 text-xs"
                >
                  <span className="font-mono text-slate-300 capitalize">
                    {sc.replace(/_/g, " ")}
                  </span>
                  <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                    Enabled
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Strict Safety Safeguards */}
          <div className="rounded-xl border border-slate-800/80 bg-slate-900/70 p-5 backdrop-blur-sm shadow-xl">
            <h4 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              Co-Host Guardrail Invariants
            </h4>
            <div className="space-y-3 text-xs text-slate-300 leading-relaxed">
              <div className="flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-white">Precedence Hierarchy:</span>{" "}
                  Safety and moderation always override co-host banter. If moderation load spikes, co-host pauses automatically.
                </div>
              </div>
              <div className="flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-white">Anti-Runaway Token Cap:</span>{" "}
                  Strict output token limiting guarantees response brevity and zero cost leakage.
                </div>
              </div>
              <div className="flex items-start gap-2.5">
                <AlertCircle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-white">Fail-Safe Silence:</span>{" "}
                  If model generation times out or returns unexpected format, Honney remains silent rather than posting garbled text.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
