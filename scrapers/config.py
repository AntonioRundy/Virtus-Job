from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScraperSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Database ───────────────────────────────────────
    DATABASE_URL: str  # Obrigatório — definir em .env (sem default para evitar credenciais hardcoded)

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_database_url(cls, v: str) -> str:
        # Render fornece postgres:// — SQLAlchemy async precisa de postgresql+asyncpg://
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # ─── AI ─────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # AI model to use for extraction
    AI_MODEL: str = "claude-haiku-4-5-20251001"  # Fast + cheap for extraction
    AI_FALLBACK_MODEL: str = "claude-sonnet-4-6"  # For complex/ambiguous content
    AI_MAX_TOKENS: int = 1024
    AI_TEMPERATURE: float = 0.1             # Low — deterministic extraction

    # ─── HTTP Client ────────────────────────────────────
    HTTP_TIMEOUT: int = 30                  # seconds
    HTTP_MAX_RETRIES: int = 3
    HTTP_RETRY_WAIT_MIN: float = 2.0        # seconds (exponential backoff base)
    HTTP_RETRY_WAIT_MAX: float = 30.0

    # Polite rate limiting — respect source servers
    REQUEST_DELAY_MIN: float = 2.0          # min seconds between requests
    REQUEST_DELAY_MAX: float = 5.0          # max seconds between requests

    HTTP_USER_AGENT: str = (
        "Mozilla/5.0 (compatible; VirtusJobBot/1.0; "
        "+https://virtusjob.ao/bot; contact@virtusjob.ao)"
    )

    # ─── AI Pipeline ────────────────────────────────────
    AI_CONFIDENCE_THRESHOLD: float = 0.6    # below this → requires_review = True
    MAX_CONTENT_LENGTH: int = 8000          # chars sent to AI (cost control)
    MIN_CONTENT_LENGTH: int = 100           # skip pages with too little content

    # ─── Scraper Behaviour ──────────────────────────────
    MAX_PAGES_PER_SOURCE: int = 10          # pagination limit per run
    MAX_ITEMS_PER_SOURCE: int = 50          # items limit per run
    DRY_RUN: bool = False                   # if True, don't save to DB

    # ─── Playwright ─────────────────────────────────────
    BROWSER_HEADLESS: bool = True
    BROWSER_TIMEOUT: int = 30000            # ms

    # ─── Jornal de Angola — credenciais do assinante ─────
    # NUNCA commitar. Definir em .env local.
    JDA_EMAIL: str = ""
    JDA_PASSWORD: str = ""
    JDA_BASE_URL: str = "https://jornaldeangola.ao"
    JDA_SESSION_FILE: str = "scrapers/sessions/jda_session.json"
    JDA_LOGIN_URL: str = "https://jornaldeangola.ao/login"
    # Selectores CSS — ajustar se o site mudar estrutura
    JDA_EMAIL_SELECTOR: str = "input[type='email'], input[name='email'], #email, #username"
    JDA_PASSWORD_SELECTOR: str = "input[type='password'], input[name='password'], #password"
    JDA_SUBMIT_SELECTOR: str = "button[type='submit'], input[type='submit'], .login-submit"
    JDA_SESSION_VALID_INDICATOR: str = ".logged-in, .subscriber, .user-menu, .logout, [data-user]"


@lru_cache
def get_scraper_settings() -> ScraperSettings:
    return ScraperSettings()


settings = get_scraper_settings()
