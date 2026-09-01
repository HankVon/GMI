# 启动 crawl4ai 精简 HTTP 服务 (11235 端口)
# 运行环境: miniconda3 GMI 环境 (Python 3.11, 已安装 crawl4ai 0.9.2 / playwright / ddddocr)
# 后端 (Docker 容器) 通过 http://host.docker.internal:11235 调用

$python = "E:\Software\miniconda3\envs\GMI\python.exe"
$server = "d:\Geology\GMI\crawl4ai-server\crawl4ai_server.py"
$log = "d:\Geology\GMI\runtime\crawl4ai-server.log"

# 检查是否已在运行
$existing = Get-NetTCPConnection -LocalPort 11235 -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "crawl4ai server already running on port 11235 (PID $($existing.OwningProcess))"
    exit 0
}

if (-not (Test-Path $python)) {
    Write-Host "ERROR: python not found: $python"
    exit 1
}

New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null
Start-Process -FilePath $python -ArgumentList $server `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
    -WindowStyle Hidden
Start-Sleep 5
if (Get-NetTCPConnection -LocalPort 11235 -ErrorAction SilentlyContinue) {
    Write-Host "crawl4ai server ready on port 11235, log: $log"
} else {
    Write-Host "WARNING: crawl4ai may not be up yet (check $log)"
}
