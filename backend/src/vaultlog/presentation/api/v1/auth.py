from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from vaultlog.application.identity.use_cases import (
    CompleteMfaLogin,
    ConfirmTotpEnrollment,
    DisableMfa,
    LoginUser,
    LogoutSession,
    RefreshTokens,
    RegisterUser,
    StartTotpEnrollment,
    StepUpVerify,
)
from vaultlog.domain.identity.exceptions import AuthenticationError
from vaultlog.domain.identity.models import TokenPair
from vaultlog.domain.identity.rate_limits import (
    LOGIN_IP_CAPACITY,
    LOGIN_IP_WINDOW_SECONDS,
    MFA_ENROLL_CAPACITY,
    MFA_ENROLL_WINDOW_SECONDS,
    REFRESH_IP_CAPACITY,
    REFRESH_IP_WINDOW_SECONDS,
    REGISTER_IP_CAPACITY,
    REGISTER_IP_WINDOW_SECONDS,
    STEP_UP_CAPACITY,
    STEP_UP_WINDOW_SECONDS,
)
from vaultlog.presentation.dependencies import (
    Principal,
    StepUpPurpose,
    current_user,
    get_complete_mfa_login,
    get_confirm_totp_enrollment,
    get_disable_mfa,
    get_login_user,
    get_logout_session,
    get_refresh_tokens,
    get_register_user,
    get_start_totp_enrollment,
    get_step_up_verify,
    rate_limit,
    require_step_up,
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


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    challenge_token: str


class RegisterResponse(BaseModel):
    user_id: str


class EnrollmentResponse(BaseModel):
    provisioning_uri: str


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class MfaVerifyRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=6, max_length=20)


class StepUpRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)
    purpose: StepUpPurpose


class StepUpResponse(BaseModel):
    step_up_token: str
    expires_in: int


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
    dependencies=[
        Depends(
            rate_limit(
                "register",
                capacity=REGISTER_IP_CAPACITY,
                window_seconds=REGISTER_IP_WINDOW_SECONDS,
                fail_closed=True,
            )
        )
    ],
)
async def register(
    body: RegisterRequest,
    use_case: RegisterUser = Depends(get_register_user),
) -> RegisterResponse:
    user_id = await use_case.execute(body.email, body.password, body.organization_name)
    return RegisterResponse(user_id=str(user_id))


@router.post(
    "/login",
    response_model=AccessTokenResponse | MfaRequiredResponse,
    dependencies=[
        Depends(
            rate_limit(
                "login",
                capacity=LOGIN_IP_CAPACITY,
                window_seconds=LOGIN_IP_WINDOW_SECONDS,
                fail_closed=True,
            )
        )
    ],
)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    use_case: LoginUser = Depends(get_login_user),
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse | MfaRequiredResponse:
    result = await use_case.execute(
        body.email,
        body.password,
        request.headers.get("user-agent"),
    )
    if result.kind == "mfa_required":
        assert result.challenge_token is not None
        return MfaRequiredResponse(challenge_token=result.challenge_token)

    assert result.pair is not None
    _set_refresh_cookie(response, result.pair, secure=settings.refresh_cookie_secure)
    return AccessTokenResponse(
        access_token=result.pair.access_token,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    dependencies=[
        Depends(
            rate_limit(
                "refresh",
                capacity=REFRESH_IP_CAPACITY,
                window_seconds=REFRESH_IP_WINDOW_SECONDS,
                fail_closed=False,
            )
        )
    ],
)
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


@router.post(
    "/mfa/enroll",
    response_model=EnrollmentResponse,
    dependencies=[
        Depends(
            rate_limit(
                "mfa-enroll",
                capacity=MFA_ENROLL_CAPACITY,
                window_seconds=MFA_ENROLL_WINDOW_SECONDS,
                fail_closed=True,
                by="user",
            )
        )
    ],
)
async def mfa_enroll(
    user_ctx: tuple[Principal, str] = Depends(current_user),
    use_case: StartTotpEnrollment = Depends(get_start_totp_enrollment),
) -> EnrollmentResponse:
    principal, email = user_ctx
    result = await use_case.execute(principal.user_id, email)
    return EnrollmentResponse(provisioning_uri=result.provisioning_uri)


@router.post("/mfa/confirm", response_model=RecoveryCodesResponse)
async def mfa_confirm(
    code: str = Body(embed=True, min_length=6, max_length=8),
    user_ctx: tuple[Principal, str] = Depends(current_user),
    use_case: ConfirmTotpEnrollment = Depends(get_confirm_totp_enrollment),
) -> RecoveryCodesResponse:
    principal, _ = user_ctx
    codes = await use_case.execute(principal.user_id, code)
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/mfa/verify", response_model=AccessTokenResponse)
async def mfa_verify(
    body: MfaVerifyRequest,
    request: Request,
    response: Response,
    use_case: CompleteMfaLogin = Depends(get_complete_mfa_login),
    settings: Settings = Depends(get_settings),
) -> AccessTokenResponse:
    pair = await use_case.execute(
        body.challenge_token,
        body.code,
        request.headers.get("user-agent"),
    )
    _set_refresh_cookie(response, pair, secure=settings.refresh_cookie_secure)
    return AccessTokenResponse(
        access_token=pair.access_token,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post(
    "/step-up/verify",
    response_model=StepUpResponse,
    dependencies=[
        Depends(
            rate_limit(
                "step-up",
                capacity=STEP_UP_CAPACITY,
                window_seconds=STEP_UP_WINDOW_SECONDS,
                fail_closed=True,
                by="user",
            )
        )
    ],
)
async def step_up_verify(
    body: StepUpRequest,
    user_ctx: tuple[Principal, str] = Depends(current_user),
    use_case: StepUpVerify = Depends(get_step_up_verify),
    settings: Settings = Depends(get_settings),
) -> StepUpResponse:
    principal, _ = user_ctx
    token = await use_case.execute(
        principal.user_id,
        principal.session_id,
        body.code,
        body.purpose.value,
    )
    return StepUpResponse(
        step_up_token=token,
        expires_in=settings.step_up_token_ttl_seconds,
    )


@router.delete("/mfa", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_disable(
    principal: Principal = Depends(require_step_up(StepUpPurpose.MANAGE_MFA)),
    use_case: DisableMfa = Depends(get_disable_mfa),
) -> None:
    await use_case.execute(principal.user_id)
