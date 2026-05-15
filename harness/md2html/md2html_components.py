"""
Component renderers for md2html.
Each function: (heading_text, body_html) → rich HTML string.
Input body_html is standard HTML from markdown lib (tables, lists, paragraphs, code blocks).
"""

import re
import html
from html import escape


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _extract_rows(table_html: str) -> tuple[list[str], list[list[str]]]:
    """Extract headers and rows from an HTML table. Returns (headers, rows)."""
    headers = []
    rows = []
    for th in re.finditer(r"<th[^>]*>(.*?)</th>", table_html, re.S):
        headers.append(th.group(1).strip())
    for tr in re.finditer(r"<tr>(.*?)</tr>", table_html, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr.group(1), re.S)
        if cells:
            rows.append([c.strip() for c in cells])
    return headers, rows


def _extract_list_items(html: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"<li>(.*?)</li>", html, re.S)]


def _badge_for_priority(text: str) -> str:
    t = text.upper()
    if "P0" in t:
        return '<span class="badge badge-p0">P0</span>'
    if "P1" in t:
        return '<span class="badge badge-p1">P1</span>'
    if "P2" in t:
        return '<span class="badge badge-p2">P2</span>'
    return ""


def _badge_for_status(text: str) -> str:
    t = _strip_tags(text)
    low = t.lower()
    if any(w in low for w in ["✅", "完成", "已集成", "done", "pass", "ok"]):
        return f'<span class="badge badge-ok">{t}</span>'
    if any(w in low for w in ["❌", "失败", "fail", "blocked"]):
        return f'<span class="badge badge-danger">{t}</span>'
    if any(w in low for w in ["⚠", "警告", "warn", "兜底", "待定", "pending"]):
        return f'<span class="badge badge-warn">{t}</span>'
    if any(w in low for w in ["进行中", "active", "wip"]):
        return f'<span class="badge badge-phase">{t}</span>'
    return t


