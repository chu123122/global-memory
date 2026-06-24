#!/usr/bin/env bash
# deploy_skill_symlinks.sh
# 将 global-memory/skills 中的 Skill 部署为 symlink 到 ~/.claude/skills/
# 用法: bash deploy_skill_symlinks.sh
# 需要: macOS/Linux 直接运行; Windows 需要管理员权限或开发者模式

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_REPO="$REPO_DIR/skills"
SKILLS_DIR="$HOME/.claude/skills"

# 自动扫描 Skill 列表（排除 _ 开头的目录，只保留含 SKILL.md 的）
SKILLS=()
for dir in "$SKILLS_REPO"/*/; do
  skill=$(basename "$dir")
  [[ "$skill" == _* ]] && continue
  [ -f "$dir/SKILL.md" ] || continue
  SKILLS+=("$skill")
done

mkdir -p "$SKILLS_DIR"

for skill in "${SKILLS[@]}"; do
  SRC="$SKILLS_REPO/$skill"
  DST="$SKILLS_DIR/$skill"

  if [ ! -d "$SRC" ]; then
    echo "⚠️  SKIP: $SRC 不存在"
    continue
  fi

  if [ -L "$DST" ]; then
    # 已经是 symlink，检查目标是否正确
    CURRENT=$(readlink "$DST" 2>/dev/null || echo "")
    if [ "$CURRENT" = "$SRC" ]; then
      echo "✅ OK:   $skill → $SRC"
    else
      echo "🔧 FIX:  $skill → 旧目标 $CURRENT，更新为 $SRC"
      rm "$DST"
      ln -s "$SRC" "$DST"
    fi
  elif [ -e "$DST" ]; then
    echo "⚠️  SKIP: $DST 已存在且不是 symlink（手动处理）"
  else
    ln -s "$SRC" "$DST"
    echo "✅ NEW:  $skill → $SRC"
  fi
done

echo ""
echo "部署完成。当前 $SKILLS_DIR 内容："
ls -la "$SKILLS_DIR"

# === Part 2: 部署 agents 目录 ===
echo ""
echo "=== 部署 Agents ==="

AGENTS_SRC="$REPO_DIR/agents"
AGENTS_DST="$HOME/.claude/agents"

if [ ! -d "$AGENTS_SRC" ]; then
  echo "⚠️  SKIP: $AGENTS_SRC 不存在"
else
  if [ -L "$AGENTS_DST" ]; then
    CURRENT=$(readlink "$AGENTS_DST" 2>/dev/null || echo "")
    if [ "$CURRENT" = "$AGENTS_SRC" ]; then
      echo "✅ OK:   agents/ → $AGENTS_SRC"
    else
      echo "🔧 FIX:  agents/ → 旧目标 $CURRENT，更新为 $AGENTS_SRC"
      rm "$AGENTS_DST"
      ln -s "$AGENTS_SRC" "$AGENTS_DST"
    fi
  elif [ -d "$AGENTS_DST" ]; then
    echo "🔧 FIX:  agents/ 是普通目录，备份后替换为 symlink"
    mv "$AGENTS_DST" "${AGENTS_DST}.bak.$(date +%Y%m%d%H%M%S)"
    ln -s "$AGENTS_SRC" "$AGENTS_DST"
  else
    ln -s "$AGENTS_SRC" "$AGENTS_DST"
    echo "✅ NEW:  agents/ → $AGENTS_SRC"
  fi
fi

echo ""
echo "当前 agents/ 内容："
ls -la "$AGENTS_DST"
