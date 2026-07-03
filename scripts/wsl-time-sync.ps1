# WSL2 时钟同步修复脚本
# 以管理员身份运行: PowerShell -ExecutionPolicy Bypass .\scripts\wsl-time-sync.ps1
#
# 解决 WSL2 笔记本合盖/休眠唤醒后的时钟漂移问题。
# 漂移症状: HTTPS 证书验证失败、JWT token 过早过期、API 返回 SSL 错误

Write-Host "=== WSL2 时钟同步修复 ===" -ForegroundColor Cyan

# 获取 WSL 发行版名称
$distro = "Ubuntu"
try {
    $list = wsl -l -q 2>$null
    if ($list) {
        $distro = ($list | Select-Object -First 1).Trim()
        Write-Host "检测到 WSL 发行版: $distro" -ForegroundColor Green
    }
} catch {
    Write-Host "未检测到 WSL，使用默认名称: $distro" -ForegroundColor Yellow
}

# 立即同步一次
Write-Host "正在同步时间..." -ForegroundColor Yellow
try {
    wsl -d $distro -u root hwclock -s 2>&1 | Out-Null
    $wslTime = wsl -d $distro date "+%Y-%m-%d %H:%M:%S"
    Write-Host "WSL 当前时间: $wslTime" -ForegroundColor Green
    Write-Host "时间同步成功" -ForegroundColor Green
} catch {
    Write-Host "时间同步失败: $_" -ForegroundColor Red
    Write-Host "请检查: 1) WSL 是否已启动  2) 是否以管理员身份运行" -ForegroundColor Yellow
    exit 1
}

# ── 注册计划任务（开机 + 唤醒） ──────────────────────────
$taskName = "WSL2-TimeSync"
$action = New-ScheduledTaskAction -Execute "wsl.exe" -Argument "-d $distro -u root hwclock -s"
$triggers = @(
    New-ScheduledTaskTrigger -AtStartup,
    New-ScheduledTaskTrigger -AtWakeFromSleep
)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Force
    Write-Host "计划任务 '$taskName' 已注册（开机 + 唤醒时自动同步）" -ForegroundColor Green
} catch {
    Write-Host "计划任务注册失败: $_" -ForegroundColor Red
    Write-Host "手动方案: 将以下命令加入 Windows 启动脚本" -ForegroundColor Yellow
    Write-Host "  wsl -d $distro -u root hwclock -s" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 完成 ===" -ForegroundColor Cyan
Write-Host "验证计划任务:" -ForegroundColor Gray
Write-Host "  Get-ScheduledTask -TaskName '$taskName' | fl" -ForegroundColor Gray
