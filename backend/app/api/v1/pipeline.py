"""数据流水线 API — 采集→筛选入库→图谱→回填 全链路/单阶段执行。

POST /pipeline/run        全链路执行(后台线程, 立即返回 task 状态)
POST /pipeline/stage/{s}  单阶段执行
GET  /pipeline/status     流水线运行状态
GET  /pipeline/stats      各阶段统计(采集/筛选/图谱/回填)
GET  /pipeline/rules      当前筛选规则(用户可查看/调整)
"""
import threading
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.middleware.auth import get_current_user, require_permission
from app.models.web_clue import WebClue
from app.models.intent_notice import IntentNotice
from app.models.bid_notice import BidNotice
from app.models.entity_relation import EntityRelation
from app.services import data_pipeline

router = APIRouter(prefix="/pipeline", tags=["数据流水线"])


class PipelineRunRequest(BaseModel):
    stages: Optional[list[str]] = Field(None, description="阶段子集 collect/filter/graph/backfill, 缺省全部")
    rules: Optional[dict] = Field(None, description="覆盖筛选规则(FilterRules 字段)")
    collect_opts: Optional[dict] = Field(None, description="采集选项 include_intent/include_clues/include_bids")


class StageRunRequest(BaseModel):
    rules: Optional[dict] = None
    deep_enrich: bool = Field(True, description="回填阶段是否深度补全单位详情(免费渠道, 慢)")
    deep_enrich_limit: Optional[int] = Field(None, ge=1, le=100, description="每轮深度补全单位数上限, 缺省 15")
    use_llm: bool = Field(False, description="图谱阶段是否用 LLM 补充开放关系(需 Ollama)")


@router.post("/run")
async def run_pipeline_api(payload: Optional[PipelineRunRequest] = None,
                           db: Session = Depends(get_db),
                           user: dict = Depends(require_permission("api_company_crud"))):
    """全链路执行(后台线程)。立即返回 task_id, 前端轮询 /pipeline/status。"""
    if data_pipeline._pipeline_status.get("running"):
        return {"success": True, "running": True, "message": "流水线正在执行中, 请稍候"}
    payload = payload or PipelineRunRequest()
    stages = payload.stages or None
    if stages:
        for s in stages:
            if s not in data_pipeline.PIPELINE_STAGES:
                raise HTTPException(status_code=400, detail=f"未知阶段: {s}")

    def _worker():
        sdb = SessionLocal()
        try:
            data_pipeline.run_pipeline(sdb, stages=stages,
                                       rules=payload.rules, collect_opts=payload.collect_opts)
        finally:
            sdb.close()

    threading.Thread(target=_worker, daemon=True).start()
    return {"success": True, "running": True,
            "message": "流水线已启动(采集→筛选→图谱→回填)", "stages": stages or data_pipeline.PIPELINE_STAGES}


@router.post("/stage/{stage}")
async def run_stage_api(stage: str, payload: Optional[StageRunRequest] = None,
                        db: Session = Depends(get_db),
                        user: dict = Depends(require_permission("api_company_crud"))):
    """单阶段执行(后台线程, 立即返回)。前端轮询 /pipeline/status + /pipeline/logs 看实时过程。"""
    if stage not in data_pipeline.PIPELINE_STAGES:
        raise HTTPException(status_code=400, detail=f"未知阶段: {stage}")
    if data_pipeline._pipeline_status.get("running"):
        cur = data_pipeline._pipeline_status.get("current_stage") or ""
        return {"success": True, "running": True, "stage": stage,
                "message": f"已有任务在执行中(阶段: {cur}), 请稍候"}
    payload = payload or StageRunRequest()

    def _worker():
        sdb = SessionLocal()
        try:
            data_pipeline.run_stage_background(sdb, stage, rules=payload.rules,
                                               deep_enrich=payload.deep_enrich,
                                               deep_enrich_limit=payload.deep_enrich_limit,
                                               use_llm=payload.use_llm)
        finally:
            sdb.close()

    threading.Thread(target=_worker, daemon=True).start()
    return {"success": True, "running": True, "stage": stage,
            "message": f"阶段「{stage}」已启动(后台执行, 日志实时刷新)"}


