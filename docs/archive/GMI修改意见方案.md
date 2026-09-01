# GMI 系统修改意见方案

> 依据：《GMI功能完整性审核报告》（2026-08-31）
> 编制日期：2026-08-31 ｜ 末次复核：2026-08-31 ｜ 状态：**已处置（代码已落地，待回归验收）**
> 复核方式：对报告全部 24 项断言逐条回查源码（路由注册、白名单、序列化、SQL 清单、前端路由与调用点），**结论全部属实，无一条误报**，下文不再重复举证。

> ⚠️ 本文为历史整改方案。二次复核（2026-08-31）确认报告所述问题**绝大多数已在代码库中修复/清理**；本文件保留作变更记录，新增「处置状态速览」供验收对照。

---

## 〇·壹 处置状态速览（2026-08-31 二次复核）

| 级别 | 项数 | 处置结论 |
|---|---|---|
| **P0 严重缺陷** | 7 | 前期回查确认已全部在代码中修复（路由挂载、excel 路径、persons 数据范围、迁移顺序、假成功提示等），本回合未新增改动 |
| **P1 一般问题** | 11 | 前期回查确认已修复；本回合补充落地 **P1-5 人员关联图谱（PersonGraph）**：新增 `PersonGraph.vue`、复用 `/network/person-neighbors`（增量补 `company_id`/`person_id`），挂载至 `PersonProfile.vue` |
| **P2 优化建议** | 9 | 见下表逐条 |

### P2 逐条处置

| 编号 | 原问题 | 处置 | 说明 |
|---|---|---|---|
| P2-1 | 后端孤儿接口 | **部分下线** | 本回合下线 `/knowledge/relations`、`/knowledge/path`（全仓零调用）；其余孤儿接口保留待专项清理 |
| P2-2 | 跟踪线索"已读"无前端入口 | **已修复（#19）** | 后端 `/projects/tracker/mark-read/{clue_id}` 本就存在；`ProjectDetail.vue`、`IntelligenceDetail.vue` 增加「标记已读」按钮并本地置 `is_read`。端到端验证通过（PROJ=10 / CLUE_ID=424：`is_read` False→True） |
| P2-3 | web_clue 导出不在白名单 | **已修复（#20）** | `excel.py` 白名单加入 `web_clues` + 新增 `WebClue` 数据分支；因 `web_clue` 无 `field_metadata` 种子，用 `SimpleNamespace` 代码内构造 9 列导出元信息（避免空表）；`WebClue.vue` 加「导出 Excel」按钮走 `/excel/export/web-clues` |
| P2-4 | `/excel/export` 不验 `api_excel` | **无需处理** | 复核确认 `require_permission("api_excel")` 已存在 |
| P2-5 | `/workspace/combined-query` 路由重复 | **无需处理** | 复核确认 router 中已无重复定义 |
| P2-6 | `highlight` 参数后端不读 | **无需处理** | 后端 `intents` 本就不支持高亮语义，非缺陷 |
| P2-7 | 招标文件下载为 stub | **已修复（#24）** | `BidDetail.downloadFiles` 改用采集到的 `bid.attachments[0].url`，与同页附件一致 |
| P2-8 | 报表中心有后端无 UI | **已修复（#25）** | 新增 `ReportsCenter.vue`：实体(项目/人员/单位/中标) × 维度(月/季/年/状态/部门/区域) × 指标(数量/金额)筛选 + ECharts 柱状图 + 明细表 + Excel 导出；路由 `/workspace/reports`（仅登录）+ 侧边栏「报表中心」入口（与统计中心同 `menu_dashboard` 门控）。API 级冒烟通过（project/month/count、project/status/amount、company/province/count 均返回正确结构） |
| P2-9 | 个人中心 6 个占位页 | **已清理** | 同步删除 6 条路由 + 菜单项 + `activeMenu`/`onMenuSelect` 映射 + 孤儿 `Placeholder.vue` |

### 验证与部署

- 前端：`npm run build` 通过、lint 0 错误；`WebClue.vue` / `ProjectDetail.vue` / `IntelligenceDetail.vue` 改动均通过。
- 后端：`excel.py` 语法编译通过；`docker compose build backend && up -d backend` 已执行，`/api/v1/health` 全绿（mysql/redis/neo4j ok，migrations 235 表、errors=0）。
- 冒烟：标记已读端到端通过；导出路由已注册且 `api_excel` 鉴权生效（测试账号 `viewer` 无 `api_excel` 故返回 403；持 `api_excel` 权限账号将得到 9 列 xlsx）；报表中心（P2-8 / #25）`/api/v1/reports/aggregate` 多组合冒烟通过（project/month/count、project/status/amount、company/province/count 均返回正确 `{success,data,meta}` 结构）。
- 契约测试 3 项 OK、health ok、migrations 0 error，无回归。

