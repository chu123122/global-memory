#!/usr/bin/env python3
"""
reconcile.py — 多数据源统一治理 (MVP: M1 manifest→doc 渲染)

设计见 docs/多数据源治理方案.md。核心 = 发现不枚举:
  扫全仓 RECONCILE 标记 → 运行时构建 cluster 集 → 按 pattern 派发。

标记格式 (markdown doc 内):
  <!-- RECONCILE: source=hook_manifest.json pattern=M1 renderer=hook_table -->
  ...(自动渲染区, 勿手改)...
  <!-- /RECONCILE -->

MVP 范围:
  - 扫标记 (动态 cluster, 非硬编码清单)
  - M1 ManifestRender: 已注册 renderer 从 source 渲染 doc 块
    已实现 renderer: hook_table (hook_manifest.json → 逐 hook 表)
  - --check 比对漂移 (退 2 if drift); --fix 重写块
  - --json 机器可读

未做 (留后续, 见治理方案 §8):
  - M2/M3/M4 模式; settings/bootstrap 渲染 (触 hook 安装链, 须确认)
  - meta-check 启发式 (疑似未标记镜像)
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        if getattr(_s, "encoding", None) != "utf-8" and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent.parent  # scripts/ → harness/ → repo
HARNESS = REPO / "harness"

MARKER_RE = re.compile(
    r"<!--\s*RECONCILE:\s*(?P<attrs>[^>]*?)-->\n(?P<body>.*?)\n?<!--\s*/RECONCILE\s*-->",
    re.DOTALL,
)


def parse_attrs(attrs: str) -> dict:
    return dict(re.findall(r"(\w+)=([^\s]+)", attrs))


# ---------- renderers (M1) ----------

def _nature(event: str, fa: str) -> str:
    if fa == "BLOCK":
        return "S1 阻断"
    if fa == "WARN":
        return "S2 软校验"
    if fa == "REPORT":
        return "S3 报告"
    if event == "UserPromptSubmit":
        return "注入(fail-open)"
    if event == "PostToolUse":
        return "只记/展示"
    return "被动"


def render_hook_table(source_path: Path) -> str:
    """hook_manifest.json → 逐 hook 表 (event|matcher|hook|failure_action|性质)"""
    data = json.loads(source_path.read_text(encoding="utf-8"))
    hooks = data.get("hooks", data)
    rows = ["| 事件 | matcher | hook | failure_action | 性质 |",
            "|------|---------|------|----------------|------|"]
    for event, groups in hooks.items():
        for g in groups:
            matcher = g.get("matcher", "") or "*"
            for h in g.get("hooks", []):
                path = h.get("path", "?")
                fa = h.get("failure_action", "NONE")
                rows.append(f"| {event} | `{matcher}` | `{path}` | {fa} | {_nature(event, fa)} |")
    return "\n".join(rows)


RENDERERS = {
    "hook_table": render_hook_table,
}


# ---------- engine ----------

def find_clusters() -> list[dict]:
    """扫全仓 .md 的 RECONCILE 标记 → cluster 列表"""
    clusters = []
    for md in REPO.rglob("*.md"):
        if "_archive" in md.parts or ".git" in md.parts:
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in MARKER_RE.finditer(text):
            a = parse_attrs(m.group("attrs"))
            clusters.append({
                "file": md, "attrs": a,
                "body": m.group("body"), "span": m.span(),
            })
    return clusters


def render_cluster(c: dict) -> tuple[bool, str, str]:
    """返回 (ok, rendered, note)。ok=False 表示无法渲染(未知 renderer/pattern)"""
    a = c["attrs"]
    if a.get("pattern") != "M1":
        return False, "", f"pattern={a.get('pattern')} 非 M1, MVP 跳过"
    rk = a.get("renderer")
    fn = RENDERERS.get(rk)
    if not fn:
        return False, "", f"无注册 renderer: {rk}"
    src = HARNESS / a["source"] if not a["source"].startswith(("/", "D:")) else Path(a["source"])
    if not src.exists():
        src = REPO / a["source"]
    if not src.exists():
        return False, "", f"source 不存在: {a['source']}"
    return True, fn(src), ""


# ---------- M3: 引用校验 (rules/ 跨层链接指针存在) ----------

_REF_RE = re.compile(r"`((?:\.\.?/)[^`<>*\s]+?\.(?:md|py|json|yaml)|[\w一-鿿]+\.md)`")


def run_m3_refcheck() -> list[dict]:
    """M3: 校验 rules/*.md 内 ../相对 或 同目录 .md 引用指针的目标存在。
    只查明确的本地路径(反引号包裹, 以 ../ 起 或 同目录 X.md), 跳过含 <>* 占位/绝对/~。"""
    out = []
    base = REPO / "rules"
    if not base.exists():
        return out
    for md in base.glob("*.md"):
        text = md.read_text(encoding="utf-8", errors="replace")
        for m in _REF_RE.finditer(text):
            ref = m.group(1)
            target = (md.parent / ref).resolve()
            if not target.exists():
                out.append({"file": str(md.relative_to(REPO)), "ref": ref, "status": "missing"})
    return out


# ---------- M2: 委托既有孤儿扫描 (不重写, 避免造新多源) ----------

def run_m2_delegate() -> dict:
    """M2: 调 scan_orphan_scripts.py(磁盘↔registry), surface verdict。不重实现。"""
    import subprocess
    script = HARNESS / "scripts" / "scan_orphan_scripts.py"
    try:
        r = subprocess.run([sys.executable, str(script), "--json"],
                           capture_output=True, text=True, encoding="utf-8", timeout=60)
        d = json.loads(r.stdout)
        return {"delegate": "scan_orphan_scripts", "unregistered": d.get("summary", {}).get("unregistered"),
                "stale": d.get("summary", {}).get("stale_in_registry")}
    except Exception as e:
        return {"delegate": "scan_orphan_scripts", "error": str(e)[:120]}


# ---------- meta-check: 疑似未标记镜像 (启发式, 仅 advisory) ----------

def run_meta_check() -> list[dict]:
    """启发式: docs/*.md 含 >=4 行引用 hooks/*.py|scripts/*.py 的表格但无 RECONCILE 标记
    → 疑似镜像 manifest/registry 却未治理。noisy, 仅提醒人看, 不影响退出码。
    白名单: scripts-registry.md(它是源不是镜像)。"""
    out = []
    base = REPO / "docs"
    wl = {"scripts-registry.md"}
    if not base.exists():
        return out
    pat = re.compile(r"(hooks|scripts)/\w+\.py")
    for md in base.glob("*.md"):
        if md.name in wl:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        if "RECONCILE" in text:
            continue
        if len(pat.findall(text)) >= 4:
            out.append({"file": str(md.relative_to(REPO)), "status": "suspected-unmarked-mirror",
                        "hint": "含多处 hooks/scripts 路径但无 RECONCILE 标记, 人工裁定是否纳入治理"})
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="reconcile 多源治理 (M1 渲染 + M2 委托 + M3 引用 + meta)")
    p.add_argument("--check", action="store_true", help="只读, 报漂移, 退 2 if drift/missing-ref")
    p.add_argument("--fix", action="store_true", help="重写 RECONCILE 块")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    if not (args.check or args.fix):
        args.check = True

    clusters = find_clusters()
    results = []
    drift = 0
    for c in clusters:
        ok, rendered, note = render_cluster(c)
        rel = str(c["file"].relative_to(REPO))
        cur = c["body"].strip()
        new = rendered.strip()
        if not ok:
            results.append({"file": rel, "source": c["attrs"].get("source"),
                            "status": "skip", "note": note})
            continue
        if cur == new:
            results.append({"file": rel, "source": c["attrs"].get("source"), "status": "ok"})
        else:
            drift += 1
            if args.fix:
                text = c["file"].read_text(encoding="utf-8")
                s, e = c["span"]
                head = text[:s]
                tail = text[e:]
                block = (f"<!-- RECONCILE: {c['attrs_raw'] if 'attrs_raw' in c else _reattr(c['attrs'])} -->\n"
                         f"{new}\n<!-- /RECONCILE -->")
                c["file"].write_text(head + block + tail, encoding="utf-8")
                results.append({"file": rel, "source": c["attrs"].get("source"), "status": "fixed"})
            else:
                results.append({"file": rel, "source": c["attrs"].get("source"),
                                "status": "drift", "note": "块内容 != manifest 渲染 (--fix 修)"})

    m3 = run_m3_refcheck()
    m2 = run_m2_delegate()
    meta = run_meta_check()

    report = {"clusters": len(clusters), "drift": drift, "results": results,
              "m3_refcheck": {"missing": len(m3), "items": m3},
              "m2_delegate": m2,
              "meta_check": {"suspected": len(meta), "items": meta}}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"[reconcile] M1: {len(clusters)} cluster, drift={drift}")
        for r in results:
            icon = {"ok": "✅", "fixed": "🔧", "drift": "❌", "skip": "⏭"}.get(r["status"], "?")
            print(f"  {icon} {r['status']:6} {r['file']}  ({r.get('source','')}) {r.get('note','')}")
        print(f"[reconcile] M3 引用校验: {len(m3)} missing")
        for r in m3:
            print(f"  ❌ {r['file']} → {r['ref']} (目标不存在)")
        print(f"[reconcile] M2 委托 scan_orphan: unregistered={m2.get('unregistered')} stale={m2.get('stale')}")
        print(f"[reconcile] meta-check: {len(meta)} 疑似未标记镜像 (advisory)")
        for r in meta:
            print(f"  ⚠ {r['file']}: {r['hint']}")
    # 退出码: M1 drift 或 M3 断链 → 2 (--check 模式)
    if args.check and (drift or m3):
        return 2
    return 0


def _reattr(a: dict) -> str:
    return " ".join(f"{k}={v}" for k, v in a.items())


if __name__ == "__main__":
    raise SystemExit(main())