@router.get("/status")
async def pipeline_status(user: dict = Depends(get_current_user)):
    """流水线运行状态(内存, 含 control 暂停/停止状态)。"""
    return {"success": True, "data": data_pipeline.get_pipeline_status()}


class ControlRequest(BaseModel):
    action: str = Field(..., pattern="^(pause|resume|stop)$", description="控制指令: pause暂停 / resume继续 / stop停止")


@router.post("/control")
async def pipeline_control(payload: ControlRequest,
                           user: dict = Depends(require_permission("api_company_crud"))):
    """暂停/继续/停止 流水线(当前阶段)。断点续跑: 停止后再次启动从断点继续。"""
    ctl = data_pipeline.set_pipeline_control(payload.action)
    msg = {
        "pause": "已请求暂停(当前单位处理完后暂停)",
        "resume": "已继续执行",
        "stop": "已请求停止(当前单位处理完后停止, 断点已记录, 下次从断点继续)",
    }[payload.action]
    return {"success": True, "message": msg, "data": ctl}


@router.get("/logs")
async def pipeline_logs(limit: int = Query(200, ge=1, le=1000), user: dict = Depends(get_current_user)):
    """流水线实时过程日志(内存环形缓冲, 供前端「一键执行」看过程)。"""
    return {"success": True, "data": data_pipeline.get_pipeline_logs(limit)}


@router.post("/logs/clear")
async def pipeline_logs_clear(user: dict = Depends(require_permission("api_company_crud"))):
    """清空流水线过程日志。"""
    data_pipeline.clear_pipeline_logs()
    return {"success": True, "message": "已清空流水线日志"}


@router.get("/stats")
async def pipeline_stats(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """各阶段数据量统计。"""
    clue_total = db.execute(select(func.count()).select_from(WebClue).where(
        WebClue.is_deleted == False)).scalar() or 0
    clue_accepted = db.execute(select(func.count()).select_from(WebClue).where(
        WebClue.is_deleted == False, WebClue.status == "accepted")).scalar() or 0
    clue_rejected = db.execute(select(func.count()).select_from(WebClue).where(
        WebClue.is_deleted == False, WebClue.status == "rejected")).scalar() or 0
    intent_total = db.execute(select(func.count()).select_from(IntentNotice).where(
        IntentNotice.is_deleted == False)).scalar() or 0
    bid_total = db.execute(select(func.count()).select_from(BidNotice).where(
        BidNotice.is_deleted == False)).scalar() or 0
    rel_total = db.execute(select(func.count()).select_from(EntityRelation).where(
        EntityRelation.is_deleted == False)).scalar() or 0
    # 已抽取线索数: meta 中含 kg_done=true (JSON_EXTRACT 兼容)
    try:
        kg_done = db.execute(
            select(func.count()).select_from(WebClue).where(
                WebClue.is_deleted == False,
                func.json_unquote(func.json_extract(WebClue.meta, "$.kg_done")) == "true",
            )
        ).scalar() or 0
    except Exception:  # noqa: BLE001
        kg_done = 0
    return {
        "success": True,
        "data": {
            "collect": {
                "clue_total": clue_total, "intent_total": intent_total, "bid_total": bid_total,
            },
            "filter": {
                "clue_total": clue_total, "accepted": clue_accepted, "rejected": clue_rejected,
                "pass_rate": round(clue_accepted / clue_total * 100, 1) if clue_total else 0,
            },
            "graph": {"relation_total": rel_total, "clue_kg_done": kg_done},
            "backfill": {"companies": _company_count(db), "persons": _person_count(db)},
            "rules": data_pipeline.FilterRules().to_dict(),
        },
    }


def _company_count(db: Session) -> int:
    from app.models.company import Company
    return db.execute(select(func.count()).select_from(Company).where(Company.is_deleted == False)).scalar() or 0


def _person_count(db: Session) -> int:
    from app.models.person import Person
    return db.execute(select(func.count()).select_from(Person).where(Person.is_deleted == False)).scalar() or 0


@router.get("/rules")
async def pipeline_rules(user: dict = Depends(get_current_user)):
    """当前筛选规则(默认值, 可在 run 请求中覆盖)。"""
    return {"success": True, "data": data_pipeline.FilterRules().to_dict()}
