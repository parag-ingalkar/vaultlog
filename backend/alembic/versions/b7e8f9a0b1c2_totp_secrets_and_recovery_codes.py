"""totp secrets and recovery codes

Revision ID: b7e8f9a0b1c2
Revises: 6dc854c15a49
Create Date: 2026-08-08 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "6dc854c15a49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "totp_secret",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("encrypted_seed", sa.LargeBinary(), nullable=False),
        sa.Column("seed_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_totp_secret_user_id"),
    )
    op.create_index("ix_totp_secret_user_id", "totp_secret", ["user_id"])

    op.create_table(
        "recovery_code",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey("app_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("code_hash", name="uq_recovery_code_code_hash"),
    )
    op.create_index("ix_recovery_code_user_id", "recovery_code", ["user_id"])

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON totp_secret, recovery_code TO vaultlog_app")


def downgrade() -> None:
    op.drop_index("ix_recovery_code_user_id", table_name="recovery_code")
    op.drop_table("recovery_code")
    op.drop_index("ix_totp_secret_user_id", table_name="totp_secret")
    op.drop_table("totp_secret")
