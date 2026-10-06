"""Клиент для Keycloak Admin API.

Используется для управления пользователями (создание, роли, пароли).
Токен кэшируется в памяти процесса (client_credentials).
"""
import logging
import time
from typing import Any, Optional

import httpx

from src.settings.config import Config

logger = logging.getLogger(__name__)

TIMEOUT = 30.0

# Кэш сервисного токена (5 минут)
_token_cache: dict = {"token": None, "expires_at": 0.0}


class KeycloakAdminError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _admin_base() -> str:
    return f"{Config.KEYCLOAK_URL}/admin/realms/{Config.KEYCLOAK_REALM}"


def _token_url() -> str:
    return f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}/protocol/openid-connect/token"


async def _get_admin_token() -> str:
    """client_credentials → access token сервисного аккаунта (с кэшем)."""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["token"]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            _token_url(),
            data={
                "grant_type": "client_credentials",
                "client_id": Config.KEYCLOAK_ADMIN_CLIENT_ID,
                "client_secret": Config.KEYCLOAK_ADMIN_CLIENT_SECRET,
            },
        )
        if r.status_code != 200:
            raise KeycloakAdminError(
                r.status_code,
                f"Не удалось получить admin token: {r.text[:300]}",
            )
        data = r.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 300)
        return data["access_token"]


async def kc_request(
    method: str,
    path: str,
    *,
    json: Optional[Any] = None,
    params: Optional[dict] = None,
) -> Any:
    """Запрос к Keycloak Admin API. Возвращает JSON или None (204)."""
    token = await _get_admin_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{_admin_base()}{path}"

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        r = await client.request(
            method, url, headers=headers, json=json, params=params
        )

    if r.status_code == 204:
        return None

    if 200 <= r.status_code < 300:
        try:
            return r.json()
        except Exception:
            return None

    try:
        body = r.json()
        detail = body.get("errorMessage") or body.get("error") or r.text[:300]
    except Exception:
        detail = r.text[:300]

    raise KeycloakAdminError(r.status_code, str(detail))


# ============ Типовые операции с пользователями ============

async def list_users(max_results: int = 500) -> list:
    return await kc_request("GET", f"/users?max={max_results}") or []


async def get_user(user_id: str) -> dict:
    return await kc_request("GET", f"/users/{user_id}") or {}


async def find_user_by_username(username: str) -> Optional[dict]:
    users = await kc_request(
        "GET", f"/users?username={username}&exact=true"
    ) or []
    return users[0] if users else None


async def get_user_realm_roles(user_id: str) -> list:
    return await kc_request("GET", f"/users/{user_id}/role-mappings/realm") or []


async def list_realm_roles() -> list:
    return await kc_request("GET", "/roles") or []


async def update_user(user_id: str, patch: dict) -> None:
    await kc_request("PUT", f"/users/{user_id}", json=patch)


async def set_user_password(user_id: str, password: str) -> None:
    await kc_request(
        "PUT",
        f"/users/{user_id}/reset-password",
        json={"type": "password", "value": password, "temporary": False},
    )


async def delete_user(user_id: str) -> None:
    await kc_request("DELETE", f"/users/{user_id}")


async def assign_realm_role(user_id: str, role_name: str) -> None:
    role = await kc_request("GET", f"/roles/{role_name}")
    if not role:
        raise KeycloakAdminError(404, f"Роль '{role_name}' не найдена")
    await kc_request(
        "POST",
        f"/users/{user_id}/role-mappings/realm",
        json=[{"id": role["id"], "name": role["name"]}],
    )


async def remove_realm_role(user_id: str, role_name: str) -> None:
    role = await kc_request("GET", f"/roles/{role_name}")
    if not role:
        return
    await kc_request(
        "DELETE",
        f"/users/{user_id}/role-mappings/realm",
        json=[{"id": role["id"], "name": role["name"]}],
    )


async def replace_realm_role(user_id: str, new_role: str) -> None:
    """Убирает все realm-роли и ставит одну новую."""
    current = await get_user_realm_roles(user_id)
    if current:
        await kc_request(
            "DELETE", f"/users/{user_id}/role-mappings/realm", json=current
        )
    await assign_realm_role(user_id, new_role)
