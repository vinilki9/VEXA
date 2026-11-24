from datetime import datetime, timedelta, timezone
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
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
from app.legal_documents import validate_acceptances
from app.legal_acceptance_service import record_acceptances
from app.models import PassengerProfile, User
from app.phone_utils import normalize_phone
from app.security import create_passenger_access_token


router = APIRouter(
    prefix="/api/v1/auth/passenger",
    tags=["Passenger authentication"],
)


class PhoneRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=30)
    legal_acceptances: list[dict] = Field(default_factory=list)


class CodeRequest(BaseModel):
    session_id: UUID
    code: str = Field(min_length=4, max_length=8)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def callback_url(path: str) -> str:
    secret = settings.sms_auth_callback_secret.strip()

    if len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="SMS callback secret не настроен",
        )

    base = settings.public_api_base_url.rstrip("/")

    return (
        f"{base}/api/v1/auth/passenger/"
        f"callback/{secret}/{path}"
    )


def get_session(
    db: Session,
    session_id: UUID,
) -> PassengerAuthSession:
    session = db.get(PassengerAuthSession, session_id)

    if session is None:
        raise HTTPException(
            404,
            "Сессия авторизации не найдена",
        )

    expires_at = session.expires_at

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(
            tzinfo=timezone.utc
        )

    # Срок проверяется раньше терминального статуса.
    if expires_at <= now_utc():
        if session.status != "expired":
            session.status = "expired"
            session.updated_at = now_utc()
            db.commit()

        raise HTTPException(
            410,
            "Срок авторизации истёк",
        )

    if session.status == "expired":
        raise HTTPException(
            410,
            "Срок авторизации истёк",
        )

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
    session_id = session.id
    phone = session.phone

    try:
        user = create_or_get_passenger(db, phone)

        # Persist legally significant document revision by verified identity.
        # Draft document catalogue must be formally approved before production.
        record_acceptances(db, user.id, "client", session.legal_acceptances, "verified_sms_session")
        session.status = "verified"
        session.verified_at = now_utc()
        session.updated_at = now_utc()

        db.commit()

    except IntegrityError:
        db.rollback()

        # Повторно читаем записи после отката транзакции.
        user = db.scalar(
            select(User).where(User.phone == phone)
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
            session_id,
        )

        if session is None:
            raise HTTPException(
                404,
                "Сессия авторизации не найдена",
            )

        # Persist legally significant document revision by verified identity.
        # Draft document catalogue must be formally approved before production.
        record_acceptances(db, user.id, "client", session.legal_acceptances, "verified_sms_session")
        record_acceptances(db, user.id, "client", session.legal_acceptances, "verified_sms_session")
        session.status = "verified"
        session.verified_at = now_utc()
        session.updated_at = now_utc()
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
                session.updated_at = now_utc()
                db.commit()

                return {"status": "failed"}

            if provider_status == "3":
                session.status = "otp_required"
            elif provider_status in {"0", "8"}:
                session.status = "pending"
            else:
                # Неизвестный статус не является успехом.
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
            elif provider_status == "AWAITING_CLIENT_ACTION":
                session.status = "pending"
            else:
                # Неизвестные статусы остаются неподтверждёнными.
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

    except (ProviderError, httpx.HTTPError):
        db.rollback()

        raise HTTPException(
            502,
            "Не удалось получить статус SMS-провайдера",
        )


@router.post("/request")
def request_authentication(
    payload: PhoneRequest,
    db: Session = Depends(get_db),
):
    try:
        verified_acceptances = validate_acceptances("client", payload.legal_acceptances)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
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

    try:
        if provider == "sms_aero":
            try:
                provider_session_id = sms_aero_send(
                    phone,
                    callback_url("sms-aero"),
                )

            except ProviderRejected:
                # Только однозначный отказ до создания сессии.
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

    except (ProviderError, httpx.HTTPError):
        # При неоднозначной ошибке резерв не вызывается.
        raise HTTPException(
            502,
            "Временная ошибка SMS-провайдера",
        )

    session = PassengerAuthSession(
        legal_acceptances=verified_acceptances,
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
            raise HTTPException(
                401,
                "Профиль недоступен",
            )

        profile = db.get(PassengerProfile, user.id)

        if profile is None or not profile.is_active:
            raise HTTPException(
                403,
                "Профиль недоступен",
            )

        return {
            "status": "verified",
            "access_token": create_passenger_access_token(user.id),
            "token_type": "bearer",
        }

    if session.status == "failed":
        return {"status": "failed"}

    return refresh_provider_status(db, session)


@router.post("/verify")
def verify_authentication_code(
    payload: CodeRequest,
    db: Session = Depends(get_db),
):
    session = get_session(db, payload.session_id)

    if session.status == "verified":
        return get_authentication_status(
            payload.session_id,
            db,
        )

    if session.status == "failed":
        raise HTTPException(
            410,
            "Сессия авторизации недействительна",
        )

    if session.attempts >= settings.sms_auth_max_attempts:
        session.status = "failed"
        session.updated_at = now_utc()
        db.commit()

        raise HTTPException(
            429,
            "Превышено количество попыток",
        )

    session.attempts += 1
    session.updated_at = now_utc()
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
        if session.attempts >= settings.sms_auth_max_attempts:
            session.status = "failed"
            db.commit()

        raise HTTPException(
            400,
            "Неверный или просроченный код",
        )

    except (ProviderError, httpx.HTTPError):
        raise HTTPException(
            502,
            "Ошибка проверки кода у провайдера",
        )

    session.status = "checking"
    session.updated_at = now_utc()
    db.commit()

    # Ответ verify сам по себе не выдаёт токен.
    # Итог подтверждается отдельным запросом статуса.
    return {
        "status": "checking",
        "message": "Проверяем подтверждение у провайдера",
    }


@router.post("/callback/{secret}/sms-aero")
async def sms_aero_callback(
    secret: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if (
        not settings.sms_auth_callback_secret
        or secret != settings.sms_auth_callback_secret
    ):
        raise HTTPException(404, "Not found")

    try:
        body = await request.json()
    except ValueError:
        return {"accepted": True}

    if not isinstance(body, dict):
        return {"accepted": True}

    provider_id = body.get("id")
    provider_status = body.get("status")
    provider_phone = body.get("number")

    if (
        provider_id is None
        or provider_status is None
        or provider_phone is None
    ):
        return {"accepted": True}

    try:
        phone = normalize_phone(str(provider_phone))
    except HTTPException:
        return {"accepted": True}

    session = db.scalar(
        select(PassengerAuthSession).where(
            PassengerAuthSession.provider == "sms_aero",
            PassengerAuthSession.provider_session_id == str(provider_id),
            PassengerAuthSession.phone == phone,
        )
    )

    if session is not None:
        # Callback только сохраняет диагностический статус.
        # Он никогда самостоятельно не выдаёт токен.
        session.provider_status = str(provider_status)[:80]
        session.updated_at = now_utc()
        db.commit()

    return {"accepted": True}


@router.post("/callback/{secret}/smsgold-status")
async def smsgold_status_callback(secret: str):
    if (
        not settings.sms_auth_callback_secret
        or secret != settings.sms_auth_callback_secret
    ):
        raise HTTPException(404, "Not found")

    # Формат callback SMSGold не предполагаем.
    # Итог проверяется отдельным запросом status API.
    return {"accepted": True}


@router.post("/callback/{secret}/smsgold-sms")
async def smsgold_sms_callback(secret: str):
    if (
        not settings.sms_auth_callback_secret
        or secret != settings.sms_auth_callback_secret
    ):
        raise HTTPException(404, "Not found")

    return {"accepted": True}
