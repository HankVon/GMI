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
]

# 启动时需确保存在的表(整文件执行 CREATE TABLE IF NOT EXISTS)
_CREATE_TABLE_SQL_FILES: list[str] = [
    "web_clue_ddl.sql",
    "bid_notice_ddl.sql",
    "entity_relation_ddl.sql",
    "business_network_ddl.sql",
    "intent_notice_ddl.sql",
    "project_clue_ddl.sql",
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


def _ensure_tables(db: Session) -> None:
    """启动时确保新增业务表存在(执行 sql/ 下的 CREATE TABLE IF NOT EXISTS)。"""
    sql_dir = Path(__file__).resolve().parent.parent.parent.parent / "sql"
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
            for stmt in sql_body.split(";"):
                stmt = stmt.strip()
                if stmt:
                    db.execute(text(stmt))
            db.commit()
            logger.info("[migrate] ensured tables from %s", fname)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.warning("[migrate] skip %s: %s", fname, e)


def run_migrations(db: Session) -> None:
    """启动时执行幂等迁移(仅补列, 不破坏数据)。"""
    _ensure_tables(db)
    for table, column, ddl in _ADD_COLUMNS:
        try:
            # DDL 拼接前校验标识符合法性(表名/列名/列定义均来自硬编码列表, 双保险)
            if not _IDENT_RE.match(table) or not _IDENT_RE.match(column):
                logger.warning("[migrate] skip unsafe identifier: %s.%s", table, column)
                continue
            if _column_exists(db, table, column):
                logger.info("[migrate] column %s.%s already exists, skip", table, column)
                continue
            db.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {ddl}"))
            db.commit()
            logger.info("[migrate] added column %s.%s", table, column)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.warning("[migrate] skip column %s.%s: %s", table, column, e)
