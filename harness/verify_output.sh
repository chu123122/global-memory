#!/bin/bash
# 通用输出文件验证脚本
# 用法：bash verify_output.sh <expected_files_list>

if [ -z "$1" ]; then
    echo "用法: bash verify_output.sh <expected_files_list>"
    exit 1
fi

EXPECTED_FILE="$1"
MISSING=0
TOTAL=0

echo "=== 文件完整性验证 ==="
while IFS= read -r file; do
    [ -z "$file" ] && continue
    TOTAL=$((TOTAL + 1))
    if [ ! -f "$file" ]; then
        echo "❌ 缺失: $file"
        MISSING=$((MISSING + 1))
    else
        SIZE=$(wc -c < "$file")
        echo "✅ 存在: $file ($SIZE bytes)"
    fi
done < "$EXPECTED_FILE"

echo ""
echo "=== 结果: $((TOTAL - MISSING))/$TOTAL 文件存在 ==="
if [ $MISSING -gt 0 ]; then
    echo "⚠️ 缺失 $MISSING 个文件"
    exit 1
else
    echo "✅ 所有文件齐全"
    exit 0
fi
