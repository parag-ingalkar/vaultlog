***

# VaultLog Backend
## Chapter 1 — Create a secure FastAPI foundation

**Goal:** Create and run a production-shaped FastAPI application with deliberate project boundaries, typed configuration, health checks, Docker-based local infrastructure, and baseline developer tooling.

**Time budget:** 25–35 minutes.

**What you will not build yet:** database models, JWT authentication, RLS, encryption, secrets, and audit logs. A senior engineer establishes a reliable base before adding security-critical features.

***

## 1. Architecture decisions

VaultLog will use:

| Concern | Choice | Why |
|---|---|---|
| Web framework | FastAPI | Async-first, typed request/response models, OpenAPI docs, dependency injection |
| Runtime | Python 3.13+ | Modern typing and strong security/cryptography ecosystem |
| Package manager | `uv` | Fast dependency installation and reproducible lockfile |
| Database | PostgreSQL 16+ | Row-Level Security, transactions, native UUID support, reliable constraints |
| ORM | SQLAlchemy 2 async | Explicit data access and transaction control |
| Database driver | `asyncpg` | Async PostgreSQL driver |
| Migrations | Alembic | Version-controlled schema and policy changes |
| Validation/config | Pydantic v2 + pydantic-settings | Typed, validated configuration; avoids scattered `os.getenv()` calls |
| Tests | pytest + pytest-asyncio | Fast tests with async support |
| Local infrastructure | Docker Compose | Reproducible PostgreSQL environment |
| Production target | Google Cloud Run | Matches a containerized, stateless FastAPI service |

The application uses clean/hexagonal boundaries:

```text
HTTP request
   |
   v
Presentation (FastAPI routers, request/response DTOs)
   |
   v
Application (use cases, commands, authorization orchestration)
   |
   v
Domain (entities, value objects, rules, ports)
   |
   v
Infrastructure (PostgreSQL, SQLAlchemy, cryptography, external services)
```

**Rule:** dependencies point inward. The domain must not import FastAPI, SQLAlchemy, Pydantic, or environment-specific code.

***

## 2. Prerequisites

Install or confirm the following:

```bash
python --version
docker --version
docker compose version
uv --version
git --version
```

Install `uv` on Fedora if necessary:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart the shell after installation if `uv` is not found.

Create a GitHub repository named `vaultlog`, preferably **private**. Even though the repository will never contain real secrets, a private repository reduces accidental exposure while you learn.

***

## 3. Create the repository

```bash
mkdir vaultlog
cd vaultlog

git init
git branch -M main

uv init --python 3.14
```

This should create a minimal `pyproject.toml` and Python entry point. Replace the generated application files shortly; we want an explicit layout rather than a framework-shaped project.

Create the directories:

```bash
mkdir -p src/vaultlog/{application,domain,infrastructure,presentation/api/v1,shared}
mkdir -p tests/{unit,integration,security}
mkdir -p docs/adr
mkdir -p scripts
touch src/vaultlog/__init__.py
touch src/vaultlog/{application,domain,infrastructure,presentation,shared}/__init__.py
touch src/vaultlog/presentation/api/__init__.py
touch src/vaultlog/presentation/api/v1/__init__.py
```

Your target structure is:

```text
vaultlog/
├── docs/
│   └── adr/
├── scripts/
├── src/
│   └── vaultlog/
│       ├── __init__.py
│       ├── main.py
│       ├── application/
│       ├── domain/
│       ├── infrastructure/
│       ├── presentation/
│       │   └── api/
│       │       └── v1/
│       └── shared/
├── tests/
│   ├── integration/
│   ├── security/
│   └── unit/
├── .env.example
├── .gitignore
├── compose.yaml
├── Dockerfile
├── pyproject.toml
├── README.md
└── uv.lock
```

### Why this structure?

Do **not** organize the entire project by technical category such as `models/`, `schemas/`, `services/`, and `crud/`. That structure works for a small tutorial but becomes hard to reason about when you add organization membership, authorization, encryption, rotation, and audit logging.

For this first chapter, we establish the layer boundaries. In later chapters, we will organize code by **bounded feature** inside these layers, such as `identity`, `organizations`, `vaults`, `secrets`, and `audit`.

***

## 4. Install dependencies

Install runtime dependencies:

```bash
uv add \
  "fastapi[standard]" \
  sqlalchemy \
  asyncpg \
  alembic \
  structlog
```

Install development dependencies:

```bash
uv add --dev \
  pytest \
  pytest-asyncio \
  pytest-cov \
  ruff \
  mypy \
  pre-commit
```

Do **not** install JWT, password hashing, TOTP, or crypto libraries yet. Adding libraries only when their security boundary is designed prevents a project from becoming a collection of packages without a coherent security model.

***

## 5. Configure `pyproject.toml`

Replace `pyproject.toml` with:

```toml
[project]
name = "vaultlog"
version = "0.1.0"
description = "Security-first multi-tenant vault and secret-management SaaS."
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "alembic>=1.16.0",
    "asyncpg>=0.30.0",
    "fastapi>=0.115.0",
    "pydantic-settings>=2.8.0",
    "sqlalchemy>=2.0.0",
    "structlog>=25.0.0",
    "uvicorn[standard]>=0.34.0",
]

[dependency-groups]
dev = [
    "httpx>=0.28.0",
    "mypy>=1.15.0",
    "pre-commit>=4.2.0",
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "ruff>=0.11.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/vaultlog"]

[tool.ruff]
target-version = "py313"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",
    "F",
    "I",
    "UP",
    "B",
    "SIM",
    "RUF",
    "S",
]
ignore = [
    "S101",
]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-ra -q --strict-markers"

[tool.coverage.run]
source = ["vaultlog"]
branch = true

[tool.mypy]
python_version = "3.13"
strict = true
mypy_path = "src"
packages = ["vaultlog"]
```

Then synchronize the environment:

```bash
uv sync
```

### Why strict linting early?

Security bugs often begin as ambiguity: unused branches, silent error handling, weak typing, broad exception catches, or inconsistent imports. Ruff and mypy will not prove VaultLog secure, but they remove avoidable sources of uncertainty before they become security flaws.

***

## 6. Add Git protections

Create `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Virtual environments
.venv/

# Environment files: never commit credentials
.env
.env.*
!.env.example

# Editors and OS
.vscode/
.idea/
.DS_Store

# Build artifacts
dist/
build/
*.egg-info/
```

Create `.env.example`:

```dotenv
# Runtime
ENVIRONMENT=local
DEBUG=true
LOG_LEVEL=INFO

# HTTP
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173

# PostgreSQL
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=vaultlog
DATABASE_USER=vaultlog_app
DATABASE_PASSWORD=CHANGE_ME_LOCAL_ONLY

# A non-secret identifier used by the app. Real key material comes later.
SERVICE_NAME=vaultlog-api
```

Copy it locally:

```bash
cp .env.example .env
```

**Security rule:** `.env.example` documents variable names and safe placeholders only. It must never contain a database password, signing key, encryption key, recovery code, API token, or production URL with credentials.

***

## 7. Create typed settings

Create `src/vaultlog/shared/config.py`:

```python
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://localhost:5173"

    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "vaultlog"
    database_user: str = "vaultlog_app"
    database_password: str

    service_name: str = "vaultlog-api"

    @property
    def database_url(self) -> PostgresDsn:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=self.database_user,
            password=self.database_password,
            host=self.database_host,
            port=self.database_port,
            path=self.database_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Why this matters

The config object is the only application-approved way to access runtime configuration. No other application code should use `os.environ`, `os.getenv`, or parse `.env` files.

Benefits:

- The application fails early if required configuration is absent.
- Constraints catch invalid ports and invalid environment names.
- Tests can override configuration predictably.
- Secrets are kept out of logs, routers, and domain logic.
- Deployment can replace `.env` with Cloud Run environment variables and Secret Manager without changing application code.

***

## 8. Add structured logging

Create `src/vaultlog/shared/logging.py`:

```python
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=log_level.upper(),
        stream=sys.stdout,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level.upper()),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### Logging rule

Logs are a security asset and a security risk.

You will later log an auditable action such as `secret.read` or `secret.rotation.completed`, but **never**:

- Raw passwords.
- JWTs or refresh tokens.
- TOTP codes.
- Recovery codes.
- Plaintext secret values.
- Encryption keys or data-encryption keys.
- Full authorization headers.
- Sensitive request bodies.

A useful future log field is `request_id`; a dangerous log field is `secret_value`.

***

## 9. Add API health router

Create `src/vaultlog/presentation/api/v1/health.py`:

```python
from fastapi import APIRouter, status
from pydantic import BaseModel


router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness health check",
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
```

This is intentionally not a database readiness check yet. A liveness endpoint answers: “Is the process alive and serving HTTP?” Later we will add a protected or separate readiness endpoint that verifies database connectivity without disclosing internal details publicly.

***

## 10. Create the FastAPI application

Create `src/vaultlog/main.py`:

```python
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vaultlog.presentation.api.v1.health import router as health_router
from vaultlog.shared.config import get_settings
from vaultlog.shared.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)

    logger = structlog.get_logger()
    logger.info(
        "application.starting",
        service=settings.service_name,
        environment=settings.environment,
    )

    yield

    logger.info("application.stopping", service=settings.service_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title="VaultLog API",
        version="0.1.0",
        description="Security-first multi-tenant vault and secret management API.",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )

    allowed_origins = [
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    app.include_router(health_router, prefix="/api/v1")

    return app


app = create_app()
```

### Senior-engineer reasoning

- `create_app()` is a factory, not a global pile of router imports. Tests will later create isolated apps with overridden dependencies.
- API routes are versioned from day one: `/api/v1/...`. This prevents a breaking migration from becoming an emergency later.
- CORS uses an explicit allowlist. Never use `allow_origins=["*"]` with credentialed requests.
- Interactive docs are turned off in production by default. This is not a substitute for API security, but it reduces unnecessary endpoint discovery.
- The lifespan handler gives us one explicit place to create and close database pools, cryptographic key providers, queues, and metrics clients later.

***

## 11. Run locally without Docker

Start the application:

```bash
uv run fastapi dev -e vaultlog.main:app
```

In a second terminal:

```bash
curl -i http://127.0.0.1:8000/api/v1/health
```

Expected response:

```http
HTTP/1.1 200 OK
content-type: application/json

{"status":"ok"}
```

Then open:

```text
http://127.0.0.1:8000/docs
```

You should see a single `GET /api/v1/health` operation.

***

## 12. Add the first test

Create `tests/unit/test_health.py`:

```python
from starlette.testclient import TestClient as TestClient  # noqa

from vaultlog.main import create_app


def test_health_check_returns_ok() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Run it:

```bash
uv run pytest
```

Run static checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Format automatically if necessary:

```bash
uv run ruff format .
uv run ruff check . --fix
```

### Engineering habit

Every implementation task in the future chapters ends with:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Do not treat these as cleanup commands. They are part of the definition of done.

***

## 13. Add pre-commit hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-merge-conflict
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
```

Install and validate:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Commit this initial foundation:

```bash
git add .
git commit -m "chore: initialize vaultlog FastAPI foundation"
```

***

## 14. Add local PostgreSQL Compose setup

Create `compose.yaml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: vaultlog-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: vaultlog
      POSTGRES_USER: vaultlog_app
      POSTGRES_PASSWORD: CHANGE_ME_LOCAL_ONLY
    ports:
      - "5432:5432"
    volumes:
      - vaultlog_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "pg_isready -U vaultlog_app -d vaultlog",
        ]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  vaultlog_postgres_data:
```

Start PostgreSQL:

```bash
docker compose up -d
docker compose ps
```

Inspect logs if the container fails:

```bash
docker compose logs postgres
```

Stop containers while retaining database data:

```bash
docker compose down
```

Delete containers **and** local database data only when you deliberately want a full reset:

```bash
docker compose down -v
```

At this stage the FastAPI app does not use the database yet. That is deliberate. The next chapter will introduce SQLAlchemy, migration ownership, the separate app role, tenant context, and RLS in a controlled sequence.

***

## 15. Write the first ADR

Create `docs/adr/0001-shared-postgresql-with-rls.md`:

```markdown
# ADR 0001: Use shared PostgreSQL with Row-Level Security

- Status: Accepted
- Date: 2026-07-29

## Context

VaultLog is a multi-tenant SaaS application. Organizations must never access
another organization's vaults, secret metadata, encrypted secret material, or
audit records.

## Decision

Use one shared PostgreSQL database and schema. Every tenant-owned table will
contain a non-null `tenant_id` column. PostgreSQL Row-Level Security will enforce
tenant isolation using a transaction-scoped tenant identifier set by the
application after JWT validation.

## Consequences

- The app database role must not have `BYPASSRLS`.
- The application must set tenant context for every transaction.
- Every tenant-owned table requires RLS enabled, forced, and tested.
- Database migrations must be reviewed as security-sensitive changes.
- RLS supplements application-level authorization; it does not replace it.
```

### Why an ADR?

This is not bureaucracy. Six weeks from now, when you ask why tenant filtering exists both in repositories and RLS policies, the ADR answers the architectural question without relying on memory. Good teams document decisions, alternatives, and consequences — not just endpoints and tables.

***

## 16. Completion checklist

Before proceeding, verify all of the following:

- [ ] `uv run fastapi dev -e vaultlog.main:app` starts successfully.
- [ ] `GET /api/v1/health` returns `200` and `{"status":"ok"}`.
- [ ] `/docs` is accessible locally.
- [ ] `docker compose up -d` starts PostgreSQL successfully.
- [ ] `uv run pytest` passes.
- [ ] `uv run ruff check .` passes.
- [ ] `uv run ruff format --check .` passes.
- [ ] `uv run mypy` passes.
- [ ] `.env` is ignored by Git.
- [ ] The initial commit exists.
- [ ] `docs/adr/0001-shared-postgresql-with-rls.md` exists.

***

## 17. Chapter outcome

You now have a deliberately small but production-shaped FastAPI service. Its important properties are not visible in the health endpoint: typed config, explicit boundaries, reproducible tooling, safe environment handling, container-ready infrastructure, and a documented tenant-isolation decision.

