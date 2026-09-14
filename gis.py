from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx
import os

from auth import manager
from config import Config

router = APIRouter()
templates = Jinja2Templates(directory="templates")

GIS_API_URL = os.environ.get("GIS_API_URL", "http://gis_api:8001")


def admin_required(user=Depends(manager)):
    if user.role != Config.KEYCLOAK_ADMIN_ROLE:
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return user


async def _get_service_token() -> str:
    """client_credentials → токен для gis_api."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{Config.KEYCLOAK_URL}/realms/{Config.KEYCLOAK_REALM}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": Config.KEYCLOAK_ADMIN_CLIENT_ID,
                "client_secret": Config.KEYCLOAK_ADMIN_CLIENT_SECRET,
            },
        )
        r.raise_for_status()
        return r.json()["access_token"]


async def gis_request(method: str, path: str, **kwargs):
    token = await _get_service_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.request(method, f"{GIS_API_URL}{path}", headers=headers, **kwargs)
    return r


# ---------- Workspaces ----------

@router.get("/workspaces")
async def workspaces(request: Request, user=Depends(admin_required)):
    r = await gis_request("GET", "/workspace/")
    items = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse("gis_workspaces.html", {
        "request": request, "current_user": user, "items": items, "error": None if r.status_code == 200 else r.text,
    })


@router.post("/workspaces/create")
async def workspace_create(request: Request,
                            name: str = Form(...),
                            user=Depends(admin_required)):
    r = await gis_request("POST", "/workspace/", json={"name": name})
    if r.status_code not in (200, 201, 204):
        raise HTTPException(400, f"gis_api: {r.text}")
    return RedirectResponse(url="/gis/workspaces", status_code=303)


@router.get("/workspaces/delete/{item_id}")
async def workspace_delete(item_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("DELETE", f"/workspace/{item_id}")
    if r.status_code not in (200, 204):
        raise HTTPException(400, f"gis_api: {r.text}")
    return RedirectResponse(url="/gis/workspaces", status_code=303)


# ---------- Layer chunks ----------

@router.get("/layer-chunks")
async def layer_chunks(request: Request, user=Depends(admin_required)):
    r = await gis_request("GET", "/layer_chunk/")
    items = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse("gis_layer_chunks.html", {
        "request": request, "current_user": user, "items": items, "error": None if r.status_code == 200 else r.text,
    })


@router.post("/layer-chunks/create")
async def layer_chunk_create(request: Request,
                              name: str = Form(...),
                              user=Depends(admin_required)):
    r = await gis_request("POST", "/layer_chunk/", json={"name": name})
    if r.status_code not in (200, 201, 204):
        raise HTTPException(400, f"gis_api: {r.text}")
    return RedirectResponse(url="/gis/layer-chunks", status_code=303)


@router.get("/layer-chunks/delete/{item_id}")
async def layer_chunk_delete(item_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("DELETE", f"/layer_chunk/{item_id}")
    if r.status_code not in (200, 204):
        raise HTTPException(400, f"gis_api: {r.text}")
    return RedirectResponse(url="/gis/layer-chunks", status_code=303)


# ---------- Product sets ----------

@router.get("/product-sets")
async def product_sets(request: Request, user=Depends(admin_required)):
    r = await gis_request("GET", "/product_set/")
    items = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse("gis_product_sets.html", {
        "request": request, "current_user": user, "items": items, "error": None if r.status_code == 200 else r.text,
    })


@router.post("/product-sets/create")
async def product_set_create(request: Request,
                              name: str = Form(...),
                              user=Depends(admin_required)):
    r = await gis_request("POST", "/product_set/", json={"name": name})
    if r.status_code not in (200, 201, 204):
        raise HTTPException(400, f"gis_api: {r.text}")
    return RedirectResponse(url="/gis/product-sets", status_code=303)


@router.get("/product-sets/delete/{item_id}")
async def product_set_delete(item_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("DELETE", f"/product_set/{item_id}")
    if r.status_code not in (200, 204):
        raise HTTPException(400, f"gis_api: {r.text}")
    return RedirectResponse(url="/gis/product-sets", status_code=303)


# ---------- Products ----------

@router.get("/products")
async def products(request: Request, user=Depends(admin_required)):
    r = await gis_request("GET", "/product")
    items = r.json() if r.status_code == 200 else []
    return templates.TemplateResponse("gis_products.html", {
        "request": request, "current_user": user, "items": items, "error": None if r.status_code == 200 else r.text,
    })


@router.post("/products/create")
async def product_create(request: Request,
                          name: str = Form(...),
                          user=Depends(admin_required)):
    r = await gis_request("POST", "/product", json={"name": name})
    if r.status_code not in (200, 201, 204):
        raise HTTPException(400, f"gis_api: {r.text}")
    return RedirectResponse(url="/gis/products", status_code=303)


@router.get("/products/delete/{item_id}")
async def product_delete(item_id: str, request: Request, user=Depends(admin_required)):
    r = await gis_request("DELETE", f"/product/{item_id}")
    if r.status_code not in (200, 204):
        raise HTTPException(400, f"gis_api: {r.text}")
    return RedirectResponse(url="/gis/products", status_code=303)
