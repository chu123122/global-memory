#!/usr/bin/env python3
"""
auto_sync_daemon.py — global-memory 自动同步守护进程

原理：
  监听 active global-memory 单仓库的文件变更。
  最后一次变更后 IDLE_MINUTES 分钟没有新变更，自动执行 git sync。
  
用法：
  pythonw auto_sync_daemon.py          # 无窗口后台运行
  python  auto_sync_daemon.py          # 前台运行（调试用）
  python  auto_sync_daemon.py --once   # 立即同步一次然后退出
"""

import io
import json
import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# ── 配置 ──
IDLE_MINUTES = 5            # 最后一次变更后多久触发同步
POLL_INTERVAL = 30          # 轮询间隔（秒）
CLAUDE_DIR = Path.home() / ".claude"
HARNESS_DIR = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("GLOBAL_MEMORY_DIR", HARNESS_DIR.parent))
WATCH_REPOS = [REPO_DIR]
LOG_FILE = CLAUDE_DIR / "auto_sync.log"

# ── 日志 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("auto_sync")


def run_maintenance_scripts(repo_path: Path):
    """在 global-memory 同步前运行维护脚本（索引同步 + 统计更新）"""
    if repo_path.resolve() != REPO_DIR.resolve():
        return

    scripts_dir = HARNESS_DIR
    if not (scripts_dir / "sync_index.py").is_file():
        log.debug("维护脚本不存在，跳过")
        return

    log.info(f"[{repo_path.name}] 运行维护脚本...")

    for script_name in ["sync_index.py", "update_stats.py"]:
        script = scripts_dir / script_name
        if script.is_file():
            try:
                result = subprocess.run(
                    [sys.executable, str(script)],
                    capture_output=True, text=True, encoding="utf-8",
                    cwd=str(scripts_dir), timeout=30
                )
                if result.returncode == 0:
                    log.info(f"  ✅ {script_name} 完成")
                else:
                    log.warning(f"  ⚠️ {script_name} 返回码 {result.returncode}")
            except subprocess.TimeoutExpired:
                log.warning(f"  ⚠️ {script_name} 超时")
            except Exception as e:
                log.warning(f"  ⚠️ {script_name} 失败: {e}")


def git_sync(repo_path: Path) -> bool:
    """对指定仓库执行同步。实际 Git 逻辑委托给 maintain.py。"""
    if not (repo_path / ".git").is_dir():
        log.warning(f"跳过（非 Git 仓库）: {repo_path}")
        return False

    repo_name = repo_path.name
    maintain = HARNESS_DIR / "maintain.py"
    log.info(f"[{repo_name}] 触发 maintain.py sync --source daemon")
    r = subprocess.run(
        [sys.executable, str(maintain), "sync", "--source", "daemon", "--json"],
        cwd=str(repo_path),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180,
    )
    if r.returncode != 0:
        log.error(f"[{repo_name}] sync 失败: {r.stderr or r.stdout}")
        return False
    try:
        data = json.loads(r.stdout)
        if data.get("synced"):
            log.info(f"[{repo_name}] ✅ 同步完成: {data.get('commit')}")
            return True
        log.info(f"[{repo_name}] 无需同步: {data.get('summary')}")
        return False
    except Exception:
        log.info(f"[{repo_name}] sync 完成")
        return True


def get_latest_mtime(repo_path: Path) -> float:
    """获取仓库中最新的文件修改时间（排除 .git 目录）"""
    latest = 0.0
    try:
        for f in repo_path.rglob("*"):
            if ".git" in f.parts:
                continue
            if f.is_file():
                mt = f.stat().st_mtime
                if mt > latest:
                    latest = mt
    except OSError:
        pass
    return latest


def sync_all():
    """同步所有仓库"""
    synced = 0
    for repo in WATCH_REPOS:
        if repo.is_dir():
            if git_sync(repo):
                synced += 1
    return synced


def main():
    # --once 模式：立即同步然后退出
    if "--once" in sys.argv:
        log.info("=== 单次同步模式 ===")
        sync_all()
        return

    log.info("=== 自动同步守护进程启动 ===")
    log.info(f"监听目录: {[str(r) for r in WATCH_REPOS]}")
    log.info(f"空闲阈值: {IDLE_MINUTES} 分钟")
    log.info(f"轮询间隔: {POLL_INTERVAL} 秒")
    log.info(f"日志文件: {LOG_FILE}")

    # 记录每个仓库上次已知的 mtime 和上次同步时间
    last_known_mtime = {}
    last_sync_time = {}
    pending_sync = {}  # 标记哪个仓库有待同步的变更

    for repo in WATCH_REPOS:
        last_known_mtime[str(repo)] = get_latest_mtime(repo)
        last_sync_time[str(repo)] = time.time()
        pending_sync[str(repo)] = False

    try:
        while True:
            time.sleep(POLL_INTERVAL)
            now = time.time()

            for repo in WATCH_REPOS:
                key = str(repo)
                if not repo.is_dir():
                    continue

                current_mtime = get_latest_mtime(repo)

                if current_mtime > last_known_mtime[key]:
                    # 有新变更
                    last_known_mtime[key] = current_mtime
                    pending_sync[key] = True
                    last_sync_time[key] = now  # 重置空闲计时器
                    log.debug(f"[{repo.name}] 检测到文件变更，重置计时器")

                elif pending_sync[key]:
                    # 有待同步的变更，检查是否已空闲足够时间
                    idle_seconds = now - last_sync_time[key]
                    if idle_seconds >= IDLE_MINUTES * 60:
                        log.info(f"[{repo.name}] 空闲 {IDLE_MINUTES} 分钟，触发自动同步")
                        if git_sync(repo):
                            pending_sync[key] = False
                            last_known_mtime[key] = get_latest_mtime(repo)
                        else:
                            pending_sync[key] = False  # 无实际变更，取消待同步

    except KeyboardInterrupt:
        log.info("=== 守护进程收到中断信号，退出 ===")
        # 退出前做最后一次同步
        log.info("退出前最后同步...")
        sync_all()
        log.info("=== 守护进程已停止 ===")


if __name__ == "__main__":
    main()
