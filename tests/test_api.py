from fastapi.testclient import TestClient

from core.models import (
    CutoutCatalogEntry,
    CutoutDefinition,
    CutoutInspectResponse,
    CutoutPrepareConfig,
)
from service import api
from service.api.catalog import CatalogSnapshot, apply_catalog_snapshot
from service.api.routers import cutouts as cutouts_router
from service.api.routers import generate as generate_router
from service.api.routers import solar as solar_router
from service.api.routers import turbines as turbines_router

client = TestClient(api.app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_turbines_endpoint(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=["X", "Y"],
            available_solar_technologies=[],
        ),
    )

    response = client.get("/turbines")

    assert response.status_code == 200
    assert response.json() == {"items": ["X", "Y"]}


def test_solar_technologies_endpoint(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=["CSi", "CdTe"],
        ),
    )

    response = client.get("/solar-technologies")

    assert response.status_code == 200
    assert response.json() == {"items": ["CSi", "CdTe"]}


def test_cutouts_endpoint(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=[],
            available_cutouts=["a.nc", "b.nc"],
        ),
    )

    response = client.get("/cutouts")

    assert response.status_code == 200
    assert response.json() == {"items": ["a.nc", "b.nc"]}


def test_cutout_inspect_endpoint(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=[],
            available_cutouts=["a.nc"],
            cutout_entries=[CutoutCatalogEntry(name="a.nc", path="/tmp/a.nc")],
        ),
    )
    monkeypatch.setattr(
        cutouts_router,
        "inspect_cutout_metadata",
        lambda _path, *, name: CutoutInspectResponse(
            filename=name,
            path="/tmp/a.nc",
            cutout=CutoutDefinition(
                module="era5",
                x=[1.0, 2.0],
                y=[3.0, 4.0],
                dx=0.25,
                dy=0.25,
                time="2024",
            ),
            prepare=CutoutPrepareConfig(features=["height", "wind"]),
            inferred=True,
        ),
    )

    response = client.get("/cutouts/a.nc")

    assert response.status_code == 200
    assert response.json()["filename"] == "a.nc"
    assert response.json()["cutout"]["dx"] == 0.25
    assert response.json()["prepare"]["features"] == ["height", "wind"]


def test_cutout_inspect_endpoint_not_found(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=[],
            available_cutouts=[],
            cutout_entries=[],
        ),
    )

    response = client.get("/cutouts/missing.nc")

    assert response.status_code == 404
    assert response.json()["detail"] == "Cutout 'missing.nc' was not found."


def test_generate_endpoint(monkeypatch):
    captured: dict[str, object] = {}
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=[],
            available_cutouts=["europe-2024-era5.nc"],
            cutout_entries=[
                CutoutCatalogEntry(
                    name="europe-2024-era5.nc",
                    path="/data/europe-2024-era5.nc",
                )
            ],
        ),
    )

    def fake_run_profiles(**kwargs):
        captured.update(kwargs)
        return {
            "status": "ok",
            "profile_type": "both",
            "wind_profiles": 1,
            "solar_profiles": 1,
            "output_dir": "output",
        }

    monkeypatch.setattr(generate_router, "run_profiles", fake_run_profiles)

    payload = {
        "profile_type": "both",
        "latitude": 52.0,
        "longitude": 5.0,
        "base_path": ".",
        "output_dir": "output",
        "cutouts": ["europe-2024-era5.nc"],
        "turbine_model": "ModelA",
        "turbine_config": {
            "name": "API_Custom",
            "hub_height_m": 120,
            "wind_speeds": [0, 10, 20],
            "power_curve_mw": [0, 2, 4],
        },
        "slopes": [30.0],
        "azimuths": [180.0],
        "panel_model": "CSi",
        "solar_technology_config": {
            "model": "huld",
            "name": "API_Solar",
            "efficiency": 0.1,
            "c_temp_amb": 1.0,
            "c_temp_irrad": 0.035,
            "r_tamb": 293.0,
            "r_tmod": 298.0,
            "r_irradiance": 1000.0,
            "k_1": -0.017162,
            "k_2": -0.040289,
            "k_3": -0.004681,
            "k_4": 0.000148,
            "k_5": 0.000169,
            "k_6": 0.000005,
            "inverter_efficiency": 0.9,
        },
        "visualize": False,
    }
    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert captured["cutouts"] == ["/data/europe-2024-era5.nc"]
    assert captured["turbine_config"]["name"] == "API_Custom"
    assert captured["solar_technology_config"]["name"] == "API_Solar"
    assert captured["solar_technology_config"]["model"] == "huld"


def test_generate_endpoint_unknown_cutout_rejected(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=[],
            available_cutouts=["known.nc"],
        ),
    )

    payload = {
        "profile_type": "both",
        "latitude": 52.0,
        "longitude": 5.0,
        "base_path": ".",
        "output_dir": "output",
        "cutouts": ["unknown.nc"],
        "turbine_model": "ModelA",
        "slopes": [30.0],
        "azimuths": [180.0],
        "panel_model": "CSi",
        "visualize": False,
    }
    response = client.post("/generate", json=payload)

    assert response.status_code == 422
    assert "Unknown cutout(s): unknown.nc." in response.json()["detail"]


