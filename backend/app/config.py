"""All settings come from environment variables so the same code runs locally and on Render."""
import os


def _load_dotenv():
    """Read backend/.env for local runs (no extra library). Real environment variables win."""
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if not os.getenv("CC_SKIP_DOTENV"):
    _load_dotenv()


def _db_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./care_companion.db")
    # Neon/Render give postgres:// or postgresql:// ; SQLAlchemy needs the psycopg v3 driver name.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Settings:
    DATABASE_URL = _db_url()
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me-in-production")
    TOKEN_DAYS = int(os.getenv("TOKEN_DAYS", "90"))  # FR1.5: no periodic re-login for patients
    MEDIA_URL_SECONDS = int(os.getenv("MEDIA_URL_SECONDS", "3600"))

    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto")  # auto | gemini | offline
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    GEMINI_EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")
    GEMINI_MIN_SCORE = float(os.getenv("GEMINI_MIN_SCORE", "0.62"))

    GEOCODER = os.getenv("GEOCODER", "nominatim")  # nominatim | off
    PLACE_RADIUS_M = float(os.getenv("PLACE_RADIUS_M", "150"))
    NEARBY_RADIUS_M = float(os.getenv("NEARBY_RADIUS_M", "200"))

    DEMO_SEED = os.getenv("DEMO_SEED", "1") == "1"
    STATIC_DIR = os.getenv("STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
    MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "8"))


settings = Settings()
