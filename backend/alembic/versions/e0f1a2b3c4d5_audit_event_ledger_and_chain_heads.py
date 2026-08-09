"""audit event ledger and chain heads

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-08-09 14:30:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e0f1a2b3c4d5"
down_revision: str | Sequence[str] | None = "d9e0f1a2b3c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_event",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("organization.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=True),
        sa.Column("outcome", sa.String(length=10), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("previous_hash", sa.LargeBinary(), nullable=True),
        sa.Column("entry_hash", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('success','failure','denied')",
            name="ck_audit_outcome",
        ),
        sa.UniqueConstraint("tenant_id", "sequence", name="uq_audit_tenant_sequence"),
        sa.UniqueConstraint("tenant_id", "entry_hash", name="uq_audit_tenant_entry_hash"),
    )
    op.create_index("ix_audit_event_tenant_id", "audit_event", ["tenant_id"])
    op.create_index(
        "ix_audit_tenant_action_time",
        "audit_event",
        ["tenant_id", "action", "occurred_at"],
    )

    op.create_table(
        "audit_chain_head",
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("organization.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("last_sequence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("last_hash", sa.LargeBinary(), nullable=True),
    )

    op.execute("GRANT SELECT, INSERT ON audit_event TO vaultlog_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON audit_chain_head TO vaultlog_app")


def downgrade() -> None:
    op.drop_table("audit_chain_head")
    op.drop_index("ix_audit_tenant_action_time", table_name="audit_event")
    op.drop_index("ix_audit_event_tenant_id", table_name="audit_event")
    op.drop_table("audit_event")
