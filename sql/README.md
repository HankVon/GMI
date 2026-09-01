# SQL 脚本目录

MySQL 8.0，库名 `ssm`（容器 `ssm-mysql`）。

---

## ⚠️ 两条铁律

### 1. 本目录必须保持平铺，**不要建子目录**

启动时 `backend/app/services/migrate.py` 会按**裸文件名**在 `sql/` 根目录查找 `_CREATE_TABLE_SQL_FILES` 清单（32 个文件）。一旦建子目录，这些文件会全部找不到，而 migrate **只打 warning 不报错**，表现为「新表静默缺失」，极难排查。

### 2. 不用 alembic

`backend/alembic/` 已废弃。首次建库走本目录挂载进 MySQL 的 `/docker-entrypoint-initdb.d`，增量走 `migrate.py` 幂等补齐。

---

## 二、执行机制

| 场景 | 机制 | 说明 |
|---|---|---|
| **首次建库** | `docker-compose.yml` 把 `./sql` 挂到 MySQL 的 `/docker-entrypoint-initdb.d` | **仅首次生效**（数据卷已存在则跳过）。此时 `001_init_ddl.sql` 会先执行 |
| **增量补列/建表** | 后端启动时 `app/services/migrate.py` | 幂等。MySQL 8 无 `ADD COLUMN IF NOT EXISTS`，故先查 `information_schema` 再决定；单条失败只告警不阻断。结果在 `/api/v1/health` 暴露 |

### 新增表的正确姿势

1. 在 `sql/` 下新建 `xxx_ddl.sql`，所有语句用 `CREATE TABLE IF NOT EXISTS`；
2. 把**文件名**加进 `backend/app/services/migrate.py` 的 `_CREATE_TABLE_SQL_FILES`；
3. 重启 backend：`docker compose restart backend`。

---

## 三、文件清单

### A. 初始建库（1 个）

| 文件 | 说明 |
|---|---|
| `001_init_ddl.sql` | ★ 业务库初始 DDL，含核心表结构。**仅首次建库时由 initdb 执行**，不在 migrate 清单内 |

### B. 编号迁移脚本（14 个，按编号顺序）

| 文件 | 说明 | 在 migrate 清单 |
|---|---|---|
| `010_data_scope.sql` | 数据范围（Data Scope）扩展 —— 数据级授权 | ✅ |
| `011_user_permission.sql` | 用户级功能直授（绕过角色，直接给用户挂权限） | ✅ |
| `012_menu_permissions.sql` | 页面级菜单权限补齐 | ✅ |
| `013_bid_admin_permissions.sql` | 标讯后台管理权限点 | ✅ |
| `013_role_menu_defaults.sql` | 存量业务角色默认页面权限（平滑过渡，避免非超管被锁死） | ✅ |
| `014_fix_menu_names.sql` | 修复 012 因客户端字符集造成的菜单名双重编码乱码 | ✅ |
| `015_notification.sql` | 站内通知表（线索过期/项目进度变更/新中标提醒） | ✅ |
| `016_report_menu.sql` | 报表中心菜单权限 | ✅ |
| `017_intent_admin.sql` | 情报中心后台管理菜单 + 权限点种子 | ✅ |
| `017_opportunity_admin.sql` | 商机管理后台权限（商机/策展标签/订阅） | ✅ |
| `018_bid_category_seed.sql` | 标讯分类选项集 seed（供前台 FilterSidebar 标签云动态加载） | ✅ |
| `019_bid_admin_ext_permissions.sql` | 标讯后台扩展权限点（分类/订阅/统计/导入） | ✅ |

### C. 模块建表 DDL（18 个）

| 文件 | 对应模块 | 在 migrate 清单 |
|---|---|---|
| `web_clue_ddl.sql` | 网页线索/情报（爬取入库） | ✅ |
| `bid_notice_ddl.sql` | 中标公告 | ✅ |
| `bid_review_record_ddl.sql` | 标讯审核记录 | ✅ |
| `bid_attachment_ddl.sql` | 标讯附件 | ✅ |
| `opportunity_ddl.sql` | 商机子产品 DDL + 种子 | ✅ |
| `intent_notice_ddl.sql` | 意向性信息结构化表 | ✅ |
| `intent_attachment_ddl.sql` | 情报附件 | ✅ |
| `intent_contact_ddl.sql` | 意向联系人 | ✅ |
| `intent_ai_cache_ddl.sql` | 情报 AI 分析结果缓存 | ✅ |
| `intelligence_category_ddl.sql` | 情报分类字典 | ✅ |
| `project_clue_ddl.sql` | 项目跟踪线索关联（各阶段增量归整） | ✅ |
| `business_network_ddl.sql` | 人脉库可扩展数据模型 | ✅ |
| `entity_relation_ddl.sql` | 知识抽取三元组（开放域关系） | ✅ |
| `geo_ddl.sql` | 营销智能体 · GEO 监测 | ✅ |
| `content_ddl.sql` | 营销智能体 · 内容工厂 | ✅ |
| `industry_data_ddl.sql` | 行业数据标准库（分项查询） | ✅ |
| `cms_ddl.sql` | 前台首页内容配置 + 默认种子 + 菜单权限 | ✅ |
| `favorite_tag_ddl.sql` | 收藏与标签表 | ✅ |
| `subscription_task_ddl.sql` | 订阅任务 | ✅ |
| `user_entity_action_ddl.sql` | 用户实体行为（已读/跟踪等） | ✅ |

### D. ES 映射（1 个）

| 文件 | 说明 |
|---|---|
| `tender_es_mapping.json` | Elasticsearch 标讯索引 mapping（settings + mappings），仅在引入 ES 时使用，当前主检索走 MySQL |

### E. 临时核查工具（3 个）

| 文件 | 说明 |
|---|---|
| `_dbcheck.py` / `_dbcheck2.py` / `_dbcheck3.py` | 一次性数据库核查脚本（直连 `mysql` 主机，**只能在容器内跑**）。非 migrate 依赖，可随时删除或更新 |

---

## 四、手工执行方式

```powershell
# 在容器内执行某个脚本
docker exec -i ssm-mysql mysql -ussm_user -pssm_pass ssm < sql\017_intent_admin.sql

# 或进入容器执行
docker exec -it ssm-mysql mysql -ussm_user -pssm_pass ssm
source /sql/xxx.sql;
```

> `sql/` 在容器内挂载为 **`/sql`**（backend 容器为只读 `/sql:ro`，mysql 容器为 initdb 目录），路径解析在容器与裸跑下都正确，**不要改动 `migrate.py` 里的层级写法**。
