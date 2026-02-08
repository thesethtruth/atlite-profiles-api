from service.api.catalog import load_catalog_snapshot


def test_load_catalog_snapshot_discovers_cutouts_from_sources(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "a.nc").write_text("x", encoding="utf-8")
    (data_dir / "b.txt").write_text("x", encoding="utf-8")

    nested_dir = tmp_path / "nested"
    nested_dir.mkdir()
    (nested_dir / "c.nc").write_text("x", encoding="utf-8")

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "api.yaml").write_text(
        ("cutout_sources:\n  - data\n  - nested/*.nc\n"),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "service.api.catalog.get_available_turbines",
        lambda: ["T1"],
    )
    monkeypatch.setattr(
        "service.api.catalog.get_available_solar_technologies",
        lambda: ["S1"],
    )

    snapshot = load_catalog_snapshot()

    assert snapshot.available_turbines == ["T1"]
    assert snapshot.available_solar_technologies == ["S1"]
    assert snapshot.available_cutouts == ["a.nc", "c.nc"]


def test_load_catalog_snapshot_handles_missing_api_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "service.api.catalog.get_available_turbines",
        lambda: [],
    )
    monkeypatch.setattr(
        "service.api.catalog.get_available_solar_technologies",
        lambda: [],
    )

    snapshot = load_catalog_snapshot()

    assert snapshot.available_cutouts == []
