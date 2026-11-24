from fastapi import HTTPException


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