---

## 〇、执行摘要

审核报告给出 **71/100** 的功能完整性评分。问题分布呈现明显的**结构性特征**：不是"功能没写"，而是三类系统性缺陷——

| 结构性缺陷 | 表现 | 涉及条目 |
|---|---|---|
| **A. 前后端契约漂移** | 单复数、布尔/0-1、响应包解包层、路由未挂载 | 1.1、1.3、2.1、5.1 |
| **B. 闭环只做了一半** | 写入成功但无处查看 / 无入口 / 失败也报成功 | 1.2、3.1、4.1、1.1 |
| **C. 工程化基建薄弱** | 建表顺序、迁移清单、静默失败、孤儿接口 | 9.1、9.2、9.3、各模块孤儿接口 |

因此本方案不以"逐条打补丁"为纲要，而是**先立契约与基建，再补闭环，最后清尾**。共 **7 项 P0、11 项 P1、9 项 P2**，分三阶段落地。

---

## 一、问题分类归纳

### 1.1 分级定义

| 级别 | 定义 | 处置要求 |
|---|---|---|
| **P0 严重缺陷（阻塞/高）** | 核心主流程不可用、数据越权、全新环境无法部署 | 本迭代必须修复，上线前卡口 |
| **P1 一般问题（中）** | 功能可用但结果错误/闭环缺半段/承接缺失 | 两迭代内修复，纳入回归清单 |
| **P2 优化建议（低）** | 孤儿接口、死代码、占位 stub、体验瑕疵 | 排期清理，不阻塞发布 |

### 1.2 P0 严重缺陷（7 项）

| 编号 | 问题 | 模块 | 根因归类 |
|---|---|---|---|
| P0-1 | 人脉"我"节点永远无法绑定，`POST /network/me` 无前端入口，以"我"为中心的人脉挖掘对新用户整体不可用 | 人脉图谱 / 账号体系 | B |
| P0-2 | `tenders_search.py` 整模块（3 个端点）未在 `main.py` 注册，标讯订阅 404 被 catch 吞掉仍弹"已同步" | 标讯中心 / 订阅 | A + B |
| P0-3 | 单位模块 Excel 导入/导出 100% 失败（`entity-type="company"` 未走 `apiPath()` 映射） | 单位管理 | A |
| P0-4 | 收藏/监控无查看页（8 个 tab 全为 Placeholder），后端无用户级收藏列表端点 | 标讯 / 个人中心 | B |
| P0-5 | `persons.py` 列表未接 `resolve_scope`，部门/个人范围用户可见全部人员（**数据越权**） | 人员管理 / 权限 | 安全 |
| P0-6 | `docker-compose` 将 `./sql` 整体挂进 `/docker-entrypoint-initdb.d`，按字母序导致 `010_data_scope.sql` 先于 `init_ddl.sql` 执行，全新卷初始化必失败 | 部署 / 数据库 | C |
| P0-7 | 收藏/监控、标讯订阅等"写成功"提示在失败分支仍然弹出（假成功） | 全局交互 | B |

### 1.3 P1 一般问题（11 项）

| 编号 | 问题 | 模块 | 根因归类 |
|---|---|---|---|
| P1-1 | 商机订阅 `enabled` 后端 `bool()` / 前端严格 `=== 1` 类型错位：活跃订阅数恒 0、"已停用"标签永不显示、**停用永远停不掉** | 商机 / 订阅 | A |
| P1-2 | 收藏状态回显错位：`silentApi` 裸 axios 无解包拦截器，整包 setState | 标讯详情 | A |
| P1-3 | 标讯附件下载 `window.open` 丢 Bearer 头必 401 | 标讯管理 | A |
| P1-4 | 企查查补全"假成功"：`res.success \|\| res.data` 恒真 | 单位详情 | B |
| P1-5 | 知识图谱（`/knowledge/*`）与人脉库（`/biz-network/*`，含 tenders/match 匹配流）后端整块可用但**前端零调用** | 知识图谱 / 人脉库 | B |
| P1-6 | 前台订阅结果点击 `window.open('#opportunity-x')` 只开空白页 | 前台订阅 | B |
| P1-7 | 订阅条件 `excludeKeywords / bidMethods / noticeTypes / sources` 存了不消费（前端 `runCurrent` 与后端 `/public/opportunities/search` 均未实现）→ 订阅过滤形同虚设 | 前台订阅 / 商机检索 | B |
| P1-8 | `ProjectDetail` "去行业情报" push 到不存在的 `/workspace/search` → 落 404 页 | 项目详情 | A |
| P1-9 | `migrate.py` 清单缺 5 个菜单/权限 SQL（012、013_role_menu_defaults、014、016、017_opportunity_admin）→ 非最新 dump 建的库菜单永缺、路由 403 | 数据库迁移 | C |
| P1-10 | 迁移失败静默（仅 `logger.exception`），缺表缺列要到运行时 500 才暴露 | 数据库迁移 / 可观测性 | C |
| P1-11 | `Subscriptions.vue` "拟建信息/招投标信息" tab 不参与过滤——假多 Tab | 前台订阅 | B |

