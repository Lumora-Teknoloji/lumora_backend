from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )  # Fazladan env key'leri görmezden gel ve .env.local oku
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

    # AI API Keys (zorunlu - .env dosyasından alınmalı)
    openai_api_key: str = ""
    tavily_api_key: str = ""
    fal_api_key: str = ""
    fal_base_url: str = "https://fal.run"
    fal_model_path: str = "fal-ai/flux/dev"

    @property
    def allowed_origins(self) -> list[str]:
        """CORS için izin verilen origin'leri döndürür."""
        if self.cors_origins:
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return [self.frontend_url]


settings = Settings()

