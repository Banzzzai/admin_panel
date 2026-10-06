"""Зависимости для JSON API /api/*.

React SPA использует Bearer-токен. Cookie (SSR) здесь не проверяется.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.jwks import jwks
from src.settings.config import Config

security = HTTPBearer(auto_error=False)


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Требует Bearer-токен с ролью `admin-panel-admin`.

    Возвращает: {"username": ..., "token": ..., "payload": ...}
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется Bearer-токен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = jwks.validate_token(token)  # бросит 401, если невалидный

    # Собираем роли из realm + всех клиентов
    roles = list(payload.get("realm_access", {}).get("roles", []))
    resource = payload.get("resource_access", {})
    for client in resource.values():
        roles += client.get("roles", [])

    if Config.KEYCLOAK_ADMIN_ROLE not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора",
        )

    return {
        "username": payload.get("preferred_username"),
        "token": token,
        "payload": payload,
    }
