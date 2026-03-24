from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
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

router = APIRouter(prefix="/auth", tags=["auth"])

bearer_scheme = HTTPBearer()


@router.post("/register", response_model=UserResponse)
def register(data: RegisterRequest):
    try:
        user = register_user(data.email, data.password)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/verify-email", response_model=UserResponse)
def verify_email(token: str):
    try:
        return verify_email_token(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):
    try:
        return login_user(data.email, data.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


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