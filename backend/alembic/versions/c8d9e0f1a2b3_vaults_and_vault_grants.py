"""vaults and vault grants

Revision ID: c8d9e0f1a2b3
Revises: b7e8f9a0b1c2
Create Date: 2026-08-08 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8d9e0f1a2b3"
down_revision: str | Sequence[str] | None = "b7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DELETE FROM vault")

    op.add_column("vault", sa.Column("description", sa.String(length=1000), nullable=True))
    op.add_column("vault", sa.Column("created_by_user_id", sa.UUID(), nullable=False))
    op.add_column(
        "vault",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column("vault", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_vault_name_nonempty", "vault", "length(name) >= 1")
    op.create_unique_constraint("uq_vault_tenant_name", "vault", ["tenant_id", "name"])

    op.create_table(
        "vault_grant",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "vault_id",
            sa.UUID(),
            sa.ForeignKey("vault.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "membership_id",
            sa.UUID(),
            sa.ForeignKey("membership.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permission", sa.String(length=10), nullable=False),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "permission IN ('read','write','admin')",
            name="ck_vault_grant_permission",
        ),
        sa.UniqueConstraint("vault_id", "membership_id", name="uq_vault_grant_vault_membership"),
    )
    op.create_index("ix_vault_grant_tenant_id", "vault_grant", ["tenant_id"])
    op.create_index("ix_vault_grant_vault_id", "vault_grant", ["vault_id"])
    op.create_index("ix_vault_grant_membership_id", "vault_grant", ["membership_id"])

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON vault_grant TO vaultlog_app")


def downgrade() -> None:
    op.drop_index("ix_vault_grant_membership_id", table_name="vault_grant")
    op.drop_index("ix_vault_grant_vault_id", table_name="vault_grant")
    op.drop_index("ix_vault_grant_tenant_id", table_name="vault_grant")
    op.drop_table("vault_grant")

    op.drop_constraint("uq_vault_tenant_name", "vault", type_="unique")
    op.drop_constraint("ck_vault_name_nonempty", "vault", type_="check")
    op.drop_column("vault", "deleted_at")
    op.drop_column("vault", "updated_at")
    op.drop_column("vault", "created_by_user_id")
    op.drop_column("vault", "description")
