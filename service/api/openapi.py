from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from service.api.catalog import get_catalog_snapshot


def _set_openapi_path_param_enum(
    openapi_schema: dict[str, Any],
    *,
    path: str,
    method: str,
    parameter_name: str,
    values: list[str],
) -> None:
    path_item = openapi_schema.get("paths", {}).get(path, {})
    operation = path_item.get(method.lower(), {})
    for parameter in operation.get("parameters", []):
        if parameter.get("name") == parameter_name:
            parameter.setdefault("schema", {})["enum"] = values


def _set_generate_cutouts_enum(
    openapi_schema: dict[str, Any],
    *,
    schema_name: str,
    values: list[str],
) -> None:
    components = openapi_schema.get("components", {})
    schemas = components.get("schemas", {})
    schema = schemas.get(schema_name, {})
    properties = schema.get("properties", {})
    cutouts = properties.get("cutouts", {})
    items = cutouts.setdefault("items", {})
    items["enum"] = values
    if values:
        cutouts["default"] = [values[0]]


def configure_openapi_dynamic_enums(app: FastAPI) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
            description=app.description,
        )

        catalog = get_catalog_snapshot(app)
        _set_openapi_path_param_enum(
            openapi_schema,
            path="/turbines/{turbine_model}",
            method="get",
            parameter_name="turbine_model",
            values=list(catalog.available_turbines),
        )
        _set_openapi_path_param_enum(
            openapi_schema,
            path="/solar-technologies/{technology}",
            method="get",
            parameter_name="technology",
            values=list(catalog.available_solar_technologies),
        )
        _set_generate_cutouts_enum(
            openapi_schema,
            schema_name="GenerateRequest",
            values=list(catalog.available_cutouts),
        )

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi
