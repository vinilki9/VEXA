
import argparse
from uuid import UUID

from app.database import SessionLocal
from app.models import Branch, DispatcherProfile, User
from app.security import hash_password


def main():
    parser = argparse.ArgumentParser(
        description="Создание учётной записи диспетчера VEXA"
    )

    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)

    parser.add_argument(
        "--role",
        choices=["dispatcher", "chief_dispatcher"],
        default="dispatcher",
    )

    parser.add_argument(
        "--branch-id",
        type=UUID,
        default=None,
        help="UUID филиала для обычного диспетчера",
    )

    args = parser.parse_args()

    if len(args.password) < 12:
        raise SystemExit(
            "Пароль должен содержать не менее 12 символов"
        )

    if args.role == "dispatcher" and args.branch_id is None:
        raise SystemExit(
            "Для обычного диспетчера необходимо указать --branch-id"
        )

    if args.role == "chief_dispatcher" and args.branch_id is not None:
        raise SystemExit(
            "Главному диспетчеру филиал назначать не нужно"
        )

    db = SessionLocal()

    try:
        existing_user = (
            db.query(User)
            .filter(User.username == args.username)
            .first()
        )

        if existing_user:
            raise SystemExit(
                "Пользователь с таким логином уже существует"
            )

        if args.branch_id is not None:
            branch = db.get(Branch, args.branch_id)

            if branch is None or not branch.is_active:
                raise SystemExit(
                    "Указанный филиал не найден или неактивен"
                )

        user = User(
            username=args.username,
            password_hash=hash_password(args.password),
            is_active=True,
        )

        db.add(user)
        db.flush()

        dispatcher_profile = DispatcherProfile(
            user_id=user.id,
            branch_id=args.branch_id,
            role=args.role,
            is_active=True,
        )

        db.add(dispatcher_profile)
        db.commit()

        print("Учётная запись диспетчера VEXA создана.")
        print(f"Логин: {user.username}")
        print(f"Роль: {args.role}")
        print(f"ID пользователя: {user.id}")
        print(f"ID филиала: {args.branch_id}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
