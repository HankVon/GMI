# 项目商机(原情报动态)后台管理系统设计文档

> 目标: 以**前台情报动态页(项目商机页)**为唯一输入, 反向推导后台管理系统 + 后端服务, 保证前后端字段、接口、权限、数据表完全对齐, 落地后"完整可运行"。
>
> 适用范围: `frontend/src/views/site/Intelligence.vue`(前台) ↔ `backend/app/api/v1/opportunities.py` + `public.py`(后端)。

---

## 1. 现状盘点(反向推导输入)

### 1.1 前台页面要素 → 数据来源映射

| 前台 UI 元素 | 组件状态 | 后端接口 | 数据表 |
|---|---|---|---|
| 热点领域(HOT pill, 单选) | `selectedTagIds` | `GET /public/opportunities/tags` | `opportunity_tag_def` (kind=hot_field) |
| 热门标签(多选 checkbox) | `selectedTagIds[]` | 同上 (kind=hot_project) | `opportunity_tag_def` |
| 项目地区(省份 select) | `form.regionProvince` | search `region_province` | `opportunity.region_province` |
| 投资金额(最小~最大+万) | `form.amountMin/Max` | search `amount_min/max` | `opportunity.amount_wan` |
| 项目阶段 select | `form.stage` | search `stage` | `opportunity.stage` |
| 项目角色 select | `form.unitRole` | search `unit_role` | `opportunity.unit_role` |
| 项目名称输入 | `form.projectName` | search `project_name`(空格多词 AND) | `opportunity.project_name` |
| 业主类型 select | `form.ownerType` | search `owner_type` | `opportunity.owner_type` |
| 业主名称输入(后台列表) | `query.owner_name` | search `owner_name` | `opportunity.owner_name` |
| 更新时间 date-range | `form.updateRange` | search `update_start/end` | `opportunity.updated_at` |
| 单位名称输入 | `form.unitName` | search `unit_name` | `opportunity.unit_name` |
| 项目类型 select | `form.projectType` | search `project_type` | `opportunity.project_type` |
| 数据集切换 pill | `datasetType` | search `dataset_type` | `opportunity.dataset_type` |
| 列表行: 名称/版本/业主类型标签/自定义标签 | `oppItems[]` | search 返回 items | 3 表 join |
| 命中总数 | `oppTotal` | search 返回 total | count(*) |
| 分页(页码/跳转) | `page/pageSize` | search `page/page_size` | — |
| 商机订阅(按钮) | 占位 | **新增** `POST /subscriptions` | `subscription_task` |
| 导出项目(按钮) | 占位 | **新增** `GET /export?<filter>` | `opportunity` |

### 1.2 前端 API 层(现状)

- `frontend/src/api/opportunities.ts` — 公开侧:
  - `listOpportunityTags()` → `GET /public/opportunities/tags`
  - `searchOpportunities(payload)` → `POST /public/opportunities/search`
- 后台侧(登录态)尚无对应 API 封装, 需新增 `opportunityAdmin.ts`。

### 1.3 后端现状(已具备)

