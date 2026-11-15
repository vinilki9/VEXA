
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_models import PassengerAuthSession
from app.auth_providers import (
    ProviderError,
    ProviderRejected,
    sms_aero_send,
    sms_aero_status,
    sms_aero_verify,
    smsgold_send,
    smsgold_status,
    smsgold_verify,
)
from app.config import settings
from app.database import get_db
from app.models import PassengerProfile, User
from app.security import create_passenger_access_token


router = APIRouter(
    prefix="/api/v1/auth/passenger",
    tags=["Passenger authentication"],
)


class PhoneRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=30)


class CodeRequest(BaseModel):
    session_id: UUID
    code: str = Field(min_length=4, max_length=8)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())

    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]

    if len(digits) != 11 or not digits.startswith("7"):
        raise HTTPException(
            status_code=422,
            detail="Укажите корректный российский номер телефона",
        )

    return digits


def callback_url(path: str) -> str:
    secret = settings.sms_auth_callback_secret.strip()

    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="SMS callback secret не настроен",
        )

    base = settings.public_api_base_url.rstrip("/")

    return f"{base}/api/v1/auth/passenger/callback/{secret}/{path}"


def get_session(
    db: Session,
    session_id: UUID,
) -> PassengerAuthSession:
    session = db.get(PassengerAuthSession, session_id)

    if session is None:
        raise HTTPException(404, "Сессия авторизации не найдена")

    if session.status in {"verified", "failed", "expired"}:
        return session

    expires_at = session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now_utc():
        session.status = "expired"
        db.commit()

        raise HTTPException(410, "Срок авторизации истёк")

    return session


def create_or_get_passenger(
    db: Session,
    phone: str,
) -> User:
    user = db.scalar(
        select(User).where(User.phone == phone)
    )

    if user is not None:
        if not user.is_active:
            raise HTTPException(
                403,
                "Учётная запись заблокирована",
            )

        profile = db.get(PassengerProfile, user.id)

        if profile is None:
            db.add(
                PassengerProfile(
                    user_id=user.id,
                    is_active=True,
                )
            )
            db.flush()

        elif not profile.is_active:
            raise HTTPException(
                403,
                "Профиль пассажира заблокирован",
            )

        return user

    user = User(
        phone=phone,
        is_active=True,
    )

    db.add(user)
    db.flush()

    db.add(
        PassengerProfile(
            user_id=user.id,
            is_active=True,
        )
    )

    db.flush()

    return user


def complete_authentication(
    db: Session,
    session: PassengerAuthSession,
) -> dict:
    try:
        user = create_or_get_passenger(
            db,
            session.phone,
        )

        session.status = "verified"
        session.verified_at = now_utc()
        session.updated_at = now_utc()

        db.commit()
        db.refresh(user)

    except IntegrityError:
        db.rollback()

        user = db.scalar(
            select(User).where(
                User.phone == session.phone
            )
        )

        if user is None or not user.is_active:
            raise HTTPException(
                409,
                "Не удалось создать профиль пассажира",
            )

        profile = db.get(PassengerProfile, user.id)

        if profile is None or not profile.is_active:
            raise HTTPException(
                403,
                "Профиль пассажира недоступен",
            )

        session = db.get(
            PassengerAuthSession,
            session.id,
        )

        session.status = "verified"
        session.verified_at = now_utc()
        db.commit()

    return {
        "status": "verified",
        "access_token": create_passenger_access_token(user.id),
        "token_type": "bearer",
    }


def refresh_provider_status(
    db: Session,
    session: PassengerAuthSession,
) -> dict:
    try:
        if session.provider == "sms_aero":
            result = sms_aero_status(
                session.provider_session_id
            )

            provider_status = str(
                result.get("status", "")
            )

            session.provider_status = provider_status

            if provider_status == "1":
                db.commit()
                return complete_authentication(db, session)

            if provider_status in {"2", "16"}:
                session.status = "failed"
                db.commit()

                return {"status": "failed"}

            if provider_status == "3":
                session.status = "otp_required"

            else:
                session.status = "pending"

        elif session.provider == "smsgold":
            result = smsgold_status(
                session.provider_session_id
            )

            provider_status = str(
                result.get("pushStatus", "")
            )

            session.provider_status = provider_status

            if provider_status == "CLIENT_ACCEPTED":
                db.commit()
                return complete_authentication(db, session)

            if provider_status == "SMS_CODE_REQUESTED":
                session.status = "otp_required"
            else:
                # Неизвестные статусы не считаются успехом.
                session.status = "pending"

        else:
            raise HTTPException(
                500,
                "Неизвестный SMS-провайдер",
            )

        session.updated_at = now_utc()
        db.commit()

        return {
            "status": session.status,
            "provider": session.provider,
        }

    except ProviderError:
        db.rollback()

        raise HTTPException(
            502,
            "Не удалось получить статус SMS-провайдера",
        )


