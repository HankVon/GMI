# 代码修改后如何生效 —— 重启指南

> 单位机部署在 Docker 里。**改了代码 ≠ 自动生效**，需要根据「改的是前端还是后端」执行不同的操作。
> 一句话总则：**改前端 → build 前端；改后端 → 重建+重启后端容器**。

---

## 0. 先认清架构（决定改完怎么生效）

```
浏览器
  │  访问域名 https://sct5dzd.xyz (Cloudflare 隧道 → 单位机)
  ▼
单位机前端容器 ssm-frontend (serve.py, 端口 8080)
  │  · 托管的是静态文件: D:\Geology\GMI\frontend\dist   ← 前端源码 build 出来的产物
  │  · ./frontend 目录是【只读实时挂载】, dist 一变, 容器立即读到
  ▼  /api 反代
单位机后端容器 ssm-backend (uvicorn, 端口 8100)
  │  · 后端代码是【build 进镜像】的, 改 .py 必须重建镜像才进容器
  ▼
MySQL / Redis / Neo4j
```

**关键区别：**
| 部分 | 代码在哪 | 改后怎么生效 |
|---|---|---|
| 前端 `.vue` 源码 | 宿主 `frontend/src`，编译进 `dist` | 只需 `npm run build` 重新生成 `dist` |
| 前端 `serve.py` 托管脚本 | 宿主 `frontend/serve.py` | 需要重启前端容器 |
| 后端 `.py` | **build 进镜像** | 必须重建镜像 + 重启后端容器 |
| 数据库结构 | SQL 脚本 | 另见第 4 节 |

---

## 1. 改前端源码（.vue / .ts）—— 只需 build

前端容器**实时挂载** `./frontend`，所以只要把 `dist` 重新生成，容器立即读到，**不用重启容器**。

```powershell
# 1) 进入前端目录
cd D:\Geology\GMI\frontend

# 2) 用 node 重新构建 dist (node 在 E:\Software\NodeJS, 不在 PATH 里, 需临时加)
$env:Path = "E:\Software\NodeJS;" + $env:Path
npm run build
```

> 看到 `✓ built in xx s` 即成功。
> 若提示缺依赖，先 `npm install` 再 build。

**生效检查：** 浏览器打开页面后 **强制刷新（Ctrl+F5）**，别用普通刷新（可能走缓存看到旧页面）。

---

## 2. 改后端源码（.py）—— 必须重建镜像 + 强制重启容器

后端代码是 **build 进镜像**的，不是挂载源码，所以改 `.py` 后**必须重建镜像并重启容器**。

```powershell
cd D:\Geology\GMI

# 1) 重建后端镜像
docker compose build backend

# 2) 强制重建并重启后端容器 (--force-recreate 确保容器重建加载新代码)
docker compose up -d --force-recreate backend

# 3) 确认健康 (等约 10 秒后应为 healthy)
docker inspect -f "{{.State.Health.Status}}" ssm-backend
```

> ⚠️ 不要只 `docker compose restart backend` —— 容器里的旧镜像/旧代码还在，restart 不会重新加载你改的 `.py`。**必须 build + force-recreate。**

---

## 3. 改前端托管脚本（serve.py）—— 需重启前端容器

`serve.py` 是前端容器**启动时**运行的程序，改它后要重启前端容器才能加载新脚本。

```powershell
cd D:\Geology\GMI
docker compose restart frontend
```

> 改了 `serve.py`（如缓存策略）才需要这步；只改 `.vue` 不用。

---

## 4. 改数据库结构（SQL）—— 需重建 MySQL 容器执行初始化

首次部署用 `./sql` 目录的脚本初始化。**已有数据时改 SQL 不会自动执行**，需手动进容器跑：

```powershell
# 进入 MySQL 容器执行 SQL (库名 ssm, root 密码 root_password)
docker exec -i ssm-mysql mysql -uroot -proot_password ssm < 你的脚本.sql
```

> 只在你改了数据库表结构/初始化数据时需要。

---

## 5. 一键全量生效（省事）

如果你一次改了一堆（前端+后端），直接全部重建：

```powershell
cd D:\Geology\GMI

# 前端 build
$env:Path = "E:\Software\NodeJS;" + $env:Path
cd frontend && npm run build && cd ..

# 后端重建 + 强制重启
docker compose build backend
docker compose up -d --force-recreate backend

# 重启前端容器 (若改了 serve.py; 没改可跳过)
docker compose restart frontend
```

---

## 6. 日常维护常用命令速查

| 操作 | 命令 |
|---|---|
| 看所有容器状态 | `docker compose ps` |
| 看后端日志 | `docker logs --tail 50 ssm-backend` |
| 看前端日志 | `docker logs --tail 50 ssm-frontend` |
| 启动全部服务 | `docker compose up -d` |
| 停掉全部服务 | `docker compose down` |
| 强制重启后端 | `docker compose up -d --force-recreate backend` |
| 后端健康检查 | `docker inspect -f "{{.State.Health.Status}}" ssm-backend` |

---

## 7. 最容易踩的坑

1. **改了后端却只 `restart`，没 `build`** → 容器还是旧代码，改动没生效。
2. **改了前端却不 `npm run build`** → 域名访问的是旧 `dist`，看不到改动。
3. **浏览器看不到新改动** → 先 **Ctrl+F5 强刷**，可能只是缓存。
4. **node 找不到** → 单位机 node 在 `E:\Software\NodeJS`，需先 `$env:Path = "E:\Software\NodeJS;" + $env:Path`。

---

## 8. 家里机（另一台机器）如何同步

家里机只跑前端 dev，不跑容器，通过域名连单位机数据。代码走 git 同步：

```bash
# 家里机
cd <家里机GMI>/frontend
git pull origin main        # 拉最新代码
npm install                 # 首次或依赖变化时
npm run dev                 # 连单位机域名, 实时看数据
```

> 家里机改动想生效到域名，需 **先 `git push`，单位机再 `git pull`**，然后按本文第 1/2 节重新 build / 重建后端。

---

## 9. 结论速记

| 改了 | 操作 | 命令 |
|---|---|---|
| 前端 `.vue` | build | `npm run build` |
| 后端 `.py` | 重建+重启后端 | `docker compose build backend && docker compose up -d --force-recreate backend` |
| `serve.py` | 重启前端 | `docker compose restart frontend` |
| SQL | 手动执行 | `docker exec -i ssm-mysql mysql -uroot -proot_password ssm < 脚本.sql` |
