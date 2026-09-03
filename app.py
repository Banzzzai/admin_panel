from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from models import Base, engine, SessionLocal
from auth import router as auth_router, manager
from users import router as users_router
from logs import router as logs_router
from activity import router as activity_router
from audit import router as audit_router

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Подключаем роутеры
app.include_router(auth_router)
app.include_router(users_router, prefix="/users")
app.include_router(logs_router, prefix="/logs")
app.include_router(activity_router, prefix="/activity")
app.include_router(audit_router, prefix="/audit")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def index(request: Request, user=Depends(manager.optional)):
    if not user:
        return RedirectResponse(url="/login")
    if user.role == "admin":
        return RedirectResponse(url="/users")
    return templates.TemplateResponse("dashboard.html", {"request": request, "current_user": user})