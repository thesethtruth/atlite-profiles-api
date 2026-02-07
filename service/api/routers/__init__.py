from service.api.routers.generate import router as generate_router
from service.api.routers.health import router as health_router
from service.api.routers.solar import router as solar_router
from service.api.routers.turbines import router as turbines_router

__all__ = [
    "generate_router",
    "health_router",
    "solar_router",
    "turbines_router",
]
