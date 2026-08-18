"""审计服务：操作日志+字段变更历史"""
from __future__ import annotations

import datetime
import json

from sqlalchemy.orm import Session

from app.models.audit import AuditLog, FieldChangeHistory


def log_action(
    db: Session,
    user_id: int | None,
    username: str | None,
    action: str,
    resource_type: str,
    resource_id: int | None = None,
    resource_name: str | None = None,
    detail: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    """写入操作审计日志"""
    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_name=resource_name,
        detail=detail,
        ip_address=ip_address,
        user_agent=user_agent,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(log)
    return log


def track_field_changes(
    db: Session,
    entity_type: str,
    entity_id: int,
    changed_by: int | None,
    changes: list[dict],
    time: datetime.datetime | None = None,
) -> list[FieldChangeHistory]:
    """
    批量记录字段值变更

    changes 格式:
      [
        {"field_key": "name", "field_label": "项目名称", "old_value": "旧名", "new_value": "新名"},
        ...
      ]
    """
    if time is None:
        time = datetime.datetime.now(datetime.timezone.utc)

    records = []
    for c in changes:
        if c.get("old_value") == c.get("new_value"):
            continue  # 值未变化,跳过
        record = FieldChangeHistory(
            entity_type=entity_type,
            entity_id=entity_id,
            field_key=c["field_key"],
            field_label=c.get("field_label", c["field_key"]),
            old_value=str(c["old_value"]) if c["old_value"] is not None else None,
            new_value=str(c["new_value"]) if c["new_value"] is not None else None,
            changed_by=changed_by,
            changed_at=time,
        )
        db.add(record)
        records.append(record)

    return records


def compute_ext_attr_changes(
    old_ext_attrs: dict | None,
    new_ext_attrs: dict | None,
    meta_map: dict[str, str],  # field_key → display_name
) -> list[dict]:
    """
    计算 ext_attrs 的差异列表

    返回: changes 列表,格式同 track_field_changes
    """
    old = old_ext_attrs or {}
    new = new_ext_attrs or {}

    all_keys = set(old.keys()) | set(new.keys())
    changes = []

    for key in all_keys:
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changes.append({
                "field_key": key,
                "field_label": meta_map.get(key, key),
                "old_value": json.dumps(old_val, ensure_ascii=False) if old_val is not None else None,
                "new_value": json.dumps(new_val, ensure_ascii=False) if new_val is not None else None,
            })

    return changes
