from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Read from `PARSER_*` environment variables, nested keys split by `__`.

    For local runs, `.local/parser.env` at the repository root is read too
    (gitignored, ADR 0006).
    """

    model_config = SettingsConfigDict(
        env_prefix="PARSER_",
        env_nested_delimiter="__",
        env_file="../../.local/parser.env",
        extra="ignore",
    )

    host: str = "[::]"
    port: int = 50051
    # One thread pool serves ParseDocument, OpenDocument, and health checks. It must exceed the backend's
    # BACKEND_PARSE_CONCURRENCY (2): parses that fill it starve previews and the 3-second healthcheck.
    workers: int = 4
    # Must exceed the backend's BACKEND_MAX_UPLOAD_MB (32): a request carries the whole file plus its
    # other fields. The backend allows itself the same 1 MiB of headroom when sending.
    max_message_mb: int = 33
    ocr: bool = True
    log_level: str = "INFO"
    # PARSER_PDF_PASSWORDS__TAISHIN=... ; keys are institution IDs.
    pdf_passwords: dict[str, SecretStr] = Field(default_factory=dict)

    def passwords(self) -> list[str]:
        return [secret.get_secret_value() for secret in self.pdf_passwords.values()]
