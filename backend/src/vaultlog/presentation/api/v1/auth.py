from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from vaultlog.application.identity.use_cases import (
    LoginUser,
    LogoutSession,
    RefreshTokens,
    RegisterUser,
)
from vaultlog.domain.identity.exceptions import AuthenticationError
from vaultlog.domain.identity.models import TokenPair
from vaultlog.presentation.dependencies import (
    get_login_user,
    get_logout_session,
    get_refresh_tokens,
    get_register_user,
)
from vaultlog.shared.config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "vaultlog_refresh"
COOKIE_PATH = "/api/v1/auth"
COOKIE_MAX_AGE = 30 * 24 * 3600


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    organization_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterResponse(BaseModel):
    user_id: str


def _set_refresh_cookie(
    response: Response,
    pair: TokenPair,
    *,
    secure: bool,
) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response, *, secure: bool) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=COOKIE_PATH,
        secure=secure,
        httponly=True,
        samesite="lax",
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=RegisterResponse,
)
async def register(
    body: RegisterRequest,
    use_case: RegisterUser = Depends(get_register_user),
) -> RegisterResponse:
    user_id = await use_case.execute(body.email, body.password, body.organization_name)
    return RegisterResponse(user_id=str(user_id))


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    use_case: LoginUser = Depends(get_login_user),
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    pair = await use_case.execute(
        body.email,
        body.password,
        request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, pair, secure=settings.refresh_cookie_secure)
    return AccessTokenResponse(
        access_token=pair.access_token,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    use_case: RefreshTokens = Depends(get_refresh_tokens),
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is None:
        raise AuthenticationError("Not authenticated")
    try:
        pair = await use_case.execute(raw)
    except AuthenticationError:
        _clear_refresh_cookie(response, secure=settings.refresh_cookie_secure)
        raise
    _set_refresh_cookie(response, pair, secure=settings.refresh_cookie_secure)
    return AccessTokenResponse(
        access_token=pair.access_token,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    use_case: LogoutSession = Depends(get_logout_session),
    settings: Settings = Depends(get_settings),
) -> None:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is not None:
        await use_case.execute(raw)
    _clear_refresh_cookie(response, secure=settings.refresh_cookie_secure)
