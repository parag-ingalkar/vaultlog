from __future__ import annotations

import uuid

import pytest

from vaultlog.domain.identity.exceptions import AuthenticationError
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.shared.config import get_settings

PASSWORD = "correct horse battery"
settings = get_settings()


def _unique_email(prefix: str = "ada") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


async def test_register_then_login_returns_token_pair(register_user, login_user) -> None:
    email = _unique_email()
    await register_user.execute(email, PASSWORD, "Acme")
    result = await login_user.execute(email, PASSWORD, "pytest")
    assert result.kind == "tokens"
    assert result.pair is not None
    pair = result.pair
    assert pair.access_token
    assert pair.refresh_token
    claims = TokenService(settings).verify_access_token(pair.access_token)
    assert claims.user_id
    assert claims.tenant_id
    assert claims.session_id


async def test_wrong_password_gives_same_error_as_unknown_email(
    register_user,
    login_user,
) -> None:
    email = _unique_email()
    await register_user.execute(email, PASSWORD, "Acme")
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await login_user.execute(email, "wrong password!!", None)
    with pytest.raises(AuthenticationError, match="Invalid email or password"):
        await login_user.execute("nobody@example.com", "any password 12", None)


async def test_refresh_rotation_consumes_old_token(
    register_user,
    login_user,
    refresh_tokens,
) -> None:
    email = _unique_email("rotate")
    await register_user.execute(email, PASSWORD, "Acme")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    pair1 = login_result.pair
    assert pair1 is not None
    pair2 = await refresh_tokens.execute(pair1.refresh_token)
    assert pair2.access_token and pair2.refresh_token
    assert pair2.refresh_token != pair1.refresh_token

    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(pair1.refresh_token)


async def test_refresh_reuse_revokes_session_family(
    register_user,
    login_user,
    refresh_tokens,
) -> None:
    email = _unique_email("reuse")
    await register_user.execute(email, PASSWORD, "Acme")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    pair1 = login_result.pair
    assert pair1 is not None
    pair2 = await refresh_tokens.execute(pair1.refresh_token)

    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(pair1.refresh_token)

    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(pair2.refresh_token)


async def test_logout_revokes_session(
    register_user,
    login_user,
    logout_session,
    refresh_tokens,
) -> None:
    email = _unique_email("logout")
    await register_user.execute(email, PASSWORD, "Acme")
    login_result = await login_user.execute(email, PASSWORD, "pytest")
    pair = login_result.pair
    assert pair is not None
    await logout_session.execute(pair.refresh_token)
    with pytest.raises(AuthenticationError):
        await refresh_tokens.execute(pair.refresh_token)