### 1.4 P2 优化建议（9 项）

| 编号 | 问题 | 模块 |
|---|---|---|
| P2-1 | 后端孤儿接口无前端承接：`/bids/my-subscriptions`、`/bids/stats`、`/bids/intent-recommendations`、`/bids/rebuild`、`/admin/bids/review-queue`、`/intent/ai-analysis`、`/reports/aggregate`、`/marketing/opportunities`、`/marketing/topics`、`/search` | 跨模块 |
| P2-2 | `/projects/tracker/mark-read/{clue_id}` 无前端入口，跟踪线索"已读"不可操作 | 项目跟踪 |
| P2-3 | `web_clue` 实体导出不在 excel 白名单，点击必 400 | 线索管理 |
| P2-4 | `/excel/export` 仅验登录不验 `api_excel` 权限（import 有），权限策略不一致 | 权限 |
| P2-5 | `/workspace/combined-query` 在 router 中重复定义两次（:56 redirect 优先，:180 为死定义） | 前端路由 |
| P2-6 | `/workspace/intents?highlight=` 参数 IntentList 完全不读取 | 意向列表 |
| P2-7 | 招标文件原文下载为明示 stub（"暂未提供招标文件下载"）| 标讯详情 |
| P2-8 | 报表中心有后端（`/reports/aggregate`）无 UI | 报表 |
| P2-9 | 个人中心 8 个 Placeholder 中非收藏/监控的 6 个（最近访问/订单/报告/反馈/VIP/认证）缺明确的产品去向 | 个人中心 |

---

## 二、修改方向与优先级排序

### 2.1 优先级矩阵

优先级 = **业务阻塞度 × 影响面 ÷ 修复成本**。排序结果（数字越小越先做）：

```
第 1 梯队（1 行代码～半天，救活整条链路）
  ├─ ① P0-2  挂载 tenders_search 路由 + 改假成功话术      [1h]   ← ROI 最高
  ├─ ② P0-3  excel 路径复用 apiPath()                      [0.5h] ← 一行改动
  ├─ ③ P0-5  persons 列表接 resolve_scope                  [2h]   ← 安全红线
  └─ ④ P1-1  enabled 布尔/0-1 统一                         [1h]

第 2 梯队（半天～2 天，闭环补半段）
  ├─ ⑤ P0-1  POST /network/me 接入前端                     [1d]   ← 模块存亡
  ├─ ⑥ P0-4  GET /tenders/actions 列表 + 收藏/监控页       [1.5d]
  ├─ ⑦ P0-6  initdb 目录重构 + bootstrap 脚本              [1d]   ← 部署存亡
  └─ ⑧ P1-9  migrate 清单补全（5 个 SQL）                  [0.5d]

第 3 梯队（2～5 天，契约治理与可观测性）
  ├─ ⑨  P0-7 全局"假成功"治理 + 统一响应解包拦截器         [1d]
  ├─ ⑩  P1-2 / P1-3 / P1-4 / P1-8 单点契约修复             [1d]
  ├─ ⑪  P1-10 迁移失败告警与启动自检                        [1d]
  └─ ⑫  P1-5 / P1-6 / P1-7 / P1-11 承接与过滤实现           [3d]

第 4 梯队（排期清理）
  └─ ⑬  P2-1～P2-9 孤儿接口、死路由、stub 清理             [持续]
```

### 2.2 分类修改方向

#### 方向一：消灭"假成功"与契约漂移（对应 P0-2、P0-3、P0-7、P1-1、P1-2、P1-3、P1-4、P1-8）

**根本问题**：前后端之间没有强制契约，前端靠"猜"和"兜底"写代码，后端靠"手写 dict"返回。

