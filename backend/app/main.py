"""App factories.

API only: uv run uvicorn app.main:create_app --factory --reload
API at /api plus the built frontend at /: uv run uvicorn app.main:create_site --factory
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base, make_engine
from app.errors import install_error_handlers
from app.routers import auth, backgrounds, files, items, jobs, outfits, profile
from app.seed import seed
from app.storage import make_storage
from app.web import SinglePageApp


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.check()

    engine = make_engine(settings.database_url)
    # v1 creates tables on startup. Add Alembic migrations before the schema needs to change
    # under real data.
    Base.metadata.create_all(engine)
    make_session = sessionmaker(engine, expire_on_commit=False)
    storage = make_storage(settings)
    with make_session() as db:
        seed(db, storage)

    app = FastAPI(title="Virtual Try-On API", version="1.0.0")
    app.state.settings = settings
    app.state.sessionmaker = make_session
    app.state.storage = storage

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )
    install_error_handlers(app)
    for module in (auth, profile, backgrounds, items, outfits, jobs, files):
        app.include_router(module.router)
    return app


def create_site(settings: Settings | None = None) -> FastAPI:
    """The API under /api and, when TRYON_FRONTEND_DIR is set, the frontend at /.

    Set TRYON_PUBLIC_BASE_URL to end in /api so signed image URLs point at the API.
    """
    settings = settings or Settings()
    site = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    site.mount("/api", create_app(settings))
    if settings.frontend_dir:
        site.mount("/", SinglePageApp(settings.frontend_dir))
    return site
