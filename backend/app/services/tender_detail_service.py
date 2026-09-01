"""标讯详情聚合、字段展示和企业实体链接服务。"""
from __future__ import annotations

import logging
from typing import Any, Iterable
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.bid_notice import BidNotice
from app.models.company import Company
from app.models.user_entity_action import UserEntityAction
from app.schemas.tender_detail import (
    DetailHeader, DetailKvItem, DetailTag, DisplayField, EntityLink,
    SupplierItem, TenderActionState, TenderDetailData, TimelineEvent,
)
from app.services.notice_text_enricher import enrich as enrich_notice_text


class GatedFieldFilter:
    """字段级展示规则。

    当前产品暂不启用会员制：所有真实值不做会员脱敏；敏感规则仍集中在此处，
    未来启用权限策略时只需替换 can_view_sensitive 的实现。
    """
    sensitive_fields = {"evaluation_method", "bid_deadline", "opening_time", "qualification", "consortium", "timeline_summary"}

    def __init__(self, user: dict | None = None):
        self.user = user or {}

    @property
    def can_view_sensitive(self) -> bool:
        return True

    def field(self, value: Any, field_name: str | None = None, date_mask: bool = False) -> DisplayField:
        if value in (None, ""):
            return DisplayField(value=None, displayText="未披露", isGated=False)
        gated = bool(field_name in self.sensitive_fields and not self.can_view_sensitive)
        display = "****-**-**" if gated and date_mask else "******" if gated else str(value)
        return DisplayField(value=None if gated else value, displayText=display, isGated=gated)


class EntityLinkResolver:
    """从公告实体名称解析本地企业 ID，未匹配时保留原名称。"""
    def __init__(self, db: Session): self.db = db

    def resolve(self, name: str | None) -> EntityLink | None:
        clean = str(name or "").strip()
        if not clean: return None
        company = self.db.execute(select(Company).where(Company.name == clean, Company.is_deleted == False)).scalar_one_or_none()
        if not company:
            company = self.db.execute(select(Company).where(Company.name.contains(clean), Company.is_deleted == False).limit(1)).scalar_one_or_none()
        return EntityLink(entityId=company.id if company else None, name=company.name if company else clean, href=f"/site/data-center/companies/{company.id}" if company else None, matched=bool(company))


class TenderDetailExtractor:
    """公告结构化抽取。

    第一层: 读取已入库 meta(采集器写入的结构化字段);
    第二层: 对正文做清洗 + 补抽, 用于回填 meta 缺失的字段
            (代理机构/项目编号/开标时间/建设规模/中标金额等)。
    补抽只做"填空", 绝不覆盖已有结构化数据。
    """
    def extract(self, notice: BidNotice) -> dict[str, Any]:
        meta = notice.meta if isinstance(notice.meta, dict) else {}
        try:
            meta["enriched"] = enrich_notice_text(meta)
        except Exception as exc:  # 补抽失败不能拖垮详情页
            logging.warning("标讯正文补抽失败 id=%s: %s", getattr(notice, "id", None), exc)
            meta["enriched"] = {}
        return meta


