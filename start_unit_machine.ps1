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

# 2.1 启动 crawl4ai 本地抓取服务(宿主机 11235, 容器通过 host.docker.internal 访问)
$c4aConn = Get-NetTCPConnection -LocalPort 11235 -ErrorAction SilentlyContinue
if (-not $c4aConn) {
    $c4aPy = "E:\Software\miniconda3\envs\GMI\python.exe"
    $c4aSrv = "$RepoDir\crawl4ai-server\crawl4ai_server.py"
    $c4aLog = "$RepoDir\runtime\crawl4ai-server.log"
    if (Test-Path $c4aPy) {
        Log "starting crawl4ai server (port 11235)..."
        New-Item -ItemType Directory -Force -Path "$RepoDir\runtime" | Out-Null
        Start-Process -FilePath $c4aPy -ArgumentList $c4aSrv `
            -RedirectStandardOutput $c4aLog -RedirectStandardError "$c4aLog.err" `
            -WindowStyle Hidden
        Start-Sleep -Seconds 8
        if (Get-NetTCPConnection -LocalPort 11235 -ErrorAction SilentlyContinue) {
            Log "crawl4ai server ready on 11235"
        } else {
            Log "WARN: crawl4ai not up yet, check $c4aLog"
        }
    } else {
        Log "WARN: crawl4ai python not found: $c4aPy"
    }
} else {
    Log "crawl4ai already running (pid $($c4aConn.OwningProcess))"
}

# 3. 启动 Cloudflare 命名隧道 (自定义域名 sct5dzd.xyz -> 前端 8080, 同源含 API)
# 前置: cloudflared login 选 sct5dzd.xyz + cloudflared tunnel create gmi-tunnel + DNS 已指向隧道
# 优先使用已注册的 Windows 服务(cloudflared, 开机自启); 服务不存在时降级为前台进程。
$TunnelName = "gmi-tunnel"
$svc = Get-Service -Name "cloudflared" -ErrorAction SilentlyContinue
if ($svc) {
    if ($svc.Status -ne "Running") {
        Log "starting cloudflared Windows service..."
        try { Start-Service -Name "cloudflared" -ErrorAction Stop } catch { Log "WARN: failed to start service: $_" }
        Start-Sleep -Seconds 5
    } else {
        Log "cloudflared service already running"
    }
    # 写固定域名信息
    $content = @"
系统首页(Web 界面): https://sct5dzd.xyz
后端 API 文档(Swagger): https://sct5dzd.xyz/api/v1/docs
本地后端(仅本机): http://localhost:8200/docs
"@
    Set-Content -Path $TunnelUrlFile -Value $content
    Log "TUNNEL READY (service): https://sct5dzd.xyz"
} else {
    # 降级: 无服务时前台启动 (避免与潜在服务实例冲突, 先检测是否已在跑)
    $tunnelProc = Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue
    if (-not $tunnelProc) {
        Log "cloudflared service not found, starting named tunnel in foreground ($TunnelName)..."
        if (Test-Path $TunnelLog) { Remove-Item $TunnelLog -Force }
        Start-Process -FilePath $Cloudflared -ArgumentList "tunnel","run","$TunnelName","--loglevel","info" -RedirectStandardOutput $TunnelLog -NoNewWindow
        $ready = $false
        for ($i = 1; $i -le 20; $i++) {
            Start-Sleep -Seconds 2
            if (Test-Path $TunnelLog) {
                $m = Select-String -Pattern "Registered tunnel connection|connection registered" -Path $TunnelLog -ErrorAction SilentlyContinue
                if ($m) { $ready = $true; break }
            }
        }
        if ($ready) {
            $content = @"
系统首页(Web 界面): https://sct5dzd.xyz
后端 API 文档(Swagger): https://sct5dzd.xyz/api/v1/docs
本地后端(仅本机): http://localhost:8200/docs
"@
            Set-Content -Path $TunnelUrlFile -Value $content
            Log "TUNNEL READY: https://sct5dzd.xyz"
        } else {
            Log "WARN: tunnel not ready, check $TunnelLog"
        }
    } else {
        Log "cloudflared already running (pid $($tunnelProc.Id))"
    }
}

Log "=== done ==="
