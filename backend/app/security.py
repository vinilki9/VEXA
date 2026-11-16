
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import (
    DispatcherProfile,
    DriverProfile,
    PassengerProfile,
    User,
)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _create_token(user_id: UUID, token_type: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_minutes
    )

    payload = {
        "sub": str(user_id),
        "exp": expires,
        "token_type": token_type,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=ALGORITHM,
    )


def create_access_token(user_id: UUID) -> str:
    return _create_token(user_id, "dispatcher")


def create_passenger_access_token(user_id: UUID) -> str:
    return _create_token(user_id, "passenger")


def create_driver_access_token(user_id: UUID) -> str:
    return _create_token(user_id, "driver")


def _decode_token(credentials):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется авторизация",
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

        user_id = UUID(payload.get("sub", ""))
        token_type = payload.get("token_type")

        return user_id, token_type

    except (JWTError, ValueError, TypeError):
        raise unauthorized


def get_current_dispatcher(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется авторизация диспетчера",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id, token_type = _decode_token(credentials)

    # None допускается для совместимости со старыми токенами.
    if token_type not in (None, "dispatcher"):
        raise unauthorized

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise unauthorized

    profile = db.get(DispatcherProfile, user_id)

    if profile is None or not profile.is_active:
        raise unauthorized

    return user


def get_current_passenger(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется авторизация пассажира",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id, token_type = _decode_token(credentials)

    if token_type != "passenger":
        raise unauthorized

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise unauthorized

    profile = db.get(PassengerProfile, user_id)

    if profile is None or not profile.is_active:
        raise unauthorized

    return user


def get_current_driver(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется авторизация водителя",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id, token_type = _decode_token(credentials)

    if token_type != "driver":
        raise unauthorized

    user = db.get(User, user_id)

    if user is None or not user.is_active:
        raise unauthorized

    profile = db.get(DriverProfile, user_id)

    if profile is None or not profile.is_active:
        raise unauthorized

    return user
