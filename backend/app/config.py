from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "AEGIS"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = (
        "Autonomous Enterprise Global Intelligence System"
    )

    API_PREFIX: str = "/api"

    DEBUG: bool = False

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    SECRET_KEY: str = "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY"
    # Used ONCE on first startup to create the initial admin API key, if
    # no admin key exists yet. After that, manage keys via issue_api_key()
    # / the api_keys table - this is a bootstrap value, not an ongoing
    # shared secret (see security.py for why a shared key model was
    # replaced with per-account keys).
    ADMIN_BOOTSTRAP_KEY: str = ""
    # Base64-encoded 32-byte key used to encrypt broker credentials at rest.
    AEGIS_MASTER_KEY: str = ""

    # CORS - comma-separated list of allowed origins. "*" is rejected
    # automatically when credentials are required (see main.py).
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    # Public URL where client_portal is actually served - used to build
    # payment provider redirect URLs (success/cancel/callback). Must be
    # set for real checkouts to land somewhere real instead of the
    # placeholder domain this defaulted to.
    PORTAL_BASE_URL: str = "http://localhost:8000/portal"

    DATABASE_URL: str = "postgresql://postgres:postgres@postgres:5432/aegis"
    REDIS_URL: str = "redis://redis:6379/0"

    # Worker pool
    WORKER_IDLE_TIMEOUT_SECONDS: int = 900       # auto-disconnect idle MT5 sessions
    WORKER_JOB_TIMEOUT_SECONDS: int = 30         # how long the API waits for a job result
    MAX_CONCURRENT_WORKERS: int = 10             # cap while testing with a small account set

    # Payment providers
    PAYSTACK_SECRET_KEY: str = ""
    FLUTTERWAVE_SECRET_KEY: str = ""
    FLUTTERWAVE_WEBHOOK_HASH: str = ""           # the "verif-hash" value you set in the Flutterwave dashboard
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Subscription enforcement
    SUBSCRIPTION_GRACE_PERIOD_DAYS: int = 5
    SUBSCRIPTION_SWEEP_INTERVAL_SECONDS: int = 300   # how often the background job checks for lapsed subs
    APK_FILE_PATH: str = "release/aegis-mobile.apk"
    DOWNLOAD_TOKEN_TTL_SECONDS: int = 3600

    # Tracing
    TRACING_ENABLED: bool = False   # off by default - enable once Tempo is actually running (see docker-compose.yml)
    OTLP_ENDPOINT: str = "tempo:4317"

    class Config:
        env_file = ".env"


settings = Settings()


def get_allowed_origins() -> list[str]:
    return [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
