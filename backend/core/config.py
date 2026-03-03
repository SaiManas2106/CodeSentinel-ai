"""Application configuration using Pydantic Settings v2."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database settings."""

    url: str = Field(..., alias="DATABASE_URL")
    host: str = Field("postgresql", alias="POSTGRES_HOST")
    port: int = Field(5432, alias="POSTGRES_PORT")
    db: str = Field(..., alias="POSTGRES_DB")
    user: str = Field(..., alias="POSTGRES_USER")
    password: str = Field(..., alias="POSTGRES_PASSWORD")

    model_config = SettingsConfigDict(extra="ignore")


class RedisSettings(BaseSettings):
    """Redis settings."""

    url: str = Field(..., alias="REDIS_URL")
    host: str = Field("redis", alias="REDIS_HOST")
    port: int = Field(6379, alias="REDIS_PORT")
    db: int = Field(0, alias="REDIS_DB")
    password: str = Field(..., alias="REDIS_PASSWORD")

    model_config = SettingsConfigDict(extra="ignore")


class QdrantSettings(BaseSettings):
    """Qdrant settings."""

    host: str = Field("qdrant", alias="QDRANT_HOST")
    port: int = Field(6333, alias="QDRANT_PORT")
    api_key: str = Field(default="", alias="QDRANT_API_KEY")
    collection: str = Field("codesentinel_chunks", alias="QDRANT_COLLECTION")

    model_config = SettingsConfigDict(extra="ignore")


class KafkaSettings(BaseSettings):
    """Kafka settings."""

    bootstrap_servers: str = Field(..., alias="KAFKA_BOOTSTRAP_SERVERS")
    pr_review_topic: str = Field("pr-review-requests", alias="KAFKA_PR_REVIEW_TOPIC")
    consumer_group: str = Field("review-workers", alias="KAFKA_CONSUMER_GROUP")

    model_config = SettingsConfigDict(extra="ignore")


class MongoSettings(BaseSettings):
    """MongoDB settings."""

    uri: str = Field(..., alias="MONGO_URI")
    host: str = Field("mongodb", alias="MONGO_HOST")
    port: int = Field(27017, alias="MONGO_PORT")
    database: str = Field("codesentinel", alias="MONGO_DATABASE")

    model_config = SettingsConfigDict(extra="ignore")


class AWSSettings(BaseSettings):
    """AWS settings."""

    access_key_id: str = Field(..., alias="AWS_ACCESS_KEY_ID")
    secret_access_key: str = Field(..., alias="AWS_SECRET_ACCESS_KEY")
    region: str = Field("us-east-1", alias="AWS_REGION")
    s3_bucket: str = Field(..., alias="S3_BUCKET_NAME")
    minio_endpoint: str = Field("http://minio:9000", alias="MINIO_ENDPOINT")

    model_config = SettingsConfigDict(extra="ignore")


class OpenAISettings(BaseSettings):
    """OpenAI/Cohere settings."""

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4o", alias="OPENAI_MODEL")
    embedding_model: str = Field("text-embedding-3-large", alias="OPENAI_EMBEDDING_MODEL")
    cohere_api_key: str = Field(..., alias="COHERE_API_KEY")
    huggingface_token: str = Field(..., alias="HUGGINGFACE_TOKEN")
    codebert_model_name: str = Field("microsoft/codebert-base", alias="CODEBERT_MODEL_NAME")

    model_config = SettingsConfigDict(extra="ignore")


class GitHubSettings(BaseSettings):
    """GitHub OAuth and App settings."""

    client_id: str = Field(..., alias="GITHUB_CLIENT_ID")
    client_secret: str = Field(..., alias="GITHUB_CLIENT_SECRET")
    redirect_uri: HttpUrl = Field(..., alias="GITHUB_OAUTH_REDIRECT_URI")
    app_id: str = Field(..., alias="GITHUB_APP_ID")
    app_private_key: str = Field(..., alias="GITHUB_APP_PRIVATE_KEY")
    webhook_secret: str = Field(..., alias="GITHUB_WEBHOOK_SECRET")

    model_config = SettingsConfigDict(extra="ignore")


class MLflowSettings(BaseSettings):
    """MLflow and W&B settings."""

    tracking_uri: str = Field(..., alias="MLFLOW_TRACKING_URI")
    wandb_api_key: str = Field(..., alias="WANDB_API_KEY")
    wandb_project: str = Field("codesentinel-ai", alias="WANDB_PROJECT")
    wandb_entity: str = Field(..., alias="WANDB_ENTITY")

    model_config = SettingsConfigDict(extra="ignore")


class SentrySettings(BaseSettings):
    """Sentry settings."""

    dsn: str = Field(default="", alias="SENTRY_DSN")
    traces_sample_rate: float = Field(0.2, alias="SENTRY_TRACES_SAMPLE_RATE")

    model_config = SettingsConfigDict(extra="ignore")


class JWTSettings(BaseSettings):
    """JWT settings."""

    secret_key: str = Field(..., alias="JWT_SECRET_KEY")
    algorithm: Literal["HS256", "HS384", "HS512"] = Field("HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(14, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    model_config = SettingsConfigDict(extra="ignore")


class Settings(BaseSettings):
    """Top-level settings."""

    app_name: str = Field("CodeSentinel AI", alias="APP_NAME")
    app_env: Literal["development", "staging", "production"] = Field("development", alias="APP_ENV")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")
    api_v1_prefix: str = Field("/api/v1", alias="API_V1_PREFIX")
    frontend_url: str = Field("http://localhost:3000", alias="FRONTEND_URL")
    backend_url: str = Field("http://localhost:8000", alias="BACKEND_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    cors_origins: str = Field("http://localhost:3000", alias="CORS_ORIGINS")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    mongo: MongoSettings = Field(default_factory=MongoSettings)
    aws: AWSSettings = Field(default_factory=AWSSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    mlflow: MLflowSettings = Field(default_factory=MLflowSettings)
    sentry: SentrySettings = Field(default_factory=SentrySettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Validate log level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()
        if normalized not in allowed:
            raise ValueError(f"Invalid log level: {value}")
        return normalized

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_prefix(cls, value: str) -> str:
        """Ensure API prefix starts with slash."""
        if not value.startswith("/"):
            raise ValueError("API prefix must start with '/'")
        return value.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        """Return parsed CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
