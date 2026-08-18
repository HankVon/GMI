# 启动 crawl4ai 精简 HTTP 服务 (11235 端口)
# 运行环境: graphene (Python 3.11, 已安装 crawl4ai 0.9.2 editable)
# 后端 (Python 3.9) 通过 http://127.0.0.1:11235 调用

$python = "D:\anaconda\envs\graphenv\python.exe"
$server = "d:\Geology\SSM\crawl4ai-server\crawl4ai_server.py"
$log = "d:\Geology\SSM\runtime\crawl4ai-server.log"

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

Start-Process -FilePath $python -ArgumentList $server `
    -RedirectStandardOutput $log -RedirectStandardError "$log.err" `
    -WindowStyle Hidden
Write-Host "crawl4ai server started, log: $log"
