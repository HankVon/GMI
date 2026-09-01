# 前台反向推导的后台管理系统与后端服务设计文档

> 项目：GMI 地质与产业情报数据平台
> 说明：本设计基于前台首页（`frontend/src/views/site/Home.vue`）已实现的功能与界面，反向推导其对应的后台管理系统与后端服务，并明确前后台职责边界，确保功能闭环。
> 技术栈基准：FastAPI + MySQL(SQLAlchemy) + Redis + Neo4j + Ollama(LLM)；前端 Vue3 + Element Plus + ECharts。

---

## 一、前台首页功能模块 → 后台管理需求映射

前台首页（Home.vue）共 12 个功能区块。逐一列出其功能、数据来源、以及反推的后台管理需求。

| # | 前台模块 | 前台实现 | 数据来源 | 反推的后台管理需求 |
|---|----------|----------|----------|--------------------|
| 1 | 顶部引导条 | 欢迎语 + 4 导航链接 | 静态 | 站点内容配置：可维护欢迎语、导航文案与链接 |
| 2 | 顶部 Banner 搜索 + 6 图标入口 | 4 类搜索跳转 + 6 个快捷入口 | 静态 + 路由跳转 | 图标入口管理：配置图标、标题、描述、跳转地址、排序、启用状态 |
| 3 | 认证条 | 4 项资质展示 | 静态数组 | 资质认证管理：维护资质名称、子描述、图标、颜色 |
| 4 | 主体三栏（左分类/中央/右排行） | 左分类链接 + 地图统计 + 三分类列表 + 排行 + 推荐 | **后端聚合接口** | ① 中央地图/统计/KPI：数据可视化配置 ② 三分类列表：标讯/项目数据管理 ③ 访问排行：访问统计采集与展示 ④ 推荐地勘单位：推荐位管理 |
| 5 | 红色 CTA Banner | 文案 + 链接 | 静态 | Banner 管理：标题、副文案、C 端链接、启用开关 |
| 6 | 请选择地质服务领域 | 8 领域 tab + 示例项目 | 静态 | 领域分类管理：领域名称、示例项目、展示顺序 |
| 7 | 地质行业情报动态（Feed） | 9 分类 tab + 列表 | **后端 `/public/home/feed`** | 内容运营：9 类数据（单位/标讯/拟建/人员/资质/荣誉/信用）的发布、排序、上下架 |
| 8 | 国际地学数据合作 | 6 机构卡片 | 静态 | 机构管理：机构名、简介、合作数、标识色 |
| 9 | 地质技术与装备服务 | 4 产品卡片 | 静态 | 产品/服务管理：标题、描述、图标、跳转 |
| 10 | 地质学术研讨 | 3 研讨卡片 | 静态 | 活动管理：类型标签、标题、描述、日期、背景色 |
| 11 | 权威资质认证体系 | 认证 Tabs + Logo 阵列 | 静态 | 认证体系管理：认证分类、机构名称、标识 |
| 12 | KPI 指标墙 | 4 项实时指标 | **后端 `/public/overview`** | 数据看板：指标口径配置、数据刷新监控 |

> **核心洞察**：首页 12 个模块中，**8 个为纯静态内容**（1/2/3/5/6/8/9/10/11 共 9 个，其中模块 2 含静态入口），仅 3 个依赖后端数据（4/7/12）。这意味着**首页数据管理重心在「内容配置」而非复杂业务**——因此后台应重点建设「首页内容配置中心」+「聚合数据看板」+「内容运营」三大能力。

---

## 二、后台管理系统功能结构设计

后台整体分为 **5 大模块**：首页配置中心、内容运营、数据看板、用户与权限、系统配置。

### 2.1 首页配置中心（Content CMS）

| 子功能 | 核心操作 | 关联前台模块 |
|--------|----------|--------------|
| 引导条配置 | 编辑欢迎语、导航项增删改、排序 | 模块1 |
| 图标入口管理 | 增删改 6 入口（图标/标题/描述/链接/排序/上架） | 模块2 |
| 资质认证管理 | 增删改资质条目（名称/描述/图标/颜色/排序） | 模块3 |
| CTA Banner 管理 | 编辑标题、副文案、链接、启用开关、背景 | 模块5 |
| 领域分类管理 | 增删改领域 tab + 每领域下的示例项目 | 模块6 |
| 机构合作管理 | 增删改国际机构（名称/简介/合作数/标识色） | 模块8 |
| 产品服务管理 | 增删改产品卡（标题/描述/图标/跳转） | 模块9 |
| 活动研讨管理 | 增删改研讨卡（类型/标题/描述/日期/背景色） | 模块10 |
| 认证体系管理 | 增删改认证分类 + 机构 logo | 模块11 |
| 推荐位管理 | 维护推荐地勘单位列表（名称/简介/排序/状态） | 模块4 |

