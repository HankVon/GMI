"""网页线索/情报模块 API — 来源站点管理 + 线索列表 + crawl4ai 抓取/筛选

筛选策略: 只有通过「域名白名单 + 关键词/地域规则」的网页才写入 web_clue,
未通过的直接丢弃(不创建记录 → 不进系统列表)。
"""
import datetime
import json
import logging
import threading
import time
from typing import Optional

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.web_source import WebSource
from app.models.web_clue import WebClue
from app.models.project import Project
from app.models.company import Company
from app.models.person import Person
from app.models.project_member import ProjectMember
from app.schemas.web_clue import (
    WebSourceCreate, WebSourceUpdate, WebSourceResponse,
    WebClueResponse, ManualCrawlRequest, WebClueBatchDelete,
    WebClueEnhanceRequest,
)
from app.schemas.common import PaginatedResponse
from app.services.crawl4ai_client import crawl4ai_client, Crawl4aiError
from app.services.clue_filter import ClueFilter
from app.services import llm_enhance

logger = logging.getLogger("web_clues")
router = APIRouter(prefix="/web-clues", tags=["网页线索"])

# ---------- 抓取日志缓冲(内存环形队列, 供前端实时查看进度) ----------
_crawl_logs: list = []
_crawl_log_lock = threading.Lock()
_CRAWL_LOG_MAX = 500

# 来源级活跃抓取任务: source_id -> {task_id, start_ts}
# 用于同一来源正在爬取时, 重复点击"立即抓取"直接续看现有任务日志, 而不是再启动新任务
_active_crawls: dict = {}
_active_crawls_lock = threading.Lock()


def register_active_crawl(source_id: int, task_id: str) -> None:
    with _active_crawls_lock:
        _active_crawls[source_id] = {"task_id": task_id, "start_ts": time.time()}


def get_active_crawl(source_id: int) -> Optional[str]:
    """返回该来源正在运行的任务 task_id; 无则 None。"""
    with _active_crawls_lock:
        info = _active_crawls.get(source_id)
        return (info or {}).get("task_id")


def clear_active_crawl(source_id: int, task_id: Optional[str] = None) -> None:
    """任务结束(或超时)时清理活跃登记, 仅当仍指向同一 task 时删除。"""
    with _active_crawls_lock:
        info = _active_crawls.get(source_id)
        if info and (task_id is None or info.get("task_id") == task_id):
            _active_crawls.pop(source_id, None)


def push_crawl_log(task_id: str, msg: str, level: str = "info") -> None:
    """追加抓取日志到环形缓冲。"""
    entry = {
        "ts": datetime.datetime.now().strftime("%H:%M:%S"),
        "task": task_id,
        "msg": str(msg),
        "level": level,
    }
    with _crawl_log_lock:
        _crawl_logs.append(entry)
        if len(_crawl_logs) > _CRAWL_LOG_MAX:
            del _crawl_logs[: len(_crawl_logs) - _CRAWL_LOG_MAX]


def clear_crawl_logs(task_id: Optional[str] = None) -> None:
    """清空日志(按 task 过滤可选)。"""
    with _crawl_log_lock:
        global _crawl_logs
        if task_id:
            _crawl_logs = [e for e in _crawl_logs if e.get("task") != task_id]
        else:
            _crawl_logs = []


def list_crawl_logs(task_id: Optional[str] = None) -> list:
    """同步读取抓取日志(按 task_id 过滤可选)。路由与数据流水线桥接共用。"""
    with _crawl_log_lock:
        logs = list(_crawl_logs)
    if task_id:
        logs = [e for e in logs if e.get("task") == task_id]
    return logs[-200:]


