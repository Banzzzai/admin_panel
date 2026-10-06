"""JSON API: /api/status — проверка здоровья зависимостей."""
import time

import httpx
from fastapi import APIRouter, Depends

from src.api.deps import require_admin
from src.settings.config import Config

router = APIRouter(prefix="/status", tags=["api:status"])


@router.get(
    "",
    summary="Статус сервисов",
    description="Проверяет доступность gis_api и Keycloak. Требуется роль `admin-panel-admin`.",
)
async def status(user: dict = Depends(require_admin)):
    """Проверка gis_api и Keycloak."""
    checks = []

    # gis_api endpoints
    gis_endpoints = [
        ("gis_api /", "/"),
        ("gis_api /workspace/", "/workspace/"),
        ("gis_api /product_set/", "/product_set/"),
        ("gis_api /product/", "/product/"),
        ("gis_api /layer_chunk/", "/layer_chunk/"),
    ]

    token = user.get("token")

    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, path in gis_endpoints:
            t0 = time.time()
            try:
                r = await client.get(
                    f"{Config.GIS_API_URL}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                dt = int((time.time() - t0) * 1000)
                checks.append({
                    "name": name,
                    "ok": r.status_code == 200,
                    "code": r.status_code,
                    "ms": dt,
                    "error": None,
                })
            except Exception as e:
                checks.append({
                    "name": name,
                    "ok": False,
                    "code": "—",
                    "ms": None,
                    "error": str(e)[:200],
                })

    # Keycloak
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}/.well-known/openid-configuration"
            )
            dt = int((time.time() - t0) * 1000)
            checks.append({
                "name": f"Keycloak /realms/{Config.KEYCLOAK_REALM}",
                "ok": r.status_code == 200,
                "code": r.status_code,
                "ms": dt,
                "error": None,
            })
    except Exception as e:
        checks.append({
            "name": "Keycloak",
            "ok": False,
            "code": "—",
            "ms": None,
            "error": str(e)[:200],
        })

    all_ok = all(c["ok"] for c in checks)
    return {
        "ok": all_ok,
        "data": checks,
        "meta": {
            "total_checks": len(checks),
            "passed": sum(1 for c in checks if c["ok"]),
            "failed": sum(1 for c in checks if not c["ok"]),
        },
    }
