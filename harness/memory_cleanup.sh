#!/bin/bash
# 记忆文件月度清理
# 检查 30 天未更新的文件，列出候选归档项

MEMORY_DIR="${1:-$HOME/.claude/global-memory}"
ARCHIVE_DIR="$MEMORY_DIR/archives/$(date +%Y-%m)"
THRESHOLD_DAYS=30

echo "=== 记忆文件清理检查 ==="
echo "目录: $MEMORY_DIR"
echo "阈值: ${THRESHOLD_DAYS} 天未更新"
echo ""

CANDIDATES=0
for dir in feedback knowledge fixes decisions interview; do
    FULL_DIR="$MEMORY_DIR/$dir"
    [ ! -d "$FULL_DIR" ] && continue

    for f in "$FULL_DIR"/*.md; do
        [ ! -f "$f" ] && continue
        [ "$(basename $f)" = ".gitkeep" ] && continue
        # 跨平台获取文件修改时间（Python，兼容 macOS/Linux/Windows Git Bash）
        MOD_TIME=$(python3 -c "import os; print(int(os.path.getmtime('$f')))" 2>/dev/null || python -c "import os; print(int(os.path.getmtime('$f')))" 2>/dev/null)
        if [ -z "$MOD_TIME" ]; then
            echo "⚠️ 无法获取修改时间: $(basename $f) (需要 python3 或 python)"
            continue
        fi
        NOW=$(date +%s)
        DAYS_AGO=$(( (NOW - MOD_TIME) / 86400 ))
        if [ $DAYS_AGO -gt $THRESHOLD_DAYS ]; then
            echo "📦 候选归档: $(basename $f) (${DAYS_AGO}天未更新)"
            CANDIDATES=$((CANDIDATES + 1))
        fi
    done
done

echo ""
if [ $CANDIDATES -gt 0 ]; then
    echo "共 $CANDIDATES 个文件建议归档到 $ARCHIVE_DIR"
    echo "确认后运行: mkdir -p $ARCHIVE_DIR && mv <file> $ARCHIVE_DIR/"
else
    echo "✅ 所有记忆文件活跃，无需清理"
fi
