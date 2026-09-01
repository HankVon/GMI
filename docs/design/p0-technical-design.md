# GMI P0 改造技术设计（对标建设通）

> 版本: v1.0 · 日期: 2026-08-26
> 前置调研: `docs/archive/cbi360-benchmark.md`
> 范围: P0 三项 — ① 单位 360° 详情扩展 ② 智能订阅引擎 ③ 业主发包排名统计
> 现有技术栈: Vue3+ElementPlus+Pinia+ECharts / FastAPI+SQLAlchemy / MySQL+Redis+Neo4j / crawl4ai+apscheduler / Ollama

---

## 0. 总体原则

1. **复用优先**：通知复用 `app/services/notification.py`，定时任务复用 `app/services/scheduler.py` 的 `_job_*` 模式，列表复用 DynamicTable，权限复用 data_scope + RBAC。
2. **增量不改存量**：新增表与接口，不重构现有项目/人员/单位主数据。
3. **脱敏合规**：联系方式/金额等敏感字段按角色返回（字段级权限）。
4. **数据质量闭环**：所有列表提供"我要纠错"入口 → 复用 `web_clue`/反馈机制。

---

## 1. P0-1 单位 360° 详情扩展

### 1.1 目标

建设通企业详情有 15+ 标签页；内部现有 `CompanyDetail.vue` 已具备「商情分析报告（潜在商机/公司背景/公关路径/情报关联）」+「单位信息」主结构。本项在**单位信息** tab 下扩展标签，补齐：中标业绩、资质台账、人员证书、竞争企业、业主关联。

### 1.2 数据模型（新增表）

```python
# backend/app/models/person_certificate.py
"""人员证书 — 证书类型/证号/有效期（对标建设通查人员证书体系）"""
class PersonCertificate(BaseModel):
    __tablename__ = "person_certificate"

    person_id: Mapped[int] = mapped_column(BigInteger, comment="人员id")
    cert_type: Mapped[str] = mapped_column(String(64), comment="证书类型(关联 option_set:cert_type: 建造师/监理/安全C证/职称)")
    cert_no: Mapped[str] = mapped_column(String(128), comment="证书编号")
    cert_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="等级(一级/二级/甲级等)")
    major: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="专业/注册类别")
    issue_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="发证日期")
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="有效期至")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="active/expired")
    source: Mapped[str] = mapped_column(String(32), default="manual", comment="manual/import/external")
```

```python
# backend/app/models/company_qualification.py
"""单位资质台账 — 对标建设通查资质的多层分类(大类/专业/等级)"""
class CompanyQualification(BaseModel):
    __tablename__ = "company_qualification"

    company_id: Mapped[int] = mapped_column(BigInteger, comment="单位id")
    category: Mapped[str] = mapped_column(String(64), comment="资质大类(施工/勘察/设计/监理/地灾治理...)")
    professional: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="专业/细分类别")
    level: Mapped[str] = mapped_column(String(32), comment="等级(甲/乙/丙/一级/二级/三级/不分等级)")
    cert_no: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="证书编号")
    issue_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="发证日期")
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="有效期至")
    source: Mapped[str] = mapped_column(String(32), default="manual", comment="manual/import")
```

> 迁移：在 `backend/app/services/migrate.py` 的 DDL 列表追加建表语句（项目约定 migrate.py 幂等建表，无需 alembic）。

### 1.3 后端接口

```python
# backend/app/api/v1/company_detail.py (新增)
router = APIRouter(prefix="/companies/{company_id}", tags=["单位360°"])

GET /companies/{company_id}/qualifications
    → 资质台账列表（按 category/professional 分组，支持 level 筛选）

GET /companies/{company_id}/bid-history
    → 该单位作为采购人/供应商的中标业绩（聚合 bid_notice，
      按 purchaser_company_id=company_id OR meta.suppliers[].supplier_company_id=company_id）

GET /companies/{company_id}/competitive
    → 竞争企业（Neo4j 同场竞标：查询与该单位出现在同一 bid_notice 供应商列表的其他企业，
      按共现次数降序）——无 Neo4j 数据时返回空并提示

GET /companies/{company_id}/owner-stats
    → 该单位作为采购人(业主)的发包统计（见 P0-3 的复用：聚合 bid_notice.purchaser）

GET /companies/{company_id}/members-with-cert
    → 本单位人员 + 各自证书列表（person + person_certificate，支持"仅看有效/全部"）
```

