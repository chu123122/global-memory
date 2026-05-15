"""MD -> HTML converter for human-readable docs (需求分析.md / 设计文档.md).

Architecture: MD → markdown lib → section split → classifier → components → assembly.
CSS from open-design reference HTMLs (dark terminal aesthetic).

Usage:
    python md2html.py <file.md>              # single file
    python md2html.py <directory>/           # all .md in dir
    python md2html.py --no-ai <file.md>      # skip Haiku fallback
"""

import sys
import re
from pathlib import Path
from html import escape

import markdown

from md2html_classifier import classify
from md2html_components import render_section

CSS = r"""
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0a0e14;--bg-card:#111827;--bg-card-alt:#0f172a;--bg-hover:#1a2332;
  --bg-code:#0d1117;--surface:#111827;--surface-raised:#1a2332;
  --text:#e2e8f0;--text-sec:#94a3b8;--text-muted:#64748b;
  --fg:#e2e8f0;--fg-secondary:#94a3b8;--muted:#64748b;
  --border:#1e293b;--border-light:#2d3748;--border-subtle:#1e293b;
  --accent:#10b981;--accent-dim:rgba(16,185,129,.08);
  --blue:#3b82f6;--purple:#8b5cf6;--red:#ef4444;--amber:#f59e0b;--green:#10b981;
  --cyan:#06b6d4;--yellow:#d29922;
  --red-dim:rgba(239,68,68,.15);--green-dim:rgba(16,185,129,.15);--yellow-dim:rgba(210,153,34,.15);
  --radius:8px;--radius-lg:10px;
  --font-sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei','Source Han Sans SC',system-ui,sans-serif;
  --font-mono:'JetBrains Mono','Cascadia Code',ui-monospace,'SF Mono',Menlo,monospace;
}
html{font-family:var(--font-sans);background:var(--bg);color:var(--text);font-size:15px;line-height:1.75;-webkit-font-smoothing:antialiased;scroll-behavior:smooth}
body{min-height:100vh}
::selection{background:var(--accent);color:var(--bg)}
p{color:var(--text-sec);margin-bottom:.75rem}
h1{font-size:clamp(1.6rem,4vw,2.2rem);font-weight:700;letter-spacing:-.02em;line-height:1.2}
h2{font-size:1.15rem;font-weight:600;color:var(--text);margin-bottom:1.25rem;display:flex;align-items:center;gap:.6rem}
h2 .section-num{font-family:var(--font-mono);font-size:.75rem;color:var(--accent);background:var(--accent-dim);padding:.15rem .5rem;border-radius:4px;font-weight:500}
.mono{font-family:var(--font-mono);font-size:.8rem}

nav{position:sticky;top:0;z-index:100;background:rgba(10,14,20,.85);backdrop-filter:blur(12px);border-bottom:1px solid var(--border);padding:0 2rem;height:52px;display:flex;align-items:center;justify-content:space-between}
nav .breadcrumb{display:flex;align-items:center;gap:.5rem;font-size:.8rem;color:var(--text-muted);font-family:var(--font-mono)}
nav .breadcrumb .sep{opacity:.4}
nav .breadcrumb .current{color:var(--accent)}
nav a{color:var(--text-sec);text-decoration:none;font-size:.8rem;font-family:var(--font-mono);transition:color .2s}
nav a:hover{color:var(--accent)}

.container{max-width:1080px;margin:0 auto;padding:2rem 1.5rem 4rem}
section{margin-bottom:3rem}

.doc-header{padding:2.5rem 0 2rem;border-bottom:1px solid var(--border);margin-bottom:2.5rem}
.doc-meta{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem;flex-wrap:wrap}
.doc-date{font-size:.8rem;color:var(--text-muted);font-family:var(--font-mono)}
.doc-subtitle{font-size:.95rem;color:var(--text-sec);max-width:640px;margin-top:.5rem}

.badge{font-size:.7rem;font-family:var(--font-mono);padding:.2rem .6rem;border-radius:4px;font-weight:500;text-transform:uppercase;letter-spacing:.04em;display:inline-flex;align-items:center;gap:5px}
.badge-p0{background:rgba(239,68,68,.12);color:var(--red);border:1px solid rgba(239,68,68,.2)}
.badge-p1{background:rgba(245,158,11,.12);color:var(--amber);border:1px solid rgba(245,158,11,.2)}
.badge-p2{background:rgba(59,130,246,.12);color:var(--blue);border:1px solid rgba(59,130,246,.2)}
.badge-ok{background:rgba(16,185,129,.12);color:var(--green);border:1px solid rgba(16,185,129,.2)}
.badge-warn{background:rgba(245,158,11,.12);color:var(--amber);border:1px solid rgba(245,158,11,.2)}
.badge-danger{background:rgba(239,68,68,.1);color:var(--red);border:1px solid rgba(239,68,68,.15)}
.badge-safe{background:rgba(16,185,129,.1);color:var(--green);border:1px solid rgba(16,185,129,.15)}
.badge-discussion{background:rgba(139,92,246,.12);color:var(--purple);border:1px solid rgba(139,92,246,.2)}
.badge-phase{background:rgba(6,182,212,.12);color:var(--cyan);border:1px solid rgba(6,182,212,.2)}
.badge-todo{background:rgba(100,116,139,.12);color:var(--text-muted);border:1px solid rgba(100,116,139,.2)}

.card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.5rem}
.card p{margin-bottom:.5rem}
.card p:last-child{margin-bottom:0}
.card ul,.card ol{margin:.5rem 0 .5rem 1.5rem;color:var(--text-sec);font-size:.85rem}
.card li{margin-bottom:.35rem;line-height:1.6}
.card li::marker{color:var(--accent)}
.card h3{font-size:.95rem;font-weight:600;margin-bottom:.5rem}
.card code{font-family:var(--font-mono);font-size:.8rem;background:var(--bg);padding:.15rem .4rem;border-radius:3px;color:var(--accent)}
.card blockquote{border-left:3px solid var(--cyan);padding:.5rem 1rem;margin:.5rem 0;color:var(--text-sec);background:rgba(6,182,212,.05);border-radius:0 6px 6px 0}

pre{background:var(--bg-code);border:1px solid var(--border);border-radius:var(--radius);padding:1rem 1.25rem;overflow-x:auto;margin:.75rem 0;font-family:var(--font-mono);font-size:.8rem;line-height:1.7;color:var(--text-sec);tab-size:4}
pre code{background:none;padding:0;color:inherit;font-size:inherit;border-radius:0}
code{font-family:var(--font-mono);font-size:.8rem;background:var(--bg);padding:.15rem .4rem;border-radius:3px;color:var(--accent)}

.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}
.metric-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.25rem;position:relative;overflow:hidden}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.metric-card:nth-child(1)::before{background:var(--accent)}
.metric-card:nth-child(2)::before{background:var(--blue)}
.metric-card:nth-child(3)::before{background:var(--red)}
.metric-card:nth-child(4)::before{background:var(--purple)}
.metric-card:nth-child(5)::before{background:var(--amber)}
.metric-card:nth-child(6)::before{background:var(--cyan)}
.metric-label{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:8px;font-family:var(--font-mono)}
.metric-value{font-size:clamp(1.5rem,3vw,2.2rem);font-weight:700;font-family:var(--font-mono);line-height:1;font-variant-numeric:tabular-nums}
.metric-value .unit{font-size:.7rem;font-weight:400;color:var(--text-muted);margin-left:.15rem}
.metric-desc{font-size:12px;color:var(--muted);margin-top:8px;font-family:var(--font-mono)}

.info-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.info-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.info-label{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-family:var(--font-mono);flex-shrink:0}
.info-value{font-size:13px;text-align:right;font-family:var(--font-mono);word-break:break-all}

.problems{display:grid;gap:1rem}
.problem-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.25rem 1.5rem;display:grid;grid-template-columns:auto 1fr;gap:1rem;align-items:start}
.problem-card .priority{display:flex;align-items:center;justify-content:center}
.problem-card h3{font-size:.95rem;font-weight:600;margin-bottom:.35rem;display:flex;align-items:center;gap:.5rem}
.problem-card .desc{font-size:.8rem;color:var(--text-sec);line-height:1.6}
.problem-card .impact{font-size:.75rem;color:var(--text-muted);margin-top:.5rem;font-family:var(--font-mono);padding-top:.5rem;border-top:1px solid var(--border)}

.phases{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem;margin:1.5rem 0}
.phase-card{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.25rem;position:relative;overflow:hidden;transition:border-color .2s}
.phase-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.phase-card.done::before{background:var(--green)}
.phase-card.active::before{background:var(--cyan)}
.phase-card.pending::before{background:var(--border-light)}
.phase-card.done{border-color:rgba(16,185,129,.25)}
.phase-num{font-family:var(--font-mono);font-size:.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.4rem;display:flex;align-items:center;gap:.5rem}
.phase-title{font-size:1rem;font-weight:600;margin-bottom:.5rem}
.phase-desc{font-size:.8rem;color:var(--text-sec);line-height:1.6}
.phase-items{list-style:none;margin-top:.75rem;padding:0}
.phase-items li{font-size:.75rem;color:var(--text-sec);padding:.2rem 0 .2rem 1rem;position:relative;font-family:var(--font-mono)}
.phase-items li::before{content:'›';position:absolute;left:0;color:var(--text-muted)}

.scope-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
.scope-col{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.25rem}
.scope-col h3{font-size:.85rem;font-weight:600;margin-bottom:.75rem;display:flex;align-items:center;gap:.4rem}
.scope-col ul{list-style:none;padding:0}
.scope-col li{font-size:.8rem;color:var(--text-sec);padding:.35rem 0 .35rem 1.25rem;position:relative;line-height:1.5}
.scope-col li::before{content:'';position:absolute;left:0;top:.65rem;width:6px;height:6px;border-radius:50%}
.scope-in li::before{background:var(--green)}
.scope-out li::before{background:var(--red);opacity:.6}

.risk-compare{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:1.5rem 0}
.risk-col{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-lg);padding:1.25rem;position:relative;overflow:hidden}
.risk-col::before{content:'';position:absolute;top:0;left:0;right:0;height:2px}
.risk-col.danger::before{background:var(--red)}
.risk-col.safe::before{background:var(--green)}
.risk-col h3{font-size:.9rem;font-weight:600;margin-bottom:.75rem;display:flex;align-items:center;gap:.4rem}
.risk-col ul{list-style:none;padding:0}
.risk-col li{font-size:.8rem;color:var(--text-sec);padding:.35rem 0 .35rem 1.25rem;position:relative;line-height:1.5}
.risk-col.danger li::before{content:'✕';position:absolute;left:0;color:var(--red);font-size:.7rem;top:.45rem}
.risk-col.safe li::before{content:'✓';position:absolute;left:0;color:var(--green);font-size:.7rem;top:.45rem}

.criteria-list{list-style:none;padding:0}
.criteria-item{font-size:.85rem;color:var(--text-sec);padding:.5rem 0;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:.75rem}
.criteria-item:last-child{border-bottom:none}
.criteria-check{color:var(--accent);font-size:1rem;flex-shrink:0}

.table-wrap{overflow-x:auto;margin:1rem 0;border-radius:var(--radius-lg);border:1px solid var(--border)}
table{width:100%;border-collapse:collapse;font-size:.85rem}
thead{background:var(--bg-card-alt)}
th{text-align:left;padding:.7rem 1rem;font-weight:600;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);font-family:var(--font-mono);border-bottom:1px solid var(--border);white-space:nowrap}
td{padding:.7rem 1rem;border-bottom:1px solid var(--border-subtle);color:var(--text-sec);vertical-align:top}
tr:last-child td{border-bottom:none}
tbody tr{transition:background .15s}
tbody tr:hover{background:var(--bg-hover)}

.flow{display:flex;align-items:stretch;gap:0;margin:1.5rem 0;overflow-x:auto;padding:.5rem 0}
.flow-node{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:1rem 1.25rem;min-width:140px;text-align:center;flex-shrink:0}
.flow-node.highlight{border-color:var(--accent);box-shadow:0 0 20px rgba(16,185,129,.08)}
.flow-node-label{font-size:.85rem;font-weight:600;margin-bottom:.35rem}
.flow-node-desc{font-size:.7rem;color:var(--text-muted);font-family:var(--font-mono)}
.flow-arrow{display:flex;align-items:center;padding:0 .5rem;color:var(--text-muted);font-size:1.2rem;flex-shrink:0;font-family:var(--font-mono)}

.seq-diagram{background:var(--bg-code);border:1px solid var(--border);border-radius:var(--radius);padding:1.5rem;overflow-x:auto;margin:1.5rem 0}
.seq-diagram pre{font-family:var(--font-mono);font-size:.72rem;line-height:1.65;color:var(--text-sec);white-space:pre;margin:0}

.code-compare{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin:1.5rem 0}
.code-block{background:var(--bg-code);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.code-header{display:flex;align-items:center;justify-content:space-between;padding:.5rem 1rem;border-bottom:1px solid var(--border);background:var(--bg-card-alt)}
.code-header span{font-size:.7rem;font-family:var(--font-mono);color:var(--text-muted);text-transform:uppercase;letter-spacing:.04em}
.code-body{padding:1rem;overflow-x:auto}
.code-body pre{font-family:var(--font-mono);font-size:.75rem;line-height:1.7;color:var(--text-sec);white-space:pre;tab-size:4;margin:0}

.timeline{position:relative;padding-left:2rem;margin:1.5rem 0}
.timeline::before{content:'';position:absolute;left:.45rem;top:0;bottom:0;width:1px;background:var(--border)}
.tl-item{position:relative;padding-bottom:1.75rem}
.tl-item:last-child{padding-bottom:0}
.tl-dot{position:absolute;left:-1.55rem;top:.35rem;width:10px;height:10px;border-radius:50%;border:2px solid var(--border);background:var(--bg)}
.tl-item.active .tl-dot{border-color:var(--accent);background:var(--accent);box-shadow:0 0 8px rgba(16,185,129,.4)}
.tl-item.done .tl-dot{border-color:var(--green);background:var(--green)}
.tl-phase{font-size:.7rem;font-family:var(--font-mono);color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em}
.tl-title{font-size:.9rem;font-weight:600;margin:.2rem 0}
.tl-desc{font-size:.8rem;color:var(--text-sec)}

.callout{background:var(--bg-card);border:1px solid var(--border);border-left:3px solid var(--cyan);border-radius:0 var(--radius) var(--radius) 0;padding:1rem 1.25rem;margin:1rem 0}
.callout p{margin-bottom:0}
.callout .label{font-size:.7rem;font-family:var(--font-mono);color:var(--cyan);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.35rem}

/* PAGE LAYOUT */
.page-layout{display:grid;grid-template-columns:220px 1fr;min-height:100vh}
.sidebar{position:sticky;top:52px;height:calc(100vh - 52px);overflow-y:auto;border-right:1px solid var(--border);padding:1.5rem 0;background:var(--bg)}
.sidebar-nav{list-style:none;padding:0}
.sidebar-nav a{display:block;padding:.4rem 1.25rem;font-size:.75rem;color:var(--text-muted);text-decoration:none;border-left:2px solid transparent;transition:all .15s;font-family:var(--font-mono);line-height:1.4}
.sidebar-nav a:hover{color:var(--text-sec);background:var(--bg-card)}
.sidebar-nav a.active{color:var(--accent);border-left-color:var(--accent);background:var(--accent-dim)}

/* PROGRESS BAR */
#progress-bar{position:fixed;top:0;left:0;height:3px;background:var(--accent);z-index:200;width:0;transition:width .1s linear}

/* CODE FIGURE */
.code-figure{margin:.75rem 0;border:1px solid var(--border);border-radius:var(--radius);overflow:hidden}
.code-figure figcaption{padding:.4rem 1rem;background:var(--bg-card-alt);border-bottom:1px solid var(--border);font-size:.65rem;font-family:var(--font-mono);color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em}
.code-figure pre{border:none;border-radius:0;margin:0}

/* SUMMARY METRICS */
.summary-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2.5rem}

/* DETAILS / COLLAPSIBLE (B2) */
details{margin:.5rem 0}
details>summary{cursor:pointer;font-size:.75rem;color:var(--text-muted);font-family:var(--font-mono);padding:.4rem 0;user-select:none}
details[open]>summary{margin-bottom:.5rem}

/* LIST GRID (B3) */
.list-grid{display:grid;grid-template-columns:1fr 1fr;gap:.5rem;list-style:none;padding:0;margin:.5rem 0}
.list-grid li{font-size:.85rem;color:var(--text-sec);padding:.35rem .5rem .35rem 1.25rem;position:relative;line-height:1.6}
.list-grid li::before{content:'›';position:absolute;left:0;color:var(--accent)}

/* METRIC INLINE (C3) */
.metric-inline{font-family:var(--font-mono);color:var(--accent);font-weight:600}

/* SUB-CONTENT inside prose sub-cards */
.sub-content{margin-top:.5rem}

footer{border-top:1px solid var(--border);padding:2rem 0;text-align:center;font-size:.7rem;color:var(--text-muted);font-family:var(--font-mono)}

@media(max-width:768px){
  .metrics{grid-template-columns:repeat(2,1fr)}
  .phases{grid-template-columns:1fr}
  .code-compare,.risk-compare,.scope-grid{grid-template-columns:1fr}
  .flow{flex-direction:column;align-items:stretch}
  .flow-arrow{transform:rotate(90deg);padding:.25rem 0;justify-content:center}
  .container{padding:1.25rem 1rem 3rem}
  nav{padding:0 1rem}
  .page-layout{grid-template-columns:1fr}
  .sidebar{display:none}
  .summary-metrics{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:480px){
  .metrics{grid-template-columns:1fr}
  .problem-card{grid-template-columns:1fr}
  .info-grid{grid-template-columns:1fr}
}
@media print{
  nav,.fab{display:none!important}
  .container{max-width:100%;padding:0}
  body{background:#fff;color:#000}
}
"""


