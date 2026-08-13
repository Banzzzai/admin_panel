from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_login import LoginManager
from sqlalchemy.orm import Session
from models import User, UserSession, SessionLocal
from config import Config
from datetime import datetime
import bcrypt

router = APIRouter()
templates = Jinja2Templates(directory="templates")
manager = LoginManager(Config.SECRET_KEY, token_url="/login", use_cookie=True)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

@manager.user_loader()
def load_user(username: str):
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()

@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(request: Request,
          username: str = Form(...),
          password: str = Form(...)):
    user = load_user(username)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверные учётные данные")

    access_token = manager.create_access_token(data={"sub": user.username})
    resp = RedirectResponse(url="/", status_code=303)
    manager.set_cookie(resp, access_token)

    db = SessionLocal()
    try:
        # Закрываем все предыдущие активные сессии этого пользователя
        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_active == True
        ).update({"is_active": False, "logout_time": datetime.utcnow()})

        # Создаём новую сессию
        ip = request.client.host
        ua = request.headers.get('User-Agent', '')
        new_session = UserSession(user_id=user.id, ip_address=ip, user_agent=ua)
        db.add(new_session)
        db.commit()
    finally:
        db.close()

    return resp

@router.get("/logout")
def logout(request: Request):
    user = manager.optional(request)
    if user:
        db = SessionLocal()
        try:
            db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.is_active == True
            ).update({"is_active": False, "logout_time": datetime.utcnow()})
            db.commit()
        finally:
            db.close()

    resp = RedirectResponse(url="/login", status_code=303)
    manager.set_cookie(resp, "")  # очистка куки
    return resp