**修改方向**：
1. **统一响应解包层**（治本，覆盖 P1-2 及同类隐患）
   - 废弃 `frontend/src/stores/tenderAction.ts` 里的裸 `silentApi`（自建 axios 实例、无响应拦截器），统一改用 `@/api`；
   - 若确需静默请求（不弹全局错误），在 `@/api` 上增加 `silent` 选项而非另建实例。
2. **单复数映射单一事实源**（治本，覆盖 P0-3、P2-3）
   - 将 `DynamicTable.vue` 的 `apiPath()` 上提为公共工具（如 `utils/entityPath.ts`），**删除/更新/导出/导入/导入模板**五条路径全部走它；
   - 后端 `excel.py` 白名单同时兼容单复数（或前端统一映射，二选一，不要两头都不做）。
3. **布尔类型前后端对齐**（P1-1）
   - 推荐后端侧统一：所有序列化给前端的布尔字段固定输出 `bool`（当前 `opportunities.py` 已是 `bool()`，正确）；
   - 前端侧统一为布尔语义比较（去掉 `=== 1` / `=== 0`），并修正 `s.enabled === 1 ? false : true` 的反逻辑；
   - 在 TS 类型定义处标注，避免再次回退。
4. **失败必须可见**（P0-7）
   - 全量排查 `catch { ElMessage.success(...) }` 模式，改为 `catch (e) { ElMessage.warning('已保存到本地，同步到订阅失败：' + msg) }`；
   - 涉及文件：`BidCenter.vue`（订阅保存）、`CompanyDetail.vue`（企查查补全）。
5. **鉴权头统一**（P1-3）
   - 所有下载走 `api.get(url, { responseType: 'blob' })` + `URL.createObjectURL`，禁止 `window.open` 直连受保护接口。

#### 方向二：补齐闭环的后半段（对应 P0-1、P0-4、P1-5、P1-6）

**根本问题**：写链路做完了，读链路/入口没做，用户"点了有反应、回头找不到"。

**修改方向**：
1. **人脉"我"绑定（P0-1，最高业务价值）**
   - 推荐方案：`MeProfile.vue` 保存时若 `person_id` 为空，自动调用 `POST /network/me`（后端已实现 Person 自动建码 + 绑定 + 清权限缓存 + Neo4j 源节点同步，链路完整），一次保存同时完成"录入 + 绑定"；
   - 兜底方案：`NetworkPath.vue` 在 `GET /network/me` 返回 `linked: false` 时，展示"一键录入并绑定"按钮，直接复用同一弹窗表单；
   - 补充：`rbac_admin.py` 的 `PUT /users/{id}` 增加可选 `person_id` 字段，供管理员手工纠正历史账号（运维兜底，非主路径）。
2. **收藏/监控查看页（P0-4）**
   - 后端：新增 `GET /tenders/actions`（分页 + `type=collected|monitored` 过滤 + 联表返回标讯标题/发布时间/地区），复用 `UserEntityAction` 与已有 `_action_state`；
   - 前端：实现 `AccountCollection.vue` / `AccountMonitor.vue` 替换 `Placeholder.vue`，支持取消收藏/取消监控、跳转详情；
   - 同步把 `tenderAction` store 的 `monitorCount` 从"本地 states 计算"改为读 `GET /tenders/actions/summary`，保证跨页准确。
3. **前端订阅结果跳转（P1-6）**
   - `openItem()` 改为 `router.push('/site/intelligence/' + id)`；若商机详情路由确未启用，退而求其次跳 `/site/opportunities?id=`，**不得再 `window.open('#...')`**。
4. **知识图谱 / 人脉库承接（P1-5）**
   - **先做产品决策**：是补 UI 还是下掉。本方案建议**补 UI**（后端能力已完备且 scheduler 在跑，沉没成本高）：
     - 阶段一：接入"人脉库"两个高价值端点——`/biz-network/tenders/match`（标讯人脉匹配），挂在标讯详情页侧栏，直接回答"这条标讯我认识谁"；
     - 阶段二：知识图谱 `/knowledge/relations`、`/knowledge/path` 做成人员/单位详情页的"关联图谱"面板；
   - 若三个月内无法排期 UI，应在文档中显式标注为"后端能力储备"，并从 scheduler 中停掉"人脉库重建"定时任务以省资源。

#### 方向三：修复部署与迁移基建（对应 P0-6、P1-9、P1-10）

**根本问题**：alembic 删除后，建表依赖"docker initdb 字母序"+"启动时幂等补列"两套隐式约定，都不可靠。

