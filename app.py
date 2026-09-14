from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config import Config
from models import Base, engine
from auth import router as auth_router, manager
from users import router as users_router
from logs import router as logs_router
from activity import router as activity_router
from audit import router as audit_router
from gis import router as gis_router


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.add_middleware(SessionMiddleware, secret_key=Config.SECRET_KEY)
app.include_router(gis_router, prefix="/gis")
app.include_router(auth_router)
app.include_router(users_router, prefix="/users")
app.include_router(logs_router, prefix="/logs")
app.include_router(activity_router, prefix="/activity")
app.include_router(audit_router, prefix="/audit")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def index(request: Request, user=Depends(manager.optional)):
    if not user:
        return RedirectResponse(url="/login")
    if user.role == Config.KEYCLOAK_ADMIN_ROLE:
        return RedirectResponse(url="/users")
    return templates.TemplateResponse("dashboard.html", {"request": request, "current_user": user})
