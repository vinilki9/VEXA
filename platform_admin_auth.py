
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.organization_access_models import PlatformAdmin
from app.security import verify_password


router = APIRouter(
    prefix="/api/v1/platform-admin/auth",
    tags=["Platform Admin Authentication"],
)

bearer = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"


class PlatformAdminLogin(BaseModel):
    username: str
    password: str


class PlatformAdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class PlatformAdminMeResponse(BaseModel):
    id: UUID
    username: str


def create_platform_admin_access_token(user_id: UUID) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_minutes
    )

    payload = {
        "sub": str(user_id),
        "exp": expires,
        "token_type": "platform_admin",
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def get_current_platform_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется авторизация главного администратора",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[ALGORITHM],
        )

        if payload.get("token_type") != "platform_admin":
            raise unauthorized

        user_id = UUID(payload.get("sub", ""))

    except (JWTError, ValueError, TypeError):
        raise unauthorized

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise unauthorized

    admin = db.get(PlatformAdmin, user_id)

    if admin is None:
        raise unauthorized

    return user


@router.post(
    "/login",
    response_model=PlatformAdminTokenResponse,
)
def platform_admin_login(
    payload: PlatformAdminLogin,
    db: Session = Depends(get_db),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Неверный логин или пароль",
    )

    username = payload.username.strip()

    user = db.scalar(
        select(User).where(User.username == username)
    )

    if user is None or not user.is_active:
        raise unauthorized

    if not user.password_hash:
        raise unauthorized

    if not verify_password(
        payload.password,
        user.password_hash,
    ):
        raise unauthorized

    admin = db.get(PlatformAdmin, user.id)

    if admin is None:
        raise unauthorized

    access_token = create_platform_admin_access_token(user.id)

    return PlatformAdminTokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_minutes * 60,
    )


@router.get(
    "/me",
    response_model=PlatformAdminMeResponse,
)
def platform_admin_me(
    user: User = Depends(get_current_platform_admin),
):
    """Verify the platform-admin token and return the logged-in account."""
    return PlatformAdminMeResponse(id=user.id, username=user.username)