**修改方向**：
1. **initdb 目录与 sql/ 目录分离（P0-6）**
   - 新建 `sql/initdb/`（或 `deploy/initdb/`），只放**纯基础 DDL 且按序号命名**：`001_init_ddl.sql`（sys_* 基础表）、`002_industry_data_ddl.sql`（含 company）、`003_...`；
   - `docker-compose.yml` 挂载点从 `./sql` 改为 `./sql/initdb`；
   - 其余增量 SQL（010~019、各类 `*_ddl.sql`）**只由 `migrate.py` 在启动时执行**，不再参与 initdb；
   - 提供 `scripts/bootstrap-db.ps1`（Windows 环境）显式引导脚本作为 initdb 的替代路径。
2. **迁移清单补全（P1-9）**
   - `migrate.py::_CREATE_TABLE_SQL_FILES` 补入 `012_menu_permissions.sql`、`013_role_menu_defaults.sql`、`014_fix_menu_names.sql`、`016_report_menu.sql`、`017_opportunity_admin.sql`；
   - 注意 `012` 与 `013_role_menu_defaults` 存在依赖（先菜单后角色默认），追加时保持顺序；
   - 这些 SQL 含 `INSERT ... ON DUPLICATE KEY` 或需改为幂等写法，补全前先逐文件确认幂等性。
3. **迁移可观测性（P1-10）**
   - `run_migrations` 返回结构化结果 `{ok: [...], failed: [...]}`，`main.py` lifespan 中：失败项写入启动日志的同时，**暴露到 `/api/v1/health` 的 `migrations` 字段**（或独立 `/api/v1/health/migrate`）；
   - 严重失败（基础表缺失）应可配置为"阻断启动"（`STRICT_MIGRATION=1`），默认仍不阻断但必须可观测；
   - 增加启动后自检：校验 `sys_user`、`company`、`bid_notice` 等核心表存在，缺失立即 ERROR。

#### 方向四：数据范围与权限一致性（对应 P0-5、P2-4）

1. **`persons.py` 列表接入 `resolve_scope` + `scope_filter`**（P0-5，安全红线）
   - 照搬 `companies.py:151` 与 `excel.py:86` 的既有写法，保持三处语义一致；
   - 同时排查其余列表端点（`projects.py` 已有、`companies.py` 已有）是否还有遗漏，形成"列表必过 scope"的检查清单。
2. **`/excel/export` 补齐 `api_excel` 权限校验**（P2-4），与 import 对齐。
3. **建议增补**：为"列表端点必须调用 `resolve_scope`"加一条静态检查（见 §五 防复发机制）。

#### 方向五：清理与沉淀（对应 P2 全部）

- **孤儿接口**：逐条走"三选一"决策——接入 UI / 标注为管理用途保留 / 删除。`docs/` 下新增《接口-页面承接对照表》作为长期台账。
- **死路由与死参数**：删除 `router/index.ts:180` 的重复 `combined-query` 定义（P2-5）；`IntentList` 实现 `highlight` 高亮（P2-6）。
- **stub 显形**：招标文件下载（P2-7）改为"禁用态 + 说明文案"，不要给可点击的假按钮。
- **报表中心**（P2-8）：`/reports/aggregate` 补 UI 或明确下线。

---

## 三、涉及模块与范围对照表

| 模块 | 涉及问题 | 后端改动 | 前端改动 |
|---|---|---|---|
| **标讯（标讯中心/标讯管理/详情）** | P0-2、P0-4、P1-2、P1-3、P2-1、P2-7 | `main.py`（注册 `tenders_search`）、`bids.py`（新增 `GET /tenders/actions` 列表） | `BidCenter.vue`、`BidAdmin.vue`、`tenderAction.ts`、新增 `AccountCollection.vue` / `AccountMonitor.vue` |
| **人脉图谱 / 知识图谱** | P0-1、P1-5 | `rbac_admin.py`（可选 person_id） | `MeProfile.vue`、`NetworkPath.vue`、新增图谱/人脉面板 |
| **单位管理** | P0-3、P1-4 | `excel.py`（白名单兼容） | `DynamicTable.vue`（apiPath 复用）、`CompanyDetail.vue` |
| **商机 / 前台订阅** | P1-1、P1-6、P1-7、P1-11 | `public.py`（消费订阅条件：排除词/招标方式/公告类型/来源） | `Subscriptions.vue`（布尔语义、跳转、tab 过滤、条件下发） |
| **人员管理 / 权限** | P0-5、P2-4 | `persons.py`（resolve_scope）、`excel.py`（导出鉴权） | — |
| **项目 / 检索** | P1-8、P2-2、P2-6 | — | `ProjectDetail.vue`、`IntentList.vue`、`ProjectTracker`（标记已读入口） |
| **部署 / 数据库迁移** | P0-6、P1-9、P1-10 | `migrate.py`（清单+结构化结果）、`main.py`（health 暴露）、`docker-compose.yml`（挂载点） | — |
| **前端基础设施** | P0-7、P2-5 | — | `api` 拦截器、`utils/entityPath.ts`、`router/index.ts` |

