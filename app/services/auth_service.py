from psycopg.errors import UniqueViolation

from app.db import get_conn
from app.core.security import hash_password, verify_password
from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.services.verification_service import create_email_verification_token
from app.services.email_service import send_verification_email
from app.settings import settings


def register_user(email: str, password: str):
    password_hash = hash_password(password)

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, is_verified, mfa_enabled)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, email, is_verified
                    """,
                    (email, password_hash, False, False)
                )
                user = cur.fetchone()
                conn.commit()

        token = create_email_verification_token(user["id"])
        verification_link = f"{settings.backend_base_url}/auth/verify-email?token={token}"
        send_verification_email(user["email"], verification_link)

        return user

    except UniqueViolation:
        raise ValueError("Já existe uma conta com este email.")


def login_user(email: str, password: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, is_verified, mfa_enabled
                FROM users
                WHERE email = %s
                """,
                (email,)
            )
            user = cur.fetchone()

    if not user:
        raise ValueError("Email ou password inválidos.")

    if not verify_password(password, user["password_hash"]):
        raise ValueError("Email ou password inválidos.")

    if not user["is_verified"]:
        raise ValueError("Confirma o teu email antes de iniciar sessão.")

    access_token = create_access_token(user["id"], user["email"])
    refresh_token = create_refresh_token(user["id"], user["email"])

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


def get_current_user_from_token(token: str):
    try:
        payload = decode_token(token)
    except Exception:
        raise ValueError("Token inválido ou expirado.")

    if payload.get("type") != "access":
        raise ValueError("Token inválido.")

    user_id = payload.get("sub")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, is_verified
                FROM users
                WHERE id = %s
                """,
                (user_id,)
            )
            user = cur.fetchone()

    if not user:
        raise ValueError("Utilizador não encontrado.")

    return user


def refresh_tokens(refresh_token: str):
    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise ValueError("Refresh token inválido ou expirado.")

    if payload.get("type") != "refresh":
        raise ValueError("Token inválido.")

    user_id = payload.get("sub")
    email = payload.get("email")

    return {
        "access_token": create_access_token(int(user_id), email),
        "refresh_token": create_refresh_token(int(user_id), email),
        "token_type": "bearer"
    }