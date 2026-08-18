# 单位机一键启动脚本
# 用途: 开机后启动 Docker 服务 + 全部容器 + Cloudflare 临时隧道
# 由 Windows 任务计划程序在"用户登录时"触发

$ErrorActionPreference = "Continue"
$RepoDir = "D:\Geology\GMI"
$TunnelLog = "$RepoDir\cloudflared_tunnel.log"
$TunnelUrlFile = "$RepoDir\tunnel_url.txt"
$Cloudflared = "C:\cloudflared\cloudflared.exe"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path "$RepoDir\start_unit_machine.log" -Value "$ts $msg"
}

Log "=== start_unit_machine triggered ==="

# 1. 确保 Docker Desktop 已启动
$dockerRunning = $false
try { docker ps 2>$null | Out-Null; $dockerRunning = $? } catch { $dockerRunning = $false }
if (-not $dockerRunning) {
    Log "Docker not responding, launching Docker Desktop..."
    $dd = "C:\Users\99446\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
    if (Test-Path $dd) { Start-Process $dd }
    # 等待 daemon 就绪 (最多 90s)
    $ready = $false
    for ($i = 1; $i -le 30; $i++) {
        Start-Sleep -Seconds 3
        try { docker ps 2>$null | Out-Null; if ($?) { $ready = $true; break } } catch {}
    }
    if (-not $ready) { Log "ERROR: Docker daemon did not become ready"; exit 1 }
    Log "Docker daemon ready"
}

# 2. 启动全部容器
Set-Location $RepoDir
Log "docker compose up -d"
docker compose up -d 2>&1 | ForEach-Object { Log "compose: $_" }

# 3. 启动 Cloudflare 临时隧道 (指向前端 8080, 同源含 API)
$tunnelProc = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
if (-not $tunnelProc) {
    Log "starting cloudflared tunnel (frontend 8080)..."
    if (Test-Path $TunnelLog) { Remove-Item $TunnelLog -Force }
    Start-Process -FilePath $Cloudflared -ArgumentList "tunnel","--url","http://localhost:8080","--loglevel","info" -RedirectStandardOutput $TunnelLog -NoNewWindow
    # 等待并抓取隧道地址
    $url = ""
    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep -Seconds 2
        if (Test-Path $TunnelLog) {
            $m = Select-String -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -Path $TunnelLog -ErrorAction SilentlyContinue
            if ($m) { $url = $m[0].Matches[0].Value; break }
        }
    }
    if ($url) {
        # 同时写出系统首页地址与后端 API 文档地址, 方便对方访问
        $content = @"
系统首页(Web 界面): $url
后端 API 文档(Swagger): $url/api/v1/docs
本地后端(仅本机): http://localhost:8100/docs
"@
        Set-Content -Path $TunnelUrlFile -Value $content
        Log "TUNNEL URL: $url"
    } else {
        Log "WARN: tunnel URL not captured, check $TunnelLog"
    }
} else {
    Log "cloudflared already running (pid $($tunnelProc.Id))"
}

Log "=== done ==="
