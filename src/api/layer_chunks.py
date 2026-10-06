"""JSON API: /api/layer-chunks"""
from fastapi import APIRouter, Depends, Path

from src.api.deps import require_admin
from src.api.gis_client import gis_request

router = APIRouter(prefix="/layer-chunks", tags=["api:layer-chunks"])


@router.get(
    "",
    summary="Список чанков",
    description=(
        "Возвращает все layer_chunks из gis_api. "
        "Создание чанков через UI не предусмотрено — они создаются через `POST /layer_chunk/` gis_api."
    ),
)
async def list_layer_chunks(user: dict = Depends(require_admin)):
    data = await gis_request("GET", "/layer_chunk/", token=user["token"])
    return {"ok": True, "data": data or []}


@router.get("/{layer_chunk_id}", summary="Получить чанк")
async def get_layer_chunk(
    layer_chunk_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    data = await gis_request(
        "GET", f"/layer_chunk/{layer_chunk_id}", token=user["token"]
    )
    return {"ok": True, "data": data}


@router.delete("/{layer_chunk_id}", summary="Удалить чанк")
async def delete_layer_chunk(
    layer_chunk_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    """Удаляет layer_chunk. Если файл был в MinIO — удалится и оттуда (data_manager)."""
    await gis_request(
        "DELETE", f"/layer_chunk/{layer_chunk_id}", token=user["token"]
    )
    return {"ok": True, "message": f"Чанк «{layer_chunk_id}» удалён"}
