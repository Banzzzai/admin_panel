from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer
from cachetools import TTLCache
import httpx
import os
import time
import logging

from .router_auth import manager
from ..settings.config import Config

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

GIS_API_URL = os.environ.get("GIS_API_URL", "http://gis_api:8001")

security = HTTPBearer(auto_error=False)


# ============ Проверка прав ============

async def admin_required(
    request: Request,
    credentials=Depends(security),
):
    """Гибкая проверка: Bearer (Swagger) ИЛИ cookie (UI)."""
    from src.jwks import jwks

    # 1. Bearer (Swagger / API)
    if credentials and credentials.credentials:
        payload = jwks.validate_token(credentials.credentials)
        roles = payload.get("realm_access", {}).get("roles", [])
        resource = payload.get("resource_access", {})
        for client in resource.values():
            roles += client.get("roles", [])
        if Config.KEYCLOAK_ADMIN_ROLE not in roles:
            raise HTTPException(403, "Требуются права администратора")
        request.session["access_token"] = credentials.credentials
        return {"username": payload.get("preferred_username"), "role": Config.KEYCLOAK_ADMIN_ROLE}

    # 2. Cookie (UI)
    user = await manager.optional(request)
    if not user:
        raise HTTPException(401, "Не авторизован")
    if user.role != Config.KEYCLOAK_ADMIN_ROLE:
        raise HTTPException(403, "Требуются права администратора")
    return user


# ============ Токен пользователя для gis_api ============

