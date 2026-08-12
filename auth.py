from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import db, User, UserSession
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            ip = request.remote_addr
            ua = request.headers.get('User-Agent', '')
            session = UserSession(user_id=user.id,
                                  ip_address=ip,
                                  user_agent=ua)
            db.session.add(session)
            db.session.commit()
            flash('Вход выполнен', 'success')
            # Перенаправление в зависимости от роли
            if user.role == 'admin':
                return redirect(url_for('users.user_list'))
            else:
                return redirect(url_for('index'))
        flash('Неверные учётные данные', 'danger')
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    active_sessions = UserSession.query.filter_by(
        user_id=current_user.id, is_active=True
    ).all()
    for s in active_sessions:
        s.is_active = False
        s.logout_time = datetime.utcnow()
    db.session.commit()
    logout_user()
    flash('Вы вышли', 'info')
    return redirect(url_for('auth.login'))