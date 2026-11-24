
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Branch, City
from app.organization_models import (
    Organization,
    OrganizationBranch,
    OrganizationCity,
)
from app.organization_access_models import AuditLog
from app.organization_service import (
    assign_branch_to_organization,
    deactivate_organization_branch,
    deactivate_organization_city,
)
from app.platform_admin_auth import get_current_platform_admin


router = APIRouter(
    prefix="/api/v1/platform-admin/organizations",
    tags=["Platform Admin Organizations"],
    dependencies=[Depends(get_current_platform_admin)],
)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=120)


class OrganizationStatusUpdate(BaseModel):
    status: str = Field(
        pattern="^(pending|active|suspended|rejected)$"
    )


def get_organization_or_404(
    db: Session,
    organization_id: UUID,
) -> Organization:
    organization = db.get(Organization, organization_id)

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Организация не найдена",
        )

    return organization


def write_audit_log(
    db: Session,
    actor_user_id: UUID,
    action: str,
    entity_type: str,
    entity_id: str | None,
    organization_id: UUID | None = None,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            organization_id=organization_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_data=before_data,
            after_data=after_data,
        )
    )


@router.get("")
def list_organizations(
    db: Session = Depends(get_db),
    organization_status: str | None = Query(
        default=None,
        alias="status",
        pattern="^(pending|active|suspended|rejected)$",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    query = select(Organization).order_by(
        Organization.created_at.desc()
    )

    if organization_status is not None:
        query = query.where(
            Organization.status == organization_status
        )

    organizations = db.scalars(
        query.limit(limit).offset(offset)
    ).all()

    return {
        "items": [
            {
                "id": str(item.id),
                "name": item.name,
                "slug": item.slug,
                "status": item.status,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            for item in organizations
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    slug = payload.slug.strip().lower()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Название организации не может быть пустым",
        )

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise HTTPException(
            status_code=400,
            detail="Slug должен содержать латинские буквы, цифры и дефисы",
        )

    organization = Organization(
        name=name,
        slug=slug,
        status="pending",
    )

    db.add(organization)

    try:
        db.flush()

        write_audit_log(
            db=db,
            actor_user_id=admin.id,
            action="organization.created",
            entity_type="organization",
            entity_id=str(organization.id),
            organization_id=organization.id,
            after_data={
                "name": organization.name,
                "slug": organization.slug,
                "status": organization.status,
            },
        )

        db.commit()
        db.refresh(organization)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Организация с таким slug уже существует",
        )

    return {
        "id": str(organization.id),
        "name": organization.name,
        "slug": organization.slug,
        "status": organization.status,
    }


@router.get("/{organization_id}")
def get_organization(
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    organization = get_organization_or_404(
        db,
        organization_id,
    )

    city_links = db.scalars(
        select(OrganizationCity).where(
            OrganizationCity.organization_id == organization_id
        )
    ).all()

    branch_links = db.scalars(
        select(OrganizationBranch).where(
            OrganizationBranch.organization_id == organization_id
        )
    ).all()

    return {
        "id": str(organization.id),
        "name": organization.name,
        "slug": organization.slug,
        "status": organization.status,
        "created_at": organization.created_at,
        "updated_at": organization.updated_at,
        "cities": [
            {
                "city_id": str(item.city_id),
                "is_active": item.is_active,
            }
            for item in city_links
        ],
        "branches": [
            {
                "branch_id": str(item.branch_id),
                "is_active": item.is_active,
            }
            for item in branch_links
        ],
    }


@router.patch("/{organization_id}/status")
def update_organization_status(
    organization_id: UUID,
    payload: OrganizationStatusUpdate,
    admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    organization = get_organization_or_404(
        db,
        organization_id,
    )

    old_status = organization.status
    new_status = payload.status

    if old_status == new_status:
        return {
            "id": str(organization.id),
            "status": organization.status,
            "changed": False,
        }

    organization.status = new_status

    write_audit_log(
        db=db,
        actor_user_id=admin.id,
        action="organization.status_changed",
        entity_type="organization",
        entity_id=str(organization.id),
        organization_id=organization.id,
        before_data={"status": old_status},
        after_data={"status": new_status},
    )

    db.commit()
    db.refresh(organization)

    return {
        "id": str(organization.id),
        "status": organization.status,
        "changed": True,
    }


@router.get("/catalog/cities")
def list_platform_cities(
    db: Session = Depends(get_db),
    active_only: bool = True,
):
    query = select(City).order_by(City.name.asc())

    if active_only:
        query = query.where(City.is_active.is_(True))

    cities = db.scalars(query).all()

    return {
        "items": [
            {
                "id": str(city.id),
                "code": city.code,
                "name": city.name,
                "is_active": city.is_active,
            }
            for city in cities
        ]
    }


@router.get("/catalog/branches")
def list_platform_branches(
    organization_id: UUID | None = None,
    city_id: UUID | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    if organization_id is not None:
        get_organization_or_404(db, organization_id)

    query = (
        select(
            Branch,
            City,
            OrganizationBranch,
        )
        .join(
            City,
            City.id == Branch.city_id,
        )
        .outerjoin(
            OrganizationBranch,
            OrganizationBranch.branch_id == Branch.id,
        )
    )

    if city_id is not None:
        query = query.where(Branch.city_id == city_id)

    if active_only:
        query = query.where(Branch.is_active.is_(True))

    if organization_id is not None:
        query = query.where(
            or_(
                OrganizationBranch.id.is_(None),
                OrganizationBranch.organization_id == organization_id,
            )
        )

    query = query.order_by(
        City.name.asc(),
        Branch.name.asc(),
    )

    rows = db.execute(query).all()

    return {
        "items": [
            {
                "id": str(branch.id),
                "branch_id": str(branch.id),
                "branch_name": branch.name,
                "city_id": str(city.id),
                "city_name": city.name,
                "branch_is_active": branch.is_active,
                "organization_id": (
                    str(link.organization_id)
                    if link is not None
                    else None
                ),
                "organization_link_is_active": (
                    link.is_active
                    if link is not None
                    else None
                ),
            }
            for branch, city, link in rows
        ]
    }


@router.post("/{organization_id}/cities/{city_id}")
def assign_city_to_organization(
    organization_id: UUID,
    city_id: UUID,
    admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    organization = get_organization_or_404(
        db,
        organization_id,
    )

    if organization.status in ("suspended", "rejected"):
        raise HTTPException(
            status_code=409,
            detail="Нельзя подключить город к приостановленной или отклонённой организации",
        )

    city = db.get(City, city_id)

    if city is None:
        raise HTTPException(
            status_code=404,
            detail="Город не найден",
        )

    if not city.is_active:
        raise HTTPException(
            status_code=409,
            detail="Нельзя подключить неактивный город",
        )

    city_link = db.scalar(
        select(OrganizationCity).where(
            OrganizationCity.organization_id == organization_id,
            OrganizationCity.city_id == city_id,
        )
    )

    if city_link is None:
        city_link = OrganizationCity(
            organization_id=organization_id,
            city_id=city_id,
            is_active=True,
        )
        db.add(city_link)
        action = "organization.city_assigned"
    else:
        if city_link.is_active:
            return {
                "organization_id": str(organization_id),
                "city_id": str(city_id),
                "is_active": True,
                "changed": False,
            }

        city_link.is_active = True
        action = "organization.city_reactivated"

    write_audit_log(
        db=db,
        actor_user_id=admin.id,
        action=action,
        entity_type="organization_city",
        entity_id=str(city_link.id),
        organization_id=organization_id,
        after_data={
            "city_id": str(city_id),
            "is_active": True,
        },
    )

    db.commit()

    return {
        "organization_id": str(organization_id),
        "city_id": str(city_id),
        "is_active": True,
        "changed": True,
    }


@router.delete("/{organization_id}/cities/{city_id}")
def remove_city_from_organization(
    organization_id: UUID,
    city_id: UUID,
    admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    get_organization_or_404(db, organization_id)

    try:
        city_link = deactivate_organization_city(
            db,
            organization_id,
            city_id,
        )

        write_audit_log(
            db=db,
            actor_user_id=admin.id,
            action="organization.city_deactivated",
            entity_type="organization_city",
            entity_id=str(city_link.id),
            organization_id=organization_id,
            before_data={
                "city_id": str(city_id),
                "is_active": True,
            },
            after_data={
                "city_id": str(city_id),
                "is_active": False,
            },
        )

        db.commit()

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return {
        "organization_id": str(organization_id),
        "city_id": str(city_id),
        "is_active": False,
    }


@router.get("/{organization_id}/branches")
def list_organization_branches(
    organization_id: UUID,
    db: Session = Depends(get_db),
):
    get_organization_or_404(db, organization_id)

    rows = db.execute(
        select(
            OrganizationBranch,
            Branch,
            City,
        )
        .join(
            Branch,
            Branch.id == OrganizationBranch.branch_id,
        )
        .join(
            City,
            City.id == Branch.city_id,
        )
        .where(
            OrganizationBranch.organization_id == organization_id
        )
        .order_by(City.name.asc(), Branch.name.asc())
    ).all()

    return {
        "items": [
            {
                "id": str(link.id),
                "branch_id": str(branch.id),
                "branch_name": branch.name,
                "city_id": str(city.id),
                "city_name": city.name,
                "is_active": link.is_active,
                "branch_is_active": branch.is_active,
            }
            for link, branch, city in rows
        ]
    }


@router.post("/{organization_id}/branches/{branch_id}")
def assign_branch(
    organization_id: UUID,
    branch_id: UUID,
    admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    organization = get_organization_or_404(
        db,
        organization_id,
    )

    if organization.status != "active":
        raise HTTPException(
            status_code=409,
            detail="Филиалы можно подключать только к активной организации",
        )

    try:
        link = assign_branch_to_organization(
            db,
            organization_id,
            branch_id,
        )

        write_audit_log(
            db=db,
            actor_user_id=admin.id,
            action="organization.branch_assigned",
            entity_type="organization_branch",
            entity_id=str(link.id),
            organization_id=organization_id,
            after_data={
                "branch_id": str(branch_id),
                "is_active": True,
            },
        )

        db.commit()
        db.refresh(link)

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return {
        "id": str(link.id),
        "organization_id": str(organization_id),
        "branch_id": str(branch_id),
        "is_active": link.is_active,
    }


@router.delete("/{organization_id}/branches/{branch_id}")
def remove_branch(
    organization_id: UUID,
    branch_id: UUID,
    admin=Depends(get_current_platform_admin),
    db: Session = Depends(get_db),
):
    get_organization_or_404(db, organization_id)

    try:
        link = deactivate_organization_branch(
            db,
            organization_id,
            branch_id,
        )

        write_audit_log(
            db=db,
            actor_user_id=admin.id,
            action="organization.branch_deactivated",
            entity_type="organization_branch",
            entity_id=str(link.id),
            organization_id=organization_id,
            before_data={
                "branch_id": str(branch_id),
                "is_active": True,
            },
            after_data={
                "branch_id": str(branch_id),
                "is_active": False,
            },
        )

        db.commit()

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return {
        "organization_id": str(organization_id),
        "branch_id": str(branch_id),
        "is_active": False,
    }
