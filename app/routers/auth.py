from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
    MessageResponse,
)
from app.services.auth_service import (
    register_user,
    login_user,
    get_current_user_from_token,
    refresh_tokens,
)
from app.services.verification_service import verify_email_token
from app.services.password_reset_service import (
    request_password_reset,
    reset_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

bearer_scheme = HTTPBearer()


@router.post("/register", response_model=UserResponse)
def register(data: RegisterRequest):
    try:
        user = register_user(data.email, data.password)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str):
    try:
        user = verify_email_token(token)
        return HTMLResponse(
            content=f"""
            <!doctype html>
            <html lang="pt">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>E-mail verificado - RentScope</title>
                <style>
                  body {{
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background: #eaf1f4;
                    color: #17202a;
                  }}
                  main {{
                    max-width: 420px;
                    margin: 48px auto;
                    padding: 24px;
                  }}
                  .card {{
                    background: white;
                    border-radius: 18px;
                    padding: 22px;
                    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
                  }}
                  h1 {{
                    margin: 0 0 10px;
                    font-size: 24px;
                  }}
                  p {{
                    color: #475569;
                    line-height: 1.45;
                    margin: 0;
                  }}
                  .success {{
                    color: #166534;
                    font-weight: 700;
                    margin-bottom: 10px;
                  }}
                </style>
              </head>
              <body>
                <main>
                  <section class="card">
                    <p class="success">Seu e-mail est&aacute; verificado.</p>
                    <h1>Verifica&ccedil;&atilde;o conclu&iacute;da</h1>
                    <p>O e-mail {user["email"]} foi confirmado e j&aacute; pode iniciar sess&atilde;o no RentScope.</p>
                  </section>
                </main>
              </body>
            </html>
            """
        )
    except ValueError as e:
        return HTMLResponse(
            status_code=400,
            content=f"""
            <!doctype html>
            <html lang="pt">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>Erro de verificacao - RentScope</title>
                <style>
                  body {{
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background: #eaf1f4;
                    color: #17202a;
                  }}
                  main {{
                    max-width: 420px;
                    margin: 48px auto;
                    padding: 24px;
                  }}
                  .card {{
                    background: white;
                    border-radius: 18px;
                    padding: 22px;
                    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
                  }}
                  h1 {{
                    margin: 0 0 10px;
                    font-size: 24px;
                  }}
                  p {{
                    color: #475569;
                    line-height: 1.45;
                    margin: 0;
                  }}
                  .error {{
                    color: #b91c1c;
                    font-weight: 700;
                    margin-bottom: 10px;
                  }}
                </style>
              </head>
              <body>
                <main>
                  <section class="card">
                    <p class="error">Nao foi possivel verificar o e-mail.</p>
                    <h1>Link invalido</h1>
                    <p>{str(e)}</p>
                  </section>
                </main>
              </body>
            </html>
            """
        )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):
    try:
        return login_user(data.email, data.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(data: ForgotPasswordRequest):
    try:
        return request_password_reset(data.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset-password", response_model=MessageResponse)
def reset_password_route(data: ResetPasswordRequest):
    try:
        return reset_password(data.token, data.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(token: str):
    return f"""
    <!doctype html>
    <html lang="pt">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Recuperar senha - RentScope</title>
        <style>
          body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #eaf1f4;
            color: #17202a;
          }}
          main {{
            max-width: 420px;
            margin: 48px auto;
            padding: 24px;
          }}
          .card {{
            background: white;
            border-radius: 18px;
            padding: 22px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
          }}
          h1 {{
            margin: 0 0 8px;
            font-size: 24px;
          }}
          p {{
            color: #475569;
            line-height: 1.45;
          }}
          label {{
            display: block;
            margin: 18px 0 6px;
            font-weight: 700;
          }}
          input {{
            width: 100%;
            box-sizing: border-box;
            border: 1px solid #cbd5e1;
            border-radius: 12px;
            padding: 12px;
            font-size: 16px;
          }}
          button {{
            width: 100%;
            margin-top: 18px;
            border: 0;
            border-radius: 12px;
            padding: 13px;
            background: #00708e;
            color: white;
            font-weight: 700;
            font-size: 15px;
          }}
          #message {{
            margin-top: 14px;
            font-weight: 700;
          }}
        </style>
      </head>
      <body>
        <main>
          <section class="card">
            <h1>Recuperar senha</h1>
            <p>Digite uma nova senha para sua conta RentScope.</p>
            <label for="password">Nova senha</label>
            <input id="password" type="password" minlength="6" autocomplete="new-password" />
            <button onclick="resetPassword()">Atualizar senha</button>
            <p id="message"></p>
          </section>
        </main>
        <script>
          async function resetPassword() {{
            const message = document.getElementById("message");
            const password = document.getElementById("password").value;
            message.textContent = "";

            if (!password || password.length < 6) {{
              message.style.color = "#b91c1c";
              message.textContent = "A senha deve ter pelo menos 6 caracteres.";
              return;
            }}

            const response = await fetch("/auth/reset-password", {{
              method: "POST",
              headers: {{ "Content-Type": "application/json" }},
              body: JSON.stringify({{
                token: "{token}",
                new_password: password
              }})
            }});

            const data = await response.json().catch(() => ({{ detail: "Erro inesperado." }}));

            if (response.ok) {{
              message.style.color = "#166534";
              message.textContent = data.message || "Senha atualizada com sucesso.";
            }} else {{
              message.style.color = "#b91c1c";
              message.textContent = data.detail || "NÃ£o foi possÃ­vel atualizar a senha.";
            }}
          }}
        </script>
      </body>
    </html>
    """


@router.get("/me", response_model=UserResponse)
def me(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        token = credentials.credentials
        return get_current_user_from_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh", response_model=TokenResponse)
def refresh(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        refresh_token = credentials.credentials
        return refresh_tokens(refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