@router.post("/request")
def request_authentication(
    payload: PhoneRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    phone = normalize_phone(payload.phone)

    since = now_utc() - timedelta(hours=1)

    requests_count = db.scalar(
        select(func.count())
        .select_from(PassengerAuthSession)
        .where(
            PassengerAuthSession.phone == phone,
            PassengerAuthSession.created_at >= since,
        )
    ) or 0

    if requests_count >= settings.sms_auth_max_requests_per_hour:
        raise HTTPException(
            429,
            "Превышен лимит запросов. Попробуйте позже",
        )

    provider = settings.sms_auth_primary_provider

    base = settings.public_api_base_url.rstrip("/")

    try:
        if provider == "sms_aero":
            try:
                provider_session_id = sms_aero_send(
                    phone,
                    callback_url("sms-aero"),
                )

            except ProviderRejected:
                # Резервный провайдер включается только при
                # однозначном отказе основного до создания сессии.
                if (
                    not settings.smsgold_user
                    or not settings.smsgold_pass
                ):
                    raise

                provider = "smsgold"

                provider_session_id = smsgold_send(
                    phone,
                    callback_url("smsgold-status"),
                    callback_url("smsgold-sms"),
                )

        else:
            provider_session_id = smsgold_send(
                phone,
                callback_url("smsgold-status"),
                callback_url("smsgold-sms"),
            )

    except ProviderRejected:
        raise HTTPException(
            503,
            "Провайдер отклонил запрос авторизации",
        )

    except ProviderError:
        # При неоднозначной ошибке резервный провайдер
        # не вызывается: первая сессия могла быть создана.
        raise HTTPException(
            502,
            "Временная ошибка SMS-провайдера",
        )

    session = PassengerAuthSession(
        phone=phone,
        provider=provider,
        provider_session_id=provider_session_id,
        status="pending",
        expires_at=now_utc() + timedelta(
            minutes=settings.sms_auth_session_minutes
        ),
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id": str(session.id),
        "status": session.status,
        "provider": session.provider,
        "expires_at": session.expires_at,
    }


@router.get("/sessions/{session_id}")
def get_authentication_status(
    session_id: UUID,
    db: Session = Depends(get_db),
):
    session = get_session(db, session_id)

    if session.status == "verified":
        user = db.scalar(
            select(User).where(
                User.phone == session.phone
            )
        )

        if user is None or not user.is_active:
            raise HTTPException(401, "Профиль недоступен")

        profile = db.get(PassengerProfile, user.id)

        if profile is None or not profile.is_active:
            raise HTTPException(403, "Профиль недоступен")

        return {
            "status": "verified",
            "access_token": create_passenger_access_token(user.id),
            "token_type": "bearer",
        }

    if session.status in {"failed", "expired"}:
        return {"status": session.status}

    return refresh_provider_status(db, session)


@router.post("/verify")
def verify_authentication_code(
    payload: CodeRequest,
    db: Session = Depends(get_db),
):
    session = get_session(db, payload.session_id)

    if session.status == "verified":
        return get_authentication_status(
            session.id,
            db,
        )

    if session.status in {"failed", "expired"}:
        raise HTTPException(
            410,
            "Сессия авторизации недействительна",
        )

    if session.attempts >= settings.sms_auth_max_attempts:
        session.status = "failed"
        db.commit()

        raise HTTPException(
            429,
            "Превышено количество попыток",
        )

    session.attempts += 1
    db.commit()

    try:
        if session.provider == "sms_aero":
            sms_aero_verify(
                session.provider_session_id,
                payload.code,
            )

        elif session.provider == "smsgold":
            smsgold_verify(
                session.provider_session_id,
                payload.code,
            )

        else:
            raise HTTPException(
                500,
                "Неизвестный SMS-провайдер",
            )

    except ProviderRejected:
        raise HTTPException(
            400,
            "Неверный или просроченный код",
        )

    except ProviderError:
        raise HTTPException(
            502,
            "Ошибка проверки кода у провайдера",
        )

    session.status = "checking"
    db.commit()

    # Сам факт успешного ответа verify не выдаёт токен.
    # Окончательный успех подтверждается отдельным status API.
    return {
        "status": "checking",
        "message": "Проверяем подтверждение у провайдера",
    }


@router.post("/callback/{secret}/sms-aero")
async def sms_aero_callback(
    secret: str,
):
    if secret != settings.sms_auth_callback_secret:
        raise HTTPException(404, "Not found")

    # Callback не является доказательством авторизации.
    # Клиент получает итоговый статус через status API.
    return {"accepted": True}


@router.post("/callback/{secret}/smsgold-status")
async def smsgold_status_callback(
    secret: str,
):
    if secret != settings.sms_auth_callback_secret:
        raise HTTPException(404, "Not found")

    return {"accepted": True}


@router.post("/callback/{secret}/smsgold-sms")
async def smsgold_sms_callback(
    secret: str,
):
    if secret != settings.sms_auth_callback_secret:
        raise HTTPException(404, "Not found")

    return {"accepted": True}
