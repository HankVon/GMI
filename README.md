# GMI 地质情报数据平台

> 统一社会信用代码商情数据中台：汇聚**招投标 / 单位画像 / 人脉网络 / AI 情报分析**，把分散的公开数据转化为可决策的情报资产。
> 代码内沿用旧工程名 **SSM**（`APP_NAME=SSM平台`、包名 `ssm-frontend`），对外品牌为 **GMI**。

---

## 一、技术栈

| 层 | 技术 | 端口 |
|---|---|---|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + ECharts + Pinia | dev `5173` / 容器 `8080` |
| 后端 | FastAPI + SQLAlchemy 2.0 + Pydantic，Uvicorn | 容器 `8200`（容器内 `8000`） |
| 数据库 | MySQL 8.0（库名 `ssm`） | `3306` |
| 缓存 | Redis 7 | `6379` |
| 图数据库 | Neo4j 2026.05（人脉/中标网络/区域图谱，可降级） | `7474` / `7687` |
| 爬虫 | crawl4ai 0.9.2 独立 HTTP 服务（conda `GMI` 环境，Python 3.11） | `11235` |
| AI | 本地 Ollama（`qwen-graphrag`）+ 企查查开放平台 | `11434` |
| 部署 | Docker Compose（5 容器）+ Cloudflare Tunnel 对外域名 | — |

---

## 二、快速启动

### 方式 A：Docker Compose（单位机 / 生产，推荐）

```powershell
# 1) 仓库根必须有 .env（至少一行 SECRET_KEY，缺失则 backend 启动即失败）
#    SECRET_KEY=<48位随机串>

# 2) 构建并启动
docker compose up -d --build
docker compose ps          # 5 个容器，backend 应为 healthy

# 3) 验证
curl http://localhost:8200/api/v1/health
```

- 前端访问 `http://localhost:8080`，API 由 `frontend/serve.py` 反代到 backend，同源无 CORS。
- **前端必须先构建**：`cd frontend && npm run build`，产物 `frontend/dist`（容器直接托管该目录）。

### 方式 B：本机裸跑（开发）

```powershell
.\ops\start_all.ps1        # 一键拉起前后端（详见 ops/README.md）
```

裸跑时后端固定 `8200`，前端 `5173`，Vite 已配 `/api` 代理。

> ⚠️ **两条铁律**
> 1. `docker-compose.yml` 必须与 `.env` 同级（后端 `SECRET_KEY: ${SECRET_KEY}` 依赖此约定）。
> 2. 容器内 `CRAWL4AI_API_URL` / `OLLAMA_BASE_URL` 必须指向 `host.docker.internal`（compose 已配 `extra_hosts`），写成 `127.0.0.1` 会连到容器自身。

---

## 三、目录结构（每项一句话）

```
GMI/
├── README.md                 本文件：项目总入口与目录索引
├── docker-compose.yml        ★ 容器编排（mysql/redis/neo4j/backend/frontend 五服务）
├── .env                      ★ 密钥与环境变量（gitignore，各机不同，缺失 backend 起不来）
├── .gitignore
├── cspell.config.json        拼写检查配置（VSCode cSpell）
├── pyrightconfig.json        Python 静态检查配置
│
├── backend/                  ★ FastAPI 后端 → 见 backend/README.md
├── frontend/                 ★ Vue3 前端   → 见 frontend/README.md
├── docs/                     ★ 全部文档     → 见 docs/README.md（含分类索引）
├── sql/                      ★ 建表/迁移/种子 SQL → 见 sql/README.md
│
├── ops/                      本机运维脚本（启停、隧道、自检）→ 见 ops/README.md
├── scripts/                  备份脚本（backup.ps1，每日 02:30 任务计划）
├── samples/                  导入样例 Excel 与样例生成脚本 → 见 samples/README.md
│
├── crawl4ai-server/          自研 crawl4ai 精简 HTTP 服务（11235），独立 conda 环境运行
├── uploads/                  ★ 附件存储唯一目录（容器挂载为 /app/uploads）→ 见 5.1
├── runtime/                  运行时数据：backups/（每日全量备份）+ logs/（gitignore）
├── migrate_in/               一次性数据迁移 dump（gitignore）
└── .nodejs/                  随仓库携带的 Node 24 运行时（可选，用于免安装部署）
```

---

## 四、核心业务域

