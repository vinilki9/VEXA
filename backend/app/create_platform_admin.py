
import argparse
from getpass import getpass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.organization_access_models import PlatformAdmin
from app.security import hash_password


def main():
    parser = argparse.ArgumentParser(
        description="Создание главного администратора платформы VEXA"
    )
    parser.add_argument("--username", required=True)
    args = parser.parse_args()

    username = args.username.strip()

    if not username:
        raise SystemExit("Логин не может быть пустым")

    if len(username) > 80:
        raise SystemExit("Логин не должен превышать 80 символов")

    password = getpass("Введите пароль главного администратора: ")
    password_confirm = getpass("Повторите пароль: ")

    if password != password_confirm:
        raise SystemExit("Пароли не совпадают")

    if len(password) < 12:
        raise SystemExit("Пароль должен содержать не менее 12 символов")

    if len(password.encode("utf-8")) > 72:
        raise SystemExit("Пароль не должен превышать 72 байта в UTF-8")

    db = SessionLocal()

    try:
        existing_user = db.scalar(
            select(User).where(User.username == username)
        )

        if existing_user is not None:
            raise SystemExit(
                "Пользователь с таким логином уже существует. "
                "Создание администратора отменено."
            )

        user = User(
            username=username,
            password_hash=hash_password(password),
            is_active=True,
        )

        db.add(user)
        db.flush()

        platform_admin = PlatformAdmin(
            user_id=user.id,
            created_by_user_id=None,
        )

        db.add(platform_admin)
        db.commit()

        print("Главный администратор VEXA успешно создан.")
        print(f"Логин: {user.username}")
        print(f"ID пользователя: {user.id}")
        print("Пароль не выводится.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
