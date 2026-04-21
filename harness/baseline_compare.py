#!/usr/bin/env python3
"""
baseline_compare.py — 改代码前后的验证结果对比工具

用法：
    python baseline_compare.py snapshot before         # 改代码前：存快照
    python baseline_compare.py snapshot after           # 改代码后：存快照
    python baseline_compare.py diff                     # 对比 before vs after
    python baseline_compare.py diff --project <dir>     # 对比时也跑项目规范检查
    python baseline_compare.py history                  # 查看所有历史快照
    python baseline_compare.py clean                    # 清理旧快照（保留最近 10 对）

快照内容：verify_all + verify_memory + verify_conventions 的完整输出
"""

import io, json, os, re, subprocess, sys
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

CLAUDE_DIR = Path.home() / ".claude"
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
SNAPSHOTS_DIR = CLAUDE_DIR / "baselines"
LOG_FILE = CLAUDE_DIR / "logs" / "baseline_compare.log"

def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {msg}\n")


def run_script(name, args=None):
    """运行一个 verify 脚本，捕获输出"""
    cmd = [sys.executable, str(SCRIPTS_DIR / name)]
    if args:
        cmd.extend(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return r.stdout + r.stderr
    except Exception as e:
        return f"ERROR running {name}: {e}"


def parse_results(output):
    """从验证脚本输出中提取 [{name, level, message}]"""
    results = []
    for line in output.splitlines():
        m = re.match(r'\s*[✅⚠️❌]\s*\[(\w+)\s*\]\s*(.*?):\s*(.*)', line)
        if m:
            results.append({
                "level": m.group(1).strip(),
                "name": m.group(2).strip(),
                "message": m.group(3).strip(),
            })
        # 也匹配 verify_conventions 格式
        m2 = re.match(r'\s*[✅⚠️❌]\s*\[([\w-]+)\]\s*(.*)', line)
        if m2 and not m:
            results.append({
                "level": "PASS" if "✅" in line else ("WARNING" if "⚠" in line else "ERROR"),
                "name": m2.group(1).strip(),
                "message": m2.group(2).strip(),
            })
    return results


def take_snapshot(tag, project_dir=None):
    """拍摄快照：跑所有验证脚本，存结果"""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"📸 正在拍摄 [{tag}] 快照...\n")

    snapshot = {
        "tag": tag,
        "timestamp": datetime.now().isoformat(),
        "sections": {},
    }

    # 1. verify_all
    print("  运行 verify_all.py ...")
    output = run_script("verify_all.py")
    snapshot["sections"]["verify_all"] = {
        "raw": output,
        "results": parse_results(output),
    }

    # 2. verify_memory
    print("  运行 verify_memory.py ...")
    output = run_script("verify_memory.py")
    snapshot["sections"]["verify_memory"] = {
        "raw": output,
        "results": parse_results(output),
    }

    # 3. verify_conventions (如果有项目目录)
    if project_dir:
        print(f"  运行 verify_conventions.py {project_dir} --all ...")
        output = run_script("verify_conventions.py", [str(project_dir), "--all"])
        snapshot["sections"]["verify_conventions"] = {
            "raw": output,
            "results": parse_results(output),
        }

    # 保存
    filename = f"{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = SNAPSHOTS_DIR / filename
    filepath.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    # 统计
    total_pass = sum(len([r for r in s["results"] if r["level"] == "PASS"])
                     for s in snapshot["sections"].values())
    total_warn = sum(len([r for r in s["results"] if r["level"] == "WARNING"])
                     for s in snapshot["sections"].values())
    total_err = sum(len([r for r in s["results"] if r["level"] == "ERROR"])
                    for s in snapshot["sections"].values())

    print(f"\n  ✅ 快照已保存: {filepath.name}")
    print(f"  结果: {total_pass} PASS / {total_warn} WARNING / {total_err} ERROR")
    log(f"snapshot [{tag}]: {total_pass}P/{total_warn}W/{total_err}E → {filepath.name}")
    return filepath


def find_latest(tag):
    """找到指定 tag 最新的快照文件"""
    if not SNAPSHOTS_DIR.is_dir():
        return None
    files = sorted(SNAPSHOTS_DIR.glob(f"{tag}_*.json"), reverse=True)
    return files[0] if files else None


