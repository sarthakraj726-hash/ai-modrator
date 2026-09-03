# Incident Runbook: OpenRouter AI Gateway Outage or Latency Spike

## Severity
- **HIGH** / **DEGRADED**: Ingestion and deterministic moderation continue without interruption.

## Architectural Guarantees
- An OpenRouter failure MUST NOT stop live chat ingestion or local moderation rules (scams, slurs, regex threats).
- The system automatically triggers the Tier Fallback chain (`PRIMARY` -> `FALLBACK` -> `LOCAL_DETERMINISTIC`).

## Symptoms
- Discord alert: `[WARNING] OpenRouter AI latency spike (>3000ms) or 5xx provider error`.
- Metric `fallback_rate_percent` elevates on `/api/v1/dashboard/ai`.
- Persona co-host replies temporarily pause or defer to pre-computed fallback responses.

## Immediate Mitigation Steps
1. **Inspect OpenRouter Model Status**:
   - Check OpenRouter status page for upstream provider degradations (e.g. Anthropic, Google Vertex, OpenAI).
2. **Switch Active Model Tier**:
   - Update `OPENROUTER_PRIMARY_MODEL` in Railway environment variables to a resilient fallback (e.g. `google/gemini-flash-1.5` or `meta-llama/llama-3.3-70b-instruct`).
3. **Verify Local Rule Engine Engagement**:
   - Confirm in Control Center that spam and malicious links continue to be automatically blocked locally by Layer 0/1 without AI dependencies.
4. **Tune Request Coalescer**:
   - Verify batching threshold in `AIRequestCoalescer` to prevent rate limit saturation.

## Post-Recovery Verification
- Monitor average latency on `/api/v1/dashboard/ai` until it stabilizes below 800ms.
