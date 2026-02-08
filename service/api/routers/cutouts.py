from fastapi import APIRouter, Request

from service.api.catalog import get_catalog_snapshot

router = APIRouter(tags=["Cutouts"])


@router.get("/cutouts")
def list_cutouts(request: Request) -> dict[str, list[str]]:
    catalog = get_catalog_snapshot(request.app)
    return {"items": list(catalog.available_cutouts)}
