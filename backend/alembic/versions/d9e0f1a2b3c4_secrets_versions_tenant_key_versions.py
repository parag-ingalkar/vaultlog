"""secrets, versions, tenant key versions

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-08-09 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e0f1a2b3c4"
down_revision: str | Sequence[str] | None = "c8d9e0f1a2b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_key_version",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=False),
        sa.Column("wrap_nonce", sa.LargeBinary(), nullable=False),
        sa.Column("wrapping_key_id", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active','retired')", name="ck_tkv_status"),
        sa.UniqueConstraint("tenant_id", "version", name="uq_tenant_key_version"),
    )
    op.create_index("ix_tenant_key_version_tenant_id", "tenant_key_version", ["tenant_id"])
    op.create_index(
        "uq_tenant_key_one_active",
        "tenant_key_version",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "secret",
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
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("vault_id", "name", name="uq_secret_vault_name"),
    )
    op.create_index("ix_secret_tenant_id", "secret", ["tenant_id"])
    op.create_index("ix_secret_vault_id", "secret", ["vault_id"])

    op.create_table(
        "secret_version",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("organization.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "secret_id",
            sa.UUID(),
            sa.ForeignKey("secret.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("dek_version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("secret_id", "version", name="uq_secret_version"),
    )
    op.create_index("ix_secret_version_tenant_id", "secret_version", ["tenant_id"])
    op.create_index("ix_secret_version_secret_id", "secret_version", ["secret_id"])

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON secret, tenant_key_version TO vaultlog_app")
    op.execute("GRANT SELECT, INSERT ON secret_version TO vaultlog_app")


def downgrade() -> None:
    op.drop_index("ix_secret_version_secret_id", table_name="secret_version")
    op.drop_index("ix_secret_version_tenant_id", table_name="secret_version")
    op.drop_table("secret_version")

    op.drop_index("ix_secret_vault_id", table_name="secret")
    op.drop_index("ix_secret_tenant_id", table_name="secret")
    op.drop_table("secret")

    op.drop_index("uq_tenant_key_one_active", table_name="tenant_key_version")
    op.drop_index("ix_tenant_key_version_tenant_id", table_name="tenant_key_version")
    op.drop_table("tenant_key_version")
