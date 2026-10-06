"""JSON API: /api/workspaces"""
from fastapi import APIRouter, Depends, Body, Path, status

from src.api.deps import require_admin
from src.api.gis_client import gis_request

router = APIRouter(prefix="/workspaces", tags=["api:workspaces"])


@router.get(
    "",
    summary="Список воркспейсов",
    description="Возвращает все воркспейсы из gis_api. Требуется Bearer-токен с ролью `admin-panel-admin`.",
)
async def list_workspaces(user: dict = Depends(require_admin)):
    data = await gis_request("GET", "/workspace/", token=user["token"])
    return {"ok": True, "data": data or []}


@router.get("/{workspace_id}", summary="Получить воркспейс")
async def get_workspace(
    workspace_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    data = await gis_request("GET", f"/workspace/{workspace_id}", token=user["token"])
    return {"ok": True, "data": data}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Создать воркспейс",
)
async def create_workspace(
    payload: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """Тело запроса: `{"workspace_id": "...", "name": "...", "description": "..."}`"""
    data = await gis_request("POST", "/workspace/", token=user["token"], json=payload)
    return {"ok": True, "data": data}


@router.put("/{workspace_id}", summary="Обновить воркспейс")
async def update_workspace(
    workspace_id: str = Path(...),
    payload: dict = Body(...),
    user: dict = Depends(require_admin),
):
    """Тело запроса: `{"name": "...", "description": "..."}`"""
    data = await gis_request("PUT", f"/workspace/{workspace_id}", token=user["token"], json=payload)
    return {"ok": True, "data": data}


@router.delete("/{workspace_id}", summary="Удалить воркспейс")
async def delete_workspace(
    workspace_id: str = Path(...),
    user: dict = Depends(require_admin),
):
    await gis_request("DELETE", f"/workspace/{workspace_id}", token=user["token"])
    return {"ok": True, "message": f"Воркспейс «{workspace_id}» удалён"}
