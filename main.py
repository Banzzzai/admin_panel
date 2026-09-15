from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from src.routers.router_auth import manager
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
    ],
)

setup_exception_handlers(app)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ---- stribog_auth (без префикса: login/callback/logout) ----
app.include_router(router_auth.router)

# ---- stribog_auth (с префиксом /auth: users/audit/activity/logs) ----
app.include_router(router_users.router,    prefix="/auth/users",    tags=["auth:users"])
app.include_router(router_audit.router,    prefix="/auth/audit",    tags=["auth:audit"])
app.include_router(router_activity.router, prefix="/auth/activity", tags=["auth:activity"])
app.include_router(router_logs.router,     prefix="/auth/logs",     tags=["auth:logs"])

# ---- gis_loader ----
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