def diff_snapshots(before_path=None, after_path=None, project_dir=None):
    """对比 before 和 after 快照"""
    before_path = before_path or find_latest("before")
    after_path = after_path or find_latest("after")

    if not before_path or not before_path.is_file():
        print("❌ 未找到 before 快照。先运行: python baseline_compare.py snapshot before")
        return
    if not after_path or not after_path.is_file():
        print("❌ 未找到 after 快照。先运行: python baseline_compare.py snapshot after")
        return

    before = json.loads(before_path.read_text(encoding="utf-8"))
    after = json.loads(after_path.read_text(encoding="utf-8"))

    print("=" * 60)
    print("  基线对比报告")
    print(f"  BEFORE: {before['timestamp'][:19]}")
    print(f"  AFTER:  {after['timestamp'][:19]}")
    print("=" * 60)

    all_sections = set(list(before["sections"].keys()) + list(after["sections"].keys()))
    total_new_warn = 0
    total_new_err = 0
    total_fixed = 0

    for section in sorted(all_sections):
        before_results = {r["name"]: r for r in before.get("sections", {}).get(section, {}).get("results", [])}
        after_results = {r["name"]: r for r in after.get("sections", {}).get(section, {}).get("results", [])}

        all_names = sorted(set(list(before_results.keys()) + list(after_results.keys())))
        changes = []

        for name in all_names:
            b = before_results.get(name)
            a = after_results.get(name)

            if b and a:
                severity = {"PASS": 0, "WARNING": 1, "ERROR": 2}
                b_sev = severity.get(b["level"], 0)
                a_sev = severity.get(a["level"], 0)
                if a_sev > b_sev:
                    changes.append(("🔴 退化", name, f"{b['level']} → {a['level']}", a.get("message", "")))
                    if a["level"] == "ERROR":
                        total_new_err += 1
                    else:
                        total_new_warn += 1
                elif a_sev < b_sev:
                    changes.append(("🟢 修复", name, f"{b['level']} → {a['level']}", a.get("message", "")))
                    total_fixed += 1
            elif a and not b:
                changes.append(("🆕 新增", name, a["level"], a.get("message", "")))
            elif b and not a:
                changes.append(("🗑️ 移除", name, f"was {b['level']}", ""))

        if changes:
            print(f"\n  --- {section} ---")
            for icon, name, level, msg in changes:
                print(f"    {icon} {name}: {level}")
                if msg:
                    print(f"         {msg}")

    # 总结
    print("\n" + "=" * 60)
    if total_new_err > 0:
        print(f"  ❌ 新增 {total_new_err} 个 ERROR（必须修复！）")
    if total_new_warn > 0:
        print(f"  ⚠️  新增 {total_new_warn} 个 WARNING")
    if total_fixed > 0:
        print(f"  🟢 修复了 {total_fixed} 项")
    if total_new_err == 0 and total_new_warn == 0:
        print("  ✅ 无退化！可以安全提交。")

    verdict = "FAIL" if total_new_err > 0 else ("WARN" if total_new_warn > 0 else "PASS")
    print(f"\n  判定: {verdict}")
    print("=" * 60)

    log(f"diff: +{total_new_err}E/+{total_new_warn}W/-{total_fixed}fixed → {verdict}")
    return verdict


def show_history():
    """列出所有历史快照"""
    if not SNAPSHOTS_DIR.is_dir():
        print("暂无快照。")
        return
    files = sorted(SNAPSHOTS_DIR.glob("*.json"))
    if not files:
        print("暂无快照。")
        return
    print(f"共 {len(files)} 个快照：\n")
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        sections = data.get("sections", {})
        total_p = sum(len([r for r in s.get("results", []) if r["level"] == "PASS"]) for s in sections.values())
        total_w = sum(len([r for r in s.get("results", []) if r["level"] == "WARNING"]) for s in sections.values())
        total_e = sum(len([r for r in s.get("results", []) if r["level"] == "ERROR"]) for s in sections.values())
        print(f"  {f.name:40s} {total_p}P/{total_w}W/{total_e}E  ({data['timestamp'][:19]})")


def clean_old():
    """保留最近 10 对快照，删除其余"""
    if not SNAPSHOTS_DIR.is_dir():
        return
    for tag in ["before", "after"]:
        files = sorted(SNAPSHOTS_DIR.glob(f"{tag}_*.json"), reverse=True)
        for old in files[10:]:
            old.unlink()
            print(f"  🗑️ 已删除: {old.name}")
    log("clean: removed old snapshots")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    project_dir = None
    if "--project" in sys.argv:
        idx = sys.argv.index("--project")
        if idx + 1 < len(sys.argv):
            project_dir = Path(sys.argv[idx + 1])

    if cmd == "snapshot":
        if len(sys.argv) < 3 or sys.argv[2] not in ("before", "after"):
            print("用法: python baseline_compare.py snapshot before|after [--project <dir>]")
            return
        take_snapshot(sys.argv[2], project_dir)

    elif cmd == "diff":
        diff_snapshots(project_dir=project_dir)

    elif cmd == "history":
        show_history()

    elif cmd == "clean":
        clean_old()

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
