from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    bind: str
    port: int
    data_dir: Path
    secrets_dir: Path
    config_dir: Path
    environment: str
    default_tenant: str
    minor_version: str
    redirect_uri: str
    authorize_url: str
    token_url: str
    sandbox_api: str
    production_api: str
    read_timeout: float
    write_timeout: float
    max_retries: int
    allow_production_writes: bool

    @property
    def audit_path(self) -> Path:
        return self.data_dir / "audit.jsonl"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "qbo.sqlite"

    @property
    def tokens_dir(self) -> Path:
        return self.data_dir / "tenants"

    def api_base(self, environment: str) -> str:
        env = (environment or self.environment).lower()
        if env == "production":
            return self.production_api.rstrip("/")
        return self.sandbox_api.rstrip("/")


def load_settings() -> Settings:
    env = (os.environ.get("QUICKBOOKS_ENV") or os.environ.get("QBO_ENV") or "sandbox").strip().lower()
    if env not in {"sandbox", "production"}:
        env = "sandbox"
    return Settings(
        bind=os.environ.get("QBO_BIND", "0.0.0.0"),
        port=int(os.environ.get("QBO_PORT", "14112")),
        data_dir=_path("QBO_DATA_DIR", "/data"),
        secrets_dir=_path("QBO_SECRETS_DIR", "/secrets"),
        config_dir=_path("QBO_CONFIG_DIR", "/app/config"),
        environment=env,
        default_tenant=os.environ.get("QBO_DEFAULT_TENANT", "company_a"),
        minor_version=os.environ.get("QBO_MINOR_VERSION", "75"),
        redirect_uri=os.environ.get("QBO_REDIRECT_URI", "http://localhost:14112/oauth/callback"),
        authorize_url=os.environ.get(
            "QBO_AUTHORIZE_URL", "https://appcenter.intuit.com/connect/oauth2"
        ),
        token_url=os.environ.get(
            "QBO_TOKEN_URL", "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
        ),
        sandbox_api=os.environ.get("QBO_SANDBOX_API", "https://sandbox-quickbooks.api.intuit.com"),
        production_api=os.environ.get("QBO_PRODUCTION_API", "https://quickbooks.api.intuit.com"),
        read_timeout=float(os.environ.get("QBO_READ_TIMEOUT", "30")),
        write_timeout=float(os.environ.get("QBO_WRITE_TIMEOUT", "30")),
        max_retries=int(os.environ.get("QBO_MAX_RETRIES", "3")),
        allow_production_writes=os.environ.get("QBO_ALLOW_PRODUCTION_WRITES", "false").strip().lower()
        in {"1", "true", "yes"},
    )