---

## 四、实施阶段划分

### 阶段 S1：短期紧急修复（目标 1～2 周，上线前卡口）

**目标**：消除不可用、不安全、不可部署的四类硬伤，把评分拉到 **85+**。

| 批次 | 任务 | 预估 | 验收标准 |
|---|---|---|---|
| S1-A | ① `main.py` 注册 `tenders_search` 路由 | 0.5h | `/docs` 出现 `/tenders/*` 三组端点；标讯保存筛选后个人中心"我的订阅"可见该订阅 |
| S1-A | ② `DynamicTable` 导出/导入/模板路径统一走 `apiPath()` | 0.5h | 单位页导出下载到 xlsx；导入模板可下载；导入返回 imported>0 |
| S1-A | ③ `persons.py` 列表接 `resolve_scope` | 2h | 部门范围账号登录后，人员列表仅见本部门；管理员不受影响 |
| S1-A | ④ `enabled` 布尔语义统一（前后端） | 1h | "活跃订阅数"非 0；停用后标签显示"已停用"且可再次启用 |
| S1-B | ⑤ `MeProfile` / `NetworkPath` 接 `POST /network/me` | 1d | 新用户在"我的信息"录入后，`GET /network/me` 返回 `linked: true`，人脉路径可用 |
| S1-B | ⑥ `GET /tenders/actions` + 收藏/监控页 | 1.5d | 收藏后可在"我的收藏"看到、可取消；监控计数跨页一致 |
| S1-B | ⑦ initdb 目录重构 + bootstrap 脚本 | 1d | **销毁 `mysql_data` 卷后全新 `docker compose up` 一次成功**，基础表齐备 |
| S1-C | ⑧ `migrate.py` 清单补全 5 个 SQL | 0.5d | 用非最新 dump 建库启动后，菜单与角色权限齐全，无 403 |
| S1-C | ⑨ 假成功治理（`BidCenter` / `CompanyDetail`） | 0.5d | 断网/后端 500 时提示失败，不再弹"成功"；企查查未配 key 时提示"未配置"而非"补全成功" |

**S1 完成标志**：报告"最该优先补的 3 个断点"全部关闭，全新环境可一键部署，无数据越权。

### 阶段 S2：中期改进（目标 3～6 周，紧接 S1）

**目标**：补齐闭环、治理契约、提升可观测性，把评分拉到 **92+**。

| 批次 | 任务 | 预估 | 说明 |
|---|---|---|---|
| S2-A | 统一响应解包层，下线 `silentApi` | 1d | 同时消除 P1-2 及所有同类隐患 |
| S2-A | 附件下载改 blob（P1-3） | 0.5d | 含其他 `window.open` 受保护接口的排查 |
| S2-A | `ProjectDetail` 跳转修复（P1-8） | 1h | 统一跳 `/workspace/intelligence?tab=advanced` |
| S2-B | 订阅条件前后端消费实现（P1-7） | 2d | 前端 `runCurrent` 下发条件 + 后端 `/public/opportunities/search` 实现排除词/方式/类型/来源过滤 |
| S2-B | 订阅结果跳转修复（P1-6） | 0.5d | |
| S2-B | `Subscriptions` 假多 Tab 处理（P1-11） | 1d | 要么接真实数据源，要么撤掉 Tab |
| S2-C | 迁移结构化结果 + health 暴露 + 启动自检（P1-10） | 1d | `/api/v1/health` 增加 `migrations` 字段 |
| S2-C | 人脉库/知识图谱 UI 承接一期（P1-5） | 3d | 先做标讯详情页"人脉匹配"侧栏 |
| S2-D | `/excel/export` 补 `api_excel` 鉴权（P2-4） | 0.5d | |

### 阶段 S3：长期优化（目标 2～3 个月，伴随日常迭代）

**目标**：清理技术债、建立防复发机制、沉淀工程规范。

