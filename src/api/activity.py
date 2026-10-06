"""JSON API: /api/activity — активность пользователей (UserSession)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import require_admin
from src.models import SessionLocal, User, UserSession

router = APIRouter(prefix="/activity", tags=["api:activity"])


def _session_to_dict(s: UserSession, username: Optional[str] = None) -> dict:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "username": username,
        "ip_address": s.ip_address,
        "user_agent": s.user_agent,
        "login_time": s.login_time.isoformat() if s.login_time else None,
        "logout_time": s.logout_time.isoformat() if s.logout_time else None,
        "last_activity": s.last_activity.isoformat() if s.last_activity else None,
        "is_active": s.is_active,
    }


@router.get(
    "",
    summary="Активность пользователей",
    description="Возвращает список сессий пользователей с пагинацией.",
)
async def list_activity(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    active_only: bool = Query(False),
    user: dict = Depends(require_admin),
):
    db = SessionLocal()
    try:
        q = db.query(UserSession, User.username).outerjoin(
            User, UserSession.user_id == User.id
        )
        if active_only:
            q = q.filter(UserSession.is_active == True)

        total = q.count()
        rows = (
            q.order_by(UserSession.login_time.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        data = [_session_to_dict(s, username) for s, username in rows]

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
    "/user/{user_id}",
    summary="Сессии одного пользователя",
    description="Возвращает список сессий конкретного пользователя (по local user_id).",
)
async def user_activity(
    user_id: int,
    limit: int = Query(50, ge=1, le=500),
    user: dict = Depends(require_admin),
):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        username = u.username if u else None

        rows = (
            db.query(UserSession)
            .filter(UserSession.user_id == user_id)
            .order_by(UserSession.login_time.desc())
            .limit(limit)
            .all()
        )
        return {
            "ok": True,
            "data": [_session_to_dict(s, username) for s in rows],
        }
    finally:
        db.close()