| 域 | 后端入口 | 前端页面 |
|---|---|---|
| 项目/商机 | `projects.py` / `opportunities.py` | `views/workspace/ProjectList.vue`、`OpportunityList.vue` |
| 单位（公司） | `companies.py` / `company_detail.py` | `CompanyList.vue`、`CompanyDetail.vue` |
| 人员与人脉 | `persons.py` / `business_network.py` | `PersonList.vue`、`PersonProfile.vue`、`NetworkPath.vue` |
| 招投标 | `bids.py` / `bid_admin.py` / `tenders_search.py` | `BidCenter.vue`、`BidManagement.vue`、`BidAdmin.vue` |
| 情报（意图/商机线索） | `intelligence.py` / `intelligence_admin.py` / `intent.py` | `IntelligenceHub.vue`、`IntentAdmin.vue` |
| 线索与爬取 | `web_clues.py` / `pipeline.py` | `WebClue.vue`、`DataPipeline.vue` |
| AI 分析 | `ai.py` / `marketing.py` | `AiAnalystChat.vue`、`Marketing.vue` |
| 报表 | `reports.py` / `dashboard.py` | `ReportsCenter.vue`、`StatisticsHub.vue` |
| 权限 | `rbac.py` / `rbac_admin.py` | `views/admin/RbacManager.vue` |

后端共 44 个路由模块（`backend/app/api/v1/`），统一前缀 `/api/v1`。

---

## 五、必须知道的几个坑

### 5.1 附件目录只有 `uploads/`（根），且是唯一真源

- `docker-compose.yml` 把 **根 `uploads/`** 挂载为容器 `/app/uploads`；
- 历史上 `backend/uploads/` 也存在过（宿主机裸跑爬虫写入），**已合并进根 `uploads/`**，请勿再使用；
- 代码统一通过 `backend/app/utils/upload_paths.py` 的 `upload_root()` 解析，不再用 `Path(__file__).parent.parent...` 的层级魔法（容器与裸跑层级不同，曾经因此丢文件）；
- 数据库 `intent_attachment.local_path` / `bid_attachment.local_path` 存的是**相对于 uploads 的相对路径**（如 `intent_attachments/97/xxx.docx`），迁移目录时无需改库。

### 5.2 数据库迁移不用 alembic

`backend/alembic/` 已废弃。现行方式：
- 首次建库：`sql/` 挂载进 MySQL 的 `/docker-entrypoint-initdb.d`；
- 新增列/表：启动时 `backend/app/services/migrate.py` 幂等补齐（读 `sql/` 下**裸文件名**清单 `_CREATE_TABLE_SQL_FILES`）。

> 因此 **`sql/` 目录必须保持平铺**，不要建子目录，否则 migrate 会全部 miss（且不报错，静默失效）。

### 5.3 `sql/` 路径解析在两套环境下都正确，别改

`migrate.py` 用 4 级 `parent`：容器内解析为 `/sql`（挂载点 `./sql:/sql:ro`），裸跑解析为仓库根 `sql/`，两边都对。

### 5.4 本机 Python 3.14 与 SQLAlchemy 有兼容问题

任何 `import app.models` 的脚本在本机会失败。**数据回填/核验一律走原生 SQL**（`create_engine` + `text()`），模板见 `backend/scripts/backfill_intent_fields.py`；或直接 `docker exec ssm-mysql mysql ...`。

### 5.5 crawl4ai 是独立进程，不是 Python 包调用

后端（Python 3.12 容器）通过 HTTP 调 `http://host.docker.internal:11235`，该服务由 conda `GMI` 环境（Python 3.11）运行 `crawl4ai-server/crawl4ai_server.py`。**仓库内不再保留 crawl4ai 上游源码副本**（需要时从 git 历史取回）。

---

## 六、文档入口

- **全部文档索引**：[`docs/README.md`](docs/README.md)
- 架构总览：[`docs/architecture.md`](docs/architecture.md)
- 启动/运维：[`docs/ops/`](docs/ops/)（部署、备份恢复、单位机、域名隧道）
- 设计文档：[`docs/design/`](docs/design/)
- 使用指南：[`docs/guides/`](docs/guides/)

## 七、备份与恢复

- `scripts/backup.ps1` 每日 02:30 由任务计划触发，产物在 `runtime/backups/<yyyyMMdd_HHmmss>/`（MySQL 全量 dump + uploads 副本 + Redis RDB + Neo4j）。
- 保留策略 `$KEEP_DAYS`，超出自动清理（每份约 170 MB）。
- 恢复步骤见 [`docs/ops/backup-restore.md`](docs/ops/backup-restore.md)。
