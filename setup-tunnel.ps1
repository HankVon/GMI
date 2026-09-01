# 安装 cloudflared 开机自启计划任务并立即启动, 关闭会冲突的原服务。
# 用法: 直接运行本脚本即可, 若当前不是管理员会自动弹出 UAC 提权。
#       & "D:\Geology\GMI\setup-tunnel.ps1"

# --- 若非管理员, 自动请求提权 ---
if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "需要管理员权限, 正在请求提权 (UAC)..."
  Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
  exit
}

$ErrorActionPreference = "Stop"
$taskName = "CloudflaredTunnel"
$xmlPath = Join-Path $PSScriptRoot "cloudflared-task.xml"

if (-not (Test-Path $xmlPath)) {
  Write-Error "missing cloudflared-task.xml"
  exit 1
}

Write-Host "Importing scheduled task..."
schtasks.exe /Create /TN $taskName /XML "$xmlPath" /F

Write-Host "Starting task..."
schtasks.exe /Run /TN $taskName
Start-Sleep -Seconds 8

Write-Host "Disabling legacy cloudflared service..."
sc.exe config cloudflared start= disabled

Write-Host "Done. The tunnel will auto-start on next boot."
Write-Host "Note: any currently-running cloudflared process is left as-is (harmless duplicate connector)."
