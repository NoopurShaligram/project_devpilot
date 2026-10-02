from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str | None = None
    llm_model: str | None = None

    checkpoint_db: str = ".forge/checkpoints.sqlite"
    max_fix_attempts: int = 2
    max_review_cycles: int = 2
    max_agent_recursion: int = 40

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def ensure_runtime_dirs(self) -> None:
        Path(self.checkpoint_db).parent.mkdir(
            parents=True,
            exist_ok=True,
        )


settings = Settings()
settings.ensure_runtime_dirs()
