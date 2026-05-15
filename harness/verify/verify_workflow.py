#!/usr/bin/env python3
"""
verify_workflow.py — 流程校验脚本

对照 workflow.json 检查一个项目是否按规定流程执行。
读取 workflow.json 中的阶段定义，逐项检查每个阶段的产出物是否存在。

用法：
    python verify_workflow.py <project_dir>                      # 自动检测适用的流程
    python verify_workflow.py <project_dir> --workflow single_agent
    python verify_workflow.py <project_dir> --workflow phase_development
    python verify_workflow.py --list                              # 列出所有已定义流程
    python verify_workflow.py --show phase_development            # 显示流程图

检查内容：
    WF-01: workflow.json 可读
    WF-02: 每个 required 阶段的 output 文件是否存在
    WF-03: 阶段顺序是否连贯（无跳跃）
    WF-04: 回退条件相关文件是否存在
    WF-05: 注册的 verify 脚本是否都存在
"""

import io, json, os, re, sys
from pathlib import Path
from datetime import datetime

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _lib import CLAUDE_DIR, SCRIPTS_DIR, TEMPLATES_DIR  # noqa: E402

WORKFLOW_JSON = TEMPLATES_DIR / "workflow.json"
LOG_FILE = CLAUDE_DIR / "logs" / "verify_workflow.log"


def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {msg}\n")


