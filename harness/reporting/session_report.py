#!/usr/bin/env python3
"""
session_report.py — 会话审计报告生成器

将 tool_audit.jsonl 转换为人可读的会话报告。

用法：
  python session_report.py                    # 列出所有 session 概览
  python session_report.py <session_prefix>   # 某个 session 的详细时间线
  python session_report.py --last             # 最近一个 session 的详细时间线
  python session_report.py --today            # 今天所有 session
"""

import io
import json
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _lib import record_tool_invocation  # noqa: E402

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

LOG_DIR = Path.home() / ".claude" / "logs"
AUDIT_FILE = LOG_DIR / "tool_audit.jsonl"
SUBAGENT_FILE = LOG_DIR / "subagent_audit.jsonl"


def load_records(filepath):
    """加载 JSONL 文件。"""
    records = []
    if not filepath.exists():
        return records
    for line in filepath.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def group_by_session(records):
    """按 session 分组，保持顺序。"""
    sessions = OrderedDict()
    for r in records:
        sid = r.get("session", "unknown")
        sessions.setdefault(sid, []).append(r)
    return sessions


def format_duration(seconds):
    """格式化时长。"""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds // 60:.0f}m{seconds % 60:.0f}s"
    else:
        return f"{seconds // 3600:.0f}h{(seconds % 3600) // 60:.0f}m"


def shorten_path(path_str):
    """缩短路径显示。"""
    home = str(Path.home()).replace("\\", "/")
    path_str = path_str.replace("\\", "/")
    path_str = path_str.replace(home + "/.claude/", "~claude/")
    path_str = path_str.replace(home + "/", "~/")
    return path_str


def shorten_bash(cmd):
    """缩短 Bash 命令显示。"""
    cmd = cmd.strip()
    # 多行命令只显示第一行 + 标记
    lines = cmd.split("\n")
    if len(lines) > 1:
        cmd = lines[0].strip() + f" ...(+{len(lines)-1} lines)"
    if len(cmd) > 120:
        cmd = cmd[:117] + "..."
    return cmd


def describe_tool(tool, summary):
    """生成工具调用的可读描述。"""
    summary = summary or ""
    if tool == "Bash":
        return shorten_bash(summary)
    elif tool == "Read":
        return f"读 {shorten_path(summary)}"
    elif tool == "Write":
        return f"写 {shorten_path(summary)}"
    elif tool == "Edit":
        return f"改 {shorten_path(summary)}"
    elif tool == "Glob":
        return f"搜文件 {summary}"
    elif tool == "Grep":
        return f"搜内容 {summary}"
    elif tool == "WebFetch":
        return f"抓取 {summary[:80]}"
    elif tool == "WebSearch":
        return f"搜索 {summary}"
    elif tool == "Agent":
        return f"派生Agent: {summary[:60]}"
    elif tool == "EnterPlanMode":
        return "进入计划模式"
    elif tool == "ExitPlanMode":
        return "退出计划模式"
    elif tool == "TaskCreate":
        return f"创建任务"
    elif tool == "TaskUpdate":
        return f"更新任务"
    elif tool == "TaskOutput":
        return f"读取任务输出"
    elif tool == "AskUserQuestion":
        return "向用户提问"
    else:
        desc = summary[:60] if summary else ""
        return f"{tool} {desc}".strip()


def detect_patterns(records):
    """检测会话中的行为模式。"""
    patterns = []
    tools = [r["tool"] for r in records]

    # 连续重试同一工具
    streak = 1
    for i in range(1, len(tools)):
        if tools[i] == tools[i-1] == "Bash":
            streak += 1
        else:
            if streak >= 5:
                patterns.append(f"连续 {streak} 次 Bash 调用（可能在调试/重试）")
            streak = 1
    if streak >= 5:
        patterns.append(f"连续 {streak} 次 Bash 调用（可能在调试/重试）")

    # 大量读文件
    reads = sum(1 for t in tools if t == "Read")
    if reads > 20:
        patterns.append(f"大量文件读取 ({reads} 次)，可能是探索/审计型任务")

    # Agent 使用
    agents = sum(1 for t in tools if t == "Agent")
    if agents > 0:
        patterns.append(f"派生了 {agents} 个子 Agent")

    # 写操作占比
    writes = sum(1 for t in tools if t in ("Write", "Edit"))
    if writes > 10:
        patterns.append(f"密集写操作 ({writes} 次)，可能是重构/批量修改")
    elif writes == 0 and len(tools) > 10:
        patterns.append("纯只读会话（无 Write/Edit）")

    return patterns


