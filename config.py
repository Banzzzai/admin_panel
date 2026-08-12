import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'supersecretkey-change-me'

    # Параметры подключения к PostgreSQL (значения по умолчанию для docker-compose)
    DB_USER = os.environ.get('POSTGRES_USER', 'admin_user')
    DB_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'admin_password')
    DB_HOST = os.environ.get('POSTGRES_HOST', 'db')      
    DB_PORT = os.environ.get('POSTGRES_PORT', '5432')
    DB_NAME = os.environ.get('POSTGRES_DB', 'admin_panel')

    SQLALCHEMY_DATABASE_URI = (
        f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,   # проверяет живость соединения перед использованием
}