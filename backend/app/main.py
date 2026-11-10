from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.application.errors import BusinessRuleError, NotFoundError, StorageLimitError
from app.config import get_settings
from app.interface.api import admin, claims, dev_sso, found_items, health, lost_reports, me, reports
from app.interface.lifespan import lifespan

# Ошибки прикладного слоя -> HTTP-коды, в одном месте для всех роутеров
ERROR_STATUS = {NotFoundError: 404, BusinessRuleError: 409, StorageLimitError: 507}


async def _app_error(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=ERROR_STATUS[type(exc)], content={"detail": str(exc)})


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(admin.router)
    app.include_router(reports.router)
    app.include_router(lost_reports.router)
    app.include_router(found_items.router)
    app.include_router(claims.router)
    for error in ERROR_STATUS:
        app.add_exception_handler(error, _app_error)
    if settings.environment == "local":
        app.include_router(dev_sso.router)
    return app


app = create_app()
