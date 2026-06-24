"""Phase 16/20/21 local web UI for the standalone collab bridge."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping

from .bridge import build_worker_launch_blueprint, dumps_bridge_json
from .bridge_host import (
    create_bridge_worker,
    create_session_from_blueprint,
    focus_worker,
    load_session_events,
    materialize_bridge_host,
    save_session_events,
    send_worker_message,
)
from .config import load_config
from .errors import CollabError
from .plan import build_dispatch_plan
from .router import build_router_snapshot, enqueue_message, fail_message, ingest_router_report, retry_message


class WebUiError(CollabError):
    """Raised when Phase 16/20 web UI input or request handling fails."""

    error_code = "COLLAB_WEB_UI_INVALID_INPUT"


INDEX_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Collab Bridge · Orca Split View</title>
  <style>
    :root {
      --surface: #f7f7f4;
      --surface-elevated: #ffffff;
      --surface-soft: #f1f1ee;
      --surface-hover: #ecece8;
      --content-area: #f7f7f4;
      --border: #d7d7d4;
      --border-soft: rgba(215, 215, 212, .62);
      --text: #242421;
      --muted: #767670;
      --muted-2: #9a9a94;
      --accent: #d97706;
      --accent-soft: rgba(217, 119, 6, .12);
      --send: #1f1f1c;
      --send-text: #ffffff;
      --tool-bg: #ffffff;
      --tool-border: #deded9;
      --shadow-soft: 0 18px 55px rgba(28, 28, 24, .08);
      font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: var(--content-area);
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; margin: 0; overflow: hidden; background: var(--content-area); color: var(--text); }
    button, input, textarea, select { font: inherit; }
    button { cursor: pointer; }
    .orca-root { height: 100vh; width: 100vw; display: flex; overflow: hidden; background: var(--content-area); }
    .pane { min-width: 0; height: 100%; display: flex; flex-direction: column; background: var(--content-area); position: relative; }
    .pane.lead { flex: 1 1 65%; }
    .pane.worker { flex: 0 0 35%; min-width: 360px; }
    .pane.maximized { flex: 1 1 100%; }
    .pane.hidden { flex: 0 0 0; min-width: 0; overflow: hidden; }
    .pane-header { height: 28px; flex: 0 0 28px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; border-bottom: 1px solid var(--border-soft); color: var(--muted); font-size: 11px; font-weight: 600; line-height: 1; letter-spacing: .01em; }
    .pane-title { display: inline-flex; align-items: center; gap: 8px; min-width: 0; }
    .agent-mark { display: inline-flex; align-items: center; justify-content: center; height: 16px; min-width: 16px; padding: 0 5px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface-elevated); color: var(--text); font-size: 10px; font-weight: 700; }
    .pane-actions { display: flex; align-items: center; gap: 4px; }
    .icon-btn { width: 20px; height: 20px; border: 0; border-radius: 5px; background: transparent; color: var(--muted); display: inline-flex; align-items: center; justify-content: center; transition: background .12s ease, color .12s ease; }
    .icon-btn:hover { background: var(--surface-hover); color: var(--text); }
    .splitter { width: 1px; flex: 0 0 1px; border: 0; padding: 0; background: rgba(0,0,0,.16); cursor: col-resize; position: relative; }
    .splitter::before { content: ""; position: absolute; top: 0; bottom: 0; left: -6px; width: 13px; }
    .stream { min-height: 0; flex: 1; overflow: auto; padding: 34px min(56px, 7vw) 210px; scroll-behavior: smooth; }
    .worker .stream { padding-left: 20px; padding-right: 20px; }
    .empty-state { height: 100%; display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 13px; text-align: center; }
    .message { display: flex; width: 100%; margin: 0 0 18px; }
    .message.user { justify-content: flex-end; }
    .bubble { max-width: 760px; border: 1px solid var(--border); border-radius: 13px; padding: 12px 14px; background: var(--surface-elevated); color: var(--text); font-size: 14px; line-height: 1.55; box-shadow: 0 1px 0 rgba(0,0,0,.025); }
    .message.user .bubble { background: #fafaf8; }
    .message.assistant .bubble { border-color: transparent; background: transparent; box-shadow: none; padding-left: 0; }
    .meta-line { display: flex; align-items: center; gap: 8px; margin-bottom: 7px; color: var(--muted); font-size: 11px; font-weight: 600; line-height: 1; }
    .tool-card { margin: 10px 0 0; border: 1px solid var(--tool-border); border-radius: 12px; background: var(--tool-bg); overflow: hidden; }
    .tool-card-head { display: flex; align-items: center; gap: 8px; padding: 9px 12px; color: var(--text); font-size: 13px; font-weight: 650; }
    .tool-card-body { border-top: 1px solid var(--tool-border); padding: 9px 12px; color: var(--muted); font-size: 12px; white-space: pre-wrap; word-break: break-word; }
    .status-pill { display: inline-flex; align-items: center; gap: 5px; height: 22px; padding: 0 9px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface-elevated); color: var(--muted); font-size: 11px; font-weight: 600; }
    .status-pill.running, .status-pill.queued { color: var(--accent); border-color: rgba(217,119,6,.42); background: var(--accent-soft); }
    .status-pill.done, .status-pill.retried { color: #287a41; border-color: rgba(40,122,65,.28); background: rgba(40,122,65,.09); }
    .overlay { position: sticky; bottom: 0; margin: 0 auto; padding: 0 0 18px; width: min(914px, calc(100% - 28px)); pointer-events: none; }
    .worker .overlay { width: calc(100% - 24px); }
    .status-bar { height: 28px; display: flex; align-items: center; gap: 8px; color: var(--accent); font-size: 13px; font-weight: 600; opacity: .96; }
    .status-bar .right { margin-left: auto; color: var(--muted); font-size: 12px; font-weight: 600; }
    .chat-input { pointer-events: auto; border: 1px solid var(--border); border-radius: 18px; background: var(--surface-elevated); box-shadow: var(--shadow-soft); padding: 11px; }
    .chat-input textarea { width: 100%; min-height: 66px; max-height: 150px; resize: vertical; border: 0; outline: none; background: transparent; color: var(--text); font-size: 14px; line-height: 1.5; padding: 4px 5px 8px; }
    .input-toolbar { display: flex; align-items: center; gap: 8px; min-height: 28px; }
    .input-toolbar .spacer { flex: 1; }
    .pill-button { height: 26px; display: inline-flex; align-items: center; justify-content: center; gap: 6px; border: 1px solid var(--border); border-radius: 999px; background: transparent; color: var(--muted); padding: 0 10px; font-size: 12px; font-weight: 600; transition: background .12s ease, color .12s ease, border-color .12s ease; }
    .pill-button:hover { background: var(--surface-hover); color: var(--text); }
    .pill-button.collab-on { color: var(--accent); border-color: var(--accent); background: transparent; }
    .pill-button.collab-on:hover { background: var(--accent-soft); }
    .send-button { width: 30px; height: 30px; border: 0; border-radius: 999px; background: var(--send); color: var(--send-text); font-size: 15px; display: inline-flex; align-items: center; justify-content: center; }
    .send-button.secondary { background: var(--surface-soft); color: var(--text); border: 1px solid var(--border); }
    .worker-strip { display: flex; gap: 6px; align-items: center; overflow: auto; padding: 8px 10px; border-bottom: 1px solid var(--border-soft); background: rgba(255,255,255,.34); }
    .worker-chip { height: 28px; display: inline-flex; align-items: center; gap: 7px; border: 1px solid var(--border); border-radius: 999px; background: var(--surface-elevated); color: var(--muted); padding: 0 10px; white-space: nowrap; font-size: 12px; font-weight: 600; }
    .worker-chip.focused { color: var(--accent); border-color: rgba(217,119,6,.55); background: var(--accent-soft); }
    .worker-chip button { all: unset; cursor: pointer; }
    .quick-panel { display: none; position: absolute; right: 14px; top: 36px; width: 320px; z-index: 30; border: 1px solid var(--border); border-radius: 14px; background: var(--surface-elevated); box-shadow: var(--shadow-soft); padding: 12px; }
    .quick-panel.open { display: block; }
    .quick-panel label { display: block; margin: 8px 0 4px; color: var(--muted); font-size: 11px; font-weight: 650; }
    .quick-panel input, .quick-panel textarea { width: 100%; border: 1px solid var(--border); border-radius: 9px; background: var(--surface); color: var(--text); padding: 8px 9px; outline: none; font-size: 12px; }
    .quick-panel textarea { min-height: 62px; resize: vertical; }
    .panel-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .mono-drawer { display: none; position: absolute; right: 12px; bottom: 88px; width: min(460px, calc(100vw - 24px)); max-height: 44vh; overflow: auto; z-index: 25; border: 1px solid var(--tool-border); border-radius: 12px; background: var(--tool-bg); box-shadow: var(--shadow-soft); padding: 12px; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 11px; color: var(--muted); white-space: pre-wrap; }
    .mono-drawer.open { display: block; }
    .mobile-tabs { display: none; height: 40px; flex: 0 0 40px; align-items: center; gap: 14px; padding: 0 13px; border-bottom: 1px solid var(--border-soft); }
    .mobile-tabs button { border: 0; background: transparent; color: var(--muted); font-size: 12px; font-weight: 650; padding: 0; }
    .mobile-tabs button.active { color: var(--text); }
    @media (max-width: 860px) {
      .orca-root { flex-direction: column; }
      .mobile-tabs { display: flex; }
      .pane { display: none; flex: 1 1 auto; min-width: 0; }
      .pane.mobile-active { display: flex; }
      .splitter { display: none; }
      .pane-header { display: none; }
      .stream { padding-left: 18px; padding-right: 18px; }
    }
  </style>
</head>
<body>
<div class="orca-root" data-testid="xdmaker-orca-split-view">
  <div class="mobile-tabs" role="tablist" aria-label="Collab panes">
    <button id="tab-lead" class="active">Lead (XD.Inc)</button>
    <span style="color:var(--muted-2)">·</span>
    <button id="tab-worker">Worker</button>
  </div>
  <section id="lead-pane" class="pane lead mobile-active" data-testid="lead-pane">
    <div class="pane-header">
      <div class="pane-title"><span>Lead (XD.Inc)</span><span class="agent-mark">XD</span></div>
      <div class="pane-actions">
        <button id="bootstrap" class="icon-btn" data-testid="bootstrap-button" title="Bootstrap/Reload">↻</button>
        <button id="create-worker" class="icon-btn" data-testid="create-worker-button" title="Create worker">＋</button>
        <button id="lead-max" class="icon-btn" title="Maximize Lead">□</button>
      </div>
    </div>
    <div id="worker-list" class="worker-strip" data-testid="worker-list"></div>
    <div id="lead-stream" class="stream" data-testid="timeline"></div>
    <div class="overlay">
      <div class="status-bar"><span>✦ Collab bridge</span><span id="lead-status" class="right">loading</span></div>
      <div class="chat-input">
        <textarea id="message" data-testid="message-box">hello worker</textarea>
        <div class="input-toolbar">
          <button id="open-create" class="pill-button collab-on">🧩 协同</button>
          <button id="enqueue" class="pill-button" data-testid="enqueue-button">Queue</button>
          <button id="show-json" class="pill-button">Status</button>
          <span class="spacer"></span>
          <button id="send" class="send-button" data-testid="send-button" title="Send Direct">↑</button>
        </div>
      </div>
    </div>
  </section>
  <button id="splitter" class="splitter" aria-label="Resize Orca panes"></button>
  <section id="worker-pane" class="pane worker" data-testid="worker-pane">
    <div class="pane-header">
      <div class="pane-title"><span id="worker-title">Worker (Codex)</span><span class="agent-mark">CX</span></div>
      <div class="pane-actions">
        <button id="worker-max" class="icon-btn" title="Maximize Worker">□</button>
        <button id="worker-close" class="icon-btn" title="Hide Worker">×</button>
      </div>
    </div>
    <div id="worker-stream" class="stream"></div>
    <div class="overlay">
      <div class="status-bar"><span id="worker-status">Waiting for worker</span><span class="right">0s · ↓ 0 tokens</span></div>
      <div class="chat-input">
        <textarea id="report" data-testid="report-box">reports/ui-report.md</textarea>
        <div class="input-toolbar">
          <select id="message-select" data-testid="message-select" style="min-width:0;max-width:190px;border:1px solid var(--border);border-radius:999px;background:transparent;color:var(--muted);height:26px;padding:0 8px;font-size:12px"></select>
          <input id="fail-error" value="manual failure" style="display:none">
          <button id="fail" class="pill-button" data-testid="fail-button">Fail</button>
          <button id="retry" class="pill-button" data-testid="retry-button">Retry</button>
          <span class="spacer"></span>
          <button id="report-button" class="send-button secondary" data-testid="report-button" title="Ingest Report">✓</button>
        </div>
      </div>
    </div>
  </section>
  <div id="create-panel" class="quick-panel">
    <label>Worker id</label>
    <input id="new-worker-id" placeholder="worker id" value="worker-ui-extra">
    <div class="panel-row">
      <div><label>Agent</label><input id="new-agent" placeholder="agent" value="find"></div>
      <div><label>Adapter</label><input id="new-adapter" value="operator_command"></div>
    </div>
    <label>Initial prompt</label>
    <textarea id="new-prompt">UI-created worker prompt</textarea>
    <div class="input-toolbar" style="margin-top:10px">
      <button id="cancel-create" class="pill-button">Cancel</button>
      <span class="spacer"></span>
      <button id="confirm-create" class="pill-button collab-on">开启协同</button>
    </div>
  </div>
  <pre id="status-json" class="mono-drawer" data-testid="status-json">loading</pre>
</div>
<script>
let state = { focused: null, model: null, router: null, maximized: null, activePane: 'lead' };
const $ = id => document.getElementById(id);
function esc(v) { return String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const json = await res.json();
  if (!json.ok && json.kind === 'collab_web_ui_error') throw new Error(json.message || json.error);
  return json;
}
async function refresh() {
  const data = await api('/api/model');
  state.model = data.materialized;
  state.router = data.router;
  state.focused = state.model.focused_worker_id || state.focused || (state.model.worker_rows[0] && state.model.worker_rows[0].worker_id);
  render();
}
function workerRows() { return (state.model && state.model.worker_rows) || []; }
function messages() { return (state.router && state.router.messages) || []; }
function focusedWorker() { return workerRows().find(w => w.worker_id === state.focused) || workerRows()[0] || null; }
function render() {
  const workers = workerRows();
  const focused = focusedWorker();
  $('worker-list').innerHTML = workers.map(w => `<span class="worker-chip ${w.worker_id===state.focused?'focused':''}"><button data-worker="${esc(w.worker_id)}">${esc(w.worker_id)}</button><span>${esc(w.agent)} · ${esc(w.status)}</span></span>`).join('') || '<span class="worker-chip">Waiting for worker</span>';
  document.querySelectorAll('[data-worker]').forEach(el => el.onclick = async () => { state.focused = el.dataset.worker; await api('/api/focus', {worker_id: state.focused}); await refresh(); });
  $('worker-title').textContent = focused ? `Worker (${focused.agent === 'codex' ? 'Codex' : focused.agent || 'Codex'})` : 'Worker (Codex)';
  $('worker-status').textContent = focused ? `${focused.status} · messages=${focused.message_count} · report=${focused.report_pointer || '-'}` : 'Waiting for worker';
  const msgs = messages();
  $('lead-stream').innerHTML = renderLeadStream(msgs, workers);
  $('worker-stream').innerHTML = renderWorkerStream(focused, msgs);
  $('message-select').innerHTML = msgs.map(m => `<option value="${esc(m.message_id)}">${esc(m.status)} · ${esc(m.message_id)}</option>`).join('');
  const summary = state.model.summary || {};
  const routerSummary = state.router.summary || {};
  $('lead-status').textContent = `${summary.worker_count || 0} workers · ${routerSummary.message_count || 0} messages`;
  $('status-json').textContent = JSON.stringify({summary, router: routerSummary, focused: state.focused, xdmaker_clone: true}, null, 2);
}
function renderLeadStream(msgs, workers) {
  const intro = `<div class="message assistant"><div class="bubble"><div class="meta-line"><span class="agent-mark">XD</span><span>Lead session</span><span class="status-pill running">协同模式开启</span></div><div>Use <b>send_to_worker</b> / <b>worker_status</b> / <b>read_worker</b> style actions through this standalone bridge.</div><div class="tool-card"><div class="tool-card-head">🧩 Orca workers</div><div class="tool-card-body">${workers.map(w => `${esc(w.worker_id)} · ${esc(w.agent)} · ${esc(w.status)}`).join('<br>') || 'No workers yet'}</div></div></div></div>`;
  const rows = msgs.map(m => `<div class="message user"><div class="bubble"><div class="meta-line"><span class="status-pill ${esc(m.status)}">${esc(m.status)}</span><span>${esc(m.message_id)}</span></div>${esc(m.message)}<div class="tool-card"><div class="tool-card-head">send_to_worker → ${esc(m.worker_id)}</div><div class="tool-card-body">attempt=${esc(m.attempt)} · correlation=${esc(m.correlation_id || '-')}</div></div></div></div>`).join('');
  return intro + (rows || `<div class="empty-state">No router messages yet<br>Send a task to the Worker pane.</div>`);
}
function renderWorkerStream(worker, msgs) {
  if (!worker) return '<div class="empty-state">Waiting for worker</div>';
  const mine = msgs.filter(m => m.worker_id === worker.worker_id);
  const head = `<div class="message assistant"><div class="bubble"><div class="meta-line"><span class="agent-mark">CX</span><span>${esc(worker.worker_id)}</span><span class="status-pill ${esc(worker.status)}">${esc(worker.status)}</span></div><div>Worker session attached to Lead. Report pointer: <b>${esc(worker.report_pointer || 'none')}</b></div></div></div>`;
  const rows = mine.map(m => `<div class="message assistant"><div class="bubble"><div class="meta-line"><span class="status-pill ${esc(m.status)}">${esc(m.status)}</span><span>${esc(m.message_id)}</span></div>${esc(m.message)}<div class="tool-card"><div class="tool-card-head">read_worker snapshot</div><div class="tool-card-body">attempt=${esc(m.attempt)} · retry_of=${esc(m.retry_of || '-')}</div></div></div></div>`).join('');
  return head + (rows || '<div class="empty-state">This worker has no queued message yet.</div>');
}
function val(id) { return $(id).value; }
function setMaximized(pane) {
  state.maximized = state.maximized === pane ? null : pane;
  $('lead-pane').classList.toggle('maximized', state.maximized === 'lead');
  $('worker-pane').classList.toggle('maximized', state.maximized === 'worker');
  $('lead-pane').classList.toggle('hidden', state.maximized === 'worker');
  $('worker-pane').classList.toggle('hidden', state.maximized === 'lead');
  $('splitter').style.display = state.maximized ? 'none' : '';
}
function setMobilePane(pane) {
  state.activePane = pane;
  $('lead-pane').classList.toggle('mobile-active', pane === 'lead');
  $('worker-pane').classList.toggle('mobile-active', pane === 'worker');
  $('tab-lead').classList.toggle('active', pane === 'lead');
  $('tab-worker').classList.toggle('active', pane === 'worker');
}
$('bootstrap').onclick = async () => { await api('/api/bootstrap', {}); await refresh(); };
$('open-create').onclick = () => $('create-panel').classList.toggle('open');
$('create-worker').onclick = () => $('create-panel').classList.toggle('open');
$('cancel-create').onclick = () => $('create-panel').classList.remove('open');
$('confirm-create').onclick = async () => { await api('/api/create-worker', {worker_id: val('new-worker-id'), agent: val('new-agent'), initial_prompt: val('new-prompt'), runtime_adapter: val('new-adapter'), focus: true}); $('create-panel').classList.remove('open'); await refresh(); };
$('send').onclick = async () => { await api('/api/send', {worker_id: state.focused, message: val('message')}); await refresh(); };
$('enqueue').onclick = async () => { await api('/api/router/enqueue', {worker_id: state.focused, message: val('message')}); await refresh(); };
$('report-button').onclick = async () => { await api('/api/report', {worker_id: state.focused, report: val('report'), status: 'done'}); await refresh(); };
$('fail').onclick = async () => { await api('/api/router/fail', {message_id: val('message-select'), error: val('fail-error')}); await refresh(); };
$('retry').onclick = async () => { await api('/api/retry', {message_id: val('message-select')}); await refresh(); };
$('show-json').onclick = () => $('status-json').classList.toggle('open');
$('lead-max').onclick = () => setMaximized('lead');
$('worker-max').onclick = () => setMaximized('worker');
$('worker-close').onclick = () => setMaximized('lead');
$('tab-lead').onclick = () => setMobilePane('lead');
$('tab-worker').onclick = () => setMobilePane('worker');
refresh().catch(err => $('status-json').textContent = String(err));
</script>
</body>
</html>"""