### 2.2 内容运营（Content Operations）

| 子功能 | 核心操作 | 关联前台模块 |
|--------|----------|--------------|
| 标讯/项目内容管理 | 对标讯（勘探招标/矿产中标）、项目（治理项目）进行增删改、审核、上下架、排序 | 模块4/7 |
| 情报 Feed 运营 | 按 9 类数据（公司/标讯/拟建/项目/人员/经理/资质/荣誉/信用）发布与维护列表 | 模块7 |
| 内容发布 | 富文本/图文发布、附件上传、定时发布、审核流 | 模块7 |
| 内容标签 | 维护热点标签、领域标签 | 模块4/7 |

### 2.3 数据看板（Dashboard）

| 子功能 | 核心操作 | 关联前台模块 |
|--------|----------|--------------|
| 概况统计管理 | 配置统计口径（标讯线索/地勘单位/AI情报/专业人才） | 模块12 |
| 地图热力配置 | 维护区域维度聚合规则（region_top） | 模块4 |
| 访问排行 | 采集并展示本周访问排行、配置排行口径 | 模块4 |
| 趋势分析 | 平台月度/季度趋势、类型分布、数据质量 | 模块4/12 |
| 数据刷新监控 | 采集任务状态、数据新鲜度、异常告警 | 全部 |

### 2.4 用户与权限（RBAC）

| 子功能 | 核心操作 | 说明 |
|--------|----------|------|
| 用户管理 | 增删改查用户、重置密码、启停用、分配部门 | 复用现有 SysUser |
| 角色管理 | 创建角色、配置权限码、数据范围 | 复用现有 SysRole |
| 权限管理 | 维护菜单/按钮/API 权限码树 | 复用现有 SysPermission |
| 部门管理 | 维护层级部门树 | 复用现有 SysDepartment |
| 数据授权 | 对象级数据授权（project/company/bid） | 复用现有 SysDataGrant |
| 审计日志 | 查看操作日志与字段变更历史 | 复用现有 AuditLog |

### 2.5 系统配置

| 子功能 | 核心操作 | 说明 |
|--------|----------|------|
| 字段管理 | 配置业务实体的元数据字段 | 复用 FieldManager |
| 选项集管理 | 维护下拉/枚举选项 | 复用 OptionManager |
| 前台入口配置 | 维护前台导航、页脚、站点信息 | 新增强化 |
| 通知中心 | 系统通知推送、站内信 | 复用 Notification |

---

## 三、后端服务整体架构设计

