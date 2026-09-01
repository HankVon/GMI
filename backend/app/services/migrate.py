"""轻量启动迁移 — 为已有表补充新列(幂等)。

项目采用 init_ddl.sql 建表(非 alembic), 因此新增列需要在启动时幂等补齐。
MySQL 8 不支持 ADD COLUMN IF NOT EXISTS, 故先查 information_schema 判断列是否存在。
"""
import logging
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("migrate")

# 白名单校验: 表名/列名仅允许纯标识符, 防止拼接进 DDL 的注入风险
_IDENT_RE = re.compile(r"^[A-Za-z0-9_]+$")

# (表名, 列名, 列定义)
_ADD_COLUMNS: list[tuple[str, str, str]] = [
    (
        "bid_notice",
        "agency",
        "VARCHAR(512) DEFAULT NULL COMMENT '采购代理机构名称'",
    ),
    # ── 标讯后台管理: 生命周期/分类维度/审核发布留痕 ──
    (
        "bid_notice",
        "source_id",
        "BIGINT DEFAULT NULL COMMENT '来源站点 id(web_source)'",
    ),
    (
        "bid_notice",
        "status",
        "VARCHAR(32) NOT NULL DEFAULT 'published' COMMENT '生命周期状态:draft/pending/approved/rejected/published/offline'",
    ),
    (
        "bid_notice",
        "category",
        "VARCHAR(64) DEFAULT NULL COMMENT '项目分类(工程/服务/货物)'",
    ),
    (
        "bid_notice",
        "industry",
        "VARCHAR(128) DEFAULT NULL COMMENT '行业类型(option_set:bid_industry)'",
    ),
    (
        "bid_notice",
        "purchase_way",
        "VARCHAR(64) DEFAULT NULL COMMENT '采购方式(公开招标/邀请招标/竞争性谈判/单一来源/询价/其他)'",
    ),
    (
        "bid_notice",
        "price_type",
        "VARCHAR(32) DEFAULT NULL COMMENT '询价方式(单价/总价)'",
    ),
    (
        "bid_notice",
        "budget_min",
        "FLOAT DEFAULT NULL COMMENT '预算金额下限(万元)'",
    ),
    (
        "bid_notice",
        "budget_max",
        "FLOAT DEFAULT NULL COMMENT '预算金额上限(万元)'",
    ),
    (
        "bid_notice",
        "submitted_by",
        "BIGINT DEFAULT NULL COMMENT '提交审核人 user_id'",
    ),
    (
        "bid_notice",
        "submitted_at",
        "DATETIME DEFAULT NULL COMMENT '提交审核时间'",
    ),
    (
        "bid_notice",
        "reviewed_by",
        "BIGINT DEFAULT NULL COMMENT '审核人 user_id'",
    ),
    (
        "bid_notice",
        "reviewed_at",
        "DATETIME DEFAULT NULL COMMENT '审核时间'",
    ),
    (
        "bid_notice",
        "review_comment",
        "TEXT DEFAULT NULL COMMENT '审核意见'",
    ),
    (
        "bid_notice",
        "publish_at",
        "DATETIME DEFAULT NULL COMMENT '后台实际发布时间'",
    ),
    (
        "bid_notice",
        "publish_by",
        "BIGINT DEFAULT NULL COMMENT '发布人 user_id'",
    ),
    (
        "bid_notice",
        "created_by",
        "BIGINT DEFAULT NULL COMMENT '创建人 user_id(后台录入)'",
    ),
    (
        "bid_notice",
        "updated_by",
        "BIGINT DEFAULT NULL COMMENT '最后编辑人 user_id'",
    ),
    (
        "project_member",
        "stage",
        "VARCHAR(64) NOT NULL DEFAULT '' COMMENT '所属阶段(关联 option_set:project_progress_stage, 空=全程/不限)'",
    ),
    (
        "project_company",
        "stage",
        "VARCHAR(64) NOT NULL DEFAULT '' COMMENT '所属阶段(关联 option_set:project_progress_stage, 空=全程/不限)'",
    ),
    (
        "web_source",
        "query_config",
        "TEXT DEFAULT NULL COMMENT '查询式抓取配置JSON(OCR验证码/接口关键字等)'",
    ),
    (
        "web_source",
        "llm_enhance",
        "VARCHAR(32) NOT NULL DEFAULT 'filter' COMMENT 'LLM增强模式: filter/extract/summary/all/空=关闭'",
    ),
    (
        "tender_match",
        "valid_until",
        "DATETIME DEFAULT NULL COMMENT '推荐有效期截止(超期自动标记过期)'",
    ),
    (
        "tender_match",
        "is_expired",
        "TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否已过期(定时任务维护)'",
    ),
    (
        "sys_notification",
        "status",
        "VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT '处理状态:pending/processing/resolved/closed'",
    ),
    (
        "sys_role",
        "data_scope_rule",
        "VARCHAR(16) DEFAULT NULL COMMENT '角色默认数据范围:ALL/DEPT_TREE/DEPT_ONLY/OWN/CUSTOM, NULL=未启用'",
    ),
    (
        "sys_role",
        "scope_dept_ids",
        "JSON DEFAULT NULL COMMENT '角色级部门范围ID列表'",
    ),
    (
        "sys_user",
        "data_scope_rule",
        "VARCHAR(16) DEFAULT NULL COMMENT '用户级数据范围, NULL=继承角色'",
    ),
    (
        "sys_user",
        "scope_dept_ids",
        "JSON DEFAULT NULL COMMENT '用户级部门范围ID列表'",
    ),
    (
        "subscription_task",
        "product_type",
        "VARCHAR(32) NOT NULL DEFAULT 'tender' COMMENT '订阅子产品类型:tender(标讯)/opportunity(商机)'",
    ),
    # ── 情报中心后台管理: intent_notice 审核/发布/展示扩展 ──
    (
        "intent_notice",
        "wf_status",
        "VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '流转状态 draft/pending/approved/published/offline/rejected'",
    ),
    (
        "intent_notice",
        "review_comment",
        "VARCHAR(512) DEFAULT NULL COMMENT '审核意见'",
    ),
    (
        "intent_notice",
        "reviewer_id",
        "BIGINT DEFAULT NULL COMMENT '审核人id'",
    ),
    (
        "intent_notice",
        "reviewed_at",
        "DATETIME DEFAULT NULL COMMENT '审核时间'",
    ),
    (
        "intent_notice",
        "publisher_id",
        "BIGINT DEFAULT NULL COMMENT '发布人id'",
    ),
    (
        "intent_notice",
        "offline_at",
        "DATETIME DEFAULT NULL COMMENT '下架时间'",
    ),
    (
        "intent_notice",
        "stage",
        "VARCHAR(64) DEFAULT NULL COMMENT '项目阶段 设计/动工/竣工/竣工验收'",
    ),
    (
        "intent_notice",
        "dataset_type",
        "VARCHAR(32) NOT NULL DEFAULT 'project' COMMENT '数据集 project/proposed/landTrade'",
    ),
    (
        "intent_notice",
        "ext_attrs",
        "JSON DEFAULT NULL COMMENT '扩展字段JSON(工程地址/招标类型/资金来源/建筑规模/层数/建设性质/项目代码等)'",
    ),
    (
        "intent_notice",
        "created_by",
        "BIGINT DEFAULT NULL COMMENT '创建人id'",
    ),
    # ── 前台 CMS: 按页面区分管理 ──
    (
        "cms_block",
        "page_key",
        "VARCHAR(32) NOT NULL DEFAULT 'home' COMMENT '所属前台页面: home/about/contact/solutions/intelligence/datacenter'",
    ),
]

