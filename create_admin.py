from models import SessionLocal, User
from auth import hash_password

if __name__ == "__main__":
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin"
            )
            db.add(admin)
            db.commit()
            print("Администратор создан: логин admin, пароль admin123")
        else:
            admin.password_hash = hash_password("admin123")
            db.commit()
            print("Пароль администратора обновлён")
    finally:
        db.close()