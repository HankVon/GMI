# SSM 项目基石数据平台 — 一键启动指南

> **已验证环境**: Windows 10/11 + Docker Desktop + Anaconda Python 3.9  
> **验证日期**: 2026-07-31  
> **MySQL端口**: 3307（因本机3306被占用）  
> **后端端口**: 8000  
> **Redis端口**: 6379  

---

## 启动步骤（按顺序，每步一票通）

### Step 1: 配置环境变量

编辑 `backend\.env`，确认端口为 3307：

```
DATABASE_URL=mysql+pymysql://ssm_user:ssm_pass@localhost:3307/ssm_db?charset=utf8mb4
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=ssm-platform-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480
APP_NAME=SSM平台
APP_VERSION=1.0.0
DEBUG=true
CORS_ORIGINS=http://localhost:5173
CACHE_FIELD_META_TTL=3600
CACHE_OPTION_SET_TTL=7200
CACHE_USER_PERM_TTL=1800
```

### Step 2: 启动 MySQL + Redis

```powershell
# 如果容器已存在但未启动
docker start ssm-mysql 2>$null
docker start ssm-redis 2>$null

# 如果容器不存在 → 首次创建
docker rm -f ssm-mysql ssm-redis 2>$null

docker run -d --name ssm-mysql `
  -e MYSQL_ROOT_PASSWORD=root_password `
  -e MYSQL_DATABASE=ssm_db `
  -e MYSQL_USER=ssm_user `
  -e MYSQL_PASSWORD=ssm_pass `
  -p 3307:3306 `
  mysql:8.0 `
  --character-set-server=utf8mb4 `
  --collation-server=utf8mb4_unicode_ci `
  --default-authentication-plugin=mysql_native_password

docker run -d --name ssm-redis `
  -p 6379:6379 `
  redis:7-alpine
```

### Step 3: 导入数据库 DDL

```powershell
# 等待 MySQL 就绪
do {
  Start-Sleep 2
  $ready = docker exec ssm-mysql mysqladmin ping -ussm_user -pssm_pass --silent 2>$null
} until ($ready)

# 导入 DDL（必须用 cmd /c，不能用 PowerShell Get-Content 管道）
cmd /c "docker exec -i ssm-mysql mysql -ussm_user -pssm_pass --default-character-set=utf8mb4 ssm_db < sql\init_ddl.sql"

# 更新管理员密码（bcrypt hash 在 DDL 中为占位值，需替换）
cd backend
python -c "from passlib.context import CryptContext; h=CryptContext(schemes=['bcrypt']).hash('admin123'); print(h)" > $env:TEMP\hash.txt
$hash = (Get-Content $env:TEMP\hash.txt).Trim()
cd ..
docker exec ssm-mysql mysql -ussm_user -pssm_pass ssm_db -e "UPDATE sys_user SET password_hash='$hash' WHERE username='admin';"
```

### Step 4: 安装 Python 依赖 + 启动后端

```powershell
cd backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> 后端启动后访问:
> - **API 文档**: http://localhost:8000/docs
> - **健康检查**: http://localhost:8000/api/v1/health

### Step 5: 验证

```powershell
# 健康检查
Invoke-RestMethod http://localhost:8000/api/v1/health

# 登录测试
$body = '{"username":"admin","password":"admin123"}'
$token = Invoke-RestMethod -Uri http://localhost:8000/api/v1/auth/login -Method POST -ContentType "application/json" -Body $body
$token.user.roles  # → [admin]

# 项目列表（带 JWT）
$headers = @{Authorization="Bearer $($token.access_token)"}
Invoke-RestMethod http://localhost:8000/api/v1/projects -Headers $headers

# 字段元数据
Invoke-RestMethod http://localhost:8000/api/v1/field-metadata?entity_type=project -Headers $headers
```

---

## 一键脚本（powershell）

将以下内容保存为 `start_all.ps1`:

```powershell
# SSM 一键启动脚本
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== Step 1: Start MySQL & Redis ===" -ForegroundColor Cyan
docker start ssm-mysql 2>$null
if ($LASTEXITCODE -ne 0) {
    docker rm -f ssm-mysql 2>$null
    docker run -d --name ssm-mysql `
      -e MYSQL_ROOT_PASSWORD=root_password `
      -e MYSQL_DATABASE=ssm_db `
      -e MYSQL_USER=ssm_user `
      -e MYSQL_PASSWORD=ssm_pass `
      -p 3307:3306 `
      mysql:8.0 `
      --character-set-server=utf8mb4 `
      --collation-server=utf8mb4_unicode_ci `
      --default-authentication-plugin=mysql_native_password
}

docker start ssm-redis 2>$null
if ($LASTEXITCODE -ne 0) {
    docker run -d --name ssm-redis -p 6379:6379 redis:7-alpine
}

Write-Host "=== Step 2: Wait for MySQL ready ===" -ForegroundColor Cyan
do { Start-Sleep 2; $ready = docker exec ssm-mysql mysqladmin ping -ussm_user -pssm_pass --silent 2>$null } until ($ready)
Write-Host "MySQL is ready!" -ForegroundColor Green

Write-Host "=== Step 3: Import DDL ===" -ForegroundColor Cyan
cmd /c "docker exec -i ssm-mysql mysql -ussm_user -pssm_pass --default-character-set=utf8mb4 ssm_db < sql\init_ddl.sql"

Write-Host "=== Step 4: Fix admin password ===" -ForegroundColor Cyan
Set-Location backend
$hash = python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('admin123'))"
Set-Location ..
docker exec ssm-mysql mysql -ussm_user -pssm_pass ssm_db -e "UPDATE sys_user SET password_hash='$($hash.Trim())' WHERE username='admin';"

Write-Host "=== Step 5: Install deps & start backend ===" -ForegroundColor Cyan
Set-Location backend
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
Start-Process python -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--reload"

Start-Sleep 3
Write-Host "=== Backend started! ===" -ForegroundColor Green
Write-Host "API Docs: http://localhost:8000/docs"
Write-Host "Health:    http://localhost:8000/api/v1/health"
Write-Host "Login:     admin / admin123"
```

运行方式：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\start_all.ps1
```

---

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 端口 3306 被占用 | 本机已有 MySQL | 已改用 3307，确认 `.env` 一致 |
| 端口 8000 被占用 | 已有旧后端进程 | `netstat -ano \| findstr :8000` 找到 PID 后 `taskkill` |
| DDL 导入报语法错误 | PowerShell 管道编码问题 | **必须用** `cmd /c "docker exec -i ... < file"` |
| 登录提示密码错误 | DDL 种子hash是占位值 | 执行 Step 4 更新 bcrypt hash |
| import 错误 (Python 3.9) | `X \| Y` 语法需 Python 3.10+ | 已全部改为 `Optional[X]` 兼容 3.9 |
| Redis 连接失败 | Redis 未启动或端口冲突 | `docker start ssm-redis` |
