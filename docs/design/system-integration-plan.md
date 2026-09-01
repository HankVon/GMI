# SSM 系统现状梳理与「提前获取招标信息」整合落地方案

> 2026-08 编制。目标：把「招标信息提前获取 → 人脉库 → 关联匹配」有机融入现有系统。

## 一、现有系统功能模块盘点

### 1. 核心业务实体（company/person/project）
| 模块 | 文件 | 能力 |
|---|---|---|
| 单位管理 | `api/v1/companies.py` | CRUD、免费补全(企查查/搜索引擎/公告库)、字段说明 |
| 人员管理 | `api/v1/persons.py` | CRUD、花名册导入(real_person_import) |
| 项目管理 | `api/v1/projects.py` | CRUD、真实项目导入(real_project_import)、项目进度/成员/单位 |
| 项目关联 | `project_members/project_companies/project_progress` | 项目↔人员/单位 角色关系 |

### 2. 数据获取与智能
| 模块 | 文件 | 能力 |
|---|---|---|
| 网页线索 | `api/v1/web_clues.py` + `clue_filter.py` | 多来源爬取(政府采购/中标/意向)、关键词筛选、AI增强、日志/进度 |
| 爬虫引擎 | `crawl4ai-server/` + `crawl4ai_client.py` | scrape/crawl/query 三模式、验证码OCR、翻页 |
| 中标分析 | `api/v1/bids.py` + `bid_network.py` | 中标公告解析、采购人/供应商严格匹配、Neo4j 图谱 |
| 知识图谱 | `api/v1/knowledge.py` + `knowledge_extractor.py` + `knowledge_ingest.py` | 开放域 NER+RE、区域关联、三元组落库 |
| 免费补全 | `company_free_enrich.py` + `search_llm.py` | 多引擎搜索+LLM结构化抽取、动态建字段 |
| 图谱同步 | `neo4j_sync.py` | Company/Person/Project/Region 节点+预设关系 |

### 3. 基础能力
- 动态字段引擎 `dynamic_field_engine.py`（field_metadata 驱动，可扩展）
- 行政区划库 `china_regions.py`（省-市-县三级）
- 认证权限 `middleware/auth`、RBAC
- 迁移 `migrate.py`（DDL 文件自动建表）

## 二、数据流全景（现状）

```
[外部源: 政府采购网/发改委等] → web_clue(线索) → ClueFilter(筛选) → 筛选入库
                                          ↓ 中标公告
                                    bid_network 解析 → bid_notice → Neo4j(Bid/采购人/供应商)
                                          ↓ 文本
                                    knowledge_extractor(NER+RE+区域) → entity_relation + Neo4j
[Excel 导入] → real_project_import/real_person_import → company/person/project + Neo4j
[搜索补全] → company_free_enrich → company.ext_attrs + Neo4j
```

**核心问题**：各模块数据已入库，但**关系查询不统一**（knowledge 只查 entity_relation、bids 只查 bid_notice、人脉只查 Neo4j 预设关系），且**无「招标信息提前获取」的入口**（现在只能手动抓政府采购网，无发改委/发改委/交通厅/自然资源局来源，无定时任务）。

## 三、复用 / 重构 / 新建清单

### ✅ 可直接复用
| 能力 | 说明 |
|---|---|
| 网页线索爬取骨架 | web_source + web_clue + crawl4ai 三模式，**新来源只加配置** |
| 关键词/结构化筛选 | ClueFilter（需增强结构化条件） |
| 中标解析 | bid_network 严格匹配、字段错位修复 |
| LLM 抽取 | knowledge_extractor/search_llm 的 prompt 与容错 |
| 区域库/动态字段/Neo4j 同步 | 基础能力直接调用 |

### 🔧 需重构/增强
| 项 | 现状 | 改造 |
|---|---|---|
| `web_clue.category` | 恒 null | ClueFilter 真正分类填充 |
| `/knowledge/relations` | 只查 entity_relation | **聚合多源关系视图**(bid/project_member/neo4j预设/三元组) |
| 意向推荐 `/bids/intent-recommendations` | 仅标题关键词 | 接入新来源结构化字段 |
| bid_notice | 无代理机构/近两年过滤 | 加 agency 字段 + 时间窗过滤 |

### 🆕 需新建
| 模块 | 内容 |
|---|---|
| **招标源配置** | 发改委/交通厅/自然资源局/公共资源交易 等来源种子(web_source) |
| **定时任务** | scheduler(apscheduler)：周期性抓取意向源 + 增量 rebuild 中标 |
| **intent_notice 表** | 意向性信息结构化(部门/项目类型/金额/地区/发布时间) |
| **人脉库** | `business_network` 系列：数据模型 + 初始化 + 更新 + 招标匹配(本期核心) |
| **前端** | 人脉库页面(关系视图+招标匹配推荐) |

## 四、整合落地方案（招标信息提前获取 → 人脉库联动）

```
[① 意向源定时抓取]                  [② 人脉库]
发改委/交通厅/自然资源局     ←→   business_network(项目/人员/单位/区域)
全国公共资源交易/寻源询价           ↑ 初始化: samples 真实数据
        ↓                          ↑ 更新: 导入脚本/增量
intent_notice(结构化)               ↑ 关联: 项目↔人员↔单位↔区域
        ↓                          ↑ 联动: 按项目类型/人员专长匹配
[③ 统一关系视图]
knowledge/relations 聚合: 三元组 + 中标 + 项目角色 + 人脉预设关系
        ↓
[④ 前端] 人脉库页 + 招标匹配推荐 + 意向列表
```

### 实施顺序
1. **人脉库模块**（本期）：数据模型 → samples 初始化 → 更新方案 → 招标匹配接口
2. 招标源配置 + 定时任务：web_source 加发改委等来源 → scheduler 定时抓
3. intent_notice 结构化 + 意向推荐增强
4. 统一关系视图 + 前端页面

## 五、招标信息源接入评估

见 `docs/archive/tender-sources-evaluation.md`（独立文档，含 8 个源实测结果）。
