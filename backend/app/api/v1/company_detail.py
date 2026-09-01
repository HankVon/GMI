"""单位 360° 详情扩展 API — 行业数据标准库查询(对标建设通分项查询)。

对应指导文档: docs/gmi-renovation-guide.md A1 / C1
数据域: 资质(qualification) / 荣誉(honor) / 诚信(credit_record) /
        人员证书(person_cert) / 工商(company_ic) / 司法风险(company_legal_risk) /
        开标记录(bid_open_record)
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.company import Company
from app.models.person import Person
from app.models.industry_data import (
    Qualification, Honor, CreditRecord, PersonCert,
    CompanyIc, CompanyLegalRisk, BidOpenRecord,
)
from app.models.bid_notice import BidNotice

router = APIRouter(prefix="/companies", tags=["单位360°"])


def _get_company(db: Session, company_id: int) -> Company:
    c = db.execute(
        select(Company).where(Company.id == company_id, Company.is_deleted == False)
    ).scalar_one_or_none()
    if not c:
        raise HTTPException(status_code=404, detail="unit not found")
    return c


def _paginate(db: Session, stmt, page: int, page_size: int) -> dict:
    """通用分页: 返回 {total, items(基础行), page, page_size}。"""
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(func.coalesce(stmt.column_descriptions[0]["entity"].id, 0).desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": rows}


def _row(item) -> dict:
    """ORM 行转可序列化 dict(公共字段)。"""
    d = {
        "id": item.id,
        "created_at": str(item.created_at) if item.created_at else None,
        "updated_at": str(item.updated_at) if item.updated_at else None,
    }
    for col in item.__table__.columns:
        key = col.name
        if key in d:
            continue
        val = getattr(item, key)
        if hasattr(val, "isoformat"):
            val = val.isoformat()
        d[key] = val
    return d


@router.get("/{company_id}/qualifications")
async def company_qualifications(
    company_id: int,
    category: Optional[str] = Query(None, description="资质大类过滤"),
    level: Optional[str] = Query(None, description="等级过滤"),
    status: Optional[str] = Query(None, description="active/expiring/expired"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单位资质台账(按大类/等级/状态筛选), 支持失效预警。"""
    _get_company(db, company_id)
    stmt = select(Qualification).where(
        Qualification.company_id == company_id, Qualification.is_deleted == False
    )
    if category:
        stmt = stmt.where(Qualification.category == category)
    if level:
        stmt = stmt.where(Qualification.level == level)
    if status:
        stmt = stmt.where(Qualification.status == status)
    res = _paginate(db, stmt, page, page_size)
    # 统计: 各状态数量 + 分类树
    rows = db.execute(
        select(Qualification.status, func.count())
        .where(Qualification.company_id == company_id, Qualification.is_deleted == False)
        .group_by(Qualification.status)
    ).all()
    return {
        "success": True,
        "data": {
            "total": res["total"],
            "page": res["page"],
            "page_size": res["page_size"],
            "items": [_row(r) for r in res["items"]],
            "status_count": {r[0]: r[1] for r in rows},
            "categories": [r[0] for r in db.execute(
                select(Qualification.category).where(
                    Qualification.company_id == company_id, Qualification.is_deleted == False
                ).distinct()
            ).all()],
        },
    }


@router.get("/{company_id}/honors")
async def company_honors(
    company_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单位荣誉台账。"""
    _get_company(db, company_id)
    stmt = select(Honor).where(
        Honor.company_id == company_id, Honor.is_deleted == False
    )
    res = _paginate(db, stmt, page, page_size)
    return {
        "success": True,
        "data": {
            "total": res["total"],
            "page": res["page"],
            "page_size": res["page_size"],
            "items": [_row(r) for r in res["items"]],
        },
    }


@router.get("/{company_id}/credit-records")
async def company_credit_records(
    company_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单位诚信/不良行为记录。"""
    _get_company(db, company_id)
    stmt = select(CreditRecord).where(
        CreditRecord.company_id == company_id, CreditRecord.is_deleted == False
    )
    res = _paginate(db, stmt, page, page_size)
    return {
        "success": True,
        "data": {
            "total": res["total"],
            "page": res["page"],
            "page_size": res["page_size"],
            "items": [_row(r) for r in res["items"]],
        },
    }


@router.get("/{company_id}/certificates")
async def company_certificates(
    company_id: int,
    status: Optional[str] = Query(None, description="active/expiring/expired"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """本单位人员的证书列表(join person, 按证书状态筛选)。"""
    _get_company(db, company_id)
    stmt = (
        select(PersonCert)
        .join(Person, Person.id == PersonCert.person_id)
        .where(
            Person.company_id == company_id,
            Person.is_deleted == False,
            PersonCert.is_deleted == False,
        )
    )
    if status:
        stmt = stmt.where(PersonCert.status == status)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(PersonCert.valid_to.is_(None), PersonCert.valid_to.asc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for pc in rows:
        p = db.get(Person, pc.person_id)
        item = _row(pc)
        item["person_name"] = p.name if p else ""
        item["person_position"] = p.position if p else ""
        items.append(item)
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        },
    }


@router.get("/{company_id}/ic")
async def company_ic(
    company_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单位工商信息(法人/资本/股东/分支/投资/变更)。"""
    _get_company(db, company_id)
    ic = db.execute(
        select(CompanyIc).where(
            CompanyIc.company_id == company_id, CompanyIc.is_deleted == False
        )
    ).scalar_one_or_none()
    if not ic:
        return {"success": True, "data": None}
    return {"success": True, "data": _row(ic)}


@router.get("/{company_id}/legal-risks")
async def company_legal_risks(
    company_id: int,
    risk_type: Optional[str] = Query(None, description="l lawsuit/judgment/executed/penalty/abnormal/..."),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单位司法与经营风险。"""
    _get_company(db, company_id)
    stmt = select(CompanyLegalRisk).where(
        CompanyLegalRisk.company_id == company_id, CompanyLegalRisk.is_deleted == False
    )
    if risk_type:
        stmt = stmt.where(CompanyLegalRisk.risk_type == risk_type)
    res = _paginate(db, stmt, page, page_size)
    # 类型计数
    rows = db.execute(
        select(CompanyLegalRisk.risk_type, func.count())
        .where(CompanyLegalRisk.company_id == company_id, CompanyLegalRisk.is_deleted == False)
        .group_by(CompanyLegalRisk.risk_type)
    ).all()
    return {
        "success": True,
        "data": {
            "total": res["total"],
            "page": res["page"],
            "page_size": res["page_size"],
            "items": [_row(r) for r in res["items"]],
            "type_count": {r[0]: r[1] for r in rows},
        },
    }


@router.get("/{company_id}/bid-open-records")
async def company_bid_open_records(
    company_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """单位参与的开标记录(含公告标题, 供同场竞标分析)。"""
    _get_company(db, company_id)
    stmt = (
        select(BidOpenRecord)
        .join(BidNotice, BidNotice.id == BidOpenRecord.bid_notice_id)
        .where(
            BidOpenRecord.company_id == company_id,
            BidOpenRecord.is_deleted == False,
            BidNotice.is_deleted == False,
        )
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(BidOpenRecord.opened_at.is_(None), BidOpenRecord.opened_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    items = []
    for r in rows:
        bn = db.get(BidNotice, r.bid_notice_id)
        item = _row(r)
        item["notice_title"] = bn.title if bn else ""
        item["notice_url"] = bn.url if bn else ""
        items.append(item)
    return {
        "success": True,
        "data": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        },
    }
