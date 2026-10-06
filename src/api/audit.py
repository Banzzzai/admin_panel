"""JSON API: /api/audit — журнал аудита (SSR-таблица audit_logs)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import joinedload

from src.api.deps import require_admin
from src.models import SessionLocal, AuditLog

router = APIRouter(prefix="/audit", tags=["api:audit"])


@router.get(
    "",
    summary="Журнал аудита",
    description="Возвращает список действий пользователей (audit_logs) с пагинацией.",
)
async def list_audit(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None),
    user: dict = Depends(require_admin),
):
    db = SessionLocal()
    try:
        q = db.query(AuditLog)
        if action:
            q = q.filter(AuditLog.action == action)

        total = q.count()
        items = (
            q.options(joinedload(AuditLog.actor))
            .order_by(AuditLog.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        data = []
        for log in items:
            data.append({
                "id": log.id,
                "user_id": log.user_id,
                "username": log.actor.username if log.actor else None,
                "action": log.action,
                "target_user_id": log.target_user_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })

        return {
            "ok": True,
            "data": data,
            "meta": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": max(1, (total + limit - 1) // limit),
            },
        }
    finally:
        db.close()


@router.get(
    "/actions",
    summary="Уникальные действия",
    description="Возвращает список уникальных `action` из audit_logs (для фильтра).",
)
async def list_actions(user: dict = Depends(require_admin)):
    db = SessionLocal()
    try:
        rows = (
            db.query(AuditLog.action)
            .distinct()
            .order_by(AuditLog.action)
            .all()
        )
        return {"ok": True, "data": [r[0] for r in rows if r[0]]}
    finally:
        db.close()
