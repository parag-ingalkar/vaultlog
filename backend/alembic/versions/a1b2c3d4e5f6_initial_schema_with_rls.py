"""initial schema with rls

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-07 19:45:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "vault",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vault_tenant_id", "vault", ["tenant_id"])

    op.execute("GRANT USAGE ON SCHEMA public TO vaultlog_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON organization, vault TO vaultlog_app")

    op.execute("ALTER TABLE organization ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON organization
        USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """
    )

    op.execute("ALTER TABLE vault ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE vault FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON vault
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON vault")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organization")
    op.drop_index("ix_vault_tenant_id", table_name="vault")
    op.drop_table("vault")
    op.drop_table("organization")