```python
# backend/app/api/v1/persons.py 追加
GET /persons/{person_id}/certificates
    → 人员证书列表（type/major/level/valid_until/status）

POST /persons/{person_id}/certificates      # 录入证书
PUT  /persons/{person_id}/certificates/{id} # 修改
```

### 1.4 前端页面结构

`CompanyDetail.vue` 的「单位信息」tab 下扩展子标签：

```
单位信息
├─ 基本信息（现有）
├─ 资质台账      → QualificationList（DynamicTable：大类/专业/等级/有效期 + 过期标记）
├─ 中标业绩      → BidHistoryList（复用 bid_notice 聚合：标题/角色/金额/时间/纠错按钮）
├─ 人员证书      → MemberCertList（人员 + 证书展开，有效期校验，红标"已过期"）
├─ 竞争企业      → CompetitiveTable（企业名/共现次数/最近时间）
└─ 业主发包统计  → OwnerStatCards（发包总额/数量/市级排名，见 P0-3）
```

新增公共组件建议：
- `components/company/QualificationTable.vue`（资质分类树筛选 + 表格）
- `components/company/CertificatePanel.vue`（证书卡片/表格 + 新增表单）
- 全局指令 `v-mask`（脱敏手机/证件号，按权限显示）

### 1.5 实施步骤

| 步骤 | 内容 | 预估 |
|---|---|---|
| S1 | 新增 2 张表 + migrate.py 追加 DDL | 0.5 天 |
| S2 | 后端接口：qualifications / bid-history / competitive / members-with-cert / certificates | 1.5 天 |
| S3 | 前端单位信息 tab 扩展 + 3 个组件 + v-mask 指令 | 2 天 |
| S4 | 人员证书录入表单 + 有效期校验逻辑 | 1 天 |
| S5 | Excel 导入（资质/证书批量导入，复用 excel 模块） | 1 天 |

---

## 2. P0-2 智能订阅引擎

### 2.1 目标

对标建设通「智能订阅」：用户配置订阅条件（数据源类型 × 地区 × 分类/关键词 × 金额区间 × 频率），系统在数据入库后匹配并站内通知。

### 2.2 数据模型

```python
# backend/app/models/subscribe_rule.py
"""订阅规则 — 数据入库后按规则匹配并推送通知"""
class SubscribeRule(BaseModel):
    __tablename__ = "subscribe_rule"

    user_id: Mapped[int] = mapped_column(BigInteger, comment="订阅用户id")
    name: Mapped[str] = mapped_column(String(128), comment="订阅名称(如: 四川地灾治理)")
    target_type: Mapped[str] = mapped_column(String(32), comment="数据源类型 bid/intent/company")
    province: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="省份")
    city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="城市")
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="分类/行业(逗号分隔, 匹配任一)")
    keywords: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="关键词(空格分隔, 标题含其一即命中)")
    amount_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True, comment="金额下限(万元)")
    amount_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True, comment="金额上限(万元)")
    frequency: Mapped[str] = mapped_column(String(16), default="realtime", comment="realtime/daily")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    last_match_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="上次匹配时间")
```

```python
# backend/app/models/subscribe_match.py
"""订阅命中记录 — 记录匹配结果, 供去重与"我的订阅"查看推送历史"""
class SubscribeMatch(BaseModel):
    __tablename__ = "subscribe_match"

    rule_id: Mapped[int] = mapped_column(BigInteger, comment="规则id")
    user_id: Mapped[int] = mapped_column(BigInteger, comment="用户id(冗余便于查询)")
    target_type: Mapped[str] = mapped_column(String(32), comment="数据源类型")
    target_id: Mapped[int] = mapped_column(BigInteger, comment="命中数据id(bid_notice/id 或 intent_notice/id)")
    title: Mapped[str] = mapped_column(String(512), comment="命中标题")
    region: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    pushed: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已推送通知")
```

> 唯一约束：(rule_id, target_type, target_id) 防重复。

### 2.3 匹配服务

