from __future__ import annotations

import uuid

import pyotp
import pytest
from sqlalchemy import func, select

from vaultlog.domain.identity.exceptions import (
    AuthenticationError,
    MfaEnrollmentError,
    MfaVerificationError,
    TokenValidationError,
)
from vaultlog.infrastructure.database.identity_models import (
    AuthSessionModel,
    RecoveryCodeModel,
    TotpSecretModel,
    UserModel,
)
from vaultlog.infrastructure.security.seed_encryption import AesGcmSeedEncryptor
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.presentation.dependencies import StepUpPurpose
from vaultlog.shared.config import get_settings

PASSWORD = "correct horse battery"
settings = get_settings()


def _unique_email(prefix: str = "mfa") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


async def _enroll_and_confirm_mfa(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
    email: str,
) -> tuple[str, list[str]]:
    await register_user.execute(email, PASSWORD, "Acme")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    assert login_result.kind == "tokens"
    assert login_result.pair is not None
    access_token = login_result.pair.access_token
    claims = TokenService(settings).verify_access_token(access_token)

    await start_totp_enrollment.execute(claims.user_id, email)
    async with identity_uow_factory() as uow:
        secret_row = await uow.session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == claims.user_id)
        )
        assert secret_row is not None
        seed = AesGcmSeedEncryptor(settings).decrypt(
            claims.user_id, secret_row.seed_nonce, secret_row.encrypted_seed
        )

    code = pyotp.TOTP(seed).now()
    recovery_codes = await confirm_totp_enrollment.execute(claims.user_id, code)
    return access_token, recovery_codes


async def test_enroll_confirm_enables_mfa(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
) -> None:
    email = _unique_email("enroll")
    await register_user.execute(email, PASSWORD, "Acme")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    claims = TokenService(settings).verify_access_token(login_result.pair.access_token)

    await start_totp_enrollment.execute(claims.user_id, email)
    async with identity_uow_factory() as uow:
        secret_row = await uow.session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == claims.user_id)
        )
        assert secret_row is not None
        seed = AesGcmSeedEncryptor(settings).decrypt(
            claims.user_id, secret_row.seed_nonce, secret_row.encrypted_seed
        )
    codes = await confirm_totp_enrollment.execute(claims.user_id, pyotp.TOTP(seed).now())

    async with identity_uow_factory() as uow:
        user = await uow.session.get(UserModel, claims.user_id)
        assert user is not None
        assert user.mfa_enabled
        count = await uow.session.scalar(
            select(func.count())
            .select_from(RecoveryCodeModel)
            .where(RecoveryCodeModel.user_id == claims.user_id)
        )
        assert count == 10
    assert len(codes) == 10


async def test_confirm_wrong_code_keeps_mfa_disabled(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
) -> None:
    email = _unique_email("badconfirm")
    await register_user.execute(email, PASSWORD, "Acme")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    claims = TokenService(settings).verify_access_token(login_result.pair.access_token)
    await start_totp_enrollment.execute(claims.user_id, email)

    with pytest.raises(MfaEnrollmentError):
        await confirm_totp_enrollment.execute(claims.user_id, "000000")

    async with identity_uow_factory() as uow:
        user = await uow.session.get(UserModel, claims.user_id)
        assert user is not None
        assert not user.mfa_enabled


async def test_mfa_login_returns_challenge_no_session(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
) -> None:
    email = _unique_email("mfalogin")
    await _enroll_and_confirm_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        email,
    )

    result = await login_user.execute(email, PASSWORD, "pytest")
    assert result.kind == "mfa_required"
    assert result.challenge_token is not None
    assert result.pair is None

    async with identity_uow_factory() as uow:
        user = await uow.session.scalar(select(UserModel).where(UserModel.email == email))
        assert user is not None
        session_count = await uow.session.scalar(
            select(func.count())
            .select_from(AuthSessionModel)
            .where(AuthSessionModel.user_id == user.id)
        )
        assert session_count == 1