### 3.1 整体架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                         前端 (Vue3 SPA)                       │
│  前台 site（无 Token / public）     后台 workspace+admin（带Token）│
└──────────────┬──────────────────────────────┬────────────────┘
               │                              │
               ▼                              ▼
        /api/v1/public/*               /api/v1/{业务}/* + /api/v1/rbac/*
        （公开只读聚合）                （鉴权 + 权限码 + 数据范围）
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI 后端服务层                        │
│  Api Router → Service Layer → Repository(ORM)               │
│  中间件: CORS / GZip / Audit / RateLimit / Auth              │
├─────────────────────────────────────────────────────────────┤
│  数据存储:  MySQL(SQLAlchemy) + Redis(缓存) + Neo4j(图谱)     │
│  外部能力:  Ollama(LLM研判) + Crawl4AI(爬虫) + 企查查(工商)   │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 接口设计思路

**原则 A：前台公开只读 + 后台鉴权可写（职责分离）**
- 前台首页全部走 `public.py`（`prefix=/public`，无 Token），返回**脱敏聚合**数据，杜绝暴露敏感字段。
- 后台所有写操作走 `rbac` 保护的业务路由，需 Token + 权限码 + 数据范围三重校验。

**原则 B：聚合接口服务展示，明细接口服务运营**
- 前台首页只需 3 类聚合接口：`GET /public/overview`（统计/地图/KPI/排行）、`GET /public/home`（各板块最新数据）、`GET /public/home/feed`（分页 Feed）。
- 后台需要明细 CRUD 接口，如 `POST/PUT/DELETE /content/*`、`POST /cms/banner` 等。

**原则 C：缓存降级**
- 首页聚合数据走 Redis 缓存 + 熔断降级（Neo4j/外部源不可用时返回降级数据）。

### 3.3 新增/复用接口清单

**（A）复用现有接口（已具备，无需改动）**

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | /api/v1/public/overview | 首页概况/地图/KPI/排行 |
| GET | /api/v1/public/home | 首页各板块最新数据 |
| GET | /api/v1/public/home/feed | 分类动态分页 |
| GET | /api/v1/public/intelligence | 情报动态 + 图谱 |
| POST | /api/v1/public/contact | 联系咨询落库 |
| 全部 | /api/v1/rbac/** | 用户/角色/权限/部门 |
| 全部 | /api/v1/audit/** | 审计日志/字段变更 |

**（B）需要新增的首页配置接口（CMS）**

| 方法 | 路径 | 用途 | 权限码 |
|------|------|------|--------|
| GET/PUT | /api/v1/cms/home-config | 读取/更新首页整体配置（JSON 结构） | `api_cms_home` |
| POST/PUT/DELETE | /api/v1/cms/nav-items | 引导条/导航项管理 | `api_cms_nav` |
| POST/PUT/DELETE | /api/v1/cms/quick-links | 图标入口管理 | `api_cms_quicklink` |
| POST/PUT/DELETE | /api/v1/cms/certs | 资质认证管理 | `api_cms_cert` |
| POST/PUT/DELETE | /api/v1/cms/banners | CTA Banner 管理 | `api_cms_banner` |
| POST/PUT/DELETE | /api/v1/cms/fields | 领域分类管理 | `api_cms_field` |
| POST/PUT/DELETE | /api/v1/cms/partners | 国际机构管理 | `api_cms_partner` |
| POST/PUT/DELETE | /api/v1/cms/products | 产品服务管理 | `api_cms_product` |
| POST/PUT/DELETE | /api/v1/cms/activities | 研讨活动管理 | `api_cms_activity` |
| POST/PUT/DELETE | /api/v1/cms/certifications | 认证体系管理 | `api_cms_certification` |
| POST/PUT/DELETE | /api/v1/cms/recommend-companies | 推荐地勘单位管理 | `api_cms_recommend` |

**说明**：新增路由可集中在 `api/v1/cms.py`（prefix=`/cms`），归属现有 RBAC 体系，通过权限码控制。

### 3.4 数据存储方案

| 数据类型 | 存储 | 说明 |
|----------|------|------|
| 首页配置内容 | MySQL 新表 `CmsHomeConfig` / `CmsBlockItem`（通用 KV 结构） | 用「区块类型 + 排序 + 启用状态 + JSON 内容」通用表，避免每模块建表 |
| 标讯/项目/人员等业务数据 | MySQL 现有模型 | `BidNotice`/`Project`/`Company`/`Person` 等 |
| 访问量统计 | MySQL `VisitRecord` 或 Redis 计数器 → 定时落库 | 支撑访问排行 |
| 缓存 | Redis | 首页聚合接口缓存，TTL 短期（如 5min） |
| 知识图谱 | Neo4j | 情报关系/人脉路径 |

**首页配置通用表设计（推荐）**：
```
CmsBlock (区块)
  id, block_key(unique, 如 banner/quick_links/certs), title,
  enabled(bool), sort_order, extra(JSON), created_at, updated_at
CmsBlockItem (区块条目)
  id, block_id(FK), item_key, title, subtitle, icon, link,
  meta(JSON, 存放颜色/日期/合作数等), sort_order, enabled, created_at, updated_at
```
> 优点：一套表支撑全部静态模块的增删改，后台可通用 CRUD，前端按 `block_key` 拉取。

### 3.5 权限控制策略

采用**三级权限控制**：

1. **认证（Authentication）**：JWT Token，`POST /api/v1/rbac/auth/login` 签发，前端 `ssm_token` 存储。
2. **功能权限（Authorization）**：`SysPermission` 权限码（`resource_type=menu/button/api`）+ `SysUserRole`/`SysRolePermission`，前端路由守卫校验 `meta.permission`。
3. **数据权限（Data Scope）**：`data_scope_rule`（ALL/DEPT_TREE/DEPT_ONLY/OWN/CUSTOM）+ `scope_dept_ids` + `SysDataGrant` 对象级授权，后端查询自动追加数据范围过滤。

**新增 CMS 模块的权限接入**：
- 在 `SysPermission` 增加 `api_cms_*` 权限码；
- 前端新增 `/admin/cms` 菜单，`meta.permission` 绑定对应权限码；
- 后端 `cms.py` 各路由声明 `Depends(require_permission("api_cms_*"))`。

### 3.6 与前台的数据交互方式

```
前台 Home.vue
  ├─ 首次挂载
  │    ├─ fetchOverview()        → GET /public/overview   （统计/地图/KPI/排行）
  │    └─ fetchHome()            → GET /public/home        （各板块最新数据）
  ├─ 分类切换
  │    └─ loadHomeCategory(k)    → GET /public/home/feed?category=&page=
  └─ 新增：拉取静态配置模块
       └─ siteApi.get("/public/home-config") → 一次性获取 banner/入口/资质/领域/机构/产品/活动/认证/推荐
```
- 前台**只读**：通过 `siteApi`（无 Token）访问 `/public/*` 聚合接口。
- 前台静态模块从硬编码改为**后台配置驱动**后，通过新增 `GET /public/home-config` 拉取配置，后台改动即时反映到前台，实现**内容闭环**。
- 前台 `contact` 表单、订阅、导出等写操作仍走 `siteApi`，但提交到后端统一落库/校验。

---

## 四、后台与后端职责边界

| 层 | 职责 | 禁止事项 |
|----|------|----------|
| **前端前台（site）** | 内容展示、搜索跳转、用户交互（订阅/咨询/导出）、数据可视化 | 不直连数据库；不携带写权限 Token 访问业务写接口；不展示敏感明细 |
| **前端后台（workspace/admin）** | 内容编辑、配置维护、数据看板、用户/权限管理 | 不绕过路由守卫；不执行未经权限码授权的操作 |
| **后端服务（FastAPI）** | 鉴权校验、业务逻辑、数据持久化、聚合计算、权限与数据范围过滤、审计日志 | 不把敏感字段透传给公开接口；不在 Service 层绕过权限校验 |
| **数据存储层** | MySQL 持久化 / Redis 缓存 / Neo4j 图谱 | 不承载展示逻辑 |

**闭环示意**：
```
后台录入内容 → 落库(CMS表/业务表) → 前台 /public 聚合接口读取
    ↑                                          │
    └──── 前台交互(咨询/订阅/导出) 写库 ←───────┘
```

---

## 五、实施建议

### 5.1 分阶段实施
- **一期（闭环优先）**：搭建 `CmsBlock/CmsBlockItem` 通用表 + `cms.py` 接口 + `/admin/cms` 配置页，将首页 9 个静态模块（1/2/3/5/6/8/9/10/11）配置化；新增 `GET /public/home-config`。
- **二期（运营增强）**：内容运营模块完善（发布/审核/定时）、标讯与 Feed 运营、推荐位管理。
- **三期（数据驱动）**：访问排行采集、数据看板（复用 dashboard.py）、趋势分析、刷新监控告警。

### 5.2 代码落点建议
- 后端：新增 `backend/app/api/v1/cms.py`、`backend/app/models/cms.py`（CmsBlock/CmsBlockItem）、`backend/app/schemas/cms.py`、`backend/app/services/cms.py`。
- 前端：新增 `frontend/src/views/admin/CmsManager.vue`（或 `HomeConfig.vue`），侧边栏「管理后台」分组新增「首页配置」菜单。

### 5.3 复用优先
- 用户/权限/审计/字段/选项：全部复用现有 RBAC 与配置模块，**不重复造轮子**。
- 权限码统一在 `SysPermission` 中维护，保证与现有 403 拦截、审计中间件无缝衔接。

---

## 六、附录：前台首页模块与后端接口对照速查

| 前台模块 | 前台实现文件 | 后端接口 |
|----------|--------------|----------|
| 顶部引导条 | Home.vue 静态 | （新增）/public/home-config |
| Banner 搜索+入口 | Home.vue 静态+跳转 | （新增）/public/home-config |
| 认证条 | Home.vue 静态 | （新增）/public/home-config |
| 三栏（地图/列表/排行/推荐） | Home.vue | /public/overview + /public/home + （新增）推荐位 |
| CTA Banner | Home.vue 静态 | （新增）/public/home-config |
| 地质服务领域 | Home.vue 静态 | （新增）/public/home-config |
| 情报动态 Feed | HomeNewsPanel.vue | /public/home + /public/home/feed |
| 国际地学合作 | Home.vue 静态 | （新增）/public/home-config |
| 技术与装备 | Home.vue 静态 | （新增）/public/home-config |
| 学术研讨 | Home.vue 静态 | （新增）/public/home-config |
| 资质认证体系 | Home.vue 静态 | （新增）/public/home-config |
| KPI 指标墙 | Home.vue | /public/overview |
