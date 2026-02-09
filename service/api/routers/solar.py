from fastapi import APIRouter, HTTPException, Request

from core.models import ListItemsResponse, SolarInspectResponse
from service.api.catalog import get_catalog_snapshot
from service.runner import inspect_solar_technology

router = APIRouter(tags=["Solar"])


@router.get("/solar-technologies")
def list_solar_technologies(request: Request) -> ListItemsResponse:
    catalog = get_catalog_snapshot(request.app)
    return ListItemsResponse(items=list(catalog.available_solar_technologies))


@router.get("/solar-technologies/{technology}")
def solar_technology_inspect(technology: str, request: Request) -> SolarInspectResponse:
    catalog = get_catalog_snapshot(request.app)
    if technology not in catalog.available_solar_technologies:
        raise HTTPException(
            status_code=404,
            detail=f"Solar technology '{technology}' was not found.",
        )

    try:
        return inspect_solar_technology(technology)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
