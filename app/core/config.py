from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Agentic Restaurant Customer Service"
    DEBUG: bool = False
    VERSION: str = "1.0.0"
    

    ##change this to your actual database URL in production or use environment variables
    # Database
    DATABASE_URL: str 
    
    OPENAI_API_KEY: str  #changed here to be read from env variable
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
