#!/usr/bin/env python3
"""
retrieve_inject.py — UserPromptSubmit hook

Generates a compact RAG Brief by calling the warm local gm.search sidecar
with the interactive_hook delivery profile. Pure read-only.

Fail-open: any exception or timeout returns silently (no brief, no error).
The hook does not cold-start gm.search/reranker by default; set
HARNESS_RAG_HOOK_ALLOW_COLD_FALLBACK=1 only for temporary diagnostics.
Disable via env HARNESS_RETRIEVE_INJECT=0.

Logs:
    - retrieve calls (one JSON line per call, with source=retrieve_inject):
        $env:GLOBAL_MEMORY_LOGS_DIR/retrieve_calls.jsonl
      File stays JSONL (one record per line) so analyze_retrieve_log.py and
      other line-by-line parsers keep working — do not pretty-print in place.

      Pretty viewer (human-readable, multi-line):
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/view_retrieve_log.py"
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/view_retrieve_log.py" -n 30
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/view_retrieve_log.py" --source retrieve_inject
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/view_retrieve_log.py" --miss

      Quick greps (raw JSONL):
        Select-String '"source": "gm.search"' <log>
        Select-String '"hit_count": 0' <log>

      Analyzer:
        python "$env:GLOBAL_MEMORY_DIR/harness/scripts/analyze_retrieve_log.py" --days 7
"""

from __future__ import annotations

import io
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

if "pytest" not in sys.modules:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

