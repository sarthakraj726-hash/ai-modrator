# Incident Runbook: Security Incident or Secret/Token Exposure

## Severity
- **CRITICAL**: Immediate revocation and credential rotation required.

## Invariants
- Secrets, tokens, and raw keys must NEVER appear in git history, logs, or API responses.
- All secrets are redacted via masking filters (`mask_secret()`, `mask_key()`).

## Symptoms
- Detection of unauthorized admin endpoint invocation (repeated 401/403 or unexpected 200).
- External alert regarding leaked API token or credentials.

## Immediate Mitigation Steps
1. **Rotate Exposed Secrets Immediately**:
   - If `ADMIN_SECRET` exposed:
     - Generate new 64-char hex secret: `openssl rand -hex 32`.
     - Update `ADMIN_SECRET` in Railway project variables.
   - If YouTube API Key exposed:
     - Delete key in Google Cloud Console -> APIs & Services -> Credentials.
     - Generate replacement key and update Railway environment variables.
   - If OpenRouter API Key exposed:
     - Delete key on OpenRouter dashboard and generate new key.
   - If WebSub Secret exposed:
     - Update `WEBSUB_SECRET` in Railway variables and re-subscribe all creator topics.
2. **Review Access Logs**:
   - Inspect Railway HTTP access logs for unusual IP addresses or user agents targeting `/api/v1/dashboard/` or `/api/v1/admin/`.
3. **Verify Git Tree Integrity**:
   - Run automated secret scan locally:
     ```bash
     python -c "import re; ..."
     ```
   - If committed to git history, use `git filter-repo` or BFG repo cleaner to expunge from git history and force-push.
