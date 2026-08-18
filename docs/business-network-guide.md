# 人脉库模块使用与更新指南

> 2026-08-14。人脉库 = 从多源(项目/人员/单位/中标/三元组)聚合的**关系视图**，支持初始化、持续更新、招标信息联动匹配。

## 一、数据模型（可扩展）

### 三张表
| 表 | 作用 | 关键字段 |
|---|---|---|
| `person_skill` | 人员专长标签 | person_id, skill, source(manual/project_infer), confidence |
| `network_edge` | 人脉边(两实体加权关系) | src_type/src_id, tgt_type/tgt_id, rel_type, weight, source, evidence, last_seen |
| `tender_match` | 招标×人脉匹配 | clue_id, title, entity_type/id, match_type, match_reason, score, status |

### 人脉边关系类型
- `PARTICIPATES_IN`：人员/单位 ↔ 项目（角色区分）
- `WORKS_AT`：人员 → 单位（任职）
- `COLLABORATED_WITH`：单位-单位 / 人员-人员 / 单位-人员（同项目共事/合作）

### 扩展性设计
- **不重复存原始数据**：边是聚合视图，源头仍是 project_member/project_company/bid_notice/entity_relation，改源头后重建即可
- **weight 累加**：同类型关系多次出现(多个项目合作)权重叠加，体现亲疏
- **source 可溯源**：每条边记录来源表，问题可定位

## 二、初始化（从 samples 真实数据）

### 方式：API 一键初始化
```
POST /api/v1/biz-network/init
```
从现有 company/person/project/project_member/project_company 全量重建：
- 25 条 人员↔项目、23 条 单位↔项目、30 条 单位-单位合作、44 条 人员-人员、45 条 单位-人员、14 条 任职
- 74 个专长标签（从项目类别+项目名关键词推导）

### 前置数据导入（samples）
| 文件 | 导入接口 | 说明 |
|---|---|---|
| `samples/real_project_info.xlsx` | `POST /projects/import-real` | 真实项目(含法人/业主/负责人/金额) |
| `samples/real_person_info.xlsx` | `POST /persons/import-real` | 人员花名册(职位/部门/电话/单位) |
| `samples/companies.xlsx` | `POST /excel/import/companies` | 甲方单位清单 |

导入完成 → `POST /biz-network/init` → 人脉库就绪。

## 三、持续更新（可复用流程）

### 场景与操作
| 场景 | 操作 | 说明 |
|---|---|---|
| 新项目导入 | 先导 xlsx → `POST /projects/import-real` → `POST /biz-network/rebuild-edges` | 自动生成新参与关系 |
| 新人员导入 | 先导 xlsx → `POST /persons/import-real` → `POST /biz-network/rebuild-edges` | 自动挂任职+项目关系 |
| 中标数据更新 | 抓取中标 → `POST /bids/rebuild` → `POST /biz-network/rebuild-edges` | 补充外部合作方 |
| 专长修正 | 前端人脉库页(预留) / 直接插 person_skill(source=manual) | 手工标注优先，重建不覆盖 manual |

### 幂等与去重
- **network_edge**：唯一键 `(src_type,src_id,tgt_type,tgt_id,rel_type)`，重建用 `delete + insert`，天然去重
- **person_skill**：唯一键 `(person_id,skill)`，`sync_person_skills` 只补不覆盖（manual 标签保留）
- **tender_match**：唯一键 `(clue_id,entity_type,entity_id)`，重复匹配更新 score/reason

### 定时更新建议（可选）
```
┌─────────┐   ┌──────────────┐   ┌─────────────┐   ┌──────────────┐
│ 招标源    │→ │ 定时抓取(6h) │→ │ bids/rebuild │→ │ rebuild-edges│
│ 意向源    │→ │ 定时抓取(24h)│→ │ web_clue 入库 │→ │ tenders/match │
└─────────┘   └──────────────┘   └─────────────┘   └──────────────┘
```

## 四、与招标信息联动（提前获取招标信息）

### 匹配逻辑（`business_network.match_tenders`）
1. **人员专长匹配**：招标标题含人员专长(skill) → 得分 0.6
2. **单位业务匹配**：招标标题含单位业务关键词(勘察/施工/设计/监理) → 得分 0.5
3. **区域加分**：招标地域含单位省份 → +0.2
4. 得分 ≥ 0.6 写入 `tender_match`，前端可跟进(状态: 待跟进/已联系/跟进中/已忽略)

### 实测效果
- 费卫平(定日地灾项目) → 匹配 4 条地质灾害类招标（万源/自贡/游仙/利州）
- PZH(生态修复项目) → 匹配 5 条生态修复类招标（泸州/宝兴/绵阳/石渠/广安）
- 全部带 得分/匹配理由/地域/预算，可在人脉库页跟进

## 五、API 一览
| 接口 | 说明 | 权限 |
|---|---|---|
| `POST /biz-network/init` | 全量初始化(边+专长) | api_company_crud |
| `POST /biz-network/rebuild-edges` | 仅重建边 | api_company_crud |
| `GET /biz-network/edges/{type}/{id}` | 实体人脉边 | 登录 |
| `GET /biz-network/skills/{person_id}` | 人员专长 | 登录 |
| `POST /biz-network/tenders/match` | 招标匹配 | api_company_crud |
| `GET /biz-network/tenders/matches` | 匹配列表 | 登录 |
| `PUT /biz-network/tenders/matches/{id}/status` | 更新状态 | api_company_crud |

## 六、后续扩展方向
- **bid_notice 关联**：把近两年中标公告的采购人/供应商作为 network_edge 来源(补外部实体)
- **entity_relation 关联**：LLM 开放三元组作为边来源
- **自动定时**：加 scheduler 定期 rebuild + match
- **专长 AI 标注**：用 knowledge_extractor 从人员简历/项目描述抽取专长
