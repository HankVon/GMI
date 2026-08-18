"""数据流水线编排服务 — 采集 → 筛选入库 → 实体识别 → 图谱构建 → 前端字段回填。

设计目标: 数据不足但必须保证质量。把零散的采集/筛选/图谱/回填能力串成完整链路。

四阶段:
  1. COLLECT  数据采集 — 从多个来源(政务意向源/网页线索源/中标解析)抓取原始信息
  2. FILTER   条件筛选入库 — 管道级规则(地域川藏新/时效/主题关键词/去重/排除词)清洗, 只留有效数据
  3. GRAPH    实体识别 + 知识图谱 — NER 抽单位/人员/项目, 关系落 Neo4j+MySQL
  4. BACKFILL 前端字段回填 — 识别出的单位/人员自动创建或补全字段(法人/电话/地址等)

每一阶段可单独执行, 也可全链路串联。全程记录统计日志。
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.web_source import WebSource
from app.models.web_clue import WebClue
from app.models.company import Company
from app.models.person import Person
from app.models.project import Project
from app.services.china_regions import extract_target_province, is_target_province

logger = logging.getLogger("data_pipeline")

# ============================================================
# 流水线实时过程日志(内存环形缓冲, 供前端「一键执行」实时查看进度)
# ============================================================
import threading

_pipeline_logs: list = []
_pipeline_log_lock = threading.Lock()
_PIPELINE_LOG_MAX = 1500

_STAGE_ZH = {"collect": "采集", "filter": "筛选入库", "graph": "图谱构建", "backfill": "前端回填"}


def push_log(stage: str, msg: str, level: str = "info") -> None:
    """追加流水线过程日志。stage ∈ collect/filter/graph/backfill/general。"""
    entry = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "stage": stage,
        "msg": str(msg),
        "level": level,
    }
    with _pipeline_log_lock:
        _pipeline_logs.append(entry)
        if len(_pipeline_logs) > _PIPELINE_LOG_MAX:
            del _pipeline_logs[: len(_pipeline_logs) - _PIPELINE_LOG_MAX]


def get_pipeline_logs(limit: int = 200) -> list:
    with _pipeline_log_lock:
        return list(_pipeline_logs[-limit:])


def clear_pipeline_logs() -> None:
    with _pipeline_log_lock:
        _pipeline_logs.clear()


# ============================================================
# 管道级筛选规则(可配置, 用户可按需调整)
# ============================================================
# 主题关键词: 命中任意即视为「行业相关」, 空=全部接受
# 用户确认六大方向: 地质 / 地灾 / 矿业 / 水文 / 规划 / 生态
TOPIC_KEYWORDS = [
    # 地质
    "地质", "勘察", "勘查", "测绘", "岩土", "探矿", "钻探", "地勘",
    # 地灾
    "地质灾害", "地灾", "滑坡", "崩塌", "泥石流", "地面沉降",
    # 矿业
    "矿业权", "采矿", "矿产", "矿山", "资源储量", "矿权",
    # 水文
    "水文", "水资源", "水利", "水库", "堤防", "防洪",
    # 规划
    "规划", "国土空间", "土地利用", "用途管制", "总体规划", "专项规划",
    # 生态
    "生态修复", "环境治理", "矿山修复", "土壤修复", "水污染治理", "生态保护",
]
# 排除关键词: 命中任意即丢弃(非项目/废数据)
EXCLUDE_KEYWORDS = ["招聘", "办公设备", "复印机", "打印机", "电脑耗材", "办公用品",
                    "会议通知", "培训通知", "征求意见稿", "中标结果公告（废标）", "废标公告",
                    "食材", "食堂", "食品", "家具", "空调", "物业"]
# 目标省份: 只保留 四川/西藏/新疆(严格限定)
TARGET_PROVINCES = ["四川", "西藏", "新疆"]
# 时效窗口: 公告实际发布时间距今超过该天数不入库(用户确认 180 天)
MAX_AGE_DAYS = 180
# 最小正文长度(字符), 太短视为废数据
MIN_CONTENT_LEN = 50


class FilterRules:
    """管道级筛选规则。字段均可按需覆盖。"""

    def __init__(self, topic_keywords=None, exclude_keywords=None, target_provinces=None,
                 max_age_days=None, min_content_len=None):
        self.topic_keywords = topic_keywords or TOPIC_KEYWORDS
        self.exclude_keywords = exclude_keywords or EXCLUDE_KEYWORDS
        self.target_provinces = target_provinces or TARGET_PROVINCES
        self.max_age_days = max_age_days if max_age_days is not None else MAX_AGE_DAYS
        self.min_content_len = min_content_len if min_content_len is not None else MIN_CONTENT_LEN

    def to_dict(self) -> dict:
        return {
            "topic_keywords": self.topic_keywords,
            "exclude_keywords": self.exclude_keywords,
            "target_provinces": self.target_provinces,
            "max_age_days": self.max_age_days,
            "min_content_len": self.min_content_len,
        }


def _published_dt(published_at) -> Optional[datetime]:
    if isinstance(published_at, datetime):
        return published_at
    if isinstance(published_at, str) and published_at:
        try:
            return datetime.fromisoformat(published_at.replace("Z", ""))
        except ValueError:
            pass
    return None


def _content_of(clue) -> str:
    meta = clue.meta if isinstance(clue.meta, dict) else {}
    return " ".join(filter(None, [
        clue.title or "", clue.summary or "", clue.content or "",
        meta.get("overview") or "", meta.get("qualification") or "",
    ]))


def check_quality(clue, rules: Optional[FilterRules] = None) -> tuple[bool, str]:
    """管道级质量检查: (是否通过, 未通过原因)。

    规则(全部满足才通过):
      1. 主题相关: 标题/正文命中 TOPIC_KEYWORDS 任一(命中排除词则直接丢弃)
      2. 地域过滤: 标题 + region 命中 川藏新 任一省市县词
         (正文不参与地域判定 — 公告正文常含"四川省"等无关提及, 会误匹配非川藏新公告)
      3. 时效: 实际发布时间距今 <= max_age_days(无时间则通过)
      4. 非废数据: 正文长度 >= min_content_len
    """
    rules = rules or FilterRules()
    content = _content_of(clue)
    # 标题 + region(不含正文) 用于地域/主题判定
    head_pool = f"{clue.title or ''} {clue.region or ''}"
    full_pool = f"{head_pool} {content}"

    # 1) 排除词优先(全文)
    for kw in rules.exclude_keywords:
        if kw and kw in full_pool:
            return False, f"命中排除词「{kw}」"
    # 2) 主题相关(标题优先, 正文兜底)
    if rules.topic_keywords:
        head_hit = any(k in head_pool for k in rules.topic_keywords if k)
        full_hit = any(k in full_pool for k in rules.topic_keywords if k)
        if not (head_hit or full_hit):
            return False, "未命中主题关键词(非地质/招标/采购相关)"
    # 3) 地域过滤(川藏新): 仅标题 + region 判定, 防正文误匹配
    prov = extract_target_province(head_pool)
    if not prov or not is_target_province(prov):
        return False, "非目标省份(标题/地域无川藏新, 仅四川/西藏/新疆)"
    # 4) 时效
    published = _published_dt(clue.published_at)
    if published and (datetime.now() - published).days > rules.max_age_days:
        return False, f"发布时间超期({(datetime.now() - published).days}天 > {rules.max_age_days}天)"
    # 5) 非废数据
    if len(content.strip()) < rules.min_content_len:
        return False, "正文过短(疑似废数据)"
    return True, ""


# ============================================================
# 阶段 1: 采集
# ============================================================
def stage_collect(db: Session, include_intent: bool = True, include_clues: bool = True,
                  include_bids: bool = True) -> dict:
    """采集: 调用各来源抓取, 汇总统计。

    意向源 → intent_notice; 网页线索 → web_clue; 中标公告 → bid_notice(从 web_clue 解析)。
    返回各源采集数。注: 实际抓取为同步耗时操作, 建议后台线程执行。
    """
    stats = {"intent": 0, "clues": 0, "bids": 0, "sources": 0}

    if include_intent:
        try:
            from app.services.intent_crawler import crawl_intent_source
            srcs = db.execute(
                select(WebSource).where(
                    WebSource.is_deleted == False, WebSource.enabled == True,
                    WebSource.scrape_mode == "intent").order_by(WebSource.id)
            ).scalars().all()
            push_log("collect", f"意向采集: 共 {len(srcs)} 个政务意向源", "info")
            for s in srcs:
                try:
                    push_log("collect", f"意向源「{s.name}」开始抓取…", "info")
                    r = crawl_intent_source(db, s)
                    stored = r.get("stored", 0)
                    stats["intent"] += stored
                    stats["sources"] += 1
                    push_log("collect", f"意向源「{s.name}」完成: 列表 {r.get('listed', 0)} 条, 入库 {stored} 条",
                             "info" if stored else "warn")
                except Exception as e:  # noqa: BLE001
                    logger.error("意向源[%s]采集失败: %s", s.name, e)
                    push_log("collect", f"意向源「{s.name}」失败: {e}", "error")
                    stats.setdefault("intent_errors", []).append(f"{s.name}: {e}")
        except Exception as e:  # noqa: BLE001
            logger.error("意向采集失败: %s", e)
            stats["intent_error"] = str(e)

    if include_clues:
        sources = db.execute(
            select(WebSource).where(WebSource.is_deleted == False,
                                    WebSource.scrape_mode.in_(["crawl", "scrape", "query"])).order_by(WebSource.id)
        ).scalars().all()
        from app.api.v1.web_clues import (_run_source_crawl, list_crawl_logs, clear_crawl_logs,
                                          get_active_crawl, register_active_crawl, clear_active_crawl)
        push_log("collect", f"网页线索采集: 共 {len(sources)} 个线索源", "info")
        for src in sources:
            # 防并发: 该源已有抓取任务在跑(来源管理页触发或本流水线), 跳过以免重复抓取+互相拖慢
            active_task = get_active_crawl(src.id)
            if active_task:
                push_log("collect", f"线索源「{src.name}」正在抓取中(任务 {active_task}), 跳过(防并发重复)", "warn")
                continue
            sub_task = f"pipe-s{src.id}"
            try:
                clear_crawl_logs(sub_task)
                register_active_crawl(src.id, sub_task)  # 登记, 防本流水线/来源页二次并发
                if src.scrape_mode == "query":
                    push_log("collect", f"线索源「{src.name}」开始抓取(查询式: 验证码+逐词检索+逐条详情, 预计数分钟, 请稍候)…", "info")
                else:
                    push_log("collect", f"线索源「{src.name}」开始抓取…", "info")
                # 实时桥接该源的抓取明细日志到流水线日志 — 查询式抓取耗时长, 必须边抓边透出
                # (原实现放在调用后才批量读回, 导致源执行期间日志面板长时间无新条目, 观感像卡死)
                seen_logs: set = set()
                forward_stop = threading.Event()

                def _forward_sub_logs():
                    while not forward_stop.is_set():
                        try:
                            for e in list_crawl_logs(sub_task):
                                key = (e.get("ts"), e.get("msg"))
                                if key in seen_logs:
                                    continue
                                seen_logs.add(key)
                                push_log("collect", e.get("msg", ""), e.get("level", "info"))
                        except Exception:  # noqa: BLE001
                            pass
                        forward_stop.wait(1.0)

                ft = threading.Thread(target=_forward_sub_logs, daemon=True)
                ft.start()
                try:
                    r = _run_source_crawl(db, src, task_id=sub_task)
                finally:
                    forward_stop.set()
                    ft.join(timeout=3)
                    # 兜底: 转发线程退出前遗漏的最后几条
                    for e in list_crawl_logs(sub_task):
                        key = (e.get("ts"), e.get("msg"))
                        if key in seen_logs:
                            continue
                        seen_logs.add(key)
                        push_log("collect", e.get("msg", ""), e.get("level", "info"))
                accepted = r.get("accepted", 0)
                stats["clues"] += accepted
                stats["sources"] += 1
                push_log("collect", f"线索源「{src.name}」完成: 入库 {accepted} 条, 丢弃 {r.get('rejected', 0)} 条",
                         "info" if accepted else "warn")
            except Exception as e:  # noqa: BLE001
                logger.error("线索源[%s]采集失败: %s", src.name, e)
                push_log("collect", f"线索源「{src.name}」失败: {e}", "error")
                stats.setdefault("source_errors", []).append(f"{src.name}: {e}")
            finally:
                clear_active_crawl(src.id, sub_task)

    if include_bids:
        try:
            from app.services.bid_network import parse_bid_clues
            push_log("collect", "中标解析: 从已入库线索解析中标公告…", "info")
            r = parse_bid_clues(db)
            stats["bids"] = r.get("parsed", 0)
            push_log("collect", f"中标解析完成: 解析 {stats['bids']} 条中标公告", "info")
        except Exception as e:  # noqa: BLE001
            logger.error("中标解析失败: %s", e)
            stats["bid_error"] = str(e)
            push_log("collect", f"中标解析失败: {e}", "error")

    return stats


# ============================================================
# 阶段 2: 筛选入库(质量过滤)
# ============================================================
def parse_contacts_from_text(text: str) -> dict:
    """从公告正文解析 采购人/代理机构/项目联系人 联系方式(与 crawl4ai 服务端版逻辑一致)。

    返回 {purchaser:{name,addr,contact,phone}, agency:{...}, project:{contact,phone}}
    鲁棒性: 无「凡对本次公告…」头也扫全文锚点; 联系方式段后跟落款/日期不受影响。
    """
    empty = {"purchaser": {}, "agency": {}, "project": {}}
    if not text:
        return empty
    tail = text
    for marker in ("凡对本次公告内容提出询问", "按以下方式联系"):
        idx = text.find(marker)
        if idx >= 0:
            tail = text[idx:]
            break
    for tail_kw in ("相关附件", "附件：", "附件:"):
        t = tail.find(tail_kw)
        if t > 0:
            tail = tail[:t]
    sections = {}
    for m in re.finditer(r"(\d\.|（\d）)?\s*(采购人信息|采购代理机构信息|代理机构信息|项目联系方式|采购人|采购代理机构|项目联系人|采购人名称|代理机构名称)", tail):
        key = (m.group(2) or "").strip()
        if "采购人" in key:
            sections.setdefault("purchaser", m.start())
        elif "代理" in key:
            sections.setdefault("agency", m.start())
        elif key in ("项目联系方式", "项目联系人"):
            sections.setdefault("project", m.start())
    if not sections:
        return empty
    ordered = sorted(sections.items(), key=lambda x: x[1])
    result = empty
    for i, (key, pos) in enumerate(ordered):
        end = ordered[i + 1][1] if i + 1 < len(ordered) else len(tail)
        seg = tail[pos:end]
        if key == "project":
            name = ""
            m = re.search(r"项目联系人[：:\s]*([\u4e00-\u9fa5·]{2,4})", seg)
            if m:
                name = m.group(1)
            elif not name:
                m0 = re.search(r"(?:联系人|采购人代表)[：:\s]*([\u4e00-\u9fa5·]{2,4})", seg)
                if m0:
                    name = m0.group(1)
            m2 = re.search(r"(?:项目)?(?:联系)?电话[：:\s]*([0-9\-()（）\s]{6,20})", seg)
            if name and not _is_valid_person_name(name):
                name = ""   # 电话/角色/科室等误判为姓名 → 置空
            result["project"] = {"contact": name, "phone": m2.group(1).strip() if m2 else ""}
            continue
        d = {}
        m = re.search(r"名称[：:\s]*([^\n]{2,60})", seg)
        if m:
            d["name"] = m.group(1).strip()
        m = re.search(r"地址[：:\s]*([^\n]{2,80})", seg)
        if m:
            d["addr"] = m.group(1).strip()
        m = re.search(r"联系方式?[：:\s]*([^\n]{2,40})", seg)
        if m:
            d["contact"] = m.group(1).strip()
        elif not d.get("contact"):
            m1 = re.search(r"联系人[：:\s]*([\u4e00-\u9fa5·]{2,4})", seg)
            if m1:
                d["contact"] = m1.group(1).strip()
        m = re.search(r"([0-9\-()（）\s]{6,20})", seg.split("名称")[0])
        if m:
            d["phone"] = m.group(1).strip()
        elif d.get("contact"):
            m2 = re.search(r"([0-9][0-9\-()（）\s]{5,19})", d["contact"])
            if m2:
                d["phone"] = m2.group(1).strip()
        if d.get("phone"):
            p = re.sub(r"[)）]", "", d["phone"]).strip()
            p = re.sub(r"\s*-\s*", "-", p)
            p = re.sub(r"\s+", "-", p)
            d["phone"] = p
        result[key] = d
    return result


def stage_filter(db: Session, rules: Optional[FilterRules] = None, limit: int = 500) -> dict:
    """筛选: 对已入库但未标注质量的 web_clue 做管道级质量复检。

    - 不通过 → status='rejected' + 记录 quality_reason(软删除保留证据)
    - 通过但未转实体 → status='accepted'
    幂等: 已 rejected/accepted 的跳过(除非 force=True)。
    """
    rules = rules or FilterRules()
    clues = db.execute(
        select(WebClue).where(WebClue.is_deleted == False, WebClue.status.in_(["new", "accepted", "pending"]))
        .order_by(WebClue.fetched_at.desc()).limit(limit)
    ).scalars().all()
    push_log("filter", f"筛选入库: 复检 {len(clues)} 条未定级线索(川藏新/时效/主题/废数据)…", "info")

    passed, rejected = 0, 0
    details = []
    for i, c in enumerate(clues, 1):
        ok, reason = check_quality(c, rules)
        meta = dict(c.meta) if isinstance(c.meta, dict) else {}
        if not ok:
            c.status = "rejected"
            c.is_deleted = True  # 软删除(保留证据)
            meta["quality_reason"] = reason
            c.meta = meta
            rejected += 1
            if len(details) < 20:
                details.append({"url": c.url, "reason": reason})
        else:
            c.status = "accepted"
            meta.pop("quality_reason", None)
            c.meta = meta
            passed += 1
        if i % 100 == 0:
            push_log("filter", f"已复检 {i}/{len(clues)} 条(通过 {passed} / 拒绝 {rejected})", "info")
    db.commit()
    push_log("filter", f"筛选完成: 复检 {len(clues)} 条, 通过 {passed}, 拒绝 {rejected}", "info")
    return {"checked": len(clues), "passed": passed, "rejected": rejected,
            "rules": rules.to_dict(), "samples": details}


# ============================================================
# 阶段 3: 实体识别 + 知识图谱
# ============================================================
def stage_graph(db: Session, limit: int = 50, use_llm: bool = False) -> dict:
    """图谱: 对已接受且未抽取的 web_clue 建实体节点 + 关系。

    双通道(保证不依赖 Ollama 也能建出项目/单位/人员节点):
      1. 规则通道(必做): 从线索 meta/title 提取采购人(单位)/供应商(单位)/项目名,
         匹配或创建系统实体, 写 Neo4j 节点 + Project-PARTICIPATES_IN-Company/Person 关系
         (与 stage_backfill 共用, 幂等)
      2. LLM 通道(可选): use_llm=True 且 Ollama 可用时, 调 ingest_knowledge
         补充开放关系(entity_relation + Neo4j 开放边)
    """
    from app.services.real_project_import import (_find_company, _find_person, _find_project, _gen_code,
                                                  _add_project_company, _add_project_member)
    from app.services.neo4j_sync import (sync_company, sync_person, sync_project,
                                         sync_project_companies, sync_project_members,
                                         sync_company_colleagues)
    from app.models.project_member import ProjectMember
    from app.models.company import ProjectCompany

    clues = db.execute(
        select(WebClue).where(WebClue.is_deleted == False, WebClue.status == "accepted",
                              func.json_unquote(func.json_extract(WebClue.meta, "$.kg_done")).is_(None))
        .order_by(WebClue.fetched_at.desc()).limit(limit)
    ).scalars().all()
    push_log("graph", f"图谱构建: 待处理已接受线索 {len(clues)} 条…", "info")

    processed = 0
    nodes = {"companies": 0, "persons": 0, "projects": 0}
    rels = 0
    errors = []
    llm_rels = 0

    for c in clues:
        before_nodes = dict(nodes)
        rels_before = rels
        push_log("graph", f"[{processed + 1}/{len(clues)}] 抽取「{(c.title or '')[:36]}」", "info")
        meta = dict(c.meta) if isinstance(c.meta, dict) else {}
        purchaser = meta.get("purchaser") or ""
        suppliers = [s.get("supplier", "") for s in (meta.get("suppliers") or []) if s.get("supplier")]
        org_names = [purchaser] + suppliers
        org_names = [n.strip() for n in org_names if n and n.strip() and len(n.strip()) >= 4]
        region = c.region or meta.get("regionName") or extract_target_province(f"{c.title or ''}")

        project = None
        project_name = _derive_project_name(c.title or "", purchaser)
        if project_name:
            project = _find_project(db, project_name)
            created_proj = False
            if not project:
                project = Project(
                    code=_gen_code("PRJ-PIP"), name=project_name, status="active",
                    description=_content_of(c)[:20000],
                )
                db.add(project)
                db.flush()
                created_proj = True
            # 统一补全: ext_attrs(类别/省份/金额/业主/联系人/来源) + 起止日期 + 进度记录(阶段/更新时间)
            _fill_project_fields(db, project, c, meta, region)
            if created_proj:
                nodes["projects"] += 1

        comp_ids = []
        if project:
            for i, name in enumerate(dict.fromkeys(org_names)):
                try:
                    comp = _find_company(db, name)
                    if not comp:
                        comp = Company(
                            code=_gen_code("CO-PIP"), name=name, short_name=name[:8],
                            company_type=_guess_company_type(name),
                            industry=_guess_company_category(name),
                            province=region or extract_target_province(name),
                            ext_attrs={"ownership": _guess_company_ownership(name)},
                        )
                        db.add(comp)
                        db.flush()
                        nodes["companies"] += 1
                    role = "owner" if i == 0 else "constructor"
                    _add_project_company(db, project.id, comp.id, role,
                                         c.fetched_at.strftime("%Y-%m-%d") if c.fetched_at else datetime.now().strftime("%Y-%m-%d"))
                    rels += 1
                    comp_ids.append(comp.id)
                except Exception as e:  # noqa: BLE001
                    db.rollback()
                    errors.append(f"单位[{name}]: {e}")

            # 联系人 → 人员节点 + 项目负责人(role=manager, 兜底; 公告联系人为采购方经办人)
            # 优先用正文联系方式解析出的 项目联系人/采购人联系人(姓名)
            _pc = meta.get("project_contact") or {}
            _puc = meta.get("purchaser_contact") or {}
            _ac = meta.get("agency_contact") or {}
            contact_name = (meta.get("contact_name") or _pc.get("contact") or _puc.get("contact")
                            or _extract_contact_name(c.title or "", meta))
            phone = _pc.get("phone") or meta.get("purchaserLinkPhone") or ""
            owner_cid = comp_ids[0] if comp_ids else None
            agency_cid = None
            agency_phone = _ac.get("phone") or ""
            agency_name = _ac.get("name") or meta.get("agency") or ""
            if agency_name:
                acomp = _find_company(db, agency_name)
                if acomp:
                    agency_cid = acomp.id
            if contact_name and owner_cid:
                try:
                    person, created = _ensure_project_manager(
                        db, project, contact_name, phone, owner_cid,
                        owner_company_id=owner_cid, agency_company_id=agency_cid,
                        agency_phone=agency_phone)
                    if created:
                        nodes["persons"] += 1
                    rels += 1
                except Exception as e:  # noqa: BLE001
                    db.rollback()
                    errors.append(f"人员[{contact_name}]: {e}")

            # 写 Neo4j 节点 + 关系(幂等)
            try:
                _p_ext = project.ext_attrs or {}
                sync_project(project.id, project.name, code=project.code or "",
                             status=project.status or "active",
                             category=_p_ext.get("category", "") if isinstance(_p_ext, dict) else "",
                             province=_p_ext.get("province", "") if isinstance(_p_ext, dict) else "",
                             city=_p_ext.get("city", "") if isinstance(_p_ext, dict) else "",
                             county=_p_ext.get("county", "") if isinstance(_p_ext, dict) else "")
                for cid in comp_ids:
                    comp = db.get(Company, cid)
                    if comp:
                        sync_company(cid, comp.name, code=comp.code or "", company_type=comp.company_type or "",
                                     province=comp.province or "", city=comp.city or "")
                pcs = db.execute(select(ProjectCompany).where(
                    ProjectCompany.project_id == project.id, ProjectCompany.is_deleted == False)).scalars().all()
                sync_project_companies(project.id, [{
                    "company_id": pc.company_id,
                    "name": (db.get(Company, pc.company_id).name if db.get(Company, pc.company_id) else ""),
                    "role": pc.role or ""} for pc in pcs])
                pms = db.execute(select(ProjectMember).where(
                    ProjectMember.project_id == project.id, ProjectMember.is_deleted == False)).scalars().all()
                _pm_rows = []
                for pm in pms:
                    per = db.get(Person, pm.person_id)
                    comp = db.get(Company, per.company_id) if per and per.company_id else None
                    _pm_rows.append({
                        "person_id": pm.person_id, "name": per.name if per else "",
                        "role": pm.role or "", "company_id": per.company_id if per else None,
                        "company_name": comp.name if comp else "",
                    })
                sync_project_members(project.id, _pm_rows)
                # ★ 同单位人员两两建立同事关系(本次新增/更新人员后自动生成)
                _seen_cids = set()
                for pm in pms:
                    per = db.get(Person, pm.person_id)
                    if not per or not per.company_id or per.company_id in _seen_cids:
                        continue
                    _seen_cids.add(per.company_id)
                    _cplist = db.execute(select(Person).where(
                        Person.company_id == per.company_id, Person.is_deleted == False)).scalars().all()
                    if len(_cplist) >= 2:
                        sync_company_colleagues(per.company_id, [
                            {"person_id": p.id, "name": p.name or ""} for p in _cplist
                        ])
            except Exception as e:  # noqa: BLE001
                logger.error("Neo4j 同步失败: %s", e)
                errors.append(f"Neo4j: {e}")

        # LLM 通道(可选): 补充开放关系
        if use_llm:
            try:
                from app.services.knowledge_ingest import ingest_knowledge
                content = _content_of(c)
                if len(content) >= MIN_CONTENT_LEN:
                    r = ingest_knowledge(db, content[:8000], source_text_id=c.id)
                    llm_rels += r.get("stored_relations", 0)
            except Exception as e:  # noqa: BLE001
                errors.append(f"LLM抽取: {e}")

        meta["kg_done"] = True
        meta["kg_stats"] = {"nodes": dict(nodes), "relations": rels, "llm_relations": llm_rels}
        c.meta = meta
        db.commit()
        processed += 1
        dn = {k: nodes[k] - before_nodes[k] for k in before_nodes}
        rel_delta = rels - rels_before
        if dn["projects"] or dn["companies"] or dn["persons"] or rel_delta:
            push_log("graph", f"→ 新增 项目+{dn['projects']} 单位+{dn['companies']} 人员+{dn['persons']} 关系+{rel_delta}", "info")
        else:
            push_log("graph", "→ 无新实体(名称已存在), 幂等跳过", "warn")

    push_log("graph", f"图谱构建完成: 处理 {processed} 条, 累计 项目 {nodes['projects']} / 单位 {nodes['companies']} / 人员 {nodes['persons']}, 关系 {rels}", "info")
    return {"processed": processed, "nodes": nodes, "relations": rels,
            "llm_relations": llm_rels, "errors": errors[:20]}


# ============================================================
# 阶段 4: 前端字段回填(实体 → 公司/人员/补全字段)
# ============================================================
# 四川本地行政区划词(用于深度补全优先级: 四川本地单位优先补)
_SC_REGION_WORDS = ("四川", "成都", "绵阳", "德阳", "广元", "遂宁", "内江", "乐山", "自贡", "泸州",
                    "宜宾", "南充", "达州", "雅安", "眉山", "资阳", "攀枝花", "巴中", "广安",
                    "阿坝", "甘孜", "凉山", "都江堰", "彭州", "邛崃", "崇州", "简阳")


# 单位深度补全「待补」的完整字段清单(与 field_metadata 对齐; 前缀标注存储位置)
#   base = Company 直接列(address/city/province), ext = Company.ext_attrs JSON
# 判定「待补」遵循「可获得性」分组:
#   - 必补(基础联系/工商): 地址/电话/法人/企业类型/登记机关/经营范围 — 几乎所有单位都可获得
#   - 尽力补(扩展): 邮编/邮箱/传真/注册号/成立日期/经营状态/注册资本/联系人 — 搜索/LLM 有才补
#   - 政府机关无工商概念: 不要求 法人/注册资本/经营范围/企业类型 等工商字段, 但仍补地址/电话
_DEEP_FIELDS = [
    # (字段, 存储前缀, 标签, 是否必补, 政府机关是否要求)
    ("address",        "col", "地址",       True,  True),
    ("contact",        "ext", "甲方联系方式", True,  True),   # contact 或 contact_phone 任一
    ("contact_phone",  "ext", "联系电话",    False, False),
    ("legal_rep",      "ext", "法定代表人",   True,  False),
    ("business_scope", "ext", "经营范围",    True,  False),
    ("econ_kind",      "ext", "企业类型",    False, False),
    ("belong_org",     "ext", "登记机关",    True,  False),
    ("registered_capital", "ext", "注册资本(万)", False, False),
    ("establish_date", "ext", "成立日期",    False, False),
    ("oper_status",    "ext", "经营状态",    False, False),
    ("contact_person", "ext", "联系人",      False, False),
    ("contact_email",  "ext", "联系邮箱",    False, False),
    ("fax",            "ext", "传真",       False, False),
    ("postal_code",    "ext", "邮政编码",    False, False),
    ("reg_no",         "ext", "注册号(统一社会信用代码)", False, False),
    ("credit_code",    "col", "统一社会信用代码",   False, False),
    ("industry",       "col", "行业",           False, False),
]
# 工商类字段(政府机关不要求补)
_BIZ_FIELDS = ("legal_rep", "business_scope", "econ_kind", "belong_org",
               "registered_capital", "establish_date", "oper_status", "reg_no",
               "credit_code", "industry")


def _missing_core_fields(co) -> list:
    """返回单位缺失的核心字段列表(深度补全「待补判定」与优先级依据)。

    判定标准:
      - 覆盖 field_metadata 全部公司字段(address/电话/法人/企业类型/登记机关/经营范围/注册资本/
        成立日期/经营状态/联系人/邮箱/传真/邮编/注册号)
      - 联系字段: address 缺失, 或 contact/contact_phone 均缺失 → 待补
      - 工商字段(必补): legal_rep/business_scope/belong_org
      - 政府机关无工商概念: 不要求工商字段, 但仍要求 address/contact
    返回缺失项标签列表, 空 = 已补全无需再补。
    """
    from app.services.real_project_import import _is_blank
    ext = co.ext_attrs or {}
    is_gov = (co.company_type or "") == "政府"
    missing = []

    def _get_val(f, prefix):
        if prefix == "col":
            return getattr(co, f, None)   # address/credit_code/industry 等均为 Company 列
        return ext.get(f)

    for f, prefix, label, must, gov_require in _DEEP_FIELDS:
        if is_gov and not gov_require and f in _BIZ_FIELDS:
            continue  # 政府机关不要求工商字段
        if f == "contact":
            # 联系字段: contact 或 contact_phone 任一即可
            if _is_blank(ext.get("contact")) and _is_blank(ext.get("contact_phone")):
                missing.append(label)
            continue
        if _is_blank(_get_val(f, prefix)):
            missing.append(label)
    return missing


def _needs_enrich(co) -> bool:
    return bool(_missing_core_fields(co))


def _is_sc_company(co) -> bool:
    """单位是否为四川本地(业务核心区域, 深度补全优先级最高)。"""
    if "四川" in (co.province or ""):
        return True
    n = co.name or ""
    return any(w in n for w in _SC_REGION_WORDS)


def stage_backfill(db: Session, limit: int = 50, deep_enrich: bool = False,
                   deep_enrich_limit: int = 15) -> dict:
    """回填: 从已入库线索识别 单位/人员/项目 三类实体, 自动创建或补全前端字段, 并同步 Neo4j。

    关键修复:
      1. 质量前置校验 — 每条线索先过 check_quality, 不通过则拒绝并软删, 不建任何实体
         (之前 bug: 先建单位后 filter 拒绝, 导致非川藏新单位残留)
      2. 三类实体全建 — 单位(采购人/供应商) + 人员(联系人/负责人) + 项目(从标题生成)
      3. 项目挂接 — 采购人单位=owner, 供应商单位=constructor, 联系人=项目成员
      4. 图谱同步 — 新建/更新的实体全部 sync 到 Neo4j(Project/Company/Person + 关联边)
    deep_enrich=True 时, 处理完线索后对「存量流水线单位(code LIKE CO-PIP%)且关键字段缺失」
    逐个做免费渠道深度补全(公告库→搜索引擎+LLM→政采网, 每单位 30~120s)。
    deep_enrich_limit: 每轮最多深度补全的单位数(默认 15, 防一次 70+ 个单位全跑卡死;
    剩余可再运行一次流水线继续补)。
    """
    from app.models.project_member import ProjectMember
    from app.models.company import ProjectCompany
    from app.services.real_project_import import (_find_company, _find_person, _find_project,
                                                  _gen_code, _is_blank, _add_project_company, _add_project_member)
    from app.services.neo4j_sync import (sync_company, sync_person, sync_project, sync_project_companies,
                                         sync_project_members, sync_company_colleagues)

    # 只处理 通过质量校验 且 未回填 的线索
    clues = db.execute(
        select(WebClue).where(WebClue.is_deleted == False, WebClue.status == "accepted",
                              func.json_unquote(func.json_extract(WebClue.meta, "$.backfill_done")).is_(None))
        .order_by(WebClue.id.asc()).limit(limit)
    ).scalars().all()
    push_log("backfill", f"前端回填: 待处理已接受线索 {len(clues)} 条…", "info")

    created_companies, updated_companies = 0, 0
    created_persons, created_projects = 0, 0
    rejected, errors = 0, []

    # 暂停/停止/断点续跑: 更新控制状态里的完成数
    with _pipeline_control_lock:
        _pipeline_control["done_count"] = 0

    done = 0
    stopped = False
    for c in clues:
        # 控制检查: 停止则跳出(断点=当前线索之前的最后一条); 暂停则等待
        if not _wait_if_paused():
            stopped = True
            break
        b0 = (created_companies, updated_companies, created_persons, created_projects)
        done += 1
        with _pipeline_control_lock:
            _pipeline_control["done_count"] = done
        push_log("backfill", f"[{done}/{len(clues)}] 回填「{(c.title or '')[:36]}」", "info")
        c_id = c.id
        # ① 质量前置校验(地域/主题/时效/废数据)
        ok, reason = check_quality(c)
        if not ok:
            c.status = "rejected"
            c.is_deleted = True
            meta = dict(c.meta) if isinstance(c.meta, dict) else {}
            meta["quality_reason"] = reason
            c.meta = meta
            rejected += 1
            push_log("backfill", f"→ 质量校验未通过: {reason}", "warn")
            continue

        meta = dict(c.meta) if isinstance(c.meta, dict) else {}
        purchaser = meta.get("purchaser") or ""
        # 中标供应商来源: 优先线索 meta 已解析的 suppliers; 否则从正文 procurement_result 提取
        suppliers = [s.get("supplier", "") for s in (meta.get("suppliers") or []) if s.get("supplier")]
        if not suppliers:
            suppliers = [s.get("supplier", "") for s in (meta.get("procurement_result") or []) if s.get("supplier")]
        org_names = [purchaser] + suppliers
        org_names = [n.strip() for n in org_names if n and n.strip() and len(n.strip()) >= 4]
        region = c.region or meta.get("regionName") or extract_target_province(f"{c.title or ''}")

        # 中标识别: 中标/成交公告 → 项目已完成(同时更新复用项目状态, 幂等)
        is_award = _is_bid_notice(c.title or "")

        # ② 项目(从标题生成, 复用或创建)
        project = None
        project_name = _derive_project_name(c.title or "", purchaser)
        if project_name:
            project = _find_project(db, project_name)
            if not project:
                project = Project(
                    code=_gen_code("PRJ-PIP"),
                    name=project_name,
                    status="completed" if is_award else "active",
                    description=_content_of(c)[:20000],
                )
                db.add(project)
                db.flush()
                created_projects += 1
            else:
                # 复用已存在项目: 中标公告触发 → 状态升级为已完成(幂等)
                if is_award and project.status not in ("completed", "cancelled"):
                    project.status = "completed"
            # 中标标记写入 ext_attrs(动态字段校验层允许的 SYSTEM_EXT_KEYS)
            ext = dict(project.ext_attrs or {})
            if is_award and ext.get("tender_result") != "won":
                ext["tender_result"] = "won"
                project.ext_attrs = ext
            # 统一补全: ext_attrs + 起止日期 + 进度记录(阶段/更新时间)
            _fill_project_fields(db, project, c, meta, region)

        # ③ 单位(采购人=业主, 供应商=施工) + ④ 人员(联系人) + 项目关联
        comp_ids = []
        for i, name in enumerate(dict.fromkeys(org_names)):
            try:
                role = "owner" if i == 0 else "constructor"  # 第一个=采购人(业主), 其余=供应商(施工)
                # 快路径: 只补 meta 内字段(即时); 深度补全统一放到末尾「存量单位补全」段(限速)
                changed, created = _ensure_or_enrich_company(db, name, meta, deep_enrich=False)
                if created:
                    created_companies += 1
                elif changed:
                    updated_companies += 1
                comp = _find_company(db, name)
                if comp and project:
                    _add_project_company(db, project.id, comp.id, role,
                                         c.fetched_at.strftime("%Y-%m-%d") if c.fetched_at else datetime.now().strftime("%Y-%m-%d"))
                    comp_ids.append(comp.id)
            except Exception as e:  # noqa: BLE001
                db.rollback()
                errors.append(f"单位[{name}]: {e}")

        # ⑤ 人员: 从线索 meta 提取联系人(采购人联系电话/联系人), 作为项目负责人兜底
        # 注意: 公告「项目联系人」常是代理机构经办人, 需按电话归属采购人/代理, 避免误挂。
        person_ids = []
        if project and comp_ids:
            _pc = meta.get("project_contact") or {}
            _puc = meta.get("purchaser_contact") or {}
            _ac = meta.get("agency_contact") or {}
            contact_name = (meta.get("contact_name") or _pc.get("contact") or _puc.get("contact")
                            or _extract_contact_name(c.title or "", meta))
            phone = _pc.get("phone") or meta.get("purchaserLinkPhone") or meta.get("contact_phone") or ""
            # 解析 采购人/代理机构 的 company_id(comp_ids 首项为采购人 owner)
            owner_cid = comp_ids[0] if comp_ids else None
            agency_cid = None
            agency_phone = _ac.get("phone") or ""
            agency_name = _ac.get("name") or meta.get("agency") or ""
            if agency_name:
                acomp = _find_company(db, agency_name)
                if not acomp and len(agency_name.strip()) >= 4:
                    # 代理公司不在库中 → 创建(采购代理是公告真实参与方, 不建则联系人归属失效)
                    _ensure_or_enrich_company(db, agency_name, meta)
                    acomp = _find_company(db, agency_name)
                if acomp:
                    agency_cid = acomp.id
                    if agency_cid and agency_cid not in comp_ids:
                        comp_ids.append(agency_cid)  # 参与单位列表含代理机构
            if contact_name:
                try:
                    person, created = _ensure_project_manager(
                        db, project, contact_name, phone, owner_cid,
                        owner_company_id=owner_cid,
                        agency_company_id=agency_cid,
                        agency_phone=agency_phone)
                    if created:
                        created_persons += 1
                    person_ids.append(person.id)
                except Exception as e:  # noqa: BLE001
                    db.rollback()
                    errors.append(f"人员[{contact_name}]: {e}")

        meta["backfill_done"] = True
        # 写回派生实体关联: 线索 → 项目/单位/人员 反向可溯源(前端详情/列表据此回显)
        if project:
            meta["derived_project_id"] = project.id
        if comp_ids:
            meta["derived_company_ids"] = comp_ids
        if person_ids:
            meta["derived_person_ids"] = person_ids
        c.meta = meta
        db.flush()

        # ⑥ Neo4j 图谱同步
        try:
            if project:
                _p_ext = project.ext_attrs or {}
                sync_project(project.id, project.name, code=project.code or "",
                             status=project.status or "active",
                             category=_p_ext.get("category", "") if isinstance(_p_ext, dict) else "",
                             province=_p_ext.get("province", "") if isinstance(_p_ext, dict) else "",
                             city=_p_ext.get("city", "") if isinstance(_p_ext, dict) else "",
                             county=_p_ext.get("county", "") if isinstance(_p_ext, dict) else "")
                for cid in comp_ids:
                    comp = db.get(Company, cid)
                    if comp:
                        sync_company(cid, comp.name, code=comp.code or "", company_type=comp.company_type or "",
                                     province=comp.province or "", city=comp.city or "")
                pcs = db.execute(select(ProjectCompany).where(
                    ProjectCompany.project_id == project.id, ProjectCompany.is_deleted == False)).scalars().all()
                sync_project_companies(project.id, [{
                    "company_id": pc.company_id,
                    "name": (db.get(Company, pc.company_id).name if db.get(Company, pc.company_id) else ""),
                    "role": pc.role or ""} for pc in pcs])
                for pid in person_ids:
                    per = db.get(Person, pid)
                    comp = db.get(Company, per.company_id) if per and per.company_id else None
                    if per:
                        sync_person(pid, per.name, position=per.position or "", status="active",
                                    company_id=per.company_id,
                                    company_name=comp.name if comp else "",
                                    province=comp.province or "" if comp else "",
                                    city=comp.city or "" if comp else "")
                pms = db.execute(select(ProjectMember).where(
                    ProjectMember.project_id == project.id, ProjectMember.is_deleted == False)).scalars().all()
                _pm_rows = []
                for pm in pms:
                    per = db.get(Person, pm.person_id)
                    comp = db.get(Company, per.company_id) if per and per.company_id else None
                    _pm_rows.append({
                        "person_id": pm.person_id,
                        "name": per.name if per else "",
                        "role": pm.role or "",
                        "company_id": per.company_id if per else None,
                        "company_name": comp.name if comp else "",
                    })
                sync_project_members(project.id, _pm_rows)
                # ★ 同单位人员两两建立同事关系(本次新增/更新人员后自动生成)
                _seen_cids = set()
                for pm in pms:
                    per = db.get(Person, pm.person_id)
                    if not per or not per.company_id or per.company_id in _seen_cids:
                        continue
                    _seen_cids.add(per.company_id)
                    _cplist = db.execute(select(Person).where(
                        Person.company_id == per.company_id, Person.is_deleted == False)).scalars().all()
                    if len(_cplist) >= 2:
                        sync_company_colleagues(per.company_id, [
                            {"person_id": p.id, "name": p.name or ""} for p in _cplist
                        ])
        except Exception as e:  # noqa: BLE001
            logger.error("图谱同步失败 project=%s: %s", project.id if project else "-", e)
            errors.append(f"图谱同步: {e}")
        db.commit()
        d_comp = (created_companies - b0[0]) + (updated_companies - b0[1])
        d_person = created_persons - b0[2]
        d_proj = created_projects - b0[3]
        if d_comp or d_person or d_proj:
            push_log("backfill", f"→ 新增 项目+{d_proj} 单位+{d_comp} 人员+{d_person}", "info")
        else:
            push_log("backfill", "→ 实体已存在, 幂等跳过", "warn")

    if stopped:
        push_log("backfill", f"⏹ 已手动停止: 线索处理到 {done}/{len(clues)} 条(断点已记录, 下次从断点继续)", "warn")
    else:
        push_log("backfill", f"前端回填完成: 处理 {len(clues)} 条, 新建单位 {created_companies} / 补全 {updated_companies} / 人员 {created_persons} / 项目 {created_projects} / 拒绝 {rejected}", "info")
    # 记录断点(停止/暂停时最后处理的线索 id)
    with _pipeline_control_lock:
        if stopped:
            _pipeline_control["last_entity_id"] = c_id
            _pipeline_control["done_count"] = done
        else:
            _pipeline_control["last_entity_id"] = None

    # ---------- ⑤ 存量流水线单位深度补全(免费渠道, 慢) ----------
    # 用户要求「点一下流水线, 单位详情自动补全」: 对 code LIKE 'CO-PIP%' 且字段缺失的
    # 单位逐个补全, 覆盖 field_metadata 全部公司字段(地址/电话/法人/企业类型/登记机关/
    # 经营范围/注册资本/成立日期/经营状态/联系人/邮箱/传真/邮编/注册号)。
    # 选择标准(谁先补):
    #   ① 待补判定 _missing_core_fields: 覆盖全部公司字段; 政府机关不要求工商字段
    #   ② 优先级: 四川本地 > 外地; 缺「必补字段」(地址/电话/法人/经营范围/登记机关)优先于
    #     仅缺扩展字段(邮编/邮箱/传真/注册号等); 缺字段多者优先; 再按 id
    #   ③ 防死循环: 已深度补过(ext._enrich_tried=1)的单位即使补不全也下轮跳过,
    #     避免每轮无限重试同一批; 新线索产生的单位 / 真正字段齐全前会持续补。
    # 每轮限 deep_enrich_limit 个, 剩余下轮继续。
    _MUST_LABELS = {"地址", "甲方联系方式", "联系电话", "法定代表人", "经营范围", "登记机关"}
    enriched_companies = 0
    enriched_pending = 0
    if deep_enrich:
        from app.services.company_free_enrich import enrich_company_free
        cands = db.execute(
            select(Company).where(Company.code.like("CO-PIP%"), Company.is_deleted == False)
        ).scalars().all()
        pending = [co for co in cands if _needs_enrich(co) and not (co.ext_attrs or {}).get("_enrich_tried")]
        pending.sort(key=lambda co: (
            0 if _is_sc_company(co) else 1,
            0 if any(m in _MUST_LABELS for m in _missing_core_fields(co)) else 1,
            -len(_missing_core_fields(co)), co.id))
        targets = pending[:deep_enrich_limit]
        enrich_stopped = False
        for co in targets:
            if not _wait_if_paused():
                enrich_stopped = True
                push_log("backfill", "⏹ 已手动停止: 单位深度补全中断(断点已记录, 下次继续)", "warn")
                break
            missing = _missing_core_fields(co)
            push_log("backfill", f"深度补全单位「{co.name}」…(缺 {len(missing)} 项: {','.join(missing)}; 公告库→搜索+LLM→政采网, 约 30~120s)", "info")
            try:
                r = enrich_company_free(db, co)
                if r.get("updated"):
                    enriched_companies += 1
                    push_log("backfill", f"✓ 「{co.name}」补全 {len(r['updated'])} 个字段[{r.get('source','')}]: {', '.join(r['updated'])}", "info")
                else:
                    push_log("backfill", f"「{co.name}」未补到新字段: {r.get('message', '')}", "warn")
                # 标记已深度尝试过(即便补不全, 下轮也跳过, 防无限重试; 除非字段继续缺失可手动清除标记)
                _e = dict(co.ext_attrs or {})
                _e["_enrich_tried"] = 1
                co.ext_attrs = _e
                db.commit()
            except Exception as e:  # noqa: BLE001
                db.rollback()
                logger.warning("深度补全失败 %s: %s", co.name, e)
                push_log("backfill", f"「{co.name}」补全失败: {e}", "error")
        still_missing = [co for co in cands if _needs_enrich(co)]
        enriched_pending = len(still_missing)
        push_log("backfill", f"单位深度补全: 本轮补全 {enriched_companies} 个, 仍待补 {enriched_pending} 个(四川本地/缺必补字段优先; 已尝试过的单位自动跳过防重复)", "info")
    return {"processed": len(clues), "created_companies": created_companies,
            "updated_companies": updated_companies, "created_persons": created_persons,
            "created_projects": created_projects, "rejected": rejected,
            "enriched_companies": enriched_companies, "enriched_pending": enriched_pending,
            "errors": errors[:20]}


def backfill_derived_links(db: Session, limit: int = 200) -> dict:
    """历史线索「派生关联」补写(轻量, 只查不建)。

    早期版本 stage_backfill 只写 backfill_done=true, 未把派生出的 project_id/
    company_ids/person_ids 写回线索 meta, 导致前端无法显示「这条线索已生成
    哪些实体」。本函数对 已回填(backfill_done) 但缺 derived_project_id 的线索,
    按确定性规则反向查找实体并写回 meta, 不创建任何新实体、不重复同步 Neo4j。
    幂等: 已写回的不再处理。
    """
    from app.services.real_project_import import _find_company, _find_project

    clues = db.execute(
        select(WebClue).where(
            WebClue.is_deleted == False, WebClue.status == "accepted",
            func.json_extract(WebClue.meta, "$.backfill_done").isnot(None),
            func.json_extract(WebClue.meta, "$.derived_project_id").is_(None),
        ).order_by(WebClue.id.desc()).limit(limit)
    ).scalars().all()

    updated = 0
    for c in clues:
        meta = dict(c.meta) if isinstance(c.meta, dict) else {}
        purchaser = meta.get("purchaser") or ""
        project_name = _derive_project_name(c.title or "", purchaser)
        comp_ids: list[int] = []
        person_ids: list[int] = []
        project_id = None

        # ① 项目: 确定性名称反向查找
        if project_name:
            proj = _find_project(db, project_name)
            if proj:
                project_id = proj.id
        # ② 单位: 采购人(owner) + 供应商(constructor)
        suppliers = [s.get("supplier", "") for s in (meta.get("suppliers") or []) if s.get("supplier")]
        for name in dict.fromkeys([purchaser] + suppliers):
            name = (name or "").strip()
            if len(name) < 4:
                continue
            comp = _find_company(db, name)
            if comp:
                comp_ids.append(comp.id)
        # ③ 人员: 从 project_member 反查(项目关联成员即此线索派生)
        from app.models.project_member import ProjectMember
        if project_id:
            pms = db.execute(
                select(ProjectMember.person_id).where(
                    ProjectMember.project_id == project_id, ProjectMember.is_deleted == False)
            ).scalars().all()
            person_ids = [pid for pid in pms if pid]

        if project_id or comp_ids or person_ids:
            if project_id:
                meta["derived_project_id"] = project_id
            if comp_ids:
                meta["derived_company_ids"] = list(dict.fromkeys(comp_ids))
            if person_ids:
                meta["derived_person_ids"] = list(dict.fromkeys(person_ids))
            c.meta = meta
            updated += 1

    db.commit()
    return {"processed": len(clues), "updated": updated}


def _derive_project_name(title: str, purchaser: str) -> str:
    """从公告标题生成项目名。策略: 去除采购人前缀 + 公告后缀词, 保留核心项目名。"""
    import re as _re
    if not title:
        return ""
    name = title
    if purchaser and name.startswith(purchaser):
        name = name[len(purchaser):]
    for suffix in ("中标（成交）结果公告", "中标(成交)结果公告", "中标结果公告", "成交结果公告",
                   "竞争性磋商公告", "竞争性谈判公告", "公开招标公告", "招标公告", "采购公告",
                   "中标公告", "成交公告", "结果公告", "公告", "项目中标", "项目成交",
                   "采购项目", "服务项目"):
        name = name.replace(suffix, "")
    # 清理残留的「(二次)」等批次括号(注意保留含业务语义的括号内容如「（二期）」
    name = _re.sub(r"[（(](?:二次|三次|四次|五次|再次|补遗)[）)]?", "", name)
    # 年份/编号括号规范: 「（2026年）」→「2026年」(去掉括号, 避免「（2026年」未闭合)
    name = _re.sub(r"[（(]([0-9]{2,4}年)[）)]?", r"\1", name)
    # 清理结尾冗余采购行为词(循环, 至多3轮: 「监理服务采购」→「监理服务」→「监理」)
    for _ in range(3):
        m = _re.search(r"(采购|服务)$", name)
        if m and len(name) - len(m.group(1)) >= 4:
            name = name[: len(name) - len(m.group(1))]
        else:
            break
    # 括号配对: 去掉孤立的未闭合括号(如「评估（2026年」→「评估2026年」)
    if name.count("（") != name.count("）"):
        name = _re.sub(r"[（）()]", "", name)
    name = name.strip("（）()[]【】 ")
    if not name:
        name = title[:40]
    # 补「项目」后缀统一
    if not name.endswith("项目") and len(name) < 30:
        name = f"{name}项目"
    return name[:60]


def _guess_category(title: str) -> str:
    """根据标题关键词猜测项目类别(与 project_category 枚举对齐)。"""
    t = title or ""
    if any(k in t for k in ("地灾", "地质灾害", "滑坡", "崩塌", "泥石流", "防治")):
        return "geo_hazard"
    if any(k in t for k in ("矿业", "采矿", "矿权", "探矿")):
        return "mining_rights"
    if any(k in t for k in ("生态", "环境", "修复", "治理", "绿化", "水源涵养")):
        return "eco_restoration"
    if any(k in t for k in ("规划", "国土", "政策", "评估")):
        return "policy"
    return "geo_survey"


def _extract_contact_name(title: str, meta: dict) -> str:
    """从标题/meta 提取联系人姓名(仅当标题含「联系人:XX」或 meta 有明确字段)。"""
    m = re.search(r"(?:联系人|采购人联系人|经办人)[：:]?\s*([\u4e00-\u9fa5]{2,4})", title or "")
    if m:
        return m.group(1)
    cn = meta.get("contact_person") or meta.get("contactName") or meta.get("linkman")
    if cn and isinstance(cn, str) and re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", cn):
        return cn
    return ""


def _ensure_or_enrich_company(db: Session, name: str, meta: dict,
                              deep_enrich: bool = False) -> tuple[bool, bool]:
    """复用/创建公司 + 补全字段。返回 (是否有更新, 是否新建)。

    deep_enrich=False(默认): 仅用线索 meta 内字段(采购人电话/地址)补全, 快。
    deep_enrich=True: 额外调免费渠道(搜索引擎+LLM)深度补全, 慢但质量高。
    """
    from app.services.real_project_import import _find_company, _gen_code, _is_blank

    # 跳过明显非机构名(纯数字/过短)
    if len(name) < 4 or re.fullmatch(r"[\d\s]+", name):
        return False, False

    company = _find_company(db, name)
    created = False
    if not company:
        company = Company(
            code=_gen_code("CO-PIP"),
            name=name,
            short_name=name[:8],
            company_type=_guess_company_type(name),
            industry=_guess_company_category(name),
            province=meta.get("province") or "",
            city=meta.get("city") or "",
            ext_attrs={"ownership": _guess_company_ownership(name)},
        )
        db.add(company)
        db.flush()
        created = True

    # 补全字段(线索 meta 内字段, 快)
    changed = []
    ext = dict(company.ext_attrs or {})
    for k, v in (("contact", meta.get("purchaserLinkPhone")), ("contact_phone", meta.get("purchaserLinkPhone"))):
        if v and _is_blank(ext.get(k)):
            ext[k] = v
            changed.append(k)
    addr = meta.get("purchaserAddr") or meta.get("address")
    if addr and _is_blank(company.address):
        company.address = addr
        changed.append("address")
    if changed:
        company.ext_attrs = ext

    # 深度补全(可选, 免费渠道搜索引擎+LLM, 慢)
    if deep_enrich:
        try:
            from app.services.company_free_enrich import enrich_company_free
            result = enrich_company_free(db, company)
            if result.get("updated"):
                changed.extend(result["updated"])
        except Exception:  # noqa: BLE001
            pass

    return bool(changed) or created, created


# ── 单位三套国家标准分类判定 ──────────────────────────────────────────────
# 企业类别(行业): 农业/工业/服务业/邮电/通信/社区服务/批发/零售业/交通运输/建筑及安装业/
#                 医疗卫生/城市建设/旅游/宾馆/餐饮业
_CATEGORY_KEYWORDS = (
    ("农业",       ("农业", "农牧", "林业", "渔业", "种植", "养殖", "种业")),
    ("工业",       ("工业", "制造", "化工", "矿业", "冶炼", "加工", "电力", "能源", "建材", "机械")),
    ("服务业",     ("服务", "咨询", "劳务", "中介", "广告", "信息", "科技")),
    ("邮电",       ("邮电", "邮政")),
    ("通信",       ("通信", "通讯", "电信", "网络", "移动")),
    ("社区服务",   ("社区服务", "家政")),
    ("批发",       ("批发",)),
    ("零售业",     ("零售", "商贸", "商场", "超市", "便利")),
    ("交通运输",   ("运输", "交通", "物流", "航运", "公路", "铁路", "港")),
    ("建筑及安装业", ("建筑", "建设", "工程", "施工", "安装", "市政", "岩土", "勘察", "地质工程",
                    "勘探", "地基", "建工", "装饰", "园林绿化")),
    ("医疗卫生",   ("医院", "医疗", "卫生", "医药", "疾控", "卫生院")),
    ("城市建设",   ("城市", "城建", "规划", "国土", "环卫", "公用事业", "房地产", "置业", "物业")),
    ("旅游",       ("旅游", "旅行", "景区")),
    ("宾馆",       ("宾馆", "酒店")),
    ("餐饮业",     ("餐饮", "饭店", "饮食", "美食")),
)

# 单位类型(所有制/机构性质): 政府部门/院校/科研所/国有企业/集体企业/股份合作企业/联营企业/
#                           有限责任公司/股份有限公司/私营企业/港澳台商投资企业/外商投资企业
# 注意: 「股份有限公司」全名含「有限公司」子串, 必须先判股份有限公司;
#       「街道/办事处/社区」可能同现于村社集体名, 村社集体先于政府机关判。
_TYPE_KEYWORDS = (
    ("集体企业",       ("股份经济合作", "村", "社区", "合作社", "联合社", "居委会", "集体经济")),
    ("政府部门",       ("人民政府", "自然资源和规划局", "自然资源局", "住建局", "住房和城乡建设", "发改委",
                      "财政局", "交通局", "交通运输局", "水利局", "农业农村局", "林业局", "生态环境局",
                      "教育局", "卫生健康局", "民政局", "商务局", "审计局", "税务局", "市场监督管理",
                      "政务", "管委会", "管理局", "厅", "办公室", "执法大队", "监察大队", "消防大队",
                      "派出所", "街道", "办事处", "乡政府", "镇政府")),
    ("院校",           ("大学", "学院", "学校", "中学", "小学", "幼儿园", "职业", "技工", "党校")),
    ("科研所",         ("研究院", "研究所", "设计院", "勘测院", "规划院", "测绘院", "地质调查", "地质队",
                      "地质", "勘察", "环科院", "监测站", "监测中心", "检测中心", "试验中心")),
    ("股份合作企业",   ("股份合作",)),
    ("股份有限公司",   ("股份有限公司", "股份公司")),
    ("外商投资企业",   ("外商投资", "中外合资", "外资", "中韩", "中德", "中美")),
    ("港澳台商投资企业", ("港澳台", "台港澳")),
    ("联营企业",       ("联营",)),
    ("国有企业",       ("全民所有制", "国有", "国控", "中石油", "中石化", "国家电网", "铁路局")),
    ("有限责任公司",   ("有限责任公司", "有限公司")),
    ("私营企业",       ("私营", "民营", "个人独资")),
)

# 企业性质(经营性质): 国有/合作/合资/独资/集体/私营/个体工商户/报关/其他
_OWNERSHIP_KEYWORDS = (
    ("国有",     ("国有", "全民", "中石油", "中石化", "国家电网")),
    ("集体",     ("集体", "股份经济合作", "合作社", "联合社", "社区", "村")),
    ("合资",     ("合资", "中外合")),
    ("独资",     ("独资",)),
    ("合作",     ("合作", "合伙")),
    ("私营",     ("私营", "民营", "自然人投资")),
    ("个体工商户", ("个体工商户", "个体经营", "个体户")),
    ("报关",     ("报关",)),
)


def _guess_company_category(name: str) -> str:
    """判定企业类别(行业)。名称中命中最靠前的行业词; 兜底返回 '其他'。"""
    n = name or ""
    for cat, kws in _CATEGORY_KEYWORDS:
        if any(k in n for k in kws):
            return cat
    return "其他"


def _guess_company_type(name: str) -> str:
    """判定单位类型(所有制/机构性质)。

    注意: 这里的「单位类型」是工商登记意义的所有制/机构类型(政府部门/院校/科研所/国有/集体/
    有限责任/股份有限公司等), 不是「业主/施工/监理」这类项目参与角色——项目角色由
    project_company.role 承载。
    """
    n = name or ""
    for t, kws in _TYPE_KEYWORDS:
        if any(k in n for k in kws):
            return t
    return "其他"


def _guess_company_ownership(name: str, econ_kind: str = "") -> str:
    """判定企业性质(经营性质)。优先看工商 econ_kind, 其次名称关键词; 兜底 '其他'。"""
    ek = econ_kind or ""
    for o, kws in _OWNERSHIP_KEYWORDS:
        if any(k in ek for k in kws):
            return o
    n = name or ""
    for o, kws in _OWNERSHIP_KEYWORDS:
        if any(k in n for k in kws):
            return o
    return "其他"


def _is_bid_notice(title: str) -> bool:
    """标题是否为中标/成交公告(用于推断项目所处阶段)。"""
    return any(k in (title or "") for k in ("中标", "成交", "中选", "候选人", "结果公告"))


def _fill_project_fields(db: Session, project: Project, clue, meta: dict, region: str) -> None:
    """创建/复用项目统一补全: ext_attrs + 起止日期 + 进度记录(幂等)。

    - ext_attrs: category/province/amount/owner/contact/contact_person/agency/agency_contact/source
    - 联系方式结构化字段(采购人/代理机构/项目联系人, 来自公告正文尾部「凡对本次公告内容提出询问」)
    - start_date/end_date: 公告发布/截止时间
    - 进度记录: 项目尚无任何进展时生成一条(中标→「工程施工」, 招标→「单位招标」),
      使列表页「项目阶段/更新时间」有值。
    """
    from app.models.project_progress import ProjectProgress
    ext = dict(project.ext_attrs or {})
    ext.setdefault("category", _guess_category(clue.title or ""))
    ext.setdefault("province", region)
    ext.setdefault("source", clue.url or "")
    if meta.get("budget"):
        ext.setdefault("amount", str(meta["budget"]))
    if meta.get("purchaser"):
        ext.setdefault("owner", str(meta["purchaser"]))
    phone = meta.get("purchaserLinkPhone") or meta.get("contact_phone") or meta.get("contact")
    if phone:
        ext.setdefault("contact", str(phone))
    # —— 联系方式结构化字段(公告正文尾部解析) ——
    p_contact = meta.get("purchaser_contact") or {}
    a_contact = meta.get("agency_contact") or {}
    j_contact = meta.get("project_contact") or {}
    if p_contact.get("name") and not ext.get("owner"):
        ext["owner"] = str(p_contact["name"])[:200]
    if p_contact.get("addr"):
        ext.setdefault("owner_addr", str(p_contact["addr"])[:255])
    if p_contact.get("contact") or p_contact.get("phone"):
        ext.setdefault("contact_person", str(p_contact.get("contact") or ""))
        if p_contact.get("phone"):
            ext.setdefault("contact", str(p_contact["phone"]))
            ext.setdefault("contact_phone", str(p_contact["phone"]))
    if a_contact.get("name"):
        ext.setdefault("agency", str(a_contact["name"])[:200])
    if a_contact.get("addr"):
        ext.setdefault("agency_addr", str(a_contact["addr"])[:255])
    if a_contact.get("phone"):
        ext.setdefault("agency_phone", str(a_contact["phone"]))
    if j_contact.get("contact"):
        ext.setdefault("contact_person", str(j_contact["contact"]))
    if j_contact.get("phone"):
        ext.setdefault("contact", str(j_contact["phone"]))
        ext.setdefault("contact_phone", str(j_contact["phone"]))
    project.ext_attrs = ext

    if not project.start_date and clue.published_at:
        project.start_date = clue.published_at.strftime("%Y-%m-%d")
    if not project.end_date:
        expire = meta.get("expireTime") or meta.get("expire_time")
        if expire:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", str(expire).replace("/", "-"))
            if m:
                project.end_date = m.group(1)

    # 进度记录(幂等: 已有进展不重复)
    has_prog = db.execute(
        select(func.count()).select_from(ProjectProgress).where(
            ProjectProgress.project_id == project.id, ProjectProgress.is_deleted == False)
    ).scalar() or 0
    if not has_prog:
        if _is_bid_notice(clue.title or ""):
            stage_title = "项目已中标"  # 中标公告 → 项目已完成, 而非「工程施工」
        else:
            stage_title = "单位招标"
        db.add(ProjectProgress(
            project_id=project.id,
            title=stage_title,
            content=f"由网页线索自动生成: {(clue.title or '')[:60]}",
            progress_date=clue.fetched_at or datetime.now(),
            sort_order=0,
        ))


_INVALID_PERSON_NAMES = ("交易组织", "综合股", "办公室", "财务室", "综合科", "办公室",
                         "财务股", "项目办", "招标代理", "代理机构", "采购人代表", "经办人",
                         "单位", "机构", "部门", "领导", "负责人", "联系人", "交易中心",
                         "综合服务中心", "办事员", "工作人员")


def _is_valid_person_name(name: str) -> bool:
    """联系人姓名合法性过滤: 必须是 2-4 个汉字, 且非电话/角色/科室词。

    修复: 之前把「18881380258(电话)」「交易组织(角色)」「综合股(科室)」当联系人姓名建了人员。
    """
    if not name or not isinstance(name, str):
        return False
    n = name.strip()
    if not re.fullmatch(r"[\u4e00-\u9fa5·]{2,4}", n):
        return False
    if any(k in n for k in _INVALID_PERSON_NAMES):
        return False
    # 纯数字/含电话符号 → 电话误判
    if re.search(r"[0-9()（）\-]", n):
        return False
    return True


def _norm_phone(p: str) -> str:
    """电话归一化: 去空格/区号括号/短横线, 便于比较。"""
    if not p:
        return ""
    return re.sub(r"[\s\-（）()]", "", str(p))


def _ensure_project_manager(db: Session, project: Project, contact_name: str,
                            phone: str, company_id: Optional[int], *,
                            owner_company_id: Optional[int] = None,
                            agency_company_id: Optional[int] = None,
                            agency_phone: str = ""):
    """公告联系人作为项目联系人兜底(role=manager), 幂等。返回 (person, created)。

    company_id: 联系人归属单位。默认传采购人; 但公告「项目联系人」常是**代理机构经办人**,
    其电话与代理机构电话一致时应归代理机构。调用方可传 owner_company_id/agency_company_id,
    本函数按电话归属规则决定实际归属(电话匹配优先, 否则归采购人)。

    人员查重带 company_id 消歧: 同名不同单位视为不同人, 防止跨项目「张老师」被合并。
    """
    if not contact_name or not _is_valid_person_name(contact_name):
        return None, False
    from app.models.project_member import ProjectMember
    from app.services.real_project_import import _find_person, _gen_code, _add_project_member

    # 归属单位消歧: 联系人是代理机构经办人(电话同代理) → 归代理; 否则归采购人/默认
    belong_cid = company_id
    if agency_company_id and agency_phone:
        c_phone = _norm_phone(phone)
        if c_phone and c_phone == _norm_phone(agency_phone):
            belong_cid = agency_company_id
    elif agency_company_id and not company_id:
        belong_cid = agency_company_id

    person = _find_person(db, contact_name, belong_cid)
    created = False
    if not person:
        person = Person(
            code=_gen_code("EMP-PIP"), name=contact_name,
            phone=phone or None, company_id=belong_cid, position="联系人", status="active",
        )
        db.add(person)
        db.flush()
        created = True
    has_mgr = db.execute(
        select(func.count()).select_from(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.role.in_(["manager", "项目负责人"]),
            ProjectMember.is_deleted == False)
    ).scalar() or 0
    if not has_mgr:
        _add_project_member(db, project.id, person.id, "manager",
                            responsibility=f"公告联系人(电话 {phone})" if phone else "公告联系人",
                            joined_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        project.manager_id = person.id
    return person, created


# ============================================================
# 全链路执行
# ============================================================
PIPELINE_STAGES = ["collect", "filter", "graph", "backfill"]

# 全局流水线状态(内存, 供前端查询)
_pipeline_status = {"running": False, "current_stage": "", "progress": {}, "last_run": None, "result": None}

# 流水线控制(暂停/停止/断点续跑), 内存态
_pipeline_control = {
    "pause": False,          # True=暂停中(线程空转等待)
    "stop": False,           # True=请求停止(线程跳出循环)
    "stage": "",             # 控制的阶段
    "mode": "",              # paused | stopping | running | idle
    "done_count": 0,         # 已完成处理数(线索)
    "last_entity_id": None,  # 断点: 最后已处理的线索 id
    "updated_at": None,
}
_pipeline_control_lock = threading.Lock()


def reset_pipeline_control(stage: str) -> None:
    """启动阶段时重置控制状态。"""
    with _pipeline_control_lock:
        _pipeline_control.update({
            "pause": False, "stop": False, "stage": stage, "mode": "running",
            "done_count": 0, "last_entity_id": None,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })


def set_pipeline_control(action: str) -> dict:
    """设置控制指令: pause | resume | stop。返回当前控制状态。

    pause:  请求暂停(当前单位处理完后线程进入等待)
    resume: 继续执行(清除暂停标志)
    stop:   请求停止(当前单位处理完后线程退出, 记录断点)
    """
    with _pipeline_control_lock:
        if action == "pause":
            _pipeline_control["pause"] = True
            _pipeline_control["mode"] = "paused"
        elif action == "resume":
            _pipeline_control["pause"] = False
            _pipeline_control["mode"] = "running"
        elif action == "stop":
            _pipeline_control["stop"] = True
            _pipeline_control["mode"] = "stopping"
        _pipeline_control["updated_at"] = datetime.now().isoformat(timespec="seconds")
        return dict(_pipeline_control)


def get_pipeline_control() -> dict:
    with _pipeline_control_lock:
        return dict(_pipeline_control)


def _wait_if_paused() -> bool:
    """暂停时阻塞等待; 返回 False 表示收到停止指令应退出。

    以 0.5s 间隔轮询, 暂停期间线程不忙转(不处理新单位), 停止时立即返回 False。
    """
    while True:
        with _pipeline_control_lock:
            paused = _pipeline_control["pause"]
            stopped = _pipeline_control["stop"]
        if stopped:
            return False
        if not paused:
            return True
        time.sleep(0.5)


def get_pipeline_status() -> dict:
    st = dict(_pipeline_status)
    st["control"] = get_pipeline_control()
    return st


def run_pipeline(db: Session, stages: Optional[list] = None, rules: Optional[dict] = None,
                 collect_opts: Optional[dict] = None) -> dict:
    """全链路执行: collect → filter → graph → backfill。

    stages: 指定要执行的阶段子集(默认全部)。
    rules: 覆盖管道级筛选规则(FilterRules 可配置字段)。
    collect_opts: 采集选项(include_intent/include_clues/include_bids)。
    """
    _pipeline_status["running"] = True
    _pipeline_status["current_stage"] = "init"
    _pipeline_status["progress"] = {}
    clear_pipeline_logs()
    push_log("general", "流水线启动(采集 → 筛选入库 → 图谱构建 → 前端回填)…", "info")
    try:
        stages = stages or PIPELINE_STAGES
        rules_obj = FilterRules(**(rules or {}))
        result = {"stages": {}, "summary": {}}
        collected = 0
        for stage in stages:
            _pipeline_status["current_stage"] = stage
            push_log("general", f"▶ 进入阶段「{_STAGE_ZH.get(stage, stage)}」", "info")
            try:
                if stage == "collect":
                    r = stage_collect(db, **(collect_opts or {}))
                    collected = sum(v for k, v in r.items() if isinstance(v, int) and not k.endswith("_error"))
                    result["stages"]["collect"] = r
                    _pipeline_status["progress"]["collect"] = r
                elif stage == "filter":
                    r = stage_filter(db, rules_obj)
                    result["stages"]["filter"] = r
                    _pipeline_status["progress"]["filter"] = r
                elif stage == "graph":
                    r = stage_graph(db)
                    result["stages"]["graph"] = r
                    _pipeline_status["progress"]["graph"] = r
                elif stage == "backfill":
                    # 深度补全: 对存量流水线单位补电话/地址/法人等(免费渠道, 每轮限速)
                    r = stage_backfill(db, deep_enrich=True)
                    result["stages"]["backfill"] = r
                    _pipeline_status["progress"]["backfill"] = r
            except Exception as e:  # noqa: BLE001
                # 单阶段失败不阻断全链路, 记录后继续下一阶段
                logger.exception("阶段[%s]执行失败", stage)
                result["stages"][stage] = {"error": str(e)}
                _pipeline_status["progress"][stage] = {"error": str(e)}
                push_log(stage, f"阶段执行失败: {e}", "error")

        result["summary"] = {
            "stages_run": stages,
            "collected_total": collected,
            "rules": rules_obj.to_dict(),
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
        _pipeline_status["result"] = result
        _pipeline_status["last_run"] = datetime.now().isoformat(timespec="seconds")
        push_log("general", f"流水线执行完成: {len(stages)} 个阶段, 采集总数 {collected}", "success")
        return result
    finally:
        _pipeline_status["running"] = False
        _pipeline_status["current_stage"] = ""


def run_stage(db: Session, stage: str, rules: Optional[dict] = None,
              deep_enrich: bool = False, deep_enrich_limit: Optional[int] = None,
              use_llm: bool = False) -> dict:
    """单阶段执行。"""
    rules_obj = FilterRules(**(rules or {}))
    if stage == "collect":
        return stage_collect(db)
    if stage == "filter":
        return stage_filter(db, rules_obj)
    if stage == "graph":
        return stage_graph(db, use_llm=use_llm)
    if stage == "backfill":
        # None → 用默认 15(前端可能未传, 避免 pending[:None] 全量跑)
        return stage_backfill(db, deep_enrich=deep_enrich,
                              deep_enrich_limit=deep_enrich_limit or 15)
    raise ValueError(f"unknown stage: {stage}")


def run_stage_background(db: Session, stage: str, rules: Optional[dict] = None,
                         deep_enrich: bool = False, deep_enrich_limit: Optional[int] = None,
                         use_llm: bool = False) -> dict:
    """单阶段后台执行: 写全局状态, 供前端轮询 /pipeline/status + /pipeline/logs。

    修复: 旧实现为同步 HTTP 长连接(回填深补全可达 30 分钟), 前端 axios 全局 30s 超时
    连接断开 → 日志/状态全部丢失(观感「没有输出/不知道在不在运行」)。
    """
    _pipeline_status["running"] = True
    _pipeline_status["current_stage"] = stage
    _pipeline_status["progress"] = {}
    clear_pipeline_logs()
    reset_pipeline_control(stage)
    push_log("general", f"▶ 进入阶段「{_STAGE_ZH.get(stage, stage)}」(单阶段后台执行)", "info")
    try:
        r = run_stage(db, stage, rules=rules, deep_enrich=deep_enrich,
                      deep_enrich_limit=deep_enrich_limit, use_llm=use_llm)
        _pipeline_status["progress"][stage] = r
        _pipeline_status["result"] = {
            "stages": {stage: r},
            "summary": {"stages_run": [stage],
                        "finished_at": datetime.now().isoformat(timespec="seconds")},
        }
        _pipeline_status["last_run"] = datetime.now().isoformat(timespec="seconds")
        push_log("general", f"阶段「{_STAGE_ZH.get(stage, stage)}」执行完成", "success")
        return r
    except Exception as e:  # noqa: BLE001
        logger.exception("阶段[%s]执行失败", stage)
        _pipeline_status["progress"][stage] = {"error": str(e)}
        push_log(stage, f"阶段执行失败: {e}", "error")
        return {"error": str(e)}
    finally:
        _pipeline_status["running"] = False
        _pipeline_status["current_stage"] = ""
        with _pipeline_control_lock:
            _pipeline_control["stop"] = False
            _pipeline_control["pause"] = False
            _pipeline_control["mode"] = "idle"
            _pipeline_control["updated_at"] = datetime.now().isoformat(timespec="seconds")
