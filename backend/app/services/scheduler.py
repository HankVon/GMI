"""定时任务 — 意向源周期抓取 + 中标增量重建 + 人脉库同步 + 过期数据清理。

依赖 apscheduler; 若未安装则任务不启动(不影响主服务)。
启停: main.py startup 时 start_scheduler() / shutdown 时 stop_scheduler()。
"""
import logging
from datetime import datetime, timedelta

from app.services.notify import send_alert

logger = logging.getLogger("scheduler")

_scheduler = None


def _fail(job_name: str, e: Exception) -> None:
    """定时任务失败: 记错误日志 + 推送运维告警(未配置 webhook 则仅日志)。"""
    logger.error("[scheduler] %s失败: %s", job_name, e)
    send_alert(f"[定时任务] {job_name}失败", str(e))


def _job_subscription_digest():
    """每日执行用户筛选快照，发现新增标讯/商机后写入站内通知。

    按 product_type 分流:
      - tender:       匹配 BidNotice.title(关键词)
      - opportunity:  匹配 Opportunity(商机搜索条件快照)
    """
    try:
        from app.database import SessionLocal
        from app.models.subscription_task import SubscriptionTask
        from app.models.notification import Notification
        from app.models.bid_notice import BidNotice
        from app.models.opportunity import Opportunity
        from sqlalchemy import select
        db = SessionLocal()
        try:
            tasks = db.execute(select(SubscriptionTask).where(SubscriptionTask.enabled == True, SubscriptionTask.is_deleted == False)).scalars().all()
            for task in tasks:
                snapshot = task.condition_snapshot if isinstance(task.condition_snapshot, dict) else {}
                product = (task.product_type or "tender").lower()
                if product == "opportunity":
                    rows, notif_type, notif_suffix = _match_opportunity_snapshot(db, snapshot)
                else:
                    rows, notif_type, notif_suffix = _match_tender_snapshot(db, snapshot)
                published_vals = [getattr(r, "published_at", None) or getattr(r, "updated_at", None) for r in rows]
                latest = max((v for v in published_vals if v), default=None)
                if rows and (task.last_run_at is None or latest and latest > task.last_run_at):
                    db.add(Notification(
                        user_id=task.user_id, type=notif_type,
                        title=f"订阅「{task.name}」{notif_suffix}",
                        content=f"本次发现 {len(rows)} 条匹配信息",
                        related_type="subscription", related_id=task.id,
                        is_read=False, is_deleted=False,
                    ))
                task.last_run_at = datetime.now(); task.last_match_count = len(rows)
            db.commit()
        finally: db.close()
    except Exception as e: _fail("订阅快照执行", e)


def _match_tender_snapshot(db, snapshot: dict):
    """按快照条件匹配标讯(与历史行为一致)。"""
    from app.models.bid_notice import BidNotice
    keyword = str(snapshot.get("keyword") or "").strip()
    stmt = select(BidNotice).where(BidNotice.is_deleted == False, BidNotice.status == "published")
    if keyword:
        stmt = stmt.where(BidNotice.title.contains(keyword))
    rows = db.execute(stmt.order_by(BidNotice.published_at.desc()).limit(5)).scalars().all()
    return rows, "bid_new", "有新标讯"


