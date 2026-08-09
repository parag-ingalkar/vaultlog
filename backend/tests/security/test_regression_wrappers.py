from __future__ import annotations

import pytest
from tests.integration.test_auth_flows import test_refresh_reuse_revokes_session_family
from tests.integration.test_tenant_isolation import test_tenant_b_sees_no_vaults
from tests.unit.test_audit_service import test_verify_chain_detects_content_tamper
from tests.unit.test_tokens import test_tampered_token_rejected
from tests.unit.test_vault_crypto import test_tampered_ciphertext_fails


@pytest.mark.asyncio
async def test_security_auth_refresh_reuse(register_user, login_user, refresh_tokens) -> None:
    await test_refresh_reuse_revokes_session_family(register_user, login_user, refresh_tokens)


@pytest.mark.asyncio
async def test_security_tenant_isolation(scoped_session) -> None:
    await test_tenant_b_sees_no_vaults(scoped_session)


def test_security_jwt_tamper_rejected(token_service) -> None:
    test_tampered_token_rejected(token_service)


def test_security_crypto_tamper_rejected() -> None:
    test_tampered_ciphertext_fails()


def test_security_audit_chain_tamper_detected() -> None:
    test_verify_chain_detects_content_tamper()
