import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Production-Safe Server-Side API Proxy for Goddess AI / AI-Modrator.
 *
 * Security Guarantee:
 * - ADMIN_SECRET is injected server-side by the Next.js backend proxy.
 * - The browser client never touches, receives, or stores ADMIN_SECRET in JavaScript or localStorage.
 * - BACKEND_API_URL is environment-driven, preventing hardcoded localhost in Railway production.
 */

function getBackendBaseUrl(): string {
  let url = (
    process.env.BACKEND_API_URL ||
    process.env.INTERNAL_BACKEND_URL ||
    process.env.RAILWAY_BACKEND_URL ||
    "http://127.0.0.1:8000"
  ).trim();

  // Strip trailing slashes
  url = url.replace(/\/+$/, "");

  // Ensure valid HTTP/HTTPS protocol
  if (!url.startsWith("http://") && !url.startsWith("https://")) {
    url = `https://${url}`;
  }

  // Strip trailing /api/v1 so subpath concatenation never doubles it
  url = url.replace(/\/api\/v1\/?$/, "");

  return url;
}

function getAdminSecret(): string {
  // This is deliberately server-only. A NEXT_PUBLIC_ value is compiled into the
  // browser bundle and must never be accepted as privileged authentication.
  const secret = process.env.ADMIN_SECRET;
  if (secret && secret.trim()) {
    return secret.trim();
  }
  if (process.env.NODE_ENV !== "production") {
    return "dev-admin-secret-replace-in-production";
  }
  return "";
}

async function proxyRequest(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const start = Date.now();
  const { path } = await context.params;
  let subpath = Array.isArray(path) ? path.join("/") : (path || "");
  // Clean leading slashes and prevent duplicate api/v1 prefix
  subpath = subpath.replace(/^\/+/, "").replace(/^api\/v1\/?/, "");

  const backendBase = getBackendBaseUrl();
  const targetUrl = `${backendBase}/api/v1/${subpath}${request.nextUrl.search}`;
  const adminSecret = getAdminSecret();
  if (!adminSecret) {
    console.error(`[API Proxy] ADMIN_SECRET is not configured for ${request.method} /api/v1/${subpath}`);
    return NextResponse.json(
      { error: "ServiceMisconfigured", message: "The service is temporarily unavailable." },
      { status: 503 },
    );
  }

  // Allowlist request headers instead of forwarding browser credentials, host
  // metadata, tracing headers, or client-provided admin credentials upstream.
  const forwardHeaders = new Headers();
  for (const header of ["accept", "content-type", "if-none-match"]) {
    const value = request.headers.get(header);
    if (value) forwardHeaders.set(header, value);
  }

  // Inject server-side admin credentials for FastAPI verification
  forwardHeaders.set("X-Admin-Secret", adminSecret);

  // Read request body for mutating HTTP methods
  let bodyBuffer: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    try {
      bodyBuffer = await request.arrayBuffer();
    } catch {
      bodyBuffer = undefined;
    }
  }

  const isSSE = subpath.includes("events/stream") || request.headers.get("accept")?.includes("text/event-stream");
  const controller = new AbortController();
  const timeoutId = isSSE ? undefined : setTimeout(() => controller.abort(), 12000);
  request.signal.addEventListener("abort", () => controller.abort());

  try {
    const backendRes = await fetch(targetUrl, {
      method: request.method,
      headers: forwardHeaders,
      body: bodyBuffer,
      signal: controller.signal,
      cache: "no-store",
    });

    if (timeoutId) clearTimeout(timeoutId);
    const duration = Date.now() - start;

    // Diagnostic logging without leaking secrets or tokens
    if (backendRes.status === 404) {
      console.warn(`[API Proxy 404] ${request.method} /api/v1/${subpath}`);
    } else {
      console.log(`[API Proxy] ${request.method} /api/v1/${subpath} -> ${backendRes.status} (${duration}ms)`);
    }

    const resHeaders = new Headers();
    backendRes.headers.forEach((val, key) => {
      const lower = key.toLowerCase();
      if (["content-type", "cache-control", "etag", "last-modified"].includes(lower)) {
        resHeaders.set(key, val);
      }
    });

    // For Server-Sent Events, stream the response directly without buffering
    const contentType = backendRes.headers.get("content-type") || "";
    if (contentType.includes("text/event-stream")) {
      return new NextResponse(backendRes.body, {
        status: backendRes.status,
        headers: resHeaders,
      });
    }

    const resBody = await backendRes.arrayBuffer();
    return new NextResponse(resBody, {
      status: backendRes.status,
      headers: resHeaders,
    });
  } catch (err: unknown) {
    if (timeoutId) clearTimeout(timeoutId);
    const duration = Date.now() - start;
    const isTimeout = err instanceof Error && err.name === "AbortError";
    const errorMessage = isTimeout
      ? "The service took too long to respond. Please try again."
      : "The service is temporarily unavailable. Please try again.";

    console.error(`[API Proxy Error] ${request.method} /api/v1/${subpath} failed after ${duration}ms:`, isTimeout ? "Timeout" : "Connection Refused");

    return NextResponse.json(
      {
        error: isTimeout ? "GatewayTimeout" : "BackendUnavailable",
        message: errorMessage,
      },
      { status: isTimeout ? 504 : 503 }
    );
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return proxyRequest(request, context);
}
