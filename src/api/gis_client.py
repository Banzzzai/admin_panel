"""Хелпер для запросов в gis_api от имени пользователя (Bearer)."""
import logging
from typing import Any

import httpx
from fastapi import HTTPException

from src.settings.config import Config

logger = logging.getLogger(__name__)

GIS_API_URL = Config.GIS_API_URL


def _humanize_error(r: httpx.Response, action: str) -> str:
    """Превращает ответ gis_api в читаемое сообщение."""
    try:
        data = r.json()
    except Exception:
        return f"Не удалось {action}: {r.status_code} {r.text[:200]}"

    # 422 от gis_api
    if isinstance(data, dict) and isinstance(data.get("detail"), list):
        parts = []
        for err in data["detail"][:5]:
            loc = ".".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", "")
            parts.append(f"{loc}: {msg}")
        return f"Неверные данные — {'; '.join(parts)}"

    if isinstance(data, dict):
        detail = data.get("detail") or data.get("message") or ""
        error_type = data.get("error_type", "")
        if error_type == "IntegrityError" and "ForeignKeyViolation" in detail:
            return "Указан несуществующий ID (нарушение внешнего ключа)."
        if error_type == "ValueError" and "empty" in detail:
            return "Пустой список — нужна минимум одна dimension."
        return str(detail)[:500] if detail else f"Ошибка {r.status_code}"

    return f"Ошибка {r.status_code}"


async def gis_request(
    method: str,
    path: str,
    token: str,
    *,
    json: dict | None = None,
) -> Any:
    """Выполняет запрос в gis_api. Возвращает JSON или бросает HTTPException."""
    url = f"{GIS_API_URL}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.request(method, url, headers=headers, json=json)
    except httpx.RequestError as e:
        logger.exception("gis_api request failed")
        raise HTTPException(503, f"gis_api недоступен: {str(e)[:200]}")

    if r.status_code == 204:
        return None

    if r.status_code >= 400:
        raise HTTPException(r.status_code, _humanize_error(r, f"{method} {path}"))

    try:
        return r.json()
    except Exception:
        return None
