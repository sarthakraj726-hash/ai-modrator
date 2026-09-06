/**
 * Production API Client for Goddess AI / AI-Modrator Dashboard.
 *
 * Security & Connectivity Architecture:
 * - All requests are made to same-origin `/api/v1/*`.
 * - The server-side Next.js route handler proxies requests to the FastAPI backend,
 *   injecting the server-side ADMIN_SECRET automatically.
 * - Client-side JavaScript NEVER accesses, stores, or transmits ADMIN_SECRET.
 * - Provides structured diagnostics and handles loading, error, unauthorized, and empty states.
 */

export interface KeyItem {
  key_index: number;
  slot?: string;
  masked_key: string;
  requests_made: number;
  quota_units: number;
  status: string;
  in_cooldown: boolean;
  cooldown_until: string | null;
  last_used_at?: string | null;
}

export interface QuotaData {
  budget: number;
  consumed: number;
  remaining: number;
  quota_remaining?: number;
  percent_used: number;
  threshold_status: string;
}

export interface StreamItem {
  id: string;
  session_id: string;
  creator_id: string;
  channel_name: string;
  youtube_video_id: string;
  youtube_live_chat_id: string;
  status: string;
  is_worker_alive?: boolean;
  messages_processed?: number;
  duration_minutes?: number;
  duration_seconds: number;
  started_at: string | null;
  ended_at?: string | null;
  last_activity_at?: string | null;
}

export interface ReviewItem {
  id: string;
  creator_id: string;
  stream_session_id?: string;
  viewer_name?: string;
  author_display_name: string;
  flagged_content?: string;
  message_text: string;
  flagged_reason?: string;
  reason: string;
  confidence_score?: number;
  confidence: number;
  severity: number;
  recommended_action: string;
  status: string;
  created_at: string;
}

export interface IncidentItem {
  id?: string;
  incident_id: string;
  severity: string;
  service: string;
  summary: string;
  status: string;
  root_cause?: string | null;
  resolution?: string | null;
  actions_taken?: string[];
  detected_at: string;
  resolved_at: string | null;
}

export interface OverviewData {
  overall_status: string;
  active_streams: number;
  total_creators: number;
  pending_moderation_reviews: number;
  open_incidents: number;
  active_websub_subscriptions: number;
  quota: QuotaData;
  subsystems?: Record<string, { status: string; latency_ms?: number }>;
  ledger_balanced?: boolean;
  uptime_seconds?: number;
  environment?: string;
  timestamp?: string;
}

export type EndpointState = "idle" | "loading" | "success" | "empty" | "error" | "unauthorized";

export interface EndpointDiagnostic {
  name: string;
  state: EndpointState;
  httpStatus?: number;
  error?: string;
}

export interface DashboardFetchResult {
  overview: OverviewData | null;
  streams: StreamItem[];
  quota: QuotaData | null;
  keys: KeyItem[];
  reviews: ReviewItem[];
  incidents: IncidentItem[];
  diagnostics: Record<string, EndpointDiagnostic>;
}

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

