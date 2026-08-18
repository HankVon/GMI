"""定时任务 — 意向源周期抓取 + 中标增量重建 + 人脉库同步 + 过期数据清理。

依赖 apscheduler; 若未安装则任务不启动(不影响主服务)。
启停: main.py startup 时 start_scheduler() / shutdown 时 stop_scheduler()。
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("scheduler")

_scheduler = None


def _job_crawl_intents():
    """每日抓取意向源(发改委/自然资源厅等) → intent_notice。"""
    try:
        from app.database import SessionLocal
        from app.services.intent_crawler import crawl_all_intent_sources
        db = SessionLocal()
        try:
            result = crawl_all_intent_sources(db)
            logger.info("[scheduler] 意向源抓取完成: %s", result)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("[scheduler] 意向抓取失败: %s", e)


def _job_rebuild_network():
    """每 3 天重建人脉库(边+专长), 增量覆盖新项目/人员/中标。"""
    try:
        from app.database import SessionLocal
        from app.services.business_network import init_network
        db = SessionLocal()
        try:
            result = init_network(db)
            logger.info("[scheduler] 人脉库重建完成: %s", result)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("[scheduler] 人脉库重建失败: %s", e)


def _job_clean_stale_clues():
    """每日清理: 标记已过截止时间的线索为过期(status=expired)。

    线索 meta.expireTime 已过 → status=expired(软标记, 可人工恢复, 不物理删除)。
    同时刷新 tender_match 的有效期/过期标记。
    """
    try:
        from app.database import SessionLocal
        from sqlalchemy import select
        from app.models.web_clue import WebClue
        from app.services.business_network import refresh_match_validity
        db = SessionLocal()
        try:
            now = datetime.now()
            expired = 0
            clues = db.execute(
                select(WebClue).where(WebClue.is_deleted == False, WebClue.status == "accepted")
            ).scalars().all()
            for c in clues:
                meta = c.meta if isinstance(c.meta, dict) else {}
                expire_raw = meta.get("expireTime") or meta.get("expire_time")
                if not expire_raw:
                    continue
                try:
                    expire_dt = _parse_dt(expire_raw)
                except Exception:  # noqa: BLE001
                    continue
                if expire_dt and expire_dt < now:
                    c.status = "expired"
                    expired += 1
            db.commit()
            # 刷新招标匹配有效期
            validity = refresh_match_validity(db, now)
            logger.info("[scheduler] 过期清理完成: 线索标记过期 %s, 匹配有效性 %s", expired, validity)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("[scheduler] 过期清理失败: %s", e)


def _parse_dt(s) -> datetime:
    """解析线索截止时间字符串(宽松)。"""
    if not s:
        raise ValueError("empty")
    t = str(s).strip().replace("/", "-").replace("T", " ")
    t = t[:16]
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        return datetime.strptime(t, fmt)
    raise ValueError(f"bad fmt: {s}")


def _job_clean_invalid_network():
    """每周清理: 删除无效人脉数据。

    规则:
      1) tender_match: 已标记 ignored 且超过 30 天的 → 软删(保证匹配推荐质量)
      2) 过期匹配(valid_until 已过) 且 超过 60 天 → 软删(防堆积)
      3) intent_notice: status=expired 超过 90 天 → 软删
    """
    try:
        from app.database import SessionLocal
        from sqlalchemy import select
        from app.models.business_network import TenderMatch
        from app.models.intent_notice import IntentNotice
        db = SessionLocal()
        try:
            now = datetime.now()
            # 1) ignored 超 30 天的匹配
            cut_ignored = now - timedelta(days=30)
            ignored = db.execute(
                select(TenderMatch).where(
                    TenderMatch.is_deleted == False, TenderMatch.status == "ignored",
                    TenderMatch.updated_at < cut_ignored,
                )
            ).scalars().all()
            for m in ignored:
                m.is_deleted = True
            # 2) 过期超 60 天的匹配
            cut_expired = now - timedelta(days=60)
            expired_matches = db.execute(
                select(TenderMatch).where(
                    TenderMatch.is_deleted == False, TenderMatch.is_expired == True,
                    TenderMatch.valid_until < cut_expired,
                )
            ).scalars().all()
            for m in expired_matches:
                m.is_deleted = True
            # 3) expired 超 90 天的意向
            cut_intent = now - timedelta(days=90)
            intents = db.execute(
                select(IntentNotice).where(
                    IntentNotice.is_deleted == False, IntentNotice.status == "expired",
                    IntentNotice.updated_at < cut_intent,
                )
            ).scalars().all()
            for it in intents:
                it.is_deleted = True
            db.commit()
            logger.info(
                "[scheduler] 无效人脉清理完成: ignored匹配 %s, 过期匹配 %s, 过期意向 %s",
                len(ignored), len(expired_matches), len(intents),
            )
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("[scheduler] 无效人脉清理失败: %s", e)


def _job_track_projects():
    """每日增量: 把新抓取的 意向/招标/中标 线索自动归整到对应项目(防张冠李戴)。"""
    try:
        from app.database import SessionLocal
        from app.services.project_tracker import match_all_clues
        db = SessionLocal()
        try:
            result = match_all_clues(db)
            logger.info("[scheduler] 项目跟踪匹配完成: %s", result)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        logger.error("[scheduler] 项目跟踪匹配失败: %s", e)


def start_scheduler() -> None:
    """启动后台定时任务(幂等)。apscheduler 不可用时静默跳过。"""
    global _scheduler
    if _scheduler is not None:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("apscheduler 未安装, 定时任务不启用")
        return
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    # 意向源: 每天 03:00 抓取(避开白天访问高峰)
    _scheduler.add_job(_job_crawl_intents, "cron", hour=3, minute=0, id="crawl_intents",
                       replace_existing=True, max_instances=1)
    # 人脉库: 每 3 天凌晨 04:00 重建
    _scheduler.add_job(_job_rebuild_network, "cron", hour=4, minute=0, day="*/3",
                       id="rebuild_network", replace_existing=True, max_instances=1)
    # 项目跟踪: 每日 04:30 增量把新线索归整到项目
    _scheduler.add_job(_job_track_projects, "cron", hour=4, minute=30,
                       id="track_projects", replace_existing=True, max_instances=1)
    # 过期数据清理: 每日 05:00 标记过期线索/匹配
    _scheduler.add_job(_job_clean_stale_clues, "cron", hour=5, minute=0,
                       id="clean_stale_clues", replace_existing=True, max_instances=1)
    # 无效人脉清理: 每周日 06:00 软删无效/过期数据
    _scheduler.add_job(_job_clean_invalid_network, "cron", day_of_week="sun", hour=6, minute=0,
                       id="clean_invalid_network", replace_existing=True, max_instances=1)
    _scheduler.start()
    logger.info("[scheduler] 定时任务已启动: 意向抓取每日03:00, 人脉重建每3天04:00, "
                "过期清理每日05:00, 无效人脉清理每周日06:00")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None
        logger.info("[scheduler] 定时任务已停止")
