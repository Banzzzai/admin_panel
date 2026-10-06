"""JSON API: /api/products"""
from fastapi import APIRouter, Depends, Body, Path, HTTPException, status

from src.api.deps import require_admin
from src.api.gis_client import gis_request

router = APIRouter(prefix="/products", tags=["api:products"])


@router.get(
    "",
    summary="Список продуктов",
    description="Возвращает все продукты из gis_api. Требуется роль `admin-panel-admin`.",
)
async def list_products(user: dict = Depends(require_admin)):
    data = await gis_request("GET", "/product/", token=user["token"])
    return {"ok": True, "data": data or []}


@router.get("/{product_id}", summary="Получить продукт")
async def get_product(
    product_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    data = await gis_request("GET", f"/product/{product_id}", token=user["token"])
    return {"ok": True, "data": data}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать продукт",
    description="Создаёт продукт. Обязательные поля: `product_id`, `set_id`.",
)
async def create_product(
    payload: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """
    Тело запроса:

        {
          "product_id": "test_product",
          "set_id": "test_set",
          "style": {"style_type": "titiler", "content": ""}
        }

    """
    if not payload.get("product_id"):
        raise HTTPException(400, "Поле «product_id» обязательно")
    if not payload.get("set_id"):
        raise HTTPException(400, "Поле «set_id» обязательно")

    data = await gis_request(
        "POST", "/product/", token=user["token"], json=payload
    )
    return {"ok": True, "data": data}


@router.put(
    "/{product_id}",
    summary="Обновить продукт",
    description="Меняет только `style`. `product_id` и `set_id` — read-only.",
)
async def update_product(
    product_id: str = Path(...),
    payload: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """Тело запроса: `{"style": {"style_type": "titiler", "content": "..."}}`"""
    if not payload.get("style"):
        raise HTTPException(400, "Поле «style» обязательно")

    # ProductPut принимает ТОЛЬКО style
    data = await gis_request(
        "PUT",
        f"/product/{product_id}",
        token=user["token"],
        json={"style": payload["style"]},
    )
    return {"ok": True, "data": data}


@router.delete("/{product_id}", summary="Удалить продукт")
async def delete_product(
    product_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    await gis_request("DELETE", f"/product/{product_id}", token=user["token"])
    return {"ok": True, "message": f"Продукт «{product_id}» удалён"}
