import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.settings import settings


def send_verification_email(email: str, verification_link: str) -> None:
    subject = "Verifique o seu email - RentScope"

    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #222;">
            <h2>Bem-vindo ao RentScope</h2>
            <p>Obrigado por criar a sua conta.</p>
            <p>Para confirmar o seu email, clique no botão abaixo:</p>
            <p>
                <a href="{verification_link}"
                   style="display: inline-block; padding: 12px 20px; background-color: #2F86D6; color: white; text-decoration: none; border-radius: 8px;">
                   Verificar email
                </a>
            </p>
            <p style="font-size: 12px; color: #666;">
                Se o botão não funcionar, copie e cole o seguinte endereço no navegador:<br>
                <span style="word-break: break-all;">{verification_link}</span>
            </p>
            <p style="font-size: 12px; color: #666;">Este link expira em 24 horas.</p>
        </body>
    </html>
    """

    text_body = f"""
Bem-vindo ao RentScope.

Obrigado por criar a sua conta.

Para confirmar o seu email, aceda ao link abaixo:
{verification_link}

Este link expira em 24 horas.
""".strip()

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = email

    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()

        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(
            settings.smtp_from_email,
            [email],
            message.as_string()
        )


def send_password_reset_email(email: str, reset_link: str) -> None:
    subject = "Recuperação de senha - RentScope"

    html_body = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #222;">
            <h2>Recuperação de senha</h2>
            <p>Recebemos um pedido para redefinir a senha da sua conta RentScope.</p>
            <p>Para criar uma nova senha, clique no botão abaixo:</p>
            <p>
                <a href="{reset_link}"
                   style="display: inline-block; padding: 12px 20px; background-color: #2F86D6; color: white; text-decoration: none; border-radius: 8px;">
                   Redefinir senha
                </a>
            </p>
            <p>Se preferir, copie e cole este link no navegador:</p>
            <p>{reset_link}</p>
            <p>Este link expira em 1 hora.</p>
            <p>Se não pediu esta recuperação, pode ignorar este email.</p>
        </body>
    </html>
    """

    text_body = f"""
Recuperação de senha - RentScope

Recebemos um pedido para redefinir a senha da sua conta.

Para criar uma nova senha, aceda ao link abaixo:
{reset_link}

Este link expira em 1 hora.
Se não pediu esta recuperação, pode ignorar este email.
""".strip()

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = email

    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_use_tls:
            server.starttls()

        server.login(settings.smtp_username, settings.smtp_password)
        server.sendmail(
            settings.smtp_from_email,
            [email],
            message.as_string()
        )
