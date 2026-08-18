# 单位机部署任务清单（给那边 Agent 执行）

> 本文件面向**单位机上的协作 Agent**。家里机代码已提交到本地 git（commit `25427a7`，分支 `main`，无远程仓库）。
> 你的目标是：在单位机把 SSM 完整跑起来（Docker: MySQL + Redis + Neo4j + Backend），把家里机的数据库/图谱数据迁过去，再用 Cloudflare Tunnel 让家里机能实时访问。
>
> 单位机环境：Windows + 已装 Docker Desktop + miniconda（Python 3.14 / 3.11 都有）。用 TeamViewer 远程操控。

---

## 铁律（跨机必须一致，已在家里机固定）
| 项 | 值 |
|---|---|
| SECRET_KEY | `eq8jVZrgSzS7-yCsZOp8U0dI0wczyV5gzBP5T1-0otTKPJcIWF61YP8bWCYcP_GT` |
| MySQL 库名 / 用户 / 口令 | `ssm` / `ssm_user` / `ssm_pass` |
| Neo4j 用户 / 口令 | `neo4j` / `ssm_neo4j_2026` |
| 后端对外端口 | `8100`（容器内部 8000，compose 已映射 `8100:8000`） |

> 任何一台机器改了这些值，两边就**无法共享登录态 / 无法解密**，务必原样照抄。

---

## 任务 0：拿到代码（直接 clone GitHub 远程，最快）

家里机代码已推到公开仓库 **`https://github.com/HankVon/GMI.git`**（分支 `main`，commit `ed09195`）。单位机直接 clone 即可，**不用 TeamViewer 拷目录**：

```
git clone https://github.com/HankVon/GMI.git D:\Geology\SSM
cd D:\Geology\SSM
git log --oneline -1    # 应显示 ed09195
```

- 不要单独拷 `.env`、`node_modules`、`frontend/dist`、`runtime` —— 它们已在 `.gitignore` 里，不会进 git，也无需迁移（clone 下来就没有这些，正常）。
- 若 clone 提示认证：用 Git Credential Manager 弹窗登录，或 `git clone https://<你的TOKEN>@github.com/HankVon/GMI.git`（token 需 `repo` 权限）。
- clone 后本地 `main` 已跟踪 `origin/main`，后续直接 `git pull` / `git push` 同步。

> **后续双向同步**：家里机改完 `git push`，单位机 `git pull origin main`；单位机若也改代码，`git commit` 后 `git push origin main`，家里机 `git pull`。统一走这个 GitHub 远程，无需 bare 中转库。

---

## 任务 1：安装 Docker Desktop（若未装）
1. 官网 https://www.docker.com/products/docker-desktop/ 下载 Windows 版安装。
2. 安装后启动，确认：
   ```
   docker --version
   docker compose version
   ```
3. 若 WSL2 后端报内存/虚拟化问题，按 Docker 提示开启 BIOS 虚拟化或重装 WSL。

---

## 任务 2：创建单位机 `backend/.env`
仓库已 gitignore 了 `.env`，所以单位机**必须自己建**。在 `D:\Geology\SSM\backend\.env` 写入：
```
SECRET_KEY=eq8jVZrgSzS7-yCsZOp8U0dI0wczyV5gzBP5T1-0otTKPJcIWF61YP8bWCYcP_GT
NEO4J_PASSWORD=ssm_neo4j_2026
```
> 注意：`docker-compose.yml` 的 backend 服务用 `${SECRET_KEY}` 从**compose 同级目录的 `.env`** 注入。所以还需在 `D:\Geology\SSM\.env`（compose 同级）写一行：
```
SECRET_KEY=eq8jVZrgSzS7-yCsZOp8U0dI0wczyV5gzBP5T1-0otTKPJcIWF61YP8bWCYcP_GT
```
（compose 同级 `.env` 不是 backend 那个，是给 docker compose 用的。两个都要有。）

---

## 任务 3：启动全部服务
```
cd D:\Geology\SSM
docker compose up -d --build
```
- 首次会构建 backend 镜像（读 `backend/Dockerfile`），拉 mysql/redis/neo4j 镜像，可能需几分钟。
- 启动顺序由 `depends_on: condition: service_healthy` 保证：mysql → redis → neo4j → backend。
- 查看状态：`docker compose ps`
- 看后端日志：`docker compose logs -f backend`

### 验证后端起来了
```
curl http://localhost:8100/docs
```
应返回 FastAPI 的 Swagger HTML。后端启动时会**自动跑迁移**（`app/main.py` 调 `run_migrations`，幂等建表补列），**无需手动执行 alembic**。日志里看到 `Application startup complete` 即成功。

> 若报缺表/缺列，多半是迁移 SQL 文件没挂进容器：`docker-compose.yml` 已把 `./sql` 挂到 mysql 的 `/docker-entrypoint-initdb.d`（仅首次建库生效），后续新增列靠 `migrate.py` 自动补。不用手动干预。

---