def _match_opportunity_snapshot(db, snapshot: dict):
    """按快照条件匹配新增商机(与 /opportunities/search 字段对齐)。"""
    from app.models.opportunity import Opportunity
    ds = (snapshot.get("dataset_type") or snapshot.get("datasetType") or "project").lower()
    if ds not in ("project", "proposed", "landtrade"):
        ds = "project"
    stmt = select(Opportunity).where(Opportunity.is_deleted == 0, Opportunity.dataset_type == ds)

    if snapshot.get("region_province"):
        stmt = stmt.where(Opportunity.region_province == snapshot["region_province"])
    if snapshot.get("region_city"):
        stmt = stmt.where(Opportunity.region_city == snapshot["region_city"])
    if snapshot.get("amount_min") is not None:
        stmt = stmt.where(Opportunity.amount_wan >= int(snapshot["amount_min"]))
    if snapshot.get("amount_max") is not None:
        stmt = stmt.where(Opportunity.amount_wan <= int(snapshot["amount_max"]))
    if snapshot.get("stage"):
        stmt = stmt.where(Opportunity.stage == snapshot["stage"])
    if snapshot.get("owner_type"):
        stmt = stmt.where(Opportunity.owner_type == snapshot["owner_type"])
    if snapshot.get("owner_name"):
        stmt = stmt.where(Opportunity.owner_name.like(f"%{snapshot['owner_name']}%"))
    if snapshot.get("project_type"):
        stmt = stmt.where(Opportunity.project_type == snapshot["project_type"])
    if snapshot.get("unit_role"):
        stmt = stmt.where(Opportunity.unit_role == snapshot["unit_role"])
    if snapshot.get("unit_name"):
        stmt = stmt.where(Opportunity.unit_name.like(f"%{snapshot['unit_name']}%"))
    if snapshot.get("project_name"):
        for kw in str(snapshot["project_name"]).split():
            kw = kw.strip()
            if kw:
                stmt = stmt.where(Opportunity.project_name.like(f"%{kw}%"))
    if snapshot.get("update_start"):
        try:
            stmt = stmt.where(Opportunity.updated_at >= datetime.fromisoformat(snapshot["update_start"]))
        except ValueError:
            pass
    if snapshot.get("update_end"):
        try:
            stmt = stmt.where(Opportunity.updated_at <= datetime.fromisoformat(snapshot["update_end"]))
        except ValueError:
            pass

    # 标签 OR 并集: 任一标签命中即视为匹配
    tags = snapshot.get("tags") or []
    if tags:
        from app.models.opportunity_tag import OpportunityTag
        opp_ids_subq = select(OpportunityTag.opportunity_id).where(OpportunityTag.tag_id.in_(tags)).distinct()
        stmt = stmt.where(Opportunity.id.in_(opp_ids_subq))

    rows = db.execute(stmt.order_by(Opportunity.published_at.desc()).limit(5)).scalars().all()
    return rows, "opp_new", "有新商机"


def _job_crawl_intents():
    """每日抓取意向源(发改委/自然资源厅等) → intent_notice → 推理侦察 → 项目跟踪。

    闭环: 采集(抓政务源) → 推理(opportunity_scout 推导高价值目标) → 反哺
    (project_tracker 把新意向归整到项目)。
    """
    try:
        from app.database import SessionLocal
        from app.services.intent_crawler import crawl_all_intent_sources
        db = SessionLocal()
        try:
            result = crawl_all_intent_sources(db)
            logger.info("[scheduler] 意向源抓取完成: %s", result)
            # 推理侦察: 从项目/人脉/中标推导当前高价值目标单位
            try:
                from app.services.opportunity_scout import scout_summary, scout_targets, feedback_to_companies
                summary = scout_summary(db, days=180)
                logger.info("[scheduler] 侦察完成: %s", summary)
                # 反哺: 目标单位画像写回 company.ext_attrs.scout
                targets = scout_targets(db, days=180, top_n=30)
                fb = feedback_to_companies(db, targets, max_units=30)
                logger.info("[scheduler] 目标单位画像回写完成: %s", fb)
            except Exception as e:  # noqa: BLE001
                _fail("机会侦察", e)
            # 反哺: 新意向自动归整到项目
            try:
                from app.services.project_tracker import match_all_clues
                tracked = match_all_clues(db)
                logger.info("[scheduler] 项目跟踪完成: %s", tracked)
            except Exception as e:  # noqa: BLE001
                _fail("项目跟踪", e)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        _fail("意向源抓取", e)


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
        _fail("人脉库重建", e)


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
            expired_items: list = []
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
                    expired_items.append((c.id, c.title or "未命名线索"))
            db.commit()
            # 刷新招标匹配有效期
            validity = refresh_match_validity(db, now)
            # 线索过期 → 逐条站内通知(admin 角色用户), 标题含线索名, related_id 指向线索供前端跳转
            if expired_items:
                from app.services.notification import notify_admin_users
                for cid, ctitle in expired_items[:10]:
                    notify_admin_users(db, "clue_expire",
                                       f"线索「{ctitle[:40]}」已到截止时间",
                                       "请及时跟进线索, 避免错过有效商机。",
                                       related_type="web_clue", related_id=cid)
            logger.info("[scheduler] 过期清理完成: 线索标记过期 %s, 匹配有效性 %s", expired, validity)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        _fail("过期线索清理", e)


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
        _fail("无效人脉清理", e)


def _job_geo_monitor():
    """每日 GEO 监测: 对启用关键词×启用引擎执行 AI 回答采集与解析(手动适配器跳过)。"""
    try:
        from app.database import SessionLocal
        from app.services.geo_monitor import run_all_enabled
        db = SessionLocal()
        try:
            result = run_all_enabled(db)
            logger.info("[scheduler] GEO 监测完成: %s", result)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        _fail("GEO监测", e)


