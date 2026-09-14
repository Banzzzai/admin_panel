from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from models import SessionLocal, AuditLog
from auth import manager
from config import Config

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def admin_required(user=Depends(manager)):
    if user.role != Config.KEYCLOAK_ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user

@router.get("/")
def audit_log(request: Request, page: int = 1, user=Depends(admin_required)):
    db = SessionLocal()
    try:
        per_page = 20
        total = db.query(AuditLog).count()
        logs = db.query(AuditLog)\
            .options(joinedload(AuditLog.actor))\
            .order_by(AuditLog.created_at.desc())\
            .offset((page - 1) * per_page)\
            .limit(per_page).all()
        total_pages = max(1, (total + per_page - 1) // per_page) if total > 0 else 1
    finally:
        db.close()

    return templates.TemplateResponse("audit_log.html", {
        "request": request,
        "logs": logs,
        "page": page,
        "total_pages": total_pages,
        "current_user": user
    })