async function safeFetchJson<T>(url: string, signal?: AbortSignal): Promise<{ data: T | null; diagnostic: EndpointDiagnostic }> {
  const name = url.split("?")[0].replace("/api/v1/dashboard/", "");
  try {
    const res = await fetch(url, {
      headers: { "Accept": "application/json" },
      signal,
      cache: "no-store",
    });

    if (res.status === 401 || res.status === 403) {
      return {
        data: null,
        diagnostic: {
          name,
          state: "unauthorized",
          httpStatus: res.status,
          error: "Admin authentication required. Server credentials rejected.",
        },
      };
    }

    if (!res.ok) {
      let errMsg = `HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson?.message) errMsg = errJson.message;
        else if (errJson?.detail && errJson.detail !== "Not Found") errMsg = errJson.detail;
        else if (res.status === 404) errMsg = `Endpoint not found (HTTP 404) on backend API`;
      } catch {
        if (res.status === 404) errMsg = `Endpoint not found (HTTP 404) on backend API`;
      }
      return {
        data: null,
        diagnostic: {
          name,
          state: "error",
          httpStatus: res.status,
          error: errMsg,
        },
      };
    }

    const json = await res.json();
    return {
      data: json as T,
      diagnostic: {
        name,
        state: "success",
        httpStatus: res.status,
      },
    };
  } catch (err: unknown) {
    const isTimeout = err instanceof Error && err.name === "AbortError";
    return {
      data: null,
      diagnostic: {
        name,
        state: "error",
        error: isTimeout ? "Request timed out (8s)" : "Network/backend connection failed",
      },
    };
  }
}

export async function fetchAllDashboardData(signal?: AbortSignal): Promise<DashboardFetchResult> {
  const [ovRes, stRes, qRes, kRes, mRes, iRes] = await Promise.all([
    safeFetchJson<OverviewData>("/api/v1/dashboard/overview", signal),
    safeFetchJson<unknown>("/api/v1/dashboard/streams", signal),
    safeFetchJson<QuotaData>("/api/v1/dashboard/quota", signal),
    safeFetchJson<KeyItem[]>("/api/v1/dashboard/youtube-keys", signal),
    safeFetchJson<unknown>("/api/v1/dashboard/moderation?status_filter=PENDING", signal),
    safeFetchJson<IncidentItem[]>("/api/v1/dashboard/incidents", signal),
  ]);

  // Normalize streams: ensure session_id and duration_seconds exist
  const rawStreams = Array.isArray(stRes.data) ? stRes.data.filter(isRecord) : [];
  const normalizedStreams: StreamItem[] = rawStreams.map((s) => {
    const durationMinutes = asNumber(s.duration_minutes);
    const sessionId = asString(s.session_id, asString(s.id));
    return {
      id: asString(s.id, sessionId), session_id: sessionId,
      creator_id: asString(s.creator_id), channel_name: asString(s.channel_name, "Live channel"),
      youtube_video_id: asString(s.youtube_video_id), youtube_live_chat_id: asString(s.youtube_live_chat_id),
      status: asString(s.status, "UNKNOWN"), is_worker_alive: s.is_worker_alive === true,
      messages_processed: asNumber(s.messages_processed), duration_minutes: durationMinutes,
      duration_seconds: asNumber(s.duration_seconds, Math.round(durationMinutes * 60)),
      started_at: typeof s.started_at === "string" ? s.started_at : null,
      ended_at: typeof s.ended_at === "string" ? s.ended_at : null,
      last_activity_at: asString(s.last_activity_at, typeof s.started_at === "string" ? s.started_at : "") || null,
    };
  });

  // Normalize moderation reviews: support both direct array or `{ items: [...] }`
  let rawReviews: UnknownRecord[] = [];
  if (Array.isArray(mRes.data)) {
    rawReviews = mRes.data.filter(isRecord);
  } else if (isRecord(mRes.data) && Array.isArray(mRes.data.items)) {
    rawReviews = mRes.data.items.filter(isRecord);
  }

  const normalizedReviews: ReviewItem[] = rawReviews.map((r) => ({
    id: asString(r.id), creator_id: asString(r.creator_id), stream_session_id: asString(r.stream_session_id) || undefined,
    viewer_name: asString(r.viewer_name) || undefined,
    author_display_name: asString(r.author_display_name, asString(r.viewer_name, "Viewer")),
    flagged_content: asString(r.flagged_content) || undefined,
    message_text: asString(r.message_text, asString(r.flagged_content)),
    flagged_reason: asString(r.flagged_reason) || undefined,
    reason: asString(r.reason, asString(r.flagged_reason, "Automated violation")),
    confidence_score: typeof r.confidence_score === "number" ? r.confidence_score : undefined,
    confidence: asNumber(r.confidence, typeof r.confidence_score === "number" ? Math.round(r.confidence_score * 100) : 90),
    severity: asNumber(r.severity, typeof r.confidence_score === "number" ? Math.round(r.confidence_score * 100) : 50),
    recommended_action: asString(r.recommended_action, "TIMEOUT"), status: asString(r.status, "PENDING"),
    created_at: asString(r.created_at, new Date().toISOString()),
  }));

  // Normalize quota
  let normalizedQuota = qRes.data;
  if (!normalizedQuota && ovRes.data?.quota) {
    normalizedQuota = ovRes.data.quota;
  }

  return {
    overview: ovRes.data,
    streams: normalizedStreams,
    quota: normalizedQuota,
    keys: Array.isArray(kRes.data) ? kRes.data : [],
    reviews: normalizedReviews,
    incidents: Array.isArray(iRes.data) ? iRes.data : [],
    diagnostics: {
      overview: ovRes.diagnostic,
      streams: stRes.diagnostic,
      quota: qRes.diagnostic,
      keys: kRes.diagnostic,
      moderation: mRes.diagnostic,
      incidents: iRes.diagnostic,
    },
  };
}

export async function sendStreamControlAction(streamId: string, action: string): Promise<boolean> {
  const res = await fetch(`/api/v1/dashboard/streams/${streamId}/control`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  return res.ok;
}

export async function sendManualConnect(urlOrVideoId: string): Promise<{ status: string; stream_session_id: string }> {
  const res = await fetch("/api/v1/dashboard/streams/manual-connect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url_or_video_id: urlOrVideoId }),
  });
  if (!res.ok) {
    let errMessage = `Connection failed (HTTP ${res.status})`;
    try {
      const errData = await res.json();
      if (errData?.detail) errMessage = errData.detail;
      else if (errData?.message) errMessage = errData.message;
    } catch {
      // Keep default error message
    }
    throw new Error(errMessage);
  }
  const payload: unknown = await res.json();
  if (!isRecord(payload) || typeof payload.status !== "string" || typeof payload.stream_session_id !== "string") {
    throw new Error("The service returned an invalid connection response.");
  }
  return { status: payload.status, stream_session_id: payload.stream_session_id };
}

export async function sendResetKeyCooldown(keyIndex: number): Promise<boolean> {
  const res = await fetch(`/api/v1/dashboard/youtube-keys/${keyIndex}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return res.ok;
}

export async function sendResolveReview(reviewId: string, action: string): Promise<boolean> {
  const res = await fetch(`/api/v1/dashboard/moderation/reviews/${reviewId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  return res.ok;
}

export async function sendResolveIncident(incidentId: string): Promise<boolean> {
  const res = await fetch(`/api/v1/dashboard/incidents/${incidentId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: "RESOLVED", resolution: "Resolved via Control Center" }),
  });
  return res.ok;
}
