# GMI 功能完整性整改总结

> 整理时间: 2026-08-31
> 来源: `docs/archive/GMI修改意见方案.md`、`docs/archive/GMI功能完整性审核报告.md`（已归档）
> 范围: 2026-08-31 功能完整性审核与整改「本回合」结果 —— P0 严重缺陷 7 项 / P1 一般问题 11 项 / P2 优化建议 9 项，共 27 项

## 一、总览

| 级别 | 数量 | 含义 | 整改结果 |
|---|---|---|---|
| P0 严重缺陷 | 7 | 核心主流程不可用、数据越权、全新环境无法部署 | 前期回查确认已全部在代码中修复 |
| P1 一般问题 | 11 | 功能可用但结果错误 / 闭环缺半段 / 承接缺失 | 全部修复；本回合补充落地 **P1-5 人员关联图谱** |
| P2 优化建议 | 9 | 孤儿接口、死路由、stub、占位页、体验瑕疵 | 逐条处置（见 §4） |

## 二、P0 严重缺陷（7 项，已全部修复）

| 编号 | 问题 | 模块 |
|---|---|---|
| P0-1 | 人脉"我"节点无法绑定，`POST /network/me` 无前端入口 | 人脉图谱 / 账号体系 |
| P0-2 | `tenders_search.py` 整模块未在 `main.py` 注册，订阅 404 被 catch 吞掉仍弹"已同步" | 标讯中心 / 订阅 |
| P0-3 | 单位 Excel 导入/导出 100% 失败（`entity-type="company"` 未走 `apiPath()` 映射） | 单位管理 |
| P0-4 | 收藏/监控无查看页（8 个 tab 全为 Placeholder），后端无用户级收藏列表端点 | 标讯 / 个人中心 |
| P0-5 | `persons.py` 列表未接 `resolve_scope`，部门/个人范围用户可见全部人员（**数据越权**） | 人员管理 / 权限 |
| P0-6 | docker-compose 将 `./sql` 整体挂入 initdb，按字母序 `010_data_scope.sql` 先于 `init_ddl.sql`，全新卷初始化必失败 | 部署 / 数据库 |
| P0-7 | 收藏/监控/订阅等"写成功"提示在失败分支仍弹出（**假成功**） | 全局交互 |

## 三、P1 一般问题（11 项，已全部修复；本回合补 P1-5）

| 编号 | 问题 | 模块 |
|---|---|---|
| P1-1 | 订阅 `enabled` 后端 `bool()` / 前端 `=== 1` 类型错位：活跃订阅恒 0、"已停用"标签永不显示、停用停不掉 | 商机 / 订阅 |
| P1-2 | 收藏状态回显错位：`silentApi` 裸 axios 无解包拦截器，整包 setState | 标讯详情 |
| P1-3 | 标讯附件下载 `window.open` 丢 Bearer 头必 401 | 标讯管理 |
| P1-4 | 企查查补全"假成功"：`res.success \|\| res.data` 恒真 | 单位详情 |
| P1-5 | 知识图谱（`/knowledge/*`）与人脉库（`/biz-network/*`）后端整块可用但**前端零调用** → 本回合补 `PersonGraph.vue` | 知识图谱 / 人脉库 |
| P1-6 | 前台订阅结果点击 `window.open('#opportunity-x')` 只开空白页 | 前台订阅 |
| P1-7 | 订阅条件 `excludeKeywords/bidMethods/noticeTypes/sources` 存了不消费，过滤形同虚设 | 前台订阅 / 商机检索 |
| P1-8 | `ProjectDetail` "去行业情报" push 到不存在的 `/workspace/search` → 落 404 页 | 项目详情 |
| P1-9 | `migrate.py` 清单缺 5 个菜单/权限 SQL（012、013_role_menu_defaults、014、016、017_opportunity_admin）→ 非最新 dump 建的库菜单永缺、路由 403 | 数据库迁移 |
| P1-10 | 迁移失败静默（仅 `logger.exception`），缺表缺列到运行时 500 才暴露 | 数据库迁移 / 可观测性 |
| P1-11 | `Subscriptions.vue` "拟建信息/招投标信息" tab 不参与过滤——假多 Tab | 前台订阅 |

## 四、P2 优化建议（9 项，逐条处置）

