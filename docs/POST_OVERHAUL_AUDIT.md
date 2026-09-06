# Post-overhaul audit

## Executive summary

The control center was rebuilt around a calm, token-based operations interface and its client contract was made explicit. The dashboard now establishes an SSE connection to the existing `/api/v1/dashboard/events/stream` feed, reconnects with capped exponential backoff, and only falls back to a 60-second refresh while the feed is unavailable. The Next.js proxy no longer accepts public environment variables as administrator credentials and does not disclose the upstream endpoint to browsers.

## Verified bugs found

| Severity | File | Problem | Evidence | Fix |
| --- | --- | --- | --- | --- |
| High | `dashboard/src/app/api/v1/[...path]/route.ts` | `NEXT_PUBLIC_ADMIN_SECRET` was accepted as an administrator secret. Next public variables are browser-bundled, so this could turn a public value into privileged authentication. | Source inspection. | Server proxy accepts only `ADMIN_SECRET`; a missing secret produces a generic 503. |
| Medium | `dashboard/src/app/api/v1/[...path]/route.ts` | Proxy failure JSON exposed `backend_url`; 404 logging also printed the complete upstream target. | Source inspection. | Responses and logs retain only the sanitized local request path and a generic user-safe message. |
| Medium | `dashboard/src/app/page.tsx` | Dashboard used unconditional ten-second polling even though the backend exposes and tests a replay-capable SSE feed. | `app/api/routes/dashboard.py`, `tests/integration/test_dashboard_sse.py`, and old page source. | SSE is primary; fallback refresh occurs only while SSE is not live. |
| Medium | `dashboard/src/lib/api.ts` | Dashboard normalization used `any` for server response payloads and manual connect returned `any`. | TypeScript source inspection. | Runtime shape checks and explicit result types now normalize unknown payloads safely. |

## Security findings

The proxy has an allowlist for forwarded browser headers, injects the admin credential only server-side, and filters response headers to a small safe set. Error responses do not contain a backend address or credentials. A source scan after the change found no `NEXT_PUBLIC_ADMIN_SECRET`, `backend_url`, development admin fallback, or prior upstream connection-error text under `dashboard/src`.

## Frontend changes

- Introduced semantic visual tokens, solid information surfaces, restrained glass elevation, consistent focus treatment, and reduced-motion handling.
- Reframed the dashboard as an operations overview with concise health, stream, review, and quota summaries; diagnostics are progressive disclosure.
- Redesigned the header around brand, overall status, and a single primary action.
- Improved the stream-connection dialog with labels, Escape support, initial focus, overlay close behavior, validation, and user-safe errors.
- Centralized response normalization and kept detailed network information out of the primary UI.

## Tests executed

| Command | Result |
| --- | --- |
| `npm install --cache .npm-cache --no-audit --no-fund` | Passed (npm reported optional native scripts pending approval; they were not approved or run). |
| `dashboard/node_modules/.bin/tsc.cmd --noEmit` | Passed after correcting one nullable prop mismatch. |
| `npm run lint` | Passed: `✔ No ESLint warnings or errors`. |
| `npm run build` | Passed: Next.js compiled, validated types, generated all 4 static pages, and wrote `.next/BUILD_ID`. |
| `git diff --check` | Passed (line-ending warnings only). |
| `python -m pytest tests/security/test_production_security.py tests/integration/test_dashboard_sse.py -q` | NOT VERIFIED — REQUIRES ENVIRONMENT / CREDENTIALS: neither `python` nor `py` is available on PATH. |

## Remaining risks

- NOT VERIFIED — REQUIRES ENVIRONMENT / CREDENTIALS: Python 3.12 and installed backend dependencies are unavailable, so the full Python, integration, migration, and external-service test suites could not run here.
- NOT VERIFIED — REQUIRES ENVIRONMENT / CREDENTIALS: a live backend with an `ADMIN_SECRET`, database, Redis, YouTube credentials, and OAuth credentials is required to exercise real mutations and end-to-end SSE delivery.
- The SSE client intentionally refreshes canonical data after events rather than interpreting arbitrary event payloads. This prevents stale/unknown event schemas from corrupting the dashboard, at the cost of one read refresh per received dashboard event.

## Files changed

### Frontend

- `dashboard/src/app/globals.css`
- `dashboard/src/app/page.tsx`
- `dashboard/src/components/Header.tsx`
- `dashboard/src/components/ManualConnectModal.tsx`
- `dashboard/src/components/StreamGrid.tsx`
- `dashboard/src/lib/api.ts`

### Infrastructure / security

- `dashboard/src/app/api/v1/[...path]/route.ts`
- `.gitignore`

### Documentation

- `docs/POST_OVERHAUL_AUDIT.md`
