from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from models import User, UserSession, SessionLocal, AuditLog  # <-- добавлен AuditLog
from auth import manager, hash_password
import bcrypt

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def admin_required(user=Depends(manager)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user

# === Вспомогательная функция для добавления записи в аудит ===
def add_audit_log(db: Session, actor_id: int, action: str, target_user_id: int = None, details: str = None, ip_address: str = None):
    log = AuditLog(
        user_id=actor_id,
        action=action,
        target_user_id=target_user_id,
        details=details,
        ip_address=ip_address
    )
    db.add(log)
# =============================================================

@router.get("/")
def user_list(request: Request, user=Depends(manager)):
    if user.role != "admin":
        return RedirectResponse(url="/", status_code=303)
    db = SessionLocal()
    try:
        users = db.query(User).all()
        active_session = db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_active == True
        ).order_by(UserSession.login_time.desc()).first()
        current_session_id = active_session.id if active_session else None
    finally:
        db.close()
    return templates.TemplateResponse("users.html", {
        "request": request,
        "current_user": user,
        "users": users,
        "current_session_id": current_session_id
    })

@router.post("/create")
def create_user(request: Request,
                username: str = Form(...),
                password: str = Form(...),
                role: str = Form("user"),
                user=Depends(admin_required)):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            raise HTTPException(status_code=400, detail="Пользователь уже существует")
        new_user = User(
            username=username,
            password_hash=hash_password(password),
            role=role
        )
        db.add(new_user)
        db.flush()  # чтобы получить new_user.id

        # === Логирование создания пользователя ===
        add_audit_log(
            db,
            actor_id=user.id,
            action="create_user",
            target_user_id=new_user.id,
            details=f"Создан пользователь {new_user.username} с ролью {new_user.role}",
            ip_address=request.client.host
        )
        # ========================================

        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/users", status_code=303)

@router.get("/delete/{user_id}")
def delete_user(user_id: int, request: Request, user=Depends(admin_required)):
    db = SessionLocal()
    try:
        target = db.query(User).get(user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if target.id == user.id:
            raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")
        if target.role == "admin":
            raise HTTPException(status_code=400, detail="Нельзя удалить администратора")

        # === Логирование удаления ===
        add_audit_log(
            db,
            actor_id=user.id,
            action="delete_user",
            target_user_id=target.id,
            details=f"Удалён пользователь {target.username}",
            ip_address=request.client.host
        )
        # =============================

        db.delete(target)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/users", status_code=303)

@router.post("/edit/{user_id}")
def edit_user(user_id: int,
              request: Request,
              username: str = Form(None),
              role: str = Form(None),
              password: str = Form(None),
              user=Depends(admin_required)):
    db = SessionLocal()
    try:
        target = db.query(User).get(user_id)
        if not target:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        # Смена логина
        if username and username != target.username:
            if db.query(User).filter(User.username == username, User.id != user_id).first():
                raise HTTPException(status_code=400, detail="Логин занят")
            target.username = username

        # Смена роли (только другим)
        if role and target.id != user.id:
            target.role = role

        # Смена пароля
        if password:
            target.password_hash = hash_password(password)

        # === Логирование редактирования ===
        add_audit_log(
            db,
            actor_id=user.id,
            action="edit_user",
            target_user_id=target.id,
            details=f"Изменены данные пользователя {target.username}",
            ip_address=request.client.host
        )
        # =================================

        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/users", status_code=303)