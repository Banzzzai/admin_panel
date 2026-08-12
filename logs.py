from flask import Blueprint, render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
import os

logs_bp = Blueprint('logs', __name__)


LOG_FILE = os.environ.get('LOG_FILE_PATH', '/var/log/auth.log')

def admin_required(func):
    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Доступ к логам разрешён только администраторам', 'danger')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return wrapper

@logs_bp.route('/')
@admin_required
def view_logs():
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
            lines = ['[ОШИБКА] Нет прав на чтение файла. Добавьте пользователя в группу adm.']
        except Exception as e:
            lines = ['[ОШИБКА] Не удалось прочитать лог: {}'.format(str(e))]
    else:
        lines = ['[ИНФО] Файл логов {} не найден.'.format(LOG_FILE)]

    return render_template('logs.html', lines=lines)