from __future__ import annotations

from typing import ClassVar

import structlog

from vaultlog.domain.access.models import OrgRole

logger = structlog.get_logger()


class LoggingEmailSender:
    """Development/test sender that records invitations in memory."""

    sent_invitations: ClassVar[list[dict[str, str]]] = []

    async def send_invitation(
        self,
        *,
        to: str,
        invite_url: str,
        organization_name: str,
        role: OrgRole,
    ) -> None:
        LoggingEmailSender.sent_invitations.append(
            {
                "to": to,
                "invite_url": invite_url,
                "organization_name": organization_name,
                "role": role.value,
            }
        )
        logger.info(
            "invitation.email",
            to=to,
            organization_name=organization_name,
            role=role.value,
            invite_url=invite_url,
        )
