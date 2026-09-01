# GMI 系统改造指导文档（对标建设通 · 保留人脉网络差异化）

> 版本: v1.1 · 日期: 2026-08-26
> 前置阅读:
> - 调研报告: `docs/archive/cbi360-benchmark.md`（建设通功能/数据/技术栈实证）
> - P0 技术设计: `docs/p0-technical-design.md`（单位 360° 落地细节）
> - 人脉库现状: `docs/business-network-guide.md`
> - 对外公开数据: `docs/site_public_data_requirements.md`

---

## 0. 文档定位

本文是 GMI 对标建设通改造的**总纲指导文档**，完整收录补齐方案（功能模块 / 数据能力 / 人脉结合 / 基础设施 / 产品差异化 / 合规 / 路线图），并明确改造边界。具体表结构、接口签名、前端结构在本文件各章节给出；调研依据见 `docs/archive/cbi360-benchmark.md`。

### 0.1 改造边界（重要）

本阶段**明确不做**以下事项，防止范围蔓延：

| 不做 | 原因 |
|---|---|
| 会员等级 / 付费墙（VIP/SVIP） | 内部平台无商业化诉求；权限用现有 RBAC + data_scope 即可 |
| 订阅推送引擎（企业监控/中标订阅/招标订阅） | 通知复用现有 `notification.py`，事件触发后续单独立项；原 `p0-technical-design.md` P0-2 一并暂缓 |
| 开放 API / 对外计费接口 | 内部使用，无第三方调用方 |

**做**：行业数据标准库（资质/荣誉/诚信/人员证书/开标/工商风险）、组合查询、收藏与标签、前台公开检索、数据采集管道、搜索引擎升级、图数据库扩充、人脉网络产品化、数据导出权限化、字段级脱敏合规。

### 0.2 改造总原则

1. **复用优先**：通知复用 `app/services/notification.py`，定时任务复用 `app/services/scheduler.py` 的 `_job_*` 模式，列表复用 DynamicTable，权限复用 RBAC + `data_scope_service`，脱敏复用 `field_meta` + `filter_fields_by_permission`。
2. **增量不改存量**：新增表与接口，不重构现有 project/person/company 主数据；人脉关系始终以 `network_edge`/Neo4j 为聚合视图，源头可重建。
3. **差异化优先**：建设通只有列表式关系，GMI 的 Neo4j 图谱 + 最短路径 + 招标匹配是护城河，所有新功能优先挂靠人脉能力。
4. **脱敏合规**：对外（`/api/v1/public/*`）一律聚合脱敏；对内敏感字段按角色字段级返回。
5. **命名统一**：本方案统一采用下文 B1 的表名（`qualification`/`person_cert` 等）；`p0-technical-design.md` 中 `company_qualification`/`person_certificate` 即本方案对应表，后续以本方案为准。

---

## 1. 现状与差距速览

### 1.1 GMI 已有能力（源码位置）

| 能力 | 位置 |
|---|---|
| 主数据：单位/人员/项目 | `models/company.py` `person.py` `project.py` |
| 项目单位/成员角色 | `models/project_company.py` `project_member.py` |
| 中标公告（采购人/供应商） | `models/bid_notice.py` + `api/v1/bids.py` |
| 人脉库（边/专长/招标匹配） | `models/business_network.py` + `api/v1/business_network.py` |
| Neo4j 图谱（任职/参与/合作/同事） | `services/neo4j_sync.py` + `api/v1/network.py` |
| 网页线索 + 政务意向采集 | `models/web_clue.py` `intent_notice.py` + `services/intent_crawler.py` |
| 企业富化（企查查） | `services/company_enrich.py` |
| 全局搜索（MySQL FULLTEXT） | `api/v1/search.py` |
| 公开脱敏接口 | `api/v1/public.py` |
| 定时任务 | `services/scheduler.py` |
| 前端 360° 详情 | `views/workspace/CompanyDetail.vue` `ProjectDetail.vue` `PersonProfile.vue` |
| 人脉路径页 | `views/workspace/NetworkPath.vue` |

### 1.2 核心差距（决定改造优先级）