def extract_doc_type(title: str) -> str:
    if "需求" in title or "Requirement" in title.lower():
        return "需求分析"
    if "设计" in title or "Design" in title.lower():
        return "设计文档"
    if "测试" in title or "Test" in title.lower():
        return "测试报告"
    return "文档"


def extract_meta(html: str) -> tuple[list[dict], str]:
    """Extract metadata from leading blockquote."""
    cards: list[dict] = []
    bq = re.match(r"(<blockquote>\s*<p>)(.*?)(</p>\s*</blockquote>)", html, re.S)
    if not bq:
        return cards, html

    content = bq.group(2)
    lines = content.split("<br />") if "<br />" in content else content.split("\n")

    keywords = {
        "文档类型": "类型", "创建": "创建", "Status": "状态", "状态": "状态",
        "任务目录": "目录", "配套": "配套", "本文档定位": "定位",
        "更新": "更新", "版本": "版本", "作者": "作者",
    }

    for line in lines:
        text = re.sub(r"<[^>]+>", "", line).strip()
        if not text:
            continue
        for key, label in keywords.items():
            if key in text:
                val = text.split("：", 1)[-1].strip() if "：" in text else text.split(":", 1)[-1].strip()
                cards.append({"label": label, "value": val})
                break

    return cards, html[bq.end():]


