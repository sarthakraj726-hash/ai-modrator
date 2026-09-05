"""Embedded Web Control Center and Root Routing for Goddess AI / AI-Modrator.

Serves an interactive single-page Cyberpunk Control Center web application
at GET / and GET /dashboard for browser visitors, while returning structured
JSON metadata for programmatic/API clients.
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

from app.core.config import get_settings

router = APIRouter(tags=["Web Interface"])


def render_control_center_html(environment: str, version: str) -> str:
    """Generate the self-contained Goddess AI Control Center HTML application."""
    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Goddess AI | Broadcast Operations Command Center</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #08090f;
      --surface: #0f111a;
      --surface-raised: #151824;
      --border: #232738;
      --text: #e2e8f0;
      --text-muted: #64748b;
      --purple: #a855f7;
      --cyan: #06b6d4;
      --emerald: #10b981;
      --rose: #f43f5e;
      --amber: #f59e0b;
    }}
    body {{
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.5;
      min-height: 100vh;
      padding-bottom: 3rem;
    }}
    code, pre, .font-mono {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }}
    .container {{ max-width: 80rem; margin: 0 auto; padding: 1.5rem; }}
    /* Header */
    header {{
      background: rgba(15, 17, 26, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 50;
      padding: 1rem 1.5rem;
    }}
    .header-inner {{
      max-width: 80rem;
      margin: 0 auto;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }}
    .brand {{ display: flex; align-items: center; gap: 0.75rem; }}
    .brand-icon {{
      width: 2.5rem;
      height: 2.5rem;
      border-radius: 0.5rem;
      background: linear-gradient(135deg, #9333ea, #06b6d4);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.25rem;
    }}
    .brand-title {{
      font-size: 1.25rem;
      font-weight: 800;
      letter-spacing: -0.025em;
      background: linear-gradient(90deg, #c084fc, #67e8f9, #34d399);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .brand-badge {{
      font-size: 0.7rem;
      padding: 0.15rem 0.5rem;
      border-radius: 0.25rem;
      background: rgba(168, 85, 247, 0.2);
      color: #d8b4fe;
      border: 1px solid rgba(168, 85, 247, 0.4);
      font-family: monospace;
      font-weight: 600;
      margin-left: 0.5rem;
    }}
    .brand-sub {{ font-size: 0.75rem; color: var(--text-muted); }}
    /* Subsystems & Auth */
    .header-actions {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.75rem;
      font-family: monospace;
      padding: 0.25rem 0.6rem;
      border-radius: 0.375rem;
      border: 1px solid var(--border);
      background: var(--surface);
    }}
    .badge-ok {{ background: rgba(16, 185, 129, 0.1); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }}
    .badge-warn {{ background: rgba(245, 158, 11, 0.1); color: #fbbf24; border-color: rgba(245, 158, 11, 0.3); }}
    .badge-danger {{ background: rgba(244, 63, 94, 0.1); color: #fb7185; border-color: rgba(244, 63, 94, 0.3); }}
    .btn {{
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      font-size: 0.75rem;
      font-weight: 600;
      padding: 0.4rem 0.8rem;
      border-radius: 0.375rem;
      border: 1px solid transparent;
      transition: all 0.2s;
    }}
    .btn-primary {{
      background: linear-gradient(90deg, #9333ea, #06b6d4);
      color: white;
    }}
    .btn-primary:hover {{ opacity: 0.9; transform: translateY(-1px); }}
    .btn-secondary {{
      background: var(--surface-raised);
      color: var(--text);
      border-color: var(--border);
    }}
    .btn-secondary:hover {{ background: var(--border); }}
    .auth-box {{
      display: flex;
      align-items: center;
      gap: 0.35rem;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      padding: 0.2rem 0.4rem;
      border-radius: 0.375rem;
    }}
    .auth-input {{
      background: transparent;
      border: none;
      color: var(--text);
      font-size: 0.75rem;
      font-family: monospace;
      outline: none;
      width: 8rem;
    }}
    /* Panels & Grids */
    .panel {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1.25rem;
      position: relative;
    }}
    .panel-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1rem;
    }}
    .panel-title {{
      font-size: 0.85rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #cbd5e1;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
    .grid-2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(24rem, 1fr)); gap: 1.5rem; margin-bottom: 1.5rem; }}
    /* Metric Card */
    .metric-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 0.6rem;
      padding: 1rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .metric-label {{ font-size: 0.7rem; font-family: monospace; color: var(--text-muted); text-transform: uppercase; }}
    .metric-val {{ font-size: 1.4rem; font-weight: 700; font-family: monospace; margin-top: 0.2rem; }}
    /* Banner */
    .banner {{
      padding: 0.75rem 1rem;
      border-radius: 0.5rem;
      margin-bottom: 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.75rem;
      font-family: monospace;
    }}
    .banner-warn {{
      background: rgba(245, 158, 11, 0.1);
      border: 1px solid rgba(245, 158, 11, 0.3);
      color: #fde68a;
    }}
    .banner-danger {{
      background: rgba(244, 63, 94, 0.1);
      border: 1px solid rgba(244, 63, 94, 0.3);
      color: #fecdd3;
    }}
    /* Diagnostics bar */
    .diag-bar {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 0.5rem;
      padding: 0.6rem 1rem;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      margin-bottom: 1.5rem;
      font-size: 0.75rem;
      font-family: monospace;
    }}
    .diag-pills {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; }}
    /* Table / Item styles */
    .item-card {{
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: 0.5rem;
      padding: 0.75rem 1rem;
      margin-bottom: 0.5rem;
      font-size: 0.8rem;
    }}
    .progress-bar {{
      width: 100%;
      height: 0.6rem;
      background: #090a10;
      border-radius: 999px;
      overflow: hidden;
      border: 1px solid var(--border);
      margin: 0.5rem 0;
    }}
    .progress-fill {{
      height: 100%;
      background: linear-gradient(90deg, #9333ea, #06b6d4);
      transition: width 0.4s ease;
    }}
    /* Modal */
    .modal-overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      z-index: 100;
      align-items: center;
      justify-content: center;
    }}
    .modal {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 0.75rem;
      padding: 1.5rem;
      max-width: 28rem;
      width: 90%;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
    }}
    .input-field {{
      width: 100%;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.5rem 0.75rem;
      border-radius: 0.375rem;
      font-size: 0.85rem;
      margin-top: 0.35rem;
      margin-bottom: 1rem;
      outline: none;
    }}
  </style>
</head>
<body>
  <!-- Header -->
  <header>
    <div class="header-inner">
      <div class="brand">
        <div class="brand-icon">📻</div>
        <div>
          <div style="display: flex; align-items: center;">
            <span class="brand-title">GODDESS AI</span>
            <span class="brand-badge">CONTROL CENTER</span>
          </div>
          <div class="brand-sub">Honney AI Co-Host • 7-Stream Multi-Channel Operations Engine • v{version} ({environment})</div>
        </div>
      </div>

      <div class="header-actions">
        <span id="subsystem-db" class="badge">DB: ...</span>
        <span id="subsystem-redis" class="badge">REDIS: ...</span>
        <span id="subsystem-yt" class="badge">YOUTUBE: ...</span>
        <span id="subsystem-workers" class="badge">WORKERS: ...</span>

        <div class="auth-box">
          <span style="font-size: 0.7rem; color: var(--text-muted); font-family: monospace;">🔑</span>
          <input type="password" id="admin-secret-input" class="auth-input" placeholder="ADMIN_SECRET" />
          <button class="btn btn-secondary" onclick="saveAdminSecret()" style="padding: 0.2rem 0.5rem; font-size: 0.7rem;">Set</button>
        </div>

        <button class="btn btn-secondary" onclick="openAddChannelModal()" style="border-color: rgba(168, 85, 247, 0.4); color: #d8b4fe;">+ Add Channel</button>
        <button class="btn btn-primary" onclick="openConnectModal()">+ Connect Stream</button>
      </div>
    </div>
  </header>

  <div class="container">
    <!-- Auth Status Banner -->
    <div id="auth-banner" class="banner banner-warn" style="display: none;">
      <span>⚠️ Admin authentication required to inspect full operational telemetry. Please enter your ADMIN_SECRET above.</span>
    </div>

    <!-- 4 Top Metric Cards -->
    <div class="grid-4">
      <div class="metric-card">
        <div>
          <div class="metric-label">Active Streams</div>
          <div id="metric-streams" class="metric-val" style="color: #f43f5e;">-- <span style="font-size: 0.75rem; color: var(--text-muted);">/ 7 max</span></div>
        </div>
        <div style="font-size: 1.5rem;">📡</div>
      </div>

      <div class="metric-card">
        <div>
          <div class="metric-label">Quota Remaining</div>
          <div id="metric-quota" class="metric-val" style="color: #06b6d4;">-- <span style="font-size: 0.75rem; color: var(--text-muted);">pts</span></div>
        </div>
        <div style="font-size: 1.5rem;">⚡</div>
      </div>

      <div class="metric-card">
        <div>
          <div class="metric-label">HITL Pending</div>
          <div id="metric-hitl" class="metric-val" style="color: #c084fc;">--</div>
        </div>
        <div style="font-size: 1.5rem;">🛡️</div>
      </div>

      <div class="metric-card">
        <div>
          <div class="metric-label">Ledger Integrity</div>
          <div id="metric-ledger" class="metric-val" style="color: #10b981;">BALANCED</div>
        </div>
        <div style="font-size: 1.5rem;">🪙</div>
      </div>
    </div>

    <!-- API Diagnostics Bar -->
    <div class="diag-bar">
      <div class="diag-pills">
        <span style="color: var(--text-muted); font-weight: 700;">API STATUS:</span>
        <span id="diag-overview" class="badge">overview: ...</span>
        <span id="diag-streams" class="badge">streams: ...</span>
        <span id="diag-channels" class="badge">channels: ...</span>
        <span id="diag-quota" class="badge">quota: ...</span>
        <span id="diag-keys" class="badge">keys: ...</span>
        <span id="diag-moderation" class="badge">moderation: ...</span>
        <span id="diag-incidents" class="badge">incidents: ...</span>
      </div>
      <div>
        <span id="last-updated" style="color: var(--text-muted);">Connecting...</span>
        <button class="btn btn-secondary" onclick="refreshDashboard()" style="margin-left: 0.5rem; padding: 0.2rem 0.5rem;">↻ Refresh</button>
      </div>
    </div>

    <!-- Section: Active Live Stream Grid -->
    <div class="panel" style="margin-bottom: 1.5rem;">
      <div class="panel-header">
        <div class="panel-title"><span style="width: 8px; height: 8px; border-radius: 50%; background: var(--rose);"></span> Active Live Stream Grid (Up to 7 Concurrent Sessions)</div>
        <span id="active-stream-badge" class="badge badge-ok">0 SESSIONS</span>
      </div>
      <div id="streams-container">
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem;">
          Querying live streams telemetry...
        </div>
      </div>
    </div>

    <!-- Section: Monitored YouTube Channels & Auto-Join -->
    <div class="panel" style="margin-bottom: 1.5rem;">
      <div class="panel-header">
        <div class="panel-title"><span style="width: 8px; height: 8px; border-radius: 50%; background: var(--purple);"></span> Monitored YouTube Channels & Auto-Join</div>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <span id="monitored-channel-badge" class="badge badge-ok">0 MONITORED</span>
          <button class="btn btn-secondary" onclick="openAddChannelModal()" style="padding: 0.2rem 0.5rem; font-size: 0.75rem;">+ Add Channel</button>
        </div>
      </div>
      <div id="monitored-channels-container">
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem;">
          Querying monitored channels...
        </div>
      </div>
    </div>

    <!-- 2-Column Grid: Quota & Incidents -->
    <div class="grid-2">
      <!-- Quota Governance -->
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">⚡ YouTube API Quota Governance</div>
          <span id="quota-budget-badge" class="badge">BUDGET: 4000 UNITS</span>
        </div>
        <div>
          <div style="display: flex; justify-content: space-between; font-size: 0.75rem; font-family: monospace;">
            <span id="quota-consumed-txt">Consumed: 0 units</span>
            <span id="quota-remaining-txt" style="color: #34d399;">Remaining: 4000 (100%)</span>
          </div>
          <div class="progress-bar">
            <div id="quota-progress-fill" class="progress-fill" style="width: 0%;"></div>
          </div>
          <div style="margin-top: 1rem; border-top: 1px solid var(--border); padding-top: 0.75rem;">
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem; font-weight: 600;">MULTI-KEY POOL</div>
            <div id="keys-container" style="font-size: 0.75rem; font-family: monospace;">
              Loading keys...
            </div>
          </div>
        </div>
      </div>

      <!-- Incidents & Outages -->
      <div class="panel">
        <div class="panel-header">
          <div class="panel-title">🚨 Operational Incidents & Outages</div>
          <span id="incidents-badge" class="badge badge-ok">0 ACTIVE</span>
        </div>
        <div id="incidents-container">
          <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem;">
            Querying active system incidents...
          </div>
        </div>
      </div>
    </div>

    <!-- Section: HITL Moderation Queue -->
    <div class="panel">
      <div class="panel-header">
        <div class="panel-title">🛡️ HITL Moderation & Co-Host Queue</div>
        <span id="moderation-badge" class="badge">0 PENDING</span>
      </div>
      <div id="moderation-container">
        <div style="text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.85rem;">
          Querying pending moderation reviews...
        </div>
      </div>
    </div>
  </div>

  <!-- Connect Stream Modal -->
  <div id="connect-modal" class="modal-overlay">
    <div class="modal">
      <h3 style="margin-bottom: 0.5rem; font-size: 1rem;">Connect Live Stream</h3>
      <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 1rem;">Enter a YouTube Live Stream URL or Video ID to allocate an isolated worker.</p>
      <div id="connect-error-box" class="banner banner-danger" style="display: none; margin-bottom: 0.75rem; padding: 0.5rem; word-break: break-word;"></div>
      <label style="font-size: 0.75rem; font-family: monospace;">YouTube Live URL or Video ID:</label>
      <input type="text" id="modal-stream-url" class="input-field" placeholder="https://www.youtube.com/watch?v=..." />
      <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
        <button class="btn btn-secondary" onclick="closeConnectModal()">Cancel</button>
        <button class="btn btn-primary" id="btn-submit-connect" onclick="submitManualConnect()">Connect Stream</button>
      </div>
    </div>
  </div>

  <!-- Add Monitored Channel Modal -->
  <div id="add-channel-modal" class="modal-overlay">
    <div class="modal">
      <h3 style="margin-bottom: 0.5rem; font-size: 1rem;">Add Monitored YouTube Channel</h3>
      <p style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 1rem;">
        Add a YouTube Channel (UC... ID, @handle, or URL) to automatically detect and auto-join live broadcasts.
      </p>
      <div id="add-channel-error" class="banner banner-danger" style="display: none; margin-bottom: 0.75rem; padding: 0.5rem; word-break: break-word;"></div>
      <label style="font-size: 0.75rem; font-family: monospace;">Channel ID (UC...), @Handle, or Channel URL:</label>
      <input type="text" id="modal-channel-identifier" class="input-field" placeholder="UC... or @CreatorHandle" />
      <label style="font-size: 0.75rem; font-family: monospace;">Display Label (Optional):</label>
      <input type="text" id="modal-channel-label" class="input-field" placeholder="e.g. Main Gaming Channel" />
      <div style="margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;">
        <input type="checkbox" id="modal-channel-autojoin" checked style="accent-color: #a855f7;" />
        <label for="modal-channel-autojoin" style="font-size: 0.75rem; cursor: pointer;">Automatically join stream when live broadcast detected</label>
      </div>
      <div style="display: flex; justify-content: flex-end; gap: 0.5rem;">
        <button class="btn btn-secondary" onclick="closeAddChannelModal()">Cancel</button>
        <button class="btn btn-primary" id="btn-submit-channel" onclick="submitAddChannel()">Verify & Add</button>
      </div>
    </div>
  </div>

  <script>
    function getAdminSecret() {{
      return sessionStorage.getItem("admin_secret") || "";
    }}

    function saveAdminSecret() {{
      const val = document.getElementById("admin-secret-input").value.trim();
      if (val) {{
        sessionStorage.setItem("admin_secret", val);
        document.getElementById("auth-banner").style.display = "none";
        refreshDashboard();
      }} else {{
        sessionStorage.removeItem("admin_secret");
      }}
    }}

    function getHeaders() {{
      const headers = {{ "Accept": "application/json" }};
      const secret = getAdminSecret();
      if (secret) headers["X-Admin-Secret"] = secret;
      return headers;
    }}

    function openConnectModal() {{
      document.getElementById("connect-error-box").style.display = "none";
      document.getElementById("connect-modal").style.display = "flex";
    }}
    function closeConnectModal() {{
      document.getElementById("connect-modal").style.display = "none";
    }}

    function openAddChannelModal() {{
      document.getElementById("add-channel-error").style.display = "none";
      document.getElementById("modal-channel-identifier").value = "";
      document.getElementById("modal-channel-label").value = "";
      document.getElementById("modal-channel-autojoin").checked = true;
      document.getElementById("add-channel-modal").style.display = "flex";
    }}
    function closeAddChannelModal() {{
      document.getElementById("add-channel-modal").style.display = "none";
    }}

    async function submitAddChannel() {{
      const identifier = document.getElementById("modal-channel-identifier").value.trim();
      const label = document.getElementById("modal-channel-label").value.trim();
      const autoJoin = document.getElementById("modal-channel-autojoin").checked;
      const errBox = document.getElementById("add-channel-error");
      const btn = document.getElementById("btn-submit-channel");
      errBox.style.display = "none";

      if (!identifier) {{
        errBox.textContent = "Please enter a Channel ID (UC...), @Handle, or Channel URL.";
        errBox.style.display = "block";
        return;
      }}

      btn.disabled = true;
      btn.textContent = "Verifying...";
      try {{
        const res = await fetch("/api/v1/dashboard/monitored-channels", {{
          method: "POST",
          headers: Object.assign({{ "Content-Type": "application/json" }}, getHeaders()),
          body: JSON.stringify({{
            identifier: identifier,
            display_label: label || null,
            auto_join_enabled: autoJoin
          }})
        }});
        if (!res.ok) {{
          let errMsg = "Verification failed (HTTP " + res.status + ")";
          try {{
            const err = await res.json();
            errMsg = err.detail || (err.error && err.error.message) || errMsg;
          }} catch (_) {{}}
          errBox.textContent = errMsg;
          errBox.style.display = "block";
        }} else {{
          closeAddChannelModal();
          refreshDashboard();
        }}
      }} catch (e) {{
        errBox.textContent = "Network error: " + e.message;
        errBox.style.display = "block";
      }} finally {{
        btn.disabled = false;
        btn.textContent = "Verify & Add";
      }}
    }}

    async function toggleAutoJoin(channelId, currentVal) {{
      try {{
        const res = await fetch(`/api/v1/dashboard/monitored-channels/${{channelId}}`, {{
          method: "PATCH",
          headers: Object.assign({{ "Content-Type": "application/json" }}, getHeaders()),
          body: JSON.stringify({{ auto_join_enabled: !currentVal }})
        }});
        if (res.ok) refreshDashboard();
        else alert("Failed to toggle auto-join: HTTP " + res.status);
      }} catch (e) {{
        alert("Action failed: " + e.message);
      }}
    }}

    async function checkChannelNow(channelId) {{
      try {{
        const res = await fetch(`/api/v1/dashboard/monitored-channels/${{channelId}}/check-now`, {{
          method: "POST",
          headers: Object.assign({{ "Content-Type": "application/json" }}, getHeaders()),
          body: JSON.stringify({{}})
        }});
        const data = await res.json();
        if (data.status === "LIVE_AUTO_JOINED") {{
          alert("Live stream detected and worker auto-joined! Video ID: " + data.video_id);
        }} else if (data.status === "ALREADY_ACTIVE") {{
          alert("Stream is already active with running worker.");
        }} else if (data.status === "OFFLINE") {{
          alert("Channel is currently offline (no active live stream).");
        }} else {{
          alert("Check result: " + (data.status || JSON.stringify(data)));
        }}
        refreshDashboard();
      }} catch (e) {{
        alert("Check failed: " + e.message);
      }}
    }}

    async function deleteMonitoredChannel(channelId) {{
      if (!confirm("Are you sure you want to stop monitoring this channel?")) return;
      try {{
        const res = await fetch(`/api/v1/dashboard/monitored-channels/${{channelId}}`, {{
          method: "DELETE",
          headers: getHeaders()
        }});
        if (res.ok) refreshDashboard();
        else alert("Failed to delete channel: HTTP " + res.status);
      }} catch (e) {{
        alert("Delete failed: " + e.message);
      }}
    }}

    async function submitManualConnect() {{
      const urlOrId = document.getElementById("modal-stream-url").value.trim();
      const errBox = document.getElementById("connect-error-box");
      const btn = document.getElementById("btn-submit-connect");
      errBox.style.display = "none";

      if (!urlOrId) {{
        errBox.textContent = "Please enter a URL or Video ID";
        errBox.style.display = "block";
        return;
      }}

      btn.disabled = true;
      btn.textContent = "Connecting...";

      try {{
        const res = await fetch("/api/v1/dashboard/streams/manual-connect", {{
          method: "POST",
          headers: Object.assign({{ "Content-Type": "application/json" }}, getHeaders()),
          body: JSON.stringify({{ url_or_video_id: urlOrId }})
        }});
        if (!res.ok) {{
          let msg = "HTTP " + res.status;
          try {{
            const err = await res.json();
            msg = err.detail || (err.error && (err.error.message || err.error.type)) || err.message || JSON.stringify(err);
          }} catch (_) {{
            msg = res.statusText || ("HTTP " + res.status);
          }}
          errBox.textContent = "Connection failed: " + msg;
          errBox.style.display = "block";
        }} else {{
          closeConnectModal();
          document.getElementById("modal-stream-url").value = "";
          refreshDashboard();
        }}
      }} catch (e) {{
        errBox.textContent = "Network error: " + e.message;
        errBox.style.display = "block";
      }} finally {{
        btn.disabled = false;
        btn.textContent = "Connect Stream";
      }}
    }}

    async function handleStreamAction(streamId, action) {{
      try {{
        const res = await fetch(`/api/v1/dashboard/streams/${{streamId}}/control`, {{
          method: "POST",
          headers: Object.assign({{ "Content-Type": "application/json" }}, getHeaders()),
          body: JSON.stringify({{ action: action }})
        }});
        if (res.ok) refreshDashboard();
        else alert("Action failed: HTTP " + res.status);
      }} catch (e) {{
        alert("Action failed: " + e.message);
      }}
    }}

    async function resolveIncident(incidentId) {{
      try {{
        const res = await fetch(`/api/v1/dashboard/incidents/${{incidentId}}/resolve`, {{
          method: "POST",
          headers: Object.assign({{ "Content-Type": "application/json" }}, getHeaders()),
          body: JSON.stringify({{ status: "RESOLVED", resolution: "Resolved via Control Center Web" }})
        }});
        if (res.ok) refreshDashboard();
      }} catch (e) {{
        alert("Resolve failed: " + e.message);
      }}
    }}

    async function resolveReview(reviewId, action) {{
      try {{
        const res = await fetch(`/api/v1/dashboard/moderation/reviews/${{reviewId}}/resolve`, {{
          method: "POST",
          headers: Object.assign({{ "Content-Type": "application/json" }}, getHeaders()),
          body: JSON.stringify({{ action: action }})
        }});
        if (res.ok) refreshDashboard();
      }} catch (e) {{
        alert("Resolve review failed: " + e.message);
      }}
    }}

    async function refreshDashboard() {{
      const headers = getHeaders();
      let hasAuthIssue = false;

      async function fetchApi(url, diagElemId) {{
        const elem = document.getElementById(diagElemId);
        try {{
          const res = await fetch(url, {{ headers }});
          if (res.status === 401 || res.status === 403) {{
            hasAuthIssue = true;
            if (elem) {{ elem.className = "badge badge-danger"; elem.textContent = elem.id.replace("diag-", "") + ": 403"; }}
            return null;
          }}
          if (!res.ok) {{
            if (elem) {{ elem.className = "badge badge-warn"; elem.textContent = elem.id.replace("diag-", "") + ": " + res.status; }}
            return null;
          }}
          if (elem) {{ elem.className = "badge badge-ok"; elem.textContent = elem.id.replace("diag-", "") + ": 200"; }}
          return await res.json();
        }} catch (err) {{
          if (elem) {{ elem.className = "badge badge-danger"; elem.textContent = elem.id.replace("diag-", "") + ": FAIL"; }}
          return null;
        }}
      }}

      const [overview, streams, channels, quota, keys, moderation, incidents] = await Promise.all([
        fetchApi("/api/v1/dashboard/overview", "diag-overview"),
        fetchApi("/api/v1/dashboard/streams", "diag-streams"),
        fetchApi("/api/v1/dashboard/monitored-channels", "diag-channels"),
        fetchApi("/api/v1/dashboard/quota", "diag-quota"),
        fetchApi("/api/v1/dashboard/youtube-keys", "diag-keys"),
        fetchApi("/api/v1/dashboard/moderation?status_filter=PENDING", "diag-moderation"),
        fetchApi("/api/v1/dashboard/incidents", "diag-incidents")
      ]);

      if (hasAuthIssue && !getAdminSecret()) {{
        document.getElementById("auth-banner").style.display = "flex";
      }} else {{
        document.getElementById("auth-banner").style.display = "none";
      }}

      // Overview
      if (overview) {{
        document.getElementById("metric-streams").innerHTML = `${{overview.active_streams}} <span style="font-size: 0.75rem; color: var(--text-muted);">/ 7 max</span>`;
        document.getElementById("metric-quota").innerHTML = `${{overview.quota?.quota_remaining ?? overview.quota?.remaining ?? "N/A"}} <span style="font-size: 0.75rem; color: var(--text-muted);">pts</span>`;
        document.getElementById("metric-hitl").textContent = overview.pending_moderation_reviews ?? 0;
        document.getElementById("metric-ledger").textContent = overview.ledger_balanced ? "BALANCED" : "AUDIT REQ";

        // Subsystems
        const sub = overview.subsystems || {{}};
        function setSub(id, name, obj) {{
          const e = document.getElementById(id);
          const st = (obj?.status || "HEALTHY").toUpperCase();
          e.textContent = `${{name}}: ${{st}}`;
          e.className = `badge ${{st === "HEALTHY" ? "badge-ok" : st === "DEGRADED" ? "badge-warn" : "badge-danger"}}`;
        }}
        setSub("subsystem-db", "DB", sub.database);
        setSub("subsystem-redis", "REDIS", sub.redis);
        setSub("subsystem-yt", "YOUTUBE", sub.youtube);
        setSub("subsystem-workers", "WORKERS", sub.workers);
      }}

      // Streams
      const streamsArr = Array.isArray(streams) ? streams : [];
      document.getElementById("active-stream-badge").textContent = `${{streamsArr.length}} SESSIONS`;
      const sContainer = document.getElementById("streams-container");
      if (streamsArr.length === 0) {{
        sContainer.innerHTML = `<div style="text-align: center; padding: 2.5rem; color: var(--text-muted); font-size: 0.85rem; border: 1px dashed var(--border); border-radius: 0.5rem;">No active YouTube live streams currently connected. Click <strong>+ Connect Stream</strong> to begin.</div>`;
      }} else {{
        sContainer.innerHTML = streamsArr.map(s => `
          <div class="item-card" style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem;">
            <div>
              <div style="font-weight: 700; color: #f8fafc; display: flex; align-items: center; gap: 0.5rem;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background: ${{s.status === "ACTIVE" || s.status === "RUNNING" || s.status === "LIVE" ? "var(--rose)" : "var(--amber)"}}"></span>
                ${{s.channel_name || "Live Stream"}}
                <span class="badge" style="font-size: 0.65rem;">${{s.status}}</span>
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace; margin-top: 0.2rem;">
                Session: ${{s.session_id || s.id}} • Video: ${{s.youtube_video_id || "N/A"}} • Duration: ${{Math.round((s.duration_seconds || (s.duration_minutes || 0)*60)/60)}}m • Msgs: ${{s.messages_processed || 0}}
              </div>
            </div>
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn btn-secondary" onclick="handleStreamAction('${{s.session_id || s.id}}', 'restart')">Restart</button>
              <button class="btn btn-secondary" style="color: var(--rose);" onclick="handleStreamAction('${{s.session_id || s.id}}', 'disconnect')">Disconnect</button>
            </div>
          </div>
        `).join("");
      }}

      // Monitored Channels
      const chanArr = Array.isArray(channels) ? channels : [];
      const mBadge = document.getElementById("monitored-channel-badge");
      if (mBadge) mBadge.textContent = `${{chanArr.length}} MONITORED`;
      const mcContainer = document.getElementById("monitored-channels-container");
      if (mcContainer) {{
        if (chanArr.length === 0) {{
          mcContainer.innerHTML = `<div style="text-align: center; padding: 2.5rem; color: var(--text-muted); font-size: 0.85rem; border: 1px dashed var(--border); border-radius: 0.5rem;">No monitored YouTube channels added. Click <strong>+ Add Channel</strong> to configure automatic live stream detection and auto-join.</div>`;
        }} else {{
          mcContainer.innerHTML = chanArr.map(c => `
            <div class="item-card" style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem;">
              <div style="display: flex; align-items: center; gap: 0.75rem;">
                ${{c.thumbnail_url ? `<img src="${{c.thumbnail_url}}" style="width: 2.25rem; height: 2.25rem; border-radius: 50%; object-fit: cover; border: 1px solid var(--border);" />` : `<div style="width: 2.25rem; height: 2.25rem; border-radius: 50%; background: var(--surface); display: flex; align-items: center; justify-content: center; font-size: 1rem; border: 1px solid var(--border);">📺</div>`}}
                <div>
                  <div style="font-weight: 700; color: #f8fafc; display: flex; align-items: center; gap: 0.5rem;">
                    <a href="https://www.youtube.com/channel/${{c.youtube_channel_id}}" target="_blank" style="color: inherit; text-decoration: none;">${{c.channel_name || "Unknown Channel"}}</a>
                    ${{c.channel_handle ? `<span style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace;">${{c.channel_handle}}</span>` : ""}}
                    <span class="badge badge-ok" style="font-size: 0.65rem;">${{c.verification_status || "VERIFIED"}}</span>
                    ${{c.last_seen_live_at ? `<span class="badge badge-danger" style="font-size: 0.65rem;">🔴 LIVE</span>` : `<span class="badge" style="font-size: 0.65rem; color: var(--text-muted);">OFFLINE</span>`}}
                  </div>
                  <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace; margin-top: 0.2rem;">
                    ID: ${{c.youtube_channel_id}} • Creator: ${{c.creator_name || "N/A"}} • Last checked: ${{c.last_checked_at ? new Date(c.last_checked_at).toLocaleTimeString() : "Never"}}
                    ${{c.last_error_code ? `<span style="color: var(--rose); margin-left: 0.5rem;">[${{c.last_error_code}}]</span>` : ""}}
                  </div>
                </div>
              </div>
              <div style="display: flex; gap: 0.4rem; align-items: center;">
                <button class="btn btn-secondary" onclick="toggleAutoJoin('${{c.id}}', ${{c.auto_join_enabled}})" style="font-size: 0.7rem; color: ${{c.auto_join_enabled ? '#34d399' : 'var(--text-muted)'}};">
                  ${{c.auto_join_enabled ? '⚡ Auto-Join: ON' : '⏸ Auto-Join: OFF'}}
                </button>
                <button class="btn btn-secondary" onclick="checkChannelNow('${{c.id}}')" style="font-size: 0.7rem;">
                  🔍 Check Live
                </button>
                <button class="btn btn-secondary" onclick="deleteMonitoredChannel('${{c.id}}')" style="font-size: 0.7rem; color: var(--rose);">
                  🗑 Delete
                </button>
              </div>
            </div>
          `).join("");
        }}
      }}

      // Quota & Keys
      if (quota) {{
        const consumed = quota.consumed || 0;
        const budget = quota.budget || 4000;
        const rem = quota.remaining ?? (budget - consumed);
        const pct = quota.percent_used ?? Math.round((consumed/budget)*100);
        document.getElementById("quota-consumed-txt").textContent = `Consumed: ${{consumed}} units`;
        document.getElementById("quota-remaining-txt").textContent = `Remaining: ${{rem}} (${{100 - pct}}%)`;
        document.getElementById("quota-progress-fill").style.width = `${{Math.min(pct, 100)}}%`;
      }}
      const keysArr = Array.isArray(keys) ? keys : [];
      const kContainer = document.getElementById("keys-container");
      if (keysArr.length === 0) {{
        kContainer.innerHTML = "No API keys configured or telemetry unavailable.";
      }} else {{
        kContainer.innerHTML = keysArr.map(k => `
          <div style="display: flex; justify-content: space-between; padding: 0.35rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <span>Key #${{k.key_index}}: <span style="color: #94a3b8;">${{k.masked_key || "****"}}</span></span>
            <span>${{k.requests_made || 0}} reqs • <span class="${{k.in_cooldown ? "badge-danger" : "badge-ok"}}" style="padding: 0 0.3rem; border-radius: 0.2rem;">${{k.in_cooldown ? "COOLDOWN" : "ACTIVE"}}</span></span>
          </div>
        `).join("");
      }}

      // Incidents
      const incArr = Array.isArray(incidents) ? incidents : [];
      document.getElementById("incidents-badge").textContent = `${{incArr.filter(i => i.status !== "RESOLVED" && i.status !== "CLOSED").length}} ACTIVE`;
      const iContainer = document.getElementById("incidents-container");
      if (incArr.length === 0) {{
        iContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: #10b981; font-size: 0.85rem;">✓ All services healthy. Zero active incidents reported.</div>`;
      }} else {{
        iContainer.innerHTML = incArr.map(inc => `
          <div class="item-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
              <span class="badge ${{inc.severity === "CRITICAL" ? "badge-danger" : "badge-warn"}}">${{inc.severity}}</span>
              <span style="font-size: 0.7rem; color: var(--text-muted); font-family: monospace;">${{inc.status}}</span>
            </div>
            <div style="font-weight: 600; color: #f1f5f9;">${{inc.summary || "Incident reported"}}</div>
            <div style="font-size: 0.7rem; color: var(--text-muted); font-family: monospace; margin-top: 0.2rem;">Service: ${{inc.service}} • ID: ${{inc.incident_id}}</div>
            ${{inc.status !== "RESOLVED" && inc.status !== "CLOSED" ? `
              <div style="display: flex; justify-content: flex-end; margin-top: 0.5rem;">
                <button class="btn btn-secondary" onclick="resolveIncident('${{inc.incident_id}}')" style="color: #34d399;">Mark Resolved</button>
              </div>
            ` : ""}}
          </div>
        `).join("");
      }}

      // Moderation
      let modArr = [];
      if (Array.isArray(moderation)) modArr = moderation;
      else if (moderation && Array.isArray(moderation.items)) modArr = moderation.items;
      document.getElementById("moderation-badge").textContent = `${{modArr.length}} PENDING`;
      const mContainer = document.getElementById("moderation-container");
      if (modArr.length === 0) {{
        mContainer.innerHTML = `<div style="text-align: center; padding: 2rem; color: #94a3b8; font-size: 0.85rem;">Zero pending moderation reviews. All live stream chats are safe.</div>`;
      }} else {{
        mContainer.innerHTML = modArr.map(m => `
          <div class="item-card" style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 0.75rem;">
            <div>
              <div style="font-weight: 700; color: #f8fafc;">
                ${{m.author_display_name || m.viewer_name || "Viewer"}}:
                <span style="font-weight: 400; color: #e2e8f0; font-family: monospace;">"${{m.message_text || m.flagged_content || ""}}"</span>
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted); font-family: monospace; margin-top: 0.2rem;">
                Reason: ${{m.reason || m.flagged_reason || "Violation"}} • Confidence: ${{m.confidence ?? 85}}% • Severity: ${{m.severity ?? 50}}%
              </div>
            </div>
            <div style="display: flex; gap: 0.4rem;">
              <button class="btn btn-secondary" onclick="resolveReview('${{m.id}}', 'APPROVE')" style="color: #34d399;">Approve</button>
              <button class="btn btn-secondary" onclick="resolveReview('${{m.id}}', 'DENY')" style="color: #f43f5e;">Delete</button>
            </div>
          </div>
        `).join("");
      }}

      document.getElementById("last-updated").textContent = `Updated: ${{new Date().toLocaleTimeString()}}`;
    }}

    // Auto-init
    const stored = getAdminSecret();
    if (stored) document.getElementById("admin-secret-input").value = stored;
    refreshDashboard();
    setInterval(refreshDashboard, 5000);
  </script>
</body>
</html>
"""