class WorkflowChecker:
    def __init__(self, project_dir, workflow_data):
        self.project_dir = Path(project_dir)
        self.workflow_data = workflow_data
        self.results = []

    def record(self, check_id, status, message):
        icon = {"PASS": "✅", "WARNING": "⚠️", "ERROR": "❌", "SKIP": "⏭️"}[status]
        self.results.append((check_id, status, message))
        print(f"  {icon} [{check_id}] {message}")

    def check_wf01_json_readable(self):
        """WF-01: workflow.json 可读且结构正确"""
        if not WORKFLOW_JSON.is_file():
            self.record("WF-01", "ERROR", f"workflow.json 不存在: {WORKFLOW_JSON}")
            return False
        try:
            data = json.loads(WORKFLOW_JSON.read_text(encoding="utf-8"))
            if "workflows" not in data:
                self.record("WF-01", "ERROR", "workflow.json 缺少 'workflows' 字段")
                return False
            n = len(data["workflows"])
            self.record("WF-01", "PASS", f"workflow.json 有效，{n} 个流程定义")
            return True
        except json.JSONDecodeError as e:
            self.record("WF-01", "ERROR", f"workflow.json 解析失败: {e}")
            return False

    def detect_workflow(self):
        """根据项目特征自动检测适用的流程"""
        docs = self.project_dir / "docs"
        has_progress = (docs / "PROGRESS.md").is_file()
        has_devlog = (docs / "dev-log").is_dir()
        has_handoff = (docs / "HANDOFF.md").is_file()
        has_spec = (docs / "SPEC.md").is_file()

        if has_progress or has_devlog:
            return "phase_development"
        elif has_handoff and not has_progress:
            return "dual_agent"
        elif has_spec:
            return "single_agent"
        return None

    def check_wf02_stage_outputs(self, workflow_name):
        """WF-02: 检查每个阶段的产出文件"""
        workflows = self.workflow_data.get("workflows", {})
        if workflow_name not in workflows:
            self.record("WF-02", "ERROR", f"未找到流程定义: {workflow_name}")
            return

        wf = workflows[workflow_name]
        stages = wf.get("stages", [])
        docs = self.project_dir / "docs"

        for stage in stages:
            if not stage.get("required", False):
                continue
            outputs = stage.get("output", [])
            stage_id = stage["id"]
            stage_name = stage["name"]

            for output in outputs:
                # 只检查明确的文件路径（以 docs/ 开头或 .md 结尾）
                if output.startswith("docs/") or output.endswith(".md"):
                    # 处理通配：phaseN → 检查是否有任何 phase*.md
                    if "phaseN" in output:
                        devlog = docs / "dev-log"
                        if devlog.is_dir() and list(devlog.glob("phase*.md")):
                            self.record("WF-02", "PASS", f"[{stage_id}] {output} → 存在 phase dev-log")
                        else:
                            self.record("WF-02", "WARNING", f"[{stage_id}] {output} → 缺少 dev-log")
                    else:
                        target = self.project_dir / output
                        if target.is_file():
                            self.record("WF-02", "PASS", f"[{stage_id}] {output} ✓")
                        else:
                            self.record("WF-02", "WARNING", f"[{stage_id}] {output} → 缺失")

    def check_wf03_stage_order(self, workflow_name):
        """WF-03: 检查阶段有没有被跳过"""
        workflows = self.workflow_data.get("workflows", {})
        wf = workflows.get(workflow_name, {})
        stages = wf.get("stages", [])
        docs = self.project_dir / "docs"

        completed = []
        for stage in stages:
            outputs = stage.get("output", [])
            has_any = False
            for output in outputs:
                if output.startswith("docs/"):
                    target = self.project_dir / output
                    if "phaseN" in output:
                        devlog = docs / "dev-log"
                        has_any = devlog.is_dir() and bool(list(devlog.glob("phase*.md")))
                    else:
                        has_any = target.is_file()
                    if has_any:
                        break
            completed.append((stage["id"], has_any))

        # 检查是否有"后面的阶段完成了但前面的没完成"
        found_gap = False
        last_completed = -1
        for i, (stage_id, done) in enumerate(completed):
            if done:
                if found_gap:
                    self.record("WF-03", "WARNING",
                                f"阶段 [{stage_id}] 已完成，但之前有阶段被跳过")
                    return
                last_completed = i
            elif i < len(completed) - 1 and last_completed >= 0:
                found_gap = True

        if not found_gap:
            self.record("WF-03", "PASS", "阶段顺序连贯，无跳跃")

    def check_wf04_scripts_exist(self):
        """WF-04: verify 脚本都存在"""
        registry = self.workflow_data.get("scripts_registry", {})
        missing = []
        for script_name in registry:
            if not (SCRIPTS_DIR / script_name).is_file():
                missing.append(script_name)
        if missing:
            self.record("WF-04", "WARNING", f"缺少验证脚本: {', '.join(missing)}")
        else:
            self.record("WF-04", "PASS", f"全部 {len(registry)} 个验证脚本存在")

    def check_wf05_progress_consistency(self, workflow_name):
        """WF-05: PROGRESS.md 中的完成状态和实际文件一致"""
        if workflow_name != "phase_development":
            self.record("WF-05", "SKIP", "非多 Phase 流程，跳过")
            return

        progress_file = self.project_dir / "docs" / "PROGRESS.md"
        if not progress_file.is_file():
            self.record("WF-05", "WARNING", "PROGRESS.md 不存在，无法校验一致性")
            return

        content = progress_file.read_text(encoding="utf-8")
        # 检查标记为 ✅ 的 Phase 是否有对应 dev-log
        completed_phases = re.findall(r'Phase\s+(\d+).*?✅', content, re.IGNORECASE)
        devlog_dir = self.project_dir / "docs" / "dev-log"

        if not completed_phases:
            self.record("WF-05", "PASS", "PROGRESS.md 无已完成 Phase（项目刚开始）")
            return

        missing_logs = []
        for phase_num in completed_phases:
            log_file = devlog_dir / f"phase{phase_num}.md"
            if not log_file.is_file():
                missing_logs.append(f"phase{phase_num}.md")

        if missing_logs:
            self.record("WF-05", "WARNING",
                        f"PROGRESS 标记完成但缺 dev-log: {', '.join(missing_logs)}")
        else:
            self.record("WF-05", "PASS",
                        f"{len(completed_phases)} 个已完成 Phase 都有 dev-log")

    def run(self, workflow_name=None):
        print("=" * 60)
        print("  verify_workflow.py — 流程校验")
        print(f"  项目: {self.project_dir}")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        print()

        # WF-01
        if not self.check_wf01_json_readable():
            return self.results

        # 检测流程
        if not workflow_name:
            workflow_name = self.detect_workflow()
            if workflow_name:
                print(f"  ℹ️  自动检测流程: {workflow_name}\n")
            else:
                print("  ⚠️  无法自动检测流程类型（项目缺少 docs/SPEC.md）\n")
                self.record("WF-detect", "WARNING", "无法检测流程类型")
                return self.results
        else:
            print(f"  ℹ️  指定流程: {workflow_name}\n")

        # WF-02 ~ WF-05
        self.check_wf02_stage_outputs(workflow_name)
        self.check_wf03_stage_order(workflow_name)
        self.check_wf04_scripts_exist()
        self.check_wf05_progress_consistency(workflow_name)

        # 统计
        counts = {"PASS": 0, "WARNING": 0, "ERROR": 0, "SKIP": 0}
        for _, status, _ in self.results:
            counts[status] = counts.get(status, 0) + 1

        print()
        print("-" * 60)
        print(f"  结果: {counts['PASS']} PASS / {counts['WARNING']} WARNING / {counts['ERROR']} ERROR")
        if counts["SKIP"] > 0:
            print(f"  跳过: {counts['SKIP']}")
        print("=" * 60)

        log(f"{self.project_dir.name} [{workflow_name}]: {counts['PASS']}P/{counts['WARNING']}W/{counts['ERROR']}E")
        return self.results