def build_meta_badges(cards: list[dict]) -> str:
    if not cards:
        return ""
    parts = []
    for c in cards:
        v = c.get("value", "").lower()
        cls = "badge-discussion"
        if any(w in v for w in ["discussion", "讨论", "draft"]):
            cls = "badge-discussion"
        elif any(w in v for w in ["implementation", "实现", "进行"]):
            cls = "badge-phase"
        elif any(w in v for w in ["done", "完成", "approved"]):
            cls = "badge-ok"
        parts.append(f'<span class="badge {cls}">{escape(c.get("label", ""))}: {escape(c.get("value", ""))}</span>')
    return "\n".join(parts)


def split_sections(html: str) -> list[tuple[str, str]]:
    """Split HTML by h2 headings into (heading_text, body_html) pairs."""
    parts = re.split(r"<h2[^>]*>(.*?)</h2>", html, flags=re.S)

    sections = []
    if parts[0].strip():
        sections.append(("", parts[0]))

    for i in range(1, len(parts), 2):
        heading = re.sub(r"<[^>]+>", "", parts[i]).strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((heading, body))

    return sections


def build_toc(sections: list[tuple[str, str]]) -> str:
    items = []
    idx = 0
    for heading, _ in sections:
        if not heading:
            continue
        idx += 1
        slug = f"section-{idx}"
        display = heading[:28] + "…" if len(heading) > 30 else heading
        items.append(f'<li><a href="#{slug}" data-section="{slug}">{escape(display)}</a></li>')
    if not items:
        return ""
    return f'<aside class="sidebar"><nav><ul class="sidebar-nav">{"".join(items)}</ul></nav></aside>'


