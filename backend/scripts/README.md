# 后端运维脚本

一次性/按需执行的运维脚本集合。**不属于应用启动链路**，不会被 `app/main.py` 调用。

---

## ⚠️ 执行前必读

> **目录状态**：本目录目前为**平铺**，脚本按**文件名前缀**分类（下表的小节即分类）。
> 之所以暂不分子目录：12 个脚本内有 `sys.path.insert(0, Path(__file__).resolve().parent.parent)`，
> 依赖「脚本位于 `backend/scripts/` 下、上两级即 `backend/`」这一前提，子目录化需同步改成 3 级。
> 若后续统一迁移，改法为 `.parent.parent` → `.parents[2]`，并在容器内按新路径调用。

1. **绝大多数脚本要在容器内跑**，因为它们 import `app.*` 且连 `mysql` / `redis` / `neo4j` 这些容器名：
   ```powershell
   docker exec -i ssm-backend python <脚本>          # 容器内，脚本需能读到
   ```
   容器内 backend 代码位于 `/app`，`sql/` 位于 `/sql`。
2. **本机直接跑会失败**：本机 Python 3.14 与 SQLAlchemy 有 ORM 兼容问题，任何 `import app.models` 的脚本都跑不起来。
   需要查库时用原生 SQL 或 `docker exec ssm-mysql mysql ...`。
3. **凡涉及写库的脚本都遵循「只填空、不覆盖」原则**（尊重人工策展数据），除非脚本注释明确说明会覆盖。
4. 标记「幂等」的脚本可重复执行；未标记的请先看清副作用。

---

## 一、数据回填类（`backfill_*`）

| 脚本 | 用途 | 幂等 | 备注 |
|---|---|---|---|
| `backfill_intent_fields.py` | 回填 `intent_notice` / `opportunity` 的空缺字段（金额 / 联系人 / 西藏地市） | ✅ 仅填 NULL | **原生 SQL 写法，本机可直接跑**，是「本机如何安全写库」的模板 |
| `backfill_company_cats.py` | 按新国标三套分类回填所有活跃单位（`company_type` / `industry` / `ownership`） | ✅ | 已有标准枚举值时保留，尊重人工/导入值 |
| `backfill_bid_attachments.py` | 补抓标讯公告附件链接（历史上采集器丢弃了附件区 `<a href>`） | ✅ | |
| `backfill_neo4j.py` | 把 MySQL 存量数据全量回填到 Neo4j 知识图谱 | ✅ | 需 Neo4j 可用，否则降级 |

## 二、种子数据类（`seed_*`）

| 脚本 | 用途 | 幂等 |
|---|---|---|
| `seed_company_fields.py` | 补全 `company` 实体的企查查字段元数据（仅插入缺失字段） | ✅ |
| `seed_company_std_cats.py` | 按国家标准初始化公司三套分类的 `option_set` 与 `field_metadata` | ✅ |
| `seed_person_project_fields.py` | 补全 `person` / `project` 字段元数据，使其像 `company` 一样可在「字段管理」中维护 | ✅ |
| `seed_project_category.py` | 为项目创建「类别」选项集与字段元数据 | ✅ |
| `seed_web_sources_chuanzang.sql` | 数据源聚焦川藏（四川 + 西藏）：移除非川藏源、启用川藏源、新增深度源 | ✅ 按 name 去重 |
| `seed_web_sources_chuanzangxin.sql` | 数据源聚焦西部三省（四川 + 西藏 + 新疆），并恢复误删的新疆两源 | ✅ |

## 三、抓取相关

| 脚本 | 用途 | 运行方式 |
|---|---|---|
| `full_crawl.py` | **全量抓取**（后台）：遍历全部启用源，限制每源页数，实时写进度日志，结束后对本次新入库 `web_clue` 做噪声比分类 | `docker exec -d ssm-backend python full_crawl.py` |
| `run_crawl_sample.py` | **抽样抓取**：对三省代表性数据源各抓一份，随后抽样 `web_clue` 看入库质量 | `docker exec -i ssm-backend python run_crawl_sample.py` |
| `check_urls.py` | 批量探活数据源 URL，区分「域名失效 DEAD」与「可访问 ALIVE/HTTP 码」 | `docker exec ssm-backend python check_urls.py` |

## 四、数据源侦察类（`recon_*`，一次性）

| 脚本 | 用途 |
|---|---|
| `recon_sc_cities.py` | 1) 拉省平台全部市州官方 URL；2) 探测凉山平台列表页；3) 确认资阳官方 URL |
| `recon_pzh_ls_zy.py` | 探测攀枝花 / 凉山 / 资阳的交易信息列表页 URL |
| `recon_zy_sc.py` | 1) 资阳 Vue SPA：从 JS 找接口/列表路由；2) 省平台 `ggzyjy.sc.gov.cn` 各市州城市码（含凉山） |
| `recon_zy2.py` | 资阳：试官方站根域名 + 用浏览器渲染 `zyzwjy.cn` 看公告列表链接 |

> 这四个是**新增数据源时如何找列表页/接口的方法记录**，不是日常运维脚本。

## 五、验证脚本

| 脚本 | 用途 |
|---|---|
| `http_verify_383.py` | 走 HTTP 调容器内 backend（8200），用 admin 登录拿 JWT 后调 `/api/v1/tenders/383/detail`，验证新代码已生效且全链路打通 |
| `verify_tender_detail.py` | 真实环境验证 `TenderDetailService.build()` 完整链路 |
| `test_marketing.ps1` | 营销智能体端到端验证（开发用）：`pwsh -File test_marketing.ps1 [baseUrl]`，默认 `http://127.0.0.1:8101` |

## 六、清理脚本

| 脚本 | 用途 |
|---|---|
| `clean_old_company_type_options.py` | 清理 `option_set:company_type` 中的旧版业务角色选项（业主/施工/监理/设计院/政府/供应商/事业单位/合作伙伴），替换为国标企业类型 |

## 七、临时查询 `_` 前缀（一次性，可随时删除）

| 文件 | 用途 |
|---|---|
| `_q3.sql` | 查询 `web_source` 中若干源的 keywords / regions / 抓取配置 |
| `_revert_id57.sql` | 把 `web_source` id=57 的 `max_pages` 回滚为 5 |
| `_zy_clue.sql` | 统计资阳线索数量 + 查看 id=57 源配置 |
| `_zy_after.sql` | 资阳抓取后的核查：源状态 + 线索数 + 按 source 分组统计 |
