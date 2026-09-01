# GMI 文档总索引

> 全部文档按 **ops（运维部署）/ design（设计）/ guides（使用）/ reports（总结）/ archive（留档）** 五类归档。
> 状态标记：✅ 现行有效 ｜ ⚠️ 部分过时（内容基本可用，但有旧路径/旧信息）｜ 📌 历史留档（不建议照做）

---

## 总览

| 分类 | 数量 | 说明 |
|---|---|---|
| [根目录](#根目录) | 2 | 架构总览 + 仓库整理方案 |
| [ops/](#一运维部署-ops) | 9 | 启动、部署、备份恢复、域名隧道、单位机/家里机 |
| [design/](#二设计文档-design) | 8 | 后台/后端设计、官网数据方案、演进规划 |
| [guides/](#三使用指南-guides) | 3 | 人脉库、营销智能体、改造指导 |
| [reports/](#四工作总结-reports) | 4 | 各阶段功能改造与接入总结 |
| [archive/](#五留档-archive) | 6 | 已过时或仅作依据的调研/审核报告 |

---

## 根目录

| 文档 | 说明 | 状态 |
|---|---|---|
| [`architecture.md`](architecture.md) | 架构设计文档：总体架构图、分层、数据模型、技术选型 | ✅ |
| [`项目文件整理方案.md`](项目文件整理方案.md) | 2026-09-01 仓库文件盘点、归位与清理方案（含决策记录与待办） | ✅ |

---

## 一、运维部署 `ops/`

| 文档 | 说明 | 状态 |
|---|---|---|
| [`STARTUP.md`](ops/STARTUP.md) | 启动与部署指南：Docker Compose 五容器的启动顺序、端口、健康检查 | ✅ 首选入口 |
| [`OPS.md`](ops/OPS.md) | 运维手册（Runbook）：日常巡检、常见故障处理、容器操作 | ✅ |
| [`backup-restore.md`](ops/backup-restore.md) | 数据备份与恢复手册：MySQL dump / uploads / Redis RDB / Neo4j 的备份与还原步骤 | ✅ |
| [`code-restart-guide.md`](ops/code-restart-guide.md) | 改完代码如何生效：区分「改前端」与「改后端」的不同重启方式 | ✅ |
| [`remote-deploy.md`](ops/remote-deploy.md) | 远程协作部署手册：家里机 ↔ 单位机实时数据的连接方式 | ✅ |
| [`home-machine-sync.md`](ops/home-machine-sync.md) | 家里机同步步骤：只跑前端，通过 `https://sct5dzd.xyz` 访问单位机数据 | ✅ |
| [`domain-access-deploy.md`](ops/domain-access-deploy.md) | 固定域名部署：Cloudflare Tunnel + `sct5dzd.xyz` + 开机自启任务计划 | ✅ |
| [`unit-machine-setup.md`](ops/unit-machine-setup.md) | 单位机部署任务清单（面向协作 Agent） | ⚠️ 内含旧路径 `D:\Geology\SSM`，应读为 `D:\Geology\GMI` |
| [`server-deploy-kunpeng-ascend.md`](ops/server-deploy-kunpeng-ascend.md) | 国产服务器部署：鲲鹏 920s + Atlas 300I Duo + Ubuntu，含 `docker-compose.server.yml` 适配版 | ✅ 特定硬件 |

---

## 二、设计文档 `design/`

| 文档 | 说明 | 状态 |
|---|---|---|
| [`p0-technical-design.md`](design/p0-technical-design.md) | GMI P0 改造技术设计（对标建设通），2026-08 | ✅ |
| [`bid-admin-backend-design.md`](design/bid-admin-backend-design.md) | 标讯中心后台与后端设计：由前台 `/site/bids` 反向推导，含数据契约 | ✅ |
| [`intelligence-admin-backend-design.md`](design/intelligence-admin-backend-design.md) | 项目商机（原情报动态）后台设计：字段/接口/权限/表结构对齐 | ✅ |
| [`admin-system-design-from-site.md`](design/admin-system-design-from-site.md) | 由前台反向推导的整体后台管理系统与后端服务设计 | ✅ |
| [`site_public_data_requirements.md`](design/site_public_data_requirements.md) | 对外官网的数据接入方案与业务需求 | ✅ |
| [`site-reference-guidance.md`](design/site-reference-guidance.md) | 官网数据产品改造指导报告（2026-08-27 调研） | ✅ |
| [`system-integration-plan.md`](design/system-integration-plan.md) | 系统现状梳理 +「提前获取招标信息 → 人脉库 → 关联匹配」整合方案 | ✅ |
| [`geo-marketing-agent-plan.md`](design/geo-marketing-agent-plan.md) | 从「招标情报数据中台」演进到「GEO 营销智能体」的规划 | ✅ 规划 |

---

## 三、使用指南 `guides/`

| 文档 | 说明 | 状态 |
|---|---|---|
| [`business-network-guide.md`](guides/business-network-guide.md) | 人脉库使用与更新：多源（项目/人员/单位/中标/三元组）关系视图的初始化与持续更新 | ✅ |
| [`marketing-agent-guide.md`](guides/marketing-agent-guide.md) | 营销智能体三大模块的使用与接入 | ✅ |
| [`gmi-renovation-guide.md`](guides/gmi-renovation-guide.md) | 系统改造指导（对标建设通，保留人脉网络差异化） | ✅ |

---

## 四、工作总结 `reports/`

| 文档 | 说明 | 状态 |
|---|---|---|
| [`GMI功能完整性整改总结.md`](reports/GMI功能完整性整改总结.md) | 2026-08-31 功能完整性整改的落地总结 | 📌 |
| [`分项查询-查人员与查项目经理功能改造总结.md`](reports/分项查询-查人员与查项目经理功能改造总结.md) | 2026-08-31 分项查询功能改造总结 | 📌 |
| [`工作总结-情报管线调通与收藏能力补齐.md`](reports/工作总结-情报管线调通与收藏能力补齐.md) | 2026-08-31 情报管线与收藏能力补齐总结 | 📌 |
| [`公共资源交易数据源接入工作总结.md`](reports/公共资源交易数据源接入工作总结.md) | 2026-08-31 公共资源交易数据源接入总结 | 📌 |

---

## 五、留档 `archive/`

> 这些文档是**当时决策的依据或一次性调研报告**，内容已落地或已过时，**不要照着执行**。

| 文档 | 说明 | 状态 |
|---|---|---|
| [`GMI功能完整性审核报告.md`](archive/GMI功能完整性审核报告.md) | 2026-08-31 功能完整性审核（46 个路由文件 + frontend 扫描），**已整改完毕** | 📌 |
| [`GMI修改意见方案.md`](archive/GMI修改意见方案.md) | 依据上述审核报告提出的修改意见，**P0/P1/P2 均已处置** | 📌 |
| [`cbi360-benchmark.md`](archive/cbi360-benchmark.md) | 建设通（hhb）深度调研报告，作为改造借鉴依据 | 📌 |
| [`参考站点体验与前台改造指导报告.md`](archive/参考站点体验与前台改造指导报告.md) | 前台数据产品改造指导（调研版） | 📌 |
| [`tender-sources-evaluation.md`](archive/tender-sources-evaluation.md) | 2026-08-14 招标信息源网站可用性实测评估 | 📌 |
| [`lead-time-verification.md`](archive/lead-time-verification.md) | 2026-08-19 商机提前量验证报告（真实数据） | 📌 |

---

## 附：文档写作约定

新增文档请按用途放入对应子目录，并在本文件的对应表格中补一行（文档名 / 一句话说明 / 状态）。
状态为 ⚠️ 或 📌 时，建议在文档开头用引用块说明「过时点」与「替代文档」。
