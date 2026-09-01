# GMI 招投标情报与关系挖掘系统 — 功能完整性审核报告

审核日期：2026-08-31 ｜ 范围：backend/app/api/v1（46 个路由文件）+ frontend/src ｜ 方法：路由枚举比对 + stub 扫描 + 事件链追踪 + 关键断言逐条对码复核（未修改任何代码）

## 总体结论

主 CRUD 链路（项目/人员/单位/情报/商机 的列表→详情→增删改→刷新）整体闭环良好；前后端路径经全量比对，**除 1 处整模块未挂载外，不存在"前端在调、后端没实现"的路径**（后端反而存在多个无前端承接的孤儿接口）。真正的断链集中在：标讯订阅落库、人脉"我"的绑定、单位导入导出、收藏/监控查看页、以及 alembic 删除后的建表顺序缺陷。

---

## 1. 标讯模块

**1.1 标讯订阅不落库（假成功提示）**
- 【功能】标讯中心 → 保存筛选为订阅
- 【断点】frontend/src/views/workspace/BidCenter.vue:416 调 `POST /tenders/subscriptions`；backend/app/api/v1/tenders_search.py 整个模块（/tenders/search、/tenders/subscriptions GET+POST）**未在 main.py 注册**（main.py:154-196 无此 router，grep 全后端无引用）
- 【现象】请求 404 被 catch 吞掉，仍弹"筛选条件已保存，并已同步到我的订阅"，实际只写了 localStorage；个人中心订阅页永远看不到标讯订阅
- 【严重度】高
- 【修复方向】main.py 挂载 tenders_search 路由（或改调已有 /bids/my-subscriptions），并把 catch 里的"假成功"改为告警

**1.2 收藏/监控"我的"页全是占位**
- 【功能】前台收藏/监控 → 查看
- 【断点】写链路正常（frontend/src/stores/tenderAction.ts:46 ↔ backend bids.py:561-568 落 user_entity_action）；但 frontend/src/router/index.ts:360-367 的我的收藏/监控等 8 个 tab 全渲染 Placeholder.vue（"正在筹备中"），后端也只有计数接口（bids.py:547），无用户级收藏列表端点
- 【现象】收藏点了提示成功，但永远无处查看/管理
- 【严重度】高（闭环缺后半段）
- 【修复方向】后端补 `GET /tenders/actions` 列表接口 + 前端实现收藏/监控页替换占位

**1.3 收藏状态回显错位**
- 【功能】详情页收藏/监控按钮状态刷新
- 【断点】stores/tenderAction.ts:32-33 用裸 axios `silentApi`（无响应拦截器），把 `{success,data}` 外层整包 setState，键名对不上 `isMonitored/isCollected`
- 【现象】刷新后按钮态不随服务端真实状态恢复（靠详情页 initial 掩盖，跨页/汇总计数不准）
- 【严重度】中
- 【修复方向】改为 `response.data.data` 或给 silentApi 加解包拦截器

**1.4 标讯附件下载 401**
- 【功能】标讯管理 → 附件下载
- 【断点】frontend/src/views/workspace/BidAdmin.vue:966 用 `window.open('/api/v1/admin/bids/.../download')`，后端 bid_attachments.py:130 要求 Bearer 头（middleware/auth.py:14-23 只认 header）
- 【现象】点击下载 → 新标签 401/空白
- 【严重度】中
- 【修复方向】改 api.get responseType:'blob' 下载

**1.5 其他**
- 招标文件原文下载为明示 stub："暂未提供招标文件下载"（BidDetail.vue:516）— 低
- /bids/my-subscriptions、/bids/stats、/bids/intent-recommendations、/bids/rebuild、/admin/bids/review-queue 前端零调用（孤儿/未承接）— 低
- /projects/tracker/mark-read/{clue_id}（project_tracker.py:90）无前端入口，跟踪线索"已读"不可操作 — 低

## 2. 单位模块

