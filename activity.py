from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, UserSession
from datetime import datetime, timedelta

activity_bp = Blueprint('activity', __name__)

def admin_required(func):
    """Декоратор: доступ только для администраторов"""
    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Доступ к активности разрешён только администраторам', 'danger')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return wrapper

@activity_bp.route('/heartbeat')
@login_required
def heartbeat():
    """Обновляет время последней активности текущей сессии"""
    session_id = request.args.get('session_id')
    if session_id:
        session = UserSession.query.get(session_id)
        if session and session.user_id == current_user.id:
            session.last_activity = datetime.utcnow()
            db.session.commit()
    return '', 204

@activity_bp.route('/')
@login_required
@admin_required
def user_activity():
    """Страница активности всех пользователей"""
    users = User.query.all()

    # Пользователь онлайн, если есть хотя бы одна активная сессия
    for u in users:
        u.is_online = any(s.is_active for s in u.sessions)

    # Получаем ID активной сессии текущего пользователя для heartbeat
    active_session = UserSession.query.filter_by(
        user_id=current_user.id, is_active=True
    ).order_by(UserSession.login_time.desc()).first()
    current_session_id = active_session.id if active_session else None

    return render_template(
        'activity.html',
        users=users,
        current_session_id=current_session_id
    )

@activity_bp.route('/user/<int:user_id>')
@login_required
@admin_required
def user_activity_detail(user_id):
    """История сессий конкретного пользователя с пагинацией по 10 записей"""
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)
    per_page = 10

    pagination = UserSession.query.filter_by(user_id=user.id)\
        .order_by(UserSession.login_time.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    sessions = pagination.items

    return render_template(
        'user_activity_detail.html',
        user=user,
        sessions=sessions,
        pagination=pagination
    )