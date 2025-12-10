from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env.local",
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

    # AI API Keys (opsiyonel - yoksa AI özellikleri çalışmaz)
    openai_api_key: str = "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"
    tavily_api_key: str = "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"
    fal_api_key: str = "68a9e3a1-59b0-4df4-8c4e-cfce378a2641:535db392c23ce433b7002e71a920c69c"
    fal_base_url: str = "https://fal.run"  # Yeni fal.run taban URL
    fal_model_path: str = "fal-ai/flux/dev"  # Model yolu (fal_client ile birebir)
    
    # Tavily Ayarları - Tutarlılık için
    tavily_min_score: float = 0.75  # Minimum Tavily score (0.0-1.0) - Güvenilirlik filtresi
    tavily_allowed_domains: str = "trendyol.com,hepsiburada.com,n11.com,gittigidiyor.com,amazon.com,amazon.com.tr,zara.com,mango.com,hm.com,lcwaikiki.com,modanisa.com,vakko.com,beymen.com,defacto.com,koton.com,mavi.com,bershka.com,pullandbear.com,stradivarius.com,massimodutti.com,oysho.com,zarahome.com"  # Virgülle ayrılmış domain listesi (boşsa tüm siteler)
    tavily_include_answer: bool = True  # Tavily'in özet cevabını dahil et
    tavily_include_raw_content: bool = False  # Ham içerik dahil et (daha fazla veri, daha yavaş)
    tavily_max_retries: int = 2  # Başarısız sorgular için retry sayısı

    @property
    def tavily_domains_list(self) -> list[str]:
        """Tavily için izin verilen domain'leri döndürür."""
        if self.tavily_allowed_domains:
            return [domain.strip() for domain in self.tavily_allowed_domains.split(",") if domain.strip()]
        return []  # Boşsa tüm siteler

    @property
    def allowed_origins(self) -> list[str]:
        """CORS için izin verilen origin'leri döndürür."""
        if self.cors_origins:
            return [origin.strip() for origin in self.cors_origins.split(",")]
        return [self.frontend_url]


settings = Settings()

