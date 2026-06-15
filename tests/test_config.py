"""Tests for goop_launcher.config — the source of truth for pinned versions."""

from goop_launcher import config


def test_wine_version_is_pinned_to_119():
    assert config.WINE_VERSION == "11.9"


def test_wine_source_url_points_at_119_tarball():
    assert config.WINE_SOURCE_URL.endswith("wine-11.9.tar.xz")
    assert "11.x" in config.WINE_SOURCE_URL


def test_dxvk_url_points_at_github_release():
    assert config.DXVK_URL.startswith(
        "https://github.com/doitsujin/dxvk/releases/download/")
    assert config.DXVK_VERSION in config.DXVK_URL


def test_wine_env_has_dxvk_overrides():
    overrides = config.WINE_ENV_BASE["WINEDLLOVERRIDES"]
    for dll in ("d3d9", "d3d10core", "d3d11", "dxgi"):
        assert dll in overrides
    assert "native" in overrides


def test_prefix_and_data_dirs_are_under_goop():
    assert config.DATA_DIR.name == "goop"
    assert config.PREFIX_DIR.parent == config.DATA_DIR


def test_expected_wine_version_string():
    assert config.EXPECTED_WINE_VERSION == "wine-11.9"


def test_roblox_url_is_official_domain():
    assert config.ROBLOX_PLAYER_LAUNCHER_URL.startswith("https://roblox.com/")
