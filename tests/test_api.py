from fastapi.testclient import TestClient

from service import api

client = TestClient(api.app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_turbines_endpoint(monkeypatch):
    monkeypatch.setattr(api, "get_available_turbines", lambda: ["X", "Y"])

    response = client.get("/turbines")

    assert response.status_code == 200
    assert response.json() == {"items": ["X", "Y"]}


def test_solar_technologies_endpoint(monkeypatch):
    monkeypatch.setattr(
        api,
        "get_available_solar_technologies",
        lambda: ["CSi", "CdTe"],
    )

    response = client.get("/solar-technologies")

    assert response.status_code == 200
    assert response.json() == {"items": ["CSi", "CdTe"]}


def test_generate_endpoint(monkeypatch):
    captured: dict[str, object] = {}

    def fake_run_profiles(**kwargs):
        captured.update(kwargs)
        return {
            "status": "ok",
            "profile_type": "both",
            "wind_profiles": 1,
            "solar_profiles": 1,
            "output_dir": "output",
        }

    monkeypatch.setattr(
        api,
        "run_profiles",
        fake_run_profiles,
    )

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
    assert captured["turbine_config"]["name"] == "API_Custom"
    assert captured["solar_technology_config"]["name"] == "API_Solar"
    assert captured["solar_technology_config"]["model"] == "huld"


def test_turbine_inspect_endpoint(monkeypatch):
    monkeypatch.setattr(
        api,
        "inspect_turbine",
        lambda name: {"status": "ok", "turbine": name, "metadata": {}, "curve": []},
    )

    response = client.get("/turbines/ModelA")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["turbine"] == "ModelA"


def test_turbine_inspect_endpoint_not_found(monkeypatch):
    def fake_inspect(_name: str):
        raise ValueError("Turbine 'missing' was not found.")

    monkeypatch.setattr(api, "inspect_turbine", fake_inspect)

    response = client.get("/turbines/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Turbine 'missing' was not found."


def test_solar_technology_inspect_endpoint(monkeypatch):
    monkeypatch.setattr(
        api,
        "inspect_solar_technology",
        lambda name: {
            "status": "ok",
            "technology": name,
            "metadata": {},
            "parameters": {},
        },
    )

    response = client.get("/solar-technologies/CSi")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["technology"] == "CSi"


def test_solar_technology_inspect_endpoint_not_found(monkeypatch):
    def fake_inspect(_name: str):
        raise ValueError("Solar technology 'missing' was not found.")

    monkeypatch.setattr(api, "inspect_solar_technology", fake_inspect)

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
