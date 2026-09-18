from fastapi import FastAPI, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from urllib.parse import parse_qs

from src.settings.config import Config
from src.models import Base, engine
from src.exception.error_handler import setup_exception_handlers
from src.routers import (
    router_auth,
    router_users,
    router_audit,
    router_activity,
    router_logs,
    router_gis,
)
from src.routers.router_auth import manager


class MethodOverrideMiddleware(BaseHTTPMiddleware):
    """Читает POST-форму, если есть _method=PUT/DELETE/PATCH — подменяет HTTP-метод."""

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            content_type = request.headers.get("content-type", "")

            if "application/x-www-form-urlencoded" in content_type:
                body = await request.body()

                override = None
                try:
                    params = parse_qs(body.decode("utf-8"))
                    override = (params.get("_method") or [None])[0]
                except Exception:
                    override = None

                async def receive():
                    return {"type": "http.request", "body": body, "more_body": False}
                request._receive = receive

                if override:
                    request.scope["method"] = override.upper()

        return await call_next(request)


app = FastAPI(
    title="Admin Panel",
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(SessionMiddleware, secret_key=Config.SECRET_KEY),
        Middleware(MethodOverrideMiddleware),
    ],
)

setup_exception_handlers(app)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(router_auth.router)

app.include_router(router_users.router,    prefix="/auth/users",    tags=["auth:users"])
app.include_router(router_audit.router,    prefix="/auth/audit",    tags=["auth:audit"])
app.include_router(router_activity.router, prefix="/auth/activity", tags=["auth:activity"])
app.include_router(router_logs.router,     prefix="/auth/logs",     tags=["auth:logs"])

app.include_router(router_gis.router, prefix="/gis", tags=["gis"])


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def index(user=Depends(manager.optional)):
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user.role == Config.KEYCLOAK_ADMIN_ROLE:
        return RedirectResponse("/auth/users/", status_code=303)
    return {"status": "ok", "user": user.username}
