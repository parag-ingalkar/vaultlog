from __future__ import annotations

import uuid

import pytest

from vaultlog.domain.identity.exceptions import TokenValidationError
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.shared.config import get_settings


@pytest.fixture()
def token_service() -> TokenService:
    return TokenService(get_settings())


def test_access_token_round_trip(token_service: TokenService) -> None:
    uid, tid, sid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    token = token_service.mint_access_token(uid, tid, sid)
    claims = token_service.verify_access_token(token)
    assert (claims.user_id, claims.tenant_id, claims.session_id) == (uid, tid, sid)
    assert claims.amr == ("pwd",)


def test_tampered_token_rejected(token_service: TokenService) -> None:
    token = token_service.mint_access_token(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    with pytest.raises(TokenValidationError):
        token_service.verify_access_token(token + "tampered")


def test_refresh_hash_is_stable_and_not_raw() -> None:
    raw = TokenService.generate_refresh_token()
    assert TokenService.hash_refresh_token(raw) == TokenService.hash_refresh_token(raw)
    assert TokenService.hash_refresh_token(raw) != raw
