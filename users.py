from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import httpx

from models import User, UserSession, SessionLocal, AuditLog
from auth import manager
from config import Config

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# ------------------ Keycloak Admin API helpers ------------------

def _kc_admin_base() -> str:
    return f"{Config.KEYCLOAK_URL}/admin/realms/{Config.KEYCLOAK_REALM}"


def _kc_token_url() -> str:
    return f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}/protocol/openid-connect/token"


async def _get_admin_token() -> str:
    """client_credentials → access token сервисного аккаунта."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            _kc_token_url(),
            data={
                "grant_type": "client_credentials",
                "client_id": Config.KEYCLOAK_ADMIN_CLIENT_ID,
                "client_secret": Config.KEYCLOAK_ADMIN_CLIENT_SECRET,
            },
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def kc_request(method: str, path: str, **kwargs):
    """Запрос к Admin API с автоматическим токеном."""
    token = await _get_admin_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.request(
            method, f"{_kc_admin_base()}{path}", headers=headers, **kwargs
        )
    return r


# ------------------ Права ------------------

def admin_required(user=Depends(manager)):
    """Пускать только с ролью admin-panel-admin."""
    if user.role != Config.KEYCLOAK_ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user


def add_audit_log(db: Session, actor_id, action, target_user_id=None, details=None, ip_address=None):
    db.add(AuditLog(
        user_id=actor_id, action=action,
        target_user_id=target_user_id, details=details, ip_address=ip_address,
    ))

def _sync_local_user(db: Session, kc_user: dict, realm_roles: list) -> User:
    """Создаёт/обновляет локальную запись User по данным из Keycloak."""
    username = kc_user.get("username")
    role = Config.KEYCLOAK_ADMIN_ROLE if Config.KEYCLOAK_ADMIN_ROLE in realm_roles \
           else Config.KEYCLOAK_DEFAULT_ROLE

    local = db.query(User).filter(User.username == username).first()
    if not local:
        local = User(username=username, email=kc_user.get("email"),
                     password_hash="", role=role)
        db.add(local)
    else:
        local.email = kc_user.get("email") or local.email
        local.role = role
    db.commit()
    db.refresh(local)
    return local

@router.get("/")
async def user_list(request: Request, user=Depends(manager)):
    if user.role != Config.KEYCLOAK_ADMIN_ROLE:
        return RedirectResponse(url="/", status_code=303)

    # Забираем список из Keycloak
    r = await kc_request("GET", "/users?max=500")
    if r.status_code != 200:
        raise HTTPException(500, f"Keycloak error: {r.status_code} {r.text}")
    kc_users = r.json()

    # Роли для формы (realm roles)
    r_roles = await kc_request("GET", "/roles")
    all_roles = [x["name"] for x in r_roles.json()] if r_roles.status_code == 200 else []

    # Синхронизируем локальные записи и подтягиваем роли каждого
    db = SessionLocal()
    try:
        users_out = []
        for u in kc_users:
            r_ur = await kc_request("GET", f"/users/{u['id']}/role-mappings/realm")
            realm_roles = [x["name"] for x in r_ur.json()] if r_ur.status_code == 200 else []
            u["realm_roles"] = realm_roles
            _sync_local_user(db, u, realm_roles)
            users_out.append(u)

        active_session = db.query(UserSession).filter(
            UserSession.user_id == user.id, UserSession.is_active == True
        ).order_by(UserSession.login_time.desc()).first()
        current_session_id = active_session.id if active_session else None
    finally:
        db.close()

    return templates.TemplateResponse("users.html", {
        "request": request,
        "current_user": user,
        "users": users_out,             # теперь это список dict из Keycloak
        "all_roles": all_roles,
        "admin_role": Config.KEYCLOAK_ADMIN_ROLE,
        "current_session_id": current_session_id,
    })

@router.get("/delete/{user_id}")
async def delete_user(user_id: str, request: Request, user=Depends(admin_required)):
    r_me = await kc_request("GET", f"/users?username={user.username}&exact=true")
    me = (r_me.json() or [None])[0]
    if me and user_id == me["id"]:
        raise HTTPException(400, "Нельзя удалить самого себя")
    r = await kc_request("DELETE", f"/users/{user_id}")
    if r.status_code not in (204, 200):
        raise HTTPException(400, f"Keycloak: {r.text}")

    db = SessionLocal()
    try:
        add_audit_log(db, actor_id=user.id, action="delete_user",
                      details=f"Удалён Keycloak user id={user_id}",
                      ip_address=request.client.host if request.client else None)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/users", status_code=303)


@router.post("/edit/{user_id}")
async def edit_user(user_id: str,
                    request: Request,
                    email: str = Form(None),
                    firstName: str = Form(None),
                    lastName: str = Form(None),
                    role: str = Form(None),
                    password: str = Form(None),
                    user=Depends(admin_required)):
    # обновление базовых полей
    patch = {}
    if email: patch["email"] = email
    if firstName: patch["firstName"] = firstName
    if lastName: patch["lastName"] = lastName
    if patch:
        r = await kc_request("PUT", f"/users/{user_id}", json=patch)
        if r.status_code not in (204, 200):
            raise HTTPException(400, f"Keycloak: {r.text}")

    # смена пароля
    if password:
        r = await kc_request(
            "PUT", f"/users/{user_id}/reset-password",
            json={"type": "password", "value": password, "temporary": False},
        )
        if r.status_code not in (204, 200):
            raise HTTPException(400, f"Keycloak: {r.text}")

    # роль: убираем все текущие realm-роли, ставим новую
    if role:
        # текущие
        r_current = await kc_request("GET", f"/users/{user_id}/role-mappings/realm")
        if r_current.status_code == 200 and r_current.json():
            await kc_request("DELETE", f"/users/{user_id}/role-mappings/realm",
                             json=r_current.json())
        # новая
        r_role = await kc_request("GET", f"/roles/{role}")
        if r_role.status_code == 200:
            role_repr = r_role.json()
            await kc_request("POST", f"/users/{user_id}/role-mappings/realm",
                             json=[{"id": role_repr["id"], "name": role_repr["name"]}])

    db = SessionLocal()
    try:
        add_audit_log(db, actor_id=user.id, action="edit_user",
                      details=f"Изменён Keycloak user id={user_id}",
                      ip_address=request.client.host if request.client else None)
        db.commit()
    finally:
        db.close()
    return RedirectResponse(url="/users", status_code=303)