from datetime import datetime, timedelta
from uuid import uuid4

from app.db import get_conn


def create_email_verification_token(user_id: int) -> str:
    token = str(uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=24)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_verification_tokens (user_id, token, expires_at)
                VALUES (%s, %s, %s)
                """,
                (user_id, token, expires_at)
            )
            conn.commit()

    return token


def verify_email_token(token: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, token, expires_at
                FROM email_verification_tokens
                WHERE token = %s
                """,
                (token,)
            )
            token_row = cur.fetchone()

            if not token_row:
                raise ValueError("Token de verificação inválido.")

            if token_row["expires_at"] < datetime.utcnow():
                raise ValueError("Token de verificação expirado.")

            cur.execute(
                """
                UPDATE users
                SET is_verified = TRUE
                WHERE id = %s
                RETURNING id, email, is_verified
                """,
                (token_row["user_id"],)
            )
            user = cur.fetchone()

            cur.execute(
                """
                DELETE FROM email_verification_tokens
                WHERE id = %s
                """,
                (token_row["id"],)
            )

            conn.commit()
            return user