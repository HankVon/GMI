# GMI 对外展示官网 · 数据接入方案与业务需求

> 版本: v1.0 · 日期: 2026-08-24
> 范围: 对外官网（`/site` 首页 / 数据展示 / 解决方案 / 关于我们 / 联系咨询）如何接入真实数据、脱敏边界、字段映射与业务需求。

---

## 1. 背景与目标

GMI 数据平台原先仅提供后台管理系统（需登录）。现新增**对外展示官网**用于品牌与能力展示。
官网需展示平台真实数据以增强可信度，但**不得暴露任何敏感实体信息**（单位名称、人员姓名、联系方式、金额明细等）。

核心目标：
1. 官网在无登录状态下展示**平台级聚合统计**（真实、实时、脱敏）。
2. 所有展示数据均可追溯至数据库真实表，杜绝编造示例数据。
3. 对外页与后台管理系统视觉一致（浅色机构风 + 勃艮第红品牌色）。

---

## 2. 数据接入架构

```
前端(对外官网 /site/*)  --GET /api/v1/public/overview-->  后端 public 路由  --聚合查询-->  MySQL
        (siteApi.ts, 无 token, 无 401 跳转)                        (app/api/v1/public.py)
```

### 2.1 后端公开接口
- **路径**: `GET /api/v1/public/overview`
- **鉴权**: 无（独立 `public_router`，不经过 `get_current_user`）
- **返回**: 平台脱敏概览聚合
- **安全**: 仅返回聚合数字与省份级别分布，绝不返回单位名 / 人名 / 联系方式 / 金额。

### 2.2 前端调用
- `frontend/src/api/siteApi.ts`: 独立 axios 实例（不附加 JWT，响应拦截**不**在 401 时跳转登录页）。
- `fetchOverview()`: 调用接口，失败返回 `null`，前端降级为占位值（`—`），保证官网不空白。

### 2.3 降级策略
接口异常 / 超时 → 页面显示 `—` 或脱敏静态文案，不报错、不跳转登录。

---

## 3. 字段映射（真实数据源）

| 官网展示项 | 后端聚合字段 | 数据来源表 | 过滤条件 |
|---|---|---|---|
| 招投标线索量 | `totals.bid_notices` | `bid_notice` | `is_deleted=0` |
| 监测单位量 | `totals.companies` | `company` | `is_deleted=0` |
| 意向公告量 | `totals.intents` | `intent_notice` | `is_deleted=0` |
| 网页线索量 | `totals.web_clues` | `web_clue` | `is_deleted=0` |
| 关联人员量 | `totals.persons` | `person` | `is_deleted=0` |
| 项目量 | `totals.projects` | `project` | `is_deleted=0` |
| 地域 Top10 | `region_top[].province/count` | `company.province` ∪ `bid_notice.region` | 去重聚合，取前 10 |
| 类型构成 | `type_dist[]` | 上述各表 count | — |
| 月度趋势 | `monthly_trend[].month/count` | `web_clue.published_at` | 近 12 个月 |
| 覆盖省级区 | `province_count` | 省份去重 | — |

### 3.1 当前真实数据快照（2026-08-24）
- 招投标 147 · 单位 285 · 意向 3 · 网页线索 160 · 人员 127 · 项目 144
- 覆盖 46 个省级行政区；地域首位为四川（251 条）。
- 月度趋势显示 2026-08 采集量激增至 88 条（采集管线刚规模化运行）。

---

## 4. 脱敏边界（安全合规）

| 允许展示 | 禁止展示 |
|---|---|
| 平台级总量、聚合百分比 | 具体单位名称、统一社会信用代码 |
| 省级 / 地级市级别分布计数 | 单位联系方式、人员手机号 |
| 时间趋势（月粒度） | 中标金额、合同明细 |
| 行业 / 类型构成占比 | 可定位到个人的任职关系 |

> 公开接口在任何情况下不 join 敏感字段；如需下钻明细，必须引导用户登录后台。

---

## 5. 业务需求

### 5.1 功能需求
1. 官网 5 个页面在无登录状态下可访问，且展示真实聚合数据。
2. 每页提供**「管理后台」登录入口**（导航栏 + 页脚 + 登录页直达），便于内部人员与已注册客户进入系统。
3. 数据展示页 / 首页大屏随数据库更新而动态变化（接口实时查库，无需发版）。
4. 接口失败降级，保证官网可用性。

### 5.2 非功能需求
- 响应式：桌面 / 平板 / 移动端一致可用（导航汉堡菜单、网格降列）。
- 性能：echarts 按需分包；公开接口仅做聚合 count，毫秒级返回。
- 一致性：对外页配色与后台管理系统统一（勃艮第红 `#a51c30` + 暗金标签 + 浅色留白）。

### 5.3 后续可扩展
- 增加「行业分布」「热门关键词云」等聚合维度（仍脱敏）。
- 公开接口增加简单频次限制（防刷）。
- 如需展示案例，须经客户授权后单独维护「客户案例」表，与公开统计解耦。

---

## 6. 改动清单

| 文件 | 改动 |
|---|---|
| `backend/app/api/v1/public.py` | 新增公开聚合接口（无鉴权、脱敏） |
| `backend/app/main.py` | 注册 `public_router`，prefix `/api/v1` |
| `frontend/src/api/siteApi.ts` | 新增官网专用 axios 实例 + `fetchOverview` |
| `frontend/src/styles/site.css` | 重写为浅色机构风（与后台统一） |
| `frontend/src/components/site/SiteLayout.vue` | 浅色导航/页脚 + 管理后台入口 |
| `frontend/src/views/site/Home.vue` | 接入真实数据 + 浅色大屏 |
| `frontend/src/views/site/Showcase.vue` | 接入真实数据 + 浅色 |
| `frontend/src/views/site/Solutions.vue` / `About.vue` / `Contact.vue` | 浅色适配 |
| `frontend/src/router/index.ts` | `/site/*` 路由 `meta.public` 放行 |

> 注：后端为镜像构建部署，`public.py` 等改动需 `docker compose build backend` 后生效。