| 差距 | 说明 | 对策 |
|---|---|---|
| 数据广度 | 无资质/荣誉/诚信/证书/工商风险库 | A1 建标准库 + B2 采集 |
| 检索能力 | 仅 project/person 两表 FULLTEXT | A2 + B3 升级索引与组合查询 |
| 关系深度 | 图能力已有但未全面产品化 | C 挂载到所有详情页 |
| 数据质量闭环 | 有 web_clue 筛选但无纠错回写 | G 阶段四补齐 |

---

## 2. 总体架构演进

```
现状：            改造后：
MySQL 主数据  ──>  MySQL 主数据 + 行业标准库（资质/荣誉/诚信/证书/工商/开标）
FULLTEXT      ──>  Elasticsearch（7 域，模糊/精准）+ MySQL 兜底
Neo4j（已有） ──>  Neo4j + 新关系类型（同场竞标/投资/控股/资质）
crawl4ai+政务源 ─>  + 四库一平台/省住建平台/水利/公路采集管道
详情页 3 个   ──>  详情页聚合 11 类 Tab（含人脉触达/关系图谱）
```

三层查询职责分离：**MySQL 主数据 + ES 全文检索 + Neo4j 关系查询**，三者以 entity_id 互链。

---

## 3. A. 需要新增的功能模块（按优先级）

### A1. 行业数据标准库（对标建设通分项查询）

新增 6 个标准数据域，均以 `source + source_url + published_at` 标注溯源：

1. **资质库 `qualification`**：企业×资质（类别三段式：`类别_细分_等级`，如 `监理资质_建设部监理_房屋建筑工程专业监理_乙级`），含发证机关/有效期/状态。企业详情页新增"资质等级"Tab（含等级筛选、失效预警）。
2. **荣誉库 `honor`**：企业×荣誉（奖项名/等级/授予机关/日期），公开字段+敏感字段分级脱敏。
3. **诚信库 `credit_record`**：企业×不良行为/公示（事由/机关/日期），对接"双随机一公开"公示。
4. **人员证书库 `person_cert`**：人员×证书（类别/证书号/印章号/有效期），复用现有 `person` + `person_skill`，扩展证书模型。建设通的"任职过企业数"用 GMI 现有 `network_edge` 的 WORKS_AT 出边计数实现（GMI 已天然支持）。
5. **开标/中标库 `bid_open_record`**：在现有 `bid_notice` 上扩展开标记录（投标单位列表、下浮率），支持"同场竞标"分析（GMI 已有 `/bids/network/company/{id}`，扩展为按场次）。
6. **工商+司法风险库**：接入供应商（企查查已有 `QCC_APP_KEY`，扩到司法/股权/对外投资/分支机构），落地为 `company_ic` + `company_legal_risk`。

### A2. 组合查询（对标建设通 /adsearch/）

在现有 `dynamic_query.py` + `list_filters.py` 基础上做条件构建器：支持企业名称/地区/资质/业绩/人员/项目经理/诚信等多维度"加入筛选"（AND 逻辑），跨表 JOIN 动态生成 SQL，导出按钮接现有 `excel_service`。

- 交互：选条件 → "加入筛选" → 条件列表（积木式）→ "查看检索结果"，一键清除
- 输出：企业列表（含各条件命中摘要），可排序/分页/导出
- 阶段一先实现企业主维度，阶段二扩展资质/业绩/人员关联条件

### A3. 订阅与监控 ——【暂缓，不在本阶段范围】

（原方案：企业监控/业主监控/中标订阅/关键词订阅。已按 0.1 边界划出，后续单独立项。）

### A4. 收藏与标签

- `favorite`（用户×实体类型×实体ID）+ 个人标签 `tag`，用于人脉收藏、竞对跟踪
- 企业/项目/人员详情页收藏按钮；"我的收藏"聚合页（按实体类型分组）
- 竞对跟踪：收藏的企业中标/新增资质时在列表上标记"新"（基于 updated_at）

### A5. 开放 API ——【不实施】

（已按 0.1 边界划出。**数据导出**保留：复用 `excel_service`，加 data_scope + 角色校验。）

### A6. 前台公开检索（对标建设通公开列表引流）

现有 `/site/data-center` 保留登录墙，新增**公开检索页**：