def extract_summary_metrics(sections: list[tuple[str, str]], max_count: int = 4) -> str:
    from md2html_components import _strip_tags, ACCENT_COLORS
    metrics: list[tuple[str, str, str]] = []
    for heading, body in sections:
        clean = re.sub(r"<pre[^>]*>.*?</pre>", "", body, flags=re.S)
        clean = re.sub(r"<code[^>]*>.*?</code>", "", clean, flags=re.S)
        text = _strip_tags(clean)
        for m in re.finditer(
            r"([一-鿿][\w一-鿿]*)\s*[：:]\s*"
            r"([<>≤≥~]?\s*[\d.,]+(?:\s*[-–]\s*[\d.,]+)?)\s*"
            r"(ms|fps|MB|KB|GB|%|秒|毫秒|LOC|k|Phase|个|项|天|周|工作日)",
            text,
        ):
            metrics.append((m.group(1), m.group(2).strip(), m.group(3) or ""))
            if len(metrics) >= max_count:
                break
        if len(metrics) >= max_count:
            break
    if not metrics:
        return ""
    cards = []
    for i, (label, value, unit) in enumerate(metrics):
        color = ACCENT_COLORS[i % len(ACCENT_COLORS)]
        unit_html = f'<span class="unit">{escape(unit)}</span>' if unit else ""
        cards.append(
            f'<div class="metric-card"><div class="metric-label">{escape(label)}</div>'
            f'<div class="metric-value" style="color:{color}">{escape(value)}{unit_html}</div></div>'
        )
    return f'<div class="summary-metrics">{"".join(cards)}</div>'


