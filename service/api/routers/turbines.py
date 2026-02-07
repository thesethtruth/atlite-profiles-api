from fastapi import APIRouter, HTTPException, Request

from service.api.catalog import get_catalog_snapshot
from service.runner import inspect_turbine

router = APIRouter(tags=["Wind"])


@router.get("/turbines")
def list_turbines(request: Request) -> dict[str, list[str]]:
    catalog = get_catalog_snapshot(request.app)
    return {"items": list(catalog.available_turbines)}


@router.get("/turbines/{turbine_model}")
def turbine_inspect(turbine_model: str, request: Request) -> dict[str, object]:
    catalog = get_catalog_snapshot(request.app)
    if turbine_model not in catalog.available_turbines:
        raise HTTPException(
            status_code=404,
            detail=f"Turbine '{turbine_model}' was not found.",
        )

    try:
        return inspect_turbine(turbine_model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
