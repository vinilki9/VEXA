
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Branch, City


CITY_CODE = "obolensk"
CITY_NAME = "Оболенск"
BRANCH_NAME = "Основной филиал"


def main() -> None:
    db = SessionLocal()

    try:
        city = db.scalar(
            select(City).where(City.code == CITY_CODE)
        )

        if city is None:
            city = City(
                code=CITY_CODE,
                name=CITY_NAME,
                is_active=True,
            )
            db.add(city)
            db.flush()

        elif not city.is_active:
            raise RuntimeError(
                "Город Оболенск существует, но неактивен. "
                "Автоматическое включение запрещено."
            )

        active_branches = db.scalars(
            select(Branch).where(
                Branch.city_id == city.id,
                Branch.is_active.is_(True),
            )
        ).all()

        if len(active_branches) > 1:
            raise RuntimeError(
                "В Оболенске уже несколько активных филиалов. "
                "Необходимо проверить их вручную."
            )

        if len(active_branches) == 1:
            branch = active_branches[0]

        else:
            existing_branch = db.scalar(
                select(Branch).where(
                    Branch.city_id == city.id,
                    Branch.name == BRANCH_NAME,
                )
            )

            if existing_branch is not None:
                raise RuntimeError(
                    "Основной филиал существует, но неактивен. "
                    "Автоматическое включение запрещено."
                )

            branch = Branch(
                city_id=city.id,
                name=BRANCH_NAME,
                is_active=True,
            )
            db.add(branch)
            db.flush()

        db.commit()

        print("Начальные данные VEXA подготовлены.")
        print(f"Город: {city.name}")
        print(f"Код города: {city.code}")
        print(f"City ID: {city.id}")
        print(f"Филиал: {branch.name}")
        print(f"Branch ID: {branch.id}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
