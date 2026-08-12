from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, UserSession
from werkzeug.security import generate_password_hash

users_bp = Blueprint('users', __name__)

def admin_required(func):
    "Ограничивает доступ: только для пользователей с ролью 'admin'."
    @wraps(func)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Требуются права администратора', 'danger')
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    return wrapper

@users_bp.route('/')
@login_required
def user_list():
    users = User.query.all()
    active_session = UserSession.query.filter_by(
        user_id=current_user.id, is_active=True
    ).order_by(UserSession.login_time.desc()).first()
    current_session_id = active_session.id if active_session else None
    return render_template('users.html', users=users, current_session_id=current_session_id)

@users_bp.route('/create', methods=['POST'])
@admin_required
def create_user():
    username = request.form['username']
    password = request.form['password']
    role = request.form.get('role', 'user')
    if User.query.filter_by(username=username).first():
        flash('Пользователь уже существует', 'danger')
    else:
        user = User(username=username,
                    password_hash=generate_password_hash(password),
                    role=role)
        db.session.add(user)
        db.session.commit()
        flash('Пользователь создан', 'success')
    return redirect(url_for('users.user_list'))

@users_bp.route('/delete/<int:user_id>')
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('Нельзя удалить самого себя', 'danger')
        return redirect(url_for('users.user_list'))

    if user.role == 'admin':
        flash('Нельзя удалить учётную запись администратора', 'danger')
        return redirect(url_for('users.user_list'))

    db.session.delete(user)
    db.session.commit()
    flash('Пользователь {} удалён'.format(user.username), 'success')
    return redirect(url_for('users.user_list'))

@users_bp.route('/edit/<int:user_id>', methods=['POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id and 'role' in request.form:
        flash('Вы не можете изменить свою собственную роль', 'danger')
        return redirect(url_for('users.user_list'))

    new_username = request.form.get('username', '').strip()
    if new_username and new_username != user.username:
        if User.query.filter(User.username == new_username, User.id != user.id).first():
            flash('Пользователь с таким логином уже существует', 'danger')
            return redirect(url_for('users.user_list'))
        user.username = new_username

    if 'role' in request.form and user.id != current_user.id:
        user.role = request.form['role']

    new_password = request.form.get('password', '').strip()
    if new_password:
        user.password_hash = generate_password_hash(new_password)

    db.session.commit()
    flash('Данные пользователя {} обновлены'.format(user.username), 'success')
    return redirect(url_for('users.user_list'))