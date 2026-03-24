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
            <p>Se preferir, pode também copiar e colar este link no navegador:</p>
            <p>{verification_link}</p>
            <p>Este link expira em 24 horas.</p>
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