| 编号 | 问题 | 处置 | 结果 |
|---|---|---|---|
| P2-1 | 后端孤儿接口无前端承接（`/bids/my-subscriptions`、`/bids/stats`、`/bids/intent-recommendations`、`/bids/rebuild`、`/admin/bids/review-queue`、`/intent/ai-analysis`、`/reports/aggregate`、`/marketing/opportunities`、`/marketing/topics`、`/search`，共 10 个） | 部分下线 | 下线 `/knowledge/relations`、`/knowledge/path`（全仓零调用）；其余保留待专项清理 |
| P2-2 | 跟踪线索"已读"无前端入口 | 已修复 (#19) | `ProjectDetail.vue` / `IntelligenceDetail.vue` 加「标记已读」按钮并本地置 `is_read`；端到端验证通过 |
| P2-3 | `web_clue` 导出不在 excel 白名单，点击必 400 | 已修复 (#20) | `excel.py` 白名单加 `web_clues` + `WebClue` 数据分支（`SimpleNamespace` 构造 9 列导出元信息）；`WebClue.vue` 加「导出 Excel」 |
| P2-4 | `/excel/export` 仅验登录不验 `api_excel` 权限 | 无需处理 | 复核确认 `require_permission("api_excel")` 已存在 |
| P2-5 | `/workspace/combined-query` 在 router 中重复定义两次 | 无需处理 | 复核确认 router 无重复定义 |
| P2-6 | `/workspace/intents?highlight=` 参数 `IntentList` 完全不读取 | 无需处理 | 后端 `intents` 本不支持高亮语义，非缺陷 |
| P2-7 | 招标文件原文下载为明示 stub | 已修复 (#24) | `BidDetail.downloadFiles` 改用采集到的 `bid.attachments[0].url`，与同页附件一致 |
| P2-8 | 报表中心有后端（`/reports/aggregate`）无 UI | 已修复 (#25) | 新增 `ReportsCenter.vue`：实体×维度×指标筛选 + ECharts 柱状图 + 明细表 + Excel 导出；路由 `/workspace/reports`（仅登录）+ 侧边栏「报表中心」入口（与统计中心同 `menu_dashboard` 门控） |
| P2-9 | 个人中心 6 个占位页（最近访问/订单/报告/反馈/VIP/认证）缺明确产品去向 | 已清理 | 删除 6 条路由 + 菜单项 + `activeMenu`/`onMenuSelect` 映射 + 孤儿 `Placeholder.vue` |

## 五、本回合重点交付

- **报表中心（P2-8 / #25）**：补齐"有后端无前端"缺口。`GET /api/v1/reports/aggregate` 支持 `entity_type`(project/person/company/bid) × `group_by`(month/quarter/year/status/department/province) × `metric`(count/amount)，UI 提供筛选 + ECharts 柱状图 + 明细表 + Excel 导出。API 级冒烟通过。
- **人员关联图谱（P1-5）**：新增 `PersonGraph.vue`，复用 `/network/person-neighbors`（增量补 `company_id`/`person_id`），挂载至 `PersonProfile.vue`，接通此前零调用的知识图谱/人脉库后端。
- **跟踪线索已读（P2-2 / #19）**：补齐"已读"操作闭环，端到端验证 `is_read` False→True。
- **Web 线索导出（P2-3 / #20）**：`web_clue` 纳入 excel 白名单，产出 9 列 xlsx。
- **招标文件真实下载（P2-7 / #24）**：去除 stub，改用采集附件 URL。
- **孤儿接口清理（P2-1）**：下线零调用接口，收敛攻击面。
- **个人中心瘦身（P2-9）**：删除 6 个无去向占位页及其路由/菜单。

## 六、验证

- 标记已读：端到端通过（PROJ=10 / CLUE_ID=424，`is_read` False→True）。
- Web 线索导出：`api_excel` 鉴权生效（测试账号 `viewer` 无 `api_excel` 返回 403；持 `api_excel` 权限账号得到 9 列 xlsx）。
- 报表中心：`/api/v1/reports/aggregate` 多组合（project/month/count、project/status/amount、company/province/count）均返回正确 `{success,data,meta}` 结构。

## 七、参考

- 原始审计/整改文档（已归档）：`docs/archive/GMI修改意见方案.md`、`docs/archive/GMI功能完整性审核报告.md`
- 技术设计：`docs/p0-technical-design.md`
