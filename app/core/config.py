from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Agentic Restaurant Customer Service"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    

    # Database
    DATABASE_URL: str = "postgresql://postgres:medo2006%40teto@localhost:5432/restaurant_db"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # LLM (Groq)
    GROQ_API_KEY: str = ""
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"

    # API
    API_V1_PREFIX: str = "/api/v1"
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
