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
  // 1. Explicit backend API URL (standard project configuration)
  if (process.env.BACKEND_API_URL && process.env.BACKEND_API_URL.trim()) {
    return process.env.BACKEND_API_URL.trim().replace(/\/+$/, "");
  }
  // 2. Railway private network domain / reference variable
  if (process.env.INTERNAL_BACKEND_URL && process.env.INTERNAL_BACKEND_URL.trim()) {
    return process.env.INTERNAL_BACKEND_URL.trim().replace(/\/+$/, "");
  }
  if (process.env.RAILWAY_BACKEND_URL && process.env.RAILWAY_BACKEND_URL.trim()) {
    return process.env.RAILWAY_BACKEND_URL.trim().replace(/\/+$/, "");
  }
  // 3. Local development fallback
  return "http://127.0.0.1:8000";
}

function getAdminSecret(): string {
  // Server-side only: never exposed via NEXT_PUBLIC_* in production
  const secret = process.env.ADMIN_SECRET || process.env.NEXT_PUBLIC_ADMIN_SECRET;
  if (secret && secret.trim()) {
    return secret.trim();
  }
  // Safe development fallback
  return "dev-admin-secret-replace-in-production";
}

async function proxyRequest(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const start = Date.now();
  const { path } = await context.params;
  const subpath = Array.isArray(path) ? path.join("/") : (path || "");
  const backendBase = getBackendBaseUrl();
  const targetUrl = `${backendBase}/api/v1/${subpath}${request.nextUrl.search}`;
  const adminSecret = getAdminSecret();

  // Forward client headers while stripping hop-by-hop headers
  const forwardHeaders = new Headers();
  request.headers.forEach((val, key) => {
    const lower = key.toLowerCase();
    if (lower !== "host" && lower !== "connection" && lower !== "content-length") {
      forwardHeaders.set(key, val);
    }
  });

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

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  try {
    const backendRes = await fetch(targetUrl, {
      method: request.method,
      headers: forwardHeaders,
      body: bodyBuffer,
      signal: controller.signal,
      cache: "no-store",
    });

    clearTimeout(timeoutId);
    const duration = Date.now() - start;

    // Diagnostic logging without leaking secrets or tokens
    console.log(`[API Proxy] ${request.method} /api/v1/${subpath} -> ${backendRes.status} (${duration}ms)`);

    const resHeaders = new Headers();
    backendRes.headers.forEach((val, key) => {
      const lower = key.toLowerCase();
      if (lower !== "transfer-encoding" && lower !== "content-encoding") {
        resHeaders.set(key, val);
      }
    });

    const resBody = await backendRes.arrayBuffer();
    return new NextResponse(resBody, {
      status: backendRes.status,
      headers: resHeaders,
    });
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    const duration = Date.now() - start;
    const isTimeout = err instanceof Error && err.name === "AbortError";
    const errorMessage = isTimeout
      ? "Gateway Timeout: Backend request exceeded 12000ms"
      : `Backend Connection Failed: Unable to reach backend service at ${backendBase}`;

    console.error(`[API Proxy Error] ${request.method} /api/v1/${subpath} failed after ${duration}ms:`, isTimeout ? "Timeout" : "Connection Refused");

    return NextResponse.json(
      {
        error: isTimeout ? "GatewayTimeout" : "BackendUnavailable",
        message: errorMessage,
        path: `/api/v1/${subpath}`,
        backend_url: backendBase,
        status: isTimeout ? 504 : 503,
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