def print_session_list(sessions):
    """打印 session 列表概览。"""
    print("=" * 70)
    print("  会话审计概览")
    print("=" * 70)
    print()

    for sid, records in sessions.items():
        ts_start = records[0].get("ts", "?")
        ts_end = records[-1].get("ts", "?")
        count = len(records)

        # 工具统计
        tool_counts = {}
        for r in records:
            t = r["tool"]
            tool_counts[t] = tool_counts.get(t, 0) + 1
        top_tools = sorted(tool_counts.items(), key=lambda x: -x[1])[:4]
        tool_str = " ".join(f"{t}:{c}" for t, c in top_tools)

        # 时长
        try:
            t0 = datetime.fromisoformat(ts_start)
            t1 = datetime.fromisoformat(ts_end)
            dur = format_duration((t1 - t0).total_seconds())
        except Exception:
            dur = "?"

        print(f"  {sid[:12]}  {ts_start[5:16]}~{ts_end[11:16]}  "
              f"{dur:>6s}  {count:>3d} calls  {tool_str}")

    print(f"\n  共 {len(sessions)} 个会话，{sum(len(v) for v in sessions.values())} 次工具调用")
    print("=" * 70)


def print_session_detail(sid, records, subagent_records=None):
    """打印单个 session 的详细时间线。"""
    ts_start = records[0].get("ts", "?")
    ts_end = records[-1].get("ts", "?")

    print("=" * 70)
    print(f"  会话详情: {sid[:16]}")
    print(f"  时间: {ts_start} → {ts_end}")
    print(f"  工具调用: {len(records)} 次")
    print("=" * 70)

    # 行为模式检测
    patterns = detect_patterns(records)
    if patterns:
        print("\n  [行为模式]")
        for p in patterns:
            print(f"    - {p}")

    # 工具统计
    tool_counts = {}
    for r in records:
        t = r["tool"]
        tool_counts[t] = tool_counts.get(t, 0) + 1
    print("\n  [工具统计]")
    for t, c in sorted(tool_counts.items(), key=lambda x: -x[1]):
        bar = "#" * min(c, 30)
        print(f"    {t:20s} {c:3d}  {bar}")

    # 子 Agent 信息
    if subagent_records:
        session_agents = [r for r in subagent_records if r.get("session", "").startswith(sid[:12])]
        if session_agents:
            print("\n  [子 Agent]")
            for a in session_agents:
                print(f"    {a.get('ts', '?')[11:19]}  "
                      f"type={a.get('agent_type', '?')}  "
                      f"id={a.get('agent_id', '?')[:12]}")

    # 时间线
    print("\n  [时间线]")
    print(f"  {'时间':>8s}  {'工具':>12s}  操作")
    print(f"  {'─'*8}  {'─'*12}  {'─'*44}")

    prev_ts = None
    phase_num = 1
    for i, r in enumerate(records):
        ts = r.get("ts", "?")
        tool = r.get("tool", "?")
        summary = r.get("input_summary", "")
        time_str = ts[11:19] if len(ts) > 11 else ts

        # 时间间隔超过 2 分钟标记阶段分隔
        if prev_ts:
            try:
                t0 = datetime.fromisoformat(prev_ts)
                t1 = datetime.fromisoformat(ts)
                gap = (t1 - t0).total_seconds()
                if gap > 120:
                    phase_num += 1
                    print(f"\n  {'':>8s}  {'--- 间隔 ' + format_duration(gap) + ' ---':^58s}")
                    print()
            except Exception:
                pass

        desc = describe_tool(tool, summary)
        print(f"  {time_str}  {tool:>12s}  {desc}")
        prev_ts = ts

    print()
    print("=" * 70)


def main():
    if not AUDIT_FILE.exists():
        print(f"审计日志不存在: {AUDIT_FILE}")
        return 1

    records = load_records(AUDIT_FILE)
    if not records:
        print("审计日志为空")
        return 1

    subagent_records = load_records(SUBAGENT_FILE)
    sessions = group_by_session(records)

    # 参数解析
    if len(sys.argv) < 2:
        print_session_list(sessions)
        print(f"\n  用法: python session_report.py <session_prefix>  查看详情")
        print(f"        python session_report.py --last            最近一个会话")
        print(f"        python session_report.py --today           今天所有会话")
        return 0

    arg = sys.argv[1]

    if arg == "--last":
        sid = list(sessions.keys())[-1]
        print_session_detail(sid, sessions[sid], subagent_records)
    elif arg == "--today":
        today = datetime.now().strftime("%Y-%m-%d")
        for sid, recs in sessions.items():
            if recs[0].get("ts", "").startswith(today):
                print_session_detail(sid, recs, subagent_records)
                print()
    else:
        # 按前缀匹配 session
        matched = [(sid, recs) for sid, recs in sessions.items() if sid.startswith(arg)]
        if not matched:
            print(f"未找到匹配 '{arg}' 的会话")
            print(f"可用会话:")
            for sid in sessions:
                print(f"  {sid[:16]}")
            return 1
        for sid, recs in matched:
            print_session_detail(sid, recs, subagent_records)

    return 0


if __name__ == "__main__":
    record_tool_invocation("session_report.py", source="session-report")
    sys.exit(main())
