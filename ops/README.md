# 运维脚本

本机（Windows）启停、自检、隧道相关脚本的集中地。

> **为什么根目录还留着几个脚本？**
> `start_all.ps1`、`start_unit_machine.ps1/.bat`、`setup-tunnel.ps1`、`cloudflared-run.bat`、`cloudflared-task.xml`
> 这 6 个**故意留在仓库根**，因为它们绑定了系统状态，移动会直接失效（详见第三节）。
> 本目录只收**无外部绑定**的脚本。

---

## 一、本目录文件

| 文件 | 用途 | 运行 |
|---|---|---|
| `verify.ps1` | 域名连通性自检：请求 `https://sct5dzd.xyz/`，输出 HTTP 状态码与响应长度。用于确认隧道 + 前端是否正常对外 | `pwsh ops\verify.ps1` |
| `services_run_enrich.py` | 单位信息全量深度补全（阻塞式）。筛选 `CO-PIP%` 编码中待补全的单位，逐个调 `enrich_company_free` 补齐字段，并标记 `_enrich_tried` 防重复 | **容器内执行**：`docker exec -d ssm-backend python /sql/../...` 或拷入容器后 `python services_run_enrich.py`。脚本内有 `sys.path.insert(0, "/app")`，**只能容器内跑** |

---

## 二、根目录保留的脚本（速查）

| 文件 | 用途 | 为什么不能移 |
|---|---|---|
| `start_all.ps1` | ★ **主力开发启动脚本**：拉起 mysql/redis → 初始化 DDL → 重置 admin 密码 → 启动 crawl4ai → 安装依赖并启动后端 | 第 4 行 `Set-Location $PSScriptRoot`，后续用相对路径 `backend`、`sql\001_init_ddl.sql`。移到 `ops/` 后 `$PSScriptRoot` 变成 `...\ops`，这些路径全部失效 |
| `start_unit_machine.ps1` / `.bat` | 单位机开机启动：拉起 compose、确认 cloudflared 服务、写 `tunnel_url.txt` | 被 **Windows 任务计划 `GMI_Startup`** 以绝对路径 `D:\Geology\GMI\start_unit_machine.ps1` 引用；`.bat` 里也是硬编码绝对路径 |
| `setup-tunnel.ps1` / `cloudflared-run.bat` / `cloudflared-task.xml` | Cloudflare Tunnel 安装与自启（域名 `sct5dzd.xyz`） | `cloudflared-task.xml` 里写死 `D:\Geology\GMI\cloudflared-run.bat`，由 **任务计划 `CloudflaredTunnel`** 加载；`setup-tunnel.ps1` 又依赖同目录的 XML |

---

## 三、如果想把它们也移进来（迁移步骤）

### `start_all.ps1`

改 4 处即可：

```powershell
$RepoRoot = Split-Path $PSScriptRoot -Parent    # 新增：仓库根
Set-Location $RepoRoot                          # 原: Set-Location $PSScriptRoot
Join-Path $RepoRoot "crawl4ai-server\crawl4ai_server.py"   # 原: Join-Path $PSScriptRoot ...
Join-Path $RepoRoot "runtime\crawl4ai-server.log"          # 原: Join-Path $PSScriptRoot ...
```

改完务必实跑一次验证。

### `start_unit_machine.ps1`（需管理员 PowerShell）

```powershell
Move-Item D:\Geology\GMI\start_unit_machine.ps1 D:\Geology\GMI\ops\start_unit_machine.ps1
Move-Item D:\Geology\GMI\start_unit_machine.bat D:\Geology\GMI\ops\start_unit_machine.bat
# 先备份现有任务定义
schtasks /Query /TN GMI_Startup /XML > D:\Geology\GMI\ops\GMI_Startup.backup.xml
# 重新注册（注意改 .bat 内部的绝对路径）
schtasks /Create /TN "GMI_Startup" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\Geology\GMI\ops\start_unit_machine.ps1" /SC ONLOGON /RL HIGHEST /F
```

### 隧道三件套（需管理员 PowerShell）

```powershell
New-Item -ItemType Directory -Force -Path D:\Geology\GMI\ops\tunnel | Out-Null
Move-Item setup-tunnel.ps1, cloudflared-run.bat, cloudflared-task.xml D:\Geology\GMI\ops\tunnel\
# 编辑 cloudflared-task.xml，把 <Command> 改为 D:\Geology\GMI\ops\tunnel\cloudflared-run.bat
schtasks /Create /TN "CloudflaredTunnel" /XML "D:\Geology\GMI\ops\tunnel\cloudflared-task.xml" /F
```

> ⚠️ 隧道是**对外域名的生产链路**，迁移前确认能重注册成功，否则崩溃后不会自动拉起。

---

## 四、相关但不在本目录

| 文件 | 用途 |
|---|---|
| `scripts/backup.ps1` | 每日 02:30 全量备份（MySQL dump + uploads + Redis RDB + Neo4j），产物在 `runtime/backups/<时间戳>/`，保留策略 `$KEEP_DAYS` |
| `crawl4ai-server/start_crawl4ai_server.ps1` | 启动 crawl4ai 服务（conda `GMI` 环境，11235 端口），自带端口占用检测 |
| `runtime/check_health.ps1` / `runtime/restart8200.ps1` | 后端健康检查与重启（运行时脚本，在 gitignore 的 `runtime/` 下） |

---

## 五、日常运维速查

```powershell
docker compose ps                       # 5 个容器状态
docker compose logs -f backend          # 后端日志
curl http://localhost:8200/api/v1/health
docker exec ssm-mysql mysql -ussm_user -pssm_pass ssm -e "SELECT COUNT(*) FROM ..."
pwsh ops\verify.ps1                     # 对外域名是否可访问
sc.exe query cloudflared                # 隧道服务状态
schtasks /Query /TN GMI_Startup         # 开机自启任务
```
