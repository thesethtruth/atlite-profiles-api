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


def test_generate_endpoint(monkeypatch):
    monkeypatch.setattr(
        api,
        "run_profiles",
        lambda **kwargs: {"status": "ok", "wind_profiles": 1, "solar_profiles": 1},
    )

    payload = {
        "profile_type": "both",
        "latitude": 52.0,
        "longitude": 5.0,
        "base_path": ".",
        "output_dir": "output",
        "cutouts": ["europe-2024-era5.nc"],
        "turbine_model": "ModelA",
        "slopes": [30.0],
        "azimuths": [180.0],
        "panel_model": "CSi",
        "visualize": False,
    }
    response = client.post("/generate", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
