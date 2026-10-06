"""JSON API: /api/product-sets"""
from fastapi import APIRouter, Depends, Body, Path, HTTPException, status

from src.api.deps import require_admin
from src.api.gis_client import gis_request

router = APIRouter(prefix="/product-sets", tags=["api:product-sets"])


@router.get(
    "",
    summary="Список продукт-сетов",
    description="Возвращает все product_sets из gis_api. Требуется Bearer-токен с ролью `admin-panel-admin`.",
)
async def list_product_sets(user: dict = Depends(require_admin)):
    data = await gis_request("GET", "/product_set/", token=user["token"])
    return {"ok": True, "data": data or []}


@router.get("/{set_id}", summary="Получить продукт-сет")
async def get_product_set(
    set_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    data = await gis_request("GET", f"/product_set/{set_id}", token=user["token"])
    return {"ok": True, "data": data}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать продукт-сет",
    description=(
        "Создаёт product_set. Обязательна минимум одна dimension "
        "(иначе gis_api вернёт `ValueError: instances empty`)."
    ),
)
async def create_product_set(
    payload: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """
    Тело запроса:

        {
          "set_id": "test_set",
          "workspace_id": "test_workspace",
          "native_crs": "EPSG:4326",
          "dimensions": [
            {"source": "manual", "description": "time",
             "dimension_id": "time", "dimension_type": "timestamp"}
          ],
          "storage_config": {"storage_type": "s3_cog", "storage_bucket": "bucket"}
        }

    """
    if not payload.get("set_id"):
        raise HTTPException(400, "Поле «set_id» обязательно")
    if not payload.get("workspace_id"):
        raise HTTPException(400, "Поле «workspace_id» обязательно")

    dims = payload.get("dimensions") or []
    if not dims:
        raise HTTPException(400, "Нужна хотя бы одна dimension")

    data = await gis_request(
        "POST", "/product_set/", token=user["token"], json=payload
    )
    return {"ok": True, "data": data}


@router.put(
    "/{set_id}",
    summary="Обновить продукт-сет",
    description="Меняет только `workspace_id`. Остальные поля — read-only.",
)
async def update_product_set(
    set_id: str = Path(...),
    payload: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """Тело запроса: `{"workspace_id": "test_workspace"}`"""
    if not payload.get("workspace_id"):
        raise HTTPException(400, "Поле «workspace_id» обязательно")

    # ProductSetPut принимает ТОЛЬКО workspace_id
    data = await gis_request(
        "PUT",
        f"/product_set/{set_id}",
        token=user["token"],
        json={"workspace_id": payload["workspace_id"]},
    )
    return {"ok": True, "data": data}


@router.delete("/{set_id}", summary="Удалить продукт-сет")
async def delete_product_set(
    set_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    """Удаляет product_set и все связанные products/layer_chunks."""
    await gis_request("DELETE", f"/product_set/{set_id}", token=user["token"])
    return {"ok": True, "message": f"Продукт-сет «{set_id}» удалён"}
