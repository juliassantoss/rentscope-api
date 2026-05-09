from datetime import datetime, timedelta
from uuid import uuid4

from app.core.security import hash_password
from app.db import get_conn
from app.services.email_service import send_password_reset_email
from app.settings import settings


GENERIC_RESET_MESSAGE = (
    "Se existir uma conta com este email, enviamos um link de recuperação."
)


def ensure_password_reset_table() -> None:
    """
    Garante que a tabela `password_reset_tokens` existe.

    Importante: `user_id` tem de ser INTEGER (igual a `users.id`).
    Usar BIGINT aqui causa erro de type mismatch no FK e a tabela
    nunca chega a ser criada — o que partia o fluxo de reset de senha.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id BIGSERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token TEXT NOT NULL UNIQUE,
                    expires_at TIMESTAMPTZ NOT NULL,
                    used_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.commit()


def request_password_reset(email: str) -> dict:
    ensure_password_reset_table()

    normalized_email = email.strip().lower()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email
                FROM users
                WHERE email = %s
                """,
                (normalized_email,)
            )
            user = cur.fetchone()

            if not user:
                return {"message": GENERIC_RESET_MESSAGE}

            cur.execute(
                """
                DELETE FROM password_reset_tokens
                WHERE user_id = %s AND used_at IS NULL
                """,
                (user["id"],)
            )

            token = str(uuid4())
            expires_at = datetime.utcnow() + timedelta(hours=1)

            cur.execute(
                """
                INSERT INTO password_reset_tokens (user_id, token, expires_at)
                VALUES (%s, %s, %s)
                """,
                (user["id"], token, expires_at)
            )
            conn.commit()

    reset_link = f"{settings.backend_base_url}/auth/reset-password?token={token}"
    send_password_reset_email(normalized_email, reset_link)

    return {"message": GENERIC_RESET_MESSAGE}


def reset_password(token: str, new_password: str) -> dict:
    ensure_password_reset_table()

    password_hash = hash_password(new_password)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, expires_at, used_at
                FROM password_reset_tokens
                WHERE token = %s
                """,
                (token,)
            )
            token_row = cur.fetchone()

            if not token_row:
                raise ValueError("Token de recuperação inválido.")

            if token_row["used_at"] is not None:
                raise ValueError("Token de recuperação já utilizado.")

            if token_row["expires_at"] < datetime.utcnow():
                raise ValueError("Token de recuperação expirado.")

            cur.execute(
                """
                UPDATE users
                SET password_hash = %s
                WHERE id = %s
                """,
                (password_hash, token_row["user_id"])
            )

            cur.execute(
                """
                UPDATE password_reset_tokens
                SET used_at = NOW()
                WHERE id = %s
                """,
                (token_row["id"],)
            )

            conn.commit()

    return {"message": "Senha atualizada com sucesso."}