`backend/app/api/v1/opportunities.py` 已实现 10 个登录态接口:
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/opportunities/sync-from-intents` | 意向公告→商机幂等建档 |
| GET | `/opportunities/tags` | 策展标签字典列表 |
| POST | `/opportunities` | 人工建档(V1.0 + 版本记录) |
| PUT | `/opportunities/{id}` | 人工更新(自动 bump 版本+摘要) |
| DELETE | `/opportunities/{id}` | 软删除 |
| POST | `/opportunities/search` | 主搜索(全套筛选) |
| GET | `/opportunities/export` | CSV 导出(当前筛选子集) |
| GET | `/opportunities/{id}` | 详情(含 vipOnly 字段) |
| GET | `/opportunities/{id}/versions` | 版本历史 |
| POST | `/opportunities/subscriptions` | 创建订阅(仅此, 无管理) |

`backend/app/api/v1/public.py` 公开侧(无需登录):
- `GET /public/opportunities/tags`
- `POST /public/opportunities/search`

---

## 2. 后端 API 接口清单(完整目标态)

> 标注 `[已有]` / `[新增]`。前缀均为 `/api/v1`。

### 2.1 公开侧(前台官网, 免登录)

| 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|
| GET | `/public/opportunities/tags` | 标签字典(前端筛选区) | [已有] |
| POST | `/public/opportunities/search` | 商机检索(全字段) | [已有] |
| GET | `/public/opportunities/export` | 公开导出(受 VIP/频控) | [新增,可选] |

### 2.2 登录侧(后台管理系统)

#### A. 商机 CRUD 主流程
| 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|
| POST | `/opportunities/search` | 主搜索 | [已有] |
| GET | `/opportunities/{id}` | 详情(含 VIP 字段) | [已有] |
| POST | `/opportunities` | 人工建档 | [已有] |
| PUT | `/opportunities/{id}` | 更新+bump 版本 | [已有] |
| DELETE | `/opportunities/{id}` | 软删除 | [已有] |
| GET | `/opportunities/{id}/versions` | 版本历史 | [已有] |
| GET | `/opportunities/export` | CSV 导出 | [已有] |
| POST | `/opportunities/sync-from-intents` | 意向→商机同步 | [已有] |

#### B. 标签字典管理(后台"策展标签"维护)
| 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|
| GET | `/opportunities/tags` | 标签字典列表 | [已有] |
| POST | `/opportunities/tags` | 新增标签 | **[新增]** |
| PUT | `/opportunities/tags/{id}` | 更新标签(名称/排序/热区) | **[新增]** |
| DELETE | `/opportunities/tags/{id}` | 软删标签(关联同步清) | **[新增]** |

#### C. 订阅管理(后台"我的订阅")
| 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|
| POST | `/opportunities/subscriptions` | 创建订阅 | [已有] |
| GET | `/opportunities/subscriptions` | 我的订阅列表 | **[新增]** |
| PUT | `/opportunities/subscriptions/{id}` | 启停切换 | **[新增]** |
| DELETE | `/opportunities/subscriptions/{id}` | 删除订阅 | **[新增]** |

### 2.3 统一响应约定
- 成功: `{"success": true, "data": ...}` (搜索含 `total/page/page_size`)
- 失败: FastAPI 标准 `{"detail": "..."}`(前端拦截器统一弹 ElMessage)
- 列表字段 camelCase, 查询参数 snake_case(兼容 `datasetType` 别名)。

---

## 3. 数据库表结构设计

> 完整 DDL 见 `sql/opportunity_ddl.sql`(幂等)。仅列核心字段与新增说明。

### 3.1 `opportunity` — 商机主表
| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | — |
| project_name | VARCHAR(255) NOT NULL | 项目名称(前台列表主标题) |
| owner_name | VARCHAR(255) NOT NULL | 业主名称 |
| owner_type | VARCHAR(64) | 国央企/民企/机关单位/事业单位/外资 |
| owner_scale | VARCHAR(64) | 大型/中型/小型 |
| amount_wan | BIGINT | 投资金额(万元) |
| stage | VARCHAR(64) | 项目阶段(立项/招标/签订等) |
| region_province / region_city | VARCHAR(64) | 省/市 |
| project_type | VARCHAR(64) | 项目类型 |
| unit_role / unit_name | VARCHAR | 我方角色/单位 |
| contact_summary | TEXT | 关键联系人(**VIP 设闸**) |
| followup_log | TEXT | 跟进记录(**VIP 设闸**) |
| body_excerpt | TEXT | 项目摘要 |
| current_version | VARCHAR(32) | 当前版本号(前台 v3.6.3 徽标) |
| dataset_type | VARCHAR(32) | project/proposed/landtrade |
| source | VARCHAR(128) | 数据来源(intent-notice-{id} 反查 intentId) |
| is_deleted / created_at / updated_at / published_at | — | 通用字段 |

索引: `idx_dataset_updated`, `idx_owner_name`, `idx_amount`。

### 3.2 `opportunity_version` — 版本历史
| 字段 | 说明 |
|---|---|
| opportunity_id | 商机 ID |
| version | V1.0 → V2.0.3 语义化版本 |
| change_summary | 变更摘要(字段 diff 自动生成或人工填写) |
| operator | 操作人 |
| released_at | 发布日期 |

### 3.3 `opportunity_tag_def` — 策展标签字典
| 字段 | 说明 |
|---|---|
| code | 唯一编码(hot_field_xxx / hot_proj_xxx) |
| label | 显示名(城市更新/大型民企项目…) |
| kind | hot_field / hot_project |
| is_new | NEW 角标 |
| sort_order | 排序 |

### 3.4 `opportunity_tag` — 商机↔标签关联
唯一键 `(opportunity_id, tag_id)`。

### 3.5 `owner` — 业主主表(聚合看板)
`opportunity_count`、`total_amount_wan` 由 `_sync_owner` 每次写操作后重算。

### 3.6 `subscription_task` — 订阅任务
| 字段 | 说明 |
|---|---|
| user_id | 订阅者 |
| name | 订阅名称 |
| condition_snapshot | JSON 筛选条件快照 |
| enabled | 启停 |
| product_type | tender / **opportunity** |
| last_run_at / last_match_count | 快照执行状态 |

---

## 4. 业务逻辑模块设计

### 4.1 版本管理(核心规则)
- 创建商机 → `V1.0`
- 人工更新 → 语义化递增: `V1.0→V1.0.1`, `V2.0.3→V2.0.4`, 无 patch 时补 `.1`
- 每次变更自动生成摘要(字段 diff), 亦可人工覆盖
- 前台列表展示 `current_version`(去 V 前缀), 详情展示完整版本历史
- 实现: `_next_version()` + `_summarize_changes()`

### 4.2 业主聚合统计
- 任何商机写入后 `_sync_owner(db, op)` 重算业主的机会数/累计投资
- 供业主概览看板/单位360°使用

### 4.3 意向→商机同步
- `POST /sync-from-intents`: 遍历 `intent_notice` 幂等建档(source 去重)
- 意向状态映射阶段: new→意向征集, qualified/matched→已匹配, skip→已跳过, expired→已过期

### 4.4 订阅快照(定时任务)
- `scheduler._job_subscription_digest()`: 每日扫描 `subscription_task`(product_type=opportunity), 按 `condition_snapshot` 匹配新增商机 → 写 `sys_notification`
- 需扩展: 目前实现仅按 keyword 匹配 `BidNotice`; 商机订阅需按 `product_type` 分流匹配 `Opportunity`

### 4.5 VIP 内容设闸
- 详情接口返回 `vipOnly: {contactSummary, followupLog}`
- 前端(前台详情页)展示前判断当前用户是否 VIP; 非 VIP 展示脱敏/引导开通

---

## 5. 管理后台功能模块(前端)

> 后台入口: 侧边栏「情报中心 → 商机管理 / 标签管理 / 订阅管理」, 路由挂在 `/workspace` 下, 与现有 `/workspace/intelligence` 同级。

### 5.1 商机管理(`/workspace/opportunities`)
功能清单:
1. 列表: 表格展示 项目名称/业主/业主类型/投资金额/阶段/地区/项目类型/数据集/当前版本/更新时间/标签/操作
2. 筛选: 复用前台全部筛选字段(数据集/地区/金额/阶段/角色/业主类型/项目名称/项目类型/更新时间)
3. 操作:
   - **新建商机**(弹窗表单, 建档后自动 V1.0)
   - **编辑**(弹窗, 提交后 bump 版本, 显示变更摘要预览)
   - **删除**(二次确认, 软删除)
   - **详情**(抽屉: 基本信息 + 版本时间线 + VIP 字段 + 标签管理)
   - **导出**(当前筛选 → CSV)
4. 标签: 新建/编辑时可勾选标签, 详情抽屉可调整

权限: 页面 `menu_intel_opportunities`; 写操作需 `api_opportunity_crud`。

### 5.2 标签管理(`/workspace/opportunity-tags`)
功能:
1. 标签字典表格(kind/名称/编码/NEW 角标/排序/状态)
2. 新增/编辑/删除标签
3. 分组展示: 热点领域(HOT) / 热门项目

权限: 页面 `menu_intel_opportunities`(与商机管理共用菜单), 写操作 `api_opportunity_crud`。

### 5.3 订阅管理(`/workspace/opportunity-subscriptions`)
功能:
1. 我的订阅列表(名称/条件快照摘要/启停/最近匹配/更新时间)
2. 新建订阅(基于当前筛选条件生成快照)
3. 启停切换 / 删除

权限: 页面 `menu_intel_opportunities`; 操作 `api_opportunity_subscription`。

---

## 6. 权限控制点

| 控制点 | 权限码 | 作用 |
|---|---|---|
| 后台商机管理菜单 | `menu_intel_opportunities` | 侧边栏菜单+路由 meta.permission |
| 商机写操作(创建/更新/删除/标签/同步) | `api_opportunity_crud` | 后端 `require_permission` |
| 订阅管理(列表/启停/删除) | `api_opportunity_subscription` | 后端 `require_permission` |
| VIP 字段(联系人/跟进记录) | 用户角色含 `vip` | 前端详情展示设闸, 后端按角色过滤 |

权限码需写入 `sys_permission` + 角色关联(见 8.3 SQL)。

---

## 7. 前后端交互方式

### 7.1 数据流(前台列表)
```
Intelligence.vue
  ├─ listOpportunityTags()          → GET  /public/opportunities/tags   (公开)
  ├─ searchOpportunities(payload)   → POST /public/opportunities/search (公开)
  └─ onSubscribe()  ──登录态──>     → POST /api/v1/opportunities/subscriptions (新增真实调用)
  └─ onExport()     ──登录态──>     → GET  /api/v1/opportunities/export?<filter> (下载 CSV)
