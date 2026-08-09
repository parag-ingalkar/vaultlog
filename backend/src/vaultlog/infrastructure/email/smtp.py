from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from vaultlog.domain.access.models import OrgRole
from vaultlog.shared.config import Settings


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._user = settings.smtp_user
        self._password = settings.smtp_password
        self._from_addr = settings.smtp_from

    async def send_invitation(
        self,
        *,
        to: str,
        invite_url: str,
        organization_name: str,
        role: OrgRole,
    ) -> None:
        message = EmailMessage()
        message["From"] = self._from_addr
        message["To"] = to
        message["Subject"] = f"You are invited to join {organization_name} on VaultLog"
        message.set_content(
            f"You have been invited to join {organization_name} on VaultLog as {role.value}.\n\n"
            f"Accept your invitation:\n{invite_url}\n\n"
            "This link expires in 7 days."
        )

        await aiosmtplib.send(
            message,
            hostname=self._host,
            port=self._port,
            username=self._user or None,
            password=self._password or None,
            start_tls=self._port == 587,
        )
