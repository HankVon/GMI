# 标讯中心 · 后台管理系统与后端服务设计

> 本文档基于前台「标讯中心」列表页（`/site/bids`）、详情页（`/site/bids/:id`）已实现的功能与界面，反向推导并设计对应的**后台管理系统**与**后端服务**，保证前后端数据契约完全匹配、且不破坏现有前台兼容性。
>
> 现状代码依据：
> - 前台详情页：`frontend/src/views/site/BidDetail.vue`（本轮已按参考图完成样式重构）
> - 前台列表页：`frontend/src/views/workspace/BidCenter.vue`
> - 详情聚合服务：`backend/app/services/tender_detail_service.py`
> - 标讯 API：`backend/app/api/v1/bids.py`
> - 数据契约：`backend/app/schemas/tender_detail.py`
> - 核心模型：`bid_notice.py` / `web_clue.py` / `web_source.py` / `user_entity_action.py` / `rbac.py` / `audit.py`
> - 鉴权中间件：`backend/app/middleware/auth.py`
> - 动态字段引擎：`field_meta.py` / `dynamic_crud.py`（可复用）

---

## 目录

1. [前台现状梳理（功能 → 数据来源 → 更新机制）](#1-前台现状梳理)
2. [后台管理系统功能模块](#2-后台管理系统功能模块)
3. [后端接口设计](#3-后端接口设计)
4. [数据模型设计](#4-数据模型设计)
5. [角色与权限体系](#5-角色与权限体系)
6. [前后端交互流程](#6-前后端交互流程)

---

## 1. 前台现状梳理

### 1.1 前台页面与数据流总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 前台（SiteLayout，需登录）                                                 │
│                                                                         │
│  列表页 /site/bids                      详情页 /site/bids/:id             │
│  ┌───────────────────────────┐         ┌──────────────────────────────┐ │
│  │ 筛选卡(关键词/类型/地区/时间) │         │ 面包屑 + 返回                  │ │
│  │ 标讯卡片列表(标题/类型/采购人/  │──跳转──▶│ 头部卡(标题+项目编号+内联标签)    │ │
│  │  地区/时间/中标数/下载)        │         │   + 平台链接 + 操作按钮          │ │
│  │ 订阅保存/分页                 │         │ Tab:基本信息/公告正文/招标单位/    │ │
│  └───────────────────────────┘         │     相似推荐                     │ │
│                                          │ 左:KV网格+关键时间+公告正文        │ │
│                                          │ 右:招标进度时间线+关联单位+关键词    │ │
│                                          │ 人脉网络图(CompanyGraph)          │ │
│                                          └──────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
          │                                        │
          ▼                                        ▼
  GET /api/v1/bids (JWT)              GET /api/v1/tenders/{id}/detail (JWT)
  POST /api/v1/bids (订阅)             GET /api/v1/tenders/{id}/similar
                                       POST /api/v1/tenders/{id}/monitor|favorite
          └──────────────┬────────────────────────────┘
                         ▼
        ┌─────────────────────────────────────────────────┐
        │ 后端 FastAPI (app/api/v1/bids.py)                │
        │ MySQL(MySQL) / Redis(缓存) / Neo4j(人脉图) / Ollama│
        └─────────────────────────────────────────────────┘
```

### 1.2 列表页模块 → 数据来源

| 界面模块 | 字段/交互 | 数据来源接口 | 更新机制 |
|---|---|---|---|
| 筛选卡（关键词/公告类型/地区/省/日期区间/采购人/供应商/仅看匹配） | `keyword, notice_type, region, province, date_from, date_to, purchaser_keyword, supplier_keyword, only_matched` | `GET /api/v1/bids` | 实时查询 `bid_notice` |
| 标讯卡片列表 | `id/title/purchaser/purchaser_company_id/region/notice_type/source_name/published_at/suppliers[]` | 同上 | 由采集解析/后台维护 |
| 卡片操作「下载招标公告」 | 跳详情页 | 前端跳转 | — |
| 保存订阅（筛选快照） | `name + 当前筛选参数` | 前端 `localStorage(gmi_bid_saved_filters)` | **建议迁移到后端**（见 §2.6） |
| 分页 | `page/page_size` | `GET /api/v1/bids` | — |
| 数据范围 | 部门过滤 | `data_scope_service.resolve_scope(scope, "bid")` | 后台权限配置 |

### 1.3 详情页模块 → 数据来源（核心）

> 前台唯一数据契约：`GET /api/v1/tenders/{id}/detail`，返回 `TenderDetailData`（见 `tender_detail.py`）。

| 界面模块 | 展示字段 | 数据来源 | 更新机制 |
|---|---|---|---|
| 面包屑 | `notice_type / title` | 前端由 `bid` 合成 | — |
| 头部标题 | `title + project_code` | `header.title / header.projectCode` | 后台编辑 |
| 头部标签 | 公告类型/行业/「N天后截止」 | `tags[].label/kind` | 服务端由 `notice_type + meta.industry + 截止日期` 合成；`kind` 支持 status/category/warning |
| 发布时间 | `header.publishedAt` | `bid_notice.published_at` | 后台维护/采集 |
| 平台来源链接 | `source_name + sourceUrl` | `header.sourceName/sourceUrl` | 来源管理（`web_source`） |
| 操作按钮（查看来源/下载/监控/收藏） | `url, attachment_url, actions` | `header.sourceUrl / attachments / actions` | 监控/收藏写 `user_entity_action` |
| 基本信息 KV 网格 | 公告编号/类型/地区/招标单位(实体)/招标代理(实体)/项目类型/建设规模(宽)/招标范围(宽)/工期/招标方式/预算/资金来源/评标办法/资格审查(宽)/联合体(宽) | `kv[]`（`bid_notice` 基本列 + `meta.project_info/finance/evaluation/requirements`） | 后台编辑结构化字段 |
| 关键时间信息 | 报名截止/文件获取截止/投标截止/开标时间 | `timeMatrix[]`（`meta.project_info.*deadline*`） | 后台编辑 |
| 招标进度时间线 | `name/date/summary`，最新在上 | `timeline[]`（`meta.timeline/dates`） | 后台事件管理 |
| 公告正文 | 全文 | `meta.body/content` | 采集入库/后台编辑 |
| 附件 | 列表/下载 | `meta.attachments` | 需落独立表（见 §2.7） |
| 关联单位 | 采购人 + 招标代理 + 中标供应商 | `entities.purchaser/agency + relatedCompanies`（`EntityLinkResolver` 名称匹配 `company`） | 后台确认匹配关系 |
| 人脉网络 | 图谱 | `CompanyGraph`（Neo4j） | 实时计算 |
| 相似推荐 | 同类型/同地区标讯 | `GET /tenders/{id}/similar` | 实时查询（`notice_type + region + 标题`） |
| 监控/收藏状态 | `actions.isMonitored/isCollected` | `user_entity_action(entity_type="bid")` | 用户操作 |

### 1.4 前台已用接口契约（现网事实，后台/公开双端必须对齐）

| 方法 | 路径 | 鉴权 | 用途 |
|---|---|---|---|
| GET | `/api/v1/bids?page=&page_size=&keyword=&region=&province=&notice_type=&date_from=&date_to=&purchaser_keyword=&supplier_keyword=&only_matched=` | JWT+数据范围 | 列表 |
| POST | `/api/v1/bids/rebuild` | `api_bid_crud` | 重建解析 |
| GET | `/api/v1/bids/company/{company_id}` | JWT | 公司中标关联 |
| GET | `/api/v1/bids/network/company/{company_id}` | JWT | 人脉网络 |
| GET | `/api/v1/tenders/{id}/detail` | JWT | 详情聚合 |
| GET | `/api/v1/tenders/{id}/similar?limit=` | JWT | 相似推荐 |
| GET | `/api/v1/tenders/actions/summary` | JWT | 监控/收藏统计 |
| GET | `/api/v1/tenders/{id}/actions` | JWT | 单条状态 |
| POST | `/api/v1/tenders/{id}/monitor` | JWT | 切换监控 |
| POST | `/api/v1/tenders/{id}/favorite` | JWT | 切换收藏 |
| POST | `/api/v1/bids/{id}/actions` | JWT | 旧版动作（兼容） |

---

## 2. 后台管理系统功能模块

后台入口沿用现有 `/workspace/*` 布局，新增菜单「标讯管理」。

```
标讯管理
├── 1. 标讯管理
│   ├── 标讯列表（多条件筛选/批量操作/数据范围）
│   ├── 标讯录入（手工建档）
│   ├── 标讯编辑（结构化字段 + 实体匹配 + 事件时间线）
│   └── 变更历史
├── 2. 审核发布
│   ├── 待审核队列
│   └── 已发布管理（发布/下架/恢复/过期）
├── 3. 分类管理（公告类型/行业/项目类型）
├── 4. 标签管理（详情页头部标签规则）
├── 5. 来源管理（数据源 CRUD + 手动抓取 + 待整理线索）
├── 6. 附件管理（上传/下载/预览/删除）
├── 7. 实体匹配（采购人/代理/供应商 → company 关联确认）
├── 8. 用户互动管理（监控/收藏明细 + 订阅管理）
├── 9. 数据看板（总量/趋势/类型分布/来源成功率）
└── 10. 系统管理（角色权限/操作日志/字段配置）
```

### 2.1 标讯管理（录入/编辑/删除）

**录入表单字段**（对齐详情页 KV 网格 + 时间矩阵 + 时间线 + 结构化信息）：

| 分组 | 字段 | 必填 | 控件 |
|---|---|---|---|
| 基础 | 标题 `title` | ✓ | 文本（≤512） |
| 基础 | 原文链接 `url` | ✓ | 文本（去重键之一） |
| 基础 | 项目编号 `project_code` | | 文本 |
| 基础 | 公告类型 `notice_type` | ✓ | 下拉（分类管理维护） |
| 基础 | 发布时间 `published_at` | ✓ | 日期时间 |
| 来源 | 来源站点 `source_id` / `source_name` | | 下拉 + 快照 |
| 地区 | 省份/地区 `region` | | 级联（复用 `region-tree`） |
| 单位 | 招标单位 `purchaser` + 匹配 `purchaser_company_id` | | 文本 + 单位库选择器 |
| 单位 | 招标代理 `agency` + 匹配 | | 文本 + 单位库选择器 |
| 项目 | 项目类型 `project.type` | | 下拉（分类管理） |
| 项目 | 建设规模 `project.scale`（宽） | | 多行文本 |
| 项目 | 招标范围 `project.scope`（宽） | | 多行文本 |
| 项目 | 建设工期 `project.duration` | | 文本 |
| 项目 | 招标方式 `project.method` | | 下拉 |
| 项目 | 报名截止 `registration_deadline` | | 日期时间 |
| 项目 | 文件获取截止 `document_deadline` | | 日期时间 |
| 项目 | 投标截止 `bid_deadline` | | 日期时间 |
| 项目 | 开标时间 `opening_time` | | 日期时间 |
| 资金 | 预算金额 `finance.budget` | | 金额（万元） |
| 资金 | 资金来源 `finance.source` | | 文本 |
| 评审 | 评标办法 `evaluation.method` | | 文本 |
| 评审 | 资格审查 `requirements.qualification`（宽） | | 多行文本 |
| 评审 | 联合体要求 `requirements.consortium`（宽） | | 多行文本 |
| 内容 | 公告正文 `meta.body` | | 富文本 |
| 内容 | 关键词 `keywords` | | 多标签 |
| 标签 | 展示标签 `tags` | | 标签选择（见 §2.4） |
| 时间线 | 招标进度事件列表 | | 动态行（名称/日期/摘要） |

**行为**：
- 保存时 `wf_status=draft`；支持从采集线索一键「补全入库」。
- 编辑任意字段写入 `field_change_history` + 一条 `audit_log`。
- 删除为软删（`is_deleted=1`），前台立即不可见。
- 详情页 `wide` 字段由服务端按标签名（建设规模/招标范围/资格审查/联合体要求等）自动判定，后台表单无需维护。

### 2.2 审核发布

状态机（新增 `wf_status` 列，与采集状态 `status` 分离）：

```
draft(草稿) ──提交──▶ pending(待审核) ──通过──▶ approved(已通过)
                        │                        │
                        └─驳回(rejected+意见) ──▶ 回 draft
                                                 ▼
                        published(已发布) ◀──发布── approved
                        │
                        ├──下架──▶ offline(已下架) ──恢复──▶ published
                        ├──过期(截止日期+定时策略)──▶ expired
                        └──编辑──▶ 回 draft 重新走审核
```

- 审核员操作写 `bid_review_record`（审核人/时间/意见/快照）。
- 发布时校验：标题、公告类型、发布时间、截止时间合法（截止 ≥ 发布时间）。
- 前台详情接口仅返回 `wf_status=published`（或 `offline` 之外）的标讯；列表同理。

### 2.3 分类管理

维护 `bid_category`（`notice_type` 公告类型 / `industry` 行业 / `project_type` 项目类型 三类字典），供录入表单下拉、筛选区、统计分组使用。复用 `option_set` 或 `field_meta` 机制均可。

### 2.4 标签管理

详情页头部标签目前由服务端规则合成：
- `notice_type` → kind=`status`（灰底）
- `meta.industry` → kind=`category`（蓝底）
- 含「截止」的倒计时 → kind=`danger`（红底）

新增 `bid_tag_def` 表支持运营维护「规则标签」：
- 按关键字自动打标（如标题含「地质灾害」→ 行业标签）。
- 支持手工为单条标讯加标签。
- 标签变更实时影响详情页头部。

### 2.5 来源管理

复用 `web_source` + `web_clue`：
- 来源站点 CRUD（名称/URL/域名白名单/关键词/排除词/地域/抓取模式/LLM增强开关）。
- 手动触发抓取：`POST /admin/bids/sources/{id}/crawl`，复用现有 crawl4ai + `ClueFilter` 流水线。
- 待整理线索列表（`web_clue.status=accepted` 未转实体）→ 一键补全进 `bid_notice`。
- 展示 `last_run_at / last_run_result / last_error`。

### 2.6 附件管理

新增 `bid_attachment` 表（替代 `meta.attachments` JSON）：
- 上传文件（落到 `uploads/`，写 `local_path/file_size`）、删除、重新抓取。
- 前台详情 `attachments` 由服务端联表聚合，保持契约不变。

### 2.7 实体匹配

- 列表展示未匹配标讯（`purchaser_company_id IS NULL` 或供应商未匹配）。
- 支持批量/单条确认：`purchaser/agency/supplier` → 选择 `company.id` 写入。
- 匹配结果驱动详情页实体链接、人脉网络、相似推荐。

### 2.8 用户互动管理

- 监控/收藏明细：查 `user_entity_action(entity_type="bid")`。
- 订阅管理：前台目前订阅存 localStorage，**建议新增 `bid_subscription` 表**（用户 id + 订阅名 + 筛选参数 JSON + 最近提醒时间），支持后台查看、订阅用户主动推送（每日新标讯邮件/站内信）。

### 2.9 数据看板

- 总量：标讯总数/已发布/待审核/草稿/下架/过期。
- 趋势：近 12 个月发布量（按 `published_at`）。
- 分布：公告类型 / 行业 / 地域 Top10。
- 来源成功率：各 `web_source` 抓取成功/失败率、解析成功率。
- 互动：总监控数、总收藏数、按标讯 Top10。

### 2.10 系统管理

- 角色权限：复用 `rbac.py`（角色/权限/用户-角色关联）。
- 操作日志：复用 `audit_log`，新增面向 `resource_type="bid"` 的筛选查询。
- 字段配置：复用 `field_meta` 动态表单驱动（可选）。

---

## 3. 后端接口设计

### 3.1 约定

- 前缀：后台管理接口统一 `/api/v1/admin/bids`；前台接口沿用现有 `/api/v1/bids`、`/api/v1/tenders/*`（**不改动**，保证前台兼容）。
- 鉴权：后台接口均 `Depends(get_current_user)` + `require_permission("bid_*")`；数据范围沿用 `data_scope_service`。
- 响应包：统一 `{ "success": bool, "detail"?: str, "data"/"items"/"total": ... }`。
- 分页：统一 `page` / `page_size`（默认 20，上限 100）。
- 校验：Pydantic Schema + 业务规则（必填、日期先后、金额 ≥ 0）；422 统一 `{ success, detail, errors[] }`。

### 3.2 接口清单

#### A. 标讯 CRUD

| 方法 | 路径 | 权限点 | 请求参数 | 响应 |
|---|---|---|---|---|
| GET | `/api/v1/admin/bids/list` | `bid_view` | `keyword, notice_type, region, province, industry, project_type, purchaser_keyword, wf_status, date_from, date_to, page, page_size` | `{ success, total, items:[BidAdminVO] }` |
| GET | `/api/v1/admin/bids/{id}` | `bid_view` | 路径参数 | `{ success, data: BidAdminDetailVO }` |
| POST | `/api/v1/admin/bids` | `bid_create` | `BidCreatePayload`（见 3.3） | `{ success, data:{ id } }` |
| PUT | `/api/v1/admin/bids/{id}` | `bid_edit` | `BidUpdatePayload`（部分字段） | `{ success }` |
| DELETE | `/api/v1/admin/bids/{id}` | `bid_delete` | 路径参数 | `{ success }`（软删） |
| POST | `/api/v1/admin/bids/batch` | `bid_edit` | `{ ids:[], action:"delete"\|"publish"\|"offline" }` | `{ success, affected }` |

#### B. 审核发布

| 方法 | 路径 | 权限点 | 请求参数 | 响应 |
|---|---|---|---|---|
| POST | `/api/v1/admin/bids/{id}/submit` | `bid_edit` | `{}`（draft→pending） | `{ success }` |
| POST | `/api/v1/admin/bids/{id}/review` | `bid_review` | `{ approve:bool, comment? }` | `{ success }`（approved/rejected） |
| POST | `/api/v1/admin/bids/{id}/publish` | `bid_publish` | `{}` | `{ success }` |
| POST | `/api/v1/admin/bids/{id}/offline` | `bid_publish` | `{ reason? }` | `{ success }` |
| POST | `/api/v1/admin/bids/{id}/restore` | `bid_publish` | `{}` | `{ success }` |
| GET | `/api/v1/admin/bids/review-queue` | `bid_review` | `page, page_size` | `{ success, items }` |
| GET | `/api/v1/admin/bids/{id}/review-history` | `bid_review` | 路径参数 | `{ success, items:[bid_review_record] }` |

#### C. 分类/标签/来源

| 方法 | 路径 | 权限点 | 说明 |
|---|---|---|---|
| GET | `/api/v1/admin/bids/categories` | `bid_category_manage` | 分类树（notice_type/industry/project_type） |
| POST/PUT/DELETE | `/api/v1/admin/bids/categories` | `bid_category_manage` | 分类增改删 |
| GET | `/api/v1/admin/bids/tags?kind=` | `bid_tag_manage` | 标签字典 |
| POST/PUT/DELETE | `/api/v1/admin/bids/tags` | `bid_tag_manage` | 标签管理 |
| POST | `/api/v1/admin/bids/{id}/tags` | `bid_tag_manage` | 手工打标签 `{ tag_ids:[] }` |
| GET | `/api/v1/admin/bids/sources` | `bid_source_manage` | 来源列表（含运行状态） |
| POST/PUT/DELETE | `/api/v1/admin/bids/sources` | `bid_source_manage` | 来源管理 |
| POST | `/api/v1/admin/bids/sources/{id}/crawl` | `bid_source_manage` | 触发单源抓取 |
| GET | `/api/v1/admin/bids/clues?status=accepted` | `bid_source_manage` | 待整理线索列表 |

#### D. 附件

| 方法 | 路径 | 权限点 | 说明 |
|---|---|---|---|
| GET | `/api/v1/admin/bids/{id}/attachments` | `bid_view` | 附件列表 |
| POST | `/api/v1/admin/bids/{id}/attachments` | `bid_edit` | multipart 上传 |
| DELETE | `/api/v1/admin/bids/{id}/attachments/{aid}` | `bid_edit` | 删除 |
| POST | `/api/v1/admin/bids/{id}/attachments/{aid}/refetch` | `bid_source_manage` | 重新抓取 |

#### E. 实体匹配

| 方法 | 路径 | 权限点 | 说明 |
|---|---|---|---|
| GET | `/api/v1/admin/bids/unmatched` | `bid_match` | 未匹配采购人/供应商列表 |
| POST | `/api/v1/admin/bids/{id}/match` | `bid_match` | `{ purchaser_company_id?, suppliers:[{name, company_id}] }` |
| POST | `/api/v1/admin/bids/match/auto` | `bid_match` | 全量触发自动名称匹配（复用 `EntityLinkResolver`） |

#### F. 用户互动/订阅

| 方法 | 路径 | 权限点 | 说明 |
|---|---|---|---|
| GET | `/api/v1/admin/bids/interactions?action=monitor\|collect` | `bid_view` | 监控/收藏明细 |
| GET | `/api/v1/admin/bids/subscriptions` | `bid_view` | 订阅列表（按用户/筛选条件） |
| DELETE | `/api/v1/admin/bids/subscriptions/{id}` | `bid_view` | 删除订阅 |

#### G. 统计/日志

| 方法 | 路径 | 权限点 | 说明 |
|---|---|---|---|
| GET | `/api/v1/admin/bids/stats` | `bid_view` | 看板统计 |
| GET | `/api/v1/admin/bids/{id}/audit-logs` | `menu_audit` | 单条标讯操作历史 |
| GET | `/api/v1/admin/audit-logs?resource_type=bid&resource_id=` | `menu_audit` | 全局日志检索 |

#### H. 复用现有接口

- 角色/权限：`/api/v1/rbac/*`、`/api/v1/rbac-admin/*`。
- 单位选择器：`/api/v1/companies/*`、`/api/v1/persons/*`。
- 前端公开接口：`/api/v1/bids`、`/api/v1/tenders/*` 保持契约不变。

### 3.3 关键请求/响应结构示例

**`BidAdminVO`（后台列表行）**：

```json
{
  "id": 4798,
  "title": "江门港开平港区水口公共码头项目设计施工总承包招标公告",
  "notice_type": "招标公告",
  "industry": "港航",
  "region": "广东省-江门市-开平市",
  "purchaser": "开平市公控港务有限公司",
  "purchaser_company_id": 711,
  "agency": "开平市公控德中交咨...",
  "budget": "10495.93万",
  "published_at": "2026-08-27",
  "bid_deadline": "2026-09-02 23:59",
  "wf_status": "published",
  "source_name": "全国公共资源交易平台(广东省)",
  "monitor_count": 12,
  "collect_count": 8,
  "matched": true,
  "created_by_name": "张三",
  "created_at": "2026-08-27 10:00"
}
```

**`BidCreatePayload`**：

```json
{
  "title": "string(required, ≤512)",
  "url": "string(required, ≤1024)",
  "project_code": "string?",
  "notice_type": "string(required)",
  "industry": "string?",
  "region": "string?",
  "published_at": "2026-08-27T10:00:00",
  "source_id": 5,
  "source_name": "string?",
  "purchaser": "string?",
  "purchaser_company_id": 711,
  "agency": "string?",
  "project": {
    "type": "设计 施工", "scale": "…", "scope": "…",
    "duration": "420天", "method": "公开招标",
    "registration_deadline": "2026-09-02", "document_deadline": "...",
    "bid_deadline": "2026-09-02 23:59", "opening_time": "..."
  },
  "finance": { "budget": "10495.93万", "source": "企业自筹: 国有投资" },
  "evaluation": { "method": "…" },
  "requirements": { "qualification": "…", "consortium": "…" },
  "keywords": ["港航", "码头"],
  "timeline": [ { "label": "招标公告", "date": "2026-08-27", "summary": "" },
                { "label": "招标计划", "date": "2026-05-29", "summary": "" } ],
  "body": "string?(正文)",
  "wf_status": "draft"
}
```

**`POST /review` 响应示例**：

```json
{ "success": true, "detail": "审核通过", "data": { "id": 4798, "status": "approved" } }
```

**`BidAdminDetailVO` = `BidCreatePayload` + `suppliers[]` + `attachments[]` + `tags[]` + `timeline[]` + `review_records[]` + `created_by/updated_by`**。

---

## 4. 数据模型设计

### 4.1 核心实体关系

```
web_source ──1:N──▶ web_clue ──1:1──▶ bid_notice(经解析/一键补全)
                        │ 1:N
                        ├──▶ bid_attachment          (新)
                        ├──▶ bid_notice_tag  M:N bid_tag_def  (新)
                        └──▶ bid_review_record        (新)

bid_notice ──1:N──▶ user_entity_action(entity_type="bid")  监控/收藏
bid_notice ──1:N──▶ bid_subscription_filter(M:N user)      订阅(新)
bid_notice.purchaser_company_id ──N:1──▶ company(实体匹配)
bid_notice.meta.suppliers[].supplier_company_id ──N:1──▶ company

sys_user ──M:N──▶ sys_role ──M:N──▶ sys_permission
sys_user ──M:N──▶ sys_department(数据范围)
audit_log / field_change_history (独立审计表)
```

### 4.2 表结构

#### 4.2.1 `bid_notice`（标讯主表，现有 + 扩展）

```sql
CREATE TABLE `bid_notice` (
  `id`                 BIGINT AUTO_INCREMENT PRIMARY KEY,
  `clue_id`            BIGINT NULL COMMENT '来源线索 web_clue.id',
  `title`              VARCHAR(512) NOT NULL COMMENT '公告标题',
  `url`                VARCHAR(1024) NULL COMMENT '公告链接(与 source_id 组成去重键)',
  `purchaser`          VARCHAR(512) NULL COMMENT '采购人/业主名称',
  `purchaser_company_id` BIGINT NULL COMMENT '匹配的公司 id',
  `region`             VARCHAR(128) NULL COMMENT '采购区域(省/地区)',
  `meta`               JSON NULL COMMENT '结构化明细: project_info/finance/evaluation/requirements/timeline/suppliers/body/attachments',
  `notice_type`        VARCHAR(64) NULL COMMENT '公告类型(招标/中标/成交)',
  `agency`             VARCHAR(512) NULL COMMENT '采购代理机构名称',
  `source_id`          BIGINT NULL COMMENT '来源站点 id(web_source)',
  `source_name`        VARCHAR(128) NULL COMMENT '来源名称快照',
  `published_at`       DATETIME NULL COMMENT '公告发布时间',
  `fetched_at`         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '解析时间',
  -- ↓↓↓ 后台审核/发布扩展字段(新增迁移) ↓↓↓
  `wf_status`          VARCHAR(32) NOT NULL DEFAULT 'draft'
                       COMMENT '流转状态: draft/pending/approved/published/offline/expired',
  `review_comment`     VARCHAR(512) NULL COMMENT '最新审核意见',
  `reviewer_id`        BIGINT NULL,
  `reviewed_at`        DATETIME NULL,
  `publisher_id`       BIGINT NULL,
  `offline_at`         DATETIME NULL,
  `industry`           VARCHAR(128) NULL COMMENT '行业(头部标签 category)',
  `project_code`       VARCHAR(256) NULL COMMENT '项目编号',
  `budget`             VARCHAR(128) NULL COMMENT '预算金额展示文本',
  `created_by`         BIGINT NULL COMMENT '创建人',
  `created_at`         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted`         TINYINT(1) NOT NULL DEFAULT 0,
  KEY `idx_title` (`title`),
  KEY `idx_region` (`region`),
  KEY `idx_source` (`source_id`),
  KEY `idx_pubtime` (`published_at`),
  KEY `idx_wf_status` (`wf_status`),
  KEY `idx_type` (`notice_type`),
  KEY `idx_purchaser` (`purchaser_company_id`),
  KEY `idx_deleted_pubtime` (`is_deleted`, `published_at`),
  CONSTRAINT `uk_source_url` UNIQUE (`source_id`, `url`(255)) COMMENT '防重复采集'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标讯公告(招标/中标)';
```

> 说明：结构化字段继续保留在 `meta` JSON（兼容现有 `TenderDetailService` 直接读取），后台录入通过 Pydantic Schema 组装进 `meta` 的 `project_info/finance/evaluation/requirements/timeline` 分组，**不拆表**，避免大规模重构；高频筛选列（`notice_type/region/industry/wf_status/published_at`）冗余到独立列以走索引。

#### 4.2.2 `bid_attachment`（新增，附件）

```sql
CREATE TABLE `bid_attachment` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `bid_id`      BIGINT NOT NULL,
  `file_name`   VARCHAR(255) NOT NULL,
  `local_path`  VARCHAR(512) NULL COMMENT 'uploads/相对路径',
  `remote_url`  VARCHAR(1024) NULL,
  `file_size`   BIGINT DEFAULT 0,
  `file_type`   VARCHAR(32) NULL COMMENT 'pdf/docx/xlsx...',
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted`  TINYINT(1) DEFAULT 0,
  KEY `idx_bid` (`bid_id`)
) ENGINE=InnoDB COMMENT='标讯附件';
```

#### 4.2.3 `bid_review_record`（新增，审核记录）

```sql
CREATE TABLE `bid_review_record` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `bid_id`      BIGINT NOT NULL,
  `action`      VARCHAR(32) NOT NULL COMMENT 'submit/review_approve/review_reject/publish/offline/restore',
  `reviewer_id` BIGINT NULL,
  `reviewer_name` VARCHAR(64) NULL,
  `comment`     VARCHAR(512) NULL COMMENT '意见',
  `snapshot`    JSON NULL COMMENT '操作时数据快照',
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_bid` (`bid_id`, `created_at`)
) ENGINE=InnoDB COMMENT='标讯审核/发布操作记录';
```

#### 4.2.4 `bid_tag_def` + `bid_notice_tag`（新增，标签）

```sql
CREATE TABLE `bid_tag_def` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `label`       VARCHAR(64) NOT NULL,
  `kind`        VARCHAR(16) NOT NULL DEFAULT 'category'
                COMMENT 'status/category/warning/danger/plain',
  `rule_keyword` VARCHAR(512) NULL COMMENT '自动打标关键字(逗号分隔)',
  `sort_order`  INT DEFAULT 0,
  `enabled`     TINYINT(1) DEFAULT 1,
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted`  TINYINT(1) DEFAULT 0,
  UNIQUE KEY `uk_label` (`label`)
) ENGINE=InnoDB COMMENT='标讯标签定义';

CREATE TABLE `bid_notice_tag` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `bid_id`      BIGINT NOT NULL,
  `tag_id`      BIGINT NOT NULL,
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_bid_tag` (`bid_id`, `tag_id`)
) ENGINE=InnoDB COMMENT='标讯-标签关联';
```

#### 4.2.5 `bid_category`（新增，分类字典）

```sql
CREATE TABLE `bid_category` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `category`    VARCHAR(32) NOT NULL COMMENT 'notice_type/industry/project_type',
  `code`        VARCHAR(64) NOT NULL,
  `label`       VARCHAR(128) NOT NULL,
  `parent_id`   BIGINT NULL,
  `sort_order`  INT DEFAULT 0,
  `enabled`     TINYINT(1) DEFAULT 1,
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted`  TINYINT(1) DEFAULT 0,
  UNIQUE KEY `uk_cat_code` (`category`, `code`)
) ENGINE=InnoDB COMMENT='标讯分类字典';
```

#### 4.2.6 `bid_subscription`（新增，订阅迁移）

```sql
CREATE TABLE `bid_subscription` (
  `id`          BIGINT AUTO_INCREMENT PRIMARY KEY,
  `user_id`     BIGINT NOT NULL,
  `name`        VARCHAR(64) NOT NULL COMMENT '订阅名称',
  `filters`     JSON NOT NULL COMMENT '筛选参数快照 {keyword, notice_type, region, ...}',
  `notify_enabled` TINYINT(1) DEFAULT 1,
  `last_notified_at` DATETIME NULL,
  `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
  `updated_at`  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `is_deleted`  TINYINT(1) DEFAULT 0,
  KEY `idx_user` (`user_id`)
) ENGINE=InnoDB COMMENT='标讯订阅';
```

#### 4.2.7 复用表（不新建）

- `web_clue` / `web_source`：采集原始线索与来源。
- `company` / `project_company`：实体匹配。
- `sys_user` / `sys_role` / `sys_permission` / `sys_user_role` / `sys_role_permission` / `sys_department` / `sys_data_grant`：RBAC + 数据范围。
- `audit_log` / `field_change_history`：审计。
- `user_entity_action`：监控/收藏（`entity_type="bid"`）。
- `field_metadata` / `option_set`：动态表单驱动（可选）。

### 4.3 索引建议

- 高频筛选组合：`(wf_status, is_deleted)`、`(notice_type, wf_status)`、`(region, wf_status)`、`(published_at, wf_status)`、`(purchaser_company_id, wf_status)`。
- 列表默认排序：`published_at DESC, id DESC` → 复合索引 `(is_deleted, published_at, id)`。
- 相似推荐：`(notice_type, region)`、`(notice_type, published_at)`。
- 订阅推送：`bid_subscription(user_id)` + `bid_notice(published_at)` 双端扫描。
- 文本模糊搜索量大时引入全文索引（`title`）或接 ElasticSearch（已有 `tender_es_mapping.json` 可对接）；MySQL LIKE 仅适用于小数据量。

---

## 5. 角色与权限体系

### 5.1 角色定义

| 角色 | 编码 | 说明 | 数据范围默认 |
|---|---|---|---|
| 超级管理员 | `super_admin` | 系统全部功能 + RBAC | ALL |
| 管理员 | `admin` | 标讯全流程 + 分类/标签/来源/统计 | ALL |
| 编辑 | `editor` | 标讯录入/编辑/提交/发布/下架/附件/标签 | DEPT_TREE 或 DEPT_ONLY |
| 审核员 | `reviewer` | 审核队列、通过/驳回 | ALL |
| 分析员 | `analyst` | 只读 + 导出 | OWN/DEPT_ONLY |
| 访客（只读） | `viewer` | 仅查看已发布内容 | DEPT_ONLY |

### 5.2 权限点编码（新增）

| 权限点 | 名称 | super_admin | admin | editor | reviewer | analyst | viewer |
|---|--|:-:|:-:|:-:|:-:|:-:|:-:|
| `bid_view` | 查看标讯 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `bid_create` | 录入标讯 | ✓ | ✓ | ✓ | | | |
| `bid_edit` | 编辑/删除/批量 | ✓ | ✓ | ✓ | | | |
| `bid_review` | 审核标讯 | ✓ | ✓ | | ✓ | | |
| `bid_publish` | 发布/下架/恢复 | ✓ | ✓ | ✓ | | | |
| `bid_match` | 实体匹配 | ✓ | ✓ | ✓ | | | |
| `bid_category_manage` | 分类管理 | ✓ | ✓ | | | | |
| `bid_tag_manage` | 标签管理 | ✓ | ✓ | | | | |
| `bid_source_manage` | 来源/抓取管理 | ✓ | ✓ | | | | |
| `bid_export` | 导出 | ✓ | ✓ | ✓ | | ✓ | |
| `menu_audit` | 操作日志 | ✓ | ✓ | | | | |

> 新增权限点需写入 `sys_permission` 并挂到角色；后台路由通过 `require_permission("bid_edit")` 生效，与现有 `auth.py` 机制一致。

### 5.3 数据范围（数据权限）

复用现有 `data_scope_service`（`resolve_scope` + `scope_filter`，scope 传 `"bid"`）：
- 列表查询自动附加部门过滤。
- 编辑仅能改本人/本部门创建的标讯（`created_by` 校验）。
- 审核员默认不受部门限制。

### 5.4 字段级权限（可选）

复用 `field_meta.field_permissions`：
- 例如 `finance.budget`（金额）、`requirements`（评审/资质）字段仅 `admin/editor/reviewer` 可见，`analyst` 仅见脱敏值。
- 详情页 `isGated` 机制已预留（`GatedFieldFilter.sensitive_fields`），当前 `can_view_sensitive=True`；未来启用会员制只需替换判定函数，后台始终返回真实值。

---

## 6. 前后端交互流程

### 6.1 完整链路：后台创建 → 前台展示

```
编辑(editor)             审核员(reviewer)          管理员(admin)           前台官网
    │                          │                       │                      │
    ├─录入标讯──────────────▶   │                       │                      │
    │ wf_status=draft          │                       │                      │
    ├─POST /admin/bids         │                       │                      │
    │ 落库(写audit_log)        │                       │                      │
    ├─提交审核───────────────▶  │                       │                      │
    │ wf_status=pending        │                       │                      │
    │                          ├─POST /review         │                      │
    │                          │ approve=true? ───✓   │                      │
    │                          │       │              │                      │
    │                          │      false(驳回)     │                      │
    │ 回draft+意见 ◀───────────┘       │              │                      │
    │                                   ▼              │                      │
    │                           wf_status=approved     │                      │
    │                                   │──POST /publish▶│                    │
    │                                   │               ├─写 published_at      │
    │                                   │               └──────────────────▶ │
    │                                   │                GET /tenders/{id}/detail
    │                                   │                ◀─ TenderDetailData    │
    │                                   │                  (wf_status=published │
    │                                   │                   过滤)               │
    │                                   │                ──详情页可见──▶         │
    └───────────────────────────────────┴───────────────────────────────────▶
```

### 6.2 采集 → 整理 → 审核 → 发布

```
定时任务/手动触发
  → POST /admin/bids/sources/{id}/crawl
  → crawl4ai 抓取列表→详情 → ClueFilter 筛选 → 写 web_clue(status=accepted)
  → 解析器结构化 → 写 bid_notice(wf_status=draft, source_id 去重)
  → 编辑在「待整理线索」逐条补全 → 提交审核 → 发布(见 6.1)
```

### 6.3 编辑已发布标讯 / 变更历史

```
编辑修改已发布标讯
  → 保存后 wf_status 回 draft（重新走审核）
  → 写 field_change_history(每个字段 old/new) + audit_log
  → 前台立即停止展示旧版本（wf_status!=published 过滤）
```

### 6.4 下架 / 过期

```
手动下架: POST /admin/bids/{id}/offline { reason }
  → wf_status=offline, offline_at=now → 前台过滤
恢复: POST /admin/bids/{id}/restore → wf_status=published
过期: 定时任务扫描(非招标类公告按发布时间 + N 天/招标类按 bid_deadline)
  → 超期自动置 expired（运营可配置阈值）
```

### 6.5 实体匹配 → 人脉联动

```
后台确认 purchaser_company_id / supplier_company_id
  → 前台详情页 kv 网格出现可点击的「招标单位」实体链接
  → 人脉网络 CompanyGraph 包含该标讯
  → 相似推荐 / 公司中标关联(/bids/company/{id}) 实时生效
```

### 6.6 前台与后台数据契约对齐原则

| 维度 | 后台接口 | 前台接口（现有，不改） |
|---|---|---|
| KV 字段 | 真实全量 | `DisplayField(value/displayText/isGated)`，未披露=「未披露」 |
| 金额 | 精确（万元文本） | 原样展示（当前无会员脱敏） |
| 联系人/电话 | 真实 | 目前不展示；未来接 `isGated` 脱敏 |
| 时间线 | 完整事件（含摘要） | `timeline[]` 最新在上 |
| 标签 | 规则+手工 | `tags[].label/kind` 五色样式 |
| 附件 | 管理端全量 | `attachments` 下载/预览 |
| 实体链接 | 确认的 company_id | `EntityLink(entityId/href/matched)` |

> 关键原则：**新增后台能力，不改动前台 `/api/v1/bids`、`/api/v1/tenders/*` 契约**；后台通过扩展 `wf_status` 与审核流转驱动「已发布才可见」，前台代码零改动即可对接。

---

## 7. 落地建议（实施顺序）

1. **阶段一（最小闭环）**：`bid_notice` 扩展迁移（`wf_status` 等）+ 后台标讯 CRUD + 审核发布状态机 + 前台列表/详情增加 `wf_status=published` 过滤（服务端），前台页面零改动。
2. **阶段二（管理完善）**：分类/标签/来源管理 + 附件表迁移 + 实体匹配页 + 数据看板。
3. **阶段三（互动增强）**：订阅表落地（从 localStorage 迁移）+ 每日新标讯推送 + 监控/收藏明细页。
4. **阶段四（体系完善）**：权限点接入 `rbac`、字段级权限、审计日志查询页、导出、ElasticSearch 全文检索。

> 参考实现可对照 `docs/intelligence-admin-backend-design.md`（情报动态后台），两者共享同一套 RBAC / 审计 / 动态字段 / 数据范围基础设施，标讯后台可直接复用其架构模式。
