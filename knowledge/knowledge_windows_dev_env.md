---
description: Windows 开发环境踩坑记录
priority: medium
status: active
trigger:
  keywords:
    - concept:build
    - platform:windows
  tags:
    - skill
    - infra
  stages:
    - implementation
last_updated: 2026-05-20
---

---
name: knowledge-windows-dev-env
description: Windows 开发环境踩坑记录，覆盖 Git Bash/MSYS 路径、软链、CRLF 等差异
summary: "已记录 ln -s / mklink 差异、cygpath、cmd //c、CRLF 与 MSYS 路径转换坑"
type: knowledge
created: 2026-04-17
updated: 2026-04-21
source: 心动项目环境初始化 + Windows 工具链排障
access_count: 0
---

# Windows 开发环境踩坑记录

> 用 git bash / MSYS / Cygwin 在 Windows 上跑 Unix 工具链时的差异点。
> 写脚本时若依赖以下行为，必须做平台分支或显式提示。

---

## 1. `ln -s` 默认是复制，不是软链

**症状**：在 git bash 里 `ln -s /src /dst` 看似成功，`ls -la` 看 dst 是普通目录（`drwxr-xr-x`，没有 `l` 标志）。改源目录后 dst 不更新。

**根因**：Windows 创建符号链接需要特权（NTFS reparse point）。Git Bash / MSYS2 默认 `MSYS=winsymlinks:cp`（复制）而非 `nativestrict`（真软链）。即使设了 native，没开发者模式 / 管理员权限也会失败。

**修复方案**（在 bash 脚本里跨平台支持）：
```bash
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) IS_WINDOWS=1 ;;
  *) IS_WINDOWS=0 ;;
esac

make_dir_symlink() {
  local src="$1" dst="$2"
  if [ "$IS_WINDOWS" = "1" ]; then
    local src_win=$(cygpath -w "$src")
    local dst_win=$(cygpath -w "$dst")
    cmd //c "mklink /D \"$dst_win\" \"$src_win\"" >/dev/null 2>&1 \
      || cp -r "$src" "$dst"   # 回退：复制（需重跑同步）
  else
    ln -s "$src" "$dst"
  fi
}
```

**让 mklink 免提权**：`Win + I` → 系统 → 开发者 → 开启「开发者模式」（Win10 1703+）。开后普通用户也能 `mklink /D`，无需管理员。

**案例**：`~/.claude/scripts/deploy_skill_symlinks.sh` 早期版本只用 `ln -s`，导致 `skills-repo/` 改了源文件后 `~/.claude/skills/` 不同步，得重跑脚本。2026-04-17 修复为平台检测 + mklink 回退。

**判断 dst 是否真软链**：
- `[ -L "$dst" ]` —— mklink /D 创建的目录链接在 git bash 里也能识别
- `ls -la` 看首字符：`l` 是软链，`d` 是普通目录

---

## 2. 路径分隔符 / drive letter

- POSIX 路径 `/c/Users/...` ↔ Windows 路径 `C:\Users\...`：用 `cygpath -w`（→Win）/ `cygpath -u`（→POSIX）转换
- 调 Windows 原生命令（cmd / 第三方 exe）传路径时几乎都要 `cygpath -w`

## 3. `cmd //c` 的双斜杠

git bash 里调 cmd 内部命令必须 `cmd //c "..."`（双斜杠）。单斜杠 `cmd /c` 会被 MSYS 路径转换吃掉变成 `cmd C:/...`。

## 4. CRLF 行尾

- git 默认 `core.autocrlf=true` 在 Windows 上 checkout 时把 LF→CRLF
- bash 脚本含 CRLF 会报 `'\r': command not found` 或 shebang 失效
- 修复：仓库根加 `.gitattributes`：
  ```
  *.sh text eol=lf
  ```
  或单文件 `dos2unix script.sh`