**2.1 单位导出/导入 100% 失败**
- 【功能】单位列表 → Excel 导出/导入
- 【断点】CompanyList.vue:10 传 `entity-type="company"`（单数），DynamicTable.vue:578/732 原样拼 `/excel/export/company`、`/excel/import/company`；excel.py:57,142 白名单只有复数 `companies` → 必 400。apiPath 单复数映射（DynamicTable.vue:620）只用于删除/更新，没用于 excel 路径
- 【现象】单位页点导出/导入必报"不支持的导出/导入实体类型"
- 【严重度】高（单位模块数据维护主流程残缺）
- 【修复方向】excel 路径同样走 apiPath() 映射（顺带：web_clue 实体导出也不在支持名单，点击必 400 — 低）

**2.2 企查查补全"假成功"**
- 【功能】单位详情 → 企查查补全
- 【断点】后端未配置 QCC key 时返回 `{success:false, data:非空}`（companies.py:308-310），前端 `if (res.success || res.data)`（CompanyDetail.vue:1365）恒真
- 【现象】弹"企查查数据补全成功"但什么都没写入；免费补全 enrich-free 链路真实可用
- 【严重度】中
- 【修复方向】判 `res.success === true`

## 3. 人脉图谱（阻塞性断链）

**3.1 "我"节点永远无法绑定**
- 【功能】人脉路径 / 以我为中心的图谱
- 【断点】唯一写 `sys_user.person_id` 的入口是 `POST /network/me`（network.py:118-174），但前端只 GET（NetworkPath.vue:273）；PUT /me/profile（rbac.py:120-141）只改显示名/邮箱/手机不建 Person；rbac_admin PUT /users/{id}（rbac_admin.py:298）也不含 person_id
- 【现象】NetworkPath 提示"请先在「我的信息」中录入"——但用户在 MeProfile 录入后依然未关联，人脉路径对所有新用户不可用（只能手工改库）
- 【严重度】阻塞（模块核心主流程不可用）
- 【修复方向】MeProfile 或 NetworkPath 接上 `POST /network/me`，或让 /me/profile 支持绑定人员

