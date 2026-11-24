
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Branch
from app.organization_models import (
    Organization,
    OrganizationBranch,
    OrganizationCity,
)


def assign_branch_to_organization(
    db: Session,
    organization_id: UUID,
    branch_id: UUID,
) -> OrganizationBranch:
    """
    Привязывает существующий филиал к организации.

    Проверяет:
    - существование организации;
    - существование и активность филиала;
    - наличие активного разрешения организации на город филиала;
    - отсутствие привязки филиала к другой организации.

    Транзакцию фиксирует вызывающий код.
    """

    organization = db.get(Organization, organization_id)

    if organization is None:
        raise ValueError("Организация не найдена")

    branch = db.get(Branch, branch_id)

    if branch is None:
        raise ValueError("Филиал не найден")

    if not branch.is_active:
        raise ValueError("Нельзя привязать неактивный филиал")

    city_access = db.scalar(
        select(OrganizationCity).where(
            OrganizationCity.organization_id == organization_id,
            OrganizationCity.city_id == branch.city_id,
            OrganizationCity.is_active.is_(True),
        )
    )

    if city_access is None:
        raise ValueError(
            "Организации не разрешена работа в городе этого филиала"
        )

    existing_link = db.scalar(
        select(OrganizationBranch).where(
            OrganizationBranch.branch_id == branch_id
        )
    )

    if existing_link is not None:
        if existing_link.organization_id != organization_id:
            raise ValueError(
                "Филиал уже принадлежит другой организации"
            )

        if not existing_link.is_active:
            existing_link.is_active = True

        return existing_link

    link = OrganizationBranch(
        organization_id=organization_id,
        branch_id=branch_id,
        is_active=True,
    )

    db.add(link)
    db.flush()

    return link


def deactivate_organization_branch(
    db: Session,
    organization_id: UUID,
    branch_id: UUID,
) -> OrganizationBranch:
    """
    Отключает филиал от организации без удаления записи и истории.
    """

    link = db.scalar(
        select(OrganizationBranch).where(
            OrganizationBranch.organization_id == organization_id,
            OrganizationBranch.branch_id == branch_id,
        )
    )

    if link is None:
        raise ValueError("Связь филиала с организацией не найдена")

    link.is_active = False
    db.flush()

    return link


def deactivate_organization_city(
    db: Session,
    organization_id: UUID,
    city_id: UUID,
) -> OrganizationCity:
    """
    Отключает город организации.

    Отключение запрещено, если в городе остаётся хотя бы
    один активный филиал этой организации.
    """

    city_access = db.scalar(
        select(OrganizationCity).where(
            OrganizationCity.organization_id == organization_id,
            OrganizationCity.city_id == city_id,
        )
    )

    if city_access is None:
        raise ValueError("Город не привязан к организации")

    active_branch = db.scalar(
        select(OrganizationBranch.id)
        .join(
            Branch,
            Branch.id == OrganizationBranch.branch_id,
        )
        .where(
            OrganizationBranch.organization_id == organization_id,
            OrganizationBranch.is_active.is_(True),
            Branch.city_id == city_id,
            Branch.is_active.is_(True),
        )
        .limit(1)
    )

    if active_branch is not None:
        raise ValueError(
            "Нельзя отключить город: в нём есть активные филиалы организации"
        )

    city_access.is_active = False
    db.flush()

    return city_access