- 企业名称/人员/项目关键词检索 + 地区筛选
- 返回**脱敏列表**（名称可示、电话/金额掩码），登录后解锁完整详情
- 复用 `/public/*` 脱敏边界：不返回联系方式、精确金额、证件信息
- 复制建设通"公开引流 + 登录解锁"双轨

---

## 4. B. 数据能力建设

### B1. 数据模型扩展（对应 `models/` 新增）

```
qualification       (company_id, category, professional, level, issue_org, cert_no,
                     valid_from, valid_to, status, source, source_url, published_at)
honor               (company_id, person_id?, title, level, org, honored_at,
                     source, source_url, published_at)
credit_record       (company_id, title, reason, org, published_at, source, source_url)
person_cert         (person_id, cert_type, cert_no, seal_no, major, valid_from,
                     valid_to, status, source)
company_ic          (company_id, legal_rep, registered_capital, est_date,
                     shareholders JSON, branches JSON, investments JSON, changes JSON)
company_legal_risk  (company_id, risk_type, title, court, amount, published_at,
                     source, source_url)
bid_open_record     (bid_notice_id, company_id, role, amount, discount_rate, opened_at)
favorite            (user_id, entity_type, entity_id)
tag                 (user_id, entity_type, entity_id, tag)
```

> 全部继承 `BaseModel`（id/created_at/updated_at/is_deleted），在 `services/migrate.py` 注册 DDL 文件，走项目既有幂等建表约定。
> 表名说明：`p0-technical-design.md` 的 `company_qualification`/`person_certificate` 即本方案的 `qualification`/`person_cert`。

### B2. 采集管道（复用 scheduler.py + intent_crawler.py + crawl4ai_client.py 模式）

分五路，全部入 `web_source`/`web_clue` 统一溯源：

1. **四库一平台（全国建筑市场监管公共服务平台）**：企业基础/资质/业绩/人员，GET + region_id 分页，遵守 robots 与频率限制，`published_at` 去重
2. **各省住建监管平台**（江苏/浙江/广东/四川等）：诚信公示、双随机通报
3. **专业库**：全国水利建设市场监管平台、公路系统（若行业匹配）
4. **招投标网站**（现有 Crawl4AI 白名单机制扩展）：中标公告 → 现有 `bid_notice` 解析管道
5. **工商/司法供应商 API**：企查查已有接入，扩到股权/司法；或对接天眼查/启信宝

新增调度任务（注册进 `scheduler.py`）：
- `_job_crawl_industry_data`：每日错峰（避开 03:00 意向抓取），行业数据采集
- `_job_sync_cert_validity`：证书到期预警（`person_cert`/`qualification` 的 valid_to 临期/过期状态刷新）

### B3. 搜索引擎

- **现状**：MySQL FULLTEXT（project/person）。建设通 3074 万级体量不适用。
- **方案**：引入 **Elasticsearch**（或轻量 **Meilisearch**）建 `company/qualification/honor/credit/person/bid/project` 7 个索引域；支持**模糊/精准**切换（分词 analyzer + phrase query）、地区过滤、金额区间、排序（时间/金额）；`/search` 接口升级为聚合搜索，返回按域分组的 `{entity_type, count, items}`（与现有返回结构兼容，前端几乎不改）。
- **演进策略**：数据量到万级先用 MySQL 虚拟列/多表 UNION 过渡（现有 `search.py` 扩展 `entity_types` 枚举）；到十万级再上 ES。
- **职责分离**：Neo4j 保留为人脉/关系查询引擎，MySQL 为主数据，ES 为全文检索，三层各司其职。

### B4. 图数据库扩充（人脉网络的增强）

现有 Neo4j 已具备 `Person/Company/Project` 三类节点 + `WORKS_AT/PARTICIPATES_IN/COLLABORATED_WITH/COLLEAGUE` 关系。补齐：

**新增节点**：
- `Region`（已在 sync 中预留）
- `Qualification/Honor/CreditRecord` 作为属性节点挂到 Company（`HAS_QUALIFICATION`/`AWARDED`/`HAS_CREDIT`）

**新增关系**：
- `COMPETES_WITH`（同场竞标，从 `bid_open_record` 推导）
- `JOINT_VENTURE`（联合体，从标书/中标公示解析）
- `INVESTS_IN`（对外投资，从工商数据）
- `CONTROLS`（股权控制，从供应商数据）

