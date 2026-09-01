# SSM Platform - One-Click Launcher
# Usage: powershell -ExecutionPolicy Bypass -File start_all.ps1
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

# 固定端口: 注册 Windows 管理员端口排除区间, 防止被系统动态保留抢占(仅管理员运行时生效, 失败不阻断启动)
function Reserve-Port($p) {
    try {
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        if (-not $isAdmin) { return }
        $existing = netsh interface ipv4 show excludedportrange protocol=tcp 2>$null
        if ($existing -match "\s+$p\s") { return }
        netsh interface ipv4 add excludedportrange protocol=tcp startport=$p numberofports=1 2>$null
    } catch {}
}
Reserve-Port 8200
Reserve-Port 5173
Reserve-Port 11235

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SSM Data Platform - Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# [1/6] Start MySQL & Redis
Write-Host "`n[1/6] Starting MySQL & Redis containers..." -ForegroundColor Yellow

$mysqlRunning = docker ps --filter "name=ssm-mysql" --format "{{.Names}}" 2>$null
if (-not $mysqlRunning) {
    $mysqlExists = docker ps -a --filter "name=ssm-mysql" --format "{{.Names}}" 2>$null
    if ($mysqlExists) {
        docker start ssm-mysql 2>$null | Out-Null
    } else {
        Write-Host "  Creating MySQL container (port 13306)..." -ForegroundColor Gray
        docker run -d --name ssm-mysql `
          -e MYSQL_ROOT_PASSWORD=root_pass `
          -e MYSQL_DATABASE=ssm `
          -e MYSQL_USER=ssm_user `
          -e MYSQL_PASSWORD=ssm_pass `
          -p 13306:3306 `
          mysql:8.0 `
          --character-set-server=utf8mb4 `
          --collation-server=utf8mb4_unicode_ci `
          --default-authentication-plugin=mysql_native_password 2>&1 | Out-Null
    }
} else {
    Write-Host "  MySQL already running" -ForegroundColor Green
}

$redisRunning = docker ps --filter "name=ssm-redis" --format "{{.Names}}" 2>$null
if (-not $redisRunning) {
    $redisExists = docker ps -a --filter "name=ssm-redis" --format "{{.Names}}" 2>$null
    if ($redisExists) {
        docker start ssm-redis 2>$null | Out-Null
    } else {
        docker run -d --name ssm-redis -p 6379:6379 redis:7-alpine 2>&1 | Out-Null
    }
} else {
    Write-Host "  Redis already running" -ForegroundColor Green
}

# [2/6] Wait for MySQL
Write-Host "`n[2/6] Waiting for MySQL..." -ForegroundColor Yellow
$retry = 0
do {
    Start-Sleep 3
    $ready = docker exec ssm-mysql mysqladmin ping -ussm_user -pssm_pass --silent 2>$null
    $retry++
    if ($retry -gt 20) {
        Write-Host "  ERROR: MySQL startup timeout" -ForegroundColor Red
        exit 1
    }
} until ($ready)
Write-Host "  MySQL ready!" -ForegroundColor Green

# [3/6] Import DDL
Write-Host "`n[3/6] Importing DDL..." -ForegroundColor Yellow
$tableCheck = docker exec ssm-mysql mysql -ussm_user -pssm_pass ssm -e "SHOW TABLES LIKE 'field_metadata';" 2>$null
if ($tableCheck -match "field_metadata") {
    Write-Host "  Tables exist, skip DDL import" -ForegroundColor Green
} else {
    Write-Host "  Running sql/001_init_ddl.sql ..." -ForegroundColor Gray
    $ddlResult = cmd /c "docker exec -i ssm-mysql mysql -ussm_user -pssm_pass --default-character-set=utf8mb4 ssm < sql\001_init_ddl.sql" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: DDL import failed" -ForegroundColor Red
        Write-Host $ddlResult
        exit 1
    }
    Write-Host "  DDL imported!" -ForegroundColor Green
}

# [4/6] Fix admin password
Write-Host "`n[4/6] Setting admin password..." -ForegroundColor Yellow
$ssmPython = "D:\anaconda\python.exe"
if (-not (Test-Path $ssmPython)) { $ssmPython = "python" }
Push-Location backend
$hashOutput = & $ssmPython -c "import sys; sys.path.insert(0,'.'); from app.services.auth_service import hash_password; print(hash_password('admin123'))" 2>$null
Pop-Location
$hash = if ($hashOutput) { ($hashOutput -split "`n")[0].Trim() } else { "" }
if ($hash) {
    docker exec ssm-mysql mysql -ussm_user -pssm_pass ssm -e "UPDATE sys_user SET password_hash='$hash' WHERE username='admin';" 2>$null
    Write-Host "  Admin password set: admin / admin123" -ForegroundColor Green
} else {
    Write-Host "  WARNING: hash generation failed (passlib/bcrypt), password unchanged" -ForegroundColor Yellow
}

# [5/6] Start crawl4ai server (local scraping service on port 11235)
Write-Host "`n[5/6] Starting crawl4ai server (port 11235)..." -ForegroundColor Yellow

$crawl4aiRunning = Get-NetTCPConnection -LocalPort 11235 -ErrorAction SilentlyContinue
if (-not $crawl4aiRunning) {
    # crawl4ai 需 Python >=3.10; 本机安装在 miniconda3 GMI 环境(3.11)
    $c4aPython = "E:\Software\miniconda3\envs\GMI\python.exe"
    $c4aServer = Join-Path $PSScriptRoot "crawl4ai-server\crawl4ai_server.py"
    $c4aLog = Join-Path $PSScriptRoot "runtime\crawl4ai-server.log"
    if (Test-Path $c4aPython) {
        New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "runtime") | Out-Null
        Start-Process -FilePath $c4aPython -ArgumentList $c4aServer `
            -RedirectStandardOutput $c4aLog -RedirectStandardError "$c4aLog.err" `
            -WindowStyle Hidden
        Write-Host "  crawl4ai server starting, log: $c4aLog" -ForegroundColor Gray
        Start-Sleep 5
        if (Get-NetTCPConnection -LocalPort 11235 -ErrorAction SilentlyContinue) {
            Write-Host "  crawl4ai ready on port 11235" -ForegroundColor Green
        } else {
            Write-Host "  WARNING: crawl4ai may not be up yet (check log)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  WARNING: crawl4ai python not found: $c4aPython (skip)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  crawl4ai already running" -ForegroundColor Green
}

# [6/6] Install deps & start backend
Write-Host "`n[6/6] Starting backend..." -ForegroundColor Yellow
Push-Location backend

# 后端端口: 统一固定 8200(与 config.py / vite 代理 / docker 映射一致; 已加入 Windows 管理员端口排除)
$env:PORT = if ($env:PORT) { $env:PORT } else { "8200" }

# Check deps
python -c "import fastapi; import sqlalchemy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Installing Python deps..." -ForegroundColor Gray
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet 2>&1 | Out-Null
}

# Kill old backend
$oldPid = (netstat -ano | Select-String ":$env:PORT" | Select-String "LISTENING" | ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -First 1)
if ($oldPid) {
    Write-Host "  Stopping old process on port $env:PORT (PID: $oldPid)..." -ForegroundColor Gray
    Stop-Process -Id $oldPid -Force 2>$null
    Start-Sleep 1
}

# Start backend
Write-Host "  Starting FastAPI on port $env:PORT..." -ForegroundColor Gray
$proc = Start-Process D:\anaconda\python.exe -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","$env:PORT" -PassThru -WindowStyle Minimized
Pop-Location

# Verify
Start-Sleep 5
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Startup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

try {
    $health = Invoke-RestMethod -Uri http://localhost:$env:PORT/api/v1/health -TimeoutSec 5
    Write-Host "  Health:   $($health.status) (v$($health.version))" -ForegroundColor Green
    Write-Host ""
    Write-Host "  API Docs: http://localhost:$env:PORT/docs" -ForegroundColor White
    Write-Host "  Login:    admin / admin123" -ForegroundColor White
    Write-Host ""
    Write-Host "  Quick test:" -ForegroundColor Gray
    Write-Host "    curl -X POST http://localhost:$env:PORT/api/v1/auth/login -H 'Content-Type: application/json' -d '{\`"username\`":\`"admin\`",\`"password\`":\`"admin123\`"}'" -ForegroundColor Gray
} catch {
    Write-Host "  WARNING: Health check failed. Check with: docker logs ssm-mysql --tail 10" -ForegroundColor Yellow
}
