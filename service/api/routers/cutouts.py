from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from core.models import CutoutInspectResponse, ListItemsResponse
from service.api.catalog import get_catalog_snapshot
from service.api.cutout_metadata import inspect_cutout_metadata

router = APIRouter(tags=["Cutouts"])


@router.get("/cutouts")
def list_cutouts(request: Request) -> ListItemsResponse:
    catalog = get_catalog_snapshot(request.app)
    return ListItemsResponse(items=list(catalog.available_cutouts))


@router.get("/cutouts/{cutout_name}")
def inspect_cutout(cutout_name: str, request: Request) -> CutoutInspectResponse:
    catalog = get_catalog_snapshot(request.app)
    entry = next(
        (item for item in catalog.cutout_entries if item.name == cutout_name),
        None,
    )
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"Cutout '{cutout_name}' was not found.",
        )

    try:
        return inspect_cutout_metadata(Path(entry.path), name=cutout_name)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to inspect cutout '{cutout_name}': {exc}",
        ) from exc
