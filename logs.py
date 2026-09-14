from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from auth import manager
from config import Config
import os

router = APIRouter()
templates = Jinja2Templates(directory="templates")

LOG_FILE = os.environ.get('LOG_FILE_PATH', '/var/log/auth.log')

@router.get("/", response_class=HTMLResponse)
def view_logs(request: Request, user=Depends(manager)):
    if user.role != Config.KEYCLOAK_ADMIN_ROLE:
        return RedirectResponse(url="/", status_code=303)

    lines_to_show = 200
    lines = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                buffer = []
                block_size = 1024
                while len(buffer) < lines_to_show and file_size > 0:
                    if file_size - block_size < 0:
                        block_size = file_size
                    file_size -= block_size
                    f.seek(file_size)
                    chunk = f.read(block_size)
                    buffer = chunk.splitlines(True) + buffer
                lines = buffer[-lines_to_show:] if len(buffer) > lines_to_show else buffer
        except PermissionError:
            lines = ["[ОШИБКА] Нет прав на чтение файла."]
        except Exception as e:
            lines = [f"[ОШИБКА] {str(e)}"]
    else:
        lines = [f"[ИНФО] Файл логов {LOG_FILE} не найден."]

    return templates.TemplateResponse("logs.html", {"request": request, "lines": lines, "current_user": user})