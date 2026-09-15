from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from ..models import User, UserSession, SessionLocal
from .router_auth import manager
from ..settings.config import Config
from datetime import datetime, timedelta

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def admin_required(user=Depends(manager)):
    if user.role != Config.KEYCLOAK_ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user

@router.get("/heartbeat")
def heartbeat(session_id: int = None, user=Depends(manager)):
    if session_id:
        db = SessionLocal()
        try:
            session = db.query(UserSession).get(session_id)
            if session and session.user_id == user.id:
                session.last_activity = datetime.utcnow()
                db.commit()
        finally:
            db.close()
    return Response(status_code=204)

@router.get("/")
def user_activity(request: Request, user=Depends(admin_required)):
    db = SessionLocal()
    try:
        users = db.query(User).all()
        # Загружаем все сессии для каждого пользователя, сортируем по убыванию login_time
        for u in users:
            sessions = db.query(UserSession).filter(UserSession.user_id == u.id)\
                          .order_by(UserSession.login_time.desc()).all()
            u.all_sessions = sessions
            # Пользователь онлайн, если есть хотя бы одна активная сессия
            u.is_online = any(s.is_active for s in sessions)

        active_session = db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_active == True
        ).order_by(UserSession.login_time.desc()).first()
        current_session_id = active_session.id if active_session else None
    finally:
        db.close()

    return templates.TemplateResponse("activity.html", {
        "request": request,
        "users": users,
        "current_session_id": current_session_id,
        "current_user": user
    })

@router.get("/user/{user_id}")
def user_activity_detail(request: Request, user_id: int, page: int = 1, user=Depends(admin_required)):
    db = SessionLocal()
    try:
        target = db.query(User).get(user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        per_page = 10
        # Сначала получаем общее количество записей
        total = db.query(UserSession).filter(UserSession.user_id == user_id).count()

        total_pages = max(1, (total + per_page - 1) // per_page) if total > 0 else 1

        if page < 1:
            page = 1
        elif page > total_pages:
            page = total_pages

        sessions = db.query(UserSession).filter(UserSession.user_id == user_id)\
            .order_by(UserSession.login_time.desc())\
            .offset((page - 1) * per_page).limit(per_page).all()
    finally:
        db.close()

    return templates.TemplateResponse("user_activity_detail.html", {
        "request": request,
        "user": target,
        "sessions": sessions,
        "page": page,
        "total_pages": total_pages,
        "current_user": user
    })