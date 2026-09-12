from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import Settings, get_settings
from .db import ensure_indexes, get_client
from .middleware import add_security_headers, limiter
from .routers import admin_catalog, admin_devices, admin_orders, auth, sync


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = get_client(settings.mongo_uri)
        app.state.settings = settings
        app.state.db = client[settings.mongo_db]
        await ensure_indexes(app.state.db)
        yield
        client.close()

    app = FastAPI(title="Festival Sales API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # explicit allowlist, never "*"
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    add_security_headers(app)

    app.include_router(auth.router)
    app.include_router(admin_devices.router)
    app.include_router(admin_orders.router)
    app.include_router(admin_catalog.router)
    app.include_router(sync.router)

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "ok"}

    return app