# 启动时需确保存在的表(整文件执行 CREATE TABLE IF NOT EXISTS)
_CREATE_TABLE_SQL_FILES: list[str] = [
    "web_clue_ddl.sql",
    "bid_notice_ddl.sql",
    "bid_review_record_ddl.sql",
    "bid_attachment_ddl.sql",
    "entity_relation_ddl.sql",
    "business_network_ddl.sql",
    "intent_notice_ddl.sql",
    "project_clue_ddl.sql",
    "geo_ddl.sql",
    "content_ddl.sql",
    "intent_ai_cache_ddl.sql",
    "intent_attachment_ddl.sql",
    "intent_contact_ddl.sql",
    "intelligence_category_ddl.sql",
    "industry_data_ddl.sql",
    "010_data_scope.sql",
    "011_user_permission.sql",
    # ★ P1-9: 补全被遗漏的菜单/角色权限 INSERT(幂等), 否则从旧 dump 恢复的库缺菜单、路由 403
    "012_menu_permissions.sql",
    "013_role_menu_defaults.sql",
    "014_fix_menu_names.sql",
    "016_report_menu.sql",
    "017_opportunity_admin.sql",
    "013_bid_admin_permissions.sql",
    "015_notification.sql",
    "018_bid_category_seed.sql",
    "019_bid_admin_ext_permissions.sql",
    "subscription_task_ddl.sql",
    "user_entity_action_ddl.sql",
    "opportunity_ddl.sql",
    "017_intent_admin.sql",
    "cms_ddl.sql",
    # ★ A4: 收藏与标签表
    "favorite_tag_ddl.sql",
]


def _column_exists(db: Session, table: str, column: str) -> bool:
    """查询 information_schema 判断列是否存在。"""
    row = db.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).scalar()
    return bool(row)


