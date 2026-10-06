"""Admin Panel API — FastAPI + React."""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from src.settings.config import Config
from src.models import Base, engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    parts = [f"{'.'.join(str(x) for x in e.get('loc', []))}: {e.get('msg', '')}" for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "; ".join(parts) or "Validation error"})


async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app = FastAPI(
    title="Admin Panel API",
    version="1.0.0",
    description="REST API для React-админки. Аутентификация — Bearer (Keycloak JWT).",
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origin_regex=Config.CORS_ORIGIN_REGEX,
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
    exception_handlers={
        StarletteHTTPException: http_exception_handler,
        RequestValidationError: validation_exception_handler,
        Exception: unhandled_exception_handler,
    },
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    logger.info("Admin Panel API started")


@app.get("/health", tags=["system"], summary="Health check")
def health():
    return {"ok": True, "data": {"status": "healthy"}}


# ============ JSON API для React SPA ============

from src.api import (  # noqa: E402
    workspaces, product_sets, products, layer_chunks,
    users, audit, activity, logs, status as status_api,
)

app.include_router(workspaces.router,    prefix="/api")
app.include_router(product_sets.router,  prefix="/api")
app.include_router(products.router,      prefix="/api")
app.include_router(layer_chunks.router,  prefix="/api")
app.include_router(users.router,         prefix="/api")
app.include_router(audit.router,         prefix="/api")
app.include_router(activity.router,      prefix="/api")
app.include_router(logs.router,          prefix="/api")
app.include_router(status_api.router,    prefix="/api")
