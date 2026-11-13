"""App factory. Run with: uv run uvicorn app.main:create_app --factory --reload"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base, make_engine
from app.errors import install_error_handlers
from app.routers import auth, backgrounds, files, items, jobs, outfits, profile
from app.seed import seed
from app.storage import LocalStorage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.check()

    engine = make_engine(settings.database_url)
    # v1 creates tables on startup. Add Alembic migrations before the schema needs to change
    # under real data.
    Base.metadata.create_all(engine)
    make_session = sessionmaker(engine, expire_on_commit=False)
    storage = LocalStorage(
        settings.storage_dir,
        settings.secret_key,
        settings.public_base_url,
        settings.file_url_ttl_seconds,
    )
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