class TenderDetailService:
    def __init__(self, db: Session, user: dict | None = None):
        self.db, self.user = db, user or {}
        self.filter = GatedFieldFilter(self.user)
        self.resolver = EntityLinkResolver(db)
        self.extractor = TenderDetailExtractor()

    def _action_state(self, bid_id: int) -> TenderActionState:
        row = self.db.execute(select(UserEntityAction).where(UserEntityAction.user_id == int(self.user.get("user_id", 0)), UserEntityAction.entity_type == "bid", UserEntityAction.entity_id == bid_id, UserEntityAction.is_deleted == False)).scalar_one_or_none()
        return TenderActionState(canDownload=True, isMonitored=bool(row and row.monitored), isCollected=bool(row and row.collected))

    def _bid_tag_labels(self, bid_id: int) -> list[DetailTag]:
        """读取运营手工/规则标签(若有关联)。"""
        from app.models.bid_tag import BidTagDef, BidNoticeTag
        rows = self.db.execute(
            select(BidTagDef)
            .join(BidNoticeTag, BidNoticeTag.tag_id == BidTagDef.id)
            .where(BidNoticeTag.bid_id == bid_id, BidTagDef.is_deleted == False)
            .order_by(BidTagDef.sort_order, BidTagDef.id.desc())
        ).scalars().all()
        return [DetailTag(label=t.label, kind=t.kind) for t in rows]

    def _auto_apply_tags(self, notice: BidNotice) -> None:
        """无手工标签时, 按规则关键字自动打标(幂等, 轻量)。"""
        from app.models.bid_tag import BidTagDef, BidNoticeTag
        rules = self.db.execute(
            select(BidTagDef).where(
                BidTagDef.is_deleted == False,
                BidTagDef.enabled == True,
                BidTagDef.rule_keyword.isnot(None),
                BidTagDef.rule_keyword != "",
            )
        ).scalars().all()
        if not rules:
            return
        title = notice.title or ""
        added = False
        for rule in rules:
            for kw in [k.strip() for k in (rule.rule_keyword or "").split(",") if k.strip()]:
                if kw and kw in title:
                    exists = self.db.execute(
                        select(BidNoticeTag.id).where(
                            BidNoticeTag.bid_id == notice.id, BidNoticeTag.tag_id == rule.id
                        )
                    ).scalar_one_or_none()
                    if not exists:
                        self.db.add(BidNoticeTag(bid_id=notice.id, tag_id=rule.id))
                        added = True
                    break
        if added:
            self.db.commit()

    # ------------------------------------------------------------------ 补抽回填

    def _build_suppliers(self, meta: dict[str, Any], enriched: dict[str, Any]) -> list[SupplierItem]:
        """构建中标供应商列表。

        meta.suppliers 为主数据源; 正文补抽到的金额/得分仅在能与之校验通过时填充,
        供应商名称/地址一律取自结构化数据, 不从连排正文里猜测。
        """
        award = enriched.get("award") or {}
        raw = meta.get("suppliers") or []
        if not isinstance(raw, list):
            return []
        items: list[SupplierItem] = []
        for index, row in enumerate(raw):
            if not isinstance(row, dict):
                continue
            amount = self._to_float(row.get("amount"))
            score = self._to_float(row.get("score"))
            # 单供应商场景用正文校验值补齐缺失的金额/得分
            if len(raw) == 1:
                amount = amount if amount is not None else award.get("amount")
                score = score if score is not None else award.get("score")
            items.append(SupplierItem(
                name=str(row.get("supplier") or row.get("name") or ""),
                address=row.get("address") or None,
                amount=amount,
                amount_text=self._format_amount(amount) if amount is not None else None,
                score=score,
                companyId=row.get("supplier_company_id") or row.get("company_id"),
                rank=index + 1,
            ))
        return [i for i in items if i.name]

    @staticmethod
    def _to_float(value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_amount(value: float) -> str:
        return f"{value / 10000:.2f}万" if abs(value) >= 10000 else f"{value:,.0f}"

    def _build_tags(self, notice: BidNotice, meta: dict[str, Any]) -> list[DetailTag]:
        """标签构造。注意: 自动打标必须在读取标签**之前**执行,
        否则首次访问打上的标签要等第二次请求才可见。"""
        self._auto_apply_tags(notice)
        tags: list[DetailTag] = []
        if notice.notice_type:
            tags.append(DetailTag(label=notice.notice_type, kind="status"))
        if meta.get("industry"):
            tags.append(DetailTag(label=str(meta["industry"]), kind="category"))
        manual_tags = self._bid_tag_labels(notice.id)
        seen = {t.label for t in tags}
        for tag in manual_tags:
            if tag.label not in seen:
                tags.append(tag)
                seen.add(tag.label)
        return tags

    @staticmethod
    def _fill(original: Any, fallback: Any) -> Any:
        """仅在原值为空时用补抽值填空, 已有结构化数据优先。"""
        if original not in (None, ""):
            return original
        return fallback

    def build(self, notice: BidNotice) -> TenderDetailData:
        meta = self.extractor.extract(notice)
        enriched = meta.get("enriched") or {}
        scalars = enriched.get("scalars") or {}
        deadlines = enriched.get("deadlines") or {}

        project = meta.get("project_info") or meta.get("projectInfo") or {}
        finance = meta.get("finance") or {}
        evaluation = meta.get("evaluation") or {}
        requirements = meta.get("requirements") or meta.get("qualification") or {}

        # ---- 补抽回填: 结构化字段缺失时用正文抽取结果填空 ----
        agency_name = self._fill(meta.get("agency") or notice.agency, scalars.get("agency_name"))
        build_scale = self._fill(project.get("scale"), scalars.get("build_scale"))
        budget = self._fill(finance.get("budget"), scalars.get("total_amount_text"))
        service_term = self._fill(project.get("duration"), scalars.get("service_term"))
        project_code = self._fill(project.get("code"), scalars.get("project_code"))

        purchaser = self.resolver.resolve(notice.purchaser)
        agency = self.resolver.resolve(agency_name)

        def item(label: str, value: Any, field_name: str | None = None, entity: EntityLink | None = None, wide: bool = False, date_mask: bool = False):
            return DetailKvItem(label=label, field=self.filter.field(value, field_name, date_mask=date_mask), entity=entity, wide=wide)

        kv = [
            item("公告编号", notice.id),
            item("公告类型", notice.notice_type),
            item("项目地区", notice.region),
            item("招标单位", notice.purchaser, entity=purchaser),
            item("招标代理", agency_name, entity=agency),
            item("项目类型", project.get("type")),
            item("建设规模", build_scale, wide=True),
            item("招标范围", project.get("scope"), wide=True),
            item("建设工期", service_term),
            item("招标方式", project.get("method")),
            item("预算金额", budget),
            item("资金来源", finance.get("source")),
            item("评标办法", evaluation.get("method"), "evaluation_method"),
            item("资格审查", requirements.get("qualification"), "qualification", wide=True),
            item("联合体要求", requirements.get("consortium"), "consortium", wide=True),
        ]

        deadline_values = {
            "registration_deadline": self._fill(project.get("registration_deadline"), None),
            "document_deadline": self._fill(project.get("document_deadline"), None),
            "bid_deadline": self._fill(project.get("bid_deadline"), deadlines.get("bid_deadline")),
            "opening_time": self._fill(project.get("opening_time"), deadlines.get("opening_time")),
        }
        time_fields = [("报名截止", "registration_deadline", False), ("文件获取截止", "document_deadline", True), ("投标截止", "bid_deadline", True), ("开标时间", "opening_time", True)]
        time_matrix = [item(label, deadline_values[key], key, date_mask=True) for label, key, _ in time_fields]

        raw_timeline = meta.get("timeline") or meta.get("dates") or []
        if isinstance(raw_timeline, dict):
            raw_timeline = [{"label": k, "value": v} for k, v in raw_timeline.items()]
        timeline = [TimelineEvent(name=str(row.get("label") or row.get("name") or "时间节点"), date=str(row.get("value") or row.get("date") or "") or None, summary=self.filter.field(row.get("summary"), "timeline_summary")) for row in raw_timeline if isinstance(row, dict)]

        # 通告类时间点(首次公告/更正日期)也进时间线, 让"招标进度"不再恒为空
        for label, value in (("首次公告", scalars.get("first_published_at")), ("更正日期", scalars.get("corrected_at"))):
            if value:
                timeline.append(TimelineEvent(name=label, date=value))

        tags = self._build_tags(notice, meta)
        suppliers = self._build_suppliers(meta, enriched)

        # 附件: 接口采集到的链接优先; 只有正文线索(无链接)时也要披露出来
        attachments = list(meta.get("attachments") or [])
        if not attachments and enriched.get("attachment_hints"):
            attachments = enriched["attachment_hints"]

        return TenderDetailData(
            header=DetailHeader(
                id=notice.id,
                title=notice.title,
                projectCode=project_code,
                publishedAt=notice.published_at.strftime("%Y-%m-%d") if notice.published_at else "",
                sourceName=notice.source_name,
                sourceUrl=notice.url,
            ),
            tags=tags,
            kv=kv,
            timeMatrix=time_matrix,
            timeline=sorted(timeline, key=lambda x: x.date or "", reverse=True),
            suppliers=suppliers,
            # 下发清洗后的正文, 去掉源站 CSS/JS/备案噪声
            body=enriched.get("body_clean") or meta.get("body") or meta.get("content") or "",
            attachments=attachments,
            relatedCompanies=[x for x in (purchaser, agency) if x],
            entities={"purchaser": purchaser, "agency": agency},
            actions=self._action_state(notice.id),
            enriched={
                "announced_at": scalars.get("announced_at"),
                "admin_region": scalars.get("admin_region"),
                "project_name": scalars.get("project_name"),
                "agency_address": scalars.get("agency_address"),
                "agency_phone": scalars.get("agency_phone"),
                "purchaser_address": scalars.get("purchaser_address"),
                "purchaser_phone": scalars.get("purchaser_phone"),
                "project_person": scalars.get("project_person"),
                "project_phone": scalars.get("project_phone"),
                "expert_list": scalars.get("expert_list") or [],
                "total_amount_text": scalars.get("total_amount_text"),
                "prev_bid_deadline": deadlines.get("prev_bid_deadline"),
                "correction_scope": scalars.get("correction_scope") or [],
                "corrections": enriched.get("corrections") or [],
                "attachment_hints": enriched.get("attachment_hints") or [],
            },
        )
