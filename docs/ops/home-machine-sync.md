# 家里机同步步骤（连接单位机 sct5dzd.xyz）

> 家里机**不跑数据库/后端**，只跑前端，通过单位机固定域名 `https://sct5dzd.xyz` 实时访问单位机数据。
> 详细部署背景见 `docs/domain-access-deploy.md` 与 `docs/unit-machine-setup.md`。

---

## 家里机前置（一次性）

1. 装 Node（与项目 `package.json` 匹配的版本），能跑 `npm run dev`。
2. clone 代码：`git clone https://github.com/HankVon/GMI.git`（或 `git pull origin main` 拉最新）。
3. `cd frontend && npm install`。

> 跨机铁律（已在单位机固定，家里机不得改）：SECRET_KEY / MySQL / Neo4j 凭据见 `unit-machine-setup.md`。
> 家里机**不要本地起 MySQL/Neo4j/Redis/backend**，所有数据走单位机后端 API。

---

## 连单位机域名（核心一步）

### 方式 A：固化到前端 .env（推荐）
复制示例并修改：
```powershell
cd frontend
copy .env.example .env
```
编辑 `frontend/.env`，确认含：
```
VITE_API_TARGET=https://sct5dzd.xyz
```
然后正常启动：
```powershell
npm run dev
```
访问 `http://localhost:5173` 即实时操作单位机数据。

### 方式 B：临时环境变量
不写文件，每次 dev 前设：
```powershell
$env:VITE_API_TARGET="https://sct5dzd.xyz"
npm run dev
```

`vite.config.ts` 的 `/api` 代理会读取 `VITE_API_TARGET`，将请求转发到单位机域名。
（不设则该变量默认为 `http://localhost:8100`，用于单位机本地开发。）

---

## 验证连通

1. 浏览器开 `http://localhost:5173`，登录。
2. 登录走的是 `https://sct5dzd.xyz/api/v1/...`，应能看到单位机同一份数据。
3. 若登录失败 / 网络错误：
   - 确认单位机 `sct5dzd.xyz` 可访问（你自己浏览器开 `https://sct5dzd.xyz` 试）。
   - 确认 `VITE_API_TARGET` 拼写无误（含 `https://`）。
   - 单位机 backend `CORS_ORIGINS` 已含 `http://localhost:5173`，正常情况下不会跨域报错。

---

## 代码同步

代码走 GitHub 远程，两边直接同步：
- 家里机改完：`git add . && git commit -m "..." && git push origin main`
- 单位机拉取：`git pull origin main`（单位机有 `GMI_Startup` 计划任务，登录时自动 `docker compose up -d`；若只改前端则无需重启容器）

> ⚠️ 不要提交 `.env`、`node_modules`、`frontend/dist`、`backend/.env` 等到 git。

---

## 家里机不需要做的事

- ❌ 不装 cloudflared、不建隧道（隧道是单位机的）。
- ❌ 不跑 MySQL / Neo4j / Redis / backend 容器。
- ❌ 不改 SECRET_KEY 等跨机一致项。
- ❌ 不需要域名 / Cloudflare 配置。
