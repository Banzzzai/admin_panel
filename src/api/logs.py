"""JSON API: /api/logs — системные логи (/var/log/auth.log)."""
import os
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import require_admin

router = APIRouter(prefix="/logs", tags=["api:logs"])

LOG_FILE = os.environ.get("LOG_FILE_PATH", "/var/log/auth.log")


def _read_logs(limit: int, offset: int, search: Optional[str] = None):
    """Читает последние N строк лога. Возвращает (lines, total, has_more)."""
    if not os.path.exists(LOG_FILE):
        return [], 0, False

    try:
        with open(LOG_FILE, "r", errors="replace") as f:
            all_lines = f.readlines()
    except PermissionError:
        return [], 0, False

    # Фильтр по строке
    if search:
        all_lines = [l for l in all_lines if search.lower() in l.lower()]

    total = len(all_lines)

    # Идём с конца (свежие сверху)
    # offset — сколько пропустить с конца
    reversed_lines = list(reversed(all_lines))
    start = offset
    end = start + limit
    page = reversed_lines[start:end]

    return page, total, end < total


@router.get(
    "",
    summary="Системные логи",
    description=(
        f"Возвращает строки из `{LOG_FILE}` (свежие сверху). "
        "Поддерживает поиск по подстроке и пагинацию."
    ),
)
async def list_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    user: dict = Depends(require_admin),
):
    lines, total, has_more = _read_logs(limit, offset, search)

    if total == 0 and not os.path.exists(LOG_FILE):
        return {
            "ok": False,
            "detail": f"Файл логов не найден: {LOG_FILE}",
        }

    return {
        "ok": True,
        "data": [l.rstrip("\n") for l in lines],
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        },
    }


@router.get(
    "/info",
    summary="Информация о лог-файле",
    description="Возвращает путь, размер и время последнего изменения файла логов.",
)
async def logs_info(user: dict = Depends(require_admin)):
    if not os.path.exists(LOG_FILE):
        return {"ok": False, "detail": f"Файл не найден: {LOG_FILE}"}

    try:
        stat = os.stat(LOG_FILE)
        return {
            "ok": True,
            "data": {
                "path": LOG_FILE,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            },
        }
    except PermissionError:
        return {"ok": False, "detail": "Нет прав на чтение файла"}
