# deploy_skill_symlinks.ps1
# 将 global-memory/skills 中的 Skill 部署为 Junction 到 ~/.claude/skills/
# 用法: powershell -ExecutionPolicy Bypass -File deploy_skill_symlinks.ps1
# 需要: 管理员权限或已开启开发者模式

$Repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$SkillsRepo = Join-Path $Repo 'skills'
$SkillsDir  = "$env:USERPROFILE\.claude\skills"

# 自动扫描：排除 _ 开头目录，只保留含 SKILL.md 的
$Skills = Get-ChildItem -Path $SkillsRepo -Directory |
    Where-Object { $_.Name -notlike '_*' } |
    Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') } |
    Select-Object -ExpandProperty Name

if (!(Test-Path $SkillsDir)) { New-Item -ItemType Directory -Path $SkillsDir | Out-Null }

foreach ($skill in $Skills) {
    $src = Join-Path $SkillsRepo $skill
    $dst = Join-Path $SkillsDir $skill

    if (!(Test-Path $src)) {
        Write-Host "[SKIP] $src not found" -ForegroundColor Yellow
        continue
    }

    if (Test-Path $dst) {
        $item = Get-Item $dst
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            $target = $item.Target
            if ($target -eq $src) {
                Write-Host "[OK]   $skill -> $src" -ForegroundColor Green
            } else {
                Remove-Item $dst -Force
                New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
                Write-Host "[FIX]  $skill -> $src (was $target)" -ForegroundColor Cyan
            }
        } else {
            Write-Host "[SKIP] $dst exists and is not a junction" -ForegroundColor Yellow
        }
    } else {
        New-Item -ItemType Junction -Path $dst -Target $src | Out-Null
        Write-Host "[NEW]  $skill -> $src" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Done. Contents of ${SkillsDir}:"
Get-ChildItem $SkillsDir | Format-Table Name, @{N='Target';E={$_.Target}} -AutoSize
