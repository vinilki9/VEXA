
import httpx

from app.config import settings


class ProviderError(Exception):
    pass


class ProviderRejected(ProviderError):
    """Провайдер явно отклонил запрос до создания сессии."""


TIMEOUT = 12.0


def _json_response(response: httpx.Response) -> dict:
    try:
        data = response.json()
    except ValueError as exc:
        raise ProviderError("Некорректный ответ SMS-провайдера") from exc

    if not isinstance(data, dict):
        raise ProviderError("Неожиданный формат ответа SMS-провайдера")

    return data


def sms_aero_send(phone: str, callback_url: str) -> str:
    if not settings.sms_aero_email or not settings.sms_aero_api_key:
        raise ProviderRejected("SMS Aero не настроен")

    response = httpx.post(
        "https://gate.smsaero.ru/v2/mobile-id/send",
        auth=(
            settings.sms_aero_email,
            settings.sms_aero_api_key,
        ),
        json={
            "number": phone,
            "sign": settings.sms_aero_sign,
            "callbackUrl": callback_url,
        },
        timeout=TIMEOUT,
    )

    if response.status_code >= 500:
        raise ProviderError("SMS Aero временно недоступен")

    if response.status_code >= 400:
        raise ProviderRejected("SMS Aero отклонил запрос")

    data = _json_response(response)

    if data.get("success") is not True:
        raise ProviderRejected(
            str(data.get("message") or "SMS Aero отклонил запрос")
        )

    provider_data = data.get("data") or {}
    provider_id = provider_data.get("id")

    if provider_id is None:
        raise ProviderError("SMS Aero не вернул идентификатор сессии")

    return str(provider_id)


def sms_aero_status(provider_id: str) -> dict:
    response = httpx.post(
        "https://gate.smsaero.ru/v2/mobile-id/status",
        auth=(
            settings.sms_aero_email,
            settings.sms_aero_api_key,
        ),
        json={"id": int(provider_id)},
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    data = _json_response(response)

    if data.get("success") is not True:
        raise ProviderError("Не удалось получить статус SMS Aero")

    return data.get("data") or {}


def sms_aero_verify(provider_id: str, code: str) -> None:
    response = httpx.post(
        "https://gate.smsaero.ru/v2/mobile-id/verify",
        auth=(
            settings.sms_aero_email,
            settings.sms_aero_api_key,
        ),
        json={
            "id": int(provider_id),
            "sign": settings.sms_aero_sign,
            "code": code,
        },
        timeout=TIMEOUT,
    )

    if response.status_code == 400:
        raise ProviderRejected("Неверный код подтверждения")

    if response.status_code == 404:
        raise ProviderRejected("Сессия подтверждения истекла")

    response.raise_for_status()

    data = _json_response(response)

    if data.get("success") is not True:
        raise ProviderRejected("SMS Aero не подтвердил код")


def smsgold_send(
    phone: str,
    status_callback_url: str,
    sms_callback_url: str,
) -> str:
    if not settings.smsgold_user or not settings.smsgold_pass:
        raise ProviderRejected("SMSGold не настроен")

    response = httpx.post(
        "https://webapi.smsgold.ru/v1/push/send",
        json={
            "auth": {
                "user": settings.smsgold_user,
                "pass": settings.smsgold_pass,
            },
            "number": phone,
            "statusCallbackUrl": status_callback_url,
            "smsCodeRequestUrl": sms_callback_url,
        },
        timeout=TIMEOUT,
    )

    if response.status_code >= 500:
        raise ProviderError("SMSGold временно недоступен")

    if response.status_code >= 400:
        raise ProviderRejected("SMSGold отклонил запрос")

    data = _json_response(response)

    if data.get("status") != "success" or not data.get("pushId"):
        raise ProviderRejected(
            "SMSGold не создал сессию авторизации"
        )

    return str(data["pushId"])


def smsgold_status(provider_id: str) -> dict:
    response = httpx.get(
        "https://webapi.smsgold.ru/v1/push/status",
        params={
            "user": settings.smsgold_user,
            "pass": settings.smsgold_pass,
            "pushId": provider_id,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    return _json_response(response)


def smsgold_verify(provider_id: str, code: str) -> None:
    response = httpx.post(
        "https://webapi.smsgold.ru/v1/push/verifySmsCode",
        json={
            "auth": {
                "user": settings.smsgold_user,
                "pass": settings.smsgold_pass,
            },
            "pushId": provider_id,
            "code": code,
        },
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    data = _json_response(response)

    if data.get("status") != "success":
        raise ProviderRejected("SMSGold не подтвердил код")
