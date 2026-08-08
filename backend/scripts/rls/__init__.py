"""Idempotent per-table RLS policy scripts applied after Alembic upgrades."""

from scripts.rls.apply import apply_rls_policies, is_upgrade_revision

__all__ = ["apply_rls_policies", "is_upgrade_revision"]
