from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_login import LoginManager
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config as StarletteConfig
from sqlalchemy.orm import Session
from models import User, UserSession, SessionLocal
from config import Config
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

manager = LoginManager(Config.SECRET_KEY, token_url="/login", use_cookie=True)

# --- Keycloak OAuth ---
oauth = OAuth()
oauth.register(
    name="keycloak",
    client_id=Config.KEYCLOAK_CLIENT_ID,
    client_secret=Config.KEYCLOAK_CLIENT_SECRET,
    # Вручную, чтобы не тянуть metadata с localhost:
    authorize_url=f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}/protocol/openid-connect/auth",
    access_token_url=f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}/protocol/openid-connect/token",
    userinfo_endpoint=f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}/protocol/openid-connect/userinfo",
    jwks_uri=f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}/protocol/openid-connect/certs",
    client_kwargs={"scope": "openid email profile"},
)


@manager.user_loader()
def load_user(username: str):
    """fastapi_login вызывает это, чтобы получить user из токена."""
    db = SessionLocal()
    try:
        return db.query(User).filter(User.username == username).first()
    finally:
        db.close()


def _extract_roles(userinfo: dict) -> list[str]:
    """Забираем роли из userinfo Keycloak."""
    roles = []
    if "realm_access" in userinfo:
        roles += userinfo["realm_access"].get("roles", [])
    # Если у клиента есть client roles:
    resource = userinfo.get("resource_access", {})
    if Config.KEYCLOAK_CLIENT_ID in resource:
        roles += resource[Config.KEYCLOAK_CLIENT_ID].get("roles", [])
    return roles


def _upsert_user(db: Session, userinfo: dict) -> User:
    """Создаём или обновляем локального пользователя по данным Keycloak."""
    username = userinfo.get("preferred_username") or userinfo["sub"]
    user = db.query(User).filter(User.username == username).first()

    roles = _extract_roles(userinfo)
    local_role = Config.KEYCLOAK_ADMIN_ROLE if Config.KEYCLOAK_ADMIN_ROLE in roles \
                 else Config.KEYCLOAK_DEFAULT_ROLE

    if not user:
        user = User(
            username=username,
            email=userinfo.get("email"),
            password_hash="",           # пароли теперь в Keycloak
            role=local_role,
            failed_login_attempts=0,
        )
        db.add(user)
    else:
        user.email = userinfo.get("email") or user.email
        user.role = local_role
        user.failed_login_attempts = 0
        user.locked_until = None

    db.commit()
    db.refresh(user)
    return user


@router.get("/login")
async def login(request: Request):
    """Редирект в Keycloak."""
    return await oauth.keycloak.authorize_redirect(
        request, Config.KEYCLOAK_REDIRECT_URI
    )


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Keycloak вернул код — меняем на токен, ставим локальную cookie."""
    token = await oauth.keycloak.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        # если id_token пришёл, попробуем распарсить
        userinfo = token.get("id_token") and token["id_token"].get("userinfo")
    if not userinfo:
        raise HTTPException(401, "Не удалось получить данные пользователя")

    db = SessionLocal()
    try:
        user = _upsert_user(db, userinfo)

        # Закрываем предыдущие активные сессии
        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_active == True,
        ).update({"is_active": False, "logout_time": datetime.utcnow()})

        ip = request.client.host if request.client else ""
        ua = request.headers.get("User-Agent", "")
        db.add(UserSession(user_id=user.id, ip_address=ip, user_agent=ua))
        db.commit()

        access_token = manager.create_access_token(data={"sub": user.username})
        resp = RedirectResponse(url="/", status_code=303)
        manager.set_cookie(resp, access_token)
        return resp
    finally:
        db.close()


@router.get("/logout")
async def logout(request: Request):
    """Локальный logout + глобальный logout в Keycloak."""
    user = await manager.optional(request)
    if user:
        db = SessionLocal()
        try:
            db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.is_active == True,
            ).update({"is_active": False, "logout_time": datetime.utcnow()})
            db.commit()
        finally:
            db.close()

    # Глобальный logout Keycloak (завершит SSO-сессию)
    kc_logout = (
        f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}"
        f"/protocol/openid-connect/logout"
        f"?redirect_uri={Config.KEYCLOAK_REDIRECT_URI.replace('/auth/callback', '/login')}"
    )
    resp = RedirectResponse(url=kc_logout, status_code=303)
    manager.set_cookie(resp, "")
    return resp