def postprocess_code_blocks(html_str: str) -> str:
    def _replacer(m):
        lang = m.group(1)
        content = m.group(2)
        label = lang.replace("language-", "")
        return (
            f'<figure class="code-figure"><figcaption>{escape(label)}</figcaption>'
            f'<pre><code class="{lang}">{content}</code></pre></figure>'
        )
    return re.sub(
        r'<pre><code class="(language-[\w+-]+)">(.*?)</code></pre>',
        _replacer, html_str, flags=re.S,
    )


def extract_first_paragraph(html_str: str) -> tuple[str, str]:
    # D1: only search BEFORE first <h2>, skip <hr> and <blockquote>
    h2_match = re.search(r"<h2[^>]*>", html_str)
    search_zone = html_str[:h2_match.start()] if h2_match else html_str[:2000]

    # Find first <p> that is not inside <blockquote> and is not <hr>
    for m in re.finditer(r"<p>(.*?)</p>", search_zone, re.S):
        # Skip if it looks like it's inside a blockquote block
        before = search_zone[:m.start()]
        open_bq = before.count("<blockquote>")
        close_bq = before.count("</blockquote>")
        if open_bq > close_bq:
            continue
        text = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if 20 < len(text) < 300:
            remaining = html_str[:m.start()] + html_str[m.end():]
            return text, remaining

    # D1 fallback: generate summary from section headings
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", html_str, re.S)
    if headings:
        names = [re.sub(r"<[^>]+>", "", h).strip() for h in headings[:4]]
        summary = "涵盖：" + "、".join(names)
        if len(headings) > 4:
            summary += "等"
        return summary, html_str

    return "", html_str


