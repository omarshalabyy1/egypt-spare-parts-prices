"""Checks for load_config: the car comes from config/client.yaml unless the environment variable
CAR_KEY is set, and a missing key stops with one line. No network and no warehouse are used."""

import pytest

import config


@pytest.fixture
def client_yaml(tmp_path, monkeypatch):
    """Write a copy of the demo config/client.yaml under tmp_path, with one line replaced."""
    demo = (config.ROOT / "config" / "client.yaml").read_text(encoding="utf-8")
    (tmp_path / "config").mkdir()
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.delenv("CAR_KEY", raising=False)

    def write(old, new):
        assert demo.count(old) == 1
        (tmp_path / "config" / "client.yaml").write_text(demo.replace(old, new), encoding="utf-8")
    return write


def test_car_key_from_the_file_unless_the_environment_sets_it(client_yaml, monkeypatch):
    client_yaml("car_key: null", "car_key: null")
    assert config.load_config()["car_key"] is None  # the demo: all cars
    client_yaml("car_key: null", "car_key: hyundai")
    assert config.load_config()["car_key"] == "hyundai"
    monkeypatch.setenv("CAR_KEY", "kia-rio")
    assert config.load_config()["car_key"] == "kia-rio"  # the environment wins
    monkeypatch.setenv("CAR_KEY", "")
    assert config.load_config()["car_key"] == "hyundai"  # empty is not set


def test_a_missing_key_stops_with_one_line(client_yaml):
    client_yaml("  undercut_pct: 5", "  other: 5")
    with pytest.raises(SystemExit, match="config/client.yaml is missing rules.undercut_pct"):
        config.load_config()