def _ensure_tables(db: Session) -> tuple[int, int]:
    """启动时确保新增业务表存在(执行 sql/ 下的 CREATE TABLE IF NOT EXISTS)。

    逐语句独立 try: 单条 DDL 失败(幂等冲突/已存在列)只告警, 不阻断后续建表;
    跳过 ``USE <db>`` 前缀语句(连接库由 DATABASE_URL 决定, 避免污染连接池默认库)。
    返回 (ok, skipped) 统计, 供启动自检与 health 暴露。
    """
    sql_dir = Path(__file__).resolve().parent.parent.parent.parent / "sql"
    total_ok = total_skip = 0
    for fname in _CREATE_TABLE_SQL_FILES:
        fpath = sql_dir / fname
        if not fpath.exists():
            logger.warning("[migrate] sql file not found: %s", fpath)
            continue
        try:
            # 逐行去掉注释后拼成语句再按 ; 切分(避免整段被 -- 注释行误判)
            clean_lines = [
                line for line in fpath.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.strip().startswith("--")
            ]
            sql_body = "\n".join(clean_lines)
            ok = fail = 0
            for stmt in sql_body.split(";"):
                stmt = stmt.strip()
                if not stmt:
                    continue
                if stmt.upper().startswith("USE "):
                    continue
                try:
                    db.execute(text(stmt))
                    db.commit()
                    ok += 1
                except Exception as e:  # noqa: BLE001 - 单条 DDL 失败仅告警
                    db.rollback()
                    fail += 1
                    logger.warning("[migrate] skip stmt from %s: %s", fname, e)
            total_ok += ok
            total_skip += fail
            logger.info(
                "[migrate] ensured tables from %s (ok=%d, skipped=%d)",
                fname, ok, fail,
            )
        except Exception as e:  # noqa: BLE001 - 文件级异常(如编码)仅告警
            logger.warning("[migrate] skip %s: %s", fname, e)
    return total_ok, total_skip


def _migrate_legacy_intent_status(db: Session) -> int:
    """历史意向数据兼容: 旧系统无审核流程, 存量数据应视为已发布。

    幂等逻辑: 仅当全库没有任何人工流转标记(published/approved/offline/pending)时,
    才将存量 draft 记录批量标记为 published, 保证前台继续展示历史情报。
    返回实际迁移条数。
    """
    try:
        n_draft = db.execute(
            text("SELECT COUNT(*) FROM intent_notice WHERE is_deleted=0 AND wf_status='draft'")
        ).scalar() or 0
        n_marked = db.execute(
            text("SELECT COUNT(*) FROM intent_notice WHERE is_deleted=0 "
                 "AND wf_status IN ('published','approved','offline','pending')")
        ).scalar() or 0
        if n_draft and not n_marked:
            db.execute(text(
                "UPDATE intent_notice SET wf_status='published', "
                "published_at=COALESCE(published_at, updated_at) "
                "WHERE is_deleted=0 AND wf_status='draft'"
            ))
            db.commit()
            logger.info("[migrate] 历史意向数据迁移为已发布: %d 条", n_draft)
            return n_draft
        return 0
    except Exception as e:  # noqa: BLE001 - 历史数据迁移失败不阻断启动
        db.rollback()
        logger.warning("[migrate] 历史意向状态迁移失败: %s", e)
        return 0


def run_migrations(db: Session) -> dict:
    """启动时执行幂等迁移(仅补列, 不破坏数据)。

    返回结构化结果, 供启动自检日志与 /api/v1/health 的 migrations 字段复用。
    """
    stats: dict = {
        "tables_ok": 0,
        "tables_skipped": 0,
        "columns_added": [],
        "columns_skipped": [],
        "legacy_intent_migrated": 0,
        "errors": [],
    }
    t_ok, t_skip = _ensure_tables(db)
    stats["tables_ok"] = t_ok
    stats["tables_skipped"] = t_skip
    for table, column, ddl in _ADD_COLUMNS:
        try:
            # DDL 拼接前校验标识符合法性(表名/列名/列定义均来自硬编码列表, 双保险)
            if not _IDENT_RE.match(table) or not _IDENT_RE.match(column):
                logger.warning("[migrate] skip unsafe identifier: %s.%s", table, column)
                stats["columns_skipped"].append(f"{table}.{column}(unsafe)")
                continue
            if _column_exists(db, table, column):
                logger.info("[migrate] column %s.%s already exists, skip", table, column)
                stats["columns_skipped"].append(f"{table}.{column}(exists)")
                continue
            db.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {ddl}"))
            db.commit()
            logger.info("[migrate] added column %s.%s", table, column)
            stats["columns_added"].append(f"{table}.{column}")
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.warning("[migrate] skip column %s.%s: %s", table, column, e)
            stats["errors"].append(f"{table}.{column}: {e}")
    stats["legacy_intent_migrated"] = _migrate_legacy_intent_status(db)
    return stats
