#!/bin/bash
# 记忆 Git 同步脚本

MEMORY_DIR="$HOME/.claude/global-memory"
cd "$MEMORY_DIR" || { echo "❌ 目录不存在: $MEMORY_DIR"; exit 1; }

if [ ! -d ".git" ]; then
    echo "❌ 不是 Git 仓库: $MEMORY_DIR"
    exit 1
fi

echo "=== 记忆同步 ==="

git pull --rebase --quiet 2>&1

CHANGES=$(git status --porcelain | wc -l)
if [ "$CHANGES" -gt 0 ]; then
    git add -A
    git commit -m "memory-sync: $(date +%Y%m%d_%H%M%S) [${CHANGES} files]" --quiet
    git push --quiet 2>&1
    echo "✅ 已同步 $CHANGES 个文件变更"
else
    echo "✅ 无变更，已是最新"
fi