**3.2 知识图谱/人脉库后端整块无 UI**
- 【断点】backend knowledge.py（/knowledge/extract、ingest、relations、region、path）与 business_network.py（/biz-network/*，含 tenders/match 匹配流）前端全局零调用
- 【现象】功能在后端可用但用户完全摸不到；scheduler 定时"人脉库重建"也无查看界面
- 【严重度】中（半成品/断承接）
- 【修复方向】补 UI 或从规划中移除

## 4. 意向/情报模块

闭环良好：IntentAdmin/IntentAdminEdit/IntentSource 的增删改、submit/review/publish/offline/restore、分类、联系人、附件、AI 分析、来源爬取、导出，路径与参数逐项对齐（intelligence_admin.py ↔ workspace 视图），落库+刷新正常。仅：
- 【功能】前台订阅结果点击
- 【断点】Subscriptions.vue:494-499 `openItem()` 自认"跳到占位"，`window.open('#opportunity-x')` 只开空白页
- 【严重度】中 ｜ 【修复方向】跳 /site/intelligence/:id 或商机详情路由
- 【功能】订阅条件生效性：对话框保存的 excludeKeywords/bidMethods/noticeTypes/sources 在 runCurrent（Subscriptions.vue:376-399）与后端 /public/opportunities/search（public.py:545+）均不被消费——写了不生效 — 中
- 【功能】/intent/ai-analysis（intent.py:461）孤儿（已由 /public/intent-ai 承接）— 低

## 5. 商机模块

CRUD/标签/导出/同步闭环正常。两处类型错位：
- 【断点】后端 `"enabled": bool(r.enabled)`（opportunities.py:680），前端按 0/1 严格比较（Subscriptions.vue:32,35,244,478；Index.vue:67）
- 【现象】个人首页"活跃订阅数"恒 0；已停用标签永不显示；点启停实际发送值与预期相反（`s.enabled===1?false:true` 对 boolean 恒发 true）→ 停用永远停不掉
- 【严重度】中 ｜ 【修复方向】前端按 boolean 处理或后端序列化 0/1
- 【断点】Subscriptions.vue:11-13 "拟建信息/招投标信息" tab 的 `tab` ref 不参与任何过滤（router 定义与 loadList 仅拉商机订阅）— 假多 Tab，中
- 另：`/workspace/intents?highlight=` 参数（App.vue:344）IntentList 完全不读取 — 低

## 6. 仪表盘/统计/营销/内容

/dashboard/* 四接口、GeoMonitor /geo/*、ContentFactory /content/*、CMS、审核日志均对齐闭环。孤儿：/reports/aggregate、/marketing/opportunities、/marketing/topics、/search（全局搜索 API）前端零调用 — 低/中（报表中心有后端无 UI）。

## 7. 检索/组合查询

- /workspace/combined-query 在 router/index.ts 定义两次（:56 redirect 在前、:180 组件在后，redirect 优先生效）——CombinedQuery.vue 实际经 IntelligenceHub"高级组合查询"tab 承接（IntelligenceHub.vue:9），真调 /combined-query/search，功能不断；但 :180 那条是死定义 — 低
- 【断链】ProjectDetail.vue:524 `router.push(navTo('/search'))` → /workspace/search 与 /site/data-center/search 均无此路由 → 点"更多"落 404 页 — 中 —【修复方向】改 push 到 /workspace/intelligence?tab=advanced
- Home 搜索框 → DataCenter → BidCenter/SubQuery 链路正常。

## 8. 登录鉴权/权限

- 后端按路由依赖鉴权，抽查写接口全部挂 require_permission；未登录访问业务 API 一律 401，前端拦截器 + 路由守卫 + 403 页闭环正常；注册无自助入口（仅 RbacManager 管理员建号，属设计）。
- 【越权】persons.py:106 列表无 resolve_scope（companies.py:151、projects.py:296、excel 导出 persons 分支 excel.py:86 都有）→ 部门/个人范围用户可见全部人员 — 高 —【修复方向】人员列表接入 resolve_scope
- 【不一致】/excel/export 仅验登录不验 api_excel 权限（import 有）— 低

## 9. Alembic 删除后的建表/迁移风险

现状：无 `Base.metadata.create_all`；启动跑自研幂等迁移 app/services/migrate.py:342（建 26 个 sql/ 文件 + _ADD_COLUMNS 补列），失败仅 `startup_logger.exception` 不阻断（main.py:104-108）。风险：
- 【断点】docker-compose.yml:19 把 ./sql 挂到 /docker-entrypoint-initdb.d，首次初始化按字母序执行：010_data_scope.sql 的 `ALTER TABLE sys_role/sys_user`、011~019 的 INSERT 都跑在 init_ddl.sql（建 sys_* 基础表）之前 → 全新卷初始化必失败；基础表（company 也不在 init_ddl，而在 industry_data_ddl.sql）实际依赖手工导入 migrate_in/ssm_mysql.sql
- 【现象】全新环境自动部署建表断链；已有环境靠 dump 掩盖
- 【严重度】高（部署/迁移主链路）
- 【修复方向】initdb 目录只放按序命名的基础 DDL，或恢复显式 bootstrap 脚本；迁移清单补全
- 【断点】migrate.py:231 清单缺 012_menu_permissions / 013_role_menu_defaults / 014_fix_menu_names / 016_report_menu / 017_opportunity_admin（均为菜单/角色权限 INSERT）→ 非最新 dump 建的库启动后不补这些权限，前端对应菜单永缺、路由 403 — 中
- 【现象】迁移失败静默（只记日志），缺表缺列要到运行时以 500 暴露

## 功能完整性评分

**71 / 100**。主数据链路（项目/人员/情报/商机 CRUD、审核发布、看板、前台公开站）扎实可信；扣分集中在：一个人脉核心功能整体不可用（3.1）、订阅"假同步"（1.1）、单位导入导出必挂（2.1）、收藏监控闭环缺失（1.2）、权限一致性（8）与部署建表风险（9）。

## 最该优先补的 3 个断点

1. **人脉"我"绑定断链**（§3.1）：把 POST /network/me 接到前端（或 /me/profile 支持绑定）——否则整个以"我"为中心的人脉挖掘模块对新用户等于不存在。
2. **标讯订阅整模块未挂载 + 假成功提示**（§1.1）：main.py 注册 tenders_search 路由，并修正失败也弹"已同步"的话术；连带补齐收藏/监控查看页（§1.2）。
3. **单位 Excel 导入导出单复数不匹配**（§2.1）：DynamicTable 的 excel 路径复用 apiPath() 映射——一行改动救活整个单位数据维护入口；同批处理 persons 数据范围（§8 越权）。
