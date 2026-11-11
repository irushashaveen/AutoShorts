import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.config import settings
from app.models import init_db
from app.web.router import router as web_router
from app.web.auth_router import auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("autoshorts")

app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous TikTok to YouTube Shorts Curation & Publishing System",
    version="0.1.0"
)

# Initialize database schema tables
init_db()

# Mount authentication and user administration router
app.include_router(auth_router)

# Mount web dashboard router
app.include_router(web_router)

# Mount static files directory if present
static_dir = Path(__file__).parent / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

logger.info(f"{settings.APP_NAME} initialized successfully. Running in {settings.APP_ENV} mode.")