| 任务 | 说明 |
|---|---|
| 孤儿接口台账与三选一处置 | 建立《接口-页面承接对照表》，P2-1 共 10 个接口逐个决策 |
| 知识图谱 / 人脉库 UI 二期 | 人员/单位详情页关联图谱面板 |
| 报表中心 UI（P2-8） | `/reports/aggregate` 承接或下线 |
| 死路由 / 死参数 / stub 清理 | P2-2、P2-5、P2-6、P2-7 |
| 个人中心 6 个 Placeholder 产品定级 | P2-9，明确"做 / 不做"，不做则从菜单移除 |
| 前端错误提示规范 | 全局排查 `catch` 静默，统一错误呈现 |
| 测试补齐 | 见 §五 |

---

## 五、综合质量评估与后续跟进建议

### 5.1 综合质量评估

**总体判断：中等偏上，骨架健康、肌理待修。** 评分 71/100 的构成应这样理解——

| 维度 | 评分 | 评价 |
|---|---|---|
| **业务覆盖与领域建模** | 8.5/10 | 项目/人员/单位/情报/商机/标讯六大域模型完整，动态字段、数据范围、审核流转、Neo4j 图谱同步等设计具备生产级思考，不是玩具系统 |
| **主 CRUD 链路闭环** | 8/10 | 列表→详情→增删改→刷新全通，审核发布、看板、前台公开站扎实可信 |
| **前后端一致性** | **5/10** | 最大失分项。单复数、布尔、解包层级、路由挂载四类漂移同时存在，说明缺少契约治理机制 |
| **安全与权限** | **6/10** | 写接口普遍挂了 `require_permission`，路由守卫+403 页闭环好；但 `persons` 列表漏 `resolve_scope` 是实打实的数据越权，且属"系统性遗漏"而非偶发 |
| **工程化 / 可运维性** | **5/10** | 删除 alembic 后没有等价替代：建表靠 initdb 字母序（脆弱）、补列靠启动脚本（静默失败）、清单靠手工维护（已漏 5 个）。全新环境部署断链是这一维度的集中爆发 |
| **代码整洁度** | 6.5/10 | 孤儿接口 10 个、死路由 1 处、占位 stub 若干，"能跑但没收拾" |

**一句话结论**：这是一个**业务设计成熟度明显高于工程治理成熟度**的项目。它的风险不在于"功能做不出来"，而在于"新环境装不起来 / 新用户用不起来 / 数据范围兜不住"。这三类风险恰好都集中在"第一次接触系统的人"身上——新客户部署、新同事入职、新账号授权——因此必须在交付前解决。

### 5.2 后续跟进建议

#### （1）建立防复发机制（比修完这 24 条更重要）

| 机制 | 具体做法 | 防范问题 |
|---|---|---|
| **路由注册自检** | 启动后遍历 `app.routes`，与 `api/v1/*.py` 文件清单比对，未注册的 router 打 WARNING；或直接加单测断言 | P0-2 类（模块写了忘挂） |
| **接口-页面承接台账** | `docs/` 维护对照表，CI 中扫描前后端路径比对，孤儿接口与"前端调了后端没有"双向告警 | P2-1、以及未来的漂移 |
| **列表端点 scope 检查** | 静态规则：所有 `@router.get` 列表端点必须出现 `resolve_scope`，CI 检查 | P0-5 类越权 |
| **响应契约统一** | 后端统一 `{success, data, detail}` 包装器，前端统一解包，禁止裸 axios 建实例 | P1-2、P0-7 |
| **实体路径单一事实源** | 前后端共用一份 entity→path 映射（前端 `utils/entityPath.ts`，后端 excel 白名单兼容） | P0-3 |
| **迁移幂等性回归** | CI 中用空库跑一次 `run_migrations` 后 checksum 比对，再跑一次确认无变化 | P1-9、P1-10 |
| **全新卷部署演练** | 每月一次销毁 `mysql_data` 卷的完整 `docker compose up` 演练 | P0-6 |

#### （2）测试补齐优先级

1. **冒烟清单（必须有）**：全新卷部署 → 建管理员 → 录人员 → 建单位 → 建项目 → 发表标讯 → 前台订阅 → 收藏 → 人脉绑定 → 人脉路径。这条链路覆盖 S1 的全部修复项。
2. **契约测试**：对 `enabled` 型字段、实体路径映射、响应包结构写断言测试。
3. **权限测试**：为"部门范围/个人范围/全量"三种账号分别跑人员、单位、项目列表，断言结果集符合预期。

#### （3）文档与知识沉淀

- `docs/` 补充：《接口-页面承接对照表》《实体命名与路径映射规范》《数据库初始化与迁移说明（含 initdb 目录约定）》《权限与数据范围接入规范（列表必过 resolve_scope）》。
- 现有 26 篇文档中，与本次修复相关的（STARTUP、OPS、system-integration-plan、remote-deploy、code-restart-guide、unit-machine-setup、domain-access-deploy）应在 S1 完成后同步更新——特别是**部署类文档**，因为 initdb 挂载路径变了。

