"""JSON API: /api/users — управление пользователями через Keycloak Admin API."""
from fastapi import APIRouter, Depends, Body, Path, HTTPException, status

from src.api.deps import require_admin
from src.services import keycloak_admin as kc
from src.services.keycloak_admin import KeycloakAdminError

router = APIRouter(prefix="/users", tags=["api:users"])


def _kc_error(e: KeycloakAdminError):
    """Преобразует KeycloakAdminError в HTTPException."""
    raise HTTPException(e.status_code, e.detail)


@router.get(
    "",
    summary="Список пользователей",
    description="Возвращает список пользователей из Keycloak с их ролями.",
)
async def list_users(user: dict = Depends(require_admin)):
    try:
        users = await kc.list_users(max_results=500)
        # Подтягиваем роли каждому (N+1, но пока так)
        for u in users:
            roles = await kc.get_user_realm_roles(u["id"])
            u["realm_roles"] = [r["name"] for r in roles]
        return {"ok": True, "data": users}
    except KeycloakAdminError as e:
        _kc_error(e)


@router.get(
    "/roles",
    summary="Список realm-ролей",
    description="Возвращает список доступных realm-ролей (для выпадающего списка).",
)
async def list_roles(user: dict = Depends(require_admin)):
    try:
        roles = await kc.list_realm_roles()
        return {"ok": True, "data": [r["name"] for r in roles]}
    except KeycloakAdminError as e:
        _kc_error(e)


@router.get("/{user_id}", summary="Получить пользователя")
async def get_user(
    user_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    try:
        u = await kc.get_user(user_id)
        roles = await kc.get_user_realm_roles(user_id)
        u["realm_roles"] = [r["name"] for r in roles]
        return {"ok": True, "data": u}
    except KeycloakAdminError as e:
        _kc_error(e)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать пользователя",
    description=(
        "Создаёт пользователя в Keycloak. "
        "Обязательные поля: `username`, `password`, `email`, `role`."
    ),
)
async def create_user(
    payload: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """
    Тело запроса:

        {
          "username": "test_user",
          "email": "test@local",
          "password": "test123",
          "firstName": "Test",
          "lastName": "User",
          "role": "app-user"
        }

    """
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip()
    role = (payload.get("role") or "").strip()

    if not username:
        raise HTTPException(400, "Поле «username» обязательно")
    if not password:
        raise HTTPException(400, "Поле «password» обязательно")
    if not email:
        raise HTTPException(400, "Поле «email» обязательно")

    kc_payload = {
        "username": username,
        "email": email,
        "firstName": (payload.get("firstName") or "").strip(),
        "lastName": (payload.get("lastName") or "").strip(),
        "enabled": True,
        "emailVerified": False,
        "credentials": [
            {"type": "password", "value": password, "temporary": False}
        ],
    }

    try:
        await kc.kc_request("POST", "/users", json=kc_payload)
    except KeycloakAdminError as e:
        _kc_error(e)

    # Назначаем роль
    if role:
        try:
            found = await kc.find_user_by_username(username)
            if found:
                await kc.replace_realm_role(found["id"], role)
        except KeycloakAdminError as e:
            # Пользователь создан, но роль не назначилась — предупреждаем
            return {
                "ok": True,
                "data": {"username": username},
                "warning": f"Пользователь создан, но роль не назначена: {e.detail}",
            }

    return {"ok": True, "data": {"username": username}}


@router.put(
    "/{user_id}",
    summary="Обновить пользователя",
    description=(
        "Обновляет `email`, `firstName`, `lastName`, `role`, `password`. "
        "Все поля опциональны."
    ),
)
async def update_user(
    user_id: str = Path(...),
    payload: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """
    Тело запроса (все поля опциональны):

        {
          "email": "new@local",
          "firstName": "New",
          "lastName": "Name",
          "password": "newpass",
          "role": "app-admin"
        }

    """
    try:
        # 1. Базовые поля
        patch = {}
        if payload.get("email"):
            patch["email"] = payload["email"].strip()
        if payload.get("firstName") is not None:
            patch["firstName"] = (payload["firstName"] or "").strip()
        if payload.get("lastName") is not None:
            patch["lastName"] = (payload["lastName"] or "").strip()

        if patch:
            await kc.update_user(user_id, patch)

        # 2. Пароль
        if payload.get("password"):
            await kc.set_user_password(user_id, payload["password"])

        # 3. Роль
        if payload.get("role"):
            await kc.replace_realm_role(user_id, payload["role"])

        # Возвращаем обновлённого
        updated = await kc.get_user(user_id)
        roles = await kc.get_user_realm_roles(user_id)
        updated["realm_roles"] = [r["name"] for r in roles]
        return {"ok": True, "data": updated}
    except KeycloakAdminError as e:
        _kc_error(e)


@router.delete("/{user_id}", summary="Удалить пользователя")
async def delete_user(
    user_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    """Удаляет пользователя из Keycloak. Себя удалить нельзя."""
    # Защита от удаления себя
    if user.get("username") == user_id:
        raise HTTPException(400, "Нельзя удалить самого себя")

    try:
        # Проверяем, что это не тот же пользователь
        target = await kc.get_user(user_id)
        if target.get("username") == user.get("username"):
            raise HTTPException(400, "Нельзя удалить самого себя")

        await kc.delete_user(user_id)
        return {"ok": True, "message": f"Пользователь «{target.get('username')}» удалён"}
    except KeycloakAdminError as e:
        _kc_error(e)
