from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

REDACTED_KEYS = frozenset(
    {
        "password",
        "value",
        "plaintext",
        "token",
        "refresh_token",
        "access_token",
        "step_up_token",
        "challenge_token",
        "code",
        "totp",
        "seed",
        "dek",
        "kek",
        "secret",
        "authorization",
        "cookie",
        "set-cookie",
    }
)


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            key: "[REDACTED]" if str(key).lower() in REDACTED_KEYS else _scrub(value)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub(item) for item in obj]
    return obj


def redact_processor(
    _logger: logging.Logger,
    _method: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    scrubbed = _scrub(dict(event_dict))
    if isinstance(scrubbed, dict):
        return scrubbed
    return event_dict


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=log_level.upper(),
        stream=sys.stdout,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level.upper()),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
