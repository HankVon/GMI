# GMI 后端（FastAPI）

Python 3.12（Docker `python:3.12-slim`），FastAPI + SQLAlchemy 2.0 + Pydantic，统一 API 前缀 `/api/v1`。

---

## 一、目录结构

```
backend/
├── README.md                 本文件
├── Dockerfile                python:3.12-slim，WORKDIR /app，uvicorn app.main:app
├── requirements.txt          Python 依赖
├── test_public_contracts.py  前台公开接口契约测试
│
├── app/
│   ├── main.py               应用入口：路由注册、中间件装配、启动时 migrate + scheduler
│   ├── config.py             ★ 全部配置项与环境变量（见第三节）
│   ├── database.py           引擎/会话/Base，Neo4j 降级逻辑
│   │
│   ├── api/
│   │   └── v1/               ★ 44 个路由模块，统一前缀 /api/v1（见下表）
│   ├── models/               37 个 SQLAlchemy ORM 模型（1 文件 ≈ 1 张/一组表）
│   ├── services/             53 个业务服务（爬虫、富化、图谱、导入、调度等）
│   ├── schemas/              13 个 Pydantic 出入参模型
│   ├── middleware/           4 个中间件：auth(JWT) / audit(审计) / rate_limit(限流)
│   └── utils/
│       └── upload_paths.py   ★ 附件根目录解析（容器/裸跑双环境统一，见 5.1）
│
├── scripts/                  运维脚本：回填 / 种子 / 抓取 / 数据源侦察 → 见 scripts/README.md
├── uploads/                  ⚠️ 已废弃，附件统一存仓库根 uploads/（见 5.1）
└── logs/                     运行日志（容器内挂载到 /app/logs）
```

### `api/v1/` 44 个路由模块

| 域 | 模块 |
|---|---|
| 项目/商机 | `projects.py`、`opportunities.py`、`project_companies.py`、`project_members.py`、`project_progress.py`、`project_tracker.py`、`project_context.py` |
| 单位 | `companies.py`、`company_detail.py`、`owners.py` |
| 人员/人脉 | `persons.py`、`business_network.py`、`network.py` |
| 招投标 | `bids.py`、`bid_admin.py`、`bid_attachments.py`、`bid_tags.py`、`tenders_search.py` |
| 情报/线索 | `intelligence.py`、`intelligence_admin.py`、`intent.py`、`web_clues.py`、`content.py` |
| 爬取管线 | `pipeline.py`、`web_clues.py` |
| AI/营销 | `ai.py`、`marketing.py`、`combined_query.py` |
| 统计/报表 | `dashboard.py`、`reports.py`、`search.py` |
| 系统 | `rbac.py`、`rbac_admin.py`、`audit.py`、`notifications.py`、`option_sets.py`、`field_meta.py`、`dynamic_crud.py`、`geo.py`、`cms.py`、`excel.py`、`favorites.py`、`knowledge.py`、`public.py` |

---

## 二、启动

### 容器（生产/单位机，推荐）

```powershell
docker compose up -d --build backend
docker compose logs -f backend          # 看到 "Application startup complete"
curl http://localhost:8200/api/v1/health
```

### 本机裸跑（开发）

```powershell
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8200 --reload
```

> 端口统一 **8200**（`config.py` 已固定，与 `start_all.ps1` / Vite 代理 / compose 映射一致）。

---

## 三、环境变量

全部在 `app/config.py` 读取，支持 `.env`（**必须放在仓库根**，与 `docker-compose.yml` 同级）。