def _detect_metric(text: str) -> tuple[str, str] | None:
    """Try to extract (value, unit) from text like '50-200ms', '100%', '<2ms'."""
    m = re.search(r"([<>≤≥~]?\s*[\d.,]+(?:\s*[-–]\s*[\d.,]+)?)\s*(ms|fps|MB|KB|GB|%|秒|毫秒|LOC|k|Phase|个|项|天|周)", text, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None


# ──────────────────────────────────────────────
# Component renderers
# ──────────────────────────────────────────────

ACCENT_COLORS = ["var(--accent)", "var(--blue)", "var(--cyan)", "var(--purple)", "var(--amber)", "var(--red)"]


def render_prose(heading: str, body: str, idx: int) -> str:
    # B1: detect h3/h4 sub-headings → split into sub-cards
    has_sub_headings = bool(re.search(r"<h[34][^>]*>", body))

    if has_sub_headings:
        # Split on h3/h4 boundaries
        parts = re.split(r"(<h[34][^>]*>.*?</h[34]>)", body, flags=re.S)
        sub_cards = []
        # Content before first sub-heading (if any)
        if parts[0].strip():
            sub_cards.append(f'<div class="card">{parts[0]}</div>')
        # Pair each heading with its following content
        i = 1
        while i < len(parts):
            sub_h = parts[i]
            sub_content = parts[i + 1] if i + 1 < len(parts) else ""
            # B3: check if sub-content is list-heavy (≥4 items)
            li_count = len(re.findall(r"<li>", sub_content))
            text_len = len(sub_content)
            list_html_len = sum(len(m.group(0)) for m in re.finditer(r"<[uo]l>.*?</[uo]l>", sub_content, re.S))
            list_ratio = list_html_len / max(text_len, 1)
            if li_count >= 4 and list_ratio >= 0.6:
                # Convert ul/ol to grid layout
                sub_content = re.sub(
                    r"<([uo]l)>(.*?)</[uo]l>",
                    lambda m: f'<ul class="list-grid">{m.group(2)}</ul>',
                    sub_content, flags=re.S
                )
            sub_cards.append(f'<div class="card">{sub_h}<div class="sub-content">{sub_content}</div></div>')
            i += 2
        body_html = "\n".join(sub_cards)
    else:
        # B3: check if body is list-heavy (≥4 items, no sub-headings)
        li_count = len(re.findall(r"<li>", body))
        text_len = len(body)
        list_html_len = sum(len(m.group(0)) for m in re.finditer(r"<[uo]l>.*?</[uo]l>", body, re.S))
        list_ratio = list_html_len / max(text_len, 1)
        if li_count >= 4 and list_ratio >= 0.6:
            body_mod = re.sub(
                r"<([uo]l)>(.*?)</[uo]l>",
                lambda m: f'<ul class="list-grid">{m.group(2)}</ul>',
                body, flags=re.S
            )
        else:
            body_mod = body

        # B2: long content → wrap in details
        stripped_len = len(_strip_tags(body))
        if stripped_len > 800:
            body_html = f'<details open>\n<summary>展开 / 收起</summary>\n<div class="card">{body_mod}</div>\n</details>'
        else:
            body_html = f'<div class="card">{body_mod}</div>'

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  {body_html}
</section>'''


def render_priority_cards(heading: str, body: str, idx: int) -> str:
    cards = []

    headers, rows = _extract_rows(body)
    if rows:
        for row in rows:
            raw = " ".join(row)
            badge = _badge_for_priority(raw)
            title = _strip_tags(row[0]) if row else ""
            desc = _strip_tags(row[1]) if len(row) > 1 else ""
            impact = _strip_tags(row[-1]) if len(row) > 2 else ""
            cards.append(f'''<div class="problem-card">
        <div class="priority">{badge}</div>
        <div>
          <h3>{escape(title)}</h3>
          <div class="desc">{escape(desc)}</div>
          {f'<div class="impact">{escape(impact)}</div>' if impact else ''}
        </div>
      </div>''')
    else:
        parts = re.split(r"<h[3-6][^>]*>", body)
        for part in parts:
            text = _strip_tags(part)
            if not text.strip():
                continue
            badge = _badge_for_priority(text)
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            title = lines[0] if lines else ""
            desc = " ".join(lines[1:]) if len(lines) > 1 else ""
            title = re.sub(r"^P[012]\s*[：:]\s*", "", title)
            cards.append(f'''<div class="problem-card">
        <div class="priority">{badge}</div>
        <div>
          <h3>{escape(title)}</h3>
          <div class="desc">{escape(desc)}</div>
        </div>
      </div>''')

    if not cards:
        return render_prose(heading, body, idx)

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="problems">{"".join(cards)}</div>
</section>'''


def render_comparison_table(heading: str, body: str, idx: int) -> str:
    headers, rows = _extract_rows(body)
    if not headers:
        return render_prose(heading, body, idx)

    ths = "".join(f"<th>{h}</th>" for h in headers)
    trs = []
    for row in rows:
        tds = []
        for cell in row:
            processed = _badge_for_status(cell)
            tds.append(f"<td>{processed}</td>")
        trs.append(f"<tr>{''.join(tds)}</tr>")

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="table-wrap">
    <table>
      <thead><tr>{ths}</tr></thead>
      <tbody>{"".join(trs)}</tbody>
    </table>
  </div>
</section>'''


def render_info_grid(heading: str, body: str, idx: int) -> str:
    headers, rows = _extract_rows(body)
    items: list[tuple[str, str]] = []

    if headers and rows:
        for row in rows:
            key = _strip_tags(row[0]) if row else ""
            val = _strip_tags(row[1]) if len(row) > 1 else ""
            items.append((key, val))
    else:
        list_items = _extract_list_items(body)
        for li in list_items:
            text = _strip_tags(li)
            parts = re.split(r"[：:]\s*", text, maxsplit=1)
            if len(parts) == 2:
                items.append((parts[0].strip(), parts[1].strip()))
            else:
                items.append((text, ""))

    if not items:
        return render_prose(heading, body, idx)

    cards = []
    for i, (k, v) in enumerate(items):
        color = ACCENT_COLORS[i % len(ACCENT_COLORS)]
        cards.append(f'''<div class="info-card">
      <div class="info-label">{escape(k)}</div>
      <div class="info-value" style="color:{color}">{escape(v)}</div>
    </div>''')

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="info-grid">{"".join(cards)}</div>
</section>'''


def render_scope_table(heading: str, body: str, idx: int) -> str:
    headers, rows = _extract_rows(body)
    if headers and rows:
        in_items = []
        out_items = []
        for row in rows:
            text = _strip_tags(row[0]) if row else ""
            status = _strip_tags(row[-1]).lower() if len(row) > 1 else ""
            if any(w in status for w in ["out", "不含", "不在", "排除", "❌"]):
                out_items.append(text)
            else:
                in_items.append(text)
    else:
        all_items = _extract_list_items(body)
        in_items = []
        out_items = []
        in_section = True
        for item in all_items:
            text = _strip_tags(item)
            if any(w in text.lower() for w in ["not ", "不含", "不在", "out of scope", "排除", "❌"]):
                in_section = False
            if not in_section:
                out_items.append(text)
            else:
                in_items.append(text)

    in_html = "".join(f"<li>{escape(i)}</li>" for i in in_items)
    out_html = "".join(f"<li>{escape(i)}</li>" for i in out_items)

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="scope-grid">
    <div class="scope-col scope-in">
      <h3><span style="color:var(--green)">●</span> In Scope</h3>
      <ul>{in_html}</ul>
    </div>
    <div class="scope-col scope-out">
      <h3><span style="color:var(--red);opacity:.7">●</span> Out of Scope</h3>
      <ul>{out_html}</ul>
    </div>
  </div>
</section>'''


def render_risk_cards(heading: str, body: str, idx: int) -> str:
    headers, rows = _extract_rows(body)
    if headers and rows:
        return render_comparison_table(heading, body, idx)

    sections = re.split(r"<h[3-6][^>]*>(.*?)</h[3-6]>", body, flags=re.S)
    cols = []
    for i in range(1, len(sections), 2):
        sub_heading = _strip_tags(sections[i])
        sub_body = sections[i + 1] if i + 1 < len(sections) else ""
        items = _extract_list_items(sub_body)
        is_danger = any(w in sub_heading for w in ["现", "旧", "问题", "风险", "before", "当前"])
        cls = "danger" if is_danger else "safe"
        mark = "✕" if is_danger else "✓"
        lis = "".join(f"<li>{escape(_strip_tags(it))}</li>" for it in items)
        cols.append(f'''<div class="risk-col {cls}">
      <h3>{escape(sub_heading)}</h3>
      <ul>{lis}</ul>
    </div>''')

    if not cols:
        return render_prose(heading, body, idx)

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="risk-compare">{"".join(cols)}</div>
</section>'''


def render_criteria_table(heading: str, body: str, idx: int) -> str:
    headers, rows = _extract_rows(body)
    if not headers:
        items = _extract_list_items(body)
        if items:
            lis = "".join(
                f'<li class="criteria-item"><span class="criteria-check">☐</span> {escape(_strip_tags(it))}</li>'
                for it in items
            )
            return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="card"><ul class="criteria-list">{lis}</ul></div>
</section>'''
        return render_prose(heading, body, idx)

    return render_comparison_table(heading, body, idx)


def render_timeline(heading: str, body: str, idx: int) -> str:
    headers, rows = _extract_rows(body)
    items = []

    if rows:
        for row in rows:
            phase = _strip_tags(row[0]) if row else ""
            title = _strip_tags(row[1]) if len(row) > 1 else ""
            desc = _strip_tags(row[2]) if len(row) > 2 else ""
            status_text = _strip_tags(row[-1]).lower() if len(row) > 1 else ""
            state = "done" if any(w in status_text for w in ["✅", "完成", "done"]) else \
                    "active" if any(w in status_text for w in ["进行", "active", "wip", "当前"]) else ""
            items.append((phase, title, desc, state))
    else:
        list_items = _extract_list_items(body)
        for i, li in enumerate(list_items):
            text = _strip_tags(li)
            items.append((f"Phase {i+1}", text, "", ""))

    if not items:
        return render_prose(heading, body, idx)

    tl_html = []
    for phase, title, desc, state in items:
        tl_html.append(f'''<div class="tl-item {state}">
      <div class="tl-dot"></div>
      <div class="tl-phase">{escape(phase)}</div>
      <div class="tl-title">{escape(title)}</div>
      {f'<div class="tl-desc">{escape(desc)}</div>' if desc else ''}
    </div>''')

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="timeline">{"".join(tl_html)}</div>
</section>'''


def render_phase_cards(heading: str, body: str, idx: int) -> str:
    sections = re.split(r"<h[3-6][^>]*>(.*?)</h[3-6]>", body, flags=re.S)
    cards = []
    card_idx = 0
    states = ["done", "active", "pending", "pending", "pending"]

    for i in range(1, len(sections), 2):
        sub_heading = _strip_tags(sections[i])
        sub_body = sections[i + 1] if i + 1 < len(sections) else ""
        items = _extract_list_items(sub_body)
        desc_parts = re.findall(r"<p>(.*?)</p>", sub_body, re.S)
        desc = _strip_tags(desc_parts[0]) if desc_parts else ""

        raw = sub_heading + " " + sub_body
        state = "done" if any(w in raw for w in ["✅", "完成", "done"]) else \
                "active" if any(w in raw for w in ["进行", "active", "当前", "🔄"]) else \
                states[min(card_idx, len(states)-1)]

        items_html = ""
        if items:
            lis = "".join(f"<li>{escape(_strip_tags(it))}</li>" for it in items[:6])
            items_html = f'<ul class="phase-items">{lis}</ul>'

        cards.append(f'''<div class="phase-card {state}">
      <div class="phase-num">Phase {card_idx + 1} {f'<span class="badge badge-ok">✓</span>' if state == "done" else ""}</div>
      <div class="phase-title">{escape(sub_heading)}</div>
      {f'<div class="phase-desc">{escape(desc)}</div>' if desc else ''}
      {items_html}
    </div>''')
        card_idx += 1

    if not cards:
        return render_prose(heading, body, idx)

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="phases">{"".join(cards)}</div>
</section>'''


def _is_code_not_flow(text: str) -> bool:
    """Detect if a code block contains programming code rather than a flow diagram."""
    code_indicators = ['{', '}', '()', ';', '//', '#include', 'import ', 'return ',
                       'class ', 'def ', 'function ', 'const ', 'let ', 'var ',
                       '::',  '<<', '>>', 'if (', 'for (', 'while (']
    hits = sum(1 for ind in code_indicators if ind in text)
    return hits >= 2


def render_flow_diagram(heading: str, body: str, idx: int) -> str:
    code_blocks = re.findall(r"<code[^>]*>(.*?)</code>", body, re.S)
    if code_blocks:
        code_text = html.unescape(_strip_tags(code_blocks[0]))

        if _is_code_not_flow(code_text):
            return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="seq-diagram"><pre>{body}</pre></div>
</section>'''

        lines = [l.strip() for l in code_text.split("\n") if l.strip()]
        nodes = []
        for line in lines:
            cleaned = re.sub(r"^[\s│├└┌┐┘┬┴┤┼─]+", "", line).strip()
            cleaned = re.sub(r"[→←↓↑]+$", "", cleaned).strip()
            if cleaned and len(cleaned) > 1:
                nodes.append(cleaned)

        if nodes:
            flow_parts = []
            for i, node in enumerate(nodes):
                highlight = " highlight" if i == len(nodes) // 2 else ""
                flow_parts.append(f'''<div class="flow-node{highlight}">
          <div class="flow-node-label">{escape(node)}</div>
        </div>''')
                if i < len(nodes) - 1:
                    flow_parts.append('<div class="flow-arrow">→</div>')

            return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="flow">{"".join(flow_parts)}</div>
</section>'''

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="seq-diagram"><pre>{body}</pre></div>
</section>'''


def render_code_compare(heading: str, body: str, idx: int) -> str:
    code_blocks = re.findall(r"<pre><code[^>]*>(.*?)</code></pre>", body, re.S)

    if len(code_blocks) >= 2:
        before_code = code_blocks[0]
        after_code = code_blocks[1]
    elif len(code_blocks) == 1:
        before_code = code_blocks[0]
        after_code = ""
    else:
        return render_prose(heading, body, idx)

    before_label = "Before"
    after_label = "After"
    sub_headings = re.findall(r"<h[3-6][^>]*>(.*?)</h[3-6]>", body, re.S)
    if len(sub_headings) >= 2:
        before_label = _strip_tags(sub_headings[0])
        after_label = _strip_tags(sub_headings[1])

    blocks = [f'''<div class="code-block">
      <div class="code-header"><span>{escape(before_label)}</span><span class="badge badge-danger">OLD</span></div>
      <div class="code-body"><pre>{before_code}</pre></div>
    </div>''']

    if after_code:
        blocks.append(f'''<div class="code-block">
      <div class="code-header"><span>{escape(after_label)}</span><span class="badge badge-ok">NEW</span></div>
      <div class="code-body"><pre>{after_code}</pre></div>
    </div>''')

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="code-compare">{"".join(blocks)}</div>
</section>'''


def render_metric_cards(heading: str, body: str, idx: int) -> str:
    metrics: list[tuple[str, str, str, str]] = []

    headers, rows = _extract_rows(body)
    if rows:
        for row in rows:
            label = _strip_tags(row[0]) if row else ""
            value_text = _strip_tags(row[1]) if len(row) > 1 else ""
            desc = _strip_tags(row[2]) if len(row) > 2 else ""
            parsed = _detect_metric(value_text)
            if parsed:
                metrics.append((label, parsed[0], parsed[1], desc))
            else:
                metrics.append((label, value_text, "", desc))
    else:
        list_items = _extract_list_items(body)
        for li in list_items:
            text = _strip_tags(li)
            parsed = _detect_metric(text)
            if parsed:
                label = re.sub(r"[<>≤≥~]?\s*[\d.,]+(?:\s*[-–]\s*[\d.,]+)?\s*(ms|fps|MB|KB|GB|%|秒|毫秒|LOC|k|Phase|个|项|天|周)", "", text, flags=re.I).strip()
                label = re.sub(r"[：:]\s*$", "", label)
                metrics.append((label, parsed[0], parsed[1], ""))
            else:
                parts = re.split(r"[：:]\s*", text, maxsplit=1)
                if len(parts) == 2:
                    metrics.append((parts[0], parts[1], "", ""))

        if not metrics:
            para_text = _strip_tags(body)
            found = re.findall(r"([\w一-鿿]+)\s*[：:=]\s*([<>≤≥~]?\s*[\d.,]+(?:\s*[-–]\s*[\d.,]+)?)\s*(ms|fps|MB|KB|GB|%|秒|毫秒|LOC|k)?", para_text)
            for label, val, unit in found:
                metrics.append((label, val, unit or "", ""))

    if not metrics:
        return render_prose(heading, body, idx)

    cards = []
    for i, (label, value, unit, desc) in enumerate(metrics[:6]):
        color = ACCENT_COLORS[i % len(ACCENT_COLORS)]
        unit_html = f'<span class="unit">{escape(unit)}</span>' if unit else ""
        cards.append(f'''<div class="metric-card">
      <div class="metric-label">{escape(label)}</div>
      <div class="metric-value" style="color:{color}">{escape(value)}{unit_html}</div>
      {f'<div class="metric-desc">{escape(desc)}</div>' if desc else ''}
    </div>''')

    return f'''<section>
  <h2><span class="section-num">{idx:02d}</span>{escape(heading)}</h2>
  <div class="metrics">{"".join(cards)}</div>
</section>'''


RENDERERS = {
    "prose": render_prose,
    "priority-cards": render_priority_cards,
    "comparison-table": render_comparison_table,
    "info-grid": render_info_grid,
    "scope-table": render_scope_table,
    "risk-cards": render_risk_cards,
    "criteria-table": render_criteria_table,
    "timeline": render_timeline,
    "phase-cards": render_phase_cards,
    "flow-diagram": render_flow_diagram,
    "code-compare": render_code_compare,
    "metric-cards": render_metric_cards,
}


def render_section(component_type: str, heading: str, body: str, idx: int) -> str:
    renderer = RENDERERS.get(component_type, render_prose)
    try:
        return renderer(heading, body, idx)
    except Exception:
        return render_prose(heading, body, idx)