```

### 7.2 数据流(后台管理)
```
OpportunityList.vue
  ├─ list/save/create/remove        → /api/v1/opportunities 系列(带 JWT)
  ├─ version history                → GET /opportunities/{id}/versions
  ├─ tags                           → GET/POST/PUT/DELETE /opportunities/tags
  └─ subscriptions                  → GET/POST/PUT/DELETE /opportunities/subscriptions
```
- 前台站点用 `siteApi`(无 token), 后台用 `api`(自动附加 Bearer)
- 后台请求经 `api/index.ts` 拦截器: 401 → 清理 token 跳登录; 业务错误 → ElMessage

### 7.3 用户操作流程
1. **普通用户(前台)**: 浏览商机 → 筛选 → 点击行跳意向详情 → VIP 查看联系人/跟进 → 订阅条件/导出 CSV
2. **调研员(后台)**: 商机管理 → 新建/编辑(自动版本) → 维护标签 → 导出 → 查看订阅推送
3. **管理员(后台)**: 标签字典维护 → 订阅任务启停 → 审计日志追踪所有写操作

---

## 8. 实施清单(落地项)

### 8.1 后端新增代码(`opportunities.py`)
- `GET /opportunities/subscriptions` — 当前用户订阅列表
- `PUT /opportunities/subscriptions/{id}` — 启停切换
- `DELETE /opportunities/subscriptions/{id}` — 删除
- `POST /opportunities/tags` — 新增标签
- `PUT /opportunities/tags/{id}` — 更新标签
- `DELETE /opportunities/tags/{id}` — 软删标签+清关联

### 8.2 前端新增代码
- `api/opportunityAdmin.ts` — 登录态商机管理 API 封装
- `views/workspace/OpportunityList.vue` — 商机管理(列表/筛选/新建/编辑/详情/导出)
- `views/workspace/OpportunityTagManage.vue` — 标签字典管理
- `views/workspace/OpportunitySubscriptions.vue` — 订阅管理
- `views/site/Intelligence.vue` — 接通 onSubscribe/onExport 真实调用
- `router/index.ts` — 注册 3 条路由(meta.permission)
- `App.vue` — 侧边栏菜单项

### 8.3 数据库/权限 SQL(`sql/017_opportunity_admin.sql`)
- 插入权限码 `menu_intel_opportunities` / `api_opportunity_crud` / `api_opportunity_subscription`
- 绑定到 `admin` 角色(全量)与 `viewer/project_mgr/member`(菜单级)

---

## 9. 一致性对照表(验收)

| 前台展示 | 后台维护 | 后端字段 | 数据表 |
|---|---|---|---|
| 项目名称 | 商机管理-新建/编辑 | `project_name` | opportunity |
| 业主名称 | 同上 | `owner_name` | opportunity |
| 业主类型标签(色块) | 同上 | `owner_type` | opportunity |
| v3.6.3 版本徽标 | 自动 bump | `current_version` | opportunity |
| 投资金额 万元 | 同上 | `amount_wan` | opportunity |
| 项目阶段 | 同上 | `stage` | opportunity |
| 地区 | 同上 | `region_province/city` | opportunity |
| 自定义标签(紫色) | 标签管理 | tag.label | opportunity_tag_def/tag |
| 热点领域/热门标签筛选 | 标签管理(策展) | kind | opportunity_tag_def |
| 数据集切换 | 商机管理(下拉) | `dataset_type` | opportunity |
| 更新时间 | 自动 updated_at | `updated_at` | opportunity |
| 商机订阅 | 订阅管理 | condition_snapshot | subscription_task |
| 导出 CSV | 商机管理-导出 | — | opportunity |