| 变量 | 默认值 | 必填 | 说明 |
|---|---|---|---|
| `SECRET_KEY` | 无 | ✅ | JWT 签名密钥，**生产环境缺失或长度 <16 直接启动失败** |
| `DATABASE_URL` | `mysql+pymysql://ssm_user:ssm_pass@localhost:3307/ssm_db` | 容器由 compose 覆盖 | 注意裸跑默认端口 3307，容器是 3306 |
| `REDIS_URL` | `redis://localhost:6379/0` | | 缓存；连续失败会熔断降级 |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | `neo4j://localhost:7687` / `neo4j` / 空 | | **口令缺失不阻断启动**，图谱功能降级 |
| `PORT` | `8200` | | 容器内部为 8000，compose 已覆盖 |
| `DEBUG` | `false` | | 为 true 时自动生成临时 `SECRET_KEY` |
| `CORS_ORIGINS` | `http://localhost:5173` | | 逗号分隔；容器由 compose 覆盖 |
| `CRAWL4AI_API_URL` | `http://127.0.0.1:11235` | ⚠️ | **容器内必须改为 `http://host.docker.internal:11235`**，否则连到容器自身 |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / `qwen-graphrag:latest` | | 容器内走 `host.docker.internal` |
| `QCC_APP_KEY` / `QCC_APP_SECRET` | 空 | | 企查查开放平台，留空则富化降级 |
| `MAX_UPLOAD_MB` | `200` | | 超限返回 413 |
| `NOTIFY_WEBHOOK_URL` | 空 | | 运维告警（企微/钉钉），留空不发送 |
| `RATE_LIMIT_PER_MINUTE` | `300` | | 按 IP 限流 |
| `LOGIN_MAX_FAILURES` / `LOGIN_WINDOW_SECONDS` | `5` / `300` | | 登录防暴力破解 |

---

## 四、数据库迁移：**不用 alembic**

`backend/alembic/` 已废弃。现行两套机制：

1. **首次建库**：`sql/` 挂载进 MySQL 容器的 `/docker-entrypoint-initdb.d`（仅首次生效）。
2. **增量补列/建表**：启动时 `app/services/migrate.py` 自动执行，幂等。
   - 它从 `sql/` 目录按**裸文件名**读取 `_CREATE_TABLE_SQL_FILES` 清单（30 个文件）；
   - MySQL 8 不支持 `ADD COLUMN IF NOT EXISTS`，故先查 `information_schema` 再决定是否添加；
   - 单条 DDL 失败只告警不阻断，结果在 `/api/v1/health` 暴露。

> ⚠️ 因此 **`sql/` 必须保持平铺**，不要建子目录，否则 migrate 会全部 miss 且**不报错**。

新增表的正确姿势：
1. 在 `sql/` 下新增 `xxx_ddl.sql`，全部语句用 `CREATE TABLE IF NOT EXISTS`；
2. 把文件名加进 `migrate.py` 的 `_CREATE_TABLE_SQL_FILES`；
3. 重启 backend 生效。

---

## 五、注意事项

### 5.1 附件目录：唯一真源是仓库根 `uploads/`

- `docker-compose.yml` 把 **根 `uploads/`** 挂载为容器 `/app/uploads`；
- 代码**一律**通过 `app/utils/upload_paths.py` 的 `upload_root()` 取路径，**禁止**再写 `Path(__file__).parent.parent... / "uploads"`：
  - 容器内 backend 位于 `/app/app/...`，裸跑位于 `<repo>/backend/app/...`，**层级不同**，曾经导致后台上传的附件写入容器可写层、重启即丢。
- `intent_attachment.local_path` / `bid_attachment.local_path` 存**相对于 uploads 的相对路径**（如 `intent_attachments/97/xxx.docx`）。
- `backend/uploads/` 为历史遗留，已合并进根 `uploads/`，请勿再使用。

### 5.2 本机 Python 3.14 与 SQLAlchemy 有 ORM 兼容问题

任何 `import app.models` 的脚本在本机直接跑会失败。**数据回填/核验走原生 SQL**：

```python
from sqlalchemy import create_engine, text
engine = create_engine("mysql+pymysql://ssm_user:ssm_pass@localhost:3306/ssm?charset=utf8mb4")
with engine.begin() as c:
    c.execute(text("UPDATE ..."))
```

或直接用容器：`docker exec ssm-mysql mysql -ussm_user -pssm_pass ssm -e "..."`
模板见 `scripts/backfill_intent_fields.py`（**只填空值，绝不覆盖人工策展数据**）。

### 5.3 crawl4ai 是独立进程，不是本地包

后端通过 HTTP 调 `CRAWL4AI_API_URL`，服务由 conda `GMI` 环境（Python 3.11）运行 `crawl4ai-server/crawl4ai_server.py`，监听 11235。仓库内**不保留** crawl4ai 上游源码。

### 5.4 分层约定

`api/v1/` 只做参数校验与鉴权 → 业务写在 `services/` → 数据访问用 `models/` ORM。
跨模块复用的枚举/选项走 `option_sets.py` + `field_meta.py`（动态字段引擎）。