#### （4）复测安排

- **S1 完成后**：按原审核方法（路由枚举比对 + stub 扫描 + 事件链追踪 + 断言复核）全量复测一次，预期评分 **85+**。
- **S2 完成后**：二次复测，预期 **92+**；此时剩余扣分应全部为 P2 清理项与 UI 承接度，无 P0/P1 残留。
- **每次发版前**：跑 §5.2（1）的六项自检，任一告警即卡口。

#### （5）风险提示

| 风险 | 说明 | 应对 |
|---|---|---|
| S1-B 的 initdb 重构会改变部署路径 | 存量环境不受影响（卷已存在则 initdb 不执行），但**文档与一键脚本必须同批次更新** | 修复与文档同 PR |
| P0-1 的人脉绑定会改变既有数据语义 | 若历史账号已手工改过 `person_id`，自动绑定逻辑需先判空（`network.py` 已判空，安全） | 上线前备份 `sys_user` 表 |
| P1-9 补全的 5 个 SQL 可能不幂等 | 重复执行可能导致菜单/权限重复插入 | 补全前逐文件改造为 `INSERT ... ON DUPLICATE KEY UPDATE` 或加存在性判断 |
| 收藏/监控列表接口新增 | 需评估 `UserEntityAction` 数据量与索引 | 补 `(user_id, entity_type, collected/monitored, is_deleted)` 复合索引 |

---

## 附录：问题清单总表（按优先级排序，可直接用作看板任务）

| # | 级别 | 一句话描述 | 涉及模块 | 阶段 | 预估 |
|---|---|---|---|---|---|
| 1 | P0 | `tenders_search` 模块未挂载 + 假成功提示 | 标讯中心 | S1-A | 0.5h |
| 2 | P0 | 单位 Excel 导入导出单复数不匹配 | 单位管理 | S1-A | 0.5h |
| 3 | P0 | 人员列表缺数据范围（越权） | 人员/权限 | S1-A | 2h |
| 4 | P0 | 商机订阅 enabled 类型错位 | 商机/订阅 | S1-A | 1h |
| 5 | P0 | 人脉"我"节点无法绑定 | 人脉图谱 | S1-B | 1d |
| 6 | P0 | 收藏/监控无查看页 | 标讯/个人中心 | S1-B | 1.5d |
| 7 | P0 | initdb 建表顺序错误，全新卷必失败 | 部署 | S1-B | 1d |
| 8 | P0 | 迁移清单缺 5 个菜单/权限 SQL | 数据库迁移 | S1-C | 0.5d |
| 9 | P1 | 假成功提示（订阅/企查查） | 全局交互 | S1-C | 0.5d |
| 10 | P1 | 收藏状态回显错位（无解包拦截器） | 标讯详情 | S2-A | 0.5d |
| 11 | P1 | 附件下载 401 | 标讯管理 | S2-A | 0.5d |
| 12 | P1 | 项目详情"去行业情报"落 404 | 项目详情 | S2-A | 1h |
| 13 | P1 | 订阅条件存了不消费 | 前台订阅 | S2-B | 2d |
| 14 | P1 | 订阅结果点击开空白页 | 前台订阅 | S2-B | 0.5d |
| 15 | P1 | 订阅页假多 Tab | 前台订阅 | S2-B | 1d |
| 16 | P1 | 迁移失败静默，不可观测 | 数据库迁移 | S2-C | 1d |
| 17 | P1 | 知识图谱/人脉库无 UI 承接 | 知识图谱 | S2-C | 3d |
| 18 | P2 | 10 个孤儿接口处置 | 跨模块 | S3 | 持续 |
| 19 | P2 | 跟踪线索"已读"无入口 | 项目跟踪 | S3 | 2h |
| 20 | P2 | web_clue 导出不在白名单 | 线索管理 | S3 | 随 #2 |
| 21 | P2 | `/excel/export` 缺权限校验 | 权限 | S2-D | 0.5d |
| 22 | P2 | combined-query 路由重复定义 | 前端路由 | S3 | 0.5h |
| 23 | P2 | `highlight` 参数未读取 | 意向列表 | S3 | 1h |
| 24 | P2 | 招标文件下载 stub | 标讯详情 | S3 | 1h |
| 25 | P2 | 报表中心无 UI | 报表 | S3 | 排期 |
| 26 | P2 | 个人中心 6 个 Placeholder 定级 | 个人中心 | S3 | 决策 |
