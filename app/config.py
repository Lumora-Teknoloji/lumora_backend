from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Lumora Backend"
    api_prefix: str = "/api"
    app_env: str = "development"
    port: int = 8000

    postgresql_host: str
    postgresql_port: int = 5432
    postgresql_database: str
    postgresql_username: str
    postgresql_password: str

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    frontend_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"  # Virgülle ayrılmış origin listesi

    # AI API Keys (opsiyonel - yoksa AI özellikleri çalışmaz)
    openai_api_key: str = ""
    tavily_api_key: str = ""
    stability_api_key: str = ""  # Stability AI SDXL API key

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def allowed_origins(self) -> list[str]:
        """CORS için izin verilen origin'leri döndürür."""
        if self.cors_origins:
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return [self.frontend_url]


settings = Settings()

