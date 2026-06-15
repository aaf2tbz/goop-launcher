"""Tests for goop_launcher.wine — prefix init and DXVK staging."""

from __future__ import annotations

import tarfile
from pathlib import Path

import pytest

from goop_launcher import config, wine


def test_find_wine_raises_when_unstaged(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "SYSTEM_WINE_DIR", tmp_path / "sys-wine")
    monkeypatch.setattr(config, "USER_WINE_DIR", tmp_path / "usr-wine")
    with pytest.raises(wine.WineError, match="not staged"):
        wine.find_wine()


def test_find_wine_prefers_system_staging(monkeypatch, tmp_path):
    sys = tmp_path / "sys-wine" / "bin"
    usr = tmp_path / "usr-wine" / "bin"
    sys.mkdir(parents=True)
    usr.mkdir(parents=True)
    (sys / "wine64").write_text("#!/bin/sh\n")
    (usr / "wine64").write_text("#!/bin/sh\n")
    monkeypatch.setattr(config, "SYSTEM_WINE_DIR", tmp_path / "sys-wine")
    monkeypatch.setattr(config, "USER_WINE_DIR", tmp_path / "usr-wine")
    found = wine.find_wine()
    assert found == sys / "wine64"


def test_install_dxvk_stages_four_dlls(monkeypatch, tmp_path, fake_dxvk_tarball):
    prefix = tmp_path / "prefix"
    system32 = prefix / "drive_c" / "windows" / "system32"
    monkeypatch.setattr(config, "PREFIX_DIR", prefix)

    wine.install_dxvk(fake_dxvk_tarball)

    for dll in ("d3d9.dll", "d3d10core.dll", "d3d11.dll", "dxgi.dll"):
        staged = system32 / dll
        assert staged.exists(), f"{dll} was not staged"
        assert staged.read_bytes().startswith(b"\x4d\x5a")  # MZ


def test_install_dxvk_rejects_incomplete_tarball(monkeypatch, tmp_path):
    """A tarball missing dxgi.dll must raise, not half-stage."""
    import io
    prefix = tmp_path / "prefix"
    monkeypatch.setattr(config, "PREFIX_DIR", prefix)
    bad = tmp_path / "bad.tar.gz"
    with tarfile.open(bad, "w:gz") as tar:
        info = tarfile.TarInfo(name="dxvk/x64/d3d9.dll")
        info.size = 2
        tar.addfile(info, io.BytesIO(b"\x4d\x5a"))
    with pytest.raises(wine.WineError, match="incomplete"):
        wine.install_dxvk(bad)


def test_verify_prefix_detects_missing_dxvk(monkeypatch, tmp_path):
    prefix = tmp_path / "prefix"
    monkeypatch.setattr(config, "PREFIX_DIR", prefix)
    # No system.reg, no DLLs.
    assert not wine.verify_prefix()


def test_verify_prefix_passes_when_complete(monkeypatch, tmp_path,
                                            fake_dxvk_tarball):
    prefix = tmp_path / "prefix"
    monkeypatch.setattr(config, "PREFIX_DIR", prefix)
    (prefix / "drive_c" / "windows" / "system32").mkdir(parents=True)
    (prefix / "system.reg").write_text("# stub\n")
    wine.install_dxvk(fake_dxvk_tarball)
    assert wine.verify_prefix()
