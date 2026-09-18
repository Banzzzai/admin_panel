"""JWKSManager для admin-panel.

Валидирует Bearer-токены через JWKS Keycloak.
Может получать сервисный токен через TOKEN_BROKER_URL (broker).
"""
import logging
from typing import Any, Dict

import httpx
from cachetools import TTLCache, cachedmethod
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from src.settings.config import Config

logger = logging.getLogger(__name__)


class JWKSManager:
    def __init__(self, jwk_url: str, jwks_ttl: int = 3600):
        self.jwk_url = jwk_url
        self.jwks_cache = TTLCache(maxsize=1, ttl=jwks_ttl)
        self.security = HTTPBearer(auto_error=False)

    @cachedmethod(lambda self: self.jwks_cache)
    def _get_jwks(self) -> dict:
        """Синхронно получает и кэширует публичные ключи Keycloak."""
        response = httpx.get(self.jwk_url, timeout=10.0)
        response.raise_for_status()
        return response.json()

    def _get_public_key(self, token: str) -> dict:
        headers = jwt.get_unverified_header(token)
        kid = headers.get("kid")
        if not kid:
            raise HTTPException(status_code=401, detail="В токене отсутствует 'kid'")

        jwks = self._get_jwks()
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        raise HTTPException(status_code=401, detail="Ключ для проверки подписи не найден")

    def validate_token(self, token: str) -> Dict[str, Any]:
        """Валидирует токен и возвращает payload. Бросает HTTPException(401)."""
        try:
            public_key = self._get_public_key(token)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                options={"verify_aud": False},  # audience может быть разной
            )
            return payload
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Невалидный или просроченный токен: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def require_roles(self, roles: set):
        """FastAPI-зависимость: требует Bearer с одной из указанных ролей."""
        def role_checker(
            credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
        ) -> Dict[str, Any]:
            token = credentials.credentials
            payload = self.validate_token(token)

            realm_roles = payload.get("realm_access", {}).get("roles", [])
            resource = payload.get("resource_access", {})
            client_roles = []
            for client in resource.values():
                client_roles += client.get("roles", [])

            all_roles = set(realm_roles) | set(client_roles)
            if not all_roles.intersection(roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Доступ запрещён: недостаточно прав",
                )
            return payload
        return role_checker

    async def get_internal_token(self) -> str:
        """Получает сервисный токен через TOKEN_BROKER_URL (для gis_api)."""
        headers = {}
        if Config.BROKER_SECRET:
            headers["X-Service-Secret"] = Config.BROKER_SECRET

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(Config.TOKEN_BROKER_URL, headers=headers)
            response.raise_for_status()
            return response.json()["access_token"]


# Единый экземпляр для всего приложения
jwks = JWKSManager(Config.JWK_URL)
