from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt

from vaultlog.domain.identity.exceptions import TokenValidationError
from vaultlog.domain.identity.models import AccessTokenClaims
from vaultlog.shared.config import Settings


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._private_key = Path(settings.jwt_private_key_pem_path).read_text()
        self._public_key = Path(settings.jwt_public_key_pem_path).read_text()

    def mint_access_token(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        amr: tuple[str, ...] = ("pwd",),
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "sub": str(user_id),
            "tid": str(tenant_id),
            "sid": str(session_id),
            "amr": list(amr),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(
                (now + timedelta(seconds=self._settings.access_token_ttl_seconds)).timestamp()
            ),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def verify_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=["RS256"],
                issuer=self._settings.jwt_issuer,
                audience=self._settings.jwt_audience,
                options={"require": ["exp", "iat", "sub", "tid", "sid", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenValidationError("Invalid token") from exc

        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tid"]),
            session_id=uuid.UUID(payload["sid"]),
            amr=tuple(payload.get("amr", [])),
        )

    def mint_challenge_token(self, user_id: uuid.UUID) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "sub": str(user_id),
            "purpose": "mfa-challenge",
            "amr": ["pwd"],
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(seconds=self._settings.challenge_token_ttl_seconds)).timestamp()
            ),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def verify_challenge_token(self, token: str) -> uuid.UUID:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=["RS256"],
                issuer=self._settings.jwt_issuer,
                audience=self._settings.jwt_audience,
                options={"require": ["exp", "sub", "purpose"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenValidationError("Invalid token") from exc
        if payload.get("purpose") != "mfa-challenge":
            raise TokenValidationError("Invalid token")
        return uuid.UUID(payload["sub"])

    def mint_step_up_token(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        purpose: str,
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": self._settings.jwt_issuer,
            "aud": self._settings.jwt_audience,
            "sub": str(user_id),
            "sid": str(session_id),
            "purpose": purpose,
            "iat": int(now.timestamp()),
            "exp": int(
                (now + timedelta(seconds=self._settings.step_up_token_ttl_seconds)).timestamp()
            ),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def verify_step_up_token(
        self,
        token: str,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        purpose: str,
    ) -> None:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=["RS256"],
                issuer=self._settings.jwt_issuer,
                audience=self._settings.jwt_audience,
                options={"require": ["exp", "sub", "sid", "purpose"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenValidationError("Invalid token") from exc
        if (
            uuid.UUID(payload["sub"]) != user_id
            or uuid.UUID(payload["sid"]) != session_id
            or payload.get("purpose") != purpose
        ):
            raise TokenValidationError("Invalid token")

    @staticmethod
    def generate_refresh_token() -> str:
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_refresh_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @staticmethod
    def constant_time_equals(a: str, b: str) -> bool:
        return hmac.compare_digest(a, b)
