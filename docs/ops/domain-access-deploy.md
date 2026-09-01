# 固定域名访问部署手册（sct5dzd.xyz）

> 本文档记录单位机（本机 `D:\Geology\GMI`）如何通过 Cloudflare Tunnel + 自定义域名 `sct5dzd.xyz` 对外提供稳定访问，并实现开机自启。
> 家里机仅跑前端、通过本域名访问单位机后端，无需本地数据库。

---

## 架构总览

```
浏览器 ──HTTPS──> sct5dzd.xyz (Cloudflare, Proxied)
                      │
                      │ Cloudflare Tunnel (命名隧道 gmi-tunnel, QUIC/HTTP2)
                      ▼
   单位机 cloudflared 服务 ──http://localhost:8080──> 前端容器 (serve.py)
                                                      │ 同源反代 /api
                                                      ▼
                                                  backend:8000 (容器映射 8100)
                                                      │
                                    ┌─────────────────┼─────────────────┐
                                    ▼                 ▼                 ▼
                                MySQL:3306       Neo4j:7687        Redis:6379
```

- 隧道指向 **前端 8080**（不是后端 8100），因为前端 `serve.py` 已同源反代 `/api` 到 backend，单域名全通。
- 家里机前端 `localhost:5173` 通过 `VITE_API_TARGET=https://sct5dzd.xyz` 连单位机。

---

## 一、前置条件（已完成）

| 项 | 状态 |
|---|---|
| 域名 `sct5dzd.xyz` 托管到 Cloudflare，NS 已切换，状态 Active/Protected | ✅ |
| `gmi-tunnel` 命名隧道已创建（ID `4c5244d5-60b2-4097-9c7f-931812553862`） | ✅ |
| Cloudflare DNS：`sct5dzd.xyz` 与 `www` 的 CNAME 指向隧道，Proxied（橙云） | ✅ |
| `cloudflared.exe` 位于 `C:\cloudflared\cloudflared.exe`，已加入 PATH | ✅ |
| 凭证 `C:\Users\99446\.cloudflared\gmi-tunnel.json` + `cert.pem` | ✅ |
| 后端 bcrypt 锁定 `4.0.1`（修复登录 500，见下文「故障排查」） | ✅ |

### 配置文件
`C:\Users\99446\.cloudflared\config.yml`：
```yaml
tunnel: gmi-tunnel
credentials-file: C:\Users\99446\.cloudflared\gmi-tunnel.json
ingress:
  - hostname: sct5dzd.xyz
    service: http://localhost:8080
  - service: http_status:404
```

---

## 二、开机自启（已完成）

### 1. cloudflared 注册为 Windows 服务
以**管理员 PowerShell** 执行（注意 `--config` 放在 `tunnel` 与 `run` 之间）：
```powershell
sc.exe create cloudflared binPath= "C:\cloudflared\cloudflared.exe tunnel --config C:\Users\99446\.cloudflared\config.yml run gmi-tunnel" DisplayName= "Cloudflare Tunnel" start= auto
```
> 注册为 `LocalSystem` 账户（能读用户目录凭证），无需密码、不会 1069 登录失败。
> 不要用 `cloudflared service install`（会把 tunnel 名当 token 解析，报 base64 错误）。

验证：`sc.exe query cloudflared` 应显示 `STATE: RUNNING`；`Start` 应为 `2`（Automatic）。

### 2. 容器 + 隧道拉起计划任务
`start_unit_machine.ps1` 已配为任务计划程序任务 `GMI_Startup`，**用户登录时**触发：
- 确保 Docker daemon 就绪（必要时启动 Docker Desktop）
- `docker compose up -d` 拉起全部容器
- 确认 cloudflared 服务在跑（已在跑则跳过，避免冲突）

以管理员 PowerShell 创建任务（已执行）：
```powershell
schtasks /Create /TN "GMI_Startup" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File D:\Geology\GMI\start_unit_machine.ps1" /SC ONLOGON /RL HIGHEST /F
```

---

## 三、家里机同步（必须做）

家里机**不跑数据库**，只跑前端通过本域名访问单位机。只需改前端 API 目标地址：

### 方式 A：开发时临时指定（推荐）
家里机前端目录执行：
```powershell
$env:VITE_API_TARGET="https://sct5dzd.xyz"
npm run dev
```
`vite.config.ts` 的 proxy 会读取 `VITE_API_TARGET`，将 `/api` 代理到单位机域名。

### 方式 B：固化到家里机前端 `.env`
在 `frontend/.env`（家里机，gitignore）写：
```
VITE_API_TARGET=https://sct5dzd.xyz
```
之后 `npm run dev` 自动生效。

### CORS 已就绪
单位机 backend `CORS_ORIGINS` 含 `http://localhost:5173`，家里前端不会被跨域拦截。✅

> 注意：本文档之前的 `unit-machine-setup.md` 任务 5.3 写的是「隧道指向 8100、hostname 用 ssm.yourdomain.com」，**已过时**。实际方案为隧道指向 8080、域名 sct5dzd.xyz，以本文档为准。

---

## 四、日常使用

- 访问：`https://sct5dzd.xyz`
- Swagger：`https://sct5dzd.xyz/api/v1/docs`
- 本机后端（仅本机）：`http://localhost:8100/docs`

开机登录后系统自动就绪，无需手动操作。

---

## 五、故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 登录报 HTTP 500，后端日志 `ValueError: password cannot be longer than 72 bytes` | bcrypt>=5 与 passlib 1.7.4 自检不兼容 | 容器内 `pip install "bcrypt==4.0.1"`；持久化靠 `backend/requirements.txt` 已锁 `bcrypt==4.0.1`，重建镜像 `docker compose build backend` |
| 域名打不开 / 502 | 8080 前端容器没起 | `docker ps` 确认 `ssm-frontend` Up；`docker compose up -d` |
| 隧道连不上 | cloudflared 服务没跑 | `sc.exe query cloudflared`；`sc.exe start cloudflared` |
| `sc.exe create` 报 Access is denied | 非管理员终端 | 用管理员 PowerShell 重跑 |
| `sc.exe start` 报 1069 登录失败 | 服务用了普通用户+密码错误/无服务登录权限 | 改用 LocalSystem（不带 `obj=/password/`），见第二节 |
| `service install` 报 token base64 错误 | `service install <name>` 把隧道名当 token | 改用 `sc.exe create`（本文档方式） |
| region2 QUIC UDP 失败 | 防火墙挡 UDP 7844 | 自动降级 HTTP2，不影响使用；可在路由器放行 UDP 7844 |
| 家里前端连不上 | `VITE_API_TARGET` 未设或仍是旧地址 | 按第三节设为 `https://sct5dzd.xyz` |

---

## 六、重建/迁移备忘

若重装系统或换机器，按序执行：
1. 装 Docker Desktop，设登录自启。
2. clone 代码，建 `backend/.env` 与 compose 同级 `.env`（SECRET_KEY 等，见 `unit-machine-setup.md` 铁律）。
3. `docker compose up -d`。
4. 装 cloudflared 到 `C:\cloudflared`，`cloudflared login`（选 sct5dzd.xyz），`cloudflared tunnel create gmi-tunnel`，`route dns` 建 CNAME。
5. 写 `config.yml`，`sc.exe create` 注册服务。
6. 建 `GMI_Startup` 计划任务。
