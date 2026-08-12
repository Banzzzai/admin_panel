from flask import Flask, redirect, url_for, render_template
from config import Config
from models import db
from flask_login import LoginManager, current_user

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Регистрация blueprint'ов
    from auth import auth_bp
    app.register_blueprint(auth_bp)
    from users import users_bp
    app.register_blueprint(users_bp, url_prefix='/users')
    from logs import logs_bp
    app.register_blueprint(logs_bp, url_prefix='/logs')
    from activity import activity_bp
    app.register_blueprint(activity_bp, url_prefix='/activity')

    @app.route('/')
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role == 'admin':
            return redirect(url_for('users.user_list'))
        # Обычный пользователь видит пустую страницу
        return render_template('dashboard.html')

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    create_app().run(host='0.0.0.0', port=5000, debug=False)