The next chapter will establish the **database foundation**: async SQLAlchemy, Alembic, distinct database owner/app roles, secure session lifecycle, transaction-scoped tenant context, the first RLS policy, and adversarial cross-tenant isolation tests. PostgreSQL RLS is effective only when policies and role privileges are carefully configured, including avoiding roles that can bypass policy enforcement. [docs.aws.amazon](https://docs.aws.amazon.com/prescriptive-guidance/latest/saas-multitenant-managed-postgresql/rls.md)

***

## Chapter 2 — PostgreSQL foundation with transaction-scoped RLS

**Goal:** Wire async SQLAlchemy 2.0 and Alembic into the FastAPI application, create distinct migration and application database roles, implement a Unit of Work that sets transaction-scoped tenant context with `SET LOCAL`, and prove cross-tenant isolation with adversarial tests before any authentication exists.

**Time budget:** 45–55 minutes.

**Why this chapter comes before authentication:** Tenant context must not depend on unfinished JWT code. By the end of this chapter, tenant isolation is a database-enforced invariant tested with raw connections. Authentication will later *supply* the tenant ID; it will never *define* the isolation rule.

***

## 1. The trust model

VaultLog connects to PostgreSQL with three distinct identities:

| Role | Privileges | Used by |
|---|---|---|
| `vaultlog_owner` | Owns schema objects, `BYPASSRLS` by ownership | Alembic migrations only |
| `vaultlog_app` | `CONNECT`, `USAGE`, DML grants, `NOBYPASSRLS` | The FastAPI application |
| `vaultlog_admin` | `BYPASSRLS`, minimal read access | Break-glass platform operations only |

The application role must never own tables. PostgreSQL table owners bypass RLS unless `FORCE ROW LEVEL SECURITY` is set, and superusers always bypass it — so the safest design is an app role that owns nothing and cannot bypass anything. [ricofritzsche](https://ricofritzsche.me/mastering-postgresql-row-level-security-rls-for-rock-solid-multi-tenancy/)

***

## 2. Recreate Compose with the owner role

Your Chapter 1 Compose used the app user as the Postgres bootstrap superuser — that role owns the database, which would quietly defeat RLS. Replace it.

Create `docker/postgres/init.sql`:

```sql
-- Executed once when the data volume is first initialized.
-- POSTGRES_USER/POSTGRES_DB create the bootstrap superuser and database.

CREATE ROLE vaultlog_owner LOGIN PASSWORD 'CHANGE_ME_OWNER_LOCAL_ONLY';
CREATE ROLE vaultlog_app LOGIN PASSWORD 'CHANGE_ME_APP_LOCAL_ONLY' NOBYPASSRLS;

-- Ownership transfer: the owner role owns the database, not the app role.
ALTER DATABASE vaultlog OWNER TO vaultlog_owner;

GRANT CONNECT ON DATABASE vaultlog TO vaultlog_app;
```

Replace `compose.yaml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: vaultlog-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: vaultlog
      POSTGRES_USER: postgres_bootstrap
      POSTGRES_PASSWORD: CHANGE_ME_BOOTSTRAP_LOCAL_ONLY
    ports:
      - "5432:5432"
    volumes:
      - vaultlog_postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vaultlog_app -d vaultlog"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  vaultlog_postgres_data:
```

Update `.env.example`:

```dotenv
# Runtime
ENVIRONMENT=local
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173
SERVICE_NAME=vaultlog-api

# Application database connection (RLS-enforced role)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=vaultlog
DATABASE_USER=vaultlog_app
DATABASE_PASSWORD=CHANGE_ME_APP_LOCAL_ONLY

# Migration database connection (schema owner, used by Alembic only)
MIGRATION_DATABASE_USER=vaultlog_owner
MIGRATION_DATABASE_PASSWORD=CHANGE_ME_OWNER_LOCAL_ONLY
```

Update your local `.env` to match, then fully reset the volume so the init script runs:

```bash
docker compose down -v
docker compose up -d
docker compose logs postgres
```

Verify the roles exist:

```bash
docker compose exec postgres psql -U postgres_bootstrap -d vaultlog -c "\du"
```

You should see `vaultlog_app`, `vaultlog_owner`, and `postgres_bootstrap`.

***

## 3. Extend settings for two database URLs

Update `src/vaultlog/shared/config.py`:

```python
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    log_level: str = "INFO"

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://localhost:5173"
    service_name: str = "vaultlog-api"

    database_host: str = "localhost"
    database_port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = "vaultlog"
    database_user: str = "vaultlog_app"
    database_password: str

    migration_database_user: str = "vaultlog_owner"
    migration_database_password: str

    def build_database_url(self, user: str, password: str) -> str:
        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=user,
            password=password,
            host=self.database_host,
            port=self.database_port,
            path=self.database_name,
        ).unicode_string()

    @property
    def database_url(self) -> str:
        return self.build_database_url(self.database_user, self.database_password)

    @property
    def migration_database_url(self) -> str:
        return self.build_database_url(
            self.migration_database_user, self.migration_database_password
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Why string URLs instead of `PostgresDsn` objects:** Alembic and `create_async_engine` both accept strings cleanly; returning the rendered unicode string avoids type friction and accidental re-validation.

***

## 4. SQLAlchemy base and engine factory

Create `src/vaultlog/infrastructure/database/base.py`:

```python
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

Create `src/vaultlog/infrastructure/database/engine.py`:

```python
from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def build_engine(database_url: str, *, pool_size: int = 5, max_overflow: int = 5) -> AsyncEngine:
    return create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        echo=False,
    )


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
```

Design notes:

- `pool_pre_ping=True` detects dead pooled connections before handing them to a request.
- `expire_on_commit=False` prevents surprising lazy loads after commit — lazy loading in async code is a classic source of `MissingGreenlet` errors, so we forbid the pattern by making objects stay loaded with their committed state. [shahadul](https://shahadul.com/blog/async-sqlalchemy-production)
- `autoflush=False` keeps flushes explicit. Implicit flushes mid-use-case can write partial state before your audit logic runs.

***

## 5. The tenant context dependency

Create `src/vaultlog/application/ports/tenant_context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class TenantContext:
    tenant_id: UUID
```

For now, tenant context is constructed manually in tests and scripts. In the authentication chapter, a FastAPI dependency will build it from a validated JWT claim — and **only** from that claim, never from headers, query params, or path params that a caller could forge.

***

## 6. The Unit of Work

Create `src/vaultlog/application/ports/unit_of_work.py`:

```python
from __future__ import annotations

from typing import Protocol, Self


class UnitOfWork(Protocol):
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

Create `src/vaultlog/infrastructure/database/unit_of_work.py`:

```python
from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultlog.application.ports.tenant_context import TenantContext


class SqlAlchemyUnitOfWork:
    """One transaction per use case, with tenant context pinned via SET LOCAL.

    SET LOCAL scopes the GUC to the current transaction, so tenant context
    cannot leak between requests sharing a pooled connection. [web:21]
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_context: TenantContext,
    ) -> None:
        self._session_factory = session_factory
        self._tenant_context = tenant_context

    async def __aenter__(self) -> Self:
        self.session: AsyncSession = self._session_factory()
        await self.session.begin()
        await self.session.execute(
            text("SET LOCAL app.current_tenant = :tenant_id"),
            {"tenant_id": str(self._tenant_context.tenant_id)},
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.session.rollback()
        finally:
            await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
```

Three security-critical properties to internalize:

1. **Parameterized `SET LOCAL`.** The tenant ID is bound as a parameter, never f-string interpolated — otherwise a SQL injection could rewrite the tenant context itself. [stackoverflow](https://stackoverflow.com/questions/67019828/using-postgresql-row-level-security-rls-policies-with-current-setting-functi)
2. **Transaction scope, not session scope.** `SET LOCAL` dies with the transaction. A bug that reuses a session across tenants cannot leak context because each new transaction starts unset — and our policies treat "unset" as "deny".
3. **One UoW per use case.** Later, the audit ledger insert and the domain mutation will share this transaction. If either fails, both roll back — no action without a log, no log without an action.

**Senior note on an alternative:** SQLAlchemy's `after_begin` session event can also emit `SET LOCAL` automatically; if you use it, emit the statement on the `Connection`, not the `Session`. We choose the explicit UoW approach because it makes the security-relevant step visible and testable rather than hidden in an event hook. [github](https://github.com/sqlalchemy/sqlalchemy/discussions/10469)

***

## 7. First tenant-owned tables

Create `src/vaultlog/infrastructure/database/models.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from vaultlog.infrastructure.database.base import Base


class OrganizationModel(Base):
    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vaults: Mapped[list["VaultModel"]] = relationship(back_populates="organization")


class VaultModel(Base):
    __tablename__ = "vault"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped[OrganizationModel] = relationship(back_populates="vaults")
```

Conventions to keep from day one:

- `tenant_id` on **every** tenant-owned table, `NOT NULL`, indexed. RLS policies filter on it; without an index, tenant-scoped queries degrade as data grows.
- The `organization` table is itself tenant-owned — its "tenant" is its own `id`, and its RLS policy will compare `id = current_setting(...)`.
- UUID primary keys, never sequential integers: sequential IDs make cross-tenant IDOR probing trivial to enumerate.

***

## 8. Alembic with an async engine and the owner role

Initialize Alembic with the async template:

```bash
uv run alembic init -t async alembic
```

Replace `alembic/env.py`:

```python
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from vaultlog.infrastructure.database.base import Base
from vaultlog.infrastructure.database import models  # noqa: F401 — registers tables
from vaultlog.shared.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.migration_database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

This follows the standard async Alembic pattern: an async engine whose connection is adapted through `run_sync`, with migrations running inside a transaction. [async-workflows](https://www.async-workflows.com/alembic-async-migrations-and-schema-evolution/configuring-alembic-with-async-sqlalchemy-engines/)

In `alembic.ini`, remove or comment out the hardcoded `sqlalchemy.url` line — `env.py` now injects it from settings, so no credentials live in the ini file.

Verify wiring (expect an empty version table):

```bash
uv run alembic current
```

***

## 9. The initial migration: tables, grants, and RLS policies

Autogenerate the tables, then hand-edit the result — autogeneration never writes roles, grants, or policies for you:

```bash
uv run alembic revision --autogenerate -m "initial schema with rls"
```

Open the generated file in `alembic/versions/` and replace its `upgrade`/`downgrade` with the following (keep the autogenerated `create_table` calls, add everything else around them):

```python
def upgrade() -> None:
    # --- autogenerated table creation (organization, vault) ---
    op.create_table(
        "organization",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "vault",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["organization.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vault_tenant_id", "vault", ["tenant_id"])

    # --- grants: app role can use the schema but owns nothing ---
    op.execute("GRANT USAGE ON SCHEMA public TO vaultlog_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON organization, vault TO vaultlog_app")

    # --- RLS: organization visible only as itself ---
    op.execute("ALTER TABLE organization ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON organization
        USING (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        """
    )

    # --- RLS: vault rows visible only to their tenant ---
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
```

Four details that carry real security weight:

- **`current_setting('app.current_tenant', true)`** — the `true` argument makes a missing GUC return `NULL` instead of raising an error; `NULLIF(..., '')::uuid` then yields `NULL`, and `NULL = anything` is never true. **An unscoped connection sees zero rows rather than crashing or, worse, a permissive fallback.** [medium](https://medium.com/@manishchaulagain/multi-tenancy-using-row-level-security-in-postgres-2ebfd6871539)
- **`FORCE ROW LEVEL SECURITY`** — without it, the table owner (which is `vaultlog_owner`, used by Alembic) bypasses policies, making your manual `psql` verification misleading.
- **`WITH CHECK`** mirrors `USING` — without it, a tenant could *insert* rows belonging to another tenant even if it couldn't read them. [stackoverflow](https://stackoverflow.com/questions/66227828/postgresql-simple-row-level-security-rls)
- **Grants in migrations** — every future `CREATE TABLE` migration must also grant the app role and add RLS statements. Treat this as a checklist item in code review.

Apply and verify:

```bash
uv run alembic upgrade head
uv run alembic current
docker compose exec postgres psql -U vaultlog_owner -d vaultlog -c "\d+ vault"
```

The `\d+` output should show `Policies: POLICY "tenant_isolation"` and the table flagged with row security enabled and forced.

***

## 10. Wire the engine into the app lifespan

Update `src/vaultlog/main.py`:

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from vaultlog.infrastructure.database.engine import build_engine, build_session_factory
from vaultlog.presentation.api.v1.health import router as health_router
from vaultlog.shared.config import get_settings
from vaultlog.shared.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(settings.log_level)
    logger = structlog.get_logger()

    engine = build_engine(settings.database_url)
    app.state.session_factory = build_session_factory(engine)

    logger.info("application.starting", service=settings.service_name, environment=settings.environment)
    yield

    await engine.dispose()
    logger.info("application.stopping", service=settings.service_name)
```

The rest of `main.py` (factory, CORS, router) stays as in Chapter 1. The engine is created once per process and disposed cleanly — never create an engine per request.

***

## 11. Adversarial isolation tests

This is the chapter's real deliverable. You will attack your own database layer and prove it holds.

Create `tests/integration/conftest.py`:

```python
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vaultlog.shared.config import get_settings

settings = get_settings()

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
async def owner_engine():
    """Migration/seed role: bypasses RLS as table owner is forced NOT to...
    We use the owner role only to seed fixture data."""
    engine = create_async_engine(settings.migration_database_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def app_engine():
    """The RLS-enforced application role."""
    engine = create_async_engine(settings.database_url)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
async def seed_tenants(owner_engine):
    async with owner_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO organization (id, name) VALUES (:a, 'Tenant A'), (:b, 'Tenant B') "
                "ON CONFLICT DO NOTHING"
            ),
            {"a": TENANT_A, "b": TENANT_B},
        )
        await conn.execute(
            text("INSERT INTO vault (id, tenant_id, name) VALUES (:id, :t, 'A secret vault') ON CONFLICT DO NOTHING"),
            {"id": uuid.uuid4(), "t": TENANT_A},
        )
    yield


@pytest.fixture()
async def scoped_session(app_engine):
    """Yields a function that opens a session scoped to a given tenant."""

    factory = async_sessionmaker(app_engine, class_=AsyncSession, expire_on_commit=False)

    async def _open(tenant_id):
        session = factory()
        await session.begin()
        await session.execute(
            text("SET LOCAL app.current_tenant = :t"), {"t": str(tenant_id)}
        )
        return session

    return _open
```

Create `tests/integration/test_tenant_isolation.py`:

```python
from __future__ import annotations

from sqlalchemy import text

from tests.integration.conftest import TENANT_A, TENANT_B


async def test_tenant_a_sees_own_vaults(scoped_session):
    session = await scoped_session(TENANT_A)
    result = await session.execute(text("SELECT name FROM vault"))
    names = [row[0] for row in result.all()]
    await session.close()
    assert names == ["A secret vault"]


async def test_tenant_b_sees_no_vaults(scoped_session):
    session = await scoped_session(TENANT_B)
    result = await session.execute(text("SELECT id FROM vault"))
    assert result.all() == []
    await session.close()


async def test_cross_tenant_insert_is_rejected(scoped_session):
    session = await scoped_session(TENANT_B)
    try:
        await session.execute(
            text("INSERT INTO vault (id, tenant_id, name) VALUES (gen_random_uuid(), :t, 'stolen')"),
            {"t": str(TENANT_A)},
        )
        assert False, "RLS WITH CHECK should have rejected the insert"
    except Exception:
        await session.rollback()
    finally:
        await session.close()


async def test_unscoped_connection_sees_nothing(app_engine):
    """No SET LOCAL at all: the fail-closed policy must yield zero rows, not an error."""
    async with app_engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM vault"))
        assert result.scalar() == 0


async def test_tenant_cannot_read_other_tenant_organization(scoped_session):
    session = await scoped_session(TENANT_B)
    result = await session.execute(text("SELECT name FROM organization"))
    names = [row[0] for row in result.all()]
    await session.close()
    assert names == ["Tenant B"]
```

Run against the live Compose database:

```bash
docker compose up -d
uv run pytest tests/integration -v
```

Every test must pass. If `test_unscoped_connection_sees_nothing` errors instead of returning zero, your policies used the error-throwing form of `current_setting` — fix them to the fail-closed form shown above.

### What each test proves

- **Tenant B sees nothing:** a forgotten `WHERE tenant_id` in application code degrades to an empty result, not a cross-tenant leak.
- **Cross-tenant insert rejected:** `WITH CHECK` blocks write-side smuggling.
- **Unscoped sees nothing:** a code path that forgets `SET LOCAL` (a background job, a new dependency) fails closed by default.
- **Org table self-isolation:** even the tenant catalog is partitioned — tenant B cannot enumerate tenant A's organization name.

***

## 12. UoW smoke test

Create `tests/integration/test_unit_of_work.py`:

```python
from __future__ import annotations

import uuid

from sqlalchemy import text

from vaultlog.application.ports.tenant_context import TenantContext
from vaultlog.infrastructure.database.engine import build_session_factory
from vaultlog.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from tests.integration.conftest import TENANT_A


async def test_uow_sets_tenant_context_and_rolls_back_on_error(app_engine):
    factory = build_session_factory(app_engine)
    uow = SqlAlchemyUnitOfWork(factory, TenantContext(tenant_id=TENANT_A))

    try:
        async with uow:
            result = await uow.session.execute(text("SELECT count(*) FROM vault"))
            assert result.scalar() == 1
            raise RuntimeError("simulate use-case failure")
    except RuntimeError:
        pass

    # After rollback the transaction is gone; a new unscoped read sees nothing.
    async with app_engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM vault"))
        assert result.scalar() == 0
```

This verifies the whole chain: factory → UoW → `SET LOCAL` → RLS → rollback. Everything in later chapters (use cases, audit ledger, secret rotation) builds on this exact mechanism.

***

## 13. Migration review checklist

Add `docs/adr/0002-database-role-separation.md`:

```markdown
# ADR 0002: Separate database roles for migrations, application, and admin

- Status: Accepted
- Date: 2026-07-29

## Context

PostgreSQL RLS is bypassed by superusers and (unless forced) by table owners.
If the application connects with the same role that runs migrations, RLS
provides no real isolation guarantee.

## Decision

- vaultlog_owner: owns schema, runs migrations via Alembic, never used by the app.
- vaultlog_app: NOBYPASSRLS, DML grants only, used by the FastAPI application.
- Break-glass admin access is a separate future role with BYPASSRLS,
  used only through an isolated code path.

## Consequences

- Every migration creating a table must also GRANT to vaultlog_app and add
  ENABLE/FORCE ROW LEVEL SECURITY plus a tenant_isolation policy.
- Local development seeds fixture data through the owner role.
- The app role cannot create tables, preventing privilege drift at runtime.
```

Also add a standing checklist to `docs/migration-checklist.md`:

```markdown
# Migration security checklist

For every migration that creates or alters a tenant-owned table:

- [ ] Table has non-null, indexed `tenant_id` (or is itself the tenant table).
- [ ] `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` executed.
- [ ] `tenant_isolation` policy created with fail-closed
      `NULLIF(current_setting('app.current_tenant', true), '')::uuid`.
- [ ] Policy has both `USING` and `WITH CHECK`.
- [ ] `GRANT SELECT, INSERT, UPDATE, DELETE` (minimum needed) to `vaultlog_app`.
- [ ] Downgrade drops policies before tables.
- [ ] Cross-tenant integration test added or updated.
```

***

## 14. Definition of done

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

Then commit:

```bash
git add .
git commit -m "feat: add async database foundation with transaction-scoped RLS"
```

## 15. Completion checklist

- [ ] Three Postgres roles exist; `vaultlog_app` is `NOBYPASSRLS` and owns nothing.
- [ ] Alembic connects as `vaultlog_owner`; `alembic upgrade head` succeeds.
- [ ] `organization` and `vault` have RLS enabled, forced, with `USING` + `WITH CHECK` policies.
- [ ] `SET LOCAL` is issued through the UoW with a bound parameter.
- [ ] All five adversarial isolation tests pass, including the unscoped-connection test.
- [ ] Engine lifecycle lives in the app lifespan; no per-request engines.
- [ ] ADR 0002 and the migration checklist are committed.

## 16. Chapter outcome

The database now enforces tenant isolation **below** your application code. Even a buggy repository, a future junior contributor, or an AI coding agent that forgets a tenant filter cannot read or write across organizations — the worst case is an empty result or a rejected write.

The next chapter builds **identity and authentication**: user model, Argon2 password hashing, RS256 JWT access tokens, rotating refresh tokens with reuse detection, and wiring the validated `tenant_id` claim into the `TenantContext` you just built.

***

## Chapter 3 — Authentication: passwords, JWTs, and refresh rotation

**Goal:** Implement registration and login with Argon2id password hashing, RS256-signed short-lived access tokens, and rotating refresh tokens stored server-side with reuse detection. By the end, the access token's `tid` claim flows into the `TenantContext` from Chapter 2, making every authenticated request automatically RLS-scoped.

**Time budget:** 35–45 minutes.

**Why this design:** VaultLog uses a *hybrid* model — stateless JWT access tokens for fast request authentication, plus stateful, server-tracked refresh tokens so you can actually revoke sessions and detect theft. Pure stateless JWTs cannot be revoked before expiry, which is unacceptable for a secrets-management product.

***

## 1. The authentication model at a glance

```text
Login (email + password)
   |
   v
Access token (RS256 JWT, 10 min, in memory / Authorization header)
Refresh token (opaque random string, 30 days, HttpOnly cookie)
   |
   |-- every refresh: old token consumed, new pair issued, DB row rotated
   |-- replayed old token detected -> entire session family revoked
```

Key properties:

- **Access tokens are stateless and short-lived.** The API verifies signature, issuer, audience, and expiry without a database hit on most requests.
- **Refresh tokens are stateful and rotatable.** Only their *hash* is stored; the raw value exists only in the client's cookie.
- **Sessions are first-class.** Logout, password change, and detected token theft all revoke a session server-side.
- **Tenant binding happens at token issue.** The `tid` claim is validated against membership when minted — never trusted from request input later.

***

## 2. Install dependencies and generate keys

```bash
uv add argon2-cffi "pyjwt[crypto]" email-validator
```

Generate an RSA key pair for token signing. **Never commit the private key.**

```bash
mkdir -p keys
openssl genrsa -out keys/jwt-private.pem 2048
openssl rsa -in keys/jwt-private.pem -pubout -out keys/jwt-public.pem
chmod 600 keys/jwt-private.pem
```

Add `keys/` to `.gitignore` (it is covered by the Chapter 1 rules — double-check). In production, the private key lives in Secret Manager or is handled by a KMS; files are a local-development convenience.

Update `.env` and `.env.example`:

```dotenv
# JWT
JWT_ISSUER=vaultlog
JWT_AUDIENCE=vaultlog-api
JWT_PRIVATE_KEY_PEM_PATH=./keys/jwt-private.pem
JWT_PUBLIC_KEY_PEM_PATH=./keys/jwt-public.pem
ACCESS_TOKEN_TTL_SECONDS=600
REFRESH_TOKEN_TTL_DAYS=30
```

Add the corresponding fields to `Settings` in `shared/config.py`:

```python
jwt_issuer: str = "vaultlog"
jwt_audience: str = "vaultlog-api"
jwt_private_key_pem_path: str
jwt_public_key_pem_path: str
access_token_ttl_seconds: int = 600
refresh_token_ttl_days: int = 30
```

***

## 3. Identity and session schema

Create a new Alembic revision:

```bash
uv run alembic revision -m "identity and auth sessions"
```

Fill in `upgrade()`:

```python
def upgrade() -> None:
    # Users are global identities — NOT tenant-scoped, no RLS.
    op.create_table(
        "app_user",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_app_user_email"),
    )

    # Membership links users to organizations with a role — tenant-owned, RLS.
    op.create_table(
        "membership",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(), sa.ForeignKey("organization.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),
        sa.CheckConstraint("role IN ('owner','admin','member','viewer')", name="ck_membership_role"),
    )
    op.create_index("ix_membership_tenant_id", "membership", ["tenant_id"])
    op.create_index("ix_membership_user_id", "membership", ["user_id"])

    # Sessions and refresh tokens are global (pre-tenant-selection), no RLS.
    op.create_table(
        "auth_session",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_auth_session_user_id", "auth_session", ["user_id"])

    op.create_table(
        "refresh_token",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("auth_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.UUID(), sa.ForeignKey("refresh_token.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_refresh_token_hash"),
    )
    op.create_index("ix_refresh_token_session_id", "refresh_token", ["session_id"])

    # Grants and RLS for the tenant-owned membership table.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON app_user, membership, auth_session, refresh_token TO vaultlog_app")
    op.execute("ALTER TABLE membership ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE membership FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON membership
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON membership")
    op.drop_table("refresh_token")
    op.drop_table("auth_session")
    op.drop_table("membership")
    op.drop_table("app_user")
```

**Why `app_user`, `auth_session`, and `refresh_token` have no RLS:** they are global identity tables — a user exists before and independently of any tenant, and login happens before tenant context exists. They are protected by application-layer queries keyed on authenticated user ID, plus the fact that the app role can only reach them through your repository code. `membership`, by contrast, is tenant-owned data and gets the standard policy.

**Naming note:** the table is `app_user`, not `user`, because `user` is a reserved word in PostgreSQL.

Apply the migration:

```bash
uv run alembic upgrade head
```

***

## 4. Password hashing with Argon2id

Create `src/vaultlog/infrastructure/security/passwords.py`:

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

_hasher = PasswordHasher()  # argon2-cffi defaults: Argon2id, OWASP-aligned parameters


def hash_password(plaintext: str) -> str:
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plaintext)
    except (VerifyMismatchError, VerificationError):
        return False
```

Rules that are non-negotiable:

- **Hash, never encrypt.** Encryption is reversible; a stolen key plus a stolen database equals every password. Argon2id is deliberately slow and memory-hard so offline guessing is expensive.
- **No homemade schemes.** No SHA-256-with-salt, no "hash it twice", no encryption. The algorithm choice has already been made by people who break these things professionally.
- **Policy:** minimum 12 characters, maximum 128 (the max prevents DoS via multi-megabyte passwords through the memory-hard hasher). Skip composition rules ("must contain a symbol") — they produce predictable passwords.

Create the password policy as a domain value object — `src/vaultlog/domain/identity/password.py`:

```python
class PasswordPolicyError(ValueError):
    pass


def validate_password_strength(plaintext: str) -> None:
    if not 12 <= len(plaintext) <= 128:
        raise PasswordPolicyError("Password must be between 12 and 128 characters")
```

Putting the rule in the domain layer means it applies whether the caller is the register endpoint, a password-change endpoint, or an admin provisioning flow.

***

## 5. Token service

Create `src/vaultlog/infrastructure/security/tokens.py`:

```python
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from vaultlog.shared.config import get_settings

settings = get_settings()


class TokenValidationError(Exception):
    pass


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    session_id: uuid.UUID
    amr: tuple[str, ...]


class TokenService:
    def __init__(self) -> None:
        self._private_key = open(settings.jwt_private_key_pem_path).read()
        self._public_key = open(settings.jwt_public_key_pem_path).read()

    # --- Access tokens ---

    def mint_access_token(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        session_id: uuid.UUID,
        amr: tuple[str, ...] = ("pwd",),
    ) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": str(user_id),
            "tid": str(tenant_id),
            "sid": str(session_id),
            "amr": list(amr),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=settings.access_token_ttl_seconds)).timestamp()),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self._private_key, algorithm="RS256")

    def verify_access_token(self, token: str) -> AccessTokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._public_key,
                algorithms=["RS256"],  # pinned — never accept alg from the token header
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
                options={"require": ["exp", "iat", "sub", "tid", "sid", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenValidationError("Invalid token") from exc

        return AccessTokenClaims(
            user_id=uuid.UUID(payload["sub"]),
            tenant_id=uuid.UUID(payload["tid"]),
            session_id=uuid.UUID(payload["sid"]),
            amr=tuple(payload.get("amr", [])),
        )

    # --- Refresh tokens (opaque, server-tracked) ---

    @staticmethod
    def generate_refresh_token() -> str:
        return secrets.token_urlsafe(48)  # 48 bytes = 384 bits of entropy

    @staticmethod
    def hash_refresh_token(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()

    @staticmethod
    def constant_time_equals(a: str, b: str) -> bool:
        return hmac.compare_digest(a, b)
```

Security properties worth understanding, not just copying:

- **`algorithms=["RS256"]` pinned at verification.** Accepting the algorithm from the JWT header enables the classic `alg=none` and RS256→HS256 confusion attacks. The server decides; the token does not.
- **Issuer and audience checked.** A token minted for a different service or environment is rejected, preventing confused-deputy replay across systems.
- **Refresh tokens are opaque, not JWTs.** A random string has no claims to forge, and storing only its SHA-256 hash means a database leak doesn't hand an attacker usable refresh tokens. The raw token has enough entropy (384 bits) that a fast hash is acceptable here — unlike passwords, there is nothing to brute-force.
- **`sub`, `tid`, `sid` are UUIDs.** The `tid` claim is what later becomes your `TenantContext` — it can only appear in a token if membership was validated at mint time (next section).

***

## 6. Domain model and repositories

Create `src/vaultlog/domain/identity/models.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: uuid.UUID
    email: str
    is_active: bool
    mfa_enabled: bool
```

Create `src/vaultlog/infrastructure/database/identity_models.py` (SQLAlchemy mappings):

```python
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from vaultlog.infrastructure.database.base import Base


class UserModel(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class MembershipModel(Base):
    __tablename__ = "membership"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AuthSessionModel(Base):
    __tablename__ = "auth_session"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RefreshTokenModel(Base):
    __tablename__ = "refresh_token"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("auth_session.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("refresh_token.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

Register these in `alembic/env.py`'s model imports if autogeneration matters to you (the migration above is handwritten, so runtime imports are what count).

***

## 7. Authentication use cases

Create `src/vaultlog/application/identity/use_cases.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.domain.identity.password import validate_password_strength
from vaultlog.infrastructure.database.identity_models import (
    AuthSessionModel,
    MembershipModel,
    RefreshTokenModel,
    UserModel,
)
from vaultlog.infrastructure.security.passwords import hash_password, verify_password
from vaultlog.infrastructure.security.tokens import TokenService
from vaultlog.shared.config import get_settings

settings = get_settings()


class AuthError(Exception):
    """Generic by design — never leak which part failed."""


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


class RegisterUser:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, email: str, password: str, organization_name: str) -> uuid.UUID:
        validate_password_strength(password)
        normalized = email.strip().lower()

        exists = await self._session.scalar(select(UserModel.id).where(UserModel.email == normalized))
        if exists is not None:
            raise AuthError("Registration failed")

        user = UserModel(email=normalized, password_hash=hash_password(password))
        self._session.add(user)
        await self._session.flush()

        from vaultlog.infrastructure.database.models import OrganizationModel

        org = OrganizationModel(name=organization_name)
        self._session.add(org)
        await self._session.flush()

        self._session.add(MembershipModel(tenant_id=org.id, user_id=user.id, role="owner"))
        return user.id


class LoginUser:
    def __init__(self, session: AsyncSession, tokens: TokenService) -> None:
        self._session = session
        self._tokens = tokens

    async def execute(self, email: str, password: str, user_agent: str | None) -> TokenPair:
        user = await self._session.scalar(
            select(UserModel).where(UserModel.email == email.strip().lower())
        )
        if user is None or not user.is_active:
            # Deliberately run a dummy verify to reduce timing difference.
            verify_password(password, "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
            raise AuthError("Invalid email or password")
        if not verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password")

        # Resolve the user's default tenant (single-org assumption for now;
        # Chapter 3.10 adds explicit organization switching).
        tenant_id = await self._session.scalar(
            select(MembershipModel.tenant_id).where(MembershipModel.user_id == user.id).limit(1)
        )
        if tenant_id is None:
            raise AuthError("Invalid email or password")

        session = AuthSessionModel(user_id=user.id, user_agent=user_agent)
        self._session.add(session)
        await self._session.flush()

        raw_refresh = self._tokens.generate_refresh_token()
        self._session.add(
            RefreshTokenModel(
                session_id=session.id,
                token_hash=self._tokens.hash_refresh_token(raw_refresh),
                expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
            )
        )

        access = self._tokens.mint_access_token(user.id, tenant_id, session.id)
        return TokenPair(access_token=access, refresh_token=raw_refresh)


class RefreshTokens:
    """Rotation with reuse detection. Runs in ONE transaction."""

    def __init__(self, session: AsyncSession, tokens: TokenService) -> None:
        self._session = session
        self._tokens = tokens

    async def execute(self, raw_refresh_token: str) -> TokenPair:
        token_hash = self._tokens.hash_refresh_token(raw_refresh_token)

        # Lock the row: concurrent refreshes with the same token serialize here.
        stored = await self._session.scalar(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash).with_for_update()
        )
        now = datetime.now(UTC)

        if stored is None:
            raise AuthError("Invalid refresh token")

        session = await self._session.get(AuthSessionModel, stored.session_id)
        if session is None or session.revoked_at is not None:
            raise AuthError("Invalid refresh token")

        if stored.used_at is not None or stored.revoked_at is not None:
            # REUSE DETECTED: an old token was presented after rotation.
            # Someone holds a stolen token — kill the whole family.
            session.revoked_at = now
            session.revocation_reason = "refresh_reuse_detected"
            raise AuthError("Invalid refresh token")

        if stored.expires_at <= now:
            session.revoked_at = now
            session.revocation_reason = "refresh_expired"
            raise AuthError("Invalid refresh token")

        # Rotate: consume old, mint new, link the chain.
        stored.used_at = now
        raw_new = self._tokens.generate_refresh_token()
        new_token = RefreshTokenModel(
            session_id=session.id,
            token_hash=self._tokens.hash_refresh_token(raw_new),
            expires_at=now + timedelta(days=settings.refresh_token_ttl_days),
        )
        self._session.add(new_token)
        await self._session.flush()
        stored.replaced_by_id = new_token.id
        session.last_used_at = now

        # Resolve tenant again — membership may have changed since login.
        tenant_id = await self._session.scalar(
            select(MembershipModel.tenant_id).where(MembershipModel.user_id == session.user_id).limit(1)
        )
        if tenant_id is None:
            raise AuthError("Invalid refresh token")

        access = self._tokens.mint_access_token(session.user_id, tenant_id, session.id)
        return TokenPair(access_token=access, refresh_token=raw_new)


class LogoutSession:
    def __init__(self, session: AsyncSession, tokens: TokenService) -> None:
        self._session = session
        self._tokens = tokens

    async def execute(self, raw_refresh_token: str) -> None:
        token_hash = self._tokens.hash_refresh_token(raw_refresh_token)
        stored = await self._session.scalar(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        if stored is not None:
            auth_session = await self._session.get(AuthSessionModel, stored.session_id)
            if auth_session is not None and auth_session.revoked_at is None:
                auth_session.revoked_at = datetime.now(UTC)
                auth_session.revocation_reason = "user_logout"
        # Logout is idempotent: unknown tokens still return success.
```

Why the reuse-detection logic matters: after a legitimate refresh, the old token's `used_at` is set. If anyone — attacker or a confused client — presents that old token again, the only explanation consistent with a correct client is theft, so the entire session family is revoked and both parties must log in again. The `SELECT ... FOR UPDATE` prevents two simultaneous refreshes from both passing the `used_at` check.

One deliberate subtlety: `LoginUser` and `RefreshTokens` query `membership` **without tenant context set** (login happens before any tenant is selected). Because `membership` has RLS and fail-closed policies, these queries would see zero rows as `vaultlog_app`! Resolve this by running the identity/session queries through the **owner-role engine** (the same pattern your tests used for seeding), in a clearly separated `IdentityUnitOfWork`. This is exactly the "admin/bypass path kept in an isolated code path" principle from Chapter 2 — it exists *only* for pre-tenant operations: login, registration, refresh, and organization listing. Never reuse it for tenant data.

***

## 8. The auth dependency and tenant wiring

Create `src/vaultlog/presentation/dependencies.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from vaultlog.infrastructure.security.tokens import TokenService, TokenValidationError

_bearer = HTTPBearer(auto_error=False)

_unauthorized = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    tenant_id: UUID
    session_id: UUID
    amr: tuple[str, ...]


async def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None:
        raise _unauthorized
    try:
        claims = TokenService().verify_access_token(credentials.credentials)
    except TokenValidationError:
        raise _unauthorized from None
    return Principal(
        user_id=claims.user_id,
        tenant_id=claims.tenant_id,
        session_id=claims.session_id,
        amr=claims.amr,
    )
```

Now connect it to the Chapter 2 machinery — `TenantContext` is built **from the verified token**, completing the chain:

```python
# In a router:
@router.post("/vaults")
async def create_vault(
    body: VaultCreateRequest,
    principal: Principal = Depends(current_principal),
    session_factory=Depends(get_session_factory),
) -> VaultResponse:
    context = TenantContext(tenant_id=principal.tenant_id)
    async with SqlAlchemyUnitOfWork(session_factory, context) as uow:
        ...  # every query is RLS-scoped to principal.tenant_id
        await uow.commit()
```

Every authenticated, tenant-scoped request in VaultLog follows this exact shape. Memorize it: **Bearer token → verified claims → Principal → TenantContext → UoW → RLS-enforced queries.**

***

## 9. Auth router

Create `src/vaultlog/presentation/api/v1/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from vaultlog.application.identity.use_cases import (
    AuthError,
    LoginUser,
    LogoutSession,
    RefreshTokens,
    RegisterUser,
    TokenPair,
)
from vaultlog.infrastructure.security.tokens import TokenService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "vaultlog_refresh"
COOKIE_MAX_AGE = 30 * 24 * 3600


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    organization_name: str = Field(min_length=1, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _set_refresh_cookie(response: Response, pair: TokenPair) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,       # JS cannot read it — XSS can't steal it
        secure=True,         # HTTPS only (disable via settings for local http)
        samesite="lax",
        path="/api/v1/auth", # sent only to auth endpoints
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, identity_uow=Depends(get_identity_uow)) -> dict:
    async with identity_uow as uow:
        try:
            user_id = await RegisterUser(uow.session).execute(
                body.email, body.password, body.organization_name
            )
        except AuthError:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registration failed")
        await uow.commit()
    return {"user_id": str(user_id)}


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    body: LoginRequest, request: Request, response: Response,
    identity_uow=Depends(get_identity_uow),
) -> AccessTokenResponse:
    async with identity_uow as uow:
        try:
            pair = await LoginUser(uow.session, TokenService()).execute(
                body.email, body.password, request.headers.get("user-agent")
            )
        except AuthError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        await uow.commit()
    _set_refresh_cookie(response, pair)
    return AccessTokenResponse(access_token=pair.access_token, expires_in=600)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(request: Request, response: Response, identity_uow=Depends(get_identity_uow)) -> AccessTokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    async with identity_uow as uow:
        try:
            pair = await RefreshTokens(uow.session, TokenService()).execute(raw)
        except AuthError:
            response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        await uow.commit()
    _set_refresh_cookie(response, pair)
    return AccessTokenResponse(access_token=pair.access_token, expires_in=600)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, identity_uow=Depends(get_identity_uow)) -> None:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw is not None:
        async with identity_uow as uow:
            await LogoutSession(uow.session, TokenService()).execute(raw)
            await uow.commit()
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
```

Cookie decisions, and why:

- **HttpOnly** is the whole point of the cookie strategy — XSS can deface the page but cannot exfiltrate the refresh token.
- **Path-scoped to `/api/v1/auth`** so the token isn't sent on every API request, shrinking its exposure surface.
- **SameSite=Lax** blocks cross-site POSTs from carrying the cookie in the common CSRF scenario; you'll add explicit CSRF protection later as defense-in-depth.
- The access token is returned in the body and stored **in memory** by the frontend — never in localStorage, where any XSS payload can read it.

Register the router in `main.py`: `app.include_router(auth_router, prefix="/api/v1")`.

Add `get_identity_uow` and `get_session_factory` providers to `dependencies.py` (the identity UoW uses the owner engine; the tenant UoW uses the app engine — this split is the security boundary).

***

## 10. Tests

Create `tests/unit/test_tokens.py`:

```python
import uuid

import pytest

from vaultlog.infrastructure.security.tokens import TokenService, TokenValidationError


def test_access_token_round_trip() -> None:
    service = TokenService()
    uid, tid, sid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    token = service.mint_access_token(uid, tid, sid)
    claims = service.verify_access_token(token)
    assert (claims.user_id, claims.tenant_id, claims.session_id) == (uid, tid, sid)


def test_tampered_token_rejected() -> None:
    service = TokenService()
    token = service.mint_access_token(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    with pytest.raises(TokenValidationError):
        service.verify_access_token(token + "tampered")


def test_refresh_hash_is_stable_and_not_raw() -> None:
    raw = TokenService.generate_refresh_token()
    assert TokenService.hash_refresh_token(raw) == TokenService.hash_refresh_token(raw)
    assert TokenService.hash_refresh_token(raw) != raw
```

Create `tests/integration/test_auth_flows.py` (against the Compose database, using the identity/owner path):

```python
async def test_register_then_login_returns_token_pair(identity_uow_factory):
    async with identity_uow_factory() as uow:
        await RegisterUser(uow.session).execute("ada@example.com", "correct horse battery", "Acme")
        await uow.commit()

    async with identity_uow_factory() as uow:
        pair = await LoginUser(uow.session, TokenService()).execute(
            "ada@example.com", "correct horse battery", "pytest"
        )
        await uow.commit()
    assert pair.access_token and pair.refresh_token


async def test_wrong_password_gives_same_error_as_unknown_email(identity_uow_factory):
    async with identity_uow_factory() as uow:
        with pytest.raises(AuthError, match="Invalid email or password"):
            await LoginUser(uow.session, TokenService()).execute("ada@example.com", "wrong password!!", None)
        with pytest.raises(AuthError, match="Invalid email or password"):
            await LoginUser(uow.session, TokenService()).execute("nobody@example.com", "any password 12", None)


async def test_refresh_rotation_consumes_old_token(identity_uow_factory):
    # login -> pair1; refresh with pair1 -> pair2
    # refresh with pair1 AGAIN -> AuthError AND session revoked
    ...


async def test_refresh_reuse_revokes_session_family(identity_uow_factory):
    # After reuse detection, even the NEWEST refresh token must fail.
    ...


async def test_logout_revokes_session(identity_uow_factory):
    # After logout, refresh with that token raises AuthError.
    ...
```

Fill in the `...` bodies following the docstring logic — writing these tests yourself is where the rotation semantics actually stick. The full matrix to cover:

- Valid rotation issues a new pair and consumes the old token.
- Reusing a rotated-out token raises `AuthError`, revokes the session, and invalidates even the newest token in the family.
- Expired refresh token revokes the session.
- Logged-out session rejects refresh.
- Tampered JWT, wrong audience, and wrong issuer are all rejected (unit level).
- `test_unscoped_connection_sees_nothing` from Chapter 2 still passes after the new tables.

Run everything:

```bash
uv run ruff check . && uv run mypy && uv run pytest
```

***

## 11. ADR and checklist

Create `docs/adr/0003-hybrid-jwt-access-rotating-refresh.md`:

```markdown
# ADR 0003: Short-lived JWT access tokens with rotating, server-tracked refresh tokens

- Status: Accepted
- Date: 2026-07-29

## Context
VaultLog manages secrets, so stolen credentials are a top-tier threat.
Pure stateless JWTs cannot be revoked; pure server sessions sacrifice
stateless verification for ordinary requests.

## Decision
- RS256 JWT access tokens, 10-minute TTL, verified without DB lookups.
- Opaque refresh tokens (384-bit random), SHA-256 hashed at rest,
  rotated on every use, delivered via HttpOnly Secure SameSite=Lax cookies
  scoped to /api/v1/auth.
- Refresh reuse revokes the entire session family.
- Identity/session tables are global (no RLS); access runs through a
  dedicated owner-role code path used ONLY for pre-tenant operations.

## Consequences
- Access tokens remain valid up to 10 minutes after revocation (accepted risk;
  sensitive operations will require step-up auth anyway).
- Token theft is detectable via reuse and recoverable via family revocation.
- The owner-role identity path must be reviewed as security-critical code.
```

## Completion checklist

- [ ] `keys/` is git-ignored; private key has mode 600.
- [ ] `app_user`, `membership`, `auth_session`, `refresh_token` migrated with correct RLS/grants.
- [ ] Registration enforces the password policy; errors are generic.
- [ ] Login runs a dummy verify for unknown users (timing side channel).
- [ ] Access tokens verify with pinned RS256, issuer, and audience.
- [ ] Refresh rotation consumes the old token in one transaction with `FOR UPDATE`.
- [ ] Reuse detection revokes the whole session family.
- [ ] Refresh cookie is HttpOnly, Secure, SameSite, path-scoped.
- [ ] The identity (owner-role) code path is used only for pre-tenant operations.
- [ ] `Principal.tenant_id` → `TenantContext` → UoW wiring works end to end.
- [ ] All unit and integration tests pass, including the rotation matrix.

## Chapter outcome

VaultLog now has a real identity system: passwords that resist offline cracking, access tokens that can't be forged or replayed across services, and refresh tokens whose theft is detectable and recoverable. Just as importantly, the verified tenant claim now drives the RLS context, closing the loop between authentication and database-enforced isolation.

**Chapter 4** builds on the `amr` claim and session model: TOTP enrollment with encrypted seeds, recovery codes, MFA-gated login via challenge tokens, and step-up authentication for the sensitive operations this whole design has been preparing for.

***

## Chapter 4 — MFA and step-up authentication

**Goal:** Implement TOTP-based two-factor authentication with encrypted seeds and one-time recovery codes, gate the login flow behind MFA for enrolled users, and add step-up authentication so sensitive operations require *recent* MFA proof rather than relying on how long ago the user logged in.

**Time budget:** 25–35 minutes.

**Why this matters for VaultLog specifically:** A leaked password must not be enough to reach secrets. And even a fully authenticated session must not be enough to delete a vault — if an attacker hijacks an unlocked laptop with a live session, step-up authentication is the control that stops them from destroying data.

***

## 1. The model: two separate concerns

Chapter 4 introduces two mechanisms that are easy to conflate. Keep them distinct in your mind and in your code:

| Mechanism | Question it answers | When | Output |
|---|---|---|---|
| **MFA at login** | "Is this really the account owner?" | During initial authentication | Access token with `amr: ["pwd", "totp"]` |
| **Step-up authentication** | "Is the account owner *present right now*?" | Before a sensitive action in an active session | Short-lived step-up proof scoped to the session |

A session authenticated with TOTP yesterday says nothing about who is at the keyboard today. That is why VaultLog requires step-up for: deleting secrets or vaults, removing members, changing owner roles, disabling MFA, regenerating recovery codes, and (later) rotating tenant encryption keys.

***

## 2. Install and model

```bash
uv add pyotp cryptography
```

(`cryptography` may already be present as a transitive dependency — adding it explicitly documents that VaultLog depends on it directly.)

### New tables

Two new tables, both **global identity data** (like `app_user`): the TOTP seed belongs to a *user*, not a tenant, and recovery codes likewise. No RLS policies — they join the owner-role identity code path from Chapter 3.

Add to `src/vaultlog/infrastructure/database/identity_models.py`:

```python
class TotpSecretModel(Base):
    __tablename__ = "totp_secret"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    encrypted_seed: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    seed_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecoveryCodeModel(Base):
    __tablename__ = "recovery_code"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

Imports needed at the top of the file: `LargeBinary` from `sqlalchemy`.

Generate and apply the migration with autogenerate:

```bash
uv run alembic revision -m "totp secrets and recovery codes" --autogenerate
```

**Review the generated file before applying it** — verify it creates only these two tables, then add the grants line manually (autogenerate never does this):

```python
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON totp_secret, recovery_code TO vaultlog_app")
```

```bash
uv run alembic upgrade head
```

### Configuration

Add to `.env` / `.env.example` and `Settings`:

```dotenv
# KEK for encrypting TOTP seeds (32 bytes, base64). Production: KMS.
MFA_KEK_B64=CHANGE_ME_32_BYTE_BASE64_KEY
STEP_UP_TOKEN_TTL_SECONDS=300
```

```python
mfa_kek_b64: str
step_up_token_ttl_seconds: int = 300
```

Generate a local key:

```bash
python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
```

***

## 3. Seed encryption

TOTP seeds are shared secrets — anyone holding a seed can generate valid codes forever. They must never be readable from a database dump alone. Encrypt them with AES-256-GCM under the MFA KEK, using the user ID as AAD so a seed row cannot be transplanted between users.

Create `src/vaultlog/infrastructure/security/seed_encryption.py`:

```python
from __future__ import annotations

import base64
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vaultlog.shared.config import get_settings

settings = get_settings()


class SeedDecryptionError(Exception):
    pass


def _kek() -> bytes:
    key = base64.b64decode(settings.mfa_kek_b64)
    if len(key) != 32:
        raise ValueError("MFA_KEK_B64 must decode to exactly 32 bytes")
    return key


def encrypt_seed(user_id: UUID, seed: str) -> tuple[bytes, bytes]:
    """Returns (nonce, ciphertext). AAD binds the ciphertext to this user."""
    nonce = os.urandom(12)
    aad = f"vaultlog:totp-seed:v1:{user_id}".encode()
    ciphertext = AESGCM(_kek()).encrypt(nonce, seed.encode(), aad)
    return nonce, ciphertext


def decrypt_seed(user_id: UUID, nonce: bytes, ciphertext: bytes) -> str:
    aad = f"vaultlog:totp-seed:v1:{user_id}".encode()
    try:
        return AESGCM(_kek()).decrypt(nonce, ciphertext, aad).decode()
    except Exception as exc:
        raise SeedDecryptionError("TOTP seed could not be decrypted") from exc
```

The AAD pattern here is exactly the one Chapter 6 will use for vault secrets — learn it once, apply it everywhere: **ciphertext is only valid for the context it was encrypted for.**

***

## 4. TOTP and recovery-code primitives

Create `src/vaultlog/infrastructure/security/mfa.py`:

```python
from __future__ import annotations

import hashlib
import secrets

import pyotp


def generate_totp_seed() -> str:
    return pyotp.random_base32()  # 160-bit random seed


def provisioning_uri(seed: str, email: str) -> str:
    return pyotp.TOTP(seed).provisioning_uri(name=email, issuer_name="VaultLog")


def verify_totp(seed: str, code: str) -> bool:
    # valid_window=1 accepts one adjacent 30s step for clock drift.
    return pyotp.TOTP(seed).verify(code.strip(), valid_window=1)


def generate_recovery_codes(count: int = 10) -> list[str]:
    """Human-readable: 10 chars, unambiguous alphabet, grouped for display."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
    return ["".join(secrets.choice(alphabet) for _ in range(10)) for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    normalized = code.strip().upper().replace("-", "").replace(" ", "")
    return hashlib.sha256(normalized.encode()).hexdigest()
```

Design decisions:

- **`valid_window=1`**, not more. Each extra window doubles the attack surface for guessing a code. Combined with rate limiting (Chapter 8), one window is the standard trade-off.
- **Recovery codes are random, high-entropy, and stored hashed.** A database leak must not reveal them. They are single-use — `used_at` set on redemption — and each redemption is auditable.
- Codes are 10 characters from a 32-symbol alphabet: ~50 bits of entropy, unguessable under rate limiting.

***

## 5. MFA enrollment and login use cases

Create `src/vaultlog/application/identity/mfa_use_cases.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.infrastructure.database.identity_models import (
    RecoveryCodeModel,
    TotpSecretModel,
    UserModel,
)
from vaultlog.infrastructure.security.mfa import (
    generate_recovery_codes,
    generate_totp_seed,
    hash_recovery_code,
    provisioning_uri,
    verify_totp,
)
from vaultlog.infrastructure.security.seed_encryption import decrypt_seed, encrypt_seed


class MfaError(Exception):
    pass


@dataclass(frozen=True)
class EnrollmentResult:
    provisioning_uri: str


class StartTotpEnrollment:
    """Creates or replaces an UNCONFIRMED seed. MFA is not enabled yet."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, user_id: uuid.UUID, email: str) -> EnrollmentResult:
        await self._session.execute(delete(TotpSecretModel).where(TotpSecretModel.user_id == user_id))
        seed = generate_totp_seed()
        nonce, ciphertext = encrypt_seed(user_id, seed)
        self._session.add(TotpSecretModel(user_id=user_id, encrypted_seed=ciphertext, seed_nonce=nonce))
        return EnrollmentResult(provisioning_uri=provisioning_uri(seed, email))


class ConfirmTotpEnrollment:
    """Proving possession of the seed activates MFA and issues recovery codes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def execute(self, user_id: uuid.UUID, code: str) -> list[str]:
        record = await self._session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == user_id, TotpSecretModel.confirmed.is_(False))
        )
        if record is None:
            raise MfaError("No pending enrollment")

        seed = decrypt_seed(user_id, record.seed_nonce, record.encrypted_seed)
        if not verify_totp(seed, code):
            raise MfaError("Invalid code")

        record.confirmed = True
        record.confirmed_at = datetime.now(UTC)

        user = await self._session.get(UserModel, user_id)
        user.mfa_enabled = True

        # Fresh recovery codes replace any previous set.
        await self._session.execute(delete(RecoveryCodeModel).where(RecoveryCodeModel.user_id == user_id))
        codes = generate_recovery_codes()
        for raw in codes:
            self._session.add(RecoveryCodeModel(user_id=user_id, code_hash=hash_recovery_code(raw)))
        return codes


class VerifyMfa:
    """Verifies a TOTP code OR a recovery code during login challenge."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def verify_totp_code(self, user_id: uuid.UUID, code: str) -> bool:
        record = await self._session.scalar(
            select(TotpSecretModel).where(TotpSecretModel.user_id == user_id, TotpSecretModel.confirmed.is_(True))
        )
        if record is None:
            return False
        seed = decrypt_seed(user_id, record.seed_nonce, record.encrypted_seed)
        return verify_totp(seed, code)

    async def redeem_recovery_code(self, user_id: uuid.UUID, code: str) -> bool:
        code_hash = hash_recovery_code(code)
        record = await self._session.scalar(
            select(RecoveryCodeModel).where(
                RecoveryCodeModel.user_id == user_id,
                RecoveryCodeModel.code_hash == code_hash,
                RecoveryCodeModel.used_at.is_(None),
            ).with_for_update()
        )
        if record is None:
            return False
        record.used_at = datetime.now(UTC)  # single use, enforced in-transaction
        return True
```

Enrollment is deliberately **two-phase**: a seed exists in an unconfirmed state until the user proves possession with a valid code. Without this, a user who scans the QR incorrectly (or whose phone eats the entry) would permanently lock themselves out the moment you set `mfa_enabled = true`. MFA is enabled *only after proof*.

***

## 6. The MFA challenge token

A user with MFA enabled who passes the password check is **not yet authenticated**. They must not receive access or refresh tokens. Instead they receive a short-lived, single-purpose challenge token that can do exactly one thing: submit an MFA code.

Add to `TokenService` in `infrastructure/security/tokens.py`:

```python
def mint_challenge_token(self, user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "purpose": "mfa-challenge",
        "amr": ["pwd"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, self._private_key, algorithm="RS256")


def verify_challenge_token(self, token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(
            token, self._public_key, algorithms=["RS256"],
            issuer=settings.jwt_issuer, audience=settings.jwt_audience,
            options={"require": ["exp", "sub", "purpose"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError("Invalid token") from exc
    if payload["purpose"] != "mfa-challenge":
        raise TokenValidationError("Invalid token")
    return uuid.UUID(payload["sub"])


def mint_step_up_token(self, user_id: uuid.UUID, session_id: uuid.UUID, purpose: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user_id),
        "sid": str(session_id),
        "purpose": purpose,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.step_up_token_ttl_seconds)).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, self._private_key, algorithm="RS256")


def verify_step_up_token(self, token: str, user_id: uuid.UUID, session_id: uuid.UUID, purpose: str) -> None:
    try:
        payload = jwt.decode(
            token, self._public_key, algorithms=["RS256"],
            issuer=settings.jwt_issuer, audience=settings.jwt_audience,
            options={"require": ["exp", "sub", "sid", "purpose"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError("Invalid token") from exc
    if (
        uuid.UUID(payload["sub"]) != user_id
        or uuid.UUID(payload["sid"]) != session_id
        or payload["purpose"] != purpose
    ):
        raise TokenValidationError("Invalid token")
```

Three distinct token types now exist. Never let one stand in for another:

| Token | Lifetime | Carries | Accepted by |
|---|---|---|---|
| Access | 10 min | `sub`, `tid`, `sid`, `amr` | All authenticated endpoints |
| MFA challenge | 5 min | `sub`, `purpose=mfa-challenge` | Only `POST /auth/mfa/verify` |
| Step-up | 5 min | `sub`, `sid`, `purpose` | Only the sensitive endpoints matching `purpose` |

The purpose claim is checked **server-side on every verification** — a challenge token cannot be replayed against a delete endpoint, and a step-up token for "disable MFA" cannot authorize "delete vault".

***

## 7. Modify the login flow

Update `LoginUser` from Chapter 3 to return a three-way result:

```python
@dataclass(frozen=True)
class LoginResult:
    kind: str                      # "tokens" or "mfa_required"
    pair: TokenPair | None = None
    challenge_token: str | None = None
```

Inside `LoginUser.execute`, after password verification succeeds:

```python
if user.mfa_enabled:
    return LoginResult(kind="mfa_required", challenge_token=self._tokens.mint_challenge_token(user.id))

# ... existing session + refresh-token creation ...
return LoginResult(kind="tokens", pair=TokenPair(access_token=access, refresh_token=raw_refresh))
```

Note what has *not* happened in the MFA branch: no session row, no refresh token, no access token. The user has proven knowledge of a password and nothing more. Then add the completion use case:

```python
class CompleteMfaLogin:
    """Exchanges a valid challenge token + TOTP/recovery code for full credentials."""

    def __init__(self, session: AsyncSession, tokens: TokenService) -> None:
        self._session = session
        self._tokens = tokens

    async def execute(
        self, challenge_token: str, code: str, user_agent: str | None
    ) -> TokenPair:
        try:
            user_id = self._tokens.verify_challenge_token(challenge_token)
        except TokenValidationError as exc:
            raise AuthError("Invalid or expired challenge") from exc

        user = await self._session.get(UserModel, user_id)
        if user is None or not user.is_active or not user.mfa_enabled:
            raise AuthError("Invalid or expired challenge")

        mfa = VerifyMfa(self._session)
        ok = await mfa.verify_totp_code(user_id, code) or await mfa.redeem_recovery_code(user_id, code)
        if not ok:
            raise AuthError("Invalid code")

        # Full session creation — identical to LoginUser's post-password path,
        # but the access token now carries amr=("pwd", "totp").
        tenant_id = await self._session.scalar(
            select(MembershipModel.tenant_id).where(MembershipModel.user_id == user.id).limit(1)
        )
        if tenant_id is None:
            raise AuthError("Invalid or expired challenge")

        session = AuthSessionModel(user_id=user.id, user_agent=user_agent)
        self._session.add(session)
        await self._session.flush()

        raw_refresh = self._tokens.generate_refresh_token()
        self._session.add(
            RefreshTokenModel(
                session_id=session.id,
                token_hash=self._tokens.hash_refresh_token(raw_refresh),
                expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
            )
        )
        access = self._tokens.mint_access_token(user.id, tenant_id, session.id, amr=("pwd", "totp"))
        return TokenPair(access_token=access, refresh_token=raw_refresh)
```

The `amr` ("authentication methods reference") claim in the final access token is your audit trail of *how* strongly this session was authenticated — Chapter 5's authorization layer can require `totp in amr` for elevated operations if you choose.

***

## 8. Step-up authentication

The step-up use case verifies a fresh TOTP code against an **active session** and returns the purpose-scoped step-up token:

```python
class StepUp:
    def __init__(self, session: AsyncSession, tokens: TokenService) -> None:
        self._session = session
        self._tokens = tokens

    async def execute(self, principal_user_id: uuid.UUID, session_id: uuid.UUID, code: str, purpose: str) -> str:
        mfa = VerifyMfa(self._session)
        ok = await mfa.verify_totp_code(principal_user_id, code)
        if not ok:
            raise MfaError("Invalid code")
        return self._tokens.mint_step_up_token(principal_user_id, session_id, purpose)
```

And the FastAPI dependency that sensitive endpoints will require:

```python
# In presentation/dependencies.py:

class StepUpPurpose(str, Enum):
    DELETE_VAULT = "step-up:delete-vault"
    DELETE_SECRET = "step-up:delete-secret"
    REMOVE_MEMBER = "step-up:remove-member"
    MANAGE_MFA = "step-up:manage-mfa"
    ROTATE_KEYS = "step-up:rotate-keys"


def require_step_up(purpose: StepUpPurpose):
    async def dependency(
        request: Request,
        principal: Principal = Depends(current_principal),
    ) -> Principal:
        token = request.headers.get("X-Step-Up-Token")
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Step-up authentication required",
            )
        try:
            TokenService().verify_step_up_token(token, principal.user_id, principal.session_id, purpose.value)
        except TokenValidationError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Step-up authentication required",
            ) from None
        return principal

    return dependency
```

Why a dedicated `X-Step-Up-Token` header rather than embedding step-up state in the access token? Because access tokens are minted at login/refresh time — long before the user steps up — and revoking or re-minting them per action would couple unrelated concerns. A separate, deliberately-scoped proof keeps the access token stable and the step-up semantics explicit.

Note the dependency returns 403, not 401: the caller *is* authenticated; they lack the required authentication *strength*. Frontend clients should treat this 403 as the signal to show the TOTP prompt, then retry with the header.

**Important:** the router dependency is a gate, not the policy. When Chapter 5 adds the service-layer authorizer, sensitive operations must *also* assert step-up proof in the use case — defense in depth means the check survives a future router that forgets the dependency.

***

## 9. Router endpoints

Add to `src/vaultlog/presentation/api/v1/auth.py`:

```python
class MfaVerifyRequest(BaseModel):
    challenge_token: str
    code: str = Field(min_length=6, max_length=20)


class StepUpRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)
    purpose: StepUpPurpose


class EnrollmentResponse(BaseModel):
    provisioning_uri: str


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


@router.post("/mfa/verify", response_model=AccessTokenResponse)
async def mfa_verify(
    body: MfaVerifyRequest, request: Request, response: Response,
    identity_uow=Depends(get_identity_uow),
) -> AccessTokenResponse:
    async with identity_uow as uow:
        try:
            pair = await CompleteMfaLogin(uow.session, TokenService()).execute(
                body.challenge_token, body.code, request.headers.get("user-agent")
            )
        except AuthError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid code")
        await uow.commit()
    _set_refresh_cookie(response, pair)
    return AccessTokenResponse(access_token=pair.access_token, expires_in=600)


@router.post("/mfa/enroll", response_model=EnrollmentResponse)
async def mfa_enroll(
    principal: Principal = Depends(current_principal),
    identity_uow=Depends(get_identity_uow),
) -> EnrollmentResponse:
    async with identity_uow as uow:
        user = await uow.session.get(UserModel, principal.user_id)
        result = await StartTotpEnrollment(uow.session).execute(principal.user_id, user.email)
        await uow.commit()
    return EnrollmentResponse(provisioning_uri=result.provisioning_uri)


@router.post("/mfa/confirm", response_model=RecoveryCodesResponse)
async def mfa_confirm(
    code: str = Body(embed=True, min_length=6, max_length=8),
    principal: Principal = Depends(current_principal),
    identity_uow=Depends(get_identity_uow),
) -> RecoveryCodesResponse:
    async with identity_uow as uow:
        try:
            codes = await ConfirmTotpEnrollment(uow.session).execute(principal.user_id, code)
        except MfaError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")
        await uow.commit()
    # Shown ONCE. Never logged, never retrievable again.
    return RecoveryCodesResponse(recovery_codes=codes)


@router.post("/step-up/verify")
async def step_up_verify(
    body: StepUpRequest,
    principal: Principal = Depends(current_principal),
    identity_uow=Depends(get_identity_uow),
) -> dict:
    async with identity_uow as uow:
        try:
            token = await StepUp(uow.session, TokenService()).execute(
                principal.user_id, principal.session_id, body.code, body.purpose.value
            )
        except MfaError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid code")
        await uow.commit()
    return {"step_up_token": token, "expires_in": 300}


@router.delete("/mfa", status_code=status.HTTP_204_NO_CONTENT)
async def mfa_disable(
    principal: Principal = Depends(require_step_up(StepUpPurpose.MANAGE_MFA)),
    identity_uow=Depends(get_identity_uow),
) -> None:
    """Disabling MFA is itself a sensitive operation — it requires step-up."""
    async with identity_uow as uow:
        await uow.session.execute(delete(TotpSecretModel).where(TotpSecretModel.user_id == principal.user_id))
        await uow.session.execute(delete(RecoveryCodeModel).where(RecoveryCodeModel.user_id == principal.user_id))
        user = await uow.session.get(UserModel, principal.user_id)
        user.mfa_enabled = False
        await uow.commit()
```

Update the `/login` handler to branch on `LoginResult.kind`: return the token pair directly for `tokens`, or `{"mfa_required": true, "challenge_token": ...}` for `mfa_required` — and in the MFA branch, **do not** set the refresh cookie.

Also note the subtle design in `mfa_disable`: it is guarded by `require_step_up(StepUpPurpose.MANAGE_MFA)`, meaning an attacker with a hijacked session cannot strip the account's second factor without knowing a current TOTP code — which they cannot produce precisely because the seed is encrypted and the authenticator is elsewhere. The same gate will protect recovery-code regeneration.

***

## 10. Tests

Create `tests/unit/test_mfa.py`:

```python
import uuid

import pyotp
import pytest

from vaultlog.infrastructure.security.mfa import (
    generate_recovery_codes,
    generate_totp_seed,
    hash_recovery_code,
    verify_totp,
)
from vaultlog.infrastructure.security.seed_encryption import (
    SeedDecryptionError,
    decrypt_seed,
    encrypt_seed,
)


def test_totp_verify_accepts_current_code() -> None:
    seed = generate_totp_seed()
    code = pyotp.TOTP(seed).now()
    assert verify_totp(seed, code)


def test_totp_verify_rejects_wrong_code() -> None:
    seed = generate_totp_seed()
    assert not verify_totp(seed, "000000")


def test_seed_encryption_round_trip() -> None:
    uid = uuid.uuid4()
    nonce, ciphertext = encrypt_seed(uid, "JBSWY3DPEHPK3PXP")
    assert decrypt_seed(uid, nonce, ciphertext) == "JBSWY3DPEHPK3PXP"


def test_seed_ciphertext_bound_to_user() -> None:
    """AAD binding: a seed row transplanted to another user must fail."""
    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    nonce, ciphertext = encrypt_seed(uid_a, "JBSWY3DPEHPK3PXP")
    with pytest.raises(SeedDecryptionError):
        decrypt_seed(uid_b, nonce, ciphertext)


def test_recovery_code_hash_normalizes_input() -> None:
    code = "ABCDE-23456"
    assert hash_recovery_code(code) == hash_recovery_code("abcde23456")


def test_recovery_codes_are_unique_and_unambiguous() -> None:
    codes = generate_recovery_codes()
    assert len(set(codes)) == 10
    for code in codes:
        assert "0" not in code and "O" not in code and "1" not in code and "I" not in code
```

Create `tests/integration/test_mfa_flows.py` covering the full matrix against the Compose database:

- Enroll → confirm with a valid code → `mfa_enabled` is true and 10 recovery codes exist.
- Confirm with a wrong code → `MfaError`, MFA stays disabled.
- Login with MFA enabled → returns `mfa_required` + challenge token, **no session row created**.
- Complete MFA with valid TOTP → token pair issued, access token claims include `amr: ["pwd", "totp"]`.
- Complete MFA with a wrong code → `AuthError`.
- Complete MFA with a recovery code → succeeds **and** that code cannot be used a second time.
- Challenge token rejected by `/auth/refresh` and ordinary endpoints (wrong `purpose` claim).
- Step-up with valid code → token verifies for the requested purpose, **fails** for any other purpose.
- Step-up token from session A rejected when presented with session B's access token.
- Challenge token used after its 5-minute expiry → rejected.

Use `pyotp.TOTP(seed).now()` to generate valid codes in tests; decrypt the seed via `decrypt_seed` when you need it from the database row.

Run the full suite:

```bash
uv run ruff check . && uv run mypy && uv run pytest
```

***

## 11. ADR and checklist

Create `docs/adr/0004-totp-mfa-and-step-up-authentication.md`:

```markdown
# ADR 0004: TOTP MFA with challenge tokens, plus purpose-scoped step-up tokens

- Status: Accepted
- Date: 2026-07-29

## Context
Secrets management demands that password compromise alone cannot grant access,
and that sensitive actions in an existing session require fresh proof of
identity. Session hijacking must not enable destructive operations.

## Decision
- TOTP (RFC 6238) as the second factor; seeds encrypted at rest with
  AES-256-GCM under a dedicated KEK, AAD-bound to the user ID.
- Two-phase enrollment: MFA activates only after a valid code is presented.
- MFA-enabled logins receive a 5-minute single-purpose challenge token
  (purpose=mfa-challenge); no session or refresh token exists until MFA passes.
- Recovery codes: 10 single-use codes, SHA-256 hashed at rest, shown once.
- Step-up: 5-minute JWT bound to user, session, and a specific purpose;
  required for deleting vaults/secrets, removing members, key rotation,
  and MFA management. Delivered via X-Step-Up-Token header.
- WebAuthn/passkeys deferred; the challenge/step-up architecture is designed
  to accommodate them later (challenge token gains a webauthn branch).

## Consequences
- Clients must handle the two-step login and the 403 -> step-up retry flow.
- TOTP seed loss without recovery codes means account recovery is a
  manual, organization-owner-mediated process (documented runbook needed).
- Clock drift tolerated to one 30-second window; rate limiting (Chapter 8)
  is load-bearing for brute-force resistance.
```

## Completion checklist

- [ ] Migration applied; grants added to the autogenerated revision.
- [ ] `MFA_KEK_B64` set locally and git-ignored; never logged.
- [ ] Seeds encrypted at rest; ciphertext provably bound to user ID (AAD test).
- [ ] Enrollment is two-phase; MFA activates only on proof.
- [ ] MFA-enabled login creates no session until the challenge completes.
- [ ] Challenge, access, and step-up tokens are mutually non-interchangeable (purpose tests).
- [ ] Recovery codes are single-use, hashed, and shown exactly once.
- [ ] Step-up tokens are bound to user + session + purpose, 5-minute TTL.
- [ ] Sensitive-operation dependency returns 403 (not 401) without proof.
- [ ] Disabling MFA itself requires step-up.
- [ ] Full test matrix passes.

## Chapter outcome

Authentication in VaultLog is now *layered*: possession of a password, possession of a TOTP device, and freshness of proof are three separate, verifiable facts. The session model records how strongly it was authenticated (`amr`), and destructive operations demand recent proof regardless of session age.

**Chapter 5** puts these mechanisms to work on real resources: the vault and grant tables, the RBAC policy service, vault CRUD, and the authorization matrix tests — the point where `Principal`, roles, and step-up proofs converge into actual access control decisions.

# VaultLog Backend
## Chapter 5 — Vaults, grants, and the RBAC policy service

**Goal:** Implement vault and vault-grant tables (fully RLS-protected), a centralized authorization service that combines organization roles with per-vault permissions, and the vault CRUD endpoints. By the end, every access decision in VaultLog flows through one auditable policy function — and denial is proven by a complete test matrix.

**Time budget:** 30–40 minutes.

**Why centralize authorization now:** Up to this point, the only question was "who are you?" From this chapter onward, the question becomes "what may you do?" If that logic scatters across routers as inline `if role == "admin"` checks, it will drift, rot, and eventually be wrong in exactly the endpoint that matters. One policy service, tested exhaustively, is the senior-engineer answer.

***

## 1. The authorization model

VaultLog uses **two-axis RBAC**:

```text
Organization role (from membership)     Vault grant (per-vault, per-membership)
        |                                       |
        +----------------+----------------------+
                         v
               PolicyService.decide()
                         v
              allow  |  deny (403)
```

- **Organization role** — `owner`, `admin`, `member`, `viewer` — sets the baseline for what a user can do *within the org*: manage members, create vaults, administer grants.
- **Vault grant** — `read`, `write`, `admin` — controls access to the *contents* of a specific vault. A member of the organization is not automatically entitled to every vault; vaults are how secrets get compartmentalized inside a tenant.

The decisive rule: **organization owner/admin can administer everything in their org; everyone else needs an explicit vault grant.** Viewers never receive grants above `read`.

### The full permission matrix

This table is the specification. The tests in section 7 are generated from it, and any future behavior change means changing this table first.

| Action | owner | admin | member | viewer |
|---|---|---|---|---|
| List org vaults | ✅ | ✅ | ✅ (granted only) | ✅ (granted only) |
| Create vault | ✅ | ✅ | ✅ | ❌ |
| Rename/delete vault | ✅ | ✅ | ❌ | ❌ |
| Manage vault grants | ✅ | ✅ | ❌ | ❌ |
| Read secret metadata | ✅ | ✅ | grant ≥ read | grant ≥ read |
| Create/rotate secret | ✅ | ✅ | grant ≥ write | ❌ |
| Delete secret (step-up) | ✅ | ✅ | grant = admin | ❌ |
| Invite/remove member | ✅ | ✅ (not owners) | ❌ | ❌ |
| Manage MFA, delete org | ✅ (step-up) | ❌ | ❌ | ❌ |

Two subtleties worth noticing:

- **Delete secret requires `admin` vault grant for members**, not merely `write` — destruction is a higher bar than modification.
- **Admins cannot remove owners.** Ownership transitions are owner-only, step-up-gated operations.

***

## 2. Schema: vaults and grants

Add to `src/vaultlog/infrastructure/database/models.py` (alongside the Chapter 2 `OrganizationModel` and `VaultModel`, which we now extend — replace the old minimal `VaultModel` with this fuller version):

```python
from sqlalchemy import CheckConstraint, ForeignKey, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid
from datetime import datetime

from vaultlog.infrastructure.database.base import Base


class VaultModel(Base):
    __tablename__ = "vault"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("length(name) >= 1", name="ck_vault_name_nonempty"),
    )


class VaultGrantModel(Base):
    __tablename__ = "vault_grant"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    vault_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vault.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("membership.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    permission: Mapped[str] = mapped_column(String(10), nullable=False)
    granted_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("permission IN ('read','write','admin')", name="ck_vault_grant_permission"),
    )
```

Note the deliberate redundancy: `vault_grant.tenant_id` duplicates what could be reached via the vault join. RLS policies filter on the table's *own* `tenant_id` column — a policy that required a join to evaluate would be both slow and fragile. Every tenant-owned row carries its tenant identity denormalized. This is a standard RLS design trade: a little redundancy for airtight, fast isolation.

Also note `deleted_at` on vault: deletion is **soft**. Hard-deleting a vault would cascade-destroy secrets and their version history; for a security product, retention and recoverability win. A scheduled purge job (much later) handles true removal per retention policy.

### Migration

Autogenerate, then review and extend:

```bash
uv run alembic revision -m "vaults and vault grants" --autogenerate
```

The generated diff should show: altered `vault` (new columns) and new `vault_grant`. Add the security-relevant statements the autogenerator cannot know about:

```python
# In upgrade(), after the autogenerated table operations:

# Grants
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON vault_grant TO vaultlog_app")

# RLS for the new table
op.execute("ALTER TABLE vault_grant ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE vault_grant FORCE ROW LEVEL SECURITY")
op.execute("""
    CREATE POLICY tenant_isolation ON vault_grant
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
""")

# Unique constraints the ORM args cover in metadata but be explicit in review:
#   uq_vault_tenant_name on (tenant_id, name) — scoped to tenant, not global.
#   uq_vault_grant on (vault_id, membership_id) — one grant per member per vault.
```

Add these uniques to the models' `__table_args__` too (`UniqueConstraint("tenant_id", "name")` on vault, `UniqueConstraint("vault_id", "membership_id")` on grant) so metadata and migration agree. Vault names unique *per tenant*, not globally — two organizations may both reasonably want a vault named "Production".

```bash
uv run alembic upgrade head
```

***

## 3. Domain vocabulary

Keep authorization language in the domain layer, framework-free — `src/vaultlog/domain/access/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class VaultPermission(StrEnum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"

    @property
    def rank(self) -> int:
        return {"read": 1, "write": 2, "admin": 3}[self.value]


class Action(StrEnum):
    VAULT_LIST = "vault.list"
    VAULT_CREATE = "vault.create"
    VAULT_UPDATE = "vault.update"
    VAULT_DELETE = "vault.delete"
    GRANT_MANAGE = "grant.manage"
    SECRET_READ_META = "secret.read_meta"
    SECRET_REVEAL = "secret.reveal"
    SECRET_WRITE = "secret.write"
    SECRET_DELETE = "secret.delete"
    MEMBER_INVITE = "member.invite"
    MEMBER_REMOVE = "member.remove"


@dataclass(frozen=True)
class AccessContext:
    user_id: UUID
    tenant_id: UUID
    role: OrgRole
    vault_permission: VaultPermission | None  # None = no grant on this vault
```

`StrEnum` keeps values serialized as plain strings in the database while giving you exhaustiveness checking in mypy. The `rank` property turns "at least write?" into a simple integer comparison — grant hierarchy is ordinal, and encoding it as such prevents the classic bug of writing `permission == "write"` and forgetting `admin` should also qualify.

***

## 4. The policy service

This is the heart of the chapter — `src/vaultlog/application/access/policy_service.py`:

```python
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.domain.access.models import (
    AccessContext,
    Action,
    OrgRole,
    VaultPermission,
)
from vaultlog.infrastructure.database.identity_models import MembershipModel
from vaultlog.infrastructure.database.models import VaultGrantModel, VaultModel


class ForbiddenError(Exception):
    """Raised for every denial. Routers map this to 403 — never leak *why*."""


class NotFoundError(Exception):
    """Resource absent OR invisible. Indistinguishable from the caller's view."""


def _org_allows(role: OrgRole, action: Action) -> bool:
    """Baseline org-role permissions, independent of vault grants."""
    match action:
        case Action.VAULT_LIST | Action.SECRET_READ_META:
            return True  # members/viewers see only what grants reveal (filtered downstream)
        case Action.VAULT_CREATE:
            return role in (OrgRole.OWNER, OrgRole.ADMIN, OrgRole.MEMBER)
        case (
            Action.VAULT_UPDATE | Action.VAULT_DELETE | Action.GRANT_MANAGE
            | Action.MEMBER_INVITE
        ):
            return role in (OrgRole.OWNER, OrgRole.ADMIN)
        case Action.MEMBER_REMOVE:
            return role in (OrgRole.OWNER, OrgRole.ADMIN)  # target-role check happens separately
        case Action.SECRET_WRITE:
            return role in (OrgRole.OWNER, OrgRole.ADMIN)
        case Action.SECRET_DELETE:
            return role in (OrgRole.OWNER, OrgRole.ADMIN)
        case _:
            return False


def _grant_allows(permission: VaultPermission | None, action: Action) -> bool:
    if permission is None:
        return False
    match action:
        case Action.SECRET_READ_META | Action.SECRET_REVEAL:
            return permission.rank >= VaultPermission.READ.rank
        case Action.SECRET_WRITE:
            return permission.rank >= VaultPermission.WRITE.rank
        case Action.SECRET_DELETE:
            return permission.rank >= VaultPermission.ADMIN.rank
        case _:
            return False


class PolicyService:
    """Single entry point for every authorization decision.

    Runs inside the tenant-scoped UoW: membership and grant queries are
    already RLS-filtered to principal.tenant_id, so a forged cross-tenant
    ID simply finds nothing.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_role(self, user_id: UUID, tenant_id: UUID) -> OrgRole | None:
        role = await self._session.scalar(
            select(MembershipModel.role).where(
                MembershipModel.user_id == user_id,
                MembershipModel.tenant_id == tenant_id,
            )
        )
        return OrgRole(role) if role else None

    async def _load_grant(self, user_id: UUID, tenant_id: UUID, vault_id: UUID) -> VaultPermission | None:
        permission = await self._session.scalar(
            select(VaultGrantModel.permission)
            .join(MembershipModel, MembershipModel.id == VaultGrantModel.membership_id)
            .where(
                VaultGrantModel.vault_id == vault_id,
                VaultGrantModel.tenant_id == tenant_id,
                MembershipModel.user_id == user_id,
            )
        )
        return VaultPermission(permission) if permission else None

    async def require_org(self, user_id: UUID, tenant_id: UUID, action: Action) -> AccessContext:
        role = await self._load_role(user_id, tenant_id)
        if role is None or not _org_allows(role, action):
            raise ForbiddenError("Access denied")
        return AccessContext(user_id=user_id, tenant_id=tenant_id, role=role, vault_permission=None)

    async def require_vault(
        self, user_id: UUID, tenant_id: UUID, vault_id: UUID, action: Action
    ) -> AccessContext:
        # 1. Existence check inside RLS scope: cross-tenant IDs are invisible.
        vault = await self._session.scalar(
            select(VaultModel.id).where(
                VaultModel.id == vault_id,
                VaultModel.tenant_id == tenant_id,
                VaultModel.deleted_at.is_(None),
            )
        )
        if vault is None:
            raise NotFoundError("Vault not found")

        # 2. Role + grant.
        role = await self._load_role(user_id, tenant_id)
        if role is None:
            raise ForbiddenError("Access denied")

        if role in (OrgRole.OWNER, OrgRole.ADMIN):
            return AccessContext(user_id, tenant_id, role, VaultPermission.ADMIN)

        permission = await self._load_grant(user_id, tenant_id, vault_id)
        if not _grant_allows(permission, action):
            raise ForbiddenError("Access denied")

        return AccessContext(user_id, tenant_id, role, permission)

    async def list_accessible_vault_ids(self, user_id: UUID, tenant_id: UUID) -> list[UUID] | None:
        """None = unrestricted (owner/admin). List = grant-scoped vault IDs."""
        role = await self._load_role(user_id, tenant_id)
        if role is None:
            raise ForbiddenError("Access denied")
        if role in (OrgRole.OWNER, OrgRole.ADMIN):
            return None
        rows = await self._session.scalars(
            select(VaultGrantModel.vault_id)
            .join(MembershipModel, MembershipModel.id == VaultGrantModel.membership_id)
            .where(VaultGrantModel.tenant_id == tenant_id, MembershipModel.user_id == user_id)
        )
        return list(rows)
```

Read this code slowly — it encodes several decisions that separate careful authorization from hopeful authorization:

1. **Existence and authorization are separate failures.** A nonexistent (or cross-tenant) vault raises `NotFoundError` → 404. An existing vault without permission raises `ForbiddenError` → 403. This avoids the classic IDOR information leak where 403 confirms "this UUID exists but isn't yours." For the *vault lookup itself*, cross-tenant UUIDs are indistinguishable from garbage — both 404.

2. **Owner/admin short-circuit grants.** Org administrators get `VaultPermission.ADMIN` synthesized without a database grant row. If you instead required explicit grant rows for admins, removing someone's admin role would leave stale grants behind — orphaned permissions are how privilege accretion happens.

3. **Every query is tenant-pinned twice**: explicitly (`tenant_id == tenant_id`) for the planner and readability, and implicitly via RLS underneath. If either layer regresses, the other holds.

4. **`list_accessible_vault_ids` returns `None` for unrestricted.** The alternative — returning *all* IDs — would require enumerating vaults for admins and would subtly change query shape by role. `None` is an honest "no filter needed."

***

## 5. Vault use cases

`src/vaultlog/application/vaults/use_cases.py`:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.application.access.policy_service import PolicyService
from vaultlog.domain.access.models import Action, VaultPermission
from vaultlog.infrastructure.database.identity_models import MembershipModel
from vaultlog.infrastructure.database.models import VaultGrantModel, VaultModel


@dataclass(frozen=True)
class VaultView:
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime


class CreateVault:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._policy = PolicyService(session)

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID, name: str, description: str | None) -> VaultView:
        await self._policy.require_org(user_id, tenant_id, Action.VAULT_CREATE)

        vault = VaultModel(
            tenant_id=tenant_id, name=name, description=description,
            created_by_user_id=user_id,
        )
        self._session.add(vault)
        await self._session.flush()

        # Creator receives an explicit admin grant — their access survives
        # any future change to their org role (e.g., member -> viewer).
        membership_id = await self._session.scalar(
            select(MembershipModel.id).where(
                MembershipModel.user_id == user_id,
                MembershipModel.tenant_id == tenant_id,
            )
        )
        self._session.add(
            VaultGrantModel(
                tenant_id=tenant_id, vault_id=vault.id, membership_id=membership_id,
                permission=VaultPermission.ADMIN.value, granted_by_user_id=user_id,
            )
        )
        return VaultView(vault.id, vault.name, vault.description, vault.created_at)


class ListVaults:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._policy = PolicyService(session)

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> list[VaultView]:
        allowed_ids = await self._policy.list_accessible_vault_ids(user_id, tenant_id)

        stmt = select(VaultModel).where(
            VaultModel.tenant_id == tenant_id,
            VaultModel.deleted_at.is_(None),
        )
        if allowed_ids is not None:  # grant-scoped member/viewer
            stmt = stmt.where(VaultModel.id.in_(allowed_ids))

        rows = await self._session.scalars(stmt.order_by(VaultModel.name))
        return [VaultView(v.id, v.name, v.description, v.created_at) for v in rows]


class DeleteVault:
    """Soft delete, step-up enforced at the router (and re-asserted here)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._policy = PolicyService(session)

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID, vault_id: uuid.UUID, *, step_up_proven: bool) -> None:
        if not step_up_proven:
            raise ForbiddenError("Step-up authentication required")
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.VAULT_DELETE)

        vault = await self._session.get(VaultModel, vault_id)
        vault.deleted_at = datetime.now(UTC)
        # Audit ledger entry lands here in Chapter 7, in this same transaction.


class ManageGrant:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._policy = PolicyService(session)

    async def grant(
        self, actor_user_id: uuid.UUID, tenant_id: uuid.UUID, vault_id: uuid.UUID,
        target_membership_id: uuid.UUID, permission: VaultPermission,
    ) -> None:
        await self._policy.require_vault(actor_user_id, tenant_id, vault_id, Action.GRANT_MANAGE)

        # Target membership must belong to THIS tenant — RLS makes a forged
        # cross-tenant membership_id invisible, so this scalar returns None.
        target_tenant = await self._session.scalar(
            select(MembershipModel.tenant_id).where(MembershipModel.id == target_membership_id)
        )
        if target_tenant != tenant_id:
            raise NotFoundError("Membership not found")

        existing = await self._session.scalar(
            select(VaultGrantModel).where(
                VaultGrantModel.vault_id == vault_id,
                VaultGrantModel.membership_id == target_membership_id,
            )
        )
        if existing is not None:
            existing.permission = permission.value
        else:
            self._session.add(
                VaultGrantModel(
                    tenant_id=tenant_id, vault_id=vault_id,
                    membership_id=target_membership_id,
                    permission=permission.value,
                    granted_by_user_id=actor_user_id,
                )
            )

    async def revoke(
        self, actor_user_id: uuid.UUID, tenant_id: uuid.UUID,
        vault_id: uuid.UUID, target_membership_id: uuid.UUID,
    ) -> None:
        await self._policy.require_vault(actor_user_id, tenant_id, vault_id, Action.GRANT_MANAGE)
        grant = await self._session.scalar(
            select(VaultGrantModel).where(
                VaultGrantModel.vault_id == vault_id,
                VaultGrantModel.membership_id == target_membership_id,
                VaultGrantModel.tenant_id == tenant_id,
            )
        )
        if grant is None:
            raise NotFoundError("Grant not found")
        await self._session.delete(grant)
```

Two patterns to absorb:

- **Step-up is asserted in the use case, not only the router.** `DeleteVault.execute` takes `step_up_proven: bool` and refuses without it. This is the defense-in-depth promised in Chapter 4 — a future endpoint variant that forgets the dependency still cannot delete. The router dependency *and* the service check draw from the same verified token.
- **Grant upsert, not blind insert.** Re-granting an existing member changes their permission rather than crashing on the unique constraint. Revocation of a nonexistent grant is a 404, keeping the API honest about state.

***

## 6. Router endpoints

`src/vaultlog/presentation/api/v1/vaults.py`:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from vaultlog.application.access.policy_service import ForbiddenError, NotFoundError
from vaultlog.application.vaults.use_cases import (
    CreateVault, DeleteVault, ListVaults, ManageGrant,
)
from vaultlog.domain.access.models import VaultPermission
from vaultlog.presentation.dependencies import (
    Principal, StepUpPurpose, current_principal, require_step_up,
    get_session_factory, get_tenant_uow,
)

router = APIRouter(prefix="/vaults", tags=["vaults"])


class VaultCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)


class VaultResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: str


class GrantRequest(BaseModel):
    membership_id: uuid.UUID
    permission: VaultPermission


@router.post("", response_model=VaultResponse, status_code=status.HTTP_201_CREATED)
async def create_vault(
    body: VaultCreateRequest,
    principal: Principal = Depends(current_principal),
    tenant_uow=Depends(get_tenant_uow),
) -> VaultResponse:
    async with tenant_uow as uow:
        try:
            view = await CreateVault(uow.session).execute(
                principal.user_id, principal.tenant_id, body.name, body.description
            )
        except ForbiddenError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        # Audit event write will join this transaction in Chapter 7.
        await uow.commit()
    return VaultResponse(id=view.id, name=view.name, description=view.description, created_at=view.created_at.isoformat())


@router.get("", response_model=list[VaultResponse])
async def list_vaults(
    principal: Principal = Depends(current_principal),
    tenant_uow=Depends(get_tenant_uow),
) -> list[VaultResponse]:
    async with tenant_uow as uow:
        try:
            views = await ListVaults(uow.session).execute(principal.user_id, principal.tenant_id)
        except ForbiddenError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        # Read-only: no commit needed; __aexit__ rolls back cleanly.
    return [VaultResponse(id=v.id, name=v.name, description=v.description, created_at=v.created_at.isoformat()) for v in views]


@router.delete("/{vault_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vault(
    vault_id: uuid.UUID,
    principal: Principal = Depends(require_step_up(StepUpPurpose.DELETE_VAULT)),
    tenant_uow=Depends(get_tenant_uow),
) -> None:
    async with tenant_uow as uow:
        try:
            await DeleteVault(uow.session).execute(
                principal.user_id, principal.tenant_id, vault_id, step_up_proven=True
            )
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vault not found")
        except ForbiddenError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        await uow.commit()


@router.post("/{vault_id}/grants", status_code=status.HTTP_204_NO_CONTENT)
async def upsert_grant(
    vault_id: uuid.UUID, body: GrantRequest,
    principal: Principal = Depends(current_principal),
    tenant_uow=Depends(get_tenant_uow),
) -> None:
    async with tenant_uow as uow:
        try:
            await ManageGrant(uow.session).grant(
                principal.user_id, principal.tenant_id, vault_id,
                body.membership_id, body.permission,
            )
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        except ForbiddenError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        await uow.commit()


@router.delete("/{vault_id}/grants/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_grant(
    vault_id: uuid.UUID, membership_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    tenant_uow=Depends(get_tenant_uow),
) -> None:
    async with tenant_uow as uow:
        try:
            await ManageGrant(uow.session).revoke(
                principal.user_id, principal.tenant_id, vault_id, membership_id
            )
        except NotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        except ForbiddenError:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        await uow.commit()
```

Note the wiring detail that makes all of this coherent: `get_tenant_uow` is the dependency that builds `TenantContext(tenant_id=principal.tenant_id)` internally and yields the open UoW — the Chapter 3 chain made reusable. Routers never construct tenant context themselves. And the delete endpoint's principal comes through `require_step_up(...)`, so by the time the handler runs, **three** facts are established: valid access token, tenant membership implied by token claims, and fresh TOTP proof for this exact purpose.

Register the router in `main.py`.

***

## 7. The authorization test matrix

This is where Chapter 5 earns its keep. Write the matrix as data, not as 40 hand-copied test functions — `tests/integration/test_authorization_matrix.py`:

```python
import uuid

import pytest

from vaultlog.domain.access.models import Action, OrgRole, VaultPermission

# (role, vault_grant, action, expected)
MATRIX: list[tuple[OrgRole, VaultPermission | None, Action, bool]] = [
    # Owner/admin: unrestricted within the tenant
    (OrgRole.OWNER, None, Action.VAULT_CREATE, True),
    (OrgRole.OWNER, None, Action.VAULT_DELETE, True),
    (OrgRole.OWNER, None, Action.GRANT_MANAGE, True),
    (OrgRole.OWNER, None, Action.SECRET_DELETE, True),
    (OrgRole.ADMIN, None, Action.VAULT_CREATE, True),
    (OrgRole.ADMIN, None, Action.SECRET_WRITE, True),
    (OrgRole.ADMIN, None, Action.SECRET_DELETE, True),
    # Member: grant-driven
    (OrgRole.MEMBER, None, Action.SECRET_READ_META, False),      # no grant -> nothing
    (OrgRole.MEMBER, VaultPermission.READ, Action.SECRET_READ_META, True),
    (OrgRole.MEMBER, VaultPermission.READ, Action.SECRET_WRITE, False),
    (OrgRole.MEMBER, VaultPermission.WRITE, Action.SECRET_WRITE, True),
    (OrgRole.MEMBER, VaultPermission.WRITE, Action.SECRET_DELETE, False),  # delete needs admin grant
    (OrgRole.MEMBER, VaultPermission.ADMIN, Action.SECRET_DELETE, True),
    (OrgRole.MEMBER, None, Action.GRANT_MANAGE, False),
    (OrgRole.MEMBER, None, Action.VAULT_DELETE, False),
    # Viewer: read-only, never more
    (OrgRole.VIEWER, VaultPermission.READ, Action.SECRET_READ_META, True),
    (OrgRole.VIEWER, VaultPermission.WRITE, Action.SECRET_WRITE, False),   # viewers capped at read
    (OrgRole.VIEWER, None, Action.VAULT_CREATE, False),
]


@pytest.mark.parametrize("role,grant,action,expected", MATRIX)
async def test_policy_matrix(role, grant, action, expected, seeded_tenant):
    ctx = await evaluate_policy(seeded_tenant, role, grant, action)
    assert ctx.allowed is expected
```

(The `seeded_tenant` fixture builds an org with four users — one per role — plus a vault and grants as requested; `evaluate_policy` wraps `PolicyService.require_*` and converts exceptions into an `allowed` bool. Write these helpers yourself — the exercise of building the fixture is where you learn how the tables interlock.)

For viewers, notice the test at `(VIEWER, WRITE, SECRET_WRITE, False)`: the *grant* says write, the *role* caps at read. Enforce that cap — add it to `_grant_allows` by refusing non-read actions when the loaded role is `VIEWER`, even if a grant row claims otherwise. Grant rows are data; roles are policy. **When they conflict, policy wins.** This is the matrix's most important row, because it catches the failure mode where someone "fixes" a permission problem by writing an over-broad grant directly into the database.

### Cross-tenant adversarial tests

Extend the Chapter 2 adversarial suite with authorization-layer attacks — `tests/integration/test_vault_isolation.py`:

- Tenant A member with `admin` grant on vault V → present V's UUID with a tenant-B access token → 404 (not 403, not data).
- Tenant B owner creates a grant targeting tenant A's `membership_id` → 404 "Membership not found", no row created (verify by querying as owner role).
- Member of tenant A revokes their own admin grant, then attempts `SECRET_WRITE` → 403.
- Vault soft-deleted in tenant A → list excludes it; direct access 404s; tenant B unaffected.
- Replay attack on the API: capture the exact HTTP request of a successful grant creation, re-send it → second call is an idempotent upsert, not a duplicate row (unique constraint holds).

***

## 8. ADR and checklist

`docs/adr/0005-two-axis-rbac-with-centralized-policy-service.md`:

```markdown
# ADR 0005: Two-axis RBAC (org role + vault grant) via a single policy service

- Status: Accepted
- Date: 2026-07-29

## Context
VaultLog must compartmentalize secrets inside a tenant. A flat org-level
role system would give every member access to every secret; a purely
grant-based system would make org administration awkward and leave
orphaned grants when roles change.

## Decision
- Organization roles (owner/admin/member/viewer) provide baseline
  capabilities; vault grants (read/write/admin) gate vault contents.
- Owner/admin synthesize vault-admin permission without grant rows.
- Viewers are hard-capped at read regardless of grant data (policy > data).
- All decisions flow through PolicyService; routers and use cases never
  implement ad-hoc role checks.
- Authorization failures split into 404 (invisible/nonexistent) and
  403 (visible, denied) to prevent IDOR existence leaks.
- Step-up proof is re-asserted inside destructive use cases, not only
  in router dependencies.

## Consequences
- The permission matrix is executable specification: tests are generated
  from it and must be updated with any behavior change.
- Listing endpoints need the None-vs-list contract for unrestricted roles.
- ABAC attributes (IP, time, classification) can later extend
  AccessContext without changing call sites.
```

## Completion checklist

- [ ] Migration applied with grants, RLS (enable + force + policy), and both unique constraints.
- [ ] `tenant_id` denormalized onto `vault_grant`; RLS policy verified with `\d+ vault_grant`.
- [ ] All authorization decisions route through `PolicyService`; no inline role checks in routers.
- [ ] Owner/admin bypass grants; viewer read-cap overrides grant data.
- [ ] 404 vs 403 split prevents resource-existence leaks.
- [ ] Vault creation assigns the creator an explicit admin grant.
- [ ] Delete vault requires step-up at router *and* use case.
- [ ] Full parametrized matrix passes, including the viewer-cap row.
- [ ] Cross-tenant adversarial tests pass (404 on foreign IDs, grant forgery rejected).
- [ ] `uv run ruff check . && uv run mypy && uv run pytest` all green.

## Chapter outcome

VaultLog now has resources worth protecting and a single, tested brain deciding who may touch them. Authentication answers "who," RLS answers "which tenant," and the policy service answers "what action" — three independent layers that each fail closed.

**Chapter 6** puts actual secrets behind this authorization: the secret and secret-version tables, tenant data-encryption keys wrapped by a KEK, AES-256-GCM with AAD binding, the reveal flow with audit hooks, and secret rotation — the cryptographic core of the entire product.

***

## Chapter 6 — Encrypted secrets: envelope encryption, key hierarchy, and rotation

**Goal:** Implement the cryptographic heart of VaultLog: tenant-scoped data-encryption keys wrapped by a key-encryption key, AES-256-GCM encryption with context-bound AAD, the secret/secret-version data model, create/reveal/rotate/delete use cases, and DEK rotation. By the end, a full database dump contains nothing an attacker can read.

**Time budget:** 40–50 minutes. Take all of it. This chapter is why VaultLog exists.

***

## 1. Theory part 1: What we are actually defending against

Before touching a cipher, name the threats precisely. Cryptography deployed without a threat model is decoration.

| Threat | What the attacker has | Our defense |
|---|---|---|
| Database dump/backup leak | Every table, every row | Secrets stored only as ciphertext; keys not in the dump |
| SQL injection reaching read queries | Arbitrary SELECT via app role | Same as above — ciphertext only, plus RLS scoping |
| Cloud disk/snapshot exposure | Raw storage bytes | Encryption at rest above the storage layer |
| Curious/compromised insider with DB access | psql as owner role | Ciphertext + wrapped DEKs are useless without the KEK |
| Ciphertext transplant (copy row A's ciphertext into row B) | Write access to DB | AAD binding — decryption fails in the wrong context |
| Tampering with stored ciphertext | Write access to DB | AEAD authentication tag — any bit flip fails decryption loudly |
| KEK compromise | The wrapping key | Rotate KEK; re-wrap DEKs without re-encrypting data |
| Application server fully compromised | Memory, KEK access, live sessions | **Out of scope for encryption** — this is what auth, RLS, audit, and step-up are for |

That last row is the most important lesson in this chapter: **encryption at rest does not protect data from a compromised application.** If the attacker controls the running app, they have the KEK, the DEKs, and the ability to ask the app to decrypt anything its legitimate users could. Encryption at rest protects *stored data at rest* — dumps, snapshots, backups, stolen disks. Your Chapters 2–5 (RLS, auth, RBAC, step-up) are what protect live access. The layers answer different threats, and a senior engineer can say which layer answers which threat without hesitating.

## 2. Theory part 2: Symmetric encryption and why AES-GCM

Symmetric encryption uses one key for both encrypt and decrypt. Its security rests entirely on key secrecy — which is why most of this chapter is about *key management*, not ciphers. The cipher is the easy part.

We use **AES-256-GCM**: AES with a 256-bit key in Galois/Counter Mode. GCM is an **AEAD** mode — Authenticated Encryption with Associated Data — which gives three guarantees in one operation:

1. **Confidentiality** — ciphertext reveals nothing about plaintext (beyond length).
2. **Integrity/authenticity** — decryption produces a 128-bit authentication tag; if *any* bit of ciphertext, nonce, or AAD was modified, decryption **fails** rather than returning garbage. This matters more than beginners expect: an attacker who can flip bits in your database can otherwise mount padding-oracle-style and bit-flipping attacks (change "role=user" to "role=root" in a poorly protected ciphertext). AEAD makes tampering detectable, not silently effective.
3. **AAD binding** — additional authenticated data is *not encrypted* but *is* authenticated. If the AAD presented at decryption differs from the AAD at encryption, decryption fails. We exploit this to weld each ciphertext to its tenant/vault/secret/version context (section 5).

**The nonce rule — memorize this:** GCM uses a 96-bit nonce (number-used-once). Reusing a nonce with the same key is catastrophic: it leaks the XOR of the two plaintexts and destroys authentication, allowing forgery. We generate a fresh random 96-bit nonce per encryption with `os.urandom(12)`. With random nonces, collision probability under a single key stays negligible up to ~2³² messages per key (birthday bound); our per-tenant DEK volumes are far below that, and rotation keeps lifetime counts small. The nonce is **not secret** — it is stored alongside the ciphertext.

Contrast with what we are *not* using, so you can defend the choice in a review:

- **AES-CBC**: no built-in authentication; requires a separate HMAC and invites padding-oracle bugs when composed wrong.
- **AES-ECB**: deterministic — identical plaintext blocks produce identical ciphertext blocks (the famous penguin picture). Never.
- **ChaCha20-Poly1305**: an excellent AEAD and a legitimate alternative (better on CPUs without AES hardware acceleration). Either is defensible; AES-GCM is the more universal default and hardware-accelerated on virtually all servers.
- **Fernet** (from the `cryptography` library): fine for simple cases, but opaque about its construction and lacks explicit AAD control. We build on AESGCM directly so every security property is visible in our code.

## 3. Theory part 3: Envelope encryption and the key hierarchy

Here is the central design problem: you need to encrypt many secrets, and you need to be able to *change keys* without re-encrypting the world. If one master key encrypted everything directly, rotating that key would mean decrypting and re-encrypting every secret — hours of downtime and a giant failure window. If you never rotate, a slowly-leaking key eventually exposes everything.

The industry-standard answer is **envelope encryption** — a two-level key hierarchy:

```text
KEK (Key-Encryption Key)                    ← lives in KMS, never in the database
   │  wraps/unwraps (AES-256-GCM)
   ▼
DEK (Data-Encryption Key)                   ← stored in DB only as wrapped_dek ciphertext
   │  encrypts/decrypts (AES-256-GCM)
   ▼
Secret plaintext                            ← stored in DB only as ciphertext
```

- The **DEK** is a random 256-bit key that actually encrypts secret data. Each tenant gets its own DEK, versioned. It is stored in the database — but only in *wrapped* (encrypted) form.
- The **KEK** wraps (encrypts) and unwraps (decrypts) DEKs. It never touches secret data. In production it lives in a managed KMS (Google Cloud KMS, AWS KMS) where it cannot be exported at all — the KMS performs wrap/unwrap *operations* and the raw key never leaves the HSM. Locally, we simulate the KEK with a base64 environment variable.

This yields four concrete wins:

1. **A database dump is useless.** It contains secret ciphertexts and wrapped DEKs; decrypting either requires the KEK, which isn't there.
2. **KEK rotation is cheap.** Rotating the KEK means re-wrapping one 32-byte DEK per tenant — not re-encrypting gigabytes of secrets.
3. **DEK rotation is possible.** Compromise or policy can force a new DEK; secrets are re-encrypted in background batches (section 9) while the old DEK version stays available for reading old versions.
4. **Blast radius is tenant-scoped.** One tenant's DEK compromise cannot decrypt another tenant's data. This mirrors the RLS philosophy: isolation at every layer.

**Key versioning** completes the picture: keys are never replaced in place. `tenant_key_version` rows are immutable; a new version is *added* and marked active, old versions are *retired* (no new encryptions) but retained (old ciphertexts still decryptable). Immutability of keys, like immutability of secret versions and audit rows, is the same principle recurring: **history is append-only; you change the present by adding, not by rewriting.**

## 4. Schema: secrets, versions, and key versions

Three new tenant-owned tables. Add to `infrastructure/database/models.py`:

```python
from sqlalchemy import LargeBinary, Integer


class TenantKeyVersionModel(Base):
    __tablename__ = "tenant_key_version"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    wrapped_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrap_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrapping_key_id: Mapped[str] = mapped_column(String(200), nullable=False)  # KMS key resource name / "local-kek-v1"
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")  # active | retired
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_tenant_key_version"),
        CheckConstraint("status IN ('active','retired')", name="ck_tkv_status"),
    )


class SecretModel(Base):
    __tablename__ = "secret"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    vault_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vault.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("vault_id", "name", name="uq_secret_vault_name"),
    )


class SecretVersionModel(Base):
    __tablename__ = "secret_version"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    secret_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("secret.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dek_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("secret_id", "version", name="uq_secret_version"),
    )
```

Design notes:

- **AAD is not stored.** It is *derived deterministically* from stable identifiers (tenant, vault, secret, version) at decryption time. Storing it would be redundant and would invite tampering with the stored copy; deriving it means the "correct" AAD is defined by where the row lives, and a transplanted row fails authentication.
- **`dek_version` on every version row.** This is what makes DEK rotation resumable: each ciphertext knows exactly which key version decrypts it.
- **Version rows are immutable.** No `updated_at`, no update path in code. Rotation appends; history never mutates.
- **`wrapping_key_id` records which KEK wrapped each DEK** — essential when you rotate the KEK later and have DEKs wrapped by different generations.

### Migration

```bash
uv run alembic revision -m "secrets, versions, tenant key versions" --autogenerate
```

Review the diff (three new tables, indexes, uniques, checks), then append what autogenerate cannot know:

```python
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON secret, tenant_key_version TO vaultlog_app")
op.execute("GRANT SELECT, INSERT ON secret_version TO vaultlog_app")  # immutable: no UPDATE/DELETE

for table in ("secret", "secret_version", "tenant_key_version"):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON {table}
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)
```

Withholding `UPDATE`/`DELETE` on `secret_version` from the app role is database-enforced immutability — even a SQL injection achieving arbitrary query execution as `vaultlog_app` cannot rewrite history. In `downgrade()`, drop the three policies before dropping tables.

```bash
uv run alembic upgrade head
```

***

## 5. The crypto core

`src/vaultlog/infrastructure/security/vault_crypto.py`. Read every comment — this file *is* the chapter's theory made executable.

```python
from __future__ import annotations

import base64
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from vaultlog.shared.config import get_settings

settings = get_settings()

DEK_SIZE = 32        # 256-bit AES key
GCM_NONCE_SIZE = 12  # 96-bit nonce, the GCM standard


class CryptoError(Exception):
    """Never say what failed (padding, tag, key). Oracles start with details."""


# ---------------------------------------------------------------------------
# AAD construction: the context weld
# ---------------------------------------------------------------------------

def secret_aad(tenant_id: UUID, vault_id: UUID, secret_id: UUID, version: int) -> bytes:
    """Deterministic AAD binding a ciphertext to exactly one logical position.

    Only STABLE identifiers. Never names (they change), never timestamps.
    The version prefix 'vaultlog:secret:v1' is domain separation: it guarantees
    these bytes can never collide with AAD from another feature (e.g. TOTP
    seeds use 'vaultlog:totp-seed:v1:...'), so ciphertexts are not
    interchangeable across features even under the same key.
    """
    return f"vaultlog:secret:v1:{tenant_id}:{vault_id}:{secret_id}:{version}".encode()


def dek_wrap_aad(tenant_id: UUID, key_version: int) -> bytes:
    return f"vaultlog:dek-wrap:v1:{tenant_id}:{key_version}".encode()


# ---------------------------------------------------------------------------
# Data layer: DEK encrypts secrets
# ---------------------------------------------------------------------------

def generate_dek() -> bytes:
    return os.urandom(DEK_SIZE)


def encrypt_secret(dek: bytes, plaintext: bytes, aad: bytes) -> tuple[bytes, bytes]:
    """Returns (nonce, ciphertext||tag). Fresh random nonce per call."""
    if len(dek) != DEK_SIZE:
        raise CryptoError("Invalid DEK size")
    nonce = os.urandom(GCM_NONCE_SIZE)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
    return nonce, ciphertext


def decrypt_secret(dek: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """Fails LOUDLY on any tampering: wrong key, flipped bit, wrong context."""
    try:
        return AESGCM(dek).decrypt(nonce, ciphertext, aad)
    except Exception as exc:
        raise CryptoError("Decryption failed") from exc


# ---------------------------------------------------------------------------
# Envelope layer: KEK wraps DEKs
# ---------------------------------------------------------------------------
#
# LocalKEKProvider simulates a KMS: the KEK arrives from configuration and is
# held only in memory. In production you replace this class with one that
# calls Cloud KMS Encrypt/Decrypt — the KEK then never exists in app memory
# at all. The interface is deliberately tiny so the swap touches nothing else.

class KEKProvider:
    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes, str]:
        """Returns (nonce, wrapped_dek, wrapping_key_id)."""
        raise NotImplementedError

    def unwrap(self, nonce: bytes, wrapped_dek: bytes, aad: bytes, wrapping_key_id: str) -> bytes:
        raise NotImplementedError


class LocalKEKProvider(KEKProvider):
    KEY_ID = "local-kek-v1"

    def __init__(self) -> None:
        self._kek = base64.b64decode(settings.master_key_b64)
        if len(self._kek) != DEK_SIZE:
            raise CryptoError("MASTER_KEY_B64 must decode to 32 bytes")

    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes, str]:
        nonce = os.urandom(GCM_NONCE_SIZE)
        return nonce, AESGCM(self._kek).encrypt(nonce, dek, aad), self.KEY_ID

    def unwrap(self, nonce: bytes, wrapped_dek: bytes, aad: bytes, wrapping_key_id: str) -> bytes:
        if wrapping_key_id != self.KEY_ID:
            raise CryptoError("Unknown wrapping key")
        try:
            return AESGCM(self._kek).decrypt(nonce, wrapped_dek, aad)
        except Exception as exc:
            raise CryptoError("DEK unwrap failed") from exc
```

Why the `KEKProvider` interface exists: the day you move to Cloud KMS, you write `GcpKmsProvider` (calling KMS `encrypt`/`decrypt`, returning the KMS key resource name as `wrapping_key_id`) and change one line of wiring. Every use case in this chapter depends only on the interface — **this is the ports-and-adapters pattern earning its keep at the exact point where your environment will change.**

The `CryptoError`-swallows-details pattern deserves attention too: `AESGCM.decrypt` raising `InvalidTag` versus a key error versus a length error is information. Decryption oracles (systems whose error behavior leaks *why* decryption failed) have broken real protocols. One exception type, one message, everywhere.

***

## 6. Key management use cases

`src/vaultlog/application/secrets/key_management.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.infrastructure.database.models import TenantKeyVersionModel
from vaultlog.infrastructure.security.vault_crypto import (
    CryptoError, KEKProvider, dek_wrap_aad, generate_dek,
)


class NoActiveKeyError(Exception):
    pass


async def provision_tenant_key(session: AsyncSession, kek: KEKProvider, tenant_id: uuid.UUID) -> int:
    """Called once at organization creation (Chapter 3 registration flow)."""
    dek = generate_dek()
    version = 1
    nonce, wrapped, key_id = kek.wrap(dek, dek_wrap_aad(tenant_id, version))
    session.add(TenantKeyVersionModel(
        tenant_id=tenant_id, version=version, wrapped_dek=wrapped,
        wrap_nonce=nonce, wrapping_key_id=key_id, status="active",
    ))
    return version


async def load_active_dek(session: AsyncSession, kek: KEKProvider, tenant_id: uuid.UUID) -> tuple[bytes, int]:
    row = await session.scalar(
        select(TenantKeyVersionModel).where(
            TenantKeyVersionModel.tenant_id == tenant_id,
            TenantKeyVersionModel.status == "active",
        )
    )
    if row is None:
        raise NoActiveKeyError("Tenant has no active encryption key")
    dek = kek.unwrap(row.wrap_nonce, row.wrapped_dek, dek_wrap_aad(tenant_id, row.version), row.wrapping_key_id)
    return dek, row.version


async def load_dek_version(session: AsyncSession, kek: KEKProvider, tenant_id: uuid.UUID, version: int) -> bytes:
    """For reading ciphertexts written under an older, retired DEK."""
    row = await session.scalar(
        select(TenantKeyVersionModel).where(
            TenantKeyVersionModel.tenant_id == tenant_id,
            TenantKeyVersionModel.version == version,
        )
    )
    if row is None:
        raise CryptoError("Unknown key version")
    return kek.unwrap(row.wrap_nonce, row.wrapped_dek, dek_wrap_aad(tenant_id, version), row.wrapping_key_id)


async def rotate_tenant_dek(session: AsyncSession, kek: KEKProvider, tenant_id: uuid.UUID) -> int:
    """Adds a new active DEK; old versions remain decryptable but retired.

    Existing ciphertexts are NOT re-encrypted here — they carry dek_version
    and decrypt via load_dek_version. A background re-encryption sweep
    (section 9) migrates them lazily. This keeps rotation O(1) instead of
    O(all secrets) — the entire point of envelope encryption.
    """
    current = await session.scalars(
        select(TenantKeyVersionModel).where(
            TenantKeyVersionModel.tenant_id == tenant_id,
            TenantKeyVersionModel.status == "active",
        )
    )
    new_version = 1
    for row in current:
        row.status = "retired"
        row.retired_at = datetime.now(UTC)
        new_version = row.version + 1

    dek = generate_dek()
    nonce, wrapped, key_id = kek.wrap(dek, dek_wrap_aad(tenant_id, new_version))
    session.add(TenantKeyVersionModel(
        tenant_id=tenant_id, version=new_version, wrapped_dek=wrapped,
        wrap_nonce=nonce, wrapping_key_id=key_id, status="active",
    ))
    return new_version
```

The DEK exists in application memory as plaintext bytes for exactly as long as a request needs it — read from DB wrapped, unwrapped via KEK, used, dropped. It is never logged, never returned in a response, never written anywhere unwrapped. In Python you cannot truly scrub immutable `bytes` from memory (a real limitation of the language — native code and HSMs exist partly for this reason); the practical mitigation is minimizing lifetime and never letting it cross a trust boundary.

***

## 7. Secret use cases

`src/vaultlog/application/secrets/use_cases.py`. Every operation runs inside the tenant-scoped UoW, goes through `PolicyService`, and (from Chapter 7) appends its audit event in the same transaction.

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.application.access.policy_service import (
    ForbiddenError, NotFoundError, PolicyService,
)
from vaultlog.application.secrets.key_management import load_active_dek, load_dek_version
from vaultlog.domain.access.models import Action
from vaultlog.infrastructure.database.models import SecretModel, SecretVersionModel
from vaultlog.infrastructure.security.vault_crypto import (
    KEKProvider, decrypt_secret, encrypt_secret, secret_aad,
)


@dataclass(frozen=True)
class SecretMetaView:
    id: uuid.UUID
    name: str
    description: str | None
    current_version: int
    created_at: datetime
    updated_at: datetime


def _meta(s: SecretModel) -> SecretMetaView:
    return SecretMetaView(s.id, s.name, s.description, s.current_version, s.created_at, s.updated_at)


class CreateSecret:
    def __init__(self, session: AsyncSession, kek: KEKProvider) -> None:
        self._session, self._kek = session, kek
        self._policy = PolicyService(session)

    async def execute(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID, vault_id: uuid.UUID,
        name: str, plaintext: str, description: str | None,
    ) -> SecretMetaView:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_WRITE)

        secret = SecretModel(
            tenant_id=tenant_id, vault_id=vault_id, name=name,
            description=description, created_by_user_id=user_id, current_version=1,
        )
        self._session.add(secret)
        await self._session.flush()  # assigns secret.id — needed for AAD

        dek, dek_version = await load_active_dek(self._session, self._kek, tenant_id)
        aad = secret_aad(tenant_id, vault_id, secret.id, 1)
        nonce, ciphertext = encrypt_secret(dek, plaintext.encode(), aad)

        self._session.add(SecretVersionModel(
            tenant_id=tenant_id, secret_id=secret.id, version=1,
            ciphertext=ciphertext, nonce=nonce, dek_version=dek_version,
            created_by_user_id=user_id,
        ))
        # Chapter 7: audit 'secret.created' in this same transaction.
        return _meta(secret)


class ListSecrets:
    """Metadata only. Plaintext is NEVER returned by list endpoints."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._policy = PolicyService(session)

    async def execute(self, user_id: uuid.UUID, tenant_id: uuid.UUID, vault_id: uuid.UUID) -> list[SecretMetaView]:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_READ_META)
        rows = await self._session.scalars(
            select(SecretModel).where(
                SecretModel.vault_id == vault_id,
                SecretModel.tenant_id == tenant_id,
                SecretModel.deleted_at.is_(None),
            ).order_by(SecretModel.name)
        )
        return [_meta(s) for s in rows]


class RevealSecret:
    def __init__(self, session: AsyncSession, kek: KEKProvider) -> None:
        self._session, self._kek = session, kek
        self._policy = PolicyService(session)

    async def execute(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID,
        vault_id: uuid.UUID, secret_id: uuid.UUID, version: int | None,
    ) -> tuple[SecretMetaView, str]:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_REVEAL)

        secret = await self._session.scalar(
            select(SecretModel).where(
                SecretModel.id == secret_id,
                SecretModel.vault_id == vault_id,
                SecretModel.tenant_id == tenant_id,
                SecretModel.deleted_at.is_(None),
            )
        )
        if secret is None:
            raise NotFoundError("Secret not found")

        wanted = version if version is not None else secret.current_version
        row = await self._session.scalar(
            select(SecretVersionModel).where(
                SecretVersionModel.secret_id == secret.id,
                SecretVersionModel.version == wanted,
                SecretVersionModel.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise NotFoundError("Secret version not found")

        dek = await load_dek_version(self._session, self._kek, tenant_id, row.dek_version)
        aad = secret_aad(tenant_id, vault_id, secret.id, row.version)
        plaintext = decrypt_secret(dek, row.nonce, row.ciphertext, aad).decode()
        # Chapter 7: audit 'secret.revealed' — this is the most sensitive
        # audit event in the system. It MUST exist, and it must never
        # contain the plaintext.
        return _meta(secret), plaintext


class RotateSecret:
    """New value = new immutable version. History is preserved."""

    def __init__(self, session: AsyncSession, kek: KEKProvider) -> None:
        self._session, self._kek = session, kek
        self._policy = PolicyService(session)

    async def execute(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID, vault_id: uuid.UUID,
        secret_id: uuid.UUID, new_plaintext: str,
    ) -> SecretMetaView:
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_WRITE)

        secret = await self._session.scalar(
            select(SecretModel).where(
                SecretModel.id == secret_id,
                SecretModel.vault_id == vault_id,
                SecretModel.tenant_id == tenant_id,
                SecretModel.deleted_at.is_(None),
            ).with_for_update()  # serialize concurrent rotations on this row
        )
        if secret is None:
            raise NotFoundError("Secret not found")

        new_version = secret.current_version + 1
        dek, dek_version = await load_active_dek(self._session, self._kek, tenant_id)
        aad = secret_aad(tenant_id, vault_id, secret.id, new_version)
        nonce, ciphertext = encrypt_secret(dek, new_plaintext.encode(), aad)

        self._session.add(SecretVersionModel(
            tenant_id=tenant_id, secret_id=secret.id, version=new_version,
            ciphertext=ciphertext, nonce=nonce, dek_version=dek_version,
            created_by_user_id=user_id,
        ))
        secret.current_version = new_version
        # Chapter 7: audit 'secret.rotated'.
        return _meta(secret)


class DeleteSecret:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._policy = PolicyService(session)

    async def execute(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID, vault_id: uuid.UUID,
        secret_id: uuid.UUID, *, step_up_proven: bool,
    ) -> None:
        if not step_up_proven:
            raise ForbiddenError("Step-up authentication required")
        await self._policy.require_vault(user_id, tenant_id, vault_id, Action.SECRET_DELETE)

        secret = await self._session.get(SecretModel, secret_id)
        if secret is None or secret.deleted_at is not None:
            raise NotFoundError("Secret not found")
        secret.deleted_at = datetime.now(UTC)
        # Chapter 7: audit 'secret.deleted'. Version rows stay: soft delete
        # preserves recoverability and audit history. A separate retention
        # job (much later) hard-deletes per policy.
```

Note the `with_for_update()` on rotation: two concurrent rotations would otherwise both read `current_version = 3`, both write version 4, and one would crash on the unique constraint (or worse, without the constraint, silently fork history). The row lock serializes them; the unique constraint is the backstop. **Concurrency is a security property** — raced writes are how invariants die in production.

## 8. Router

`src/vaultlog/presentation/api/v1/secrets.py`:

```python
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from vaultlog.application.access.policy_service import ForbiddenError, NotFoundError
from vaultlog.application.secrets.use_cases import (
    CreateSecret, DeleteSecret, ListSecrets, RevealSecret, RotateSecret,
)
from vaultlog.infrastructure.security.vault_crypto import LocalKEKProvider
from vaultlog.presentation.dependencies import (
    Principal, StepUpPurpose, current_principal, get_tenant_uow, require_step_up,
)

router = APIRouter(prefix="/vaults/{vault_id}/secrets", tags=["secrets"])

NO_STORE = {"Cache-Control": "no-store"}


class SecretCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=10_000)
    description: str | None = Field(default=None, max_length=1000)


class SecretMetaResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    current_version: int
    created_at: str
    updated_at: str


class RevealResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    value: str


@router.post("", response_model=SecretMetaResponse, status_code=status.HTTP_201_CREATED)
async def create_secret(
    vault_id: uuid.UUID, body: SecretCreateRequest,
    principal: Principal = Depends(current_principal),
    tenant_uow=Depends(get_tenant_uow),
) -> SecretMetaResponse:
    async with tenant_uow as uow:
        try:
            view = await CreateSecret(uow.session, LocalKEKProvider()).execute(
                principal.user_id, principal.tenant_id, vault_id,
                body.name, body.value, body.description,
            )
        except NotFoundError:
            raise HTTPException(404, "Vault not found")
        except ForbiddenError:
            raise HTTPException(403, "Access denied")
        await uow.commit()
    return SecretMetaResponse(
        id=view.id, name=view.name, description=view.description,
        current_version=view.current_version,
        created_at=view.created_at.isoformat(), updated_at=view.updated_at.isoformat(),
    )


@router.get("", response_model=list[SecretMetaResponse])
async def list_secrets(
    vault_id: uuid.UUID,
    principal: Principal = Depends(current_principal),
    tenant_uow=Depends(get_tenant_uow),
) -> list[SecretMetaResponse]:
    async with tenant_uow as uow:
        try:
            views = await ListSecrets(uow.session).execute(principal.user_id, principal.tenant_id, vault_id)
        except NotFoundError:
            raise HTTPException(404, "Vault not found")
        except ForbiddenError:
            raise HTTPException(403, "Access denied")
    return [
        SecretMetaResponse(
            id=v.id, name=v.name, description=v.description, current_version=v.current_version,
            created_at=v.created_at.isoformat(), updated_at=v.updated_at.isoformat(),
        )
        for v in views
    ]


@router.post("/{secret_id}/reveal", response_model=RevealResponse)
async def reveal_secret(
    vault_id: uuid.UUID, secret_id: uuid.UUID, response: Response,
    version: int | None = None,
    principal: Principal = Depends(current_principal),
    tenant_uow=Depends(get_tenant_uow),
) -> RevealResponse:
    async with tenant_uow as uow:
        try:
            meta, plaintext = await RevealSecret(uow.session, LocalKEKProvider()).execute(
                principal.user_id, principal.tenant_id, vault_id, secret_id, version,
            )
        except NotFoundError:
            raise HTTPException(404, "Secret not found")
        except ForbiddenError:
            raise HTTPException(403, "Access denied")
        await uow.commit()  # commits the audit event (Chapter 7), not the plaintext
    response.headers["Cache-Control"] = "no-store"
    return RevealResponse(id=meta.id, name=meta.name, version=version or meta.current_version, value=plaintext)


@router.post("/{secret_id}/rotate", response_model=SecretMetaResponse)
async def rotate_secret(
    vault_id: uuid.UUID, secret_id: uuid.UUID,
    value: str = Body(embed=True, min_length=1, max_length=10_000),
    principal: Principal = Depends(current_principal),
    tenant_uow=Depends(get_tenant_uow),
) -> SecretMetaResponse:
    async with tenant_uow as uow:
        try:
            view = await RotateSecret(uow.session, LocalKEKProvider()).execute(
                principal.user_id, principal.tenant_id, vault_id, secret_id, value,
            )
        except NotFoundError:
            raise HTTPException(404, "Secret not found")
        except ForbiddenError:
            raise HTTPException(403, "Access denied")
        await uow.commit()
    return SecretMetaResponse(
        id=view.id, name=view.name, description=view.description,
        current_version=view.current_version,
        created_at=view.created_at.isoformat(), updated_at=view.updated_at.isoformat(),
    )


@router.delete("/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    vault_id: uuid.UUID, secret_id: uuid.UUID,
    principal: Principal = Depends(require_step_up(StepUpPurpose.DELETE_SECRET)),
    tenant_uow=Depends(get_tenant_uow),
) -> None:
    async with tenant_uow as uow:
        try:
            await DeleteSecret(uow.session).execute(
                principal.user_id, principal.tenant_id, vault_id, secret_id,
                step_up_proven=True,
            )
        except NotFoundError:
            raise HTTPException(404, "Secret not found")
        except ForbiddenError:
            raise HTTPException(403, "Access denied")
        await uow.commit()
```

Details that are deliberate, not incidental:

- **Reveal is POST, not GET.** GETs with sensitive responses leak into browser history, proxy logs keyed on URLs, and prefetchers. A POST to `/reveal` is an explicit action — which also maps naturally onto the audit event "someone revealed this secret at this time."
- **`Cache-Control: no-store` on reveal.** The plaintext must not persist in any cache between server and user: browser cache, CDN, shared proxy.
- **The 10 KB value cap.** Secrets are credentials, not file storage. Unbounded values invite the database to become a blob store and inflate every dump's blast radius.
- **Delete requires step-up at both layers** (router dependency + `step_up_proven` in the use case), consistent with vault deletion in Chapter 5.

## 9. Key rotation in production shape

Two distinct operations, often confused:

**KEK rotation (cheap):** generate a new KEK in KMS, re-wrap every tenant's active DEK (one 32-byte encrypt per tenant per version retained), update `wrapping_key_id`. No secret ciphertext is touched. With a real KMS this is often just *creating a new key version in the KMS* — the KMS keeps old versions for decryption automatically, and your `wrapping_key_id` bookkeeping tracks it.

**DEK rotation (batched):** `rotate_tenant_dek` (section 6) installs a new active DEK instantly. Old ciphertexts still reference `dek_version` and decrypt fine. Then a background job re-encrypts in resumable batches:

```python
# Pseudocode for the sweep job (runs per tenant, step-up initiated):
while True:
    batch = await find_versions_where(dek_version < active_version, limit=100)
    if not batch:
        break
    async with tenant_uow as uow:  # fresh transaction per batch: resumable, short locks
        old_dek = await load_dek_version(...)
        new_dek, new_version = await load_active_dek(...)
        for row in batch:
            aad = secret_aad(row.tenant_id, vault_of(row), row.secret_id, row.version)
            plaintext = decrypt_secret(old_dek, row.nonce, row.ciphertext, aad)
            row.nonce, row.ciphertext = encrypt_secret(new_dek, plaintext, aad)
            row.dek_version = new_version
        await uow.commit()
# Only when batch count == 0 across ALL tenants: the retired DEK version
# may be destroyed. Never destroy a key version while ciphertexts reference it.
```

Three invariants this preserves: every batch is a separate transaction (a crash mid-sweep loses at most one batch and can resume), the AAD is unchanged (same secret, same version — only the key changes), and old keys die only after verification proves nothing references them.

## 10. Tests — the cryptographic proof

`tests/unit/test_vault_crypto.py`:

```python
import uuid

import pytest

from vaultlog.infrastructure.security.vault_crypto import (
    CryptoError, LocalKEKProvider, decrypt_secret, encrypt_secret,
    generate_dek, secret_aad,
)

T, V, S = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def test_round_trip() -> None:
    dek = generate_dek()
    aad = secret_aad(T, V, S, 1)
    nonce, ct = encrypt_secret(dek, b"hunter2", aad)
    assert decrypt_secret(dek, nonce, ct, aad) == b"hunter2"
    assert b"hunter2" not in ct  # ciphertext contains no plaintext


def test_tampered_ciphertext_fails() -> None:
    dek = generate_dek()
    aad = secret_aad(T, V, S, 1)
    nonce, ct = encrypt_secret(dek, b"hunter2", aad)
    tampered = bytes([ct[0] ^ 1]) + ct[1:]  # flip one bit
    with pytest.raises(CryptoError):
        decrypt_secret(dek, nonce, tampered, aad)


def test_wrong_aad_fails() -> None:
    """THE core property: ciphertext transplanted to another secret/version/
    tenant/vault context must not decrypt."""
    dek = generate_dek()
    nonce, ct = encrypt_secret(dek, b"hunter2", secret_aad(T, V, S, 1))
    with pytest.raises(CryptoError):
        decrypt_secret(dek, nonce, ct, secret_aad(T, V, S, 2))        # wrong version
    with pytest.raises(CryptoError):
        decrypt_secret(dek, nonce, ct, secret_aad(uuid.uuid4(), V, S, 1))  # wrong tenant


def test_wrong_dek_fails() -> None:
    aad = secret_aad(T, V, S, 1)
    nonce, ct = encrypt_secret(generate_dek(), b"x", aad)
    with pytest.raises(CryptoError):
        decrypt_secret(generate_dek(), nonce, ct, aad)


def test_nonces_are_unique() -> None:
    dek = generate_dek()
    aad = secret_aad(T, V, S, 1)
    nonces = {encrypt_secret(dek, b"same", aad)[0] for _ in range(1000)}
    assert len(nonces) == 1000


def test_kek_wrap_unwrap_and_aad_binding() -> None:
    kek = LocalKEKProvider()
    from vaultlog.infrastructure.security.vault_crypto import dek_wrap_aad
    dek = generate_dek()
    nonce, wrapped, key_id = kek.wrap(dek, dek_wrap_aad(T, 1))
    assert dek not in wrapped
    assert kek.unwrap(nonce, wrapped, dek_wrap_aad(T, 1), key_id) == dek
    with pytest.raises(CryptoError):
        kek.unwrap(nonce, wrapped, dek_wrap_aad(uuid.uuid4(), 1), key_id)  # tenant swap
    with pytest.raises(CryptoError):
        kek.unwrap(nonce, wrapped, dek_wrap_aad(T, 1), "some-other-key")   # key id mismatch
```

`tests/integration/test_secret_flows.py` — against the real stack (Compose DB, RLS, policy service):

- Provision org (DEK v1 created) → create vault → create secret → reveal returns exact plaintext.
- Rotate secret twice → versions 1, 2, 3 all reveal their own distinct values; default reveal returns v3.
- Rotate tenant DEK → old versions still reveal (via retired key), new rotation writes under v2, reveal works throughout.
- Member with only `read` grant → reveal works, rotate is 403, delete is 403.
- Member with no grant → even list is 403; direct reveal of a known secret UUID is 404-invisible.
- Cross-tenant: tenant B token presenting tenant A's secret UUID → 404; verify at the DB layer that tenant B's scoped session cannot even SELECT the row (RLS).
- Delete without step-up → 403 from the router; use case called directly with `step_up_proven=False` → `ForbiddenError`.
- **Log-safety test:** create a secret with a canary value, exercise every endpoint, then assert the canary string appears nowhere in captured logs (use structlog's testing utilities or a capture fixture).
- **Concurrency test:** two simultaneous rotations → both succeed with versions 2 and 3, unique constraint never violated, final `current_version` is 3.

## 11. ADR and checklist

`docs/adr/0006-envelope-encryption-with-per-tenant-deks.md`:

```markdown
# ADR 0006: Envelope encryption — per-tenant versioned DEKs wrapped by a KMS KEK

- Status: Accepted
- Date: 2026-07-29

## Context
Secrets must survive database dumps, backup leaks, and insider DB access.
Keys must be rotatable without re-encrypting all data or causing downtime.
Compromise of one tenant must not affect others.

## Decision
- AES-256-GCM (AEAD) for all encryption; random 96-bit nonces, never reused.
- Per-tenant, versioned DEKs encrypt secret values; DEKs are stored only
  wrapped by a KEK via a KEKProvider interface (local env-var KEK in dev,
  Cloud KMS in production).
- AAD binds every ciphertext to tenant/vault/secret/version and every
  wrapped DEK to tenant/version; AAD is derived, never stored.
- Secret versions are immutable and DB-enforced (app role lacks UPDATE/DELETE
  on secret_version); value rotation appends versions.
- DEK rotation installs a new active version instantly; re-encryption sweeps
  in resumable batches; KEK rotation only re-wraps DEKs.
- Plaintext appears only in reveal responses (POST, Cache-Control: no-store)
  and never in logs, audit rows, list endpoints, or error messages.

## Consequences
- Application compromise is out of scope for at-rest encryption (documented);
  mitigated by auth, RLS, RBAC, step-up, and audit layers.
- Key versions must be retained until a verified sweep shows zero references.
- Python cannot guarantee memory scrubbing of DEKs; lifetime is minimized
  instead. Documented as accepted residual risk.
```

## Completion checklist

- [ ] Migration applied: 3 tables, RLS ×3, grants, uniques, no app UPDATE/DELETE on `secret_version`.
- [ ] `MASTER_KEY_B64` (32 bytes, base64) set, git-ignored, never logged.
- [ ] AAD is derived from stable IDs with domain-separated prefixes; never stored.
- [ ] Every encryption call uses a fresh `os.urandom(12)` nonce.
- [ ] KEK access only through the `KEKProvider` interface.
- [ ] DEK plaintext never leaves memory scope of a use case; never in responses/logs.
- [ ] Reveal is POST + `no-store`; list endpoints carry metadata only.
- [ ] Rotation is append-only with row lock + unique constraint; delete is soft + step-up.
- [ ] All crypto unit tests pass (tamper, wrong AAD, wrong key, nonce uniqueness, wrap binding).
- [ ] All integration flows pass, including DEK rotation continuity and the log-canary test.

## Chapter outcome

VaultLog now keeps secrets the way a vault should: a database dump yields ciphertext and wrapped keys, a transplanted row refuses to decrypt, a flipped bit fails loudly, keys rotate without downtime, and every layer of isolation (tenant DEKs, RLS, grants, step-up) reinforces the others.

**Chapter 7** closes the evidentiary loop: the append-only, hash-chained audit ledger — every reveal, rotation, grant change, and denial recorded immutably, in the same transaction as the action itself, so VaultLog can always answer the question every secrets system must answer: *who touched what, and can we prove it?*

***

## Chapter 7 — The immutable audit ledger

**Goal:** Implement an append-only, hash-chained audit ledger where every security-relevant action — reveal, rotation, grant change, deletion, denial — is recorded in the *same database transaction* as the action itself, protected from modification by database privileges, and verifiable end-to-end with a chain-integrity checker.

**Time budget:** 30–40 minutes.

**Why this chapter is the soul of VaultLog:** A secrets manager without a trustworthy audit trail is a black box with a lock. Every compliance regime, every incident investigation, every "who leaked this credential?" postmortem begins with the same question: *what happened, and can you prove it?* Chapter 6 made secrets unreadable to outsiders; this chapter makes actions undeniable to insiders — including insiders with database access.

***

## 1. Theory: what "immutable" actually means

"Immutable log" is a phrase people use loosely. There are four distinct levels of protection, and you should know exactly which ones you have:

| Level | Mechanism | Defeats | Does not defeat |
|---|---|---|---|
| **1. Convention** | App code simply never updates | Accidental modification | Any attacker or insider with write access |
| **2. Database privilege** | App role lacks `UPDATE`/`DELETE` grants | SQL injection as app role, app bugs, rogue ORM calls | Schema owner, superuser |
| **3. Tamper evidence** | Hash chain: each entry commits to all history before it | *Silent* modification — tampering is detectable by verification | Tampering itself; an attacker who recomputes the whole chain |
| **4. External anchoring** | Periodically sign/store chain-head digests in an independent system (WORM object storage, separate log service) | Even attackers with full DB control — they cannot rewrite what they don't control | Nothing cheaply; this is the real endgame |

VaultLog implements levels 2 and 3 in this chapter, and designs level 4 as a documented extension (section 9). Understanding why level 3 alone is insufficient is the mark of someone who has thought about adversaries rather than auditors: an attacker with owner-level database access can rewrite rows **and recompute the hash chain forward from the tampered point**, producing a perfectly valid chain of fabricated history. The hash chain's job is to make tampering *provably evident* against any snapshot taken before the attack — and level 4's job is to guarantee a snapshot exists that the attacker cannot touch.

### Why hash chaining works

The construction is borrowed from the same family of ideas as blockchains and certificate-transparency logs, minus the hype:

```text
entry_hash(n) = SHA-256( entry_hash(n-1) || canonical_bytes(event n) )
```

Each entry's hash incorporates the previous entry's hash. Change any historical field — an actor ID, a timestamp, an outcome — and that entry's hash changes, which invalidates every subsequent entry's `previous_hash` link. Verification walks the chain from the beginning: recompute each hash, compare with the stored value, and confirm each `previous_hash` matches the actual predecessor. Any break means tampering or corruption, and the verifier names the exact entry where the chain stops agreeing with itself.

The property that matters: **you cannot edit history without rewriting everything after it.** Combined with level 2 (the app role physically cannot execute the rewrite) and level 4 (an external snapshot of an earlier chain head that the rewrite can never match), the ledger becomes genuinely trustworthy.

### Canonicalization: the silent killer

A hash chain is only as strong as its canonicalization. `SHA-256` over `"some string built ad hoc"` fails in practice because two runs of the code must produce *byte-identical* input for the same event — including when the verifier is a different process, written months later, possibly in a different language. The classic traps:

- `str(dict)` in Python — key order is insertion order, format is language-specific.
- JSON with whitespace variance — `{"a":1}` and `{ "a": 1 }` hash differently.
- Float formatting, timezone formatting, Unicode normalization differences.

Our rule: **canonical JSON** — keys sorted, no whitespace, UTF-8, datetimes as ISO-8601 UTC with fixed precision, UUIDs lowercase. The spec lives in one function, and the verifier uses the *same* function. Both are tested against a golden vector (section 7).

***

## 2. Schema

Two tables: the events themselves, and a per-tenant chain head that serializes appends. Add to `infrastructure/database/models.py`:

```python
from sqlalchemy import BigInteger, Index
from sqlalchemy.dialects.postgresql import JSONB


class AuditEventModel(Base):
    __tablename__ = "audit_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    previous_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)  # NULL only for sequence 1
    entry_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "sequence", name="uq_audit_tenant_sequence"),
        UniqueConstraint("tenant_id", "entry_hash", name="uq_audit_tenant_entry_hash"),
        CheckConstraint("outcome IN ('success','failure','denied')", name="ck_audit_outcome"),
        Index("ix_audit_tenant_action_time", "tenant_id", "action", "occurred_at"),
    )


class AuditChainHeadModel(Base):
    __tablename__ = "audit_chain_head"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organization.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    last_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_hash: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
```

Design decisions, each deliberate:

- **`ondelete="RESTRICT"` on the organization foreign key.** Audit history must outlive the org it describes; deleting an organization must be a deliberate archival/export process, never a cascade that vaporizes evidence. (Contrast with vault/secret cascades, which are internal to a tenant.)
- **Per-tenant chains, not one global chain.** A global chain serializes *every tenant's* writes through one lock — a throughput catastrophe and an availability coupling between tenants. Per-tenant chains give each tenant an independent, verifiable history; cross-tenant ordering is not a security requirement here.
- **`metadata` is a reserved attribute name in SQLAlchemy's Declarative base** — hence the Python attribute `event_metadata` mapped to the SQL column `"metadata"`. This trips everyone exactly once; now it has tripped you in a book instead of at 1 AM.
- **The index on `(tenant_id, action, occurred_at)`** is shaped for the real query: "show me all `secret.revealed` events in this tenant, newest first" — the incident-investigation query.
- **`actor_user_id` nullable** because some events (pre-auth login failures, future system jobs) have no authenticated actor.

### Migration

```bash
uv run alembic revision -m "audit event ledger and chain heads" --autogenerate
```

Review, then append the security statements:

```python
# The app role can APPEND and READ. It cannot UPDATE or DELETE. Ever.
op.execute("GRANT SELECT, INSERT ON audit_event TO vaultlog_app")
op.execute("GRANT SELECT, INSERT, UPDATE ON audit_chain_head TO vaultlog_app")

for table in ("audit_event", "audit_chain_head"):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")

op.execute("""
    CREATE POLICY tenant_isolation ON audit_event
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
""")
op.execute("""
    CREATE POLICY tenant_isolation ON audit_chain_head
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
""")
```

`audit_chain_head` needs `UPDATE` (each append advances the head) but not `DELETE`. Note the asymmetry: the *head* is mutable because it is a pointer, not history; the *events* are history and are frozen. In `downgrade()`, drop policies before tables.

```bash
uv run alembic upgrade head
```

***

## 3. The canonicalization and hashing core

`src/vaultlog/infrastructure/audit/hashing.py`:

```python
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

GENESIS_DOMAIN = b"vaultlog:audit:genesis:v1"


def canonical_event_bytes(
    *,
    tenant_id: UUID,
    sequence: int,
    actor_user_id: UUID | None,
    session_id: UUID | None,
    action: str,
    target_type: str,
    target_id: UUID | None,
    outcome: str,
    metadata: dict,
    occurred_at: datetime,
) -> bytes:
    """Byte-stable encoding of an event. Verifier MUST use this same function.

    Rules: keys sorted, no whitespace, UTF-8, UUIDs lowercase, datetimes
    rendered as fixed-precision ISO-8601 UTC. Any future change to this
    function is a HASH FORMAT VERSION CHANGE — old chains verify only under
    the old code. Do not change casually; version the algorithm in the
    genesis domain separator if you ever must.
    """
    doc = {
        "tenant_id": str(tenant_id),
        "sequence": sequence,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "session_id": str(session_id) if session_id else None,
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id) if target_id else None,
        "outcome": outcome,
        "metadata": metadata,
        "occurred_at": occurred_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z",
    }
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_entry_hash(previous_hash: bytes | None, canonical: bytes) -> bytes:
    """entry_hash = SHA-256(previous_hash || canonical_bytes).

    Sequence 1 chains to a domain separator instead of a previous hash, so a
    first-entry hash can never collide with a mid-chain entry hash.
    """
    prev = previous_hash if previous_hash is not None else GENESIS_DOMAIN
    return hashlib.sha256(prev + canonical).digest()
```

The genesis domain separator is a small detail with real purpose: without it, the hash of the first entry is `SHA-256(canonical)` with no prefix — structurally different from every other entry. An attacker rewriting a chain from scratch might exploit ambiguity between "no previous" and "previous is 32 zero bytes" or similar edge cases. Explicit domain separation eliminates the ambiguity class entirely. You saw this same idea in Chapter 6's AAD prefixes; domain separation is a habit, not a one-off trick.

***

## 4. The AuditWriter — append under lock, inside the UoW

`src/vaultlog/application/audit/writer.py`:

```python
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.infrastructure.audit.hashing import canonical_event_bytes, compute_entry_hash
from vaultlog.infrastructure.database.models import AuditChainHeadModel, AuditEventModel

# Actions that exist in the system. String values go to the DB; the type
# prevents typo'd action strings from polluting the ledger.
AUDIT_ACTIONS = frozenset({
    "vault.created", "vault.deleted", "vault.updated",
    "grant.created", "grant.updated", "grant.revoked",
    "secret.created", "secret.revealed", "secret.rotated", "secret.deleted",
    "key.rotated", "member.invited", "member.removed", "member.role_changed",
    "mfa.enabled", "mfa.disabled", "stepup.issued",
    "access.denied",
})

# Metadata keys that must never appear. The writer strips them defensively;
# use cases must never pass them in the first place.
FORBIDDEN_METADATA_KEYS = frozenset({
    "value", "plaintext", "password", "secret", "token", "code",
    "refresh_token", "access_token", "totp", "seed", "key", "dek",
})


class AuditMetadataError(ValueError):
    pass


class AuditWriter:
    """Appends one hash-chained event inside the caller's transaction.

    INVARIANT: callers never commit separately. The business mutation and
    its audit event commit together or roll back together — an action
    without evidence and evidence without an action are both corruption.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        tenant_id: uuid.UUID,
        action: str,
        target_type: str,
        actor_user_id: uuid.UUID | None,
        session_id: uuid.UUID | None,
        target_id: uuid.UUID | None = None,
        outcome: str = "success",
        metadata: dict | None = None,
    ) -> None:
        if action not in AUDIT_ACTIONS:
            raise ValueError(f"Unknown audit action: {action}")

        safe_metadata = metadata or {}
        offending = FORBIDDEN_METADATA_KEYS & {k.lower() for k in _walk_keys(safe_metadata)}
        if offending:
            raise AuditMetadataError(f"Forbidden audit metadata keys: {sorted(offending)}")

        # 1. Lock this tenant's chain head. Concurrent appends in other
        #    transactions serialize HERE — this is the ordering guarantee.
        head = await self._session.scalar(
            select(AuditChainHeadModel)
            .where(AuditChainHeadModel.tenant_id == tenant_id)
            .with_for_update()
        )
        if head is None:
            head = AuditChainHeadModel(tenant_id=tenant_id, last_sequence=0, last_hash=None)
            self._session.add(head)
            await self._session.flush()

        sequence = head.last_sequence + 1
        occurred_at = datetime.now(UTC)

        # 2. Canonicalize and hash.
        canonical = canonical_event_bytes(
            tenant_id=tenant_id, sequence=sequence,
            actor_user_id=actor_user_id, session_id=session_id,
            action=action, target_type=target_type, target_id=target_id,
            outcome=outcome, metadata=safe_metadata, occurred_at=occurred_at,
        )
        entry_hash = compute_entry_hash(head.last_hash, canonical)

        # 3. Append the immutable row and advance the head — same transaction.
        self._session.add(AuditEventModel(
            tenant_id=tenant_id, sequence=sequence,
            actor_user_id=actor_user_id, session_id=session_id,
            action=action, target_type=target_type, target_id=target_id,
            outcome=outcome, event_metadata=safe_metadata,
            occurred_at=occurred_at,
            previous_hash=head.last_hash, entry_hash=entry_hash,
        ))
        head.last_sequence = sequence
        head.last_hash = entry_hash


def _walk_keys(doc: dict):
    for key, value in doc.items():
        yield str(key)
        if isinstance(value, dict):
            yield from _walk_keys(value)
```

Three load-bearing mechanics:

1. **`SELECT ... FOR UPDATE` on the chain head** is the concurrency design. Two simultaneous `secret.revealed` calls in one tenant both need the head row; the second blocks until the first commits, then reads the updated `last_hash` and chains correctly. Without the lock, both would read the same head, compute the same sequence number, and one would die on the unique constraint — worse, naive "retry on conflict" logic would then produce subtly wrong chains. The lock makes correctness automatic. Cross-tenant traffic never contends, because heads are per-tenant.

2. **The forbidden-metadata guard.** Audit rows are replicated, exported, retained, and read by investigators — they are the *least* secret data store in the system and the *most* tempting place for a careless developer to drop a debug field like `{"value": plaintext}`. The writer refuses, loudly, at the trust boundary. This is the same philosophy as Chapter 6's `CryptoError` discipline: the dangerous mistake should be impossible, not merely discouraged.

3. **Action vocabulary is a closed set.** Free-text action strings rot into `"secret.reveal"` vs `"secret.revealed"` vs `"reveal_secret"` within a year, and investigations grep the ledger. A `frozenset` plus a hard error keeps the vocabulary a reviewed artifact.

***

## 5. Wiring the writer into the use cases

The pattern is uniform: **authorize → mutate → audit → one commit.** Revisit each use case and insert the audit call at the marked spots. Examples:

```python
# In RevealSecret.execute, immediately before `return`:
await AuditWriter(self._session).record(
    tenant_id=tenant_id,
    action="secret.revealed",
    target_type="secret",
    target_id=secret.id,
    actor_user_id=user_id,
    session_id=session_id,          # thread Principal.session_id through
    metadata={"vault_id": str(vault_id), "version": row.version},
)

# In RotateSecret.execute:
await AuditWriter(self._session).record(
    tenant_id=tenant_id, action="secret.rotated", target_type="secret",
    target_id=secret.id, actor_user_id=user_id, session_id=session_id,
    metadata={"vault_id": str(vault_id), "new_version": new_version, "dek_version": dek_version},
)

# In ManageGrant.grant:
await AuditWriter(self._session).record(
    tenant_id=tenant_id, action="grant.created" if existing is None else "grant.updated",
    target_type="vault", target_id=vault_id, actor_user_id=actor_user_id, session_id=session_id,
    metadata={"membership_id": str(target_membership_id), "permission": permission.value},
)
```

This requires threading `session_id` from the `Principal` into every use case — a mechanical change to use-case signatures (`user_id, session_id` travel together; consider a small `ActorContext` dataclass to avoid parameter sprawl).

**Recording denials** deserves special mention. In `PolicyService.require_vault`, when permission is denied for a sensitive action (reveal, delete, grant management), record an `access.denied` event *before* raising — in a **separate, immediately-committed transaction** via a dedicated short UoW, because the main UoW is about to roll back and would take the audit row with it:

```python
# In a helper used by the router's exception handler, NOT inside the rolled-back UoW:
async def record_denial(uow_factory, tenant_id, actor, action, target_type, target_id) -> None:
    async with uow_factory(tenant_id) as uow:
        await AuditWriter(uow.session).record(
            tenant_id=tenant_id, action="access.denied", target_type=target_type,
            target_id=target_id, actor_user_id=actor.user_id, session_id=actor.session_id,
            outcome="denied", metadata={"attempted_action": action},
        )
        await uow.commit()
```

This split — *successes audit inside the action's transaction; denials audit in their own* — is not a compromise of the invariant, it is the invariant correctly understood: the atomic unit is "state change + its evidence." A denial *is* the entire event; there is no state change to atomically accompany.

***

## 6. Query and verification

### Read endpoint

`GET /api/v1/audit-events?action=secret.revealed&target_id=...&limit=100&before_sequence=...` — org owner/admin only (add `Action.AUDIT_READ` to the matrix from Chapter 5), tenant-scoped by the usual UoW, keyset-paginated by `sequence` (offset pagination on an append-only table is both slow and semantically unstable). Response fields are exactly the table columns minus the hashes (hashes are verification internals, not API surface; expose them only if you later build client-side verification).

### The chain verifier

`src/vaultlog/application/audit/verify.py` — runnable as a CLI (`scripts/verify_chain.py`), a scheduled job, and a test:

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultlog.infrastructure.audit.hashing import canonical_event_bytes, compute_entry_hash
from vaultlog.infrastructure.database.models import AuditChainHeadModel, AuditEventModel


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    events_checked: int
    failure_sequence: int | None = None
    reason: str | None = None


async def verify_tenant_chain(session: AsyncSession, tenant_id: uuid.UUID) -> VerificationResult:
    rows = (await session.scalars(
        select(AuditEventModel)
        .where(AuditEventModel.tenant_id == tenant_id)
        .order_by(AuditEventModel.sequence)
    )).all()

    expected_previous: bytes | None = None
    expected_sequence = 1

    for row in rows:
        # 1. Sequence continuity: no gaps, no reordering.
        if row.sequence != expected_sequence:
            return VerificationResult(False, expected_sequence - 1, row.sequence,
                                      f"sequence gap: expected {expected_sequence}, found {row.sequence}")

        # 2. Link integrity: this row must name the actual previous hash.
        if row.previous_hash != expected_previous:
            return VerificationResult(False, row.sequence - 1, row.sequence,
                                      "previous_hash link broken")

        # 3. Content integrity: recompute from the stored fields.
        recomputed = compute_entry_hash(
            expected_previous,
            canonical_event_bytes(
                tenant_id=row.tenant_id, sequence=row.sequence,
                actor_user_id=row.actor_user_id, session_id=row.session_id,
                action=row.action, target_type=row.target_type,
                target_id=row.target_id, outcome=row.outcome,
                metadata=row.event_metadata, occurred_at=row.occurred_at,
            ),
        )
        if recomputed != row.entry_hash:
            return VerificationResult(False, row.sequence - 1, row.sequence,
                                      "entry_hash mismatch — content altered")

        expected_previous = row.entry_hash
        expected_sequence += 1

    # 4. Head consistency: the chain head must agree with the last event.
    head = await session.scalar(
        select(AuditChainHeadModel).where(AuditChainHeadModel.tenant_id == tenant_id)
    )
    if head is not None and (head.last_hash != expected_previous or head.last_sequence != expected_sequence - 1):
        return VerificationResult(False, expected_sequence - 1, None, "chain head inconsistent with events")

    return VerificationResult(True, expected_sequence - 1)
```

Read the four checks as answering four different attack or failure modes: **(1)** row deleted or inserted out of order; **(2)** rows rewritten and re-linked imperfectly; **(3)** a field silently edited in place; **(4)** head rolled back while events kept (or vice versa). A verifier that only recomputed hashes would miss deletion; one that only checked links would miss content edits. All four are required.

The CLI wrapper:

```python
# scripts/verify_chain.py
import asyncio, sys, uuid
from vaultlog.infrastructure.database.engine import build_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import text
from vaultlog.application.audit.verify import verify_tenant_chain
from vaultlog.shared.config import get_settings

async def main(tenant_id: uuid.UUID) -> int:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(tenant_id)})
        result = await verify_tenant_chain(session, tenant_id)
    await engine.dispose()
    print(result)
    return 0 if result.ok else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main(uuid.UUID(sys.argv[1]))))
```

Note it runs as `vaultlog_app` with tenant context set — verification needs *read* access only, and it proves RLS doesn't hide history from its rightful tenant.

***

## 7. Tests

`tests/unit/test_audit_hashing.py`:

```python
import uuid
from datetime import UTC, datetime

from vaultlog.infrastructure.audit.hashing import canonical_event_bytes, compute_entry_hash

T, U, S, X = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
AT = datetime(2026, 7, 29, 12, 0, 0, tzinfo=UTC)


def _canonical(**overrides):
    kwargs = dict(
        tenant_id=T, sequence=1, actor_user_id=U, session_id=S,
        action="secret.revealed", target_type="secret", target_id=X,
        outcome="success", metadata={"version": 3}, occurred_at=AT,
    )
    kwargs.update(overrides)
    return canonical_event_bytes(**kwargs)


def test_golden_vector() -> None:
    """Pins the format forever. If this breaks, you changed the hash format —
    knowingly or not. Old chains verify only under the old format."""
    assert _canonical() == (
        b'{"action":"secret.revealed","actor_user_id":"%s","metadata":{"version":3},'
        b'"occurred_at":"2026-07-29T12:00:00.000000Z","outcome":"success","sequence":1,'
        b'"session_id":"%s","target_id":"%s","target_type":"secret","tenant_id":"%s"}'
        % (str(U).encode(), str(S).encode(), str(X).encode(), str(T).encode())
    )


def test_key_order_is_canonical() -> None:
    a = canonical_event_bytes(
        tenant_id=T, sequence=1, actor_user_id=None, session_id=None,
        action="vault.created", target_type="vault", target_id=None,
        outcome="success", metadata={"b": 2, "a": 1}, occurred_at=AT,
    )
    b = canonical_event_bytes(
        tenant_id=T, sequence=1, actor_user_id=None, session_id=None,
        action="vault.created", target_type="vault", target_id=None,
        outcome="success", metadata={"a": 1, "b": 2}, occurred_at=AT,
    )
    assert a == b  # insertion order must not affect the hash


def test_genesis_differs_from_chained() -> None:
    canonical = _canonical()
    assert compute_entry_hash(None, canonical) != compute_entry_hash(b"\x00" * 32, canonical)
```

`tests/integration/test_audit_ledger.py` — the proofs that matter:

- **Atomicity:** perform a secret rotation; verify one `secret.rotated` row exists and the chain verifies. Then force a use case to raise *after* the audit write (e.g., patch a downstream call to throw); verify **both** the mutation and the audit row are absent — rollback took them together.
- **Immutability at the DB layer:** connect as `vaultlog_app`, attempt `UPDATE audit_event SET outcome='failure'` and `DELETE FROM audit_event` → both raise insufficient-privilege errors.
- **Tamper detection:** as the *owner* role, flip one `metadata` value in an early row → `verify_tenant_chain` returns `ok=False` with `reason="entry_hash mismatch — content altered"` at exactly that sequence. Delete the middle row → detected as a sequence gap. Swap two rows' `previous_hash` values → link break detected.
- **Concurrency:** fire 20 concurrent reveals in one tenant; all 20 succeed, sequences are exactly 1..20 with no gaps, chain verifies. (This test proves the `FOR UPDATE` design under real contention — run it, don't just believe it.)
- **Metadata guard:** passing `metadata={"value": "hunter2"}` raises `AuditMetadataError`; nested `{"debug": {"password": "x"}}` also caught.
- **Denial recording:** an unauthorized reveal attempt produces an `access.denied` row with `outcome="denied"` — and the chain still verifies (denials are chain members like any event).
- **Cross-tenant:** tenant B's scoped session cannot select tenant A's events (RLS), and tenant A's chain verification is unaffected by tenant B's activity.

## 8. ADR

`docs/adr/0007-hash-chained-append-only-audit-ledger.md`:

```markdown
# ADR 0007: Hash-chained, append-only audit ledger with per-tenant chains

- Status: Accepted
- Date: 2026-07-29

## Context
A secrets manager must provide provable history: who accessed what, when,
and with what outcome. Insider threats include users with database access,
so "the app doesn't provide an update endpoint" is insufficient.

## Decision
- Append-only audit_event table; app role holds SELECT+INSERT only —
  UPDATE/DELETE are physically impossible at the privilege level.
- Per-tenant hash chains: entry_hash = SHA-256(previous_hash || canonical),
  canonical = sorted-keys, whitespace-free JSON with fixed datetime format.
- Per-tenant chain head row locked with SELECT ... FOR UPDATE serializes
  appends and provides the ordering guarantee under concurrency.
- Business mutations and their audit events commit in ONE transaction
  (UoW). Denials are audited in a separate immediate transaction.
- Audit metadata passes through a forbidden-key guard; plaintext, tokens,
  codes, and keys can never enter the ledger.
- Chain verification (sequence continuity, link integrity, content
  integrity, head consistency) runs in CI and as an operational command.
- Hash chains provide tamper EVIDENCE, not tamper impossibility: an attacker
  with owner-level DB access can rewrite and recompute. External anchoring
  of chain-head digests (signed, stored in WORM storage or an independent
  logging service on a schedule) is the documented next step.

## Consequences
- Concurrent writes within one tenant serialize on the chain head (accepted;
  measured by the concurrency test, acceptable at expected volumes).
- Canonicalization is a frozen, versioned format — changing it invalidates
  historical verification and requires a format-version migration.
- Organization deletion is RESTRICTed by audit FKs; org teardown becomes an
  explicit archival procedure, not a cascade.
```

## 9. Completion checklist

- [ ] Migration applied: both tables, RLS ×2, app role lacks UPDATE/DELETE on `audit_event`, DELETE on `audit_chain_head`.
- [ ] Canonicalization is one shared function; golden-vector test pins the format.
- [ ] Genesis entry chains to a domain separator, not empty bytes.
- [ ] Every state-changing use case (Chapters 5–6) now records its audit event in-transaction.
- [ ] `session_id` threaded from Principal through to audit rows.
- [ ] Denials recorded via separate immediate transaction with `outcome="denied"`.
- [ ] Forbidden metadata keys rejected, including nested dictionaries.
- [ ] Verifier implements all four checks; tamper tests prove each one fires.
- [ ] Concurrency test: 20 parallel appends, gapless sequences, chain verifies.
- [ ] DB-level immutability proven by negative privilege tests.
- [ ] Read endpoint is owner/admin-only, keyset-paginated, RLS-scoped.

## Chapter outcome

VaultLog can now answer for itself. Every reveal, rotation, grant, and denial is written into a ledger that the application itself cannot rewrite, that silent tampering cannot survive, and that any operator can verify with one command. Combined with the previous chapters, the system now has the complete security loop: **identity (3–4), authorization (5), confidentiality (6), and accountability (7)** — each enforced at multiple independent layers, each failing closed.

**Chapter 8** hardens the edges the first seven chapters deliberately deferred: rate limiting, security headers, structured error handling, request-ID correlation, CSRF posture for the cookie flow, dependency/secret scanning in CI, and the full security regression suite wired into a pipeline — the difference between a secure design and a deployable one.

# VaultLog Backend
## Chapter 8 — Security hardening and the production pipeline

**Goal:** Harden the edges every previous chapter deliberately deferred: rate limiting, structured error handling, security headers, request-ID correlation, CSRF protection for the cookie flow, log redaction, and a CI pipeline that enforces all of it — plus the consolidated security regression suite that turns the whole book's guarantees into executable proof.

**Time budget:** 25–35 minutes.

**Why this chapter exists:** Chapters 1–7 built a system whose *design* is secure. This chapter makes it *operationally* secure. Most real breaches don't defeat cryptography — they walk through an unrate-limited login endpoint, a verbose stack trace, a poisoned dependency, or a missing header. Hardening is not polish; it is the difference between a fortress and a fortress with the side gate propped open.

***

Excellent instinct — that's exactly the right question to ask, and you're correct. Dev/prod parity is a real principle (it's literally one of the twelve-factor app tenets), and rate limiting is precisely the kind of component where an in-memory stand-in hides bugs: atomicity races, key expiry behavior, distributed semantics across multiple app instances. Let me revise that section of Chapter 8 properly.

# Chapter 8 — Section 1 (revised): Rate limiting with Redis in all environments

## Why Redis everywhere, not just production

My initial suggestion of in-memory-for-dev was the wrong call for three reasons:

1. **Environment parity:** The in-memory implementation would have had subtly different semantics — no TTL-based key cleanup, no atomic increments, per-process state. Any bug those differences hide ships to production undetected.
2. **Multi-instance honesty:** Even locally, the moment you run two uvicorn workers (`--workers 2`) or the app plus a background job, in-memory limits silently double. Redis behaves identically at one instance or fifty.
3. **It's cheap:** Redis is one service block in the Compose file you already have. The "simplicity" argument for in-memory doesn't survive contact with how trivial the container is.

The one legitimate use of the in-memory `Bucket` class: **unit tests** of the token-bucket math itself. Keep it for that, but the application never uses it.

## Compose

Add to `compose.yaml`:

```yaml
services:
  postgres:
    # ... unchanged from Chapter 2 ...

  redis:
    image: redis:7-alpine
    container_name: vaultlog-redis
    restart: unless-stopped
    command: ["redis-server", "--maxmemory", "64mb", "--maxmemory-policy", "allkeys-lru"]
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
```

Notes on the choices:

- **`allkeys-lru` eviction with a small memory cap:** rate-limit keys are ephemeral counters; if memory fills, evicting old limiter keys is harmless (worst case, a few extra requests get through). Never use a no-eviction policy for this workload — a full Redis that errors on writes would either break requests or fail-open your limits depending on how you handle it.
- **No persistence needed:** losing rate-limit state on restart is acceptable (it's a 5-minute window of counters). Don't add AOF/RDB here. This is also why VaultLog's Redis is *not* a session store — refresh sessions live in PostgreSQL (Chapter 3), where durability is guaranteed. Keep that boundary clear: **Redis holds only data you're willing to lose.**
- **No password locally,** but in production use your platform's managed Redis (Memorystore on GCP) with TLS and AUTH — it's network-isolated there, not exposed.

Install the client:

```bash
uv add redis
```

Add to `.env` / `.env.example` and `Settings`:

```dotenv
REDIS_URL=redis://localhost:6379/0
```

```python
redis_url: str = "redis://localhost:6379/0"
```

## The sliding-window limiter on Redis

Token bucket in Redis requires Lua scripting for atomicity; a **sliding-window log** with sorted sets is simpler to implement atomically with a single pipeline and has excellent precision. Create `src/vaultlog/infrastructure/security/rate_limit.py` (replacing the earlier version):

```python
from __future__ import annotations

import time
import uuid

import redis.asyncio as redis


class RateLimiter:
    """Sliding-window counter backed by Redis sorted sets.

    Each key is a ZSET of request timestamps. On check:
      1. drop entries older than the window,
      2. count what remains,
      3. if under the limit, add this request and allow.
    All four commands run in ONE pipeline (MULTI/EXEC), so concurrent
    instances can't interleave between count and add — the race that
    breaks naive implementations.
    """

    def __init__(self, client: redis.Redis) -> None:
        self._redis = client

    async def check(self, key: str, *, capacity: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds
        member = f"{now}:{uuid.uuid4()}"  # unique member per request

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {member: now})
            pipe.expire(key, window_seconds)  # self-cleaning keys
            _, count, _, _ = await pipe.execute()

        if count >= capacity:
            # Over the limit: remove the optimistic add so rejected
            # requests don't consume quota.
            await self._redis.zrem(key, member)
            return False
        return True
```

Design decisions worth understanding:

- **Why sorted sets over simple `INCR` with expiry:** `INCR`-per-fixed-window has the boundary problem — 5 requests at 11:59:59 plus 5 at 12:00:01 means 10 requests in 2 seconds while both "windows" show legal counts. Sliding windows have no boundary to exploit.
- **The rollback on rejection** (`zrem` of the optimistic add) keeps rejected requests from counting against the quota. Without it, an attacker hammering a limited endpoint inflates their own count — which sounds like it self-throttles, but it also means a *victim* whose account is being brute-forced accumulates phantom usage and stays locked out longer after the attack stops.
- **`expire` on every check** ensures idle keys vanish; Redis won't accumulate millions of stale keys from one-off IPs.
- **Failure posture — decide it explicitly:** if Redis is *down*, do you fail open (allow) or closed (deny)? For VaultLog: **fail open on availability endpoints** (reveal, vault list — denial of service against legitimate users is the worse outcome; the DB, RLS, and crypto layers still protect data), and **fail closed on credential endpoints** (login, MFA verify — these exist to be throttled; an unthrottled login endpoint is worse than a temporarily unavailable one). Implement as a parameter:

```python
async def check(self, key, *, capacity, window_seconds, fail_closed: bool = False) -> bool:
    try:
        ...  # pipeline logic above
    except redis.RedisError:
        if fail_closed:
            raise
        return True
```

## Wiring

Create the client in the app lifespan (Chapter 2's pattern — one pool per process):

```python
# main.py lifespan
redis_client = redis.from_url(settings.redis_url, decode_responses=False)
app.state.rate_limiter = RateLimiter(redis_client)
yield
await redis_client.aclose()
```

Dependency provider in `dependencies.py`:

```python
async def get_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.rate_limiter
```

And the endpoint guard, updated for async + failure posture:

```python
def rate_limit(bucket: str, *, capacity: int, window_seconds: int, fail_closed: bool = False):
    async def dependency(
        request: Request,
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        identity = request.client.host if request.client else "unknown"
        try:
            allowed = await limiter.check(
                f"rl:{bucket}:{identity}",
                capacity=capacity, window_seconds=window_seconds,
                fail_closed=fail_closed,
            )
        except redis.RedisError:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Service unavailable")
        if not allowed:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Too many requests",
                headers={"Retry-After": str(window_seconds)},
            )
    return dependency
```

Apply with `fail_closed=True` on `login`, `mfa/verify`, `step-up/verify`, and `register`; default (fail open) elsewhere. The account-keyed check inside `LoginUser` uses the same limiter instance passed into the use case.

## Tests now run against real Redis

Since Compose already provides it, integration tests use the genuine implementation — no mocks:

```python
@pytest.fixture()
async def limiter(redis_client):
    limiter = RateLimiter(redis_client)
    yield limiter
    await redis_client.flushdb()  # clean slate per test


async def test_allows_up_to_capacity(limiter):
    for _ in range(5):
        assert await limiter.check("rl:test:a", capacity=5, window_seconds=60)
    assert not await limiter.check("rl:test:a", capacity=5, window_seconds=60)


async def test_rejected_requests_do_not_consume_quota(limiter):
    for _ in range(10):  # 5 allowed, 5 rejected
        await limiter.check("rl:test:b", capacity=5, window_seconds=60)
    # exactly 5 entries, not 10 — the zrem rollback worked
    assert await redis_client.zcard("rl:test:b") == 5


async def test_concurrent_instances_share_state(limiter, redis_client):
    """Two RateLimiter objects (simulating two app instances) share ONE limit."""
    other = RateLimiter(redis_client)
    for _ in range(3):
        await limiter.check("rl:test:c", capacity=5, window_seconds=60)
    for _ in range(2):
        await other.check("rl:test:c", capacity=5, window_seconds=60)
    assert not await other.check("rl:test:c", capacity=5, window_seconds=60)
    assert not await limiter.check("rl:test:c", capacity=5, window_seconds=60)
```

That last test is the one the in-memory version could never pass honestly — it's the entire argument for this revision, executable.

Also update the ADR decision line:

```markdown
- Token-bucket/sliding-window rate limiting backed by Redis in ALL
  environments (Compose locally, Memorystore in production); in-memory
  buckets exist only for unit-testing limiter math. Redis holds only
  disposable counters — sessions and durable state stay in PostgreSQL.
```

## 1. Rate limiting

### Theory: what rate limiting actually defends

Rate limiting answers attacks that are cheap for the attacker and expensive for you:

| Attack | Target endpoint | Defense |
|---|---|---|
| Password brute force / credential stuffing | `POST /auth/login` | Per-account + per-IP limits, progressive slowdown |
| TOTP guessing (1M codes in 5 min) | `POST /auth/mfa/verify` | Strict per-challenge limit — 6-digit codes are only safe under throttling |
| Recovery-code guessing | Same MFA endpoint | Same bucket as TOTP |
| Refresh-token probing | `POST /auth/refresh` | Per-IP limit (abuse also triggers reuse detection from Ch. 3) |
| Enumeration via timing/volume | Register, member invite | Per-IP limits + generic responses (already built) |
| Secret scraping | `POST .../reveal` | Per-user limit — a compromised token shouldn't yield the whole vault in seconds |

The load-bearing insight: **your cryptography's strength assumes rate limiting exists.** A 6-digit TOTP has ~20 bits of entropy — trivially brute-forced *online* if the endpoint accepts unlimited attempts. `valid_window=1` from Chapter 4 gives an attacker 3 valid codes per million at any moment; that's safe at 5 attempts per challenge, catastrophic at 5,000. Rate limiting is not an operational nicety layered on top of security — it is part of the security argument for the algorithms you chose.

### Implementation: token bucket per key, Redis in production

Create `src/vaultlog/infrastructure/security/rate_limit.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Bucket:
    capacity: int
    refill_per_second: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def try_consume(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.last_refill) * self.refill_per_second)
        self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """In-memory limiter for local dev and tests.

    PRODUCTION NOTE: replace with Redis (or a managed limiter) — in-memory
    buckets reset per instance, so N Cloud Run instances = N times the
    intended limit. The interface is what matters; swap the storage.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, Bucket] = {}

    def check(self, key: str, *, capacity: int, window_seconds: int) -> bool:
        bucket = self._buckets.setdefault(
            key, Bucket(capacity=capacity, refill_per_second=capacity / window_seconds)
        )
        return bucket.try_consume()
```

The FastAPI dependency — `presentation/dependencies.py` addition:

```python
class RateLimitExceeded(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": "60"},
        )


def rate_limit(bucket: str, *, capacity: int, window_seconds: int, by: str = "ip"):
    """by='ip' keys on client IP; by='account' keys on the submitted identifier
    (compose both checks in the endpoint for login)."""
    limiter = RateLimiter()

    async def dependency(request: Request) -> None:
        if by == "ip":
            identity = request.client.host if request.client else "unknown"
        else:
            identity = "global"  # overridden per-endpoint for account keys
        if not limiter.check(f"{bucket}:{identity}", capacity=capacity, window_seconds=window_seconds):
            raise RateLimitExceeded()

    return dependency
```

Apply the policy matrix:

| Endpoint | Key | Limit | Window |
|---|---|---|---|
| `POST /auth/login` | IP **and** email | 5 / 20 | 5 min / 15 min |
| `POST /auth/mfa/verify` | challenge token's `sub` | 5 | 5 min (challenge lifetime) |
| `POST /auth/register` | IP | 10 | 1 hour |
| `POST /auth/refresh` | IP | 60 | 5 min |
| `POST /auth/step-up/verify` | user ID | 5 | 5 min |
| `POST .../secrets/{id}/reveal` | user ID | 100 | 5 min |
| `POST /auth/mfa/enroll` | user ID | 5 | 1 hour |

Login gets *both* keys checked: per-IP (stops distributed stuffing against one account from one box) and per-account (stops distributed stuffing of one account from a botnet). Neither alone is sufficient — that's a common and consequential gap.

For account-keyed limits, implement inside the use case (where the email is available) rather than the dependency — call `limiter.check(f"login:acct:{email}")` before password verification, and raise the same generic `AuthError` on failure so throttling doesn't become an account-existence oracle.

***

## 2. Structured error handling

Right now, exceptions leak framework defaults. Production needs one consistent, leak-free shape. Create `src/vaultlog/presentation/errors.py`:

```python
from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger()


def error_body(code: str, message: str, request_id: str | None) -> dict:
    return {"error": {"code": code, "message": message, "request_id": request_id}}


def register_error_handlers(app: FastAPI) -> None:

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Client errors: safe to echo our own detail (we wrote them).
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(f"http_{exc.status_code}", str(exc.detail), getattr(request.state, "request_id", None)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 422 with SANITIZED detail: which fields failed, never the values.
        fields = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "validation_failed", "fields": fields,
                               "request_id": getattr(request.state, "request_id", None)}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
        # THE security-critical handler. Log everything internally;
        # return nothing but a reference externally.
        logger.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body("internal_error", "An internal error occurred",
                               getattr(request.state, "request_id", None)),
        )
```

Register in `create_app()`: `register_error_handlers(app)`.

The doctrine in one sentence: **internals get stack traces with request IDs; externals get a code and the same request ID** — support can correlate a user report to logs without ever sending the user a stack trace. The validation handler strips `input` values from Pydantic errors deliberately: a failed `SecretCreateRequest` validation would otherwise echo the submitted secret value back in the 422 response body. Read that sentence twice — it's the kind of leak that survives code review because 422 details *look* helpful.

***

## 3. Request-ID correlation middleware

Every log line and error response from Chapters 7–8 references `request_id`. Generate it in middleware — `src/vaultlog/presentation/middleware.py`:

```python
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        # Reject absurdly long client-supplied IDs: they land in every log line.
        request_id = request_id[:64]
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "method", "path")
```

Register **first** in `create_app()` (middleware executes in reverse registration order — first registered is outermost). Now every structlog event in the request lifecycle carries the ID automatically, and Chapter 7's audit `metadata` can include it for end-to-end traceability: audit row → request → log lines.

Trust note: accepting a client-supplied `X-Request-ID` aids debugging (the client can quote its own ID) but the 64-char cap and treating it as opaque text prevent log-injection games.

***

## 4. Security headers

Add a headers middleware (same file):

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
        # HSTS only behind real HTTPS — Cloud Run terminates TLS, so enable
        # in production via settings, never in local http dev.
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
```

Why each header earns its place for an API (not just web pages):

- **`X-Content-Type-Options: nosniff`** — stops browsers from MIME-sniffing a JSON error response into executable HTML. Old attack class, still real.
- **`X-Frame-Options: DENY` + CSP `frame-ancestors 'none'`** — your API responses must never render inside an iframe (clickjacking defense; CSP version is the modern one, both for compatibility).
- **`Referrer-Policy: no-referrer`** — URLs can carry IDs (`/vaults/{uuid}`); don't leak them into referrer headers to third parties.
- **`default-src 'none'`** — for a pure JSON API, the correct CSP is "load nothing, ever." The React frontend gets its own, separate policy when served.
- **HSTS** — once set, browsers refuse plaintext HTTP to your domain for a year. Only enable after HTTPS works universally, because it's sticky.

***

## 5. CSRF posture for the refresh-cookie flow

Chapter 3 put the refresh token in a `SameSite=Lax` cookie scoped to `/api/v1/auth`. Assess precisely which endpoints are cookie-authenticated and state-changing:

- `POST /auth/refresh`, `POST /auth/logout` — these are the *only* endpoints that authenticate via cookie.

`SameSite=Lax` already blocks cross-site POSTs carrying the cookie in modern browsers. But "modern browsers" is doing work in that sentence, and a senior design doesn't rely on a single mechanism. Add explicit CSRF defense for cookie-bearing endpoints — the **Origin check** pattern, appropriate here because these endpoints have no token in the request body to double-submit:

```python
class OriginCheckMiddleware(BaseHTTPMiddleware):
    """For cookie-authenticated mutation endpoints only: require Origin to
    match an allowed frontend origin. Browsers always send Origin on
    cross-origin POSTs; attackers cannot forge it from a victim's browser."""

    PROTECTED_PREFIXES = ("/api/v1/auth/refresh", "/api/v1/auth/logout")

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and any(
            request.url.path.startswith(p) for p in self.PROTECTED_PREFIXES
        ):
            origin = request.headers.get("origin")
            allowed = {o.strip() for o in settings.cors_origins.split(",") if o.strip()}
            if origin is not None and origin not in allowed:
                return JSONResponse(status_code=403, content=error_body("csrf_origin_mismatch", "Forbidden", None))
        return await call_next(request)
```

Note `origin is not None and ...`: non-browser clients (curl, scripts) send no Origin and are allowed — they can't be CSRF vectors because CSRF requires a browser. The refresh endpoint returning 401-not-403 on a *successful* cross-site POST would be the real risk; rotation means a silent CSRF-triggered refresh would burn the victim's current refresh token — an availability nuisance, not a compromise, but the Origin check removes it cleanly.

***

## 6. Log redaction — the last plaintext leak

Chapter 6's canary test checks for one secret value. Systematize it: a structlog processor that redacts known-dangerous keys from every event, forever — `shared/logging.py` addition:

```python
REDACTED_KEYS = frozenset({
    "password", "value", "plaintext", "token", "refresh_token", "access_token",
    "step_up_token", "challenge_token", "code", "totp", "seed", "dek", "kek",
    "secret", "authorization", "cookie", "set-cookie",
})


def redact_processor(logger, method, event_dict):
    def scrub(obj):
        if isinstance(obj, dict):
            return {
                k: "[REDACTED]" if str(k).lower() in REDACTED_KEYS else scrub(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [scrub(i) for i in obj]
        return obj

    return scrub(event_dict)
```

Add `redact_processor` to the structlog processor chain, right before `JSONRenderer`. Belt-and-suspenders alongside Chapter 7's audit-metadata guard: even when a future developer writes `logger.info("debug", value=plaintext)` — and someone eventually will — the log pipeline itself refuses to emit it. **Pipelines that make the dangerous thing impossible beat conventions that make it discouraged.**

Add the regression test: log a dict containing every redacted key plus a canary value, capture stdout, assert neither keys' values nor the canary appear.

***

## 7. The consolidated security regression suite

Everything from eight chapters, assembled into one suite that runs in CI — `tests/security/`. The suite is the book's promises, executable:

```text
tests/security/
├── test_tenant_isolation.py        # Ch. 2: RLS cross-tenant, unscoped, WITH CHECK
├── test_auth_security.py           # Ch. 3: alg confusion, wrong aud/iss, tampered JWT,
│                                   #      refresh reuse → family revocation, cookie flags
├── test_mfa_security.py            # Ch. 4: challenge/step-up purpose confusion,
│                                   #      session binding, single-use recovery codes
├── test_authorization.py           # Ch. 5: full matrix, viewer cap, 404-vs-403, IDOR
├── test_crypto_security.py         # Ch. 6: tamper, AAD transplant, wrong DEK/KEK,
│                                   #      DEK rotation continuity, nonce uniqueness
├── test_audit_integrity.py         # Ch. 7: tamper detection ×3 modes, app-role
│                                   #      UPDATE/DELETE denied, atomicity, concurrency
├── test_hardening.py               # Ch. 8: rate limits fire 429, error shape has no
│                                   #      stack traces, 422 has no input values,
│                                   #      headers present, origin check enforced
└── test_log_safety.py              # Ch. 6+8: canary plaintext absent from all logs,
                                    #      redaction processor works
```

Three representative hardening tests — `tests/security/test_hardening.py`:

```python
async def test_login_rate_limit_fires(client, registered_user):
    for _ in range(5):
        await client.post("/api/v1/auth/login", json={"email": registered_user.email, "password": "wrong password 12"})
    response = await client.post("/api/v1/auth/login", json={"email": registered_user.email, "password": "wrong password 12"})
    assert response.status_code == 429
    assert "retry-after" in {k.lower() for k in response.headers.keys()}


async def test_500_response_leaks_nothing(client, monkeypatch):
    # Force an unhandled error inside an endpoint.
    monkeypatch.setattr(some_use_case_module, "ListVaults", ExplodingUseCase)
    response = await client.get("/api/v1/vaults", headers=auth_headers())
    assert response.status_code == 500
    body = response.json()["error"]
    assert body["code"] == "internal_error"
    assert "Traceback" not in response.text and "File \"/" not in response.text
    assert body["request_id"]


async def test_validation_error_omits_submitted_secret(client, auth_headers, vault_id):
    canary = "CANARY-SECRET-VALUE-7f3d"
    response = await client.post(
        f"/api/v1/vaults/{vault_id}/secrets",
        json={"name": "", "value": canary},   # name fails validation
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert canary not in response.text
```

That last test is worth the entire section: without the sanitized 422 handler, Pydantic's default error body would have reflected the canary straight back — to logs, to error trackers, to anyone reading responses.

***

## 8. The CI pipeline

`.github/workflows/ci.yml` — every check from the book, enforced on every push:

```yaml
name: CI
on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-groups
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run mypy

  security-scans:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-groups
      - name: Dependency vulnerability audit
        run: uv run pip-audit --strict
      - name: Secret scanning
        uses: gitleaks/gitleaks-action@v2
        env:
          GITLEAKS_ENABLE_COMMENTS: "false"

  test:
    runs-on: ubuntu-latest
    needs: [quality, security-scans]
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: vaultlog_test
          POSTGRES_USER: vaultlog_owner
          POSTGRES_PASSWORD: ci-owner-password
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U vaultlog_owner -d vaultlog_test"
          --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      DATABASE_HOST: localhost
      DATABASE_NAME: vaultlog_test
      DATABASE_USER: vaultlog_app
      DATABASE_PASSWORD: ci-app-password
      MIGRATION_DATABASE_USER: vaultlog_owner
      MIGRATION_DATABASE_PASSWORD: ci-owner-password
      ENVIRONMENT: test
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-groups

      - name: Provision CI database roles
        run: |
          psql "postgresql://vaultlog_owner:ci-owner-password@localhost:5432/vaultlog_test" \
            -c "CREATE ROLE vaultlog_app LOGIN PASSWORD 'ci-app-password' NOBYPASSRLS;" \
            -c "GRANT CONNECT ON DATABASE vaultlog_test TO vaultlog_app;" \
            -c "GRANT USAGE ON SCHEMA public TO vaultlog_app;"

      - name: Generate test keys
        run: |
          mkdir -p keys
          openssl genrsa -out keys/jwt-private.pem 2048
          openssl rsa -in keys/jwt-private.pem -pubout -out keys/jwt-public.pem
          echo "MASTER_KEY_B64=$(python -c 'import os,base64; print(base64.b64encode(os.urandom(32)).decode())')" >> "$GITHUB_ENV"
          echo "MFA_KEK_B64=$(python -c 'import os,base64; print(base64.b64encode(os.urandom(32)).decode())')" >> "$GITHUB_ENV"

      - name: Migrations apply cleanly from empty schema
        run: uv run alembic upgrade head

      - name: Full test suite
        run: uv run pytest --cov=vaultlog --cov-report=term-missing --cov-fail-under=85

      - name: Security regression suite (explicit, must pass alone)
        run: uv run pytest tests/security -v

      - name: Audit chain verification smoke test
        run: uv run pytest tests/integration/test_audit_ledger.py -v
```

Pipeline design notes:

- **`pip-audit --strict`** fails the build on known CVEs in your dependency tree. Combined with Dependabot (enable it in repo settings) this closes the "poisoned/vulnerable dependency" class. Crypto and auth libraries (`cryptography`, `pyjwt`, `argon2-cffi`) deserve immediate-response upgrades when advisories land.
- **gitleaks** catches the day someone commits `keys/jwt-private.pem` or a real `.env`. The `.gitignore` from Chapter 1 is the first wall; scanning is the wall that survives human error.
- **Migrations run against a truly empty schema** in CI every push — the only way to know your migration chain is reproducible and your RLS/grant statements actually execute in order.
- **The security suite runs as its own step**, visibly, so a red build names the broken *guarantee*, not just a test file.
- Coverage gate at 85%: not a security metric, but it prevents the slow rot where critical paths lose test coverage unnoticed.

Add branch protection: require the `test` job to pass before merge. A security suite that can be merged around is documentation, not enforcement.

***

## 9. Operations: the minimum viable observability

Before Chapter 9's deployment, wire the alerts that make the security model *self-reporting*. With structlog already emitting JSON events, these are log-based alerts (Cloud Logging → metrics → alerts in GCP; equivalents everywhere):

| Signal | Source | Threshold suggestion | Meaning |
|---|---|---|---|
| `refresh_reuse_detected` revocations | auth_session updates | > 3/hour | Active token theft or broken client — investigate |
| `access.denied` audit events | audit ledger | spike vs baseline | Probing/IDOR attempts in progress |
| 429 rate-limit hits | middleware | sustained high rate | Brute force underway (or a limit set too tight) |
| `secret.revealed` volume per user | audit ledger | > 3× user baseline | Possible token compromise — mass exfiltration pattern |
| Audit chain verification failure | scheduled verifier job | **any** | Page someone. This is the smoke-alarm of the whole system. |
| `unhandled_exception` rate | error handler | > 1% of requests | Bugs creating availability and info-leak risk |

Schedule `scripts/verify_chain.py` (Chapter 7) to run per tenant on an interval — hourly is reasonable — via Cloud Scheduler or your platform's cron. Its failure mode must be loud: this is the control that converts the hash chain from "tamper-evident in principle" to "tamper-*detected* in practice."

***

## 10. ADR and checklist

`docs/adr/0008-hardening-and-pipeline-controls.md`:

```markdown
# ADR 0008: Hardening controls and CI enforcement

- Status: Accepted
- Date: 2026-07-29

## Context
Cryptographic strength assumes online throttling; error paths leak more
than success paths; cookie flows carry CSRF exposure; dependencies and
committed secrets are top breach vectors. Design security without
operational enforcement decays silently.

## Decision
- Token-bucket rate limiting on auth, MFA, step-up, and reveal endpoints;
  dual-key (IP + account) on login. In-memory locally, Redis in production.
- Unified error contract: sanitized 422 (no input values), generic 500 with
  request ID, structured internal logs.
- Security headers middleware; HSTS gated on HTTPS; Origin check on
  cookie-authenticated mutations as CSRF defense-in-depth behind SameSite.
- Log pipeline redaction of dangerous keys — pipeline-enforced, not
  convention-enforced.
- CI enforces lint/types, pip-audit, gitleaks, migrations-from-empty, full
  suite, and a standalone security regression job; branch protection
  requires it.
- Log-based alerting on reuse detection, denial spikes, reveal anomalies,
  500 rates, and any audit-chain verification failure (scheduled verifier).

## Consequences
- Rate limits need tuning runbooks; false 429s are an availability cost.
- Redis becomes an operational dependency in production.
- The security suite is a merge gate: changing a guarantee means changing
  its test in the same PR, with review.
```

## Completion checklist

- [ ] Rate limits active on all seven endpoint classes; 429 tests pass with `Retry-After`.
- [ ] Error contract: 500 leaks nothing, 422 omits input values, all errors carry `request_id`.
- [ ] Request-ID middleware binds structlog context; ID echoed in response headers.
- [ ] Security headers on every response; HSTS only over HTTPS.
- [ ] Origin check on refresh/logout; foreign-origin POST rejected, origin-less clients unaffected.
- [ ] Redaction processor in the logging pipeline; canary/redaction tests pass.
- [ ] `tests/security/` suite assembled and passing as a standalone step.
- [ ] CI: quality, scans, migrations-from-empty, full suite, security suite, coverage gate.
- [ ] Branch protection requires the pipeline.
- [ ] Alerting table implemented as log-based metrics; chain verifier scheduled.

## Chapter outcome

VaultLog is no longer just well-designed — it is *defended in operation*. Attacks that are cheap to attempt are expensive to sustain, errors confess nothing, logs keep no secrets, the pipeline refuses to merge regressions, and the system pages a human the moment its own integrity guarantees break.

**Chapter 9** ships it: the production Dockerfile, Cloud Run service topology, Secret Manager and Cloud KMS integration (swapping `LocalKEKProvider` for the real thing), migration jobs, connection pooling under autoscaling, and the production readiness review — the final gate between this codebase and real users.

# VaultLog Backend
## Chapter 9 — Production deployment: containers, Cloud Run, KMS, and the go-live gate

**Goal:** Ship VaultLog to production: a hardened multi-stage Dockerfile, a Cloud Run topology with Cloud SQL, real KMS replacing the local KEK, secrets in Secret Manager, migrations as separate jobs, correct connection math under autoscaling, TLS to the database, and a final production-readiness review you run before real users arrive.

**Time budget:** 35–45 minutes.

**Why deployment is a security chapter:** Everything you built assumes its environment. RS256 assumes the private key stays private; envelope encryption assumes the KEK never touches disk; RLS assumes the app connects as a least-privilege role over a channel nobody can sniff; audit alerts assume someone is watching. Deployment is where those assumptions are either made true or silently broken. A senior engineer treats infrastructure as part of the threat model — because attackers do.

***

## 1. Theory: what changes in production

| Concern | Local development | Production |
|---|---|---|
| KEK | Base64 env var (`LocalKEKProvider`) | Cloud KMS — key never exists in app memory, ever |
| Secrets (DB password, JWT private key) | `.env` file, git-ignored | Secret Manager, injected at runtime, access-audited |
| Database | Compose container, plaintext TCP | Cloud SQL / managed Postgres, TLS required, private IP where possible |
| Database role | Same roles, but you hold all passwords | App role credentials in Secret Manager; owner credentials used only by migration jobs |
| Migrations | `alembic upgrade head` by hand | Separate one-shot job, never at API startup |
| Instances | 1 process | 0–N autoscaled containers — connection math becomes a capacity limit |
| Rate limiting | Compose Redis | Memorystore Redis with TLS + AUTH |
| HTTPS | absent | Load balancer / Cloud Run managed TLS, HSTS active |
| Docs | `/docs` enabled | Disabled (already coded in Chapter 1 — verify `ENVIRONMENT=production` flips it) |
| Observability | terminal logs | Structured logs to Cloud Logging, alert policies from Chapter 8 live |

The recurring pattern: **everything that was a file or a variable locally becomes a managed, access-controlled, audited service in production.** Your code was designed for this (settings injection, `KEKProvider` interface, role separation) — now the environment catches up to the design.

***

## 2. The production Dockerfile

`Dockerfile` at repo root:

```dockerfile
# ---------- Build stage: resolve and install dependencies ----------
FROM python:3.13-slim AS builder
WORKDIR /app

RUN pip install --no-cache-dir uv

# Copy only dependency manifests first: this layer caches until
# pyproject.toml or uv.lock changes, making rebuilds fast.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev


# ---------- Runtime stage: minimal, non-root ----------
FROM python:3.13-slim AS runtime
WORKDIR /app

# Dedicated unprivileged user. If the app is ever compromised, the
# attacker's process has no root, no package manager rights, nothing.
RUN groupadd --gid 10001 vaultlog && \
    useradd --uid 10001 --gid vaultlog --no-create-home --shell /usr/sbin/nologin vaultlog

COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER vaultlog
EXPOSE 8080

# Cloud Run injects PORT. 2 workers is a sane start; see section 7 for
# the connection math that decides this number deliberately.
CMD ["sh", "-c", "uvicorn vaultlog.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers ${WORKERS:-2}"]
```

Security properties to note:

- **Two stages** mean compilers, pip, and build tooling never exist in the running image — smaller attack surface, smaller CVE count in scans, faster cold starts.
- **Non-root user with `nologin` shell.** Containers are not security boundaries the way VMs are; user namespace discipline inside the container is part of the defense.
- **No `.env`, no `keys/`, no tests, no dev dependencies in the image.** The JWT private key never exists as a file in production — it comes from Secret Manager as an environment variable (section 4), which is why Chapter 3's `TokenService` should be extended to accept PEM *content* from settings in addition to a path. Make that change now:

```python
# settings: jwt_private_key_pem: str | None = None  (takes precedence)
#           jwt_private_key_pem_path: str | None = None
# TokenService loads content if present, else reads the path. Same for public key.
```

- **Verify locally before deploying:**

```bash
docker build -t vaultlog-api:local .
docker run --rm -p 8080:8080 --env-file .env -e PORT=8080 vaultlog-api:local
curl http://localhost:8080/api/v1/health
```

Also add a `.dockerignore` so build context can't smuggle secrets into layers:

```gitignore
.env
.env.*
keys/
.git/
.venv/
tests/
docs/
```

***

## 3. GCP topology

```text
                         HTTPS (managed TLS)
                                │
                    ┌───────────▼────────────┐
                    │   Cloud Run: vaultlog  │  service account: vaultlog-api@...
                    │   min 0 / max 10 inst. │
                    └───┬────────┬────────┬──┘
                        │        │        │
              private IP│  TLS   │  API   │  API
                        │        │        │
              ┌─────────▼──┐  ┌──▼─────┐ ┌▼─────────────┐
              │ Cloud SQL  │  │Memory- │ │ Secret Mgr:  │
              │ Postgres 16│  │store   │ │ db-password  │
              │ (require   │  │ Redis  │ │ jwt-priv-key │
              │  SSL)      │  │        │ └──────────────┘
              └────────────┘  └────────┘ ┌──────────────┐
                                         │ Cloud KMS:   │
                                         │ vaultlog-kek │
                                         └──────────────┘
```

Provisioning outline (adjust names/regions — `europe-west3` fits your Frankfurt proximity):

```bash
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  secretmanager.googleapis.com cloudkms.googleapis.com redis.googleapis.com

# Database
gcloud sql instances create vaultlog-db --database-version=POSTGRES_16 \
  --tier=db-f1-micro --region=europe-west3 --require-ssl

# Roles inside the instance (same doctrine as Chapter 2):
#   vaultlog_owner (migrations), vaultlog_app (NOBYPASSRLS, runtime)
gcloud sql databases create vaultlog --instance=vaultlog-db

# KMS key ring + key
gcloud kms keyrings create vaultlog --location=europe-west3
gcloud kms keys create kek --keyring=vaultlog --location=europe-west3 \
  --purpose=encryption

# Secrets
printf '%s' 'APP_DB_PASSWORD' | gcloud secrets create vaultlog-db-password --data-file=-
gcloud secrets create vaultlog-jwt-private --data-file=keys/jwt-private.pem  # upload once, then the local copy's days are numbered

# Runtime service account with LEAST privilege
gcloud iam service-accounts create vaultlog-api
gcloud secrets add-iam-policy-binding vaultlog-db-password \
  --member="serviceAccount:vaultlog-api@PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding vaultlog-jwt-private \
  --member="serviceAccount:vaultlog-api@PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
gcloud kms keys add-iam-policy-binding kek --keyring=vaultlog --location=europe-west3 \
  --member="serviceAccount:vaultlog-api@PROJECT.iam.gserviceaccount.com" \
  --role="roles/cloudkms.cryptoKeyEncrypterDecrypter"
```

Read the IAM bindings carefully — they are the production expression of your whole key-hierarchy design: the service account can *use* the KMS key (encrypt/decrypt operations) but cannot export it, cannot administer it, and cannot read other secrets. If the Cloud Run service is compromised, the attacker can ask KMS to decrypt DEKs (which is why Chapters 2–5 exist), but cannot steal the KEK itself to exfiltrate-and-decrypt-later. That distinction is the entire value of a KMS over an env var.

***

## 4. The real KEK provider

`src/vaultlog/infrastructure/security/gcp_kms_provider.py`:

```python
from __future__ import annotations

import base64

from google.cloud import kms

from vaultlog.infrastructure.security.vault_crypto import CryptoError, KEKProvider


class GcpKmsProvider(KEKProvider):
    """Production KEK: wrap/unwrap are KMS RPCs. The key never leaves the HSM.

    Note on AAD: Cloud KMS supports additional_authenticated_data natively —
    pass our context bytes so wrap/unwrap are context-bound exactly like the
    local provider's AES-GCM AAD. Same property, managed implementation.
    """

    def __init__(self, key_resource_name: str) -> None:
        self._client = kms.KeyManagementServiceClient()
        self._key_name = key_resource_name  # projects/.../locations/.../keyRings/vaultlog/cryptoKeys/kek

    def wrap(self, dek: bytes, aad: bytes) -> tuple[bytes, bytes, str]:
        response = self._client.encrypt(
            request={"name": self._key_name, "plaintext": dek,
                     "additional_authenticated_data": aad}
        )
        # KMS output already embeds its framing; no separate nonce to store.
        return b"", response.ciphertext, self._key_name

    def unwrap(self, nonce: bytes, wrapped_dek: bytes, aad: bytes, wrapping_key_id: str) -> bytes:
        if wrapping_key_id != self._key_name:
            raise CryptoError("Unknown wrapping key")
        try:
            response = self._client.decrypt(
                request={"name": wrapping_key_id, "ciphertext": wrapped_dek,
                         "additional_authenticated_data": aad}
            )
        except Exception as exc:
            raise CryptoError("DEK unwrap failed") from exc
        return response.plaintext
```

Wire provider selection in settings:

```python
# Settings additions
kms_key_resource: str | None = None   # production
# Factory:
def build_kek_provider(settings) -> KEKProvider:
    if settings.kms_key_resource:
        return GcpKmsProvider(settings.kms_key_resource)
    return LocalKEKProvider()  # local/dev only
```

Everything from Chapter 6 — key versioning, AAD construction, rotation, the sweep job — works unchanged. **This is the payoff for the interface discipline**: the riskiest infrastructure swap in the project touches one factory function.

Also note the KEK-rotation story is now nearly free: create a new KMS key *version* (`gcloud kms keys versions create` — KMS rotates the underlying material); KMS continues decrypting ciphertexts made by old versions automatically. Your `wrapping_key_id` stays the same resource name. What you designed as a careful manual procedure in Chapter 6 becomes a routine operation in production — because you designed for it.

***

## 5. Migrations as jobs, never at startup

The rule from earlier chapters, now operationalized: **the API container must never run migrations.** With max-instances > 1, several containers starting simultaneously would race `alembic upgrade head`; with a bad migration, every instance crash-loops together and you get an outage *plus* a half-migrated schema.

Cloud Run Jobs are the right shape:

```bash
# Same image, different command — one revision of truth.
gcloud run jobs create vaultlog-migrate \
  --image gcr.io/PROJECT/vaultlog-api:SHA \
  --region europe-west3 \
  --service-account vaultlog-migrate@PROJECT.iam.gserviceaccount.com \
  --set-cloudsql-instances PROJECT:europe-west3:vaultlog-db \
  --set-secrets DATABASE_PASSWORD=vaultlog-owner-db-password:latest \
  --set-env-vars DATABASE_USER=vaultlog_owner,DATABASE_NAME=vaultlog,ENVIRONMENT=production \
  --command "alembic" --args "upgrade,head"

gcloud run jobs execute vaultlog-migrate --region europe-west3 --wait
```

Three details carry the doctrine:

1. **The migration job uses a *different service account and different secret*** — the owner-role database password — than the API service. Your Chapter 2 role separation survives deployment because the credentials are physically issued to different identities.
2. **Deploy order is migrate → deploy API**, and the migration must be *backward-compatible* with the currently-running API revision (expand-only migrations: add columns nullable, add tables, never rename/drop in the same release). This is the expand-contract pattern: expand schema → deploy code that uses it → (later release) contract old shapes. With RLS policies, be extra careful: a migration that alters `tenant_id` semantics mid-flight is an incident, not a deploy.
3. **`--wait` in CI/CD**, so a failed migration blocks the API deploy automatically.

***

## 6. Deploy the API

```bash
gcloud builds submit --tag gcr.io/PROJECT/vaultlog-api:$(git rev-parse --short HEAD)

gcloud run deploy vaultlog-api \
  --image gcr.io/PROJECT/vaultlog-api:$(git rev-parse --short HEAD) \
  --region europe-west3 \
  --service-account vaultlog-api@PROJECT.iam.gserviceaccount.com \
  --set-cloudsql-instances PROJECT:europe-west3:vaultlog-db \
  --set-secrets DATABASE_PASSWORD=vaultlog-db-password:latest,JWT_PRIVATE_KEY_PEM=vaultlog-jwt-private:latest \
  --set-env-vars "\
ENVIRONMENT=production,\
LOG_LEVEL=INFO,\
DATABASE_USER=vaultlog_app,\
DATABASE_NAME=vaultlog,\
DATABASE_HOST=/cloudsql/PROJECT:europe-west3:vaultlog-db,\
JWT_ISSUER=vaultlog,\
JWT_AUDIENCE=vaultlog-api,\
KMS_KEY_RESOURCE=projects/PROJECT/locations/europe-west3/keyRings/vaultlog/cryptoKeys/kek,\
REDIS_URL=rediss://:AUTH@MEMORYSTORE_IP:6378/0,\
CORS_ORIGINS=https://vaultlog.example.com" \
  --min-instances 0 --max-instances 10 \
  --concurrency 40 \
  --allow-unauthenticated
```

Notes:

- **`--allow-unauthenticated`** controls *platform* IAM on the URL, not your app auth. Public API + application-layer JWT from Chapter 3 is the intent; every endpoint except `/health` still requires a valid access token.
- **Cloud SQL connection via Unix socket** (`/cloudsql/...`) with `--require-ssl` on the instance; asyncpg needs the `ssl=require` connect arg and the host-as-socket path. Private IP + Serverless VPC connector is the stricter variant — adopt it when the database holds real customers.
- **`rediss://`** (TLS) for Memorystore with in-transit encryption enabled.
- **Set `JWT_PUBLIC_KEY_PEM` too** (it's not secret, but same mechanism keeps config uniform), or derive public from private at startup.

***

## 7. Connection math under autoscaling

This is the calculation juniors skip and seniors do before every deploy. Cloud SQL `db-f1-micro` allows ~25 connections; bigger tiers allow hundreds to thousands. Your budget:

```text
max_connections_needed =
    max_instances × workers_per_instance × pool_size_per_worker
  + migration job headroom (2)
  + admin/psql headroom (2)

Example: 10 × 2 × 5 = 100 + 4 = 104 connections
```

Chapter 2's `build_engine(pool_size=5, max_overflow=5)` means each worker can burst to 10 — so worst case is actually 10 × 2 × 10 = **200**. Either size the database for it, or tighten: `pool_size=2, max_overflow=1` (10 × 2 × 3 = 60) with `--concurrency 40` still comfortably absorbs load for an early-stage product because requests are short. **Rules:** decide the budget explicitly, write it in an ADR, and set `pool_pre_ping=True` (already done) so idle-killed connections self-heal. If you later add PgBouncer/Cloud SQL's built-in pooler, re-run this math — transaction pooling interacts with `SET LOCAL` in ways that require care (your `SET LOCAL` is transaction-scoped, which is precisely the pooler-safe choice; `SET` session-scoped would have been a latent catastrophe under a transaction pooler — another reason Chapter 2's choice matters).

Also set `--max-instances` as a **cost and blast-radius control**, not just scaling: an unthrottled autoscaler behind a public endpoint is a wallet-DDoS waiting to happen.

***

## 8. Production verification drill

After deploy, run the same adversarial discipline as Chapter 8's suite, but live:

```bash
# 1. Health
curl -s https://API_URL/api/v1/health

# 2. Docs are off in production
curl -s -o /dev/null -w "%{http_code}" https://API_URL/docs        # expect 404

# 3. Unauthenticated request rejected
curl -s -o /dev/null -w "%{http_code}" https://API_URL/api/v1/vaults  # expect 401

# 4. TLS + headers
curl -sI https://API_URL/api/v1/health | grep -iE "strict-transport|x-content-type|x-frame"

# 5. Register → login → MFA enroll → create vault → create secret → reveal
#    (full happy path with a throwaway org)

# 6. Verify the KMS path actually engaged: the new tenant's
#    tenant_key_version.wrapping_key_id should be the KMS resource name,
#    NOT 'local-kek-v1'. Check from the owner-role psql session.

# 7. Run the chain verifier against the production database:
python scripts/verify_chain.py <tenant-id>

# 8. Trigger one deliberate login failure burst → confirm 429s arrive
#    and the rate-limit metric registers in Cloud Monitoring.
```

Then delete the throwaway org's data per your retention procedure — don't leave test tenants in the production audit ledger... actually, you *can't* delete their audit rows (RESTRICT FK + no DELETE privilege), which is correct: even your verification drill is now part of the provable record. Use clearly-labeled tenant names like `smoke-test-2026-07-29`.

***

## 9. The production readiness review — the final gate

Before real users, walk this list as a formal review (print it, check items in a meeting, file gaps as issues):

**Identity & access**
- [ ] API runs as dedicated service account; permissions are exactly: Secret Manager accessor on two named secrets, KMS encrypterDecrypter on one key, Cloud SQL client. Nothing project-wide.
- [ ] Owner-role DB credentials exist only in the migration job's secret.
- [ ] JWT private key exists in Secret Manager only; local copies shredded (`shred -u keys/jwt-private.pem` after upload).

**Data protection**
- [ ] Cloud SQL `--require-ssl`; app connects with `ssl=require`; private IP enabled or scheduled.
- [ ] `wrapping_key_id` on new tenants shows the KMS resource; `local-kek-v1` appears nowhere in production data.
- [ ] Automated backups + point-in-time recovery enabled; **restore drill performed once** (a backup never tested is a hope, not a backup).
- [ ] Redis: TLS, AUTH, no public endpoint.

**Application guarantees**
- [ ] `ENVIRONMENT=production` confirmed: docs off, debug off.
- [ ] Security suite green in CI on the exact deployed SHA.
- [ ] RLS verified live: connect as `vaultlog_app`, no tenant set → zero rows from `vault`, `secret`, `audit_event`.
- [ ] Rate limits respond 429 under test burst; Redis shared across instances.

**Detection & response**
- [ ] Chapter 8 alert policies created in Cloud Monitoring: reuse detection, denial spikes, reveal anomalies, 500 rate, chain-verification failure (scheduled verifier running — Cloud Scheduler → Cloud Run Job).
- [ ] Log retention set; audit-sensitive logs access-controlled.
- [ ] Incident runbook v0 exists: key compromise procedure (rotate KMS version → rotate tenant DEKs → sweep), token-theft procedure (family revocation is automatic; review audit), DB-credential rotation procedure.

**Change management**
- [ ] Branch protection + required CI on `main`.
- [ ] Migrations only via the job; expand-contract discipline agreed.
- [ ] ADRs 0001–0008 committed; ADR 0009 for deployment decisions written today.

***

## 10. ADR and completion

`docs/adr/0009-cloud-run-production-topology.md`:

```markdown
# ADR 0009: Cloud Run + Cloud SQL + KMS production topology

- Status: Accepted
- Date: 2026-07-29

## Context
Local dev used env-var keys, plaintext DB, and manual migrations. Production
must make the book's security assumptions environmentally true: non-exportable
KEK, audited secret access, TLS everywhere, role-separated credentials,
migration safety under autoscaling.

## Decision
- Multi-stage non-root image; no secrets or dev tooling in layers.
- Cloud Run API with dedicated least-privilege service account; Secret
  Manager for DB password and JWT private key (injected as env, never files).
- Cloud KMS KEK via GcpKmsProvider implementing the Chapter 6 interface;
  KMS IAM grants use-only (no export, no admin).
- Cloud SQL Postgres 16 with --require-ssl; owner/app role credential split
  enforced by issuing different secrets to different service accounts.
- Migrations as Cloud Run Jobs, expand-contract ordering, never at startup.
- Memorystore Redis (TLS/AUTH) for the Chapter 8 rate limiter.
- Connection budget ADR'd: max_instances × workers × (pool+overflow) + headroom
  ≤ database max_connections, reviewed on any scaling change.
- --max-instances doubles as cost/blast-radius control.

## Consequences
- Cold starts with min-instances=0 add latency on first request; acceptable
  now, revisit with min-instances=1 if UX demands.
- KMS adds per-operation latency and cost on secret reveal/rotation paths;
  acceptable for the security property; cache unwrapped DEKs per-request only
  (never cross-request) if profiling demands.
- Restore drills and the readiness review recur quarterly, not once.
```

## Chapter completion checklist

- [ ] Image builds, runs non-root, health-checks locally under `docker run`.
- [ ] All GCP resources provisioned; IAM bindings are least-privilege, audited.
- [ ] `GcpKmsProvider` live; production `wrapping_key_id` verified.
- [ ] Migration job executed separately; API never migrates.
- [ ] TLS to Postgres and Redis verified from the deployed service.
- [ ] Connection budget calculated, documented, fits the instance tier.
- [ ] Live verification drill passed, including chain verification against production.
- [ ] Readiness review completed with all items checked or ticketed.

## Book outcome

Nine chapters ago this was an empty directory. It is now a deployed multi-tenant secrets manager in which: a forgotten `WHERE` clause cannot leak a row (RLS), a stolen password cannot open a session (MFA), a hijacked session cannot destroy data (step-up), a database dump cannot reveal a secret (envelope encryption), a stolen refresh token revokes itself (rotation + reuse detection), an insider cannot quietly edit history (hash-chained ledger with no UPDATE privilege), and the system pages a human if any of those guarantees break (alerting + scheduled verification).

You built it layer by layer, and every layer fails closed. That is what security-first engineering actually looks like: not a checklist of features, but a system whose components *vouch for each other*.

**Where to go next** (choose your own Chapter 10): passkeys/WebAuthn as a phishing-resistant MFA upgrade riding the existing challenge-token architecture; external audit anchoring to WORM storage (the level-4 guarantee from Chapter 7); ABAC extensions to the policy service; or the React frontend consuming this API with the in-memory access token + cookie refresh pattern from Chapter 3. Whichever you pick, you now have the habits that matter: threat-model first, negative tests always, pipelines that enforce, and ADRs that remember why.

# VaultLog Backend
## Bonus Chapter — The Theory Behind Every Decision: Security Explained Like Stories

**Goal:** This chapter contains no code. It contains *understanding*. Every security mechanism in this book is explained here as a story — the way you'd explain it to a smart 15-year-old, and the way you should be able to explain it in an interview when someone asks *"but why?"* Read this chapter and you'll be able to defend every decision in VaultLog to a skeptic, an interviewer, or a colleague who thinks security is "just add HTTPS."

***

## Part 1 — The One Idea Behind Everything: Layers and Locks

### The castle story

Imagine a medieval castle. It doesn't have one wall. It has:

- A moat (most attackers can't even approach)
- An outer wall (most who cross the moat stop here)
- An inner wall (the few who climb the outer wall face another)
- Guards at the inner gate (who check *who* you are, not just whether you climbed)
- A locked treasury room (even guests of the castle can't enter)
- A scribe inside the treasury writing down everything everyone touches

Now the key question: **why so many layers?** Because every wall can fail. A guard can be bribed. A gate can be left open. If the castle has one wall and it fails, everything is lost. If it has six, an attacker must defeat *all six at the same time* — while you only need *one* to hold.

This is called **defense in depth**, and it's the single organizing idea of this entire book:

| Castle layer | VaultLog layer | Chapter |
|---|---|---|
| Moat | TLS/HTTPS, security headers, rate limiting | 8, 9 |
| Outer wall | Authentication (password + MFA) | 3, 4 |
| Inner wall | Tenant isolation via Row-Level Security | 2 |
| Gate guards | Authorization (roles + grants + policy service) | 5 |
| Locked treasury | Encryption at rest (KEK/DEK hierarchy) | 6 |
| The scribe | The hash-chained audit ledger | 7 |
| Alarm system | Alerting, anomaly detection | 8 |

Every interview answer in security should eventually come back to this: *"This layer exists because the other layers can fail."*

### Failing closed

One more idea that appears everywhere: **fail closed** versus **fail open**.

A door that "fails open" unlocks when its electronics die. A door that "fails closed" stays locked. For a hotel, fail-open doors are good (fire safety — people must escape). For a vault, fail-closed is the only option.

In VaultLog, every component fails closed:

- If the tenant ID can't be determined, the database session shows **zero rows** — not all rows.
- If a JWT is malformed, expired, or even slightly weird, it's rejected — not "best-effort accepted."
- If Redis dies, the login endpoint refuses logins (fail closed), because an unthrottled login page is worse than a temporarily unavailable one.
- If decryption fails for *any reason*, the user gets "decryption failed" — never a best guess at the plaintext.

When in doubt, deny. You can always relax a denial later with evidence. You can never un-leak data.

***

## Part 2 — Passwords: Why We Never Store Them

### The hotel key drawer story

Imagine a hotel that keeps every guest's room key in a drawer at the front desk, labeled with room numbers. One night, someone steals the drawer. Every room in the hotel is now open. The thief doesn't even have to break anything — the hotel *handed them* the keys.

That's what storing passwords in plaintext is: a labeled drawer of keys. Databases get stolen all the time — through SQL injection, stolen backups, rogue employees, misconfigured cloud buckets. If passwords are in there, every user's account is gone in one night. And because people reuse passwords, their email and bank accounts are gone too.

### The solution: don't store the password, store a *question only the password can answer*

Here's the trick. Instead of storing `hunter2`, you store something like this:

1. Take the password.
2. Mix it with a random value called a **salt** (unique per user).
3. Push the mixture through a mathematical meat grinder called a **hash function** — something easy to do forward, impossible to reverse.
4. Store the result.

When the user logs in, you grind their submitted password with the same salt and check if the result matches. The meat grinder analogy is literal: you can turn a cow into a burger, but no one can turn a burger back into a cow.

In VaultLog we use **Argon2id**. Why not just SHA-256? Because SHA-256 is *fast* — a stolen database lets an attacker test billions of password guesses per second on a gaming GPU. Argon2id is deliberately **slow and memory-hungry**: each guess costs real time and real RAM, so the attacker's billions-per-second become thousands-per-second. "123456" still falls instantly; a decent passphrase becomes practically unguessable.

**Interview answer:** "We hash passwords with Argon2id, with per-user salts and per-user pepper. Hashing makes the stored value irreversible; salting makes each user's hash unique so attackers can't use precomputed rainbow tables and can't see which users share passwords; the pepper — a server-side secret outside the database — means a database dump alone can't even *start* guessing; and Argon2id's memory-hardness specifically defeats GPU cracking rigs."

### Why we return the same error for everything

When login fails, VaultLog always says "Invalid credentials" — never "this email doesn't exist" and never "wrong password." Why?

Imagine a burglar calling apartment buildings: *"Does John live in 4B?"* If the building answers "no one by that name here," the burglar learns which buildings *do* have a John. That's an **enumeration attack** — and "this email isn't registered" is exactly that answer. Attackers use it to build lists of valid accounts before ever guessing a single password. Same message, same response time (as much as feasible), every time. The building says "we can't confirm that" to everyone.

***

## Part 3 — Tokens: The Wristband and the Coat-Check Ticket

### The festival story

You arrive at a three-day music festival. At the entrance, you show your ID and ticket (that's **authentication** — proving who you are). They give you two things:

1. **A wristband** — you flash it at every stage and food stall. Nobody re-checks your ID; the wristband itself is proof. But it fades and stops working at the end of each day.
2. **A coat-check ticket** — when your wristband fades, you don't go back to showing your passport. You present the coat-check ticket at the entrance booth, and they give you a fresh wristband. Crucially: they *take the old ticket* and hand you a *new one* each time.

The wristband is the **access token** (short-lived, shown everywhere, self-contained). The coat-check ticket is the **refresh token** (long-lived, used only at one booth, exchanged for new wristbands).

### Why two tokens instead of one?

Ask the opposite question: why not one wristband that lasts all three days? Because wristbands get stolen. Someone bumps into you, slips it off, and now they eat and drink as you for three days.

With VaultLog's design:

- The **access token** lives 10 minutes. If stolen, the thief has 10 minutes of access, then a useless scrap. Short life = small blast radius.
- The **refresh token** lives 30 days, but it's only ever sent to *one endpoint* (`/auth/refresh`), over HTTPS, in a `Secure`, `HttpOnly`, `SameSite` cookie that JavaScript can't read and browsers won't send cross-site. It's the crown jewel, so it travels in an armored car on a private road, not flashed at every food stall.

### JWT: the wristband that verifies itself

How does a food stall know your wristband is real without calling the entrance booth every time? In VaultLog, the wristband is a **JWT** — a small signed document. It contains claims (who you are, which tenant you belong to, when it expires) and a **digital signature** made with the server's private key.

Think of the signature as a wax seal made with a unique signet ring. Anyone can *look* at the seal (the public key is, well, public) and verify it matches the ring's imprint. But only the server, holding the ring (the private key), can *make* the seal. Change one letter of the document and the seal no longer matches — the stall rejects it instantly, no phone call needed. That's why JWT verification is fast and stateless.

VaultLog uses **RS256** (asymmetric — private key signs, public key verifies) rather than HS256 (symmetric — one shared secret does both). Why? With a shared secret, *every service that can verify tokens can also forge them*. With RS256, only the auth service holds the signing key; everyone else can only verify. In an interview: "asymmetric signing separates the power to mint tokens from the power to check them."

**The algorithm-confusion trap:** a famous JWT attack works like this — the attacker takes a token and changes its header from `RS256` to `HS256`, then signs it using the *public key* as if it were the shared secret. Sloppy libraries, told to accept "any algorithm," verify it successfully — because with HS256, the public key works as an HMAC secret! The attacker has forged a token using only public information. VaultLog's defense is one line that matters enormously: the verifier accepts **only RS256**, hardcoded, and demands `issuer`, `audience`, and `expiry` claims explicitly. Never let the token itself decide how it should be verified — that's letting the wristband tell the guard which checks to skip.

### Rotation and reuse detection: the stolen coat-check ticket

Here's the clever part of Chapter 3, worth understanding deeply. Every time a refresh token is used, it's *rotated*: the old one dies, a new one is issued. Now imagine the ticket gets stolen, and both the thief and the real user try to use tickets from the same family:

- The thief presents ticket #7. It's valid! The booth honors it, destroys it, issues ticket #8 *to the thief*.
- Later, the real user presents ticket #7 — the last one they have. The booth says: "Ticket #7 was already exchanged. **Someone else used this ticket.** That means a theft occurred."
- The booth's response: *shred the entire family of tickets* — #8 included — and force a fresh login.

This is **reuse detection**. A stolen refresh token becomes a burglar alarm: the moment thief and victim both act, the whole session family is revoked and the theft is logged. The alternative — a refresh token that works forever until expiry — is a ticket that, once photocopied, works for both people silently for 30 days.

***

## Part 4 — MFA and Step-Up: Something You Know, Something You Have

### The two-locks story

A bank vault door has two keyholes, and the two keys are held by two different managers. Why? Because one stolen key — one bribed manager — is no longer enough.

Authentication factors work the same way. There are three kinds of proof:

1. **Something you know** (a password) — can be phished, guessed, keylogged, reused.
2. **Something you have** (a phone with an authenticator app, a hardware key) — must be physically stolen.
3. **Something you are** (fingerprint, face) — convenient, but can't be changed if copied.

Requiring two *different kinds* means the attack that defeats one (a phishing email stealing your password) does nothing to the other (your phone is in your pocket, not in the email).

### TOTP: the synchronized secret clocks

How does the phone prove itself without the password? VaultLog uses **TOTP** — Time-based One-Time Passwords. Here's the whole trick, and it's beautiful:

- At enrollment, the server generates a random secret (the **seed**) and shares it with your authenticator app (via QR code). Now *both* sides know the seed.
- From then on, both sides independently compute: `code = HMAC(seed, current_time_slice)`. Every 30 seconds, the time slice changes, so the code changes.
- At login, you type the 6-digit code your phone shows. The server computes the same formula. If they match, you must possess the seed — you must have the phone.

No secrets travel at login time — just a disposable 6-digit proof that *knowledge of* the seed exists. It's like two people who agreed on a secret handshake formula based on the day of the week: if you do today's handshake correctly, you must be in on the formula.

Two implementation details with real theory behind them:

**Why the seed is encrypted in the database (Chapter 4).** The seed is a *shared* secret — unlike a password, it can't be hashed, because the server needs the actual seed to compute expected codes. So the database must store something an attacker could use. Our answer: encrypt it with AES-GCM under a dedicated key (the MFA KEK), so a database dump yields ciphertext, not seeds. This is the same envelope-encryption logic as secrets proper — see Part 6.

**Why enrollment is two-phase.** When you enable MFA, VaultLog first creates an *unconfirmed* seed, and only activates MFA after you submit a valid code from your app. Why not activate immediately? Because if your phone scanned the QR wrong or ate the entry, you'd be locked out of your own account the moment MFA turned on — locked out by your own security feature. Proof first, enforcement second.

### The challenge token: "you've proven half, finish the job"

When a user with MFA enters a correct password, VaultLog does **not** log them in. It issues a tiny 5-minute **challenge token** that can do exactly one thing: submit an MFA code. No session, no refresh token, no access token exists yet.

Why the ceremony? Because a half-authenticated user is a dangerous state. If we issued a normal access token after the password step "with a flag saying MFA pending," every endpoint would have to remember to check that flag — and one forgotten check is a bypass. Instead, the challenge token is a *different kind of thing* with a `purpose` claim, and every verifier checks the purpose. A challenge token presented to a normal endpoint fails not because of a flag, but because it's *structurally the wrong credential* — like trying to board a plane with a parking ticket.

### Step-up authentication: "prove you're still you"

Here's a scenario passwords and MFA-at-login can't solve: you log in at 9 AM with full MFA. At 2 PM, you step away from your unlocked laptop. A colleague (or an attacker with remote access) sits down and clicks "Delete vault: Production."

Your session is valid. Your token is fresh. Everything checks out — and the data is gone. The question "did this person authenticate?" was answered at 9 AM, but the question that matters now is "**is the account owner present *right now*?**"

That's **step-up authentication**: before destructive operations, require a fresh TOTP code, and issue a 5-minute **step-up token** bound to three things: the user, *that specific session*, and *that specific purpose* (`step-up:delete-vault`). The token proving "I just entered a TOTP code to manage MFA" cannot be replayed to delete a vault. The 5-minute window is long enough to complete the action, too short to be useful to a laptop-thief later.

**Interview framing:** "Authentication establishes identity at a point in time. Step-up establishes *presence* — freshness of proof — at the moment of consequence. Sessions age; risk doesn't."

***

## Part 5 — Tenant Isolation: The Apartment Building

### The problem in one sentence

VaultLog is **multi-tenant**: many organizations share one database, one app, one codebase — like an apartment building where every tenant's furniture is in the same warehouse, separated only by labels on the boxes.

Every query must somehow only touch the right tenant's boxes. The naive approach: "just remember to write `WHERE tenant_id = ?` in every query." This is like telling every warehouse worker "just remember to check the labels." Someday, someone forgets. In security, "someday someone forgets" is not a risk — it's a schedule.

### Row-Level Security: the warehouse itself checks

**PostgreSQL Row-Level Security** moves the check from the workers to the warehouse walls. The rule lives *inside the database*:

> "Any session may only see rows where `tenant_id` equals the tenant declared at the start of this session. Any attempt to insert a row for a different tenant is rejected."

Now the forgotten `WHERE` clause doesn't matter. The application can write the sloppiest query imaginable — `SELECT * FROM secret` — and the database returns only the current tenant's rows, because the *database itself* filters every row on the way out and every row on the way in (`USING` for reads, `WITH CHECK` for writes).

Two details worth being able to defend:

**`FORCE ROW LEVEL SECURITY`.** By default, PostgreSQL exempts the table owner from RLS — sensible for admin tooling, but a trap if your app ever connects as the owner. `FORCE` removes the exemption: *no one* bypasses, so the rule is universal. Meanwhile the app connects as a dedicated role (`vaultlog_app`) created with `NOBYPASSRLS` — it physically cannot bypass even if an attacker gains full SQL injection through it. Two small statements, one principle: **the security boundary must not depend on which door the attacker came through.**

**Why the tenant context is `SET LOCAL` inside the transaction.** The tenant ID is set per-transaction, not per-connection. If it were connection-scoped, a connection returned to the pool could carry the *previous request's* tenant into the next request — tenant A's context bleeding into tenant B's request through a recycled connection. `SET LOCAL` evaporates at commit/rollback; every transaction starts clean and must declare its tenant. And in Chapter 9 this choice pays off again: connection poolers that multiplex transactions across connections are only safe with transaction-scoped settings.

### Why the DB layer instead of the app layer?

Defense in depth again — but also *blast radius of bugs*. Application-layer filtering is defeated by application-layer bugs: a new endpoint, a raw query, an ORM feature someone misused. Database-layer filtering is defeated only by breaking the database itself. We kept app-layer tenant pinning *too* (every query also says `tenant_id = ?` explicitly) — not because either layer is insufficient, but because the layers protect *each other* from regressions. Belt and suspenders, where either one alone genuinely holds.

### The 404-not-403 rule

One subtle piece: when a user from tenant A asks for tenant B's vault UUID, VaultLog answers **404 Not Found**, not 403 Forbidden. Why?

A 403 says: "this thing exists, and it's not yours." That's information — the attacker just learned the UUID is real, and real UUIDs get collected for later attacks. A 404 says nothing: maybe it exists elsewhere, maybe it never existed at all. This is called preventing **IDOR** (Insecure Direct Object Reference) information leaks. Existence itself is a secret.

***

## Part 6 — Encryption at Rest: Envelopes Inside Envelopes

This is the topic that intimidates people most and is, at heart, a set of simple stories.

### What "encryption at rest" does and does not defend

First, the misconception to kill: encryption at rest does **not** protect data from someone attacking the running application. If the app is compromised, the attacker can simply *ask the app* to decrypt things — the same way a bank robber inside the bank doesn't need to crack the safe if the teller will open it. Live-access protection is what auth, authorization, RLS, and audit are for.

Encryption at rest protects the **stored data when the storage itself leaks**: database dumps, stolen backups, cloud snapshots, decommissioned disks, curious employees with psql access. A huge fraction of real breaches are exactly these — nobody "broke crypto," they just downloaded a backup that was left in a public bucket.

### Symmetric encryption: one key, both directions

VaultLog's actual cipher is **symmetric**: the same key encrypts and decrypts. Think of a lockbox with one key. The whole security rests on keeping that key secret — which is why almost all the engineering in Chapter 6 is about *keys*, not ciphers.

### AES-GCM: the sealed envelope

We use **AES-256-GCM**. AES is the scrambling algorithm (256-bit key — guessing it would take longer than the age of the universe on any conceivable hardware). GCM is the *mode* — how AES is applied — and it's chosen because it's an **AEAD** mode, giving three things at once:

1. **Confidentiality** — ciphertext looks like noise; nothing about the plaintext leaks (except its length).
2. **Tamper-evidence** — decryption produces a built-in "seal check." Flip even one bit of the ciphertext, and decryption *fails loudly* instead of returning corrupted data. Why this matters: without it, an attacker who can write to your database can flip bits to change meaning — the classic example is changing an encrypted `role=user` to `role=admin` — and the system happily decrypts the forged message. With GCM, forgery is detected, not silently accepted. Confidentiality without integrity is a letter in a transparent envelope.
3. **AAD (Associated Authenticated Data)** — and this one deserves its own story.

### AAD: the envelope with an address printed through the seal

Imagine a wax-sealed envelope where the address is written *across the seal itself*. You can still read the address — it's not secret — but you cannot move the seal to a different envelope, and you cannot change the address without breaking the seal.

That's AAD. In VaultLog, every secret's ciphertext is bound to its **context**: `tenant : vault : secret : version`. The AAD isn't encrypted or stored — it's *recomputed from where the row lives* at decryption time. The consequence is a defense against **ciphertext transplantation**: an attacker with database write access copies the ciphertext from the "root password" secret into their own low-value secret's row, then reveals their own secret to read the root password. With AAD, decryption of the transplanted row recomputes the AAD from *their* secret's identity — which doesn't match the AAD used at encryption — and the seal breaks. The ciphertext only makes sense in its original home.

The prefix (`vaultlog:secret:v1:...`) is **domain separation**: it guarantees AAD from one feature can never collide with another feature's (TOTP seeds use a different prefix), so ciphertexts aren't interchangeable across features even under the same key. Small string, big idea: context is part of the message.

### The nonce rule: never wear the same disguise twice

GCM needs a **nonce** — a random number used once per encryption. The rule is absolute: **never reuse a nonce with the same key.** Reuse catastrophically breaks both secrecy (an attacker can XOR the two ciphertexts to cancel out the keystream and recover plaintext relationships) and integrity (forgery becomes possible).

VaultLog's answer: a fresh `os.urandom(12)` — 96 random bits — per encryption. Random nonces can theoretically collide (birthday paradox), but with 96 bits you need billions of messages under one key before collision probability matters, and we stay far below that, with key rotation shrinking exposure further. The nonce isn't secret; it's stored next to the ciphertext. Its only job is uniqueness.

### The key hierarchy: why envelopes need envelopes

Now the central design. Naive approach: one master key encrypts every secret. Two fatal problems:

- If the master key ever leaks, *everything* ever encrypted is exposed.
- To rotate (replace) the key, you must decrypt and re-encrypt *every secret* — hours of downtime, giant failure window.

**Envelope encryption** adds a level of indirection, like Russian dolls:

```text
KEK (key-encryption key) — the "master key," stored in a vault (KMS)
   └── wraps → DEK (data-encryption key) — a random key per tenant
        └── encrypts → the actual secrets
```

- Each tenant gets a random **DEK** that actually encrypts their secrets.
- The DEK itself is encrypted ("wrapped") by the **KEK**, and only the *wrapped* DEK is stored in the database.
- The KEK lives in a **KMS** (Key Management Service) where, in production, it *cannot be exported at all* — the KMS performs wrap/unwrap operations internally, in hardware. The application never holds the raw KEK; it sends requests: "please unwrap this."

Now trace what a database thief gets: encrypted secrets (useless without DEKs) and wrapped DEKs (useless without the KEK, which was never in the database). The dump is a pile of envelopes inside locked envelopes, and the one key that opens the outer envelope never left the vault.

Four wins, each worth stating in an interview:

1. **Database compromise ≠ data compromise.** The KEK lives elsewhere.
2. **KEK rotation is cheap.** To change the master key, re-wrap a handful of 32-byte DEKs — not terabytes of secrets. The heavy data is untouched.
3. **Tenant blast radius.** Each tenant has its own DEK; one tenant's DEK compromise decrypts only that tenant's data — mirroring the RLS isolation philosophy at the cryptographic layer.
4. **DEK rotation without downtime.** This one needs its own paragraph.

### Key versioning: change the present by adding, never by rewriting

Keys in VaultLog are **versioned and immutable**. Rotating a tenant's DEK doesn't rewrite anything: a *new* DEK version is added and marked active; the old version is *retired* — no new encryptions, but kept for decryption, because old ciphertexts still reference it (every secret-version row records which `dek_version` encrypted it).

Rotation becomes instant (install new key), and re-encrypting old data becomes a *background sweep* — small batches, each its own transaction, resumable after crashes, each ciphertext re-encrypted under the new DEK with identical AAD (same secret, same context — only the key changes). Only when verification proves *nothing* references the old key version may it be destroyed. **Never destroy a key while ciphertexts reference it** — that's not data loss by accident, that's data loss by procedure.

The same immutability principle recurs everywhere in VaultLog — secret versions, audit rows, key versions: *history is append-only; you change the present by adding, not by rewriting.* Mutable history invites both accidents and forgeries.

### Why the KEKProvider interface

Chapter 6 wraps all KEK access behind a tiny interface (`wrap`, `unwrap`), with a local AES-GCM implementation for development and a Cloud KMS implementation for production. This isn't abstraction for its own sake — it's the recognition that **the riskiest infrastructure swap in the project** (where does the master key live?) should touch exactly one factory function, with behavior — AAD binding, error discipline — identical across both. When Chapter 9 swapped in the real KMS, zero use-case code changed.

***

## Part 7 — Authorization: Roles, Grants, and One Brain

### Who are you vs. what may you do

Authentication (Parts 3–4) answers *who are you*. **Authorization** answers *what may you do*. VaultLog's model is two-axis RBAC:

- **Organization role** (owner / admin / member / viewer): your standing in the org — the badge on your chest.
- **Vault grant** (read / write / admin, per vault): which specific rooms your badge opens.

Think of an office building: your employee badge (role) gets you into the building and the cafeteria. But the finance floor (vault) requires the finance sticker (grant) on your badge. A badge without the sticker doesn't open that door, no matter how senior you are — seniority decides who *hands out stickers*, not who walks through every door.

### The permission matrix is the specification

Chapter 5 encoded the rules as an explicit table (owner can do everything in their org; members act through grants; viewers are read-only *even if a grant row says otherwise*) and then **generated the tests from the table**. That last point is the senior habit: the matrix is the specification, the tests are the specification made executable, and changing behavior means changing the spec first. Authorization logic that lives scattered across routers rots silently; a single tested policy service fails loudly.

Three rules from the matrix worth defending anywhere:

- **"Policy beats data":** a viewer with a forged/mistaken `write` grant row still can't write. Grant rows are data, and data can be corrupted, mis-written, or planted; the role cap is policy, enforced in code. When the two disagree, the stricter wins.
- **Destruction costs more than modification:** deleting a secret needs a higher grant (`admin`) than writing one. Losing data is worse than changing it.
- **Owner/admin bypass grants deliberately:** synthesizing their vault-admin permission in code instead of requiring grant rows means that when someone's role is removed, no stale grant rows linger. **Orphaned permissions** — access rights left behind after their justification disappears — are how privilege quietly accumulates in real systems ("privilege accretion"). Every access should have a living reason to exist.

### One brain, not a hundred if-statements

Every authorization decision flows through `PolicyService`. The failure mode this prevents: inline `if role == "admin"` checks scattered across 30 endpoints, each slightly different, each aging independently, until one day the endpoint that deletes vaults has the *old* rules. Centralization isn't about elegance — it's about there being **one place to audit, one place to test, one place to fix**.

And step-up proof is re-checked *inside* the destructive use cases, not just at the router: if a future developer adds a new path to the same use case and forgets the decorator, the check still fires. Defense in depth applied to code structure.

***

## Part 8 — The Audit Ledger: The Camera That Can't Be Edited

### Why logging isn't enough

Every system has logs. Logs are text files a developer can edit, a compromised server can erase, and an insider can truncate. For a secrets manager, the question "who revealed the production database password last Tuesday?" must have an answer that **survives the person it might incriminate**.

### Append-only: the pen with no eraser

Level one: the database role the application runs as is granted `INSERT` and `SELECT` on the audit table — and *not* `UPDATE` or `DELETE`. The application **physically cannot** modify history, even if an attacker achieves arbitrary SQL execution as that role. Privilege-level immutability beats code-level immutability because code has bugs and privileges don't.

### Hash chaining: the photo album where every photo contains the previous page

Level two is the elegant part — **tamper evidence**. Each audit entry's hash is computed over its own content *plus the previous entry's hash*:

```text
hash(entry 3) = SHA-256( hash(entry 2)  +  content of entry 3 )
```

Think of a photo album where each photograph's border contains a tiny picture of the previous page. Now try to secretly replace page 5: the replacement's border won't match page 6's tiny picture of page 5. To hide your edit you must re-shoot page 6 — but then page 6's image-in-page-7's-border is wrong, so you must redo page 7... **changing any page forces you to redo every page after it.** A verifier just walks the album checking that each page's border matches the actual previous page. One mismatch, and it names the exact page where history stops agreeing with itself.

Honesty matters here — know the limit: an attacker with *full database control* can rewrite all pages and re-shoot every border, producing a flawless fake album. Hash chaining guarantees **detection against any earlier snapshot**, not impossibility. That's why the design includes level three (not fully built in the book): **external anchoring** — periodically publishing the latest hash to a system the attacker doesn't control (WORM storage, an independent logging service). The attacker can rewrite the album, but can never rewrite yesterday's published snapshot of its last page — and the mismatch exposes the forgery. This is the same idea behind certificate transparency logs and, yes, blockchains — minus the hype: no mining, no tokens, just chained hashes and an independent witness.

### The atomicity rule: the action and its receipt, together or not at all

VaultLog writes each audit event in the **same database transaction** as the action it records. Commit together or roll back together. Why does this matter so much? Because the two failure modes are both corruption:

- Action commits, audit write fails → something happened with no evidence. An invisible reveal.
- Audit commits, action rolls back → evidence of something that never happened. A false accusation.

"Either both or neither" is the only acceptable outcome, and transactions are precisely the tool that guarantees it. (Denials are the exception that proves the rule: a denied action leaves no state change, so its audit row commits alone — the denial *is* the entire event.)

### What must never be in the ledger

The audit trail is the *least* secret store in the system — exported, retained, read by investigators. So it must never contain plaintext secrets, tokens, or codes. VaultLog enforces this with a forbidden-key guard that *refuses* suspicious metadata — because "please be careful" conventions fail, and a developer logging `{"value": secret}` for debugging is a when, not an if. Make the dangerous thing impossible at the boundary, not merely discouraged in a style guide.

***

## Part 9 — The Web Edge: CSRF, Headers, Rate Limits, and Errors

### CSRF: the forged request with your signature on it

**Cross-Site Request Forgery** works like this: you're logged into VaultLog, so your browser holds your refresh cookie. You visit an evil page in another tab. That page silently submits a form to `vaultlog.example.com/api/v1/auth/refresh` — and your browser, helpful creature that it is, *attaches your cookie automatically*. The request arrives with your identity. The evil page forged your signature by tricking your own pen.

The layered defenses:

- **`SameSite=Lax` cookie:** the browser refuses to attach the cookie to cross-site POSTs at all. The pen refuses to sign foreign documents. (Modern browsers; first layer.)
- **Origin check:** the server verifies the `Origin` header matches the real frontend. Browsers send `Origin` on cross-origin requests and — critically — *the evil page cannot forge or suppress it*; that header is controlled by the browser, not page JavaScript. It's like the postmark on the envelope: the thief can write any letter, but can't fake which post office it came through.
- Why not a classic **CSRF token** (the cookie/header double-submit the question mentioned)? Because VaultLog's API is consumed via `Authorization: Bearer` headers for access tokens — attackers can't set custom headers cross-site, so those endpoints are immune by construction. Only the two cookie-authenticated endpoints (refresh, logout) needed protection, and Origin checking covers them with less machinery. *Match the defense to the actual exposure.*

### Security headers: instructions to the browser

Headers are the server telling browsers how to handle its content, and each one VaultLog sets disables an entire attack class:

- **`X-Content-Type-Options: nosniff`** — "don't guess what this file is." Stops browsers from deciding a JSON error page is actually HTML and executing it.
- **`X-Frame-Options: DENY` / CSP `frame-ancestors 'none'`** — "never display me inside an iframe." Defeats **clickjacking**: an evil page overlaying your real page invisibly, so the user's click on "Play video" actually clicks "Delete vault."
- **`Referrer-Policy: no-referrer`** — URLs contain IDs (`/vaults/{uuid}`); don't leak them to third parties via referrer headers.
- **CSP `default-src 'none'`** — for a pure JSON API: "load nothing, ever." The strictest possible answer, correct by default.
- **HSTS** — "for the next year, refuse to even speak plain HTTP to this domain." Defeats downgrade attacks where an attacker intercepts the first insecure request. Sticky and powerful, so enable only when HTTPS is universal.

### Rate limiting: the bouncer who counts

Every security control that involves guessing — passwords, 6-digit TOTP codes, recovery codes, token values — is only as strong as **how many guesses per second the attacker gets**. A 6-digit TOTP has a million possibilities; with unlimited attempts that's seconds of compute. Rate limiting is what makes "a million possibilities" mean "a million *months*."

The deeper point: **rate limiting is part of the cryptographic argument.** When we chose TOTP, we implicitly promised "attackers get single-digit attempts per window." The sliding-window limiter in Redis is what keeps that promise — and it's shared across all app instances, because a per-server limit times N servers is N times the intended limit. Also note the failure postures from Chapter 8: credential endpoints *fail closed* when the limiter is down (an unthrottled login page is worse than an unavailable one); data endpoints *fail open* (availability matters, and RLS + crypto still protect the data underneath).

### Error handling: the poker face

Error messages are an information channel, and attackers read it carefully. The rules:

- **500s return a generic message plus a request ID.** Internally, logs capture everything (stack trace, request ID); externally, the user gets a reference number support can correlate. Stack traces reveal file paths, library versions, and code structure — free reconnaissance.
- **422 validation errors omit the submitted values.** Pydantic's default errors echo the offending input back. If that input was a secret value that failed validation, the default behavior *reflects the secret* into responses, logs, and error trackers. Sanitized errors show *which field* failed, never *what was submitted*.
- **Auth failures are uniform** ("Invalid credentials"), as covered in Part 2 — enumeration via differing messages, differing timing, differing status codes is a whole attack family, and uniformity is the counter to all of it.

***

## Part 10 — Sessions, Least Privilege, and Secrets Hygiene

### Why the refresh cookie is `HttpOnly`, `Secure`, `SameSite`

Each flag disables a theft channel:

- **`HttpOnly`** — JavaScript cannot read the cookie. If an attacker ever achieves XSS (injecting script into a page), they can steal what's in memory but *not* the refresh token. The most valuable credential is placed where the most common web attack can't reach.
- **`Secure`** — the cookie only travels over HTTPS. It cannot leak over a plaintext connection.
- **`SameSite=Lax`** — the CSRF defense from Part 9.

Meanwhile the **access token lives in memory**, not `localStorage` — because `localStorage` is readable by *any* JavaScript on the page (including injected scripts) and persists across sessions. Memory is wiped when the tab closes; the XSS blast radius shrinks from "everything, forever" to "whatever the token can do in its remaining minutes."

### Least privilege: everyone gets exactly the keys they need

Throughout VaultLog, every identity holds the minimum access required:

- The **app database role** can read/write data tables, cannot change schema, cannot bypass RLS, cannot UPDATE or DELETE audit rows, cannot UPDATE secret versions.
- The **owner role** exists only for migrations and is held only by the migration job — a *different service account with a different secret* than the API.
- The **Cloud Run service account** can read exactly two secrets and use exactly one KMS key (encrypt/decrypt — not export, not administer).
- The **JWT private key** lives in Secret Manager; services that only verify tokens get only the public key.

The pattern: assume each component *will* be compromised someday, and arrange in advance for that compromise to be boring. "If this box is owned, what does the attacker get?" should always have a disappointingly small answer.

### Secrets in the environment

A few hygiene rules that show up across the book:

- **`.env` is git-ignored; `.env.example` documents shape without values.** Committed secrets are one of the top real-world breach vectors — and git history never forgets, so one commit is forever (rotating after the fact is the only fix).
- **In production, secrets come from a manager, injected at runtime**, with access audited. Files on disk can be read by any process; a secret manager answers only authenticated identities and logs every read.
- **Nothing secret is ever logged.** VaultLog enforces this in the *pipeline* — a redaction processor scrubs dangerous keys from every log event — because "be careful" is a convention, and conventions fail on tired Fridays. Pipelines that make the dangerous thing impossible beat conventions that make it discouraged.

***

## Part 11 — How to Talk About All of This

### In an interview

The pattern that signals senior thinking is always the same three beats: **threat → mechanism → limit**. For any control:

> "We use X to defend against Y. It works by Z. Its limit is W, so we pair it with V."

Examples, using the stories above:

- *"We store passwords with Argon2id, salted and peppered, to defend against database-dump cracking. Hashing is irreversible, salts kill rainbow tables, the memory-hardness kills GPU rigs. Its limit is that it does nothing against phishing — that's why MFA exists as a separate layer."*
- *"Refresh tokens are rotated and reuse-detected, so a stolen token burns the entire session family the moment thief and victim collide. Its limit is the 10-minute access-token window — acceptable because the token is short-lived and memory-only on the client."*
- *"Secrets are envelope-encrypted: per-tenant DEKs wrapped by a KMS KEK. A database dump yields ciphertext and wrapped keys, neither usable. Its limit is that a compromised app can request decryptions — which is why authorization, step-up, and audit exist; encryption at rest was never meant to answer live-access threats."*
- *"The audit ledger is append-only at the privilege level and hash-chained for tamper evidence. Its honest limit: an attacker with full DB control can recompute the chain — so the design includes external anchoring as the next layer."*

Notice: stating the *limit* unprompted is what separates someone who read a checklist from someone who designed a system.

### Explaining to a non-engineer

Lead with the physical metaphor and the *why*, skip the names:

- Not "AES-256-GCM with AAD" → "every secret is in a sealed envelope, and the address is written through the seal, so nobody can move the contents into a different envelope."
- Not "hash chaining" → "a photo album where every photo shows the previous page — change any page and the album stops matching itself."
- Not "RLS" → "the warehouse itself checks the label on every box, so even a careless worker physically cannot hand you the wrong tenant's box."
- Not "step-up authentication" → "being logged in proves who walked in this morning; a fresh code proves it's still you at the keyboard right now, before anything irreversible happens."

If they understand the castle, the wristband, the coat-check ticket, the envelope, and the photo album — they understand the system.

***

## Part 12 — The Master Table: Every Decision and Its Threat

| Mechanism | Story | Threat it answers | Its honest limit |
|---|---|---|---|
| Argon2id + salt + pepper | The meat grinder with a secret ingredient | Stolen password database | Phishing, keyloggers → hence MFA |
| Short-lived JWT (RS256) | The self-verifying wristband | Token theft blast radius | 10-minute window; needs refresh UX |
| Refresh rotation + reuse detection | The coat-check ticket that burns itself | Long-term token theft | Detection lags first misuse |
| HttpOnly/Secure/SameSite cookie | The armored car on a private road | XSS theft, sniffing, CSRF | Cookie endpoints need Origin checks |
| TOTP MFA | Two synchronized secret clocks | Password-only compromise | Phishable in real-time → passkeys next |
| Challenge token | The parking ticket that can't board a plane | Half-authenticated state abuse | 5-minute window |
| Step-up tokens | "Prove you're still at the keyboard" | Session hijack for destructive ops | UX friction; must be scoped narrowly |
| Row-Level Security | The warehouse checks every label | Cross-tenant leaks, forgotten WHERE | Bypassed only by owner/superuser → FORCE + NOBYPASSRLS |
| Two-axis RBAC + policy service | Badge plus room stickers, one brain | Over-privilege, drift, orphaned grants | Complexity of the matrix → keep it executable |
| 404-not-403 | "Maybe it never existed" | IDOR existence leaks | Slightly harder debugging |
| AES-256-GCM | The sealed tamper-evident envelope | Dumps, tampering | Nonce reuse → random per call |
| AAD binding | Address written through the seal | Ciphertext transplantation | Must derive, never store |
| KEK/DEK envelope encryption | Envelopes inside a locked envelope | DB dump + insider access | App compromise is out of scope |
| Key versioning + sweep | Change the present by adding | Rotation downtime, stale keys | Old keys retained until sweep verifies |
| Append-only audit + hash chain | Pen with no eraser + self-matching album | Insider evidence-tampering | Full DB control can recompute → anchor externally |
| Same-transaction audit | Action and receipt, together or never | Actionless evidence, evidenceless actions | Denials need their own transaction |
| Rate limiting (sliding window) | The bouncer who counts | Brute force, stuffing, scraping | Redis availability → fail postures per endpoint |
| Sanitized errors + request IDs | The poker face with a case number | Info leakage via errors | Internal logs must stay protected |
| Security headers + HSTS | Instructions the browser must obey | Sniffing, clickjacking, downgrade | HSTS is sticky — enable carefully |
| Least-privilege roles | Everyone gets exactly their keys | Component compromise blast radius | More accounts/secrets to manage |
| Log redaction pipeline | The censor at the printing press | Secrets in logs | New key names must be added to the list |
| CI security gates | The bouncer at the merge button | Regression of every guarantee above | Only as strong as the suite → keep it current |

***

## Closing: The Habit Behind the Knowledge

If you take one thing from this book, take the *order of questions*:

1. **What am I defending, and from whom?** (threat model before mechanisms)
2. **What happens when this layer fails?** (defense in depth; every answer must exist)
3. **How would I prove it's broken?** (negative tests, tamper tests, verification)
4. **Who can defeat this control, and what do they get?** (least privilege, blast radius)
5. **Will the next person understand why this exists?** (ADRs, honest limits documented)

The mechanisms in this chapter — hashing, tokens, AEAD, key hierarchies, hash chains — are all learnable in an afternoon each. The habit of asking these five questions about *everything you build* is what makes someone a security engineer rather than someone who once read a security book. You now have both.

# Bonus Chapter — Security Theory, Explained Like You're Fifteen

**Goal:** This chapter contains zero code. It contains everything you need to *explain* the code. By the end, you can defend every decision in VaultLog to a security engineer in an interview, and explain it to your cousin over dinner. Both audiences matter — the first one hires you, the second one reminds you whether you actually understand it.

**How to use this chapter:** Each section has three parts: **The Story** (an analogy), **What's Really Happening** (the technical truth), and **The Interview Answer** (how to say it to a professional). Read actively. Try explaining each section out loud afterward — if you stumble, reread.

***

## 1. The one idea everything else hangs on: defense in depth

**The Story.** A medieval castle doesn't have one defense. It has a moat, then outer walls, then an inner wall, then a keep, then guards at the keep door, then a locked vault inside the keep. Attackers don't lose because one wall is unclimbable — every wall can be climbed given enough time. They lose because climbing six walls takes so long and makes so much noise that they get caught between wall three and wall four.

**What's Really Happening.** Every security control can fail. Passwords get phished. Sessions get hijacked. Databases get dumped. Code has bugs. Defense in depth means designing so that *no single failure is fatal*. In VaultLog: a stolen password is stopped by MFA. A hijacked session is stopped by step-up authentication for dangerous actions. A leaked database is stopped by encryption. A SQL injection is stopped by RLS scoping. A rogue employee is stopped by the audit ledger. Each layer assumes the one above it might already be broken.

**The Interview Answer.** "We practiced defense in depth: independent layers that each fail closed. The RLS layer doesn't trust the application layer to add correct WHERE clauses. The use-case layer doesn't trust the router to check step-up. The encryption layer doesn't trust the access control to prevent dumps. Any single bug or compromise degrades security; it doesn't collapse it."

***

## 2. Password hashing: why we never store passwords

**The Story.** Imagine a hotel that, instead of keeping a list of guests' room keys, keeps a machine that can *test* keys. You walk up and insert your key; the machine says "yes, this opens room 12" or "no." The hotel never has your key — it only ever *checks* keys. Now imagine a thief breaks into the hotel office and steals everything. He gets the machine... which is useless. It can test keys, but it can't tell him what the keys look like. He'd have to cut millions of random keys and try them one by one.

**What's Really Happening.** We don't store passwords; we store the output of a **one-way function** — math that's easy to compute forward and practically impossible to reverse. Argon2id (our choice from Chapter 3) additionally is:

- **Slow on purpose.** Checking one password takes ~100 milliseconds. That's nothing for a user logging in once — but an attacker who stole the hash database must spend 100ms *per guess*. Guessing a billion passwords takes years instead of seconds.
- **Memory-hard.** It requires significant RAM per attempt, which destroys the attacker's favorite tool: GPUs, which are fast precisely because they run thousands of small parallel tasks with little memory each.
- **Salted.** A random value (the salt) is mixed into each password before hashing. Without salts, two users with the password `hunter2` would have identical hashes — the attacker cracks one and gets both, and precomputed "rainbow tables" of common passwords work instantly. The salt is stored in plain sight next to the hash — its job isn't secrecy, it's uniqueness. Same password, different salt, completely different hash.

**The subtle part interviews love:** when you verify a password, you hash the attempt and compare — and Argon2's compare is **constant-time**, meaning it takes the same time whether the guess is right or wrong. Otherwise, an attacker measuring response times could figure out the hash character by character (a *timing side-channel*). You never write `hash == stored` yourself; you use the library's verify function.

**The Interview Answer.** "We used Argon2id with per-user salts and constant-time verification. Passwords are never stored, only proofs that can be checked. The work factor makes online and offline brute force economically infeasible, and memory-hardness resists GPU cracking."

***

## 3. JWTs: signed envelopes, not encrypted ones

**The Story.** A JWT is like a **wax-sealed letter**, not a locked box. Anyone can open it and read what's inside — the letter isn't secret. But the wax seal has the sender's unique stamp, and the stamp is *impossible to forge*. If anyone changes even one word of the letter and re-seals it, the seal looks wrong, and you throw the letter away.

That's the entire point of a JWT: it doesn't hide information, it **proves the information hasn't been tampered with and came from us**.

**What's Really Happening.** A JWT is three parts, dot-separated:

```text
header.payload.signature
```

- **Header:** "I'm a JWT, signed with RS256."
- **Payload:** the claims — who you are (`sub`), which tenant (`tid`), which session (`sid`), when you expire (`exp`), how you authenticated (`amr`).
- **Signature:** computed as `sign(header + "." + payload, private_key)`.

When VaultLog receives a JWT, it recomputes the verification using its public key. If the payload was changed by even one character, the signature check fails. The server doesn't need to *store* anything — the token carries its own proof of authenticity. That's what "stateless" means.

**Why RS256 (asymmetric) instead of HS256 (symmetric)?** HS256 uses one shared secret to both sign and verify — anyone who can verify tokens can also *mint* them. If that secret leaks from any service that only needs to verify, the attacker can forge tokens for anyone. RS256 splits the powers: the **private key** signs (only the auth service has it), the **public key** verifies (anyone can have it, it's public). VaultLog's API verifies but can never mint. This is **least privilege applied to cryptography**.

**The classic JWT attacks — know these cold:**

1. **Algorithm confusion ("alg: none" or RS256→HS256).** Old libraries let the *token itself* declare which algorithm to verify with. An attacker takes a real token, re-signs a forged payload using the server's *public* key as an HMAC secret, sets `alg: HS256` — and a naive server verifies it with the public key as the HMAC secret. Forgery succeeds. Defense (which we implemented): **hard-code the allowed algorithm list** (`algorithms=["RS256"]`), never read `alg` from the token.
2. **Missing expiry/audience checks.** A token minted for a *different* application but signed by a trusted key might verify fine unless you check `aud` ("who is this token for?"). We require `iss`, `aud`, and `exp` on every verification.
3. **Theft.** A JWT is a *bearer token* — whoever holds it, is it. Like cash. That's why access tokens live only 10 minutes and why we pair them with the refresh machinery (next section).

**The Interview Answer.** "JWTs provide integrity and authenticity, not confidentiality — anyone can base64-decode the payload, so we never put secrets in it. We used RS256 so verification keys can be distributed without minting power, pinned the algorithm server-side against confusion attacks, and validated issuer, audience, and expiry explicitly."

***

## 4. Refresh tokens and rotation: the two-key hotel

**The Story.** Imagine a hotel with a clever key system. You get two keys at check-in:

- A **room key** that stops working after 10 minutes.
- A **front-desk voucher**, good for a week, that you trade at the desk for a fresh room key.

Why bother? If a pickpocket steals your *room key*, they can enter your room for at most 10 minutes. If they steal your *voucher*, that's worse — but here's the trick: **every time you trade in a voucher, you get a new voucher, and the old one is destroyed.** There's only ever one valid voucher.

Now the pickpocket tries to use the stolen voucher. One of two things happens: either they use it first — and when *you* later present your voucher, the desk says "this was already exchanged, and we only ever issue one at a time... someone's been pickpocketed" — or you use yours first and theirs dies. Either way, **the moment both of you touch the system, the hotel knows there's a thief**, cancels the entire stay, and calls security. The theft detects itself.

**What's Really Happening.** This is refresh token rotation with reuse detection, exactly as Chapter 3 implements it:

- **Access token** (the room key): short-lived JWT, 10 minutes, sent on every API request. If stolen, the damage window is small.
- **Refresh token** (the voucher): long-lived random string, stored in the database *only as a SHA-256 hash*, sent in an HttpOnly cookie. Traded for a new access token **and a new refresh token** on every use; the old one is marked used.
- **Reuse detection:** if a token marked "used" is ever presented again, both the legitimate user and the thief must exist. We can't tell which is which — so we revoke the entire **token family** (the whole session) and force re-login. Security over convenience, deliberately.

**Why hash the refresh token in the database?** Because a database leak (the threat from Chapter 6) would otherwise hand attackers every active session. Refresh tokens are random, high-entropy strings, so a plain fast hash (SHA-256) suffices — no Argon2 needed, because brute-forcing 256 random bits is impossible regardless of hash speed. Argon2's slowness defends *human-chosen* secrets; refresh tokens are machine-generated.

**Why a cookie, and why HttpOnly + Secure + SameSite?**

- **HttpOnly:** JavaScript cannot read the cookie. The most common token thief is **XSS** — malicious JavaScript injected into a page. If tokens live in localStorage, any XSS bug hands them over. HttpOnly cookies are invisible to the script, so the XSS attacker can't steal the crown jewel.
- **Secure:** sent only over HTTPS, so it can't be sniffed on the network.
- **SameSite=Lax:** the browser won't attach the cookie to cross-site POSTs — the primary CSRF defense (section 6).
- **Path scoping** (`/api/v1/auth`): the cookie is only sent to the refresh endpoint, not every API call — shrinking its exposure surface.

**The Interview Answer.** "We paired 10-minute stateless access tokens with rotating refresh tokens stored server-side as hashes. Rotation with reuse detection turns token theft into a self-revealing event — a replayed refresh token revokes the whole session family. The refresh token rides in an HttpOnly, Secure, SameSite, path-scoped cookie so XSS can't read it and CSRF can't fire it cross-site."

***

## 5. Sessions vs. tokens: the revocation problem

**The Story.** Back to the wax-sealed letter. Its great strength — "the letter carries its own proof" — is also its weakness. Suppose you fire an employee and want their access *dead right now*. Their JWT says "valid until 12:10," the seal is genuine, and there's no phone line to every guard in the building saying "don't honor this letter." The letter is truth; you can't un-print it.

**What's Really Happening.** Stateless JWTs can't be individually revoked — that's the price of not consulting a database on every request. The honest options:

1. **Short expiry** (our choice): the token dies on its own in ≤10 minutes, and revocation happens at the *session* level — kill the session row, and the refresh flow that would mint the next access token is dead. Worst case: 10 minutes of stale access.
2. **Server-side token store** (your Redis idea from our discussion): check every token against a live registry. Real instant revocation, but you've re-introduced state, a per-request lookup, and a new availability dependency. Valid choice — a tradeoff, not an upgrade.
3. **Deny-lists**: track revoked token IDs in Redis and check them. Same tradeoff, selectively applied.

VaultLog chose option 1 plus step-up gates (section 8) so that even inside that 10-minute window, a stolen token can't do destructive things.

**The Interview Answer.** "Stateless tokens trade revocability for scalability. We bounded the risk with short lifetimes, session-level revocation that stops renewal, and step-up requirements that limit what a stale token can do. If the threat model demanded instant revocation, we'd move to server-checked tokens and accept the latency and availability cost consciously."

***

## 6. CSRF: the forged request your browser helpfully signs

**The Story.** Suppose your bank's website keeps you logged in via a wristband the browser automatically shows to the bank *every time you visit any bank page*. Now a scammer sends you an email: "Click here for cute cats." The link secretly opens a page with a hidden form that auto-submits "transfer $1000 to the scammer" *to your bank's website*. Your browser, being helpful, goes to the bank — and politely flashes your wristband. The bank sees a valid wristband and executes the transfer. You never typed anything. Your browser was tricked into vouching for a request you didn't intend.

That's **Cross-Site Request Forgery**: the attack rides on the browser's habit of automatically attaching cookies to requests.

**What's Really Happening.** The defense family:

- **SameSite cookies (our primary):** tells the browser "don't attach this cookie when the request originates from another site." The cute-cats page's form submission arrives *without* the wristband. `Lax` allows top-level navigations (links you click) but blocks cross-site POSTs — which are exactly the dangerous ones.
- **Origin checking (our second layer):** the server inspects the `Origin` header browsers attach to cross-origin requests and rejects ones that don't match our known frontend. An attacker *cannot* forge the Origin header from a victim's browser — the browser controls it.
- **CSRF tokens (the classic pattern you mentioned):** the server issues a random token; the frontend must echo it back in a header *and* it exists in a cookie. A malicious site can make the browser *send* the cookie, but it can't *read* it (same-origin policy) — so it can't put the matching value in the header. Mismatch or absence → reject. Your summary was almost right: it's not that a mismatch proves the account is compromised — it proves the request didn't come from our legitimate frontend.

**Key nuance for interviews:** CSRF only threatens **cookie-based authentication**. If the access token travels in an `Authorization: Bearer` header set by JavaScript, CSRF is impossible by construction — attacker sites can't read your token, so they can't set the header. That's why VaultLog's *access* tokens need no CSRF defense, but the refresh *cookie* flow does (hence SameSite + Origin check in Chapter 8).

**The Interview Answer.** "CSRF exploits ambient cookie authority. We layered SameSite=Lax with server-side Origin validation on the cookie-authenticated endpoints. Bearer-token endpoints are inherently CSRF-immune because attackers can't read the token to forge the header."

***

## 7. MFA and TOTP: the shared clock secret

**The Story.** You and the VaultLog club agree on a secret recipe at enrollment time: a magic number generator seeded with a secret only you two share (that's the QR code you scan). The recipe is: *"take the secret seed, mix it with the current 30-second time slice, shake with one-way math, pour out a 6-digit number."*

Because you both have the same seed and roughly the same clocks, you both compute the same number at the same time. When you type `483 920`, the server computes its own number and compares. An attacker who steals your *password* still can't log in — they'd need your seed, which lives on your phone, encrypted, somewhere else entirely.

**What's Really Happening.** TOTP (RFC 6238) is `HMAC(secret_seed, floor(current_time / 30))`, truncated to 6 digits. Security properties to know:

- **Something you know (password) + something you have (the seed/device)** — two different failure modes. Phishing your password doesn't phish your phone.
- **The seed is the crown jewel.** Anyone with the seed generates codes forever. That's why Chapter 4 encrypts seeds at rest with AES-GCM under a dedicated KEK, AAD-bound to the user ID — a database dump can't reveal seeds, and a seed row transplanted to another user fails to decrypt.
- **6 digits ≈ 20 bits of entropy.** Online brute force is trivially feasible *unless rate-limited*. This is why Chapter 8's limiter (5 attempts per challenge) isn't optional polish — **the rate limit is part of what makes the cryptography sufficient.** Always mention this pairing in interviews; it shows systems thinking.
- **`valid_window=1`** tolerates one adjacent 30-second step for clock drift — usability vs. a slightly larger guessing window. A conscious tradeoff.
- **Recovery codes** are one-time, high-entropy, stored hashed. They're a backup *possession* factor, which is why using one is auditable and single-use.

**Why step-up authentication is separate from MFA-at-login** — this deserves its own mini-story: A session authenticated yesterday proves *someone* with the phone logged in yesterday. It says nothing about who's holding the keyboard *now* — maybe a thief with your unlocked laptop. Step-up ("prove the phone is present **right now** before deleting a vault") is about **freshness of proof**, not strength of the original login. Session hijacking is a top real-world attack; step-up is the control that caps its blast radius. We implemented it as a 5-minute JWT bound to user *and* session *and* purpose — so a step-up token for "disable MFA" can't authorize "delete vault," and a step-up from session A can't be replayed into session B.

**The Interview Answer.** "TOTP gives possession-factor proof via a time-sliced HMAC of a shared seed. We encrypted seeds at rest with context-bound AEAD, throttled verification because 6-digit entropy only works under rate limits, and separated login-time MFA from step-up MFA — the latter answers freshness, defending against live session hijacking for destructive operations."

***

## 8. Row-level security: the bouncer who checks every row, not every guest

**The Story.** Normal application security is like a bouncer at the club door who checks your ticket and wristband, then lets you wander anywhere inside — trusting that the bartenders (the code) will only serve you drinks you're allowed to have. If a bartender has a buggy night and forgets to check, you get served someone else's tab.

Row-level security moves the check *into the warehouse*. Every bottle in the storeroom is tagged with the club it belongs to, and the storeroom itself refuses to hand a bottle to anyone whose current club tag doesn't match — no matter what the bartender asked for. Even if the bartender's order pad says "give me ALL the bottles" (a bug, or SQL injection), the storeroom only releases yours.

**What's Really Happening.** RLS is a policy *inside the database engine*: for every query on a protected table, Postgres automatically appends `AND tenant_id = current_setting('app.current_tenant')` — to SELECTs, and via `WITH CHECK`, to INSERTs/UPDATEs too. Why this is a *security boundary* and not just a filter:

- **It can't be forgotten.** Every `WHERE tenant_id = ...` in application code is one distracted developer away from an omission — and the omission is silent; everything works, data just leaks. RLS makes the correct behavior the default at the layer no application bug can bypass.
- **It can't be bypassed by injection.** SQL injection runs as the app role, in the app's session, with the app's tenant context set. Injected SQL can read *this tenant's* data — a real problem — but structurally cannot reach across tenants.
- **`FORCE ROW LEVEL SECURITY`** matters because table owners skip RLS by default; forcing it means even the owner role obeys the policy.
- **A separate `NOBYPASSRLS` app role with least-privilege grants** means the app isn't the table owner, can't disable policies, and can't UPDATE/DELETE immutable tables (secret versions, audit events) *even under full SQL injection*.

This is the deepest layer of the moat — the one that still holds when every application-layer defense has failed.

**The Interview Answer.** "We enforced tenant isolation in Postgres itself via RLS with FORCE, a NOBYPASSRLS application role, and tenant context set transaction-locally (SET LOCAL) so pooled connections can't leak context. The application-layer filters exist for performance and clarity; the RLS layer exists so their failure is never fatal."

***

## 9. RBAC, least privilege, and IDOR

**The Story.** An office building has two kinds of rules. **Role badges:** managers can enter any floor; staff can enter floors they're *assigned* to; interns, the lobby and their assigned rooms. **Room assignment lists:** even staff with a valid badge can't open a room they're not assigned to. Your badge says what *kind* of things you may do; the assignment list says *which specific ones*.

Now, the classic burglary trick: a staff member assigned to room 201 walks up to room 305's door and tries their badge — just to see. If the building only checks "is this a valid badge?" (authentication) and never "is this person assigned to *this* room?" (authorization), they're in. That bug has a name — **IDOR**: Insecure Direct Object Reference. "I know the UUID of a vault; let me just ask for it and see what happens."

**What's Really Happening.**

- **Authentication ≠ authorization.** Knowing *who* someone is never implies *what* they may touch. VaultLog's Chapter 5 policy service exists because authorization scattered across routers rots into IDOR bugs.
- **Two axes:** org role (owner/admin/member/viewer) for baseline capabilities, per-vault grants (read/write/admin) for compartmentalization *within* a tenant — so one compromised member account doesn't expose the whole org's secrets.
- **Least privilege** is the umbrella principle: every identity (user, app DB role, service account, KMS binding) gets the *minimum* access for its job. VaultLog's app role can't UPDATE audit rows; the Cloud Run service account can *use* the KMS key but not export or administer it; the JWT public key can verify but not sign. Same principle, three different layers.
- **The 404 vs 403 trick:** for objects that aren't yours, we return 404 "not found" — not 403 "exists but forbidden." A 403 confirms the UUID exists, which is itself information (an *existence oracle*) that helps attackers enumerate resources.

**The Interview Answer.** "We centralized authorization in a policy service combining org roles with per-vault grants, enforced least privilege across users, DB roles, and cloud IAM identically, and returned 404 rather than 403 on invisible resources to avoid existence oracles. Authorization checks live in the service layer, not just routers, so they survive future endpoint variants."

***

## 10. Encryption at rest: the core of it all

### Symmetric encryption and AES-GCM

**The Story.** Symmetric encryption is a lockbox where the *same key* locks and unlocks. Simple — but early lockbox designs had a flaw: a sneaky person could *file down or swap parts of a locked box's contents* without opening it, and you'd unlock it later to find altered contents and no sign of tampering.

AES-GCM fixes this with a **tamper-evident seal** on the lockbox. When you lock it, the mechanism stamps a seal that depends on the exact contents. When you unlock, the mechanism checks the seal first — if anyone changed even one bit of the contents, *the box refuses to open at all* and tells you it was tampered with. It never hands you silently-corrupted contents.

**What's Really Happening.** AES-256-GCM is **AEAD**: authenticated encryption with associated data. Three guarantees: confidentiality (ciphertext reveals nothing), integrity (the 128-bit tag makes any modification detectable — decryption *fails loudly* rather than returning garbage), and AAD binding (below). The one hard rule: **never reuse a nonce with the same key** — doing so catastrophically breaks both secrecy and integrity. We generate a fresh random 96-bit nonce per encryption; the nonce isn't secret and travels with the ciphertext.

Why not CBC or ECB (common interview bait)? ECB is deterministic — identical plaintext blocks produce identical ciphertext blocks, leaking patterns (the famous ECB penguin). CBC lacks authentication entirely and, when glued to a MAC by hand, historically produced padding-oracle disasters. AEAD modes like GCM (or ChaCha20-Poly1305) make the dangerous composition the library's job, not yours.

### AAD: welding ciphertext to its home

**The Story.** Imagine the tamper-evident seal also **embosses the box's address onto the seal**: "Property of Tenant 7, Vault 3, Secret 42, Version 2." If a thief steals the box and slips it into a *different* vault's shelf, the unlock mechanism reads the new shelf's address, compares it with the embossed address, sees the mismatch — and refuses to open. The box only opens *in its rightful place*.

**What's Really Happening.** AAD (additional authenticated data) isn't encrypted, but it's *authenticated* — decryption only succeeds if you present the exact AAD used at encryption. VaultLog derives AAD from stable identifiers (`tenant:vault:secret:version`). This kills the **ciphertext transplant attack**: an attacker with database write access copies secret A's ciphertext over secret B's row, then asks the system to reveal "secret B" — without AAD, they'd read A's plaintext through B's authorized path. With AAD, decryption fails because the context doesn't match. We *derive* rather than store the AAD, so it can't be tampered with to match.

### Envelope encryption: KEKs and DEKs — the chapter's centerpiece

**The Story.** A bank has 10,000 safe deposit boxes. Option one: one master key opens all 10,000 boxes. Simple — but if that key is ever copied, everything is gone, and *changing* the lock means a locksmith visiting all 10,000 boxes while the bank stays closed for a week.

So real banks use two keys per box: the **box key** (opens the box) and the **guard's key** (doesn't open any box — it unlocks the small cabinet where all the *box keys* are kept). Now:

- A burglar who photographs the vault room (database dump) gets locked boxes *and* a locked key cabinet. Useless without the guard's key.
- Rotating the guard's key means re-locking *one cabinet* — not 10,000 boxes.
- Each bank branch (tenant) has its own box keys, so one branch's key compromise doesn't touch another branch.
- And the guard's key itself never sleeps in the bank — the guard (the KMS) keeps it on their belt. Bank staff *ask the guard* to unlock the cabinet; they never hold the key.

**What's Really Happening.** This is envelope encryption, exactly as Chapter 6 builds it:

- **DEK (data-encryption key):** a random 256-bit key per tenant that actually encrypts secrets. Stored in the database — but only *wrapped* (encrypted).
- **KEK (key-encryption key):** wraps/unwraps DEKs. In production it lives in a KMS/HSM where it **cannot be exported** — the API sends wrap/unwrap *requests*; the key material never enters application memory, let alone the database.
- **Consequences that make this worth the complexity:** a full database dump (ciphertext secrets + wrapped DEKs) is worthless without the KEK; KEK rotation re-wraps 32-byte DEKs instead of re-encrypting all data; DEK rotation installs a new version instantly with lazy re-encryption in batches; compromise is tenant-scoped.
- **Key versioning:** keys are never replaced in place — new versions are added, old ones retired but retained while ciphertexts reference them. Destroying a key version that data still references is irrecoverable data loss, so retirement is gated on a verified sweep.

**And the honest limit — say this in interviews before they ask:** encryption at rest does *not* protect against a fully compromised running application, because the app can legitimately ask the KMS to unwrap anything. It defends against *storage-layer* threats: dumps, backups, snapshots, stolen disks, rogue DBAs. The live-access threats are what auth, MFA, RLS, RBAC, step-up, and audit are for. Knowing where each layer's protection *ends* is the difference between an engineer and a brochure.

### Hash chains: the audit ledger's tamper evidence

**The Story.** A notary keeps a ledger where each new entry includes a **photocopy of a special fingerprint of the previous page** — and each page's own fingerprint depends on everything on that page plus the previous fingerprint it carries. If someone tears out page 40 and rewrites it, page 40's fingerprint changes — so page 41 (which carries a photocopy of the old fingerprint) no longer matches, and neither does anything after. To hide one change, the forger must rewrite *every later page* — and if the notary already mailed last month's final fingerprint to an independent archive, the forgery is caught instantly.

**What's Really Happening.** Chapter 7's ledger: `hash(n) = SHA-256(hash(n-1) || canonical_bytes(event n))`. Each entry commits to the entire history before it. Verification recomputes the chain and checks sequence continuity, link integrity, content hashes, and the chain head. Four attacks, four checks: deletion, re-linking, content edits, head rollback. The supporting controls matter as much as the math: **the app role has no UPDATE/DELETE privilege** (the application cannot rewrite history even if fully compromised via injection), and **canonicalization** (byte-stable serialization) is what makes "recompute and compare" possible at all — two runs must produce byte-identical input. And the honest ceiling again: a hash chain is tamper-*evident*, not tamper-*proof* — an attacker with full DB control can rewrite and recompute the chain. Detecting *that* requires anchoring chain-head digests in an independent system (the level-4 design), which we documented as the next step.

***

## 11. The quiet controls: rate limiting, error handling, logging

**Rate limiting.** A combination lock with a million combinations is "secure" mathematically and worthless practically if you can try a thousand combinations per second. Every entropy argument in this book — 6-digit TOTPs, recovery codes, even passwords — silently assumes "online guessing is throttled." Rate limiting isn't an add-on; it's the premise that makes the math true. We used sliding-window counters in Redis so the limit holds across all autoscaled instances, with fail-closed on credential endpoints (an unthrottled login is worse than a temporarily unavailable one) and fail-open on data endpoints (availability matters; other layers still protect data).

**Error handling.** Every error message is a tiny press release to a potential attacker. Stack traces reveal framework, file paths, library versions; Pydantic's default 422s echo back submitted *values* (including the secret you just tried to store); "invalid password" vs "no such account" is an account-enumeration oracle. VaultLog's rule: internals get full detail with request IDs; externals get a code and the same request ID — correlation without disclosure.

**Logging.** Logs are the least-protected data store and the most attractive leak target: they get shipped to third parties, retained for years, read by many employees. So dangerous values are stripped *by the pipeline* (a redaction processor and an audit-metadata guard), not by developer discipline. The recurring principle of this whole book in one sentence: **make the dangerous thing impossible, not merely discouraged.**

***

## 12. Putting it together: the interview simulation

Interviewer: *"Walk me through what happens when a user reveals a secret, and how each layer contributes to security."*

> "The request hits the API with a short-lived RS256 access token — verified against the public key with pinned algorithms, so forgery and algorithm-confusion are out. The token's tenant claim builds a transaction-local context, and Postgres RLS enforces it at the engine, so even a bug or injection in my code can't cross tenants. The policy service then checks authorization — org role plus per-vault grant — returning 404 for anything invisible to avoid existence oracles. The reveal itself fetches the wrapped DEK, asks KMS to unwrap it — the KEK never enters our memory — and decrypts with AES-GCM using AAD derived from tenant, vault, secret, and version, so any tampering or ciphertext transplant fails loudly. The plaintext goes out in a POST response with no-store caching; it's never logged — the pipeline redacts by construction. In the same transaction, a hash-chained audit event is appended — the app role physically can't update or delete it — so the access is provably recorded, and a scheduled verifier plus alerts mean tampering gets a human paged. And if this were a *delete* rather than a reveal, a 5-minute, purpose-bound step-up token would also be required, because a day-old session doesn't prove who's at the keyboard right now."

That's one paragraph, and it demonstrates threat modeling, cryptography, systems design, and operational maturity. Practice saying your version of it out loud.

Interviewer: *"What's the weakest part of this design?"* — the correct answer is never "nothing." It's: *"The application tier is the trusted computing base. If the running app is fully compromised, at-rest encryption doesn't help — KMS will unwrap for the attacker as readily as for us. We mitigated with least-privilege IAM, step-up, anomaly alerts on reveal volume, and instant session revocation, and the next hardening step would be external audit anchoring and passkeys."* Candidates who know where their own design ends are the ones who get hired.

***

## The vocabulary cheat sheet

| Term | One-line explanation |
|---|---|
| **Hashing (Argon2id)** | One-way, slow, memory-hard password proof; salted per user; verified constant-time |
| **Salting** | Random per-user input making identical passwords hash differently; defeats rainbow tables |
| **JWT / RS256** | Signed (not encrypted) claims; asymmetric keys separate minting from verifying |
| **Algorithm confusion** | Attack where the token picks its verification algorithm; defense: pin algorithms server-side |
| **Bearer token** | Possession = identity, like cash; hence short lifetimes |
| **Refresh rotation** | Every refresh destroys the old token; reuse proves theft and kills the session family |
| **HttpOnly cookie** | Token storage JavaScript can't read; the XSS mitigation |
| **CSRF** | Tricking a browser into attaching its cookies to a request the user didn't intend; defenses: SameSite, Origin checks, CSRF tokens |
| **TOTP** | HMAC of shared seed + 30-second time slice; possession factor; only safe under rate limits |
| **Step-up auth** | Fresh proof for dangerous actions; answers "who's here *now*," not "who logged in then" |
| **RLS** | Database-enforced per-row tenant filtering; the boundary bugs and injection can't cross |
| **Least privilege** | Every identity gets the minimum access, at every layer — users, DB roles, IAM, keys |
| **IDOR** | Authorization gap: asking for an object by ID you don't own; defense: centralized policy + 404s |
| **AEAD / AES-GCM** | Encryption + tamper-evident seal in one; nonce reuse is catastrophic |
| **AAD** | Context authenticated with ciphertext; binds data to its rightful place; kills transplants |
| **Envelope encryption** | DEKs encrypt data; KEK encrypts DEKs; cheap rotation, scoped blast radius, dump-proof storage |
| **KMS/HSM** | Holds the KEK so it can be *used* but never *held* or exported |
| **Key versioning** | Keys are added and retired, never replaced; history stays decryptable, new writes use the latest |
| **Hash chain** | Each audit entry commits to all previous ones; tampering requires rewriting everything — and gets caught |
| **Canonicalization** | Byte-stable serialization; the unglamorous thing every hash/signature scheme depends on |
| **Fail closed** | When a security control breaks, it denies; the only acceptable failure direction for credential checks |
| **Defense in depth** | Independent layers that each assume the layer above may already be compromised |

You now hold both halves of security engineering: the implementation from Chapters 1–9, and the language to defend it from this chapter. The best engineers move fluidly between the two — building the lock, and being able to explain to anyone, in plain words, exactly why it's shaped that way.