def _get_user_token(request: Request) -> str | None:
    """Берёт токен пользователя из Bearer-заголовка или из сессии (cookie)."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    token = request.session.get("access_token")
    return token


async def gis_request(method: str, path: str, request: Request, **kwargs):
    """Запрос к gis_api с токеном пользователя."""
    token = _get_user_token(request)
    if not token:
        raise HTTPException(401, "Нет токена пользователя — войдите или передайте Bearer")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.request(method, f"{GIS_API_URL}{path}", headers=headers, **kwargs)
    return r


# ============ Кэш GET-ответов (10 сек) ============

_gis_cache: TTLCache = TTLCache(maxsize=200, ttl=10)


async def gis_get_cached(path: str, request: Request):
    """GET с кэшем (10 сек)."""
    if path in _gis_cache:
        return _gis_cache[path]
    r = await gis_request("GET", path, request=request)
    if r.status_code == 200:
        _gis_cache[path] = r
    return r


def _invalidate_cache(path: str = None):
    if path is None:
        _gis_cache.clear()
    else:
        _gis_cache.pop(path, None)


# ============ Хелперы для flash-сообщений ============

def pop_flash(request: Request) -> dict:
    return {
        "flash_error": request.session.pop("flash_error", None),
        "flash_success": request.session.pop("flash_success", None),
    }


def flash_error(request: Request, message: str, redirect_to: str) -> RedirectResponse:
    request.session["flash_error"] = message
    return RedirectResponse(url=redirect_to, status_code=303)


def flash_success(request: Request, message: str, redirect_to: str) -> RedirectResponse:
    request.session["flash_success"] = message
    return RedirectResponse(url=redirect_to, status_code=303)


def _humanize_error(r: httpx.Response, action: str) -> str:
    try:
        data = r.json()
    except Exception:
        return f"Не удалось {action}: {r.status_code} {r.text[:200]}"

    if isinstance(data, dict) and "detail" in data and isinstance(data["detail"], list):
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
        return f"Не удалось {action}: {detail[:300]}"

    return f"Не удалось {action}: {r.status_code}"


# ==================== WORKSPACES ====================

@router.get(
    "/workspaces/",
    summary="Список воркспейсов",
    description="Возвращает список всех воркспейсов из gis_api. Требуется роль `admin-panel-admin`.",
    tags=["gis:workspaces"],
)
async def workspaces(request: Request, user=Depends(admin_required)):
    r = await gis_get_cached("/workspace/", request=request)
    items = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse("gis_workspaces.html", {
        "request": request, "current_user": user, "items": items,
        **pop_flash(request),
    })


@router.post(
    "/workspaces/",
    summary="Создать воркспейс",
    description="Создаёт новый воркспейс. Обязательные поля: `workspace_id`, `name`.",
    tags=["gis:workspaces"],
)
async def workspace_create(request: Request,
                            workspace_id: str = Form(...),
                            name: str = Form(...),
                            description: str = Form(None),
                            user=Depends(admin_required)):
    if not workspace_id.strip() or not name.strip():
        return flash_error(request, "Заполните workspace_id и name.", "/gis/workspaces/")

    payload = {"workspace_id": workspace_id.strip(), "name": name.strip(), "description": (description or "").strip()}
    r = await gis_request("POST", "/workspace/", request=request, json=payload)
    if r.status_code not in (200, 201, 204):
        return flash_error(request, _humanize_error(r, "создать воркспейс"), "/gis/workspaces/")
    _invalidate_cache("/workspace/")
    return flash_success(request, f"Воркспейс «{workspace_id}» создан.", "/gis/workspaces/")


@router.get(
    "/workspaces/{workspace_id}",
    summary="Получить воркспейс",
    description="Возвращает один воркспейс по его `workspace_id` в формате JSON.",
    tags=["gis:workspaces"],
)
async def workspace_get(workspace_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("GET", f"/workspace/{workspace_id}", request=request)
    if r.status_code != 200:
        raise HTTPException(r.status_code, _humanize_error(r, "получить воркспейс"))
    return r.json()


@router.put(
    "/workspaces/{workspace_id}",
    summary="Обновить воркспейс",
    description="Обновляет `name` и `description` воркспейса. `workspace_id` неизменяем.",
    tags=["gis:workspaces"],
)
async def workspace_update(workspace_id: str, request: Request,
                            name: str = Form(...),
                            description: str = Form(None),
                            user=Depends(admin_required)):
    if not name.strip():
        return flash_error(request, "Поле «Название» обязательно.", "/gis/workspaces/")

    payload = {"name": name.strip(), "description": (description or "").strip()}
    r = await gis_request("PUT", f"/workspace/{workspace_id}", request=request, json=payload)
    if r.status_code not in (200, 204):
        return flash_error(request, _humanize_error(r, "обновить воркспейс"), "/gis/workspaces/")
    _invalidate_cache("/workspace/")
    return flash_success(request, f"Воркспейс «{workspace_id}» обновлён.", "/gis/workspaces/")


@router.delete(
    "/workspaces/{workspace_id}",
    summary="Удалить воркспейс",
    description="Удаляет воркспейс и все связанные product_sets (каскадно на стороне gis_api).",
    tags=["gis:workspaces"],
)
async def workspace_delete(workspace_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("DELETE", f"/workspace/{workspace_id}", request=request)
    if r.status_code not in (200, 204):
        return flash_error(request, _humanize_error(r, "удалить воркспейс"), "/gis/workspaces/")
    _invalidate_cache("/workspace/")
    return flash_success(request, f"Воркспейс «{workspace_id}» удалён.", "/gis/workspaces/")


# ==================== PRODUCT SETS ====================

@router.get(
    "/product-sets/",
    summary="Список продукт-сетов",
    description="Возвращает список product_sets и доступных воркспейсов для выпадающего списка.",
    tags=["gis:product-sets"],
)
async def product_sets(request: Request, user=Depends(admin_required)):
    r = await gis_get_cached("/product_set/", request=request)
    items = r.json() if r.status_code == 200 else []

    r_ws = await gis_get_cached("/workspace/", request=request)
    workspaces_list = r_ws.json() if r_ws.status_code == 200 else []

    return templates.TemplateResponse("gis_product_sets.html", {
        "request": request, "current_user": user, "items": items,
        "workspaces": workspaces_list,
        **pop_flash(request),
    })


@router.post(
    "/product-sets/",
    summary="Создать продукт-сет",
    description="Создаёт product_set. Обязательна хотя бы одна dimension. "
                "Типы `storage_type`: `s3_cog`, `s3_zarr`, `postgres_vector_polygon`.",
    tags=["gis:product-sets"],
)
async def product_set_create(request: Request,
                              set_id: str = Form(...),
                              workspace_id: str = Form(...),
                              native_crs: str = Form("EPSG:4326"),
                              storage_type: str = Form("s3_cog"),
                              storage_bucket: str = Form("default-bucket"),
                              dimension_id: str = Form("time"),
                              dimension_type: str = Form("timestamp"),
                              dimension_source: str = Form("manual"),
                              dimension_description: str = Form("time dimension"),
                              user=Depends(admin_required)):
    if not set_id.strip():
        return flash_error(request, "Поле «set_id» обязательно.", "/gis/product-sets/")
    if not workspace_id.strip():
        return flash_error(request, "Выберите workspace_id.", "/gis/product-sets/")
    if not storage_bucket.strip():
        return flash_error(request, "Поле «storage_bucket» обязательно.", "/gis/product-sets/")
    if not dimension_id.strip():
        return flash_error(request, "Нужна хотя бы одна dimension.", "/gis/product-sets/")

    payload = {
        "set_id": set_id.strip(),
        "workspace_id": workspace_id.strip(),
        "native_crs": native_crs.strip() or "EPSG:4326",
        "dimensions": [
            {
                "source": dimension_source,
                "description": dimension_description,
                "dimension_id": dimension_id.strip(),
                "dimension_type": dimension_type,
            }
        ],
        "storage_config": {
            "storage_type": storage_type,
            "storage_bucket": storage_bucket.strip(),
        },
    }
    r = await gis_request("POST", "/product_set/", request=request, json=payload)
    if r.status_code not in (200, 201, 204):
        return flash_error(request, _humanize_error(r, "создать продукт-сет"), "/gis/product-sets/")
    _invalidate_cache("/product_set/")
    return flash_success(request, f"Продукт-сет «{set_id}» создан.", "/gis/product-sets/")


@router.get(
    "/product-sets/{set_id}",
    summary="Получить продукт-сет",
    description="Возвращает один product_set по его `set_id`.",
    tags=["gis:product-sets"],
)
async def product_set_get(set_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("GET", f"/product_set/{set_id}", request=request)
    if r.status_code != 200:
        raise HTTPException(r.status_code, _humanize_error(r, "получить продукт-сет"))
    return r.json()


@router.put(
    "/product-sets/{set_id}",
    summary="Обновить продукт-сет",
    description="Меняет **только** `workspace_id`. Остальные поля (`native_crs`, `storage_config`, `dimensions`) — read-only.",
    tags=["gis:product-sets"],
)
async def product_set_update(set_id: str, request: Request,
                              workspace_id: str = Form(...),
                              user=Depends(admin_required)):
    if not workspace_id.strip():
        return flash_error(request, "Выберите workspace_id.", "/gis/product-sets/")

    payload = {"workspace_id": workspace_id.strip()}
    r = await gis_request("PUT", f"/product_set/{set_id}", request=request, json=payload)
    if r.status_code not in (200, 204):
        return flash_error(request, _humanize_error(r, "обновить продукт-сет"), "/gis/product-sets/")
    _invalidate_cache("/product_set/")
    return flash_success(request, f"Продукт-сет «{set_id}» обновлён.", "/gis/product-sets/")


@router.delete(
    "/product-sets/{set_id}",
    summary="Удалить продукт-сет",
    description="Удаляет product_set и все связанные продукты и чанки.",
    tags=["gis:product-sets"],
)
async def product_set_delete(set_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("DELETE", f"/product_set/{set_id}", request=request)
    if r.status_code not in (200, 204):
        return flash_error(request, _humanize_error(r, "удалить продукт-сет"), "/gis/product-sets/")
    _invalidate_cache("/product_set/")
    return flash_success(request, f"Продукт-сет «{set_id}» удалён.", "/gis/product-sets/")


# ==================== PRODUCTS ====================

@router.get(
    "/products/",
    summary="Список продуктов",
    description="Возвращает список продуктов и доступных product_sets для выпадающего списка.",
    tags=["gis:products"],
)
async def products(request: Request, user=Depends(admin_required)):
    r = await gis_get_cached("/product/", request=request)
    items = r.json() if r.status_code == 200 else []

    r_ps = await gis_get_cached("/product_set/", request=request)
    product_sets_list = r_ps.json() if r_ps.status_code == 200 else []

    return templates.TemplateResponse("gis_products.html", {
        "request": request, "current_user": user, "items": items,
        "product_sets": product_sets_list,
        **pop_flash(request),
    })


@router.post(
    "/products/",
    summary="Создать продукт",
    description="Создаёт продукт. Обязательные поля: `product_id`, `set_id`.",
    tags=["gis:products"],
)
async def product_create(request: Request,
                          product_id: str = Form(...),
                          set_id: str = Form(...),
                          style_type: str = Form("titiler"),
                          style_content: str = Form(""),
                          user=Depends(admin_required)):
    if not product_id.strip():
        return flash_error(request, "Поле «product_id» обязательно.", "/gis/products/")
    if not set_id.strip():
        return flash_error(request, "Выберите set_id.", "/gis/products/")

    payload = {
        "product_id": product_id.strip(),
        "set_id": set_id.strip(),
        "style": {"style_type": style_type.strip() or "titiler", "content": style_content or ""},
    }
    r = await gis_request("POST", "/product/", request=request, json=payload)
    if r.status_code not in (200, 201, 204):
        return flash_error(request, _humanize_error(r, "создать продукт"), "/gis/products/")
    _invalidate_cache("/product/")
    return flash_success(request, f"Продукт «{product_id}» создан.", "/gis/products/")


@router.get(
    "/products/{product_id}",
    summary="Получить продукт",
    description="Возвращает один продукт по его `product_id`.",
    tags=["gis:products"],
)
async def product_get(product_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("GET", f"/product/{product_id}", request=request)
    if r.status_code != 200:
        raise HTTPException(r.status_code, _humanize_error(r, "получить продукт"))
    return r.json()


@router.put(
    "/products/{product_id}",
    summary="Обновить продукт",
    description="Меняет **только** `style`. `product_id` и `set_id` — read-only.",
    tags=["gis:products"],
)
async def product_update(product_id: str, request: Request,
                          style_type: str = Form("titiler"),
                          style_content: str = Form(""),
                          user=Depends(admin_required)):
    payload = {"style": {"style_type": style_type.strip() or "titiler", "content": style_content or ""}}
    r = await gis_request("PUT", f"/product/{product_id}", request=request, json=payload)
    if r.status_code not in (200, 204):
        return flash_error(request, _humanize_error(r, "обновить продукт"), "/gis/products/")
    _invalidate_cache("/product/")
    return flash_success(request, f"Продукт «{product_id}» обновлён.", "/gis/products/")


@router.delete(
    "/products/{product_id}",
    summary="Удалить продукт",
    description="Удаляет продукт по его `product_id`.",
    tags=["gis:products"],
)
async def product_delete(product_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("DELETE", f"/product/{product_id}", request=request)
    if r.status_code not in (200, 204):
        return flash_error(request, _humanize_error(r, "удалить продукт"), "/gis/products/")
    _invalidate_cache("/product/")
    return flash_success(request, f"Продукт «{product_id}» удалён.", "/gis/products/")


# ==================== LAYER CHUNKS ====================

@router.get(
    "/layer-chunks/",
    summary="Список чанков",
    description="Возвращает список layer_chunks. Создание и редактирование чанков через UI не предусмотрено "
                "(они создаются через API `POST /layer_chunk/` gis_api).",
    tags=["gis:layer-chunks"],
)
async def layer_chunks(request: Request, user=Depends(admin_required)):
    r = await gis_get_cached("/layer_chunk/", request=request)
    items = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse("gis_layer_chunks.html", {
        "request": request, "current_user": user, "items": items,
        **pop_flash(request),
    })


@router.get(
    "/layer-chunks/{layer_chunk_id}",
    summary="Получить чанк",
    description="Возвращает один layer_chunk по его `layer_chunk_id` (UUID).",
    tags=["gis:layer-chunks"],
)
async def layer_chunk_get(layer_chunk_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("GET", f"/layer_chunk/{layer_chunk_id}", request=request)
    if r.status_code != 200:
        raise HTTPException(r.status_code, _humanize_error(r, "получить чанк"))
    return r.json()


@router.delete(
    "/layer-chunks/{layer_chunk_id}",
    summary="Удалить чанк",
    description="Удаляет layer_chunk. Если файл был в MinIO — удалится и оттуда (data_manager).",
    tags=["gis:layer-chunks"],
)
async def layer_chunk_delete(layer_chunk_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("DELETE", f"/layer_chunk/{layer_chunk_id}", request=request)
    if r.status_code not in (200, 204):
        return flash_error(request, _humanize_error(r, "удалить чанк"), "/gis/layer-chunks/")
    _invalidate_cache("/layer_chunk/")
    return flash_success(request, "Чанк удалён.", "/gis/layer-chunks/")