**价值**：全量入图后，"某资质企业 + 同区域 + 有人脉路径"这类组合查询可直接在图上一跳完成——这是建设通没有的杀手锏。

**规范**：新增关系一律走 `neo4j_sync.py` 的 `_run`（MERGE 幂等）+ `name_zh` 属性；MySQL 侧 `network_edge` 同步新增关系类型供降级查询。

---

## 5. C. 人脉网络 × 建设通结合方式（差异化核心）

### C1. 企业详情页 = 建设通 11 模块 + GMI 关系图谱

`CompanyDetail.vue` 新增/重构 Tab：

| Tab | 接口（复用/新增） | 内容 |
|---|---|---|
| 关系图谱 | `GET /network/graph/company/{id}`（已有） | 中心企业 → 人员（任职/参与项目）/合作单位/竞对（COMPETES_WITH）/投资关系（INVESTS_IN）；ECharts 图 + 节点着色 + 点击跳转 |
| 人脉触达 | `GET /network/path-to-company/{id}`（已有） | "我 → 桥接人 → 目标单位"最短路径；桥接人卡片含职位/共同项目凭据；AI 生成触达话术（复用 LLM 管线） |
| 中标关系 | `GET /bids/network/company/{id}`（已有） | 潜在业主/竞对/合作方 + 公告证据列表 |
| 资质等级 | `GET /companies/{id}/qualifications`（新增） | 资质台账，分类树/等级筛选/失效预警 |
| 荣誉 | `GET /companies/{id}/honors`（新增） | 荣誉列表，分级脱敏 |
| 诚信 | `GET /companies/{id}/credit-records`（新增） | 不良行为/公示列表 |
| 工商与风险 | `GET /companies/{id}/ic`、`/legal-risks`（新增） | 工商信息（法人/资本/股东/投资/分支）+ 司法风险 |
| 开标记录 | `GET /companies/{id}/bid-open-records`（新增） | 参与的开标 + 同场竞标单位 |

### C2. 项目详情页 = 参与方关系

`ProjectDetail.vue` 已有 `project_companies`/`project_members` 角色表，增强为：

- **参与方关系网**：建设单位→设计→施工→监理→分包的关系链路 + 各自的联系人及任职企业（复用 `GET /network/graph/company/{id}` 或按项目过滤）
- **中标关联**：该项目对应的 `bid_notice`（采购人=建设单位），显示中标金额/时间/来源

### C3. 人员详情页 = 合作网络

`PersonProfile.vue` 已有 `GET /network/person-neighbors/{id}`，增强展示：

- **任职轨迹**：`person.company_id` + `network_edge` WORKS_AT 历史（对应建设通"任职过 N 家企业"）
- **证书墙**：`person_cert`（含过期预警——建设通只做掩码展示）
- **合作网络**："人→项目→人→单位"两条路径展开
- **人脉价值分**：基于图中心度 + 证书 + 项目数计算（新增 `GET /network/score/{person_id}`）

### C4. 差异化产品：人脉雷达

建设通"人脉服务"是人工撮合；GMI 做成**自助产品**：

1. 输入目标企业/招标意向 → 自动计算全图最短路径 + 桥接人 TopK + 每一步"凭据"（共同项目/同事/合作记录）
2. 一键生成触达话术（LLM，复用 `intelligence` 与 `public/intent-ai` 管线）
3. **招标匹配升级**（现有 `tender_match`）：意向 × 人脉路径 × 企业能力（资质+业绩+人员证书）三维打分

---

## 6. D. 技术基础设施补充

| 基础设施 | 现状 | 补什么 |
|---|---|---|
| 搜索引擎 | MySQL FULLTEXT | Elasticsearch/Meilisearch + 7 域索引 + 模糊/精准（B3） |
| 图数据库 | Neo4j（已有） | 扩充节点/关系类型，图查询服务化（B4） |
| 采集管道 | intent_crawler/crawl4ai（已有） | 行业数据五路采集 + 去重/溯源/限速 + 增量调度（B2） |
| 用户体系 | JWT + RBAC（已有） | 补充第三方登录、邀请注册（可选） |
| 权限体系 | RBAC + 字段权限 + 数据授权（已有） | 增加收藏权限对象；导出走角色+data_scope 校验 |
| 消息系统 | notification + notify webhook（已有） | 事件触发扩展（订阅引擎暂缓，后续立项）；渠道抽象（站内/邮件/企微） |
| 任务队列 | apscheduler（已有） | 采集任务量大后迁 Celery/RQ 分布式（可选） |
| 数据质量 | 部分 | 来源管理表 `web_source` 已有，补可信度评分 + 数据更新时间戳全局展示 |

