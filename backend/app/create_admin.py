import argparse
from app.database import Base, engine, SessionLocal
from app.models import Dispatcher
from app.security import hash_password

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    if len(args.password) < 12:
        raise SystemExit("Пароль должен содержать не менее 12 символов")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Dispatcher).filter_by(username=args.username).first():
            raise SystemExit("Такой диспетчер уже существует")
        db.add(Dispatcher(username=args.username, password_hash=hash_password(args.password), role="admin"))
        db.commit()
        print("Учётная запись диспетчера создана.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
