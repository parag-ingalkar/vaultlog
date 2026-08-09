from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import pyotp
import pytest
from starlette.testclient import TestClient

from vaultlog.domain.access.models import OrgRole
from vaultlog.infrastructure.email.logging_sender import LoggingEmailSender
from vaultlog.infrastructure.security.seed_encryption import AesGcmSeedEncryptor
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.shared.config import get_settings

PASSWORD = "correct horse battery"
MEMBER_PASSWORD = "member horse battery"
settings = get_settings()


def _unique_email(prefix: str = "me") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture(autouse=True)
def _clear_sent_invitations() -> None:
    LoggingEmailSender.sent_invitations.clear()


def _extract_invite_token(invite_url: str) -> str:
    query = parse_qs(urlparse(invite_url).query)
    token = query.get("token", [None])[0]
    assert token is not None
    return token


async def _register_owner_with_mfa(
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
    email: str,
) -> str:
    await register_user.execute(email, PASSWORD, "Acme Corp")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    assert login_result.pair is not None
    claims = TokenService(settings).verify_access_token(login_result.pair.access_token)
    await start_totp_enrollment.execute(claims.user_id, email)
    async with identity_uow_factory() as uow:
        from sqlalchemy import select

        from vaultlog.infrastructure.database.identity_models import TotpSecretModel

        secret_row = await uow.session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == claims.user_id)
        )
        assert secret_row is not None
        seed = AesGcmSeedEncryptor(settings).decrypt(
            claims.user_id, secret_row.seed_nonce, secret_row.encrypted_seed
        )
    await confirm_totp_enrollment.execute(claims.user_id, pyotp.TOTP(seed).now())
    return login_result.pair.access_token


async def test_owner_me_requires_mfa_enrollment_before_confirm(
    client: TestClient,
    register_user,
    login_user,
) -> None:
    email = _unique_email("owner-pre-mfa")
    await register_user.execute(email, PASSWORD, "Acme Corp")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    assert login_result.pair is not None

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_result.pair.access_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email
    assert body["role"] == "owner"
    assert body["mfa_enabled"] is False
    assert body["mfa_enrollment_required"] is True
    assert body["capabilities"]["can_create_vaults"] is True


async def test_owner_me_after_mfa_enrollment(
    client: TestClient,
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
) -> None:
    email = _unique_email("owner-post-mfa")
    token = await _register_owner_with_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        email,
    )

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mfa_enabled"] is True
    assert body["mfa_enrollment_required"] is False


async def test_invited_member_me_has_no_mfa_enrollment_gate(
    client: TestClient,
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
) -> None:
    owner_email = _unique_email("owner-invite")
    member_email = _unique_email("member-invite")
    owner_token = await _register_owner_with_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        owner_email,
    )

    invite_response = client.post(
        "/api/v1/invitations",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"email": member_email, "role": OrgRole.MEMBER.value},
    )
    assert invite_response.status_code == 201
    raw_token = _extract_invite_token(LoggingEmailSender.sent_invitations[0]["invite_url"])
    accept = client.post(
        "/api/v1/invitations/accept",
        json={"token": raw_token, "password": MEMBER_PASSWORD},
    )
    assert accept.status_code == 204

    login_member = await login_user.execute(member_email, MEMBER_PASSWORD, "pytest")
    assert login_member.pair is not None

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_member.pair.access_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == member_email
    assert body["role"] == "member"
    assert body["mfa_enrollment_required"] is False
    assert body["capabilities"]["can_create_vaults"] is False
