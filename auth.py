from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_login import LoginManager
from sqlalchemy.orm import Session
from models import User, UserSession, SessionLocal
from config import Config
from datetime import datetime, timedelta
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
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Неверные учётные данные")

        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(status_code=403, detail="Аккаунт заблокирован. Попробуйте позже.")

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                user.failed_login_attempts = 0
            db.commit()
            raise HTTPException(status_code=401, detail="Неверные учётные данные")

        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

        access_token = manager.create_access_token(data={"sub": user.username})
        resp = RedirectResponse(url="/", status_code=303)
        manager.set_cookie(resp, access_token)

        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_active == True
        ).update({"is_active": False, "logout_time": datetime.utcnow()})

        ip = request.client.host
        ua = request.headers.get('User-Agent', '')
        new_session = UserSession(user_id=user.id, ip_address=ip, user_agent=ua)
        db.add(new_session)
        db.commit()

        return resp
    finally:
        db.close()

@router.get("/logout")
async def logout(request: Request):
    user = await manager.optional(request)
    if user:
        db = SessionLocal()
        try:
            db_user = db.query(User).filter(User.id == user.id).first()
            if db_user:
                db.query(UserSession).filter(
                    UserSession.user_id == db_user.id,
                    UserSession.is_active == True
                ).update({"is_active": False, "logout_time": datetime.utcnow()})
                db.commit()
        finally:
            db.close()

    resp = RedirectResponse(url="/login", status_code=303)
    manager.set_cookie(resp, "")
    return resp