def test_generate_endpoint_out_of_bounds_rejected(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=[],
            available_cutouts=["known.nc"],
            cutout_metadata={
                "known.nc": CutoutInspectResponse(
                    filename="known.nc",
                    path="/tmp/known.nc",
                    cutout=CutoutDefinition(
                        module="era5",
                        x=[1.0, 2.0],
                        y=[3.0, 4.0],
                        time="2024",
                    ),
                    prepare=CutoutPrepareConfig(features=["wind"]),
                    inferred=True,
                )
            },
        ),
    )

    payload = {
        "profile_type": "both",
        "latitude": 10.0,
        "longitude": 10.0,
        "base_path": ".",
        "output_dir": "output",
        "cutouts": ["known.nc"],
        "turbine_model": "ModelA",
        "slopes": [30.0],
        "azimuths": [180.0],
        "panel_model": "CSi",
        "visualize": False,
    }
    response = client.post("/generate", json=payload)

    assert response.status_code == 422
    assert "outside cutout bounds" in response.json()["detail"]
    assert "known.nc" in response.json()["detail"]


def test_turbine_inspect_endpoint(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=["ModelA"],
            available_solar_technologies=[],
        ),
    )
    monkeypatch.setattr(
        turbines_router,
        "inspect_turbine",
        lambda name: {
            "status": "ok",
            "turbine": name,
            "metadata": {
                "name": name,
                "manufacturer": "unknown",
                "source": "custom",
                "provider": "custom",
                "hub_height_m": 120.0,
                "rated_power_mw": 5.0,
                "definition_file": "config/wind/ModelA.yaml",
            },
            "curve": [{"speed": 0.0, "power_mw": 0.0}],
            "curve_summary": {"point_count": 1, "speed_min": 0.0, "speed_max": 0.0},
        },
    )

    response = client.get("/turbines/ModelA")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["turbine"] == "ModelA"


def test_turbine_inspect_endpoint_not_found(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=["missing"],
            available_solar_technologies=[],
        ),
    )

    def fake_inspect(_name: str):
        raise ValueError("Turbine 'missing' was not found.")

    monkeypatch.setattr(turbines_router, "inspect_turbine", fake_inspect)

    response = client.get("/turbines/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Turbine 'missing' was not found."


def test_solar_technology_inspect_endpoint(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=["CSi"],
        ),
    )
    monkeypatch.setattr(
        solar_router,
        "inspect_solar_technology",
        lambda name: {
            "status": "ok",
            "technology": name,
            "metadata": {
                "name": name,
                "manufacturer": "unknown",
                "source": "custom",
                "provider": "custom",
                "definition_file": "config/solar/CSi.yaml",
            },
            "parameters": {},
        },
    )

    response = client.get("/solar-technologies/CSi")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["technology"] == "CSi"


def test_solar_technology_inspect_endpoint_not_found(monkeypatch):
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=[],
            available_solar_technologies=["missing"],
        ),
    )

    def fake_inspect(_name: str):
        raise ValueError("Solar technology 'missing' was not found.")

    monkeypatch.setattr(solar_router, "inspect_solar_technology", fake_inspect)

    response = client.get("/solar-technologies/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Solar technology 'missing' was not found."


def test_generate_endpoint_invalid_turbine_config():
    payload = {
        "profile_type": "wind",
        "latitude": 52.0,
        "longitude": 5.0,
        "base_path": ".",
        "output_dir": "output",
        "cutouts": ["europe-2024-era5.nc"],
        "turbine_model": "ModelA",
        "turbine_config": {
            "name": "Broken",
            "hub_height_m": 120,
            "wind_speeds": [0, 10, 20],
            "power_curve_mw": [0, 4],
        },
        "slopes": [30.0],
        "azimuths": [180.0],
        "panel_model": "CSi",
        "visualize": False,
    }

    response = client.post("/generate", json=payload)

    assert response.status_code == 422


def test_docs_uses_api_prefixed_openapi_url():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "url: '/api/openapi.json'" in response.text


def test_openapi_contains_enum_for_inspect_path_params():
    apply_catalog_snapshot(
        api.app,
        CatalogSnapshot(
            available_turbines=["T1", "T2"],
            available_solar_technologies=["CSi", "CdTe"],
            available_cutouts=["c1.nc", "c2.nc"],
        ),
    )
    api.app.openapi_schema = None

    schema = client.get("/openapi.json").json()
    turbine_params = schema["paths"]["/turbines/{turbine_model}"]["get"]["parameters"]
    solar_params = schema["paths"]["/solar-technologies/{technology}"]["get"][
        "parameters"
    ]

    turbine_enum = next(
        p["schema"]["enum"] for p in turbine_params if p["name"] == "turbine_model"
    )
    solar_enum = next(
        p["schema"]["enum"] for p in solar_params if p["name"] == "technology"
    )
    cutout_enum = schema["components"]["schemas"]["GenerateRequest"]["properties"][
        "cutouts"
    ]["items"]["enum"]

    assert turbine_enum == ["T1", "T2"]
    assert solar_enum == ["CSi", "CdTe"]
    assert cutout_enum == ["c1.nc", "c2.nc"]


def test_openapi_declares_api_root_path_server():
    api.app.openapi_schema = None

    schema = client.get("/openapi.json").json()

    assert schema["servers"] == [{"url": "/api"}]