---

## 7. E. 产品形态上需保留的差异化

1. **人脉路径可视化**（建设通只有列表）——核心护城河，全站贯穿（企业/项目/人员详情 + 首页入口）。
2. **招标×人脉×能力三维匹配推荐**（`tender_match`）——建设通只做标讯订阅。
3. **LLM 研判 + 触达话术**（`intent-ai`/`intelligence` 管线）——建设通"AI 标讯"偏资讯聚合，GMI 是深度经营分析。
4. **内网私有数据优先 + 公共数据补充**：GMI 的企业/人员/项目是用户自己的业务数据（真实、即时、可维护），公共库做自动匹配挂接（同名/信用代码归一），形成"自己的关系 + 行业的事实"叠加。
5. **合规克制**：不公开姓名/电话/金额，延续 `public` 接口脱敏模式；GMI 面向内部经营，信息可分级开放。

---

## 8. F. 数据合规与来源说明

1. 公共数据仅采集**政府公开公示渠道**（四库一平台、省级住建平台、水利/公路系统、招投标公示），页面标注来源与链接、采集时间。
2. 页面加"信息来源"列 + 详情页加"数据来源与免责声明"（对齐建设通做法）。
3. 工商/司法类数据**优先走合规供应商 API**（企查查已接入，按次计费），不自行爬取商业站点。
4. 采集遵守目标站点 robots、频控、仅公开内容、最小必要原则；平台内展示遵循**字段级脱敏矩阵**（公开/内部/加密三档，已有 `field_meta` + `data_scope_service` 基础可扩展）。
5. 用户个人（我/人脉）信息仅内部可见，不进入公共接口。

---

## 9. G. 分阶段落地路径

### 阶段一（4-6 周）：数据地基 + 详情聚合

- 建 A1 的行业数据表（qualification/honor/credit_record/person_cert/bid_open_record/company_ic/company_legal_risk）+ 四库一平台/政务公示采集管道（复用 intent_crawler 模式）
- `CompanyDetail.vue` 新增：资质/荣誉/诚信/工商风险 Tab；`PersonProfile.vue` 新增证书墙
- ES 索引 company 域 + 公开检索页（可用 MySQL 过渡）
- **验收**：企业详情能展示"资质+荣誉+诚信+风险+关系图谱"五合一

### 阶段二（4-6 周）：搜索与关系增强

- ES 全 7 域 + 模糊/精准 + 组合查询（dynamic_query 扩展）
- Neo4j 扩节点/关系（HAS_QUALIFICATION/COMPETES_WITH/INVESTS_IN）
- 企业详情新增"人脉触达"Tab（最短路径 + AI 话术）；项目详情参与方关系网
- **验收**：输入"XX 资质 + XX 地区"能搜出企业并给出人脉触达路径

### 阶段三（4-6 周）：运营能力

- 收藏与标签（favorite/tag）+ 我的收藏页
- 数据导出权限化（excel_service + data_scope + 角色校验）
- 纠错闭环（数据反馈 → 处理 → 回流更新）
- 查询审计（检索行为记录）
- **验收**：收藏的竞对企业新增资质可见"新"标记；导出行受权限控制；纠错工单可流转

### 阶段四（持续）：扩展与深化

- 多库扩展（公路/水利）
- 图算法深化（PageRank 找关键桥接人、社区发现找商圈）
- 人脉雷达产品化（C4）
- 移动端适配、私有化部署

---

## 10. 验收标准汇总（各阶段可度量）

| 里程碑 | 验收 |
|---|---|
| M1（阶段一） | 企业详情五合一（资质+荣誉+诚信+风险+关系图谱）；人员证书墙含过期预警 |
| M2（阶段二） | 7 域检索 + 模糊/精准 + 组合查询；资质×地区可搜企业并给出人脉触达路径 |
| M3（阶段三） | 收藏/标签/导出权限/纠错/审计全部可用 |
| M4（阶段四） | 多库采集稳定运行，图算法输出关键桥接人/商圈 |

