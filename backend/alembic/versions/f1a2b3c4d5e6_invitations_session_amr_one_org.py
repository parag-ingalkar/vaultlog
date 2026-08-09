"""invitations, session amr, one org per user

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-08-09 16:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e0f1a2b3c4d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "auth_session",
        sa.Column(
            "amr",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY['pwd']::text[]"),
        ),
    )

    op.create_index(
        "uq_membership_one_user",
        "membership",
        ["user_id"],
        unique=True,
    )

    op.create_table(
        "invitation",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('admin','member','viewer')",
            name="ck_invitation_role",
        ),
    )
    op.create_index("ix_invitation_tenant_id", "invitation", ["tenant_id"])
    op.create_index("ix_invitation_token_hash", "invitation", ["token_hash"], unique=True)
    op.create_index(
        "uq_invitation_pending_tenant_email",
        "invitation",
        ["tenant_id", "email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON invitation TO vaultlog_app")


def downgrade() -> None:
    op.execute("REVOKE ALL ON invitation FROM vaultlog_app")
    op.drop_index("uq_invitation_pending_tenant_email", table_name="invitation")
    op.drop_index("ix_invitation_token_hash", table_name="invitation")
    op.drop_index("ix_invitation_tenant_id", table_name="invitation")
    op.drop_table("invitation")
    op.drop_index("uq_membership_one_user", table_name="membership")
    op.drop_column("auth_session", "amr")
