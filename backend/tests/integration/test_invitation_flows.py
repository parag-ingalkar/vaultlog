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


def _unique_email(prefix: str = "invite") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture(autouse=True)
def _clear_sent_invitations() -> None:
    LoggingEmailSender.sent_invitations.clear()


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


def _extract_invite_token(invite_url: str) -> str:
    query = parse_qs(urlparse(invite_url).query)
    token = query.get("token", [None])[0]
    assert token is not None
    return token


async def test_owner_without_mfa_blocked_from_vaults(
    client: TestClient,
    register_user,
    login_user,
) -> None:
    email = _unique_email("owner-gate")
    await register_user.execute(email, PASSWORD, "Acme")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    assert login_result.pair is not None

    response = client.get(
        "/api/v1/vaults",
        headers={"Authorization": f"Bearer {login_result.pair.access_token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "mfa_enrollment_required"


async def test_invite_accept_and_login_flow(
    client: TestClient,
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
) -> None:
    owner_email = _unique_email("owner")
    member_email = _unique_email("member")
    token = await _register_owner_with_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        owner_email,
    )

    invite_response = client.post(
        "/api/v1/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": member_email, "role": OrgRole.MEMBER.value},
    )
    assert invite_response.status_code == 201
    assert len(LoggingEmailSender.sent_invitations) == 1
    raw_token = _extract_invite_token(LoggingEmailSender.sent_invitations[0]["invite_url"])

    preview = client.get("/api/v1/invitations/preview", params={"token": raw_token})
    assert preview.status_code == 200
    assert preview.json()["organization_name"] == "Acme Corp"

    accept = client.post(
        "/api/v1/invitations/accept",
        json={"token": raw_token, "password": MEMBER_PASSWORD},
    )
    assert accept.status_code == 204

    login_member = await login_user.execute(member_email, MEMBER_PASSWORD, "pytest")
    assert login_member.kind == "tokens"
    assert login_member.pair is not None

    members = client.get(
        "/api/v1/members",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert members.status_code == 200
    emails = {row["email"] for row in members.json()}
    assert member_email in emails


async def test_cannot_accept_invitation_twice(
    client: TestClient,
    register_user,
    login_user,
    start_totp_enrollment,
    confirm_totp_enrollment,
    identity_uow_factory,
) -> None:
    owner_email = _unique_email("owner2")
    member_email = _unique_email("member2")
    token = await _register_owner_with_mfa(
        register_user,
        login_user,
        start_totp_enrollment,
        confirm_totp_enrollment,
        identity_uow_factory,
        owner_email,
    )

    client.post(
        "/api/v1/invitations",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": member_email, "role": OrgRole.MEMBER.value},
    )
    raw_token = _extract_invite_token(LoggingEmailSender.sent_invitations[0]["invite_url"])
    assert (
        client.post(
            "/api/v1/invitations/accept",
            json={"token": raw_token, "password": MEMBER_PASSWORD},
        ).status_code
        == 204
    )

    retry = client.post(
        "/api/v1/invitations/accept",
        json={"token": raw_token, "password": MEMBER_PASSWORD},
    )
    assert retry.status_code == 404