def ensure_session_events(path: str | Path, *, worker_limit: int = 1, reset: bool = False) -> dict[str, Any]:
    event_path = Path(path)
    if reset or not event_path.exists() or not event_path.read_text(encoding="utf-8", errors="replace").strip():
        event_path.parent.mkdir(parents=True, exist_ok=True)
        plan = build_dispatch_plan(load_config(), intent="Phase 20 operable web UI session.")
        blueprint = build_worker_launch_blueprint(plan)
        session = create_session_from_blueprint(blueprint, worker_limit=worker_limit, runtime_mode="fake")
        save_session_events(session, event_path)
        return {"created": True, "session": session}
    return {"created": False, "session": load_session_events(event_path)}


def make_handler(events_path: str | Path) -> type[BaseHTTPRequestHandler]:
    path = Path(events_path)

    class Handler(BaseHTTPRequestHandler):
        server_version = "CollabWebUi/0.2"

        def do_GET(self) -> None:  # noqa: N802
            try:
                if self.path == "/" or self.path.startswith("/index.html"):
                    _send(self, 200, INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
                elif self.path.startswith("/api/model"):
                    session = ensure_session_events(path)["session"]
                    _json(self, _model_payload(session))
                elif self.path.startswith("/api/events"):
                    session = ensure_session_events(path)["session"]
                    _json(self, {"ok": True, "kind": "collab_web_ui_events", "phase": 21, "events": list(session.get("events", []))})
                else:
                    _json(self, {"ok": False, "error": "not found"}, status=404)
            except Exception as exc:
                _json(self, _error_payload(exc), status=500)

        def do_POST(self) -> None:  # noqa: N802
            try:
                payload = _read_json(self)
                route = self.path.split("?", 1)[0]
                if route == "/api/bootstrap":
                    worker_limit = int(payload.get("worker_limit") or 1)
                    bootstrap = ensure_session_events(path, worker_limit=worker_limit, reset=bool(payload.get("reset", False)))
                    _json(self, {"ok": True, "kind": "collab_web_ui_bootstrap", "phase": 21, "created": bootstrap["created"], **_model_payload(bootstrap["session"])})
                    return
                session = ensure_session_events(path)["session"]
                result: Mapping[str, Any]
                if route == "/api/create-worker":
                    session = create_bridge_worker(
                        session,
                        worker_id=_required(payload, "worker_id"),
                        agent=_required(payload, "agent"),
                        initial_prompt=_required(payload, "initial_prompt"),
                        dispatch_id=str(payload.get("dispatch_id") or ""),
                        role=str(payload.get("role") or ""),
                        runtime_adapter=str(payload.get("runtime_adapter") or "operator_command"),
                        focus=bool(payload.get("focus", False)),
                    )
                    result = {"status": "created", "worker_id": payload["worker_id"]}
                elif route == "/api/focus":
                    session = focus_worker(session, _required(payload, "worker_id"))
                    result = {"status": "focused", "worker_id": payload["worker_id"]}
                elif route == "/api/send":
                    session = send_worker_message(session, _required(payload, "worker_id"), _required(payload, "message"))
                    result = {"status": "sent", "worker_id": payload["worker_id"]}
                elif route == "/api/report":
                    session, result = ingest_router_report(session, _required(payload, "worker_id"), _required(payload, "report"), status=str(payload.get("status") or "done"))
                elif route == "/api/router/enqueue":
                    session, result = enqueue_message(session, _required(payload, "worker_id"), _required(payload, "message"), correlation_id=str(payload.get("correlation_id") or ""), dedupe_key=str(payload.get("dedupe_key") or ""))
                elif route == "/api/router/fail":
                    session, result = fail_message(session, _required(payload, "message_id"), _required(payload, "error"), retryable=bool(payload.get("retryable", True)))
                elif route == "/api/retry":
                    session, result = retry_message(session, _required(payload, "message_id"))
                else:
                    _json(self, {"ok": False, "error": "not found"}, status=404)
                    return
                save_session_events(session, path)
                _json(self, {"ok": True, "kind": "collab_web_ui_action", "phase": 21, "result": dict(result), **_model_payload(session)})
            except Exception as exc:
                _json(self, _error_payload(exc), status=400)

        def log_message(self, fmt: str, *args: Any) -> None:
            return

    return Handler


def serve_web_ui(events_path: str | Path, *, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    ensure_session_events(events_path)
    return ThreadingHTTPServer((host, int(port)), make_handler(events_path))


def run_web_ui_smoke(out_dir: str | Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    events = out / "events.jsonl"
    server = serve_web_ui(events, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        html = urllib.request.urlopen(base + "/", timeout=5).read().decode("utf-8")
        model = _http_json("GET", base + "/api/model")
        created = _http_json("POST", base + "/api/create-worker", {"worker_id": "worker-ui-extra", "agent": "find", "initial_prompt": "ui worker", "focus": True})
        focus = _http_json("POST", base + "/api/focus", {"worker_id": "worker-ui-extra"})
        send = _http_json("POST", base + "/api/send", {"worker_id": "worker-ui-extra", "message": "ui smoke message"})
        queued = _http_json("POST", base + "/api/router/enqueue", {"worker_id": "worker-ui-extra", "message": "ui smoke router", "correlation_id": "ui-smoke", "dedupe_key": "ui-smoke"})
        message_id = queued["result"]["message_id"]
        failed = _http_json("POST", base + "/api/router/fail", {"message_id": message_id, "error": "synthetic failure"})
        retried = _http_json("POST", base + "/api/retry", {"message_id": message_id})
        report = _http_json("POST", base + "/api/report", {"worker_id": "worker-ui-extra", "report": "reports/ui-smoke.md", "status": "done"})
        events_payload = _http_json("GET", base + "/api/events")
        final_model = _http_json("GET", base + "/api/model")
        reloaded = _http_json("GET", base + "/api/model")
    finally:
        server.shutdown()
        server.server_close()
    controls = [
        "data-testid=\"xdmaker-orca-split-view\"",
        "Lead (XD.Inc)",
        "Worker (",
        "data-testid=\"worker-list\"",
        "data-testid=\"send-button\"",
        "data-testid=\"report-button\"",
        "data-testid=\"retry-button\"",
    ]
    result = {
        "schema_version": 1,
        "kind": "collab_web_ui_smoke",
        "phase": 21,
        "base_url": base,
        "events": str(events),
        "page_controls_present": all(marker in html for marker in controls),
        "api_ok": all(item.get("ok") for item in [model, created, focus, send, queued, failed, retried, report, events_payload, final_model, reloaded]),
        "actions": {"created": created["result"], "focus": focus["result"], "send": send["result"], "queued": queued["result"], "failed": failed["result"], "retried": retried["result"], "report": report["result"]},
        "event_count": len(events_payload["events"]),
        "final_summary": final_model["materialized"]["summary"],
        "router_summary": final_model["router"]["summary"],
        "reload_preserved_worker_count": reloaded["materialized"]["summary"]["worker_count"],
    }
    (out / "web-ui-smoke.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def dumps_web_ui_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def _model_payload(session: Mapping[str, Any]) -> dict[str, Any]:
    return {"ok": True, "kind": "collab_web_ui_model", "phase": 21, "materialized": materialize_bridge_host(session), "router": build_router_snapshot(session)}


def _send(handler: BaseHTTPRequestHandler, status: int, body: bytes, content_type: str) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _json(handler: BaseHTTPRequestHandler, payload: Mapping[str, Any], *, status: int = 200) -> None:
    _send(handler, status, json.dumps(dict(payload), ensure_ascii=False, indent=2).encode("utf-8"), "application/json; charset=utf-8")


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    payload = json.loads(raw or "{}")
    if not isinstance(payload, dict):
        raise WebUiError("request JSON must be an object")
    return payload


def _required(payload: Mapping[str, Any], key: str) -> str:
    text = str(payload.get(key) or "").strip()
    if not text:
        raise WebUiError(f"{key} is required")
    return text


def _error_payload(exc: BaseException) -> dict[str, Any]:
    return {"ok": False, "kind": "collab_web_ui_error", "error": str(exc), "message": str(exc), "details": {}}


def _http_json(method: str, url: str, body: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = None if body is None else json.dumps(dict(body)).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise WebUiError(exc.read().decode("utf-8")) from exc