async def test_complete_mfa_login_with_totp(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    complete_mfa_login,
    identity_uow_factory,
) -> None:
    email = _unique_email("completetotp")
    await _enroll_and_confirm_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        email,
    )

    login_result = await login_user.execute(email, PASSWORD, "pytest")
    assert login_result.challenge_token is not None

    async with identity_uow_factory() as uow:
        user = await uow.session.scalar(select(UserModel).where(UserModel.email == email))
        assert user is not None
        secret_row = await uow.session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == user.id)
        )
        assert secret_row is not None
        seed = AesGcmSeedEncryptor(settings).decrypt(
            user.id, secret_row.seed_nonce, secret_row.encrypted_seed
        )

    pair = await complete_mfa_login.execute(
        login_result.challenge_token,
        pyotp.TOTP(seed).now(),
        "pytest",
    )
    claims = TokenService(settings).verify_access_token(pair.access_token)
    assert "totp" in claims.amr
    assert "pwd" in claims.amr


async def test_complete_mfa_login_wrong_code_fails(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    complete_mfa_login,
    identity_uow_factory,
) -> None:
    email = _unique_email("wrongcode")
    await _enroll_and_confirm_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        email,
    )
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    with pytest.raises(MfaVerificationError):
        await complete_mfa_login.execute(login_result.challenge_token, "000000", "pytest")


async def test_recovery_code_single_use(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    complete_mfa_login,
    identity_uow_factory,
) -> None:
    email = _unique_email("recovery")
    _, recovery_codes = await _enroll_and_confirm_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        email,
    )
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    await complete_mfa_login.execute(login_result.challenge_token, recovery_codes[0], "pytest")
    login_result2 = await login_user.execute(email, PASSWORD, "pytest")
    with pytest.raises(MfaVerificationError):
        await complete_mfa_login.execute(login_result2.challenge_token, recovery_codes[0], "pytest")


async def test_challenge_token_rejected_by_refresh(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    refresh_tokens,
    identity_uow_factory,
) -> None:
    email = _unique_email("challengerefresh")
    await _enroll_and_confirm_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        email,
    )
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(login_result.challenge_token)


async def test_challenge_token_rejected_as_access_token(tokens) -> None:
    user_id = uuid.uuid4()
    challenge = tokens.mint_challenge_token(user_id)
    with pytest.raises(TokenValidationError):
        tokens.verify_access_token(challenge)


async def test_step_up_token_bound_to_purpose(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    step_up_verify,
    identity_uow_factory,
    tokens,
) -> None:
    email = _unique_email("stepup")
    access_token, _ = await _enroll_and_confirm_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        email,
    )
    claims = tokens.verify_access_token(access_token)

    async with identity_uow_factory() as uow:
        secret_row = await uow.session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == claims.user_id)
        )
        assert secret_row is not None
        seed = AesGcmSeedEncryptor(settings).decrypt(
            claims.user_id, secret_row.seed_nonce, secret_row.encrypted_seed
        )

    step_up_token = await step_up_verify.execute(
        claims.user_id,
        claims.session_id,
        pyotp.TOTP(seed).now(),
        StepUpPurpose.MANAGE_MFA.value,
    )
    tokens.verify_step_up_token(
        step_up_token,
        claims.user_id,
        claims.session_id,
        StepUpPurpose.MANAGE_MFA.value,
    )
    with pytest.raises(TokenValidationError):
        tokens.verify_step_up_token(
            step_up_token,
            claims.user_id,
            claims.session_id,
            StepUpPurpose.DELETE_VAULT.value,
        )


async def test_step_up_token_rejected_for_different_session(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    step_up_verify,
    identity_uow_factory,
    tokens,
) -> None:
    email = _unique_email("stepupsession")
    access_token, _ = await _enroll_and_confirm_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        email,
    )
    claims = tokens.verify_access_token(access_token)

    async with identity_uow_factory() as uow:
        secret_row = await uow.session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == claims.user_id)
        )
        assert secret_row is not None
        seed = AesGcmSeedEncryptor(settings).decrypt(
            claims.user_id, secret_row.seed_nonce, secret_row.encrypted_seed
        )

    step_up_token = await step_up_verify.execute(
        claims.user_id,
        claims.session_id,
        pyotp.TOTP(seed).now(),
        StepUpPurpose.MANAGE_MFA.value,
    )
    other_session = uuid.uuid4()
    with pytest.raises(TokenValidationError):
        tokens.verify_step_up_token(
            step_up_token,
            claims.user_id,
            other_session,
            StepUpPurpose.MANAGE_MFA.value,
        )