def postprocess_inline_decorations(html_str: str) -> str:
    """C: Decorate inline text — P0/P1/P2 badges, status emoji badges, metric spans.
    Protects <pre> content from processing.
    """
    # Extract <pre> blocks → placeholders
    pre_blocks: list[str] = []
    def _save_pre(m: re.Match) -> str:
        pre_blocks.append(m.group(0))
        return f"\x00PRE{len(pre_blocks)-1}\x00"

    safe = re.sub(r"<pre[^>]*>.*?</pre>", _save_pre, html_str, flags=re.S)

    # C1: P0/P1/P2 → badge spans (only inside <p>, <li>, <td> content)
    def _decorate_tag_content(m: re.Match) -> str:
        tag_open = m.group(1)
        inner = m.group(2)
        tag_close = m.group(3)
        # Priority badges — avoid double-wrapping existing spans
        inner = re.sub(
            r'(?<!["\w>])\b(P[012])\b(?!["\w<])',
            lambda x: f'<span class="badge badge-{x.group(1).lower()}">{x.group(1)}</span>',
            inner
        )
        # C2: status emoji → badge (match emoji + rest of text until tag boundary)
        inner = re.sub(
            r'(✅|✓)([^<]*)',
            lambda x: f'<span class="badge badge-ok">{x.group(1)}{x.group(2)}</span>',
            inner
        )
        inner = re.sub(
            r'(❌|✕)([^<]*)',
            lambda x: f'<span class="badge badge-danger">{x.group(1)}{x.group(2)}</span>',
            inner
        )
        # C3: numbers + units → metric-inline
        inner = re.sub(
            r'(\d+(?:\.\d+)?)\s*(ms|fps|MB|KB|GB|%|秒|毫秒)',
            r'<span class="metric-inline">\1\2</span>',
            inner
        )
        return tag_open + inner + tag_close

    safe = re.sub(
        r"(<(?:p|li|td)[^>]*>)(.*?)(</(?:p|li|td)>)",
        _decorate_tag_content,
        safe,
        flags=re.S
    )

    # Restore <pre> blocks
    for i, block in enumerate(pre_blocks):
        safe = safe.replace(f"\x00PRE{i}\x00", block)

    return safe


