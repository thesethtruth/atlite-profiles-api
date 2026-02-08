from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from service.api.catalog import (
    CatalogSnapshot,
    apply_catalog_snapshot,
    load_catalog_snapshot,
)
from service.api.openapi import configure_openapi_dynamic_enums
from service.api.routers import (
    cutouts_router,
    generate_router,
    health_router,
    solar_router,
    turbines_router,
)
from service.logging_utils import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    apply_catalog_snapshot(app_instance, load_catalog_snapshot())
    configure_openapi_dynamic_enums(app_instance)
    app_instance.openapi_schema = None
    yield


app = FastAPI(
    title="Renewables Profiles API",
    version="0.1.0",
    root_path="/api",
    lifespan=lifespan,
)

# Initial defaults before startup events run.
apply_catalog_snapshot(app, CatalogSnapshot())
configure_openapi_dynamic_enums(app)

app.include_router(health_router)
app.include_router(cutouts_router)
app.include_router(turbines_router)
app.include_router(solar_router)
app.include_router(generate_router)


def serve() -> None:
    import uvicorn

    uvicorn.run("service.api:app", host="0.0.0.0", port=8000, reload=False)