**风险与对策**：
- 采集源反爬/变动 → 源抽象 + 解析器可替换 + 失败告警（复用 `notify.send_alert`）
- 主体归一化误合并 → 人工确认队列 + 置信度阈值
- Neo4j 不可用 → 已有熔断降级 + `network_edge` 兜底，勿阻塞主流程
- ES 运维成本 → 先用 MySQL 过渡，十万级再引入

---

## 11. 与现有文档的衔接

- 功能/数据实证 → `docs/archive/cbi360-benchmark.md`
- P0 三项技术设计 → `docs/p0-technical-design.md`（其中 P0-2 订阅引擎按 0.1 暂缓；P0-1 表名以本文 B1 为准）
- 人脉库维护流程 → `docs/business-network-guide.md`
- 公开数据接口约束 → `docs/site_public_data_requirements.md`

---

## 12. 阶段一落地状态（2026-08-27 更新）

**已实现并通过验证**：

| 项 | 内容 | 验证结果 |
|---|---|---|
| 数据模型 | `models/industry_data.py` 7 表 | MySQL 建表成功（`SHOW TABLES` 全部存在） |
| 建表 | `sql/industry_data_ddl.sql` + migrate 注册 | 手动执行无报错 |
| 单位详情 API | `api/v1/company_detail.py` 7 端点 | 8101 端口实测：资质/荣誉/诚信/工商/司法/开标/证书全部正常返回（插入测试数据后 total=1、中文/状态统计正确） |
| 人员证书 API | `persons.py /persons/{id}/certificates` | 实测返回正确 |
| 采集管道 | `services/industry_crawler.py` + scheduler 注册（06:30 采集 / 05:45 证书有效性） | 实测抓取通过：配置 kyqgs 矿业权人异常名录（`search_jymlyc.jspx`）→ 提取 10 家企业名 → 匹配到公司库的 1 家成功落库 `credit_record`（`stored=1 / no_company=9`，未匹配为库中无对应企业，符合设计）；另支持「列表页即数据页」模式（免详情页/验证码） |
| 公开检索 | `public.py /public/search` + `PublicSearch.vue` + 路由（`meta.public` 豁免登录） | 8101 端口实测：无命中 0.05s 正常返回 |
| 前端 | `CompanyDetail.vue` 行业数据 Tab（5 子 Tab）、`PersonProfile.vue` 证书墙 | `npm run build` 通过 |

**验证中发现的环境问题（已修复）**：
- `config.py` 默认 `DATABASE_URL` 指向 `localhost:3307/ssm_db` 与实际容器不符，导致新进程连不上库、startup 卡死约 100s。已在 `backend/.env` 补充正确的 `DATABASE_URL`（`127.0.0.1:3306/ssm`）。
- 本地 8100 端口存在旧实例占用（`bind 10048`），验证改在 8101 端口完成；**重启本地后端时需先停掉 8100 旧进程**。

**采集实测结论与注意点**：
- 已实测数据源：自然资源部「矿业权人异常名录」（`kyqgs.mnr.gov.cn/search_jymlyc.jspx`）——列表页即公示数据（免详情页，详情页有验证码）。实测 `listed=10 → stored=1`（仅命中 GMI 公司库的企业落库）。
- **落库依赖公司库命中**：外部公示企业若不在 `company` 库中则不入库（设计如此，保证 360° 关联）。要在生产中跑出数据，需先扩充公司库（导入矿业/建筑企业），或对高频目标企业预建档案。
- 政务站点常见 SSL 证书链问题，`industry_crawler._fetch` 已用 `verify=False`；采集仅针对政府公开公示渠道，遵守最小必要原则。
- 测试用的 `web_source` 配置与测试数据已清理，生产启用时按 B2 配置真实源即可。

**尚未落地（阶段一剩余）**：公开检索页的上线导航联调；生产级 `web_source` 行业数据源配置（待公司库规模到位后启用）。

*本文为改造总纲，各阶段开工前按需补充详细技术设计。*
