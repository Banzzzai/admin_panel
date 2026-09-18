from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime
from .settings.config import Config

Base = declarative_base()
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(255), nullable=True)          
    password_hash = Column(String(256), nullable=True)  
    role = Column(String(20), default='viewer')         
    created_at = Column(DateTime, default=datetime.utcnow)

    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    sessions = relationship('UserSession', backref='user', lazy='dynamic')

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    def get_id(self):
        return self.username
class UserSession(Base):
    __tablename__ = 'user_sessions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    ip_address = Column(String(45))
    user_agent = Column(String(256))
    login_time = Column(DateTime, default=datetime.utcnow)
    logout_time = Column(DateTime, nullable=True)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class AuditLog(Base):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))   # кто совершил действие
    action = Column(String(100), nullable=False)        # тип действия (create_user, delete_user, edit_user)
    target_user_id = Column(Integer, nullable=True)     # над кем совершено действие
    details = Column(String(500), nullable=True)        # дополнительная информация
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=datetime.utcnow)

    actor = relationship('User', foreign_keys=[user_id], backref='audit_actions')