INLINE_JS = r"""
const bar=document.getElementById('progress-bar');
window.addEventListener('scroll',()=>{
  const h=document.documentElement.scrollHeight-window.innerHeight;
  bar.style.width=h>0?Math.min(window.scrollY/h*100,100)+'%':'0';
},{passive:true});
const secs=document.querySelectorAll('section[id]');
const links=document.querySelectorAll('.sidebar-nav a');
if(secs.length&&links.length){
  const obs=new IntersectionObserver(es=>{
    es.forEach(e=>{
      if(e.isIntersecting){
        links.forEach(a=>a.classList.remove('active'));
        const a=document.querySelector('.sidebar-nav a[data-section="'+e.target.id+'"]');
        if(a)a.classList.add('active');
      }
    });
  },{rootMargin:'-80px 0px -60% 0px'});
  secs.forEach(s=>obs.observe(s));
}
"""


def convert_md_to_html(md_path: Path, use_ai: bool = True) -> Path:
    text = md_path.read_text(encoding="utf-8")

    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "meta"])
    body_html = md.convert(text)

    title = md_path.stem
    h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", body_html)
    if h1_match:
        title = re.sub(r"<[^>]+>", "", h1_match.group(1))
        body_html = body_html[h1_match.end():]

    doc_type = extract_doc_type(title)
    meta_cards, body_html = extract_meta(body_html)
    meta_html = build_meta_badges(meta_cards)

    subtitle, body_html = extract_first_paragraph(body_html)

    sections = split_sections(body_html)

    toc_html = build_toc(sections)
    summary_html = extract_summary_metrics(sections)

    rendered = []
    section_idx = 1
    for heading, body in sections:
        if not heading:
            if body.strip():
                rendered.append(f'<div class="card">{body}</div>')
            continue
        comp_type = classify(heading, body, use_ai=use_ai)
        section_html = render_section(comp_type, heading, body, section_idx)
        section_html = section_html.replace("<section>", f'<section id="section-{section_idx}">', 1)
        section_html = postprocess_code_blocks(section_html)
        rendered.append(section_html)
        section_idx += 1

    nav_project = md_path.parent.name or "Project"
    sections_html = "\n".join(rendered)

    # C: inline decorations (after code block postprocess)
    sections_html = postprocess_inline_decorations(sections_html)

    subtitle_html = f'<p class="doc-subtitle">{escape(subtitle)}</p>' if subtitle else (
        f'<p class="doc-subtitle">{escape(doc_type)} — {escape(nav_project)}</p>' if nav_project != "Project" else ""
    )

    # D2: reading time estimate
    char_count = len(re.sub(r"<[^>]+>", "", sections_html))
    read_minutes = max(1, char_count // 400)
    read_time_html = f'<span class="doc-date">约 {read_minutes} 分钟阅读</span>'

    # D3: sibling document links
    siblings = [f for f in md_path.parent.glob("*.md") if f.name != md_path.name]
    sibling_links_html = ""
    if siblings:
        links = []
        for sib in siblings[:5]:
            sib_html = sib.with_suffix(".html").name
            links.append(f'<a href="{escape(sib_html)}">{escape(sib.stem)}</a>')
        sibling_links_html = '<div class="sibling-links">' + " · ".join(links) + "</div>"

    html_out = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)} · {escape(doc_type)}</title>