def show_workflow(name, data):
    """文字版流程图"""
    wf = data["workflows"].get(name)
    if not wf:
        print(f"未找到流程: {name}")
        return
    print(f"\n  📋 {wf['name']}")
    print(f"  触发条件: {wf.get('trigger', '—')}\n")

    stages = wf["stages"]
    for i, s in enumerate(stages):
        req = "★" if s.get("required") else " "
        actor = s.get("actor", "?")
        outputs = ", ".join(s.get("output", []))
        rb = s.get("rollback")
        rb_str = f" ↩ [{rb['condition']}]→{rb['target']}" if rb else ""

        connector = "───>" if i < len(stages) - 1 else "    "
        branch = s.get("branch")
        if branch:
            print(f"  {req} [{s['id']}] {s['name']} ({actor})")
            for cond, target in branch.items():
                print(f"        ├─ {cond} → {target}")
        else:
            print(f"  {req} [{s['id']}] {s['name']} ({actor}){rb_str}")
            if outputs:
                print(f"        产出: {outputs}")
        if i < len(stages) - 1:
            print(f"        │")


def main():
    if "--list" in sys.argv:
        data = json.loads(WORKFLOW_JSON.read_text(encoding="utf-8"))
        print("已定义的流程：")
        for name, wf in data["workflows"].items():
            print(f"  {name}: {wf['name']} (触发: {wf.get('trigger', '—')})")
        return

    if "--show" in sys.argv:
        idx = sys.argv.index("--show")
        if idx + 1 < len(sys.argv):
            data = json.loads(WORKFLOW_JSON.read_text(encoding="utf-8"))
            show_workflow(sys.argv[idx + 1], data)
        return

    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print(__doc__)
        return

    project_dir = Path(sys.argv[1])
    if not project_dir.is_dir():
        print(f"❌ 目录不存在: {project_dir}")
        return

    workflow_name = None
    if "--workflow" in sys.argv:
        idx = sys.argv.index("--workflow")
        if idx + 1 < len(sys.argv):
            workflow_name = sys.argv[idx + 1]

    data = json.loads(WORKFLOW_JSON.read_text(encoding="utf-8"))
    checker = WorkflowChecker(project_dir, data)
    results = checker.run(workflow_name)

    has_error = any(s == "ERROR" for _, s, _ in results)
    sys.exit(1 if has_error else 0)


if __name__ == "__main__":
    main()
