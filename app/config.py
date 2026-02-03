from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
    )  # Fazladan env key'leri görmezden gel ve .env.local oku
    app_name: str = "Lumora Backend"
    api_prefix: str = "/api"
    app_env: str = "production"
    host: str = "0.0.0.0"
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
    cors_origins: str = "*"  # Virgülle ayrılmış origin listesi
    allowed_hosts: str = "localhost,127.0.0.1,lumoraboutique.com,www.lumoraboutique.com"  # TrustedHost middleware için
    
    # Connection limits (DoS protection)
    max_connections: int = 200
    connection_timeout: int = 5

    # AI API Keys (zorunlu - .env dosyasından alınmalı)
    openai_api_key: str = ""
    tavily_api_key: str = ""
    serpapi_api_key: str = ""  # Google Trends için
    fal_api_key: str = ""
    fal_base_url: str = "https://fal.run"
    fal_model_path: str = "fal-ai/flux/dev"

    @property
    def allowed_origins(self) -> list[str]:
        """CORS için izin verilen origin'leri döndürür."""
        if self.cors_origins == "*":
            return ["*"]
        if self.cors_origins:
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return [self.frontend_url]


settings = Settings()

