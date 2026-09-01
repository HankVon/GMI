# SSM 项目基石数据平台 — 启动与部署指南

> **当前部署方式**: Docker Compose（MySQL / Redis / Neo4j / backend / frontend 五容器）
> **版本**: 2026-08 更新（原裸跑 + 3307 端口方式已废弃，见文末说明）

---

## 一、Docker Compose 一键部署（推荐）

### 前置条件
- Windows + Docker Desktop
- `docker-compose.yml` 已配置（库名 `ssm`、端口 `3306/6379/7474/7687/8100/8080`）
- 根目录 `.env` 提供 `SECRET_KEY`（生产环境必须 ≥16 位）

### 启动
```powershell
cd d:\Geology\GMI
docker compose up -d --build    # 首次构建后端镜像 + 启动全部服务
```

### 服务与端口
| 服务 | 容器名 | 端口 | 说明 |
|---|---|---|---|
| MySQL | ssm-mysql | 3306 | 业务库 `ssm`，首次启动自动执行 `sql/*.sql` 初始化 |
| Redis | ssm-redis | 6379 | 缓存/限流 |
| Neo4j | ssm-neo4j | 7474/7687 | 知识图谱 |
| 后端 | ssm-backend | 8100→8000 | FastAPI，代码 build 进镜像 |
| 前端 | ssm-frontend | 8080→80 | 托管 `frontend/dist`（挂载） |

### 访问
- 前端：http://localhost:8080
- API 文档：http://localhost:8100/docs
- 健康检查：http://localhost:8100/api/v1/health（返回 mysql/redis/neo4j 依赖状态）

### 常用操作
```powershell
docker compose ps                  # 查看状态
docker compose logs -f backend     # 后端日志
docker compose restart backend     # 重启后端(代码未改时)
docker compose up -d backend       # 代码变更后重建容器
docker compose stop                # 停止全部
docker compose down                # 停止并移除(保留数据卷)
```

---

## 二、代码发布流程

### 后端（代码打进镜像，必须 rebuild）
```powershell
cd d:\Geology\GMI
docker compose build backend
docker compose up -d backend
docker compose logs -f backend     # 确认启动无 ERROR
```

### 前端（dist 挂载，只 build 不重建容器）
```powershell
cd frontend
npm run build                      # 生成 dist
docker restart ssm-frontend        # 刷新容器(可选, 挂载立即可见)
```

> 注意：后端 `runtime/logs`（日志）、`uploads`（附件）为挂载目录，容器重建不丢失。

---

## 三、数据库变更

- 新增表/列：在 `sql/` 下新建 `NNN_xxx.sql`，并加入 `backend/app/services/migrate.py` 的
  `_CREATE_TABLE_SQL_FILES` / `_ADD_COLUMNS`（启动时幂等执行）。
- 含中文的 SQL 手动执行时必须带字符集，否则中文会乱码：
  ```powershell
  docker exec ssm-mysql sh -c "mysql --default-character-set=utf8mb4 -ussm_user -pssm_pass ssm < /docker-entrypoint-initdb.d/NNN_xxx.sql"
  ```

---

## 四、关键配置（环境变量）

| 变量 | 默认 | 说明 |
|---|---|---|
| `SECRET_KEY` | 无(生产必填) | JWT 密钥，缺失且非 DEBUG 时启动失败 |
| `DEBUG` | false | 生产必须 `false`（异常不泄露堆栈） |
| `CORS_ORIGINS` | localhost 列表 | 跨域白名单 |
| `MAX_UPLOAD_MB` | 200 | 上传大小上限 |
| `RATE_LIMIT_PER_MINUTE` | 300 | API 限流(每 IP/分钟) |
| `NOTIFY_WEBHOOK_URL` | 空 | 定时任务失败告警(企业微信/钉钉/通用) |
| `OLLAMA_BASE_URL` | host.docker.internal:11434 | 本地大模型 |

完整配置见 `backend/app/config.py`。

---

## 五、旧裸跑方式（已废弃）

原「3307 端口 + `ssm_db` + 本地 uvicorn 裸跑」方式已废弃，统一改用 Docker Compose。
如仍需本地裸跑连远程库，参考旧配置（3306/`ssm` 库）自行调整，不再维护。
