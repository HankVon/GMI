# SSM 远程协作部署手册（家里机 ↔ 单位机 实时数据）

## 目标
- 数据库/图谱**只跑在单位机**（Docker: MySQL + Neo4j + Redis + Backend）。
- 家里机**不本地跑数据库**，通过 Cloudflare Tunnel 访问单位机后端，实时看到同一份数据。
- 代码用 git 双向同步（单位机建 bare 中转库）。

## 跨机必须一致的项（已写入本机 backend/.env，单位机也要填一样）
| 项 | 值 |
|---|---|
| SECRET_KEY | `eq8jVZrgSzS7-yCsZOp8U0dI0wczyV5gzBP5T1-0otTKPJcIWF61YP8bWCYcP_GT` |
| Neo4j 用户/口令 | `neo4j` / `ssm_neo4j_2026` |
| MySQL 库名/用户/口令 | `ssm` / `ssm_user` / `ssm_pass` |

---

## 一、单位机：首次部署（TeamViewer 远程操作）

### 1. 同步代码到单位机
本机已 `git init`。首次用 TeamViewer 把 `D:\Geology\SSM` 整目录拷到单位机同路径（排除 node_modules/.codebuddy/runtime，或用 .gitignore 后 git 传）。

### 2. 安装 Docker Desktop（单位机）
官网下载安装，启动后确认 `docker --version`、`docker compose version` 可用。

### 3. 创建单位机 backend/.env
在 `backend/.env` 写入（与家里一致）：
```
SECRET_KEY=eq8jVZrgSzS7-yCsZOp8U0dI0wczyV5gzBP5T1-0otTKPJcIWF61YP8bWCYcP_GT
NEO4J_PASSWORD=ssm_neo4j_2026
# 其余 DATABASE_URL 等由 docker-compose backend 服务环境变量覆盖, 可不写
```

### 4. 启动服务
```
cd D:\Geology\SSM
docker compose up -d
```
起：mysql(3306) redis(6379) neo4j(7474/7687) backend(8100)。
查看：`docker compose ps` / `docker compose logs -f backend`。

### 5. 初始化数据库表 + 迁移
SSM 用 Alembic 迁移（见 backend 的 migrate 脚本）。首次：
```
docker compose exec backend python -m alembic upgrade head
# 若有自定义 migrate 脚本(sql/_ADD_COLUMNS 等), 按 backend 文档执行
```
> 具体迁移命令以 backend 实际为准，启动后若接口报缺表再补。

---

## 二、Cloudflare Tunnel（让家里访问单位机 8100）

> 免费 Tunnel 仅代理 HTTP/HTTPS，**不能直连 MySQL 3306/Neo4j 7687**。
> 因此家里机**只通过后端 REST API（8100）**访问数据，不直连数据库。完全满足「展示一致」。

### 方案 A：临时验证（无需域名）
单位机安装 cloudflared 后：
```
cloudflared tunnel --url http://localhost:8100
```
终端会输出 `https://xxxx.trycloudflare.com` 临时地址（每次重启变）。记下它给家里机用。

### 方案 B：固化（需一个托管到 Cloudflare 的域名，如 yourdomain.com）
1. 单位机安装 cloudflared，登录：`cloudflared tunnel login`
2. 建隧道：`cloudflared tunnel create ssm`
3. 写配置 `C:\cloudflared\config.yml`：
```yaml
tunnel: ssm
credentials-file: C:\Users\<你>\.cloudflared\<id>.json
ingress:
  - hostname: ssm.yourdomain.com
    service: http://localhost:8100
  - service: http_status:404
```
4. 域名 DNS 加 `ssm` 的 CNAME 指向 `<id>.cfargotunnel.com`（cloudflared 可自动加）。
5. 以服务运行：`cloudflared tunnel run ssm`（或 `cloudflared service install` 装系统服务）。

> 没有域名前用方案 A 验证；买了域名再切 B。

---

## 三、家里机：连接单位机实时数据

### 前端连 Tunnel（推荐，家里只跑前端）
编辑 `frontend/vite.config.ts`，把 proxy target 改为 Tunnel 地址：
```ts
"/api": {
  target: "https://<你的tunnel地址>",  // 如 https://ssm.yourdomain.com 或 https://xxxx.trycloudflare.com
  changeOrigin: true,
  // ...其余不变
}
```
然后 `npm run dev`，访问 `http://localhost:5173` 即实时操作单位机数据。

### 后端开发（可选）
家里机改后端逻辑时，可临时连单位机 Tunnel？不行（TCP 被挡）。
→ 后端开发用**本地临时 MySQL/Neo4j** 测逻辑，测好 push 到单位机重启验证真数据。

---

## 四、代码双向同步（git）

单位机建 bare 中转库（远程登单位机）：
```
cd D:\Geology\SSM
git clone --bare . D:\Geology\SSM_mirror.git
```
家里机和单位机都：
```
git remote add origin <对方能访问的 bare 路径>
git push origin main      # 首次家里推代码到单位机裸库
git pull origin main      # 拉对方改动
```
由于两台不直连，首次把家里代码送进单位机裸库，需用 TeamViewer 在单位机直接 clone 家里副本（或打包传过去再 `git clone --bare`）。之后两边互相 push/pull 同一 origin。

---

## 五、数据迁移（本机 → 单位机，一次性）
```
# 本机导出 MySQL
mysqldump -u ssm_user -p ssm > ssm_mysql.sql
# 本机 Neo4j: 停服后 neo4j-admin database dump neo4j --to=/path/neo4j.dump
# TeamViewer 传 ssm_mysql.sql + neo4j.dump 到单位机
# 单位机导入 MySQL
mysql -u ssm_user -p ssm < ssm_mysql.sql
# 单位机 Neo4j 导入
docker compose exec neo4j neo4j-admin database load neo4j --from=/import/neo4j.dump --overwrite-destination
```

---

## 六、注意事项
- 家里机 `backend/.env` 的 SECRET_KEY / NEO4J_PASSWORD 必须与单位机一致（已统一）。
- 家里机不要本地起 MySQL/Neo4j（除非仅本地测后端），避免端口/数据混乱。
- `.env`、`node_modules`、`.codebuddy`、`runtime`、`frontend/dist` 已加入 `.gitignore`，不会进 git。
- Cloudflare 免费 Tunnel 仅 HTTP，家里无法直连单位机数据库，只能通过后端 API。