## 任务 4：数据迁移（家里机 → 单位机，一次性）
家里机已导好两份文件，通过 TeamViewer 传到单位机（建议放 `D:\Geology\SSM\migrate_in\`）。

### 4.1 MySQL
家里机导出（已在家里执行过）：
```
mysqldump -u ssm_user -p ssm > ssm_mysql.sql
```
单位机导入（MySQL 已在容器内，端口 3306 已映射）：
```
mysql -h 127.0.0.1 -u ssm_user -p ssm < ssm_mysql.sql
```
> 若单位机 mysql 容器还没建库，先 `docker compose exec mysql mysql -u root -proot_password -e "CREATE DATABASE ssm CHARACTER SET utf8mb4;"` 再导入。

### 4.2 Neo4j
家里机导出（家里执行）：
```
# 停家里 Neo4j 后
neo4j-admin database dump neo4j --to=/path/neo4j.dump
```
单位机导入（neo4j 容器，端口已映射）：
```
docker compose exec neo4j neo4j-admin database load neo4j --from=/import/neo4j.dump --overwrite-destination
```
> 导入前需把 `neo4j.dump` 放到容器能读的路径（可在 compose 给 neo4j 加个 `- ./migrate_in:/import` 临时卷，或 `docker cp` 进去）。导入后重启 neo4j 容器。

### 4.3 验证数据
- MySQL：`mysql -h 127.0.0.1 -u ssm_user -p ssm -e "SHOW TABLES; SELECT COUNT(*) FROM project;"`
- Neo4j：浏览器开 `http://localhost:7474`，登录 `neo4j/ssm_neo4j_2026`，跑 `MATCH (n) RETURN count(n);`

---

## 任务 5：Cloudflare Tunnel（让家里机访问单位机 8100）
> 免费 Tunnel 只代理 HTTP，**不能代理 MySQL 3306 / Neo4j 7687**。所以家里机只通过后端 REST API 看数据，完全满足"展示一致"。

### 5.1 装 cloudflared（单位机）
- 下载 https://github.com/cloudflare/cloudflared/releases 的 Windows 版，放到 `C:\cloudflared\cloudflared.exe`，并加入 PATH。

### 5.2 临时验证（无域名，先用这个）
单位机开一个常驻命令行：
```
cloudflared tunnel --url http://localhost:8100
```
终端会输出 `https://xxxx.trycloudflare.com`（每次重启变）。**把这个地址发给家里机**。

### 5.3 固化（可选，需一个域名）
1. `cloudflared tunnel login`（需把某个域名托管到 Cloudflare）
2. `cloudflared tunnel create ssm`
3. 写 `C:\cloudflared\config.yml`：
```yaml
tunnel: ssm
credentials-file: C:\Users\<你>\.cloudflared\<id>.json
ingress:
  - hostname: ssm.yourdomain.com
    service: http://localhost:8100
  - service: http_status:404
```
4. 域名 DNS 加 `ssm` 的 CNAME 指向 `<id>.cfargotunnel.com`
5. `cloudflared tunnel run ssm`（或装系统服务常驻）

---

## 任务 6：把 Tunnel 地址回传给家里机
把任务 5.2 / 5.3 拿到的地址（如 `https://xxxx.trycloudflare.com` 或 `https://ssm.yourdomain.com`）告诉家里机主人。
家里机那边会：
- 改 `frontend/vite.config.ts` 的 proxy target 为该地址，或
- `VITE_API_TARGET=https://<地址> npm run dev`
然后访问 `http://localhost:5173` 即实时操作单位机数据。

---

## 任务 7（可选）：代码双向同步
代码已走 GitHub 远程（`origin` = `https://github.com/HankVon/GMI.git`），两边直接同步，无需 bare 中转库：
- 家里机改完：`git add . && git commit -m "..." && git push origin main`
- 单位机拉取：`git pull origin main`
- 单位机若也改代码：`git commit` 后 `git push origin main`，家里机 `git pull origin main`
- 若两边并发改同一文件冲突，先 `git pull` 解决冲突再 `git push`。

---

## 排查速查
| 现象 | 可能原因 | 处理 |
|---|---|---|
| backend 容器起不来 / SECRET_KEY 空 | compose 同级 `.env` 没写 SECRET_KEY | 任务 2 补 `D:\Geology\SSM\.env` |
| 家里机连 Tunnel 报 CORS | backend `CORS_ORIGINS` 不含家里前端地址 | compose backend 环境变量加 `http://localhost:5173` 后 `docker compose up -d backend` |
| 数据为空 | 迁移漏了 MySQL/Neo4j 导入 | 回任务 4 重导 |
| Tunnel 地址变 | 用了临时 tunnel，重启即变 | 用任务 5.3 固化域名 |
| `docker compose up` 报 Dockerfile 找不到 | backend/Dockerfile 没拷过来 | 确认整目录拷贝，含 backend/Dockerfile |

---

## 给 Agent 的执行顺序建议
1. 任务 0（拿代码）→ 2（建 backend/.env + compose .env）→ 1（装 Docker，若未装）→ 3（起服务，验证 /docs）→ 4（迁数据）→ 5（开 Tunnel，回传地址）→ 6（等家里确认连通）。
2. 每完成一步，向家里机主人汇报结果，尤其是 Tunnel 地址和 `/docs` 是否可访问。
3. 不要提交 `.env`、不要改 SECRET_KEY、不要把 `node_modules`/`frontend/dist` 加进 git。
