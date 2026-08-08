from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

RLS_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = RLS_DIR / "template.sql"
POLICIES_DIR = RLS_DIR / "policies"

_TABLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def render_policy(table: str, tenant_column: str = "tenant_id") -> str:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    return template.replace("{{table}}", table).replace("{{tenant_column}}", tenant_column)


def create_policy_file(table: str, tenant_column: str = "tenant_id") -> Path:
    if not _TABLE_NAME_RE.match(table):
        raise ValueError(f"Invalid table name: {table}")

    output = POLICIES_DIR / f"{table}.sql"
    if output.exists():
        raise FileExistsError(f"Policy file already exists: {output}")

    output.write_text(render_policy(table, tenant_column), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an idempotent RLS policy script from template.sql"
    )
    parser.add_argument("table", help="Table name (e.g. vault_grant)")
    parser.add_argument(
        "--column",
        default="tenant_id",
        help="Tenant isolation column (default: tenant_id; use id for organization)",
    )
    args = parser.parse_args()

    try:
        output = create_policy_file(args.table, args.column)
    except (ValueError, FileExistsError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)

    print(f"Created {output}")


if __name__ == "__main__":
    main()