@router.get("/", summary="Goddess AI Web Control Center & API Status")
async def root_index(request: Request, accept: str = Header(default="*/*")) -> Any:
    """
    Root entrypoint. Returns an interactive Control Center Web UI for browser requests,
    or structured JSON metadata for API clients.
    """
    settings = get_settings()

    # If accessed by a web browser, serve the embedded Control Center
    if "text/html" in accept or "text/html" in request.headers.get("accept", ""):
        html_content = render_control_center_html(
            environment=settings.APP_ENV,
            version="0.1.0",
        )
        return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)

    # If requested by API client, return service descriptor JSON
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "service": "Goddess AI / AI-Modrator",
            "status": "HEALTHY",
            "version": "0.1.0",
            "environment": settings.APP_ENV,
            "endpoints": {
                "health": "/health",
                "liveness": "/health/live",
                "readiness": "/health/ready",
                "dashboard_web": "/",
                "dashboard_api_overview": "/api/v1/dashboard/overview",
                "dashboard_api_streams": "/api/v1/dashboard/streams",
                "dashboard_api_quota": "/api/v1/dashboard/quota",
            },
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


@router.get("/dashboard", summary="Dashboard Web View Alias")
async def dashboard_web_alias() -> HTMLResponse:
    """Web view alias for /dashboard."""
    settings = get_settings()
    html_content = render_control_center_html(
        environment=settings.APP_ENV,
        version="0.1.0",
    )
    return HTMLResponse(content=html_content, status_code=status.HTTP_200_OK)
