#!/bin/bash
# 通用格式规范检查
# 用法：bash format_check.sh [目录，默认当前目录]

DIR="${1:-.}"
ISSUES=0

echo "=== 格式规范检查: $DIR ==="

# 检查文件命名（不含中文和特殊字符）
echo "--- 文件命名 ---"
for f in $(find "$DIR" -type f -name "*[^a-zA-Z0-9._/-]*" | grep -v ".git"); do
    echo "⚠️ 异常命名: $f"
    ISSUES=$((ISSUES + 1))
done

# 检查行尾空格
echo "--- 行尾空格 ---"
TRAILING=$(grep -rn ' $' "$DIR" --include="*.md" --include="*.lua" --include="*.cpp" --include="*.h" 2>/dev/null | wc -l)
if [ "$TRAILING" -gt 0 ]; then
    echo "⚠️ $TRAILING 行有行尾空格"
    ISSUES=$((ISSUES + 1))
fi

# 检查 Tab vs Space
echo "--- Tab/Space 一致性 ---"
TAB_FILES=$(grep -rl '	' "$DIR" --include="*.lua" --include="*.cpp" --include="*.h" 2>/dev/null | wc -l)
if [ "$TAB_FILES" -gt 0 ]; then
    echo "⚠️ $TAB_FILES 个文件使用了 Tab 缩进"
fi

echo ""
if [ $ISSUES -eq 0 ]; then
    echo "✅ 格式检查通过"
    exit 0
else
    echo "⚠️ 共 $ISSUES 个格式问题"
    exit 1
fi
