"""Application settings using Pydantic Settings for type-safe configuration."""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings are type-safe and validated by Pydantic.
    """
    
    # Application
    app_name: str = "Interstellar Mare - AI Real Estate Assistant"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"
    
    # API
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/interstellar_mare"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10
    
    # LLM Configuration (DeepSeek/OpenAI Compatible)
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 1000
    
    # Per-Agent LLM Configuration
    question_agent_temperature: float = 0.7
    question_agent_max_tokens: int = 1000
    analysis_agent_temperature: float = 0.8
    analysis_agent_max_tokens: int = 1500
    validation_agent_temperature: float = 0.2
    validation_agent_max_tokens: int = 800
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # SMTP / Email Configuration
    smtp_server: Optional[str] = None
    smtp_port: int = 587
    smtp_email: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_recipient_emails: str = ""  # Comma-separated list of recipient emails
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Returns:
        Singleton Settings instance
    """
    return Settings()
