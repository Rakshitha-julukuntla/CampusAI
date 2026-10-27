from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/campusai"

    JWT_SECRET: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    ADMIN_EMAIL: str = "admin@campusai.in"
    ADMIN_PASSWORD: str = "admin123"

    CHROMA_DIR: str = "./chroma_db"
    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    COLLECTION_NAME: str = "campus_docs"

    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    TOP_K: int = 5

    FRONTEND_ORIGIN: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
