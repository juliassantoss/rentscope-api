from datetime import datetime, timedelta, timezone
import jwt
from app.settings import settings


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm
    )


def create_refresh_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "refresh",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm]
    )