def _job_harvest_companies():
    """每日扩充企业库: 从 bid_notice 未匹配供应商/采购人自动建档。

    在 06:30 行业采集之前运行(06:00), 提升外部公示企业命中 company 库的概率。
    """
    try:
        from app.database import SessionLocal
        from app.services.company_harvest import harvest_bid_companies
        db = SessionLocal()
        try:
            result = harvest_bid_companies(db)
            logger.info("[scheduler] 企业库扩充完成: %s", result)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        _fail("企业库扩充", e)


def _job_crawl_industry_data():
    """每日抓取行业数据源(政务公示等) → credit_record/honor/qualification。

    对应指导文档: docs/gmi-renovation-guide.md B2 / G-阶段一。
    错峰运行(06:30), 避开 03:00 意向抓取与 05:00 过期清理。
    """
    try:
        from app.database import SessionLocal
        from app.services.industry_crawler import crawl_all_industry_sources
        db = SessionLocal()
        try:
            result = crawl_all_industry_sources(db)
            logger.info("[scheduler] 行业数据抓取完成: %s", result)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        _fail("行业数据抓取", e)


def _job_sync_cert_validity():
    """每日刷新 person_cert/qualification 状态(active/expiring/expired), 支撑失效预警。"""
    try:
        from app.database import SessionLocal
        from app.services.industry_crawler import sync_cert_validity
        db = SessionLocal()
        try:
            result = sync_cert_validity(db)
            logger.info("[scheduler] 证书有效性刷新完成: %s", result)
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        _fail("证书有效性刷新", e)


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
        _fail("项目跟踪匹配", e)


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
    _scheduler.add_job(_job_subscription_digest, "cron", hour=2, minute=30, id="subscription_digest", replace_existing=True, max_instances=1)
    # 意向源: 每天 03:00 抓取(避开白天访问高峰)
    _scheduler.add_job(_job_crawl_intents, "cron", hour=3, minute=0, id="crawl_intents",
                       replace_existing=True, max_instances=1)
    # 人脉库: 每 3 天凌晨 04:00 重建
    _scheduler.add_job(_job_rebuild_network, "cron", hour=4, minute=0, day="*/3",
                       id="rebuild_network", replace_existing=True, max_instances=1)
    # 项目跟踪: 每日 04:30 增量把新线索归整到项目
    _scheduler.add_job(_job_track_projects, "cron", hour=4, minute=30,
                       id="track_projects", replace_existing=True, max_instances=1)
    # GEO 监测: 每日 07:00 采集 AI 引擎回答(串行限速, 与意向抓取错峰)
    _scheduler.add_job(_job_geo_monitor, "cron", hour=7, minute=0,
                       id="geo_monitor", replace_existing=True, max_instances=1)
    # 证书有效性刷新: 每日 05:45(避开 05:00 过期清理)
    _scheduler.add_job(_job_sync_cert_validity, "cron", hour=5, minute=45,
                       id="sync_cert_validity", replace_existing=True, max_instances=1)
    # 企业库扩充: 每日 06:00(先建档案, 提升 06:30 行业采集命中率)
    _scheduler.add_job(_job_harvest_companies, "cron", hour=6, minute=0,
                       id="harvest_companies", replace_existing=True, max_instances=1)
    # 行业数据抓取: 每日 06:30(避开 03:00 意向抓取 / 05:00 过期清理)
    _scheduler.add_job(_job_crawl_industry_data, "cron", hour=6, minute=30,
                       id="crawl_industry_data", replace_existing=True, max_instances=1)
    # 过期数据清理: 每日 05:00 标记过期线索/匹配
    _scheduler.add_job(_job_clean_stale_clues, "cron", hour=5, minute=0,
                       id="clean_stale_clues", replace_existing=True, max_instances=1)
    # 无效人脉清理: 每周日 06:00 软删无效/过期数据
    _scheduler.add_job(_job_clean_invalid_network, "cron", day_of_week="sun", hour=6, minute=0,
                       id="clean_invalid_network", replace_existing=True, max_instances=1)
    _scheduler.start()
    logger.info("[scheduler] 定时任务已启动: 意向抓取每日03:00, 人脉重建每3天04:00, "
                "GEO监测每日07:00, 过期清理每日05:00, 无效人脉清理每周日06:00")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # noqa: BLE001
            pass
        _scheduler = None
        logger.info("[scheduler] 定时任务已停止")