<style>{CSS}</style>
</head>
<body>
<div id="progress-bar"></div>
<nav>
  <div class="breadcrumb">
    <span>{escape(nav_project)}</span>
    <span class="sep">/</span>
    <span class="current">{escape(doc_type)}</span>
  </div>
  {sibling_links_html}
</nav>

<div class="page-layout">
  {toc_html}
  <main>
    <div class="container">
      <header class="doc-header">
        <div class="doc-meta">
          {meta_html}
          {read_time_html}
        </div>
        <h1>{escape(title)}</h1>
        {subtitle_html}
      </header>

      {summary_html}
      {sections_html}
    </div>
    <footer>
      Generated by md2html · {escape(doc_type)}
    </footer>
  </main>
</div>
<script>{INLINE_JS}</script>
</body>
</html>"""

    out_path = md_path.with_suffix(".html")
    out_path.write_text(html_out, encoding="utf-8")
    return out_path


def main():
    use_ai = True
    args = [a for a in sys.argv[1:] if a != "--no-ai"]
    if "--no-ai" in sys.argv:
        use_ai = False

    if not args:
        print("Usage: python md2html.py [--no-ai] <file.md | directory/>")
        sys.exit(1)

    target = Path(args[0])

    if target.is_dir():
        files = list(target.glob("*.md"))
        if not files:
            print(f"No .md files in {target}")
            sys.exit(1)
        for f in files:
            out = convert_md_to_html(f, use_ai=use_ai)
            print(f"  {f.name} -> {out.name}")
    elif target.is_file() and target.suffix == ".md":
        out = convert_md_to_html(target, use_ai=use_ai)
        print(f"  {target.name} -> {out.name}")
    else:
        print(f"Not a .md file or directory: {target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