HARNESS_ROOT = Path(__file__).resolve().parent.parent
HARNESS_SCRIPTS = Path(os.environ.get("GLOBAL_HARNESS_SCRIPTS", str(HARNESS_ROOT / "scripts")))
sys.path.insert(0, str(HARNESS_ROOT.parent))
sys.path.insert(0, str(HARNESS_ROOT))
sys.path.insert(0, str(HARNESS_SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config import GLOBAL_MEMORY_LOGS_DIR, is_runtime_logs_dir_in_repo, runtime_logs_repo_warning
except Exception:  # fail-open fallback for standalone hook invocation
    GLOBAL_MEMORY_LOGS_DIR = Path.home() / ".global-memory" / "logs"

    def is_runtime_logs_dir_in_repo(_logs_dir: Path | None = None) -> bool:
        return False

    def runtime_logs_repo_warning(_logs_dir: Path | None = None) -> str:
        return "WARNING: runtime logs dir is inside the global-memory repository"

try:
    from runtime_brief import build_runtime_brief, runtime_brief_topic
except Exception:  # fail-open fallback: runtime brief is optional

    def runtime_brief_topic(_user_msg: str) -> str | None:
        return None

    def build_runtime_brief(_user_msg: str, **_kwargs: object) -> str | None:
        return None

TIMEOUT_SEC = float(os.environ.get("HARNESS_RAG_HOOK_TIMEOUT_SEC", "1.2"))
MIN_QUERY_LEN = 3
CLAUDE_DIR = Path.home() / ".claude"
POLICY_FACT_MAX_ELAPSED_SEC = 0.2
SESSION_TASKS_DIR = CLAUDE_DIR / ".session_tasks"
DEFAULT_SIDECAR_HOST = "127.0.0.1"
DEFAULT_SIDECAR_PORT = 8766
DEFAULT_SIDECAR_PYTHON = Path(os.environ.get("GM_SEARCH_SIDECAR_PYTHON", sys.executable))
SIDECAR_START_THROTTLE_SEC = float(os.environ.get("GM_SEARCH_SIDECAR_START_THROTTLE_SEC", "30"))
SIDECAR_COOLDOWN_FAILURE_THRESHOLD = int(os.environ.get("GM_SEARCH_SIDECAR_COOLDOWN_FAILURE_THRESHOLD", "3"))
SIDECAR_COOLDOWN_SEC = float(os.environ.get("GM_SEARCH_SIDECAR_COOLDOWN_SEC", "300"))



def _parse_stdin() -> tuple[str, str, str]:
    try:
        raw_bytes = sys.stdin.buffer.read()
        raw = raw_bytes.decode("utf-8", errors="replace").strip()
    except Exception:
        raw = sys.stdin.read().strip()
    if not raw:
        return "", "", ""
    try:
        d = json.loads(raw)
        prompt = d.get("prompt") or d.get("user_prompt") or d.get("message") or ""
        session_id = d.get("session_id") or d.get("hook_session_id") or d.get("conversation_id") or ""
        client = d.get("client") or d.get("source") or ""
        return prompt, session_id, client
    except Exception:
        return raw, "", ""


def _read_session_task_file(session_id: str) -> str:
    if not session_id:
        return ""
    try:
        marker = SESSION_TASKS_DIR / session_id
        if marker.is_file():
            name = marker.read_text(encoding="utf-8").strip()
            if name:
                return name
    except Exception:
        pass
    return ""


def _resolve_task(session_id: str = "") -> str:
    """Resolve the task name for THIS session's brief.

    All signals are per-terminal, so one terminal cannot pollute another's brief:
        1. ~/.claude/.session_tasks/<session_id>  (this session's marker)
        2. cwd → registry owner                   (cwd is terminal-specific)
    The global ~/.claude/.current_task is an informational marker only and is
    NOT consulted; nor do we blindly fall back to active_tasks[0] (a global guess
    unrelated to this terminal). No per-terminal match → "unknown".
    """
    session_task = _read_session_task_file(session_id or os.environ.get("CLAUDE_CODE_SESSION_ID", ""))
    if session_task:
        return session_task
    try:
        from _task_resolver import load_registry, resolve_task_owner
        t = resolve_task_owner(os.getcwd(), load_registry())
        if t:
            return t
    except Exception:
        pass
    return "unknown"




def _run_policy_fact(user_msg: str) -> str | None:
    """Return a compact Policy Brief YAML for common governance decision questions.

    This is intentionally deterministic and fail-open.  It makes retrieve_inject
    useful for "can/should I do X" prompts without waiting for semantic retrieval
    or relying on reranker threshold calibration.
    """
    if os.environ.get("HARNESS_POLICY_FACT_INJECT", "1") == "0":
        return None
    started = time.perf_counter()
    try:
        from policy_fact import match_policy_fact
        match = match_policy_fact(user_msg)
    except Exception:
        return None
    if (time.perf_counter() - started) > POLICY_FACT_MAX_ELAPSED_SEC:
        return None
    if match is None:
        return None
    return match.to_yaml_like()

def _yaml_scalar(value: object) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", "\n", "'", '"']):
        return json.dumps(text, ensure_ascii=False)
    return text


def _format_rag_brief(result: dict) -> str | None:
    """Format delivered gm.search pointers for hook injection.

    Abstained or pointerless results intentionally produce no brief: low-quality
    hook context is worse than no context.
    """
    if result.get("abstained") or not result.get("hit"):
        return None
    pointers = [p for p in result.get("pointers") or [] if isinstance(p, dict)]
    if not pointers:
        return None
    diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
    timings = diagnostics.get("timings") if isinstance(diagnostics.get("timings"), dict) else {}
    gate = ((result.get("debug") or {}).get("deliver_gate") or {}) if isinstance(result.get("debug"), dict) else {}
    lines = [
        "source: gm.search",
        f"delivery_profile: {_yaml_scalar(result.get('delivery_profile') or diagnostics.get('delivery_profile') or 'interactive_hook')}",
        f"confidence: {result.get('confidence', 0.0)}",
        f"abstain_threshold: {gate.get('rerank_abstain_threshold')}",
        f"best_reranker_score: {gate.get('best_reranker_score')}",
        f"latency_ms: {diagnostics.get('elapsed_ms', timings.get('backend_ms', 0.0))}",
        "pointers:",
    ]
    for pointer in pointers[:2]:
        lines.append(f"  - path: {_yaml_scalar(pointer.get('path') or '')}")
        if pointer.get("summary"):
            lines.append(f"    summary: {_yaml_scalar(pointer.get('summary'))}")
        elif pointer.get("why"):
            lines.append(f"    why: {_yaml_scalar(pointer.get('why'))}")
        if pointer.get("reranker_score") is not None:
            lines.append(f"    reranker_score: {pointer.get('reranker_score')}")
        if pointer.get("semantic_confidence") is not None:
            lines.append(f"    semantic_confidence: {pointer.get('semantic_confidence')}")
    return "\n".join(lines) + "\n"


def _query_id(*, ts: str, session_id: str, user_msg: str) -> str:
    seed = "\x1f".join([ts, session_id or "", user_msg or ""])
    return hashlib.sha1(seed.encode("utf-8", errors="replace")).hexdigest()[:16]


def _result_debug(result: dict) -> dict:
    return result.get("debug") if isinstance(result.get("debug"), dict) else {}


def _result_gate(result: dict) -> dict:
    debug = _result_debug(result)
    return debug.get("deliver_gate") if isinstance(debug.get("deliver_gate"), dict) else {}


def _result_thresholds(result: dict) -> dict:
    debug = _result_debug(result)
    return debug.get("thresholds") if isinstance(debug.get("thresholds"), dict) else {}


def _top_candidate_scores(result: dict) -> list[dict[str, object]]:
    debug = _result_debug(result)
    candidates = debug.get("top_candidates") if isinstance(debug.get("top_candidates"), list) else []
    out: list[dict[str, object]] = []
    for candidate in candidates[:5]:
        if not isinstance(candidate, dict):
            continue
        out.append({
            "path": candidate.get("path"),
            "raw_cosine": candidate.get("raw_cosine"),
            "retrieval_score": candidate.get("retrieval_score"),
            "reranker_score": candidate.get("reranker_score"),
            "evidence_class": candidate.get("evidence_class"),
        })
    if out:
        return out
    raw = result.get("raw") if isinstance(result.get("raw"), dict) else {}
    for pointer in (raw.get("pointers") or result.get("pointers") or [])[:5]:
        if not isinstance(pointer, dict):
            continue
        signals = pointer.get("signals") if isinstance(pointer.get("signals"), dict) else {}
        out.append({
            "path": pointer.get("path"),
            "raw_cosine": signals.get("raw_cosine") if isinstance(signals, dict) else pointer.get("semantic_confidence"),
            "retrieval_score": pointer.get("retrieval_score"),
            "reranker_score": pointer.get("reranker_score"),
            "evidence_class": signals.get("evidence_class") if isinstance(signals, dict) else None,
        })
    return out


def _best_raw_cosine_from_result(result: dict) -> float | None:
    debug = _result_debug(result)
    value = debug.get("best_raw_cosine")
    if isinstance(value, (int, float)):
        return float(value)
    scores = [item.get("raw_cosine") for item in _top_candidate_scores(result)]
    numeric = [float(score) for score in scores if isinstance(score, (int, float))]
    return max(numeric) if numeric else None


def _sidecar_status_from_result(result: dict) -> str:
    if result.get("sidecar_status"):
        return str(result.get("sidecar_status") or "")
    diagnostics = result.get("diagnostics") if isinstance(result.get("diagnostics"), dict) else {}
    sidecar = diagnostics.get("sidecar") if isinstance(diagnostics.get("sidecar"), dict) else {}
    return str(sidecar.get("status") or "")


def _decision_reason(result: dict) -> str:
    if result.get("abstained"):
        return f"abstain:{result.get('abstain_reason') or 'unknown'}"
    if not result.get("hit"):
        return "no_hit"
    pointers = [p for p in result.get("pointers") or [] if isinstance(p, dict)]
    if pointers:
        return "inject"
    return "hit_without_pointer"


def _sidecar_unavailable_result(reason: str) -> dict:
    return {
        "tool": "gm.search",
        "hit": False,
        "count": 0,
        "pointers": [],
        "abstained": True,
        "abstain_reason": "sidecar_unavailable",
        "delivery_profile": "interactive_hook",
        "diagnostics": {"sidecar": {"status": "unavailable", "error": reason}},
        "debug": {"deliver_gate": {"abstained": True, "abstain_reason": "sidecar_unavailable"}},
    }



def _write_rag_log(*, task_name: str, user_msg: str, result: dict, elapsed_ms: float, session_id: str, client: str) -> None:
    try:
        log_path = GLOBAL_MEMORY_LOGS_DIR / "retrieve_calls.jsonl"
        if is_runtime_logs_dir_in_repo(log_path.parent):
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        pointers = [p for p in result.get("pointers") or [] if isinstance(p, dict)]
        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        gate = _result_gate(result)
        thresholds = _result_thresholds(result)
        top_candidate_scores = _top_candidate_scores(result)
        record = {
            "ts": ts,
            "query_id": _query_id(ts=ts, session_id=session_id, user_msg=user_msg),
            "source": "gm.search",
            "client": client,
            "hook_session_id": session_id,
            "task_name": task_name,
            "query": user_msg,
            "hit_count": len(pointers),
            "hit": bool(result.get("hit")),
            "abstained": bool(result.get("abstained")),
            "abstain_reason": result.get("abstain_reason") or "",
            "delivery_profile": result.get("delivery_profile") or (result.get("diagnostics") or {}).get("delivery_profile"),
            "elapsed_ms": round(elapsed_ms, 3),
            "top_refs": [str(p.get("path")) for p in pointers[:3] if p.get("path")],
            "best_raw_cosine": _best_raw_cosine_from_result(result),
            "best_reranker_score": gate.get("best_reranker_score"),
            "rerank_threshold": gate.get("rerank_abstain_threshold", thresholds.get("rerank_abstain_threshold")),
            "pre_rerank_threshold": thresholds.get("pre_rerank_min_raw_cosine"),
            "top_candidate_paths": [str(item.get("path")) for item in top_candidate_scores if item.get("path")],
            "top_candidate_scores": top_candidate_scores,
            "sidecar_status": _sidecar_status_from_result(result),
            "decision_reason": _decision_reason(result),
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass



class SidecarUnavailable(RuntimeError):
    """Raised when the loopback sidecar is not reachable from the hook."""


def _sidecar_host() -> str:
    return os.environ.get("GM_SEARCH_SIDECAR_HOST", DEFAULT_SIDECAR_HOST).strip() or DEFAULT_SIDECAR_HOST


def _sidecar_port() -> int:
    raw = os.environ.get("GM_SEARCH_SIDECAR_PORT", str(DEFAULT_SIDECAR_PORT)).strip()
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_SIDECAR_PORT


def _sidecar_url() -> str:
    override = os.environ.get("GM_SEARCH_SIDECAR_URL", "").strip()
    if override:
        return override
    return f"http://{_sidecar_host()}:{_sidecar_port()}/v1/hook/search"


def _sidecar_health_url() -> str:
    return f"http://{_sidecar_host()}:{_sidecar_port()}/health"


def _sidecar_python() -> Path:
    raw = os.environ.get("GM_SEARCH_SIDECAR_PYTHON", "").strip()
    return Path(raw) if raw else DEFAULT_SIDECAR_PYTHON


def _sidecar_start_stamp_path() -> Path:
    return GLOBAL_MEMORY_LOGS_DIR / "gm_search_sidecar_start_attempt.json"


def _sidecar_start_log_path() -> Path:
    return GLOBAL_MEMORY_LOGS_DIR / "gm_search_sidecar_start.log"


def _sidecar_cooldown_path() -> Path:
    return GLOBAL_MEMORY_LOGS_DIR / "gm_search_sidecar_cooldown.json"


def _read_sidecar_cooldown_state() -> dict:
    try:
        path = _sidecar_cooldown_path()
        if is_runtime_logs_dir_in_repo(path.parent) or not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_sidecar_cooldown_state(state: dict) -> None:
    try:
        path = _sidecar_cooldown_path()
        if is_runtime_logs_dir_in_repo(path.parent):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def _clear_sidecar_cooldown_state() -> None:
    try:
        path = _sidecar_cooldown_path()
        if is_runtime_logs_dir_in_repo(path.parent):
            return
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _iso_from_epoch(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(epoch))


def _sidecar_cooling_down() -> bool:
    state = _read_sidecar_cooldown_state()
    until = state.get("cooldown_until_epoch")
    try:
        return float(until) > time.time()
    except Exception:
        return False


def _sidecar_cooldown_result() -> dict:
    return {
        "tool": "gm.search",
        "hit": False,
        "count": 0,
        "pointers": [],
        "abstained": True,
        "abstain_reason": "sidecar_cooldown",
        "delivery_profile": "interactive_hook",
        "diagnostics": {"sidecar": {"status": "cooldown"}},
        "debug": {"deliver_gate": {"abstained": True, "abstain_reason": "sidecar_cooldown"}},
    }


def _sidecar_failure_reason(result: dict) -> str | None:
    status = _sidecar_status_from_result(result)
    if status == "degraded":
        return "sidecar_degraded"
    reason = str(result.get("abstain_reason") or "")
    if reason.startswith("sidecar_degraded:") or reason.startswith("reranker_fallback:timeout_ms_exceeded"):
        return reason
    return None


def _record_sidecar_failure(reason: str) -> None:
    state = _read_sidecar_cooldown_state()
    count = int(state.get("failure_count") or 0) + 1
    now = time.time()
    payload = {
        "failure_count": count,
        "last_reason": reason,
        "last_failure_at": _iso_from_epoch(now),
        "cooling_down": False,
    }
    if count >= SIDECAR_COOLDOWN_FAILURE_THRESHOLD:
        until = now + SIDECAR_COOLDOWN_SEC
        payload.update({
            "cooling_down": True,
            "cooldown_until": _iso_from_epoch(until),
            "cooldown_until_epoch": until,
        })
    _write_sidecar_cooldown_state(payload)


def _record_sidecar_success(result: dict) -> None:
    if _sidecar_failure_reason(result) is None:
        _clear_sidecar_cooldown_state()


def _recent_sidecar_start_attempt() -> bool:
    try:
        stamp = _sidecar_start_stamp_path()
        if is_runtime_logs_dir_in_repo(stamp.parent) or not stamp.exists():
            return False
        data = json.loads(stamp.read_text(encoding="utf-8"))
        # Prefer the absolute epoch ("time") field: time.monotonic() resets on
        # reboot, so a pre-reboot stamp would keep (monotonic - last) permanently
        # negative and throttle sidecar starts forever. Fall back to monotonic
        # only when "time" is absent, and treat a non-positive delta as stale.
        abs_last = float(data.get("time") or 0.0)
        if abs_last > 0:
            return (time.time() - abs_last) < SIDECAR_START_THROTTLE_SEC
        last = float(data.get("monotonic", 0.0))
        delta = time.monotonic() - last
        return 0 < delta < SIDECAR_START_THROTTLE_SEC
    except Exception:
        return False


def _mark_sidecar_start_attempt(status: str, **extra: object) -> None:
    try:
        stamp = _sidecar_start_stamp_path()
        if is_runtime_logs_dir_in_repo(stamp.parent):
            return
        stamp.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "time": time.time(),  # absolute epoch; immune to reboot monotonic reset
            "monotonic": time.monotonic(),
            "status": status,
            **extra,
        }
        stamp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def _sidecar_env() -> dict[str, str]:
    env = os.environ.copy()
    repo = str(HARNESS_ROOT.parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = repo if not existing else repo + os.pathsep + existing
    env.setdefault("GLOBAL_MEMORY_DIR", repo)
    env["GM_SEARCH_REWRITE"] = "off"
    env["GM_SEARCH_RERANKER"] = "sentence-transformers"
    env["GM_SEARCH_RERANK_MODEL"] = "Qwen/Qwen3-Reranker-0.6B"
    return env


def _start_sidecar_fire_and_forget() -> None:
    if _recent_sidecar_start_attempt():
        _trace("sidecar_start_throttled")
        return
    python = _sidecar_python()
    if not python.exists():
        _mark_sidecar_start_attempt("missing_python", python=str(python))
        _trace("sidecar_start_missing_python", python=str(python))
        return
    try:
        log_path = _sidecar_start_log_path()
        if is_runtime_logs_dir_in_repo(log_path.parent):
            return
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("ab")
        cmd = [
            str(python),
            "-m",
            "harness.gm_mcp.sidecar",
            "--host",
            _sidecar_host(),
            "--port",
            str(_sidecar_port()),
        ]
        creationflags = 0
        for name in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
            creationflags |= int(getattr(subprocess, name, 0))
        proc = subprocess.Popen(
            cmd,
            cwd=str(HARNESS_ROOT.parent),
            env=_sidecar_env(),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            close_fds=True,
            creationflags=creationflags,
        )
        log_file.close()
        _mark_sidecar_start_attempt("started", pid=proc.pid, python=str(python), port=_sidecar_port())
        _trace("sidecar_start_started", pid=proc.pid, python=str(python), port=_sidecar_port())
    except Exception as exc:
        _mark_sidecar_start_attempt("error", error=str(exc), python=str(python))
        _trace("sidecar_start_error", error=str(exc))


def _sidecar_probe() -> str:
    """Probe the sidecar /health with a short timeout; returns status string.

    Returns "ready" | "warming" | "degraded" | "cold" | "unreachable".
    Used to avoid treating a cold-starting sidecar as a hard failure.
    """
    url = _sidecar_health_url()
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:  # noqa: S310 - loopback only
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
            if isinstance(payload, dict):
                status = str(payload.get("status") or "")
                if status in ("ready", "warming", "degraded", "cold"):
                    return status
        return "unreachable"
    except Exception:
        return "unreachable"


def _request_sidecar(task_name: str, user_msg: str, session_id: str, client: str) -> dict:
    payload = {
        "query": user_msg,
        "session_id": session_id,
        "client": client,
        "task_name": task_name,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        _sidecar_url(),
        data=data,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as response:  # noqa: S310 - loopback sidecar only
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code in {502, 503, 504}:
            raise SidecarUnavailable(str(exc)) from exc
        return {}
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise SidecarUnavailable(str(exc)) from exc
    try:
        result = json.loads(raw)
    except Exception as exc:
        raise SidecarUnavailable(f"invalid_json:{exc}") from exc
    return result if isinstance(result, dict) else {}


def _run_retrieve_cold(task_name: str, user_msg: str, session_id: str = "", client: str = "") -> str | None:
    """Diagnostic-only in-process fallback; disabled unless explicitly allowed."""
    try:
        from harness.gm_mcp import search as gm_search
    except Exception:
        return None

    t0 = time.perf_counter()
    try:
        result = gm_search.search(
            user_msg,
            top=2,
            intent_top=1,
            max_delivered_unique_paths=2,
            delivery_profile=gm_search.HOOK_DELIVERY_PROFILE,
        )
    except Exception:
        return None
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    _write_rag_log(
        task_name=task_name,
        user_msg=user_msg,
        result=result,
        elapsed_ms=elapsed_ms,
        session_id=session_id,
        client=client,
    )
    return _format_rag_brief(result)


def _run_retrieve(task_name: str, user_msg: str, session_id: str = "", client: str = "") -> str | None:
    """Call the warm gm.search sidecar. Returns brief yaml or None."""
    if _sidecar_cooling_down():
        _trace("sidecar_cooldown")
        _write_rag_log(
            task_name=task_name,
            user_msg=user_msg,
            result=_sidecar_cooldown_result(),
            elapsed_ms=0.0,
            session_id=session_id,
            client=client,
        )
        return None

    # Probe before requesting: a cold-starting sidecar (model warmup ~15-20s) is
    # not a failure — hitting it with the 1.2s request timeout would record a
    # failure and enter cooldown, making it impossible to ever come up. Instead
    # abstain (no brief, no failure) and let the start attempt proceed.
    probe = _sidecar_probe()
    if probe != "ready":
        _trace("sidecar_not_ready", probe=probe)
        if probe == "unreachable":
            _start_sidecar_fire_and_forget()
        return None

    t0 = time.perf_counter()
    try:
        result = _request_sidecar(task_name, user_msg, session_id, client)
    except SidecarUnavailable as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        reason = str(exc)
        _trace("sidecar_unavailable", error=reason, health_url=_sidecar_health_url())
        _record_sidecar_failure("sidecar_unavailable")
        _write_rag_log(
            task_name=task_name,
            user_msg=user_msg,
            result=_sidecar_unavailable_result(reason),
            elapsed_ms=elapsed_ms,
            session_id=session_id,
            client=client,
        )
        _start_sidecar_fire_and_forget()
        if os.environ.get("HARNESS_RAG_HOOK_ALLOW_COLD_FALLBACK", "0") == "1":
            return _run_retrieve_cold(task_name, user_msg, session_id=session_id, client=client)
        return None
    except Exception as exc:
        _trace("sidecar_error", error=str(exc))
        return None

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    failure_reason = _sidecar_failure_reason(result)
    if failure_reason:
        _record_sidecar_failure(failure_reason)
    else:
        _record_sidecar_success(result)
    _write_rag_log(
        task_name=task_name,
        user_msg=user_msg,
        result=result,
        elapsed_ms=elapsed_ms,
        session_id=session_id,
        client=client,
    )
    return _format_rag_brief(result)

def _trace(stage: str, **extra) -> None:
    try:
        p = GLOBAL_MEMORY_LOGS_DIR / "retrieve_inject_debug.log"
        if is_runtime_logs_dir_in_repo(p.parent):
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            kv = " ".join(f"{k}={v!r}" for k, v in extra.items())
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} HOOK {stage} {kv}\n")
    except Exception:
        pass


def main() -> None:
    _trace("entry", pid=os.getpid(), inject_env=os.environ.get("HARNESS_RETRIEVE_INJECT", "1"), log_env=os.environ.get("HARNESS_RETRIEVE_LOG", "1"))
    if os.environ.get("HARNESS_RETRIEVE_INJECT", "1") == "0":
        _trace("skip_disabled")
        return

    user_msg, session_id, client = _parse_stdin()
    _trace("parsed", msg_len=len(user_msg or ""), preview=(user_msg or "")[:60], client=client, session_id=session_id)
    if not user_msg or len(user_msg.strip()) < MIN_QUERY_LEN:
        _trace("skip_short")
        return

    if os.environ.get("HARNESS_RUNTIME_BRIEF_INJECT", "0") == "1":
        runtime_brief = build_runtime_brief(user_msg, logs_dir=GLOBAL_MEMORY_LOGS_DIR, harness_root=HARNESS_ROOT)
        if runtime_brief:
            _trace("runtime_brief", topic=runtime_brief_topic(user_msg))
            print("📌 Runtime Config Brief (deterministic current-state snapshot):")
            print("```yaml")
            print(runtime_brief.rstrip())
            print("```")
            return
    else:
        _trace("runtime_brief_disabled")

    t_start = time.perf_counter()
    task_name = _resolve_task(session_id)
    _trace("resolved", task=task_name)
    policy_yaml = _run_policy_fact(user_msg)
    brief_yaml = _run_retrieve(task_name, user_msg, session_id=session_id, client=client)
    elapsed = time.perf_counter() - t_start
    _trace("after_gm_search", elapsed_ms=round(elapsed*1000,1), has_policy=bool(policy_yaml), has_brief=bool(brief_yaml))

    if not policy_yaml and (elapsed > TIMEOUT_SEC or not brief_yaml):
        return

    if policy_yaml:
        print("📌 Policy Brief (deterministic anchored rule):")
        print("```yaml")
        print(policy_yaml.rstrip())
        print("```")
    if brief_yaml and elapsed <= TIMEOUT_SEC:
        print("📌 RAG Brief (auto-retrieved gm.search pointers):")
        print("```yaml")
        print(brief_yaml.rstrip())
        print("```")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