@router.get("/logs")
async def get_crawl_logs(task_id: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    """获取抓取日志(按 task_id 过滤可选)。"""
    return {"logs": list_crawl_logs(task_id)}


def _parse_query_config(raw) -> Optional[dict]:
    """web_source.query_config 存 JSON 字符串, 解析为 dict; 非法返回 None。"""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return None
    return None


def _to_source_response(src) -> WebSourceResponse:
    """序列化来源(含 query_config JSON -> dict)。

    注意: query_config 在库中存 JSON 字符串, schema 期望 dict, 须先转换再 validate。
    """
    data = {
        "id": src.id,
        "name": src.name,
        "url": src.url,
        "description": src.description,
        "allow_domains": src.allow_domains,
        "keywords": src.keywords,
        "exclude_keywords": src.exclude_keywords,
        "regions": src.regions,
        "scrape_mode": src.scrape_mode,
        "max_depth": src.max_depth,
        "max_pages": src.max_pages,
        "include_urls": src.include_urls,
        "query_config": _parse_query_config(src.query_config),
        "llm_enhance": src.llm_enhance,
        "enabled": src.enabled,
        "last_run_at": src.last_run_at,
        "last_run_result": src.last_run_result,
        "last_error": src.last_error,
    }
    return WebSourceResponse.model_validate(data)


# ============================================================
# 来源站点配置 CRUD
# ============================================================
@router.get("/sources", response_model=PaginatedResponse)
async def list_sources(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    q = select(WebSource).where(WebSource.is_deleted == False)
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar() or 0
    rows = db.execute(
        q.order_by(WebSource.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return PaginatedResponse(total=total, page=page, page_size=page_size,
                             items=[_to_source_response(r) for r in rows])


@router.post("/sources", response_model=WebSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(data: WebSourceCreate, db: Session = Depends(get_db),
                        user: dict = Depends(get_current_user)):
    payload = data.model_dump()
    if isinstance(payload.get("query_config"), dict):
        payload["query_config"] = json.dumps(payload["query_config"], ensure_ascii=False)
    src = WebSource(**payload)
    db.add(src)
    db.commit()
    db.refresh(src)
    return _to_source_response(src)


@router.put("/sources/{source_id}", response_model=WebSourceResponse)
async def update_source(source_id: int, data: WebSourceUpdate, db: Session = Depends(get_db),
                        user: dict = Depends(get_current_user)):
    src = db.execute(select(WebSource).where(WebSource.id == source_id, WebSource.is_deleted == False)).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="来源站点不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "query_config" and isinstance(v, dict):
            v = json.dumps(v, ensure_ascii=False)
        setattr(src, k, v)
    db.commit()
    db.refresh(src)
    return _to_source_response(src)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: int, db: Session = Depends(get_db),
                        user: dict = Depends(get_current_user)):
    src = db.execute(select(WebSource).where(WebSource.id == source_id, WebSource.is_deleted == False)).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="来源站点不存在")
    src.is_deleted = True
    db.commit()
    return None


# ============================================================
# 线索列表
# ============================================================
@router.get("", response_model=PaginatedResponse)
async def list_clues(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_: Optional[str] = Query(None, alias="status"),
    keyword: Optional[str] = None,
    region: Optional[str] = None,
    province: Optional[str] = Query(None, description="省过滤(核心词: 四川/西藏/新疆)"),
    city: Optional[str] = Query(None, description="市过滤(核心词: 成都/日喀则/喀什)"),
    county: Optional[str] = Query(None, description="县过滤(核心词: 喜德/普兰/定日)"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """线索列表(支持 关键词/省-市-县级联地域 筛选)。

    web_clue 无省/市/县列 → SQL 粗筛后 Python 层按 meta.regionName/region 做地域过滤。
    数据量有限(数百~数千条), Python 过滤可行。
    """
    from app.services.china_regions import extract_target_province
    conds = [WebClue.is_deleted == False]
    if status_:
        conds.append(WebClue.status == status_)
    if keyword:
        conds.append(or_(WebClue.title.like(f"%{keyword}%"), WebClue.summary.like(f"%{keyword}%")))
    if region:
        conds.append(WebClue.region == region)
    q = select(WebClue).where(*conds)
    rows = db.execute(
        q.order_by(WebClue.fetched_at.desc())
    ).scalars().all()

    # 省-市-县 地域过滤(Python)
    if province or city or county:
        filtered = []
        for c in rows:
            meta = c.meta if isinstance(c.meta, dict) else {}
            text_pool = " ".join([
                c.title or "", c.region or "",
                meta.get("regionName") or "", meta.get("regionName_") or "",
                meta.get("purchaserAddr") or "", meta.get("purchaser") or "",
            ])
            if province:
                if extract_target_province(text_pool) != province:
                    continue
            if city and city not in text_pool:
                continue
            if county and county not in text_pool:
                continue
            filtered.append(c)
        rows = filtered

    total = len(rows)
    paged = rows[(page - 1) * page_size: page * page_size]
    return PaginatedResponse(total=total, page=page, page_size=page_size,
                             items=[WebClueResponse.model_validate(r) for r in paged])


@router.post("/backfill-derived")
async def backfill_derived_links_api(db: Session = Depends(get_db),
                                     user: dict = Depends(get_current_user)):
    """为历史线索补写「派生实体关联」(derived_project_id/company_ids/person_ids)。

    轻量操作: 只按确定性规则反向查找已存在的项目/单位/人员并写回线索 meta,
    不创建实体、不重复同步图谱。用于升级前已回填但缺关联字段的存量线索。
    """
    from app.services.data_pipeline import backfill_derived_links
    result = backfill_derived_links(db)
    return {"success": True, "processed": result.get("processed", 0),
            "updated": result.get("updated", 0),
            "message": f"已扫描 {result.get('processed', 0)} 条线索, 补写关联 {result.get('updated', 0)} 条"}


def _ensure_derived_links(db: Session, clue: WebClue) -> dict:
    """惰性补写线索 meta 的 derived_* 关联(仅对已回填但缺关联的历史线索)。

    详情页打开时触发一次: 确定性反向查找(项目名/采购人/供应商/项目成员),
    不创建实体、不重复同步 Neo4j。返回(可能已更新)的 meta。
    """
    meta = dict(clue.meta) if isinstance(clue.meta, dict) else {}
    if not meta.get("backfill_done") or meta.get("derived_project_id"):
        return meta  # 未回填 或 已有关联 → 直接返回

    from app.services.real_project_import import _find_company, _find_project
    from app.services.data_pipeline import _derive_project_name

    purchaser = meta.get("purchaser") or ""
    project_name = _derive_project_name(clue.title or "", purchaser)
    comp_ids: list[int] = []
    person_ids: list[int] = []
    project_id = None
    if project_name:
        proj = _find_project(db, project_name)
        if proj:
            project_id = proj.id
    suppliers = [s.get("supplier", "") for s in (meta.get("suppliers") or []) if s.get("supplier")]
    for name in dict.fromkeys([purchaser] + suppliers):
        name = (name or "").strip()
        if len(name) < 4:
            continue
        comp = _find_company(db, name)
        if comp:
            comp_ids.append(comp.id)
    if project_id:
        pms = db.execute(select(ProjectMember.person_id).where(
            ProjectMember.project_id == project_id, ProjectMember.is_deleted == False)).scalars().all()
        person_ids = list(pms)

    if project_id or comp_ids or person_ids:
        if project_id:
            meta["derived_project_id"] = project_id
        if comp_ids:
            meta["derived_company_ids"] = list(dict.fromkeys(comp_ids))
        if person_ids:
            meta["derived_person_ids"] = list(dict.fromkeys(person_ids))
        clue.meta = meta
        db.commit()
    return meta


def _build_derived(db: Session, clue: WebClue) -> list:
    """从线索 meta 的 derived_* 字段构建实体明细(供前端回显, 已删实体跳过)。"""
    meta = _ensure_derived_links(db, clue)
    out: list = []
    if meta.get("derived_project_id"):
        p = db.get(Project, meta["derived_project_id"])
        if p and not p.is_deleted:
            out.append({"entity_type": "project", "id": p.id, "name": p.name, "code": p.code})
    for cid in (meta.get("derived_company_ids") or []):
        comp = db.get(Company, cid)
        if comp and not comp.is_deleted:
            out.append({"entity_type": "company", "id": comp.id, "name": comp.name, "code": comp.code})
    for pid in (meta.get("derived_person_ids") or []):
        per = db.get(Person, pid)
        if per and not per.is_deleted:
            out.append({"entity_type": "person", "id": per.id, "name": per.name, "code": per.code})
    return out


@router.get("/{clue_id}", response_model=WebClueResponse)
async def get_clue(clue_id: int, db: Session = Depends(get_db),
                   user: dict = Depends(get_current_user)):
    clue = db.execute(select(WebClue).where(WebClue.id == clue_id, WebClue.is_deleted == False)).scalar_one_or_none()
    if not clue:
        raise HTTPException(status_code=404, detail="线索不存在")
    resp = WebClueResponse.model_validate(clue)
    resp.derived = _build_derived(db, clue)
    return resp


@router.delete("/{clue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clue(clue_id: int, db: Session = Depends(get_db),
                      user: dict = Depends(get_current_user)):
    clue = db.execute(select(WebClue).where(WebClue.id == clue_id, WebClue.is_deleted == False)).scalar_one_or_none()
    if not clue:
        raise HTTPException(status_code=404, detail="线索不存在")
    clue.is_deleted = True
    db.commit()
    return None


@router.post("/batch-delete")
async def batch_delete_clues(data: WebClueBatchDelete, db: Session = Depends(get_db),
                             user: dict = Depends(get_current_user)):
    """批量删除线索(软删除)。返回删除数量。"""
    if not data.ids:
        return {"deleted": 0}
    rows = db.execute(select(WebClue).where(
        WebClue.id.in_(data.ids), WebClue.is_deleted == False)).scalars().all()
    for r in rows:
        r.is_deleted = True
    db.commit()
    return {"deleted": len(rows)}


@router.post("/enhance")
async def enhance_clues(data: WebClueEnhanceRequest, db: Session = Depends(get_db),
                        user: dict = Depends(get_current_user)):
    """LLM 增强: 对选中线索做 AI 总结/抽取(手动触发, 每条耗时 5~13s)。"""
    rows = db.execute(select(WebClue).where(
        WebClue.id.in_(data.ids), WebClue.is_deleted == False)).scalars().all()
    done = []
    errors = []
    for clue in rows:
        try:
            content = clue.content or clue.summary or ""
            if not content:
                errors.append({"id": clue.id, "error": "无正文"})
                continue
            result = llm_enhance.enhance_content(clue.title or "", content, data.mode)
            if not result:
                errors.append({"id": clue.id, "error": "LLM 未返回结果(可能不可用)"})
                continue
            meta = clue.meta or {}
            if isinstance(meta, dict):
                # 新 dict 强制 SQLAlchemy 检测 JSON 列变更
                clue.meta = {**meta, "llm": {**meta.get("llm", {}), **result}}
            clue.summary = result.get("ai_summary", {}).get("summary") or clue.summary
            db.commit()
            done.append(clue.id)
        except Exception as e:  # noqa: BLE001
            logger.warning("enhance clue %s error: %s", clue.id, e)
            db.rollback()
            errors.append({"id": clue.id, "error": str(e)[:120]})
    return {"done": done, "errors": errors}


# ============================================================
# crawl4ai 抓取 + 筛选
# ============================================================
def _parse_dt(s) -> Optional[datetime.datetime]:
    """解析日期字符串(兼容 'YYYY-MM-DD HH:MM:SS' 与 ISO)。失败返回 None。"""
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y年%m月%d日 %H时%M分"):
        try:
            return datetime.datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        return None


def _time_window_reject(meta: Optional[dict]) -> Optional[str]:
    """按公告截止时间窗口过滤。返回拒绝原因字符串, 通过则返回 None。

    规则: expire_time(截止时间)存在且已过期 -> 拒绝; 其他情况通过。
    """
    if not meta or not isinstance(meta, dict):
        return None
    now = datetime.datetime.now()
    expire = _parse_dt(meta.get("expire_time") or meta.get("end_time"))
    if expire and expire < now:
        return f"公告已截止(截止时间 {expire:%Y-%m-%d %H:%M})"
    return None


def _ccgp_procurement_result(text: str) -> list:
    """从中国政府采购网中标公告详情 HTML 提取「三、采购结果」表格(供应商/地址/金额)。

    详情页为静态 HTML, 采购结果在 supplier 容器内的 <table>, 列:
      供应商名称 | 供应商地址 | 中标（成交）金额 | 评审总得分
    兼容 markdown pipe / tab 分隔的纯文本输入(内部工具复用)。
    返回 [ {supplier, address, amount} ]。
    """
    import re as _re
    if not text:
        return []
    # 0) 文本列表格式: 供应商名称：X 供应商地址：Y 中标（成交）金额：Z (无表格)
    if _re.search(r"供应商名称[：:]", text) and "供应商名称：" in text.replace("&nbsp;", " "):
        plain = _re.sub(r"<[^>]+>", " ", text)
        plain = _re.sub(r"&nbsp;", " ", plain)
        plain = _re.sub(r"\s+", " ", plain)
        m_name = _re.search(r"供应商名称[：:\s]*([^\s]{2,})", plain)
        if m_name:
            supplier = m_name.group(1).strip()
            m_addr = _re.search(r"供应商地址[：:\s]*([^\s]{4,})", plain)
            m_amt = _re.search(r"金额[^0-9]{0,15}?([\d,]+\.\d+)", plain)
            if m_name and supplier and not _re.fullmatch(r"[\d\s]+", supplier):
                return [{
                    "supplier": supplier[:120],
                    "address": (m_addr.group(1) if m_addr else "")[:200],
                    "amount": ((m_amt.group(1) if m_amt else "") + "元")[:80],
                }]
    # 1) 若为 HTML: 提取 supplier 容器内的表格
    if "<table" in text or "<td" in text:
        seg = text
        # 定位「三、采购结果」/「中标（成交）信息」, 从其后开始; 找不到则退回「采购包」关键词
        i = seg.find("三、采购结果")
        if i < 0:
            i = seg.find("中标（成交）信息")
        if i < 0:
            i = seg.find("中标/成交结果信息")
        if i < 0:
            i = seg.find("采购结果")
        if i >= 0:
            seg = seg[i:]
        else:
            # 无任何标题: 找含「供应商名称」表头的 table 起点
            i = seg.find("供应商名称")
            if i >= 0:
                seg = seg[max(0, i - 300):]
            else:
                i = seg.find("采购包")
                if i >= 0:
                    seg = seg[i:]
        # 找第一个 table(供应商结果表)
        ti = seg.find("<table")
        if ti < 0:
            return []
        ti2 = seg.find("</table>", ti)
        if ti2 < 0:
            return []
        table_html = seg[ti:ti2 + len("</table>")]
        rows = []
        for rm in _re.finditer(r"<tr[^>]*>([\s\S]*?)</tr>", table_html):
            cells = [_re.sub(r"<[^>]+>", "", c).strip()
                     for c in _re.findall(r"<t[dh][^>]*>([\s\S]*?)</t[dh]>", rm.group(1))]
            if not cells:
                continue
            cells = [c for c in cells if c]
            # 序号列: 首列纯数字(如「1」)视为行号, 供应商从第二列开始
            if cells and _re.fullmatch(r"\d{1,3}", cells[0].strip()) and len(cells) >= 4:
                cells = cells[1:]
            rows.append(cells)
        result = []
        header_seen = False
        for cells in rows:
            if any(("供应商名称" in c or "供应商地址" in c) for c in cells):
                header_seen = True
                continue
            if not header_seen:
                continue
            if len(cells) < 3:
                continue
            supplier = cells[0]
            address = cells[1]
            amount_cell = ""
            for c in cells[2:]:
                if "元" in c or _re.search(r"\d", c):
                    amount_cell = c
                    break
            if not amount_cell and len(cells) > 3:
                amount_cell = cells[2]
            amount_cell = amount_cell.replace(",", "")
            if supplier and not _re.fullmatch(r"[\d\s]+", supplier) and "供应商名称" not in supplier:
                result.append({"supplier": supplier[:120], "address": address[:200], "amount": amount_cell[:80]})
        if result:
            return result
        # HTML 表格未解析出, 回退到纯文本逻辑
        text = _re.sub(r"<[^>]+>", "\n", text)

    # 2) 纯文本: 定位「三、采购结果」段(tab 分隔或 markdown pipe)
    start = text.find("三、采购结果")
    if start < 0:
        start = text.find("中标（成交）供应商")
    if start < 0:
        start = text.find("采购结果")
    if start < 0:
        return []
    end = len(text)
    for kw in ("四、主要标的信息", "五、评审专家", "五、评审"):
        i = text.find(kw, start + 10)
        if 0 < i < end:
            end = i
            break
    block = text[start:end]
    result = []
    header_seen = False

    def _row(cells: list):
        if not cells:
            return None
        if any(c.strip().replace("-", "").replace("+", "") == "" for c in cells):
            return None
        cleaned = [c for c in cells if c.strip()]
        if not cleaned:
            return None
        if any(("供应商名称" in c or "供应商地址" in c) for c in cleaned):
            return {"_header": True}
        if all(_re.fullmatch(r"[-:\s]*", c) for c in cleaned):
            return None
        if len(cleaned) < 3:
            return None
        supplier = cleaned[0]
        address = cleaned[1]
        amount_cell = ""
        for c in cleaned[2:]:
            if "元" in c or _re.search(r"\d", c):
                amount_cell = c
                break
        if not amount_cell and len(cleaned) > 3:
            amount_cell = cleaned[2]
        amount_cell = amount_cell.replace(",", "")
        if supplier and not _re.fullmatch(r"[\d\s]+", supplier) and "供应商名称" not in supplier:
            return {"supplier": supplier[:120], "address": address[:200], "amount": amount_cell[:80]}
        return None

    for line in block.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            r = _row(cells)
        elif "\t" in line:
            cells = [c.strip() for c in line.split("\t")]
            r = _row(cells)
        else:
            continue
        if r is None:
            continue
        if r.get("_header"):
            header_seen = True
            continue
        if not header_seen:
            continue
        result.append(r)
        header_seen = False
    return result


def _ccgp_fetch_html(url: str, timeout: float = 30.0) -> str:
    """抓取中国政府采购网静态页, 自动处理 GB2312/GBK 编码。"""
    try:
        resp = httpx.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Referer": "https://www.ccgp.gov.cn/",
        }, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.content
        for enc in ("utf-8", "gb18030", "gbk"):
            try:
                return raw.decode(enc)
            except Exception:  # noqa: BLE001
                continue
        return raw.decode("gb18030", errors="replace")
    except Exception as e:  # noqa: BLE001
        logger.warning("[ccgp] fetch %s error: %s", url, e)
        return ""


def _ccgp_crawl_list(source: WebSource, task: str, logf) -> list:
    """采集中国政府采购网中标公告列表 + 详情, 返回入库 page dict 列表。

    source.url 形如: https://www.ccgp.gov.cn/cggg/dfgg/zbgg/index.htm
    列表页为静态 HTML, 解析公告链接/标题/时间/采购人, 再抓详情提取供应商。
    logf(msg, level) 用于透出进度。
    """
    list_url = source.url
    pages = []
    seen = set()
    # 分页: index.htm -> index_2.htm -> index_3.htm ...; max_pages 为单页条数上限,
    # 用 max_depth 控制翻页页数(默认 5 页)。
    page_count = max(int(source.max_depth or 5), 1)
    idx = 0
    for page_no in range(1, page_count + 1):
        if page_no == 1:
            cur = list_url
        else:
            cur = list_url.replace("index.htm", f"index_{page_no}.htm").replace("index.htm", f"index_{page_no}.htm")
        html = _ccgp_fetch_html(cur)
        if not html:
            logf(f"ccgp 第 {page_no} 页列表抓取失败(空响应)", "error")
            break
        items = _parse_ccgp_list_items(html)
        logf(f"第 {page_no} 页列表解析到 {len(items)} 条公告", "info")
        if not items:
            break
        for it in items:
            url = it.get("url") or ""
            if not url or url in seen:
                continue
            seen.add(url)
            if int(source.max_pages or 20) > 0 and len(seen) > int(source.max_pages or 20):
                return pages
            idx += 1
            logf(f"[{idx}] 抓详情: {(it.get('title') or '')[:30]}", "info")
            detail_html = _ccgp_fetch_html(url)
            wins = _ccgp_procurement_result(detail_html)
            detail_text = _ccgp_html_to_text(detail_html)
            meta = {
                "purchaser": it.get("purchaser") or "",
                "region": it.get("region") or "",
                "published_at": it.get("published_at") or "",
                "notice_type": "中标（成交）公告",
            }
            if wins:
                meta["procurement_result"] = wins
            pages.append({
                "url": url,
                "title": it.get("title") or "",
                "markdown": detail_text[:5000] or it.get("title") or "",
                "meta": meta,
                "published_at": it.get("published_at"),
            })
    return pages


_BJ_URL_PREFIX = "//www.ccgp-beijing.gov.cn"


def _beijing_fetch_html(url: str, timeout: float = 30.0) -> str:
    """抓取北京市政府采购网静态页, 自动处理编码。"""
    try:
        resp = httpx.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Referer": "http://www.ccgp-beijing.gov.cn/",
        }, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        raw = resp.content
        for enc in ("utf-8", "gb18030", "gbk"):
            try:
                return raw.decode(enc)
            except Exception:  # noqa: BLE001
                continue
        return raw.decode("gb18030", errors="replace")
    except Exception as e:  # noqa: BLE001
        logger.warning("[beijing] fetch %s error: %s", url, e)
        return ""


def _beijing_winners(html: str) -> list:
    """从北京政采详情页提取中标供应商列表。

    详情页常见两种结构:
      1. 文本: 中标成交供应商名称：X 中标成交供应商地址：Y 中标金额：Z万元 ...
      2. 表格: 供应商名称/供应商地址/统一信用代码/中标金额 列
    返回 [{supplier, address, amount}]。
    """
    import re as _re
    text = _re.sub(r"(?i)<script.*?</script>|<style.*?</style>", "", html)
    text = _re.sub(r"<br\s*/?>", "\n", text)
    text = _re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", text)
    text = _re.sub(r"<[^>]+>", " ", text)
    text = _re.sub(r"&nbsp;", " ", text)
    text = _re.sub(r"\s+", " ", text)

    results = []
    # 结构1: 成对的 名称/地址/金额
    for m in _re.finditer(
        r"中标成交供应商名称[：:]\s*([^\s，。；]+?(?:（[^）]*）)?[^\s，。；]*)"
        r"\s*中标成交供应商地址[：:]\s*([^ ]+?)"
        r"\s*中标金额[：:]\s*([\d.,]+)\s*(万元|元)?",
        text,
    ):
        supplier = m.group(1).strip()
        if not supplier or "供应商" in supplier or len(supplier) < 4:
            continue
        results.append({
            "supplier": supplier[:120],
            "address": m.group(2).strip()[:200],
            "amount": (m.group(3) + (m.group(4) or "")).strip(),
        })
    if results:
        return results
    # 结构2: 表格 "供应商名称 供应商地址 统一信用代码 中标金额"
    rows = _re.findall(
        r"供应商名称[：:]?\s*(?:</td>\s*)?([^\s<，;；]+?)"
        r"\s*(?:供应商地址|</td>\s*<td>)\s*[：:]?([^\s<，;；]+?)"
        r"\s*(?:统一信用代码|</td>\s*<td>)\s*[：:]?[^\s<，;；]*"
        r"\s*(?:中标金额|</td>\s*<td>)\s*[：:]?([\d.,]+)\s*(万元|元)?",
        text,
    )
    for supplier, addr, amt, unit in rows:
        if not supplier or "供应商" in supplier or len(supplier) < 4:
            continue
        results.append({
            "supplier": supplier[:120],
            "address": addr[:200],
            "amount": (amt + (unit or "")).strip(),
        })
    return results


def _beijing_crawl_list(source: WebSource, task: str, logf) -> list:
    """采集北京市政府采购网中标/成交公告列表 + 详情, 返回入库 page dict 列表。

    source.url 形如: http://www.ccgp-beijing.gov.cn/xxgg/sjxxgg/zbggs/A002004001002index_1.htm
    列表页静态 HTML, 每条 <li><a href=".../YYYY/M/xxx.htm">标题</a><span class=datetime>日期</span></li>;
    max_depth 控制翻页页数, max_pages 控制总条数上限。
    """
    list_url = source.url
    pages = []
    seen = set()
    page_count = max(int(source.max_depth or 10), 1)
    idx = 0
    for page_no in range(1, page_count + 1):
        if page_no == 1:
            cur = list_url
        else:
            cur = list_url.replace("index_1.htm", f"index_{page_no}.htm")
        html = _beijing_fetch_html(cur)
        if not html:
            logf(f"北京政采第 {page_no} 页列表抓取失败(空响应)", "error")
            break
        import re as _re
        items = _re.findall(
            r'<a href="(//www\.ccgp-beijing\.gov\.cn/xxgg/[^"]+\.htm)"[^>]*>(?:<[^>]+>)?([\s\S]{0,90}?)</a>'
            r'<span[^>]*class="[^"]*datetime[^"]*"[^>]*>([\d-]+)',
            html,
        )
        logf(f"北京政采第 {page_no} 页列表解析到 {len(items)} 条公告", "info")
        if not items:
            break
        for href, title, date in items:
            title = _re.sub(r"<[^>]+>", "", title).strip()
            if not title:
                continue
            url = ("https:" + href) if href.startswith("//") else href
            if url in seen:
                continue
            seen.add(url)
            if int(source.max_pages or 200) > 0 and len(seen) > int(source.max_pages or 200):
                return pages
            idx += 1
            logf(f"[{idx}] 抓详情: {title[:30]}", "info")
            detail_html = _beijing_fetch_html(url)
            wins = _beijing_winners(detail_html)
            detail_text = _ccgp_html_to_text(detail_html)
            meta = {
                "purchaser": "",
                "region": "北京",
                "published_at": date,
                "notice_type": "中标（成交）公告",
            }
            if wins:
                meta["procurement_result"] = wins
            pages.append({
                "url": url,
                "title": title,
                "markdown": detail_text[:5000] or title,
                "meta": meta,
                "published_at": date,
            })
    return pages


def _parse_ccgp_list_items(html: str) -> list:
    """解析中国政府采购网列表页的公告条目。

    结构: <li><a href="/cggg/dfgg/zbgg/202608/t....htm">标题</a>
    标题旁有「中标公告 发布时间：xxx 地域：xx 采购人：xxx」文本。
    返回 [ {url,title,published_at,purchaser,region} ]。
    """
    import re as _re
    items = []
    # 匹配 <li ...> ... <a href="...">title</a> ... 区域文本
    for m in _re.finditer(r"<li[^>]*>([\s\S]{0,600}?)</li>", html):
        seg = m.group(1)
        am = _re.search(r"<a[^>]+href=\"([^\"]+\.htm)\"[^>]*>(?:<[^>]+>)?([\s\S]{0,90}?)</a>", seg)
        if not am:
            continue
        href = am.group(1)
        title = _re.sub(r"<[^>]+>", "", am.group(2)).strip()
        if not href.startswith("http"):
            href = href.replace("./", "https://www.ccgp.gov.cn/cggg/dfgg/zbgg/", 1) if href.startswith("./") \
                else "https://www.ccgp.gov.cn" + href
        if "zbgg" not in href and "cjgg" not in href:
            continue
        item = {"url": href, "title": title}
        tm = _re.search(r"发布时间[：:]\s*<em>([\s\S]{0,30}?)</em>", seg)
        if tm:
            item["published_at"] = tm.group(1).strip()
        rm = _re.search(r"地域[：:]\s*<em>([\s\S]{0,30}?)</em>", seg)
        if rm:
            item["region"] = rm.group(1).strip()
        pm = _re.search(r"采购人[：:]\s*<em>([\s\S]{0,60}?)</em>", seg)
        if pm:
            item["purchaser"] = pm.group(1).strip()
        items.append(item)
    return items


def _ccgp_html_to_text(html: str) -> str:
    """粗略把 ccgp 详情 HTML 转纯文本(标签去掉, 保留换行)。"""
    import re as _re
    html = _re.sub(r"(?i)<script.*?</script>|<style.*?</style>", "", html)
    html = _re.sub(r"<br\s*/?>", "\n", html)
    html = _re.sub(r"</(p|div|tr|li|h[1-6])>", "\n", html)
    text = _re.sub(r"<[^>]+>", "", html)
    text = _re.sub(r"&nbsp;", " ", text)
    text = _re.sub(r"[ \t]+", " ", text)
    return text


def _mark_clue_irrelevant(db: Session, url: str, reason: str) -> None:
    """AI 筛选不相关: 软删除该 URL 的线索(若已插入)。"""
    if not url:
        return
    clue = db.execute(select(WebClue).where(WebClue.url == url, WebClue.is_deleted == False)).scalar_one_or_none()
    if clue:
        clue.is_deleted = True
        meta = clue.meta or {}
        if isinstance(meta, dict):
            meta["ai_reject_reason"] = reason
            clue.meta = meta
        db.commit()


def _insert_if_passed(db: Session, source: Optional[WebSource], page: dict, flt: ClueFilter) -> dict:
    """单个网页筛选: 通过则入库, 未通过返回 rejected 结果(不写库)。"""
    title = page.get("title") or ""
    markdown = page.get("markdown") or ""
    url = page.get("url") or ""
    # 空内容: 可能是 JS 渲染失败 / 反爬拦截, 给出明确原因
    if not markdown.strip():
        return {"url": url, "title": title[:100], "passed": False,
                "reason": "页面内容为空(可能是 JS 渲染失败或被反爬拦截)"}
    res = flt.filter(url, title, markdown)
    if not res.passed:
        return {"url": url, "title": title[:100], "passed": False, "reason": res.reason}
    # 按公告开始/截止时间窗口过滤
    t_reason = _time_window_reject(page.get("meta"))
    if t_reason:
        return {"url": url, "title": title[:100], "passed": False, "reason": t_reason}

    # 查重: 已存在(含软删除)则幂等刷新内容(重新抓取时升级为完整正文)
    existing = db.execute(select(WebClue).where(WebClue.url == url)).scalar_one_or_none()
    if existing:
        existing.is_deleted = False
        existing.title = title[:512]
        existing.summary = markdown[:300] or None
        existing.content = markdown or None
        existing.source_id = source.id if source else None
        existing.source_name = source.name if source else None
        existing.hit_keywords = ",".join(res.hit_keywords) or None
        existing.region = res.region
        existing.category = res.category
        existing.meta = page.get("meta")
        if page.get("published_at"):
            try:
                existing.published_at = datetime.datetime.fromisoformat(
                    str(page["published_at"]).replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                pass
        try:
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        return {"url": url, "title": title[:100], "passed": True, "duplicate": True}

    clue = WebClue(
        url=url,
        title=title[:512],
        summary=markdown[:300] or None,
        content=markdown or None,
        source_id=source.id if source else None,
        source_name=source.name if source else None,
        hit_keywords=",".join(res.hit_keywords) or None,
        region=res.region,
        category=res.category,
        status="accepted",
        meta=page.get("meta"),
    )
    if page.get("published_at"):
        try:
            clue.published_at = datetime.datetime.fromisoformat(str(page["published_at"]).replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            pass
    db.add(clue)
    try:
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.warning("web_clue insert failed url=%s err=%s", url, e)
        return {"url": url, "title": title[:100], "passed": True, "duplicate": True}
    return {"url": url, "title": title[:100], "passed": True}


def _run_source_crawl(db: Session, source: WebSource, task_id: str = "") -> dict:
    """按来源配置抓取并筛选: 返回统计。"""
    task = task_id or f"s{source.id}-{int(time.time() * 1000)}"
    push_crawl_log(task, f"开始抓取来源「{source.name}」 url={source.url}", "info")
    flt = ClueFilter(
        allow_domains=source.allow_domains or "",
        keywords=source.keywords or "",
        exclude_keywords=source.exclude_keywords or "",
        regions=source.regions or "",
    )
    stats = {"total": 0, "accepted": 0, "rejected": 0, "rejected_reasons": []}
    try:
        if source.scrape_mode == "query":
            # 查询式抓取: OCR 验证码 + 模拟查询(用来源关键词在站内检索), 公告列表接口返回 JSON 行
            qconfig = _parse_query_config(source.query_config) or {}
            push_crawl_log(task, "查询式抓取: 打开页面 → OCR 验证码 → 关键词检索中...", "info")
            # 后台轮询 crawl4ai 服务的查询式抓取进度, 实时透出到日志
            progress_seen: set = set()
            progress_stop = threading.Event()

            def _poll_query_progress():
                # 分批抓取时每批 task_id 带 -b{i} 后缀(如 pipe-s1-b1), 必须轮询所有批次 key 才能透出进度。
                # 关键: 取 ts 最新的进度(而非第一个有 stage 的)——否则上一批残留的「完成」状态
                # 会一直抢占, 后续批次的新进度永远透不出来(观感像卡死)。
                kw_count = len([k for k in (source.keywords or "").split(",") if k and k.strip()]) or 1
                progress_keys = [task] + [f"{task}-b{i}" for i in range(1, kw_count + 1)]
                while not progress_stop.is_set():
                    try:
                        best = None
                        for pk in progress_keys:
                            resp = httpx.get(
                                f"{crawl4ai_client.base_url}/query-progress/{pk}",
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                pj = resp.json() or {}
                                if pj.get("stage") and (best is None or (pj.get("ts") or "") > (best.get("ts") or "")):
                                    best = pj
                        stage = (best or {}).get("stage") or ""
                        detail = (best or {}).get("detail") or ""
                        if not stage:
                            continue
                        key = f"{stage}|{detail}"
                        if key not in progress_seen:
                            progress_seen.add(key)
                            push_crawl_log(task, f"[查询式] {stage}: {detail}", "info")
                    except Exception:  # noqa: BLE001
                        pass
                    progress_stop.wait(2.0)

            poll_thread = threading.Thread(target=_poll_query_progress, daemon=True)
            poll_thread.start()
            try:
                # 分批抓取: 按关键词每批 1 个(避免多关键词单次请求超时), 每批 900s 超时
                kw = source.keywords or ""
                if kw and "," in kw:
                    push_crawl_log(task, f"分批抓取: {kw.count(',') + 1} 个关键词, 每批 1 个", "info")
                    result = crawl4ai_client.query_crawl_batched(
                        source.url,
                        query_config=qconfig,
                        # 查询式翻页: 每页 10 条, 默认最多 5 页(50 条)
                        max_pages=max(1, min(int(source.max_pages or 5), 5)),
                        search_keywords=kw,
                        batch_size=1,
                        timeout_per_batch=900.0,
                        task_id=task,
                    )
                    # 把分批统计写入日志
                    for b in (result.get("batches") or []):
                        if b.get("ok"):
                            push_crawl_log(task, f"批次 {b['batch']}「{','.join(b['keywords'])}」: 抓到 {b.get('count', 0)} 条", "info")
                        else:
                            push_crawl_log(task, f"批次 {b['batch']}「{','.join(b.get('keywords',[]))}」失败: {b.get('error','')}", "warn")
                else:
                    result = crawl4ai_client.query_crawl(
                        source.url,
                        query_config=qconfig,
                        max_pages=max(1, min(int(source.max_pages or 5), 5)),
                        search_keywords=kw,
                        task_id=task,
                        timeout=900.0,
                    )
            finally:
                progress_stop.set()
                poll_thread.join(timeout=3)
            if result.get("error"):
                stats["rejected_reasons"].append(f"查询式抓取: {result['error']}")
                push_crawl_log(task, f"查询式抓取错误: {result['error']}", "error")
            data_list = result.get("data") or []
            push_crawl_log(task, f"共检索到 {len(data_list)} 条公告(去重后), 开始逐条抓详情与筛选...", "info")
            for idx, item in enumerate(data_list, 1):
                meta = item.get("meta") or {}
                title = item.get("title") or ""
                desc = item.get("description") or ""
                detail_content = item.get("detail_content") or ""
                item_url = item.get("url") or ""
                # 公告无独立详情 URL 时, 用公告 id 构造合成 URL 保证唯一入库
                if not item_url and (meta.get("noticeId") or meta.get("id")):
                    nid = meta.get("noticeId") or meta.get("id")
                    item_url = f"{source.url}#notice-{nid}"
                # 正文优先用完整详情正文(含资格/资质要求), 否则用描述/标题
                markdown = detail_content or desc or title
                # 结构化字段(项目概况/资格要求/资质)并入 meta
                for k in ("overview", "qualification", "specific_qualification"):
                    if item.get(k):
                        meta[k] = item[k]
                page = {
                    "url": item_url or source.url,
                    "title": title,
                    "markdown": markdown,
                    "meta": meta,
                    "published_at": item.get("published_at"),
                }
                stats["total"] += 1
                r = _insert_if_passed(db, source, page, flt)
                if r["passed"]:
                    # AI 语义筛选(可选): 配置 llm_enhance 含 filter 时启用
                    ai_mode = (source.llm_enhance or "").strip()
                    if ai_mode in ("filter", "all"):
                        try:
                            push_crawl_log(task, f"[{idx}/{len(data_list)}] AI 语义筛选: {title[:30]}...", "info")
                            ai = llm_enhance.ai_filter(
                                title, markdown,
                                domain_hints=source.keywords or "",
                            )
                            if not ai.get("relevant"):
                                stats["rejected"] += 1
                                reason = f"AI筛选不相关: {ai.get('reason') or ''}"
                                stats["rejected_reasons"].append(reason)
                                logger.info("[llm] rejected clue %s: %s", title[:40], reason)
                                push_crawl_log(task, f"[{idx}/{len(data_list)}] ✗ {title[:30]} — {reason}", "warn")
                                # 丢弃已入库的线索(如果刚插入)
                                _mark_clue_irrelevant(db, item_url or source.url, reason)
                                continue
                            push_crawl_log(task, f"[{idx}/{len(data_list)}] ✓ {title[:30]} — AI 相关", "info")
                        except Exception as e:  # noqa: BLE001
                            logger.warning("[llm] filter error: %s", e)
                    stats["accepted"] += 1
                    push_crawl_log(task, f"[{idx}/{len(data_list)}] 入库: {title[:30]}", "info")
                else:
                    stats["rejected"] += 1
                    stats["rejected_reasons"].append(r["reason"])
                    push_crawl_log(task, f"[{idx}/{len(data_list)}] 丢弃: {title[:30]} — {r['reason']}", "warn")
        elif source.scrape_mode == "ccgp_list":
            # 中国政府采购网全国中标公告(静态页, 无需验证码): 列表+详情采集
            push_crawl_log(task, "ccgp 全国中标公告采集: 列表 → 逐条详情 → 提取供应商", "info")
            data_list = _ccgp_crawl_list(
                source, task,
                logf=lambda m, l="info": push_crawl_log(task, m, l),
            )
            for item in data_list:
                stats["total"] += 1
                r = _insert_if_passed(db, source, item, flt)
                if r["passed"]:
                    stats["accepted"] += 1
                    push_crawl_log(task, f"入库: {(item.get('title') or '')[:30]}", "info")
                else:
                    stats["rejected"] += 1
                    stats["rejected_reasons"].append(r["reason"])
        elif source.scrape_mode == "beijing_list":
            # 北京市政府采购网中标/成交公告(静态页, 无验证码): 列表+详情采集
            push_crawl_log(task, "北京政采中标公告采集: 列表 → 逐条详情 → 提取供应商", "info")
            data_list = _beijing_crawl_list(
                source, task,
                logf=lambda m, l="info": push_crawl_log(task, m, l),
            )
            for item in data_list:
                stats["total"] += 1
                r = _insert_if_passed(db, source, item, flt)
                if r["passed"]:
                    stats["accepted"] += 1
                    push_crawl_log(task, f"入库: {(item.get('title') or '')[:30]}", "info")
                else:
                    stats["rejected"] += 1
                    stats["rejected_reasons"].append(r["reason"])
                    push_crawl_log(task, f"丢弃: {(item.get('title') or '')[:30]} — {r['reason']}", "warn")
        elif source.scrape_mode == "scrape":
            page = crawl4ai_client.scrape(source.url, max_depth=source.max_depth)
            stats["total"] += 1
            r = _insert_if_passed(db, source, page, flt)
            if r["passed"]:
                stats["accepted"] += 1
            else:
                stats["rejected"] += 1
                stats["rejected_reasons"].append(r["reason"])
        else:
            pages = crawl4ai_client.crawl(
                source.url,
                max_depth=source.max_depth,
                max_pages=source.max_pages,
                include_urls=source.include_urls or "",
            )
            data_list = pages.get("data") or []
            for item in data_list:
                page = {
                    "url": (item.get("meta") or {}).get("url") or item.get("url", ""),
                    "title": (item.get("meta") or {}).get("title") or item.get("title", "") or "",
                    "markdown": item.get("markdown") or item.get("content") or "",
                    "meta": item.get("meta"),
                    "published_at": item.get("published_at") or (item.get("meta") or {}).get("date"),
                }
                stats["total"] += 1
                r = _insert_if_passed(db, source, page, flt)
                if r["passed"]:
                    stats["accepted"] += 1
                else:
                    stats["rejected"] += 1
                    stats["rejected_reasons"].append(r["reason"])
        source.last_run_at = datetime.datetime.now()
        source.last_run_result = f"抓取 {stats['total']} 页, 通过 {stats['accepted']} 条, 丢弃 {stats['rejected']} 条"
        source.last_error = None
        db.commit()
        push_crawl_log(task, f"抓取完成: 共 {stats['total']} 条, 入库 {stats['accepted']} 条, 丢弃 {stats['rejected']} 条", "success")
    except Crawl4aiError as e:
        source.last_error = str(e)
        push_crawl_log(task, f"抓取失败: {e}", "error")
        db.commit()
        raise
    return stats


@router.post("/crawl-source/{source_id}")
async def crawl_source(source_id: int, db: Session = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    """按来源配置抓取并筛选(通过才入库)。

    改为后台线程执行: 立即返回 task_id, 前端轮询 /web-clues/logs?task_id= 查看实时进度。
    """
    source = db.execute(select(WebSource).where(WebSource.id == source_id, WebSource.is_deleted == False)).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="来源站点不存在")
    if not source.enabled:
        raise HTTPException(status_code=400, detail="来源站点已禁用")

    # 同一来源已有运行中任务: 不重复启动, 直接返回现有 task_id 供前端续看日志
    active_task = get_active_crawl(source.id)
    if active_task:
        return {"source_id": source.id, "source_name": source.name, "task_id": active_task,
                "status": "running", "resumed": True}

    task_id = f"s{source.id}-{int(time.time() * 1000)}"
    clear_crawl_logs(task_id)
    push_crawl_log(task_id, "任务已提交, 后台开始抓取...", "info")
    register_active_crawl(source.id, task_id)

    def _worker():
        try:
            from app.database import SessionLocal
            with SessionLocal() as wdb:
                src = wdb.execute(select(WebSource).where(WebSource.id == source_id)).scalar_one_or_none()
                if src:
                    _run_source_crawl(wdb, src, task_id)
                else:
                    push_crawl_log(task_id, "来源不存在", "error")
        except Exception as e:  # noqa: BLE001
            logger.exception("crawl worker error")
            push_crawl_log(task_id, f"抓取线程异常: {e}", "error")
        finally:
            # 任务结束清理活跃登记(超时兜底: 12 分钟后即使线程未退也允许重新发起)
            clear_active_crawl(source.id, task_id)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return {"source_id": source.id, "source_name": source.name, "task_id": task_id,
            "status": "running"}


@router.post("/crawl-manual")
async def crawl_manual(data: ManualCrawlRequest, db: Session = Depends(get_db),
                       user: dict = Depends(get_current_user)):
    """手动提交一批 URL 抓取并筛选(通过才入库)"""
    flt = ClueFilter(
        allow_domains="",
        keywords=data.keywords or "",
        exclude_keywords=data.exclude_keywords or "",
        regions=data.regions or "",
    )
    stats = {"total": 0, "accepted": 0, "rejected": 0, "rejected_reasons": []}
    for url in data.urls:
        try:
            page = crawl4ai_client.scrape(url)
        except Crawl4aiError as e:
            stats["rejected"] += 1
            stats["rejected_reasons"].append(str(e))
            continue
        stats["total"] += 1
        r = _insert_if_passed(db, None, page, flt)
        if r["passed"]:
            stats["accepted"] += 1
        else:
            stats["rejected"] += 1
            stats["rejected_reasons"].append(r["reason"])
    return stats
