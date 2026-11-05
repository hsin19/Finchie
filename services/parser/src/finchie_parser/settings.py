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
    workers: int = 2
    max_message_mb: int = 32
    ocr: bool = True
    log_level: str = "INFO"
    # PARSER_PDF_PASSWORDS__TAISHIN=... ; keys are institution IDs.
    pdf_passwords: dict[str, SecretStr] = Field(default_factory=dict)

    def passwords(self) -> list[str]:
        return [secret.get_secret_value() for secret in self.pdf_passwords.values()]
