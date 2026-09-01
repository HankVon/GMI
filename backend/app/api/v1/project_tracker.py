"""项目跟踪器 API — 线索自动归整到项目 + 按阶段监控。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.project import Project
from app.services import project_tracker as tracker

router = APIRouter(prefix="/projects/tracker", tags=["项目跟踪"])


def _fallback_clues(db: Session, project: Project, src: str) -> list:
    """跟踪情报兜底: 已归整线索为空时, 实时按「同类别」匹配外部公告作为候选线索。

    复用 project_context 的匹配函数(动态导入避免循环依赖), 返回与 tracked_clues
    一致的分组结构(投资意向期/招标期/中标公示期), 并标记 from_fallback=True。
    """
    from app.api.v1 import project_context as pc
    from app.models.web_clue import WebClue
    from app.models.bid_notice import BidNotice
    from app.models.intent_notice import IntentNotice

    ctx = pc._project_ctx(project)
    county_ctx = ctx["county"] or ""
    city_ctx = ctx["city"] or ""
    cat = ctx["category"] or ""
    stage_zh = {"investment": "投资意向期", "bidding": "招标期", "awarded": "中标公示期", "construction": "施工期"}
    groups: dict = {}

    def _add(ttype, sid, title, url, published, source_name, purchaser):
        if (url or "").strip() and (url or "").strip() == src:
            return  # 排除项目自身来源公告
        tpool = title or ""
        _k, _ks, cat_hit = pc._keyword_overlap(ctx["name_kw"], tpool, cat)
        # 兜底用 level=2(仅同类别), 与行业情报最后一级兜底一致
        if not pc._is_industry_related(county_ctx, city_ctx, tpool, cat_hit, level=2):
            return
        stage_map = {"investment": "investment", "bidding": "bidding", "awarded": "awarded"}
        stage = stage_map.get(ttype, "bidding")
        g = groups.setdefault(stage, {"stage": stage, "stage_label": stage_zh[stage], "items": []})
        if hasattr(published, "strftime"):
            pub_str = published.strftime("%Y-%m-%d")
        else:
            pub_str = (str(published)[:10] if published else "")
        g["items"].append({
            "id": sid, "clue_type": ttype, "clue_id": sid,
            "stage": stage, "title": title or "", "url": url or "",
            "source_name": source_name or "", "region": "",
            "purchaser": purchaser or "",
            "published_at": pub_str,
            "confidence": 0.6, "match_reason": "同类候选(兜底, 未正式归整)",
            "from_fallback": True,
        })

    # 各表字段不统一, 用 getattr 安全访问缺失字段(如 WebClue 无 purchaser, IntentNotice 无 source_name)
    for w in db.execute(select(WebClue).where(WebClue.is_deleted == False, WebClue.status == "accepted").limit(5000)).scalars().all():
        _add("bidding", w.id, w.title, w.url, w.published_at,
             getattr(w, "source_name", "") or "网页线索", getattr(w, "purchaser", "") or "")
    for b in db.execute(select(BidNotice).where(BidNotice.is_deleted == False).limit(5000)).scalars().all():
        _add("awarded", b.id, b.title, b.url, b.published_at,
             getattr(b, "source_name", "") or "中标公告", getattr(b, "purchaser", "") or "")
    for it in db.execute(select(IntentNotice).where(IntentNotice.is_deleted == False).limit(5000)).scalars().all():
        _add("investment", it.id, it.title, it.url, it.published_at,
             getattr(it, "source_name", "") or "意向信息", getattr(it, "purchaser", "") or "")
    # 按阶段顺序输出
    order = ["investment", "bidding", "awarded", "construction"]
    out = [groups[s] for s in order if s in groups]
    for g in out:
        g["items"].sort(key=lambda x: x["published_at"] or "", reverse=True)
        g["items"] = g["items"][:10]
    return out


@router.post("/run")
async def tracker_run(
    limit: int = 3000,
    db: Session = Depends(get_db),
    user: dict = Depends(require_permission("api_project_crud")),
):
    """全量增量匹配: 把未关联的 意向/招标/中标 线索归整到项目(幂等, 防张冠李戴)。"""
    result = tracker.match_all_clues(db, limit=limit)
    return {"success": True, "message": f"匹配完成: 意向 {result['intent']} / 线索 {result['web_clue']} / 中标 {result['bid']}",
            "data": result}


@router.post("/mark-read/{clue_id}")
async def tracker_mark_read(
    clue_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """标记一条跟踪情报已读。"""
    tracker.mark_read(db, clue_id)
    return {"success": True}


@router.get("/{project_id}")
async def tracker_list(
    project_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """项目已跟踪线索(按阶段分组: 投资意向期/招标期/中标公示期/施工期)。"""
    project = db.execute(
        select(Project).where(Project.id == project_id, Project.is_deleted == False)
    ).scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    # 排除项目自身来源公告(已导入为项目本体), 避免「跟踪情报=项目本身」
    src = ((project.ext_attrs or {}).get("source") or "").strip()
    groups = tracker.tracked_clues(db, project_id)
    if src:
        for g in groups:
            g["items"] = [it for it in g["items"] if (it.get("url") or "").strip() != src]
        groups = [g for g in groups if g["items"]]
    # 兜底: 已归整线索为空时, 实时用行业情报匹配规则查同类外部公告作为「候选线索」,
    # 保证跟踪情报在尚未跑 /projects/tracker/run 时也有内容可看, 并提示可归整。
    fallback = False
    if not groups:
        fb = _fallback_clues(db, project, src)
        if fb:
            groups = fb
            fallback = True
    total = sum(len(g["items"]) for g in groups)
    return {"success": True, "total": total, "groups": groups,
            "project": {"id": project.id, "name": project.name},
            "fallback": fallback}  # True=当前为兜底候选线索, 尚未正式归整
