from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db import get_conn


def create_email_verification_token(user_id: int) -> str:
    token = str(uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

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
    """
    Verifica um token de email.

    Idempotente: pode ser chamado várias vezes com o mesmo token enquanto este
    estiver válido (até `expires_at`). Cliques múltiplos — feitos pelo
    utilizador ou por scanners de email (Gmail, Outlook, etc.) que pré-acedem
    aos links — continuam a devolver sucesso em vez de "Token inválido".

    O token só é removido depois de expirar (limpeza pode ser feita por um job).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id AS token_id,
                       t.user_id,
                       t.token,
                       t.expires_at,
                       u.id AS user_id_check,
                       u.email,
                       u.is_verified
                FROM email_verification_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token = %s
                """,
                (token,)
            )
            token_row = cur.fetchone()

            if not token_row:
                raise ValueError("Token de verificação inválido.")

            if token_row["expires_at"] < datetime.now(timezone.utc):
                raise ValueError("Token de verificação expirado.")

            # Já verificado: idempotência — devolvemos os dados sem tocar na BD.
            if token_row["is_verified"]:
                return {
                    "id": token_row["user_id"],
                    "email": token_row["email"],
                    "is_verified": True,
                }

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

            # Não apagamos o token aqui de propósito: queremos suportar cliques
            # múltiplos (utilizador + scanners de email) enquanto o token for
            # válido. Tokens expirados podem ser removidos por um job periódico.
            conn.commit()
            return user


def cleanup_expired_email_verification_tokens() -> int:
    """
    Remove tokens de verificação de email que já expiraram.

    Pode ser chamado por um job periódico (ex.: cron, scheduler do Render).
    Devolve o número de tokens removidos.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM email_verification_tokens
                WHERE expires_at < %s
                """,
                (datetime.now(timezone.utc),)
            )
            removed = cur.rowcount
            conn.commit()
            return removed