```python
# backend/app/services/subscribe_engine.py
def match_rule(db, rule: SubscribeRule, candidates: list[dict]) -> list[dict]:
    """对候选数据逐条判断是否命中规则。
    规则: 省/市精确 + 分类命中任一 + 关键词命中任一(标题 LIKE) + 金额区间。
    """
    hits = []
    for c in candidates:
        if rule.province and c.get("province") != rule.province:
            continue
        if rule.city and c.get("city") != rule.city:
            continue
        if rule.category and not _hit_any(c.get("category", ""), rule.category):
            continue
        if rule.keywords and not _hit_keywords(c.get("title", ""), rule.keywords):
            continue
        if rule.amount_min is not None and (c.get("amount") or 0) < rule.amount_min:
            continue
        if rule.amount_max is not None and (c.get("amount") or 0) > rule.amount_max:
            continue
        hits.append(c)
    return hits

def run_subscribe_matching(db, target_type: str, new_rows: list[dict], now=None) -> int:
    """对一批新入库数据执行全部启用规则的匹配，命中后:
       1) INSERT subscribe_match(幂等, 冲突忽略)
       2) 未推送过的 → create_notifications(type="subscribe")
    """
```

### 2.4 定时/触发集成

- **入库即匹配（推荐）**：在 `bid_notice`/`intent_notice` 新增解析入口后调用 `run_subscribe_matching(db, "bid"/"intent", rows)`，实时性最好。
- **兜底任务**：scheduler.py 新增 `_job_subscribe_daily`（每日 03:30，补扫近 24h 新数据，适配 frequency=daily 与漏配场景），在 `start_scheduler()` 注册 cron。

### 2.5 后端接口

```python
# backend/app/api/v1/subscribe.py (新增)
router = APIRouter(prefix="/subscribe", tags=["智能订阅"])

GET    /subscribe/rules              我的订阅规则列表
POST   /subscribe/rules              创建规则
PUT    /subscribe/rules/{id}         更新规则
DELETE /subscribe/rules/{id}         删除(软删)
POST   /subscribe/rules/{id}/toggle  启用/停用
GET    /subscribe/matches            推送历史(分页, 按 rule_id 过滤)
POST   /subscribe/rules/{id}/test    测试命中(不建记录, 仅返回当前库命中条数)
```

### 2.6 前端页面

- `views/workspace/Subscribe.vue`（菜单：`menu_subscribe`）
  - 规则卡片列表：名称 / 条件摘要 / 启用开关 / 命中数 / 最近匹配时间
  - 新建/编辑表单：目标类型 → 省/市（复用 china_regions 树）→ 分类（选项集）→ 关键词（tag 输入）→ 金额区间 → 频率
  - "立即测试"按钮：显示当前库命中预览
- 列表页（标讯/意向）加"订阅此条件"按钮：将当前筛选条件一键生成为规则
- 站内通知铃铛：复用现有通知 API，新增 type=`subscribe`，点击跳转到对应数据详情

### 2.7 实施步骤

| 步骤 | 内容 | 预估 |
|---|---|---|
| S1 | 2 张表 + migrate.py DDL + Redis 去重键设计 | 0.5 天 |
| S2 | subscribe_engine 匹配服务 + 单元测试 | 1.5 天 |
| S3 | subscribe API（CRUD/test/matches） | 1 天 |
| S4 | 入库点接入（bid/intent 解析后调用）+ scheduler 兜底任务 | 1 天 |
| S5 | 前端规则管理页 + 列表页"订阅此条件" | 2 天 |
| S6 | 通知联动 + 推送历史页 | 0.5 天 |

---

## 3. P0-3 业主发包排名统计

### 3.1 目标

对标建设通"查业主"：按单位聚合发包数据（发包项目数、发包总额、金额市级排名、数量市级排名），用于商机评估与客户经营。

### 3.2 统计口径

- **数据源**：`bid_notice`（purchaser 为业主，purchaser_company_id 匹配 company 主数据）。
- **口径**：
  - 发包总额 = SUM(该业主全部 bid_notice 的 meta.suppliers[].amount) 或公告金额
  - 发包数量 = COUNT(bid_notice)
  - 市级排名 = 按 `region`(省) 分组后，对总额/数量排序取 rank
  - 时间窗：近 1 年 / 上年度 / 全部（可选）
- **含子公司**：可选开启 company 主数据的归属关系（P1，先不做）。

### 3.3 实现方式（二选一，推荐 B）

**A. 实时聚合**：每次请求 `GROUP BY purchaser_company_id` + 子查询排名。
- 优点：无一致性维护
- 缺点：bid_notice 量大时慢（加索引后可接受）

**B. 物化统计表（推荐）**：定时任务（每日 04:00）聚合写 `owner_stat`，接口只读表。

```python
# backend/app/models/owner_stat.py
"""业主发包统计(物化) — 每日定时重建"""
class OwnerStat(BaseModel):
    __tablename__ = "owner_stat"

    company_id: Mapped[int] = mapped_column(BigInteger, unique=True, comment="业主单位id")
    company_name: Mapped[str] = mapped_column(String(256), comment="单位名称")
    province: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bid_count: Mapped[int] = mapped_column(BigInteger, default=0, comment="发包数量")
    bid_total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0, comment="发包总额(万元)")
    bid_count_rank: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="数量市级排名")
    bid_amount_rank: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="金额市级排名")
    stat_date: Mapped[datetime] = mapped_column(DateTime, comment="统计日期")
```

### 3.4 聚合任务

```python
# app/services/owner_stat.py
def rebuild_owner_stat(db, now=None) -> dict:
    """1) 按 purchaser_company_id 聚合 bid_notice → 数量/总额
       2) 按 province 分组对 数量/总额 排序写 rank
       3) 全量重建 owner_stat(先软删旧数据, 再插入新快照, 保留 stat_date)
    """
```

scheduler.py 注册：`_job_rebuild_owner_stat`，cron `hour=4, minute=20`。

### 3.5 接口

```python
# backend/app/api/v1/owner_query.py (新增)
router = APIRouter(prefix="/owner-stats", tags=["业主发包统计"])

GET /owner-stats?province=&city=&min_count=&min_amount=&page=&page_size=
    → 业主列表: company_id/name/city/bid_count/bid_total_amount/rank + 排序(金额/数量)

GET /owner-stats/{company_id}
    → 单业主: 聚合卡 + 发包明细(bid_notice 列表, 分页) + 关联联系人(company person)

GET /owner-stats/top?province=&limit=20&by=amount|count
    → 省域 TopN(供图表)
```

### 3.6 前端

- `views/workspace/OwnerStats.vue`（菜单：`menu_owner_stats`）
  - 筛选条：省/市（china_regions 树）+ 金额/数量区间
  - 汇总表格：单位/城市/发包数量/总额/数量排名/金额排名（排名列高亮 Top10）
  - 点击行 → 业主明细抽屉：发包公告列表 + 关联单位人员
- 图表：省域 TopN 柱状图（复用 EChart.vue）
- 数据中心"单位画像"tab：单位详情内嵌本单位的发包统计卡（复用 P0-1 的 owner-stats）

### 3.7 实施步骤

| 步骤 | 内容 | 预估 |
|---|---|---|
| S1 | owner_stat 表 + rebuild 服务 + scheduler 任务 | 1 天 |
| S2 | owner-stats 接口（列表/详情/TopN） | 1 天 |
| S3 | 前端 OwnerStats 页 + 图表 | 1.5 天 |
| S4 | 单位详情嵌发包统计卡 | 0.5 天 |

---

## 4. 里程碑与依赖

```
M1 (P0-1) 单位360°详情扩展 —— 约 6 天   ← 依赖: 无
M2 (P0-2) 智能订阅引擎     —— 约 6.5 天 ← 依赖: M1 的列表纠错(可选)
M3 (P0-3) 业主发包排名     —— 约 4 天   ← 依赖: bid_notice 数据完整度

总工期: 约 17 人天（前端后端并行可压到 2 周内）
```

### 风险与对策

| 风险 | 对策 |
|---|---|
| bid_notice 数据量小(当前 147 条)导致统计无意义 | 先扩充数据源(ccgp 增量 + ggzy)再上线统计；统计表每日重建自适应 |
| 竞争企业分析依赖 Neo4j 数据完整度 | 无数据时接口降级返回"暂无竞争企业数据"提示 |
| 订阅匹配性能(规则×数据量) | 按 target_type 分批 + Redis 去重 + 入库点触发(非全量扫) |
| 证书/资质数据需人工录入成本高 | 提供 Excel 批量导入(复用 excel 模块) + 半自动从公告抽取 |

---

*本设计为落地基线，实施时可按里程碑拆分排期。*
