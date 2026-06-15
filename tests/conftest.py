"""Shared pytest fixtures for Goop Launcher tests.

The most important one is a fake DXVK tarball builder, so test_wine can exercise
install_dxvk without hitting the network.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest


@pytest.fixture
def fake_dxvk_tarball(tmp_path: Path) -> Path:
    """Build a minimal DXVK-shaped tarball with the 4 expected x64 DLLs."""
    tarball = tmp_path / f"dxvk-fake.tar.gz"
    dll_names = ["d3d9.dll", "d3d10core.dll", "d3d11.dll", "dxgi.dll"]
    with tarfile.open(tarball, "w:gz") as tar:
        for name in dll_names:
            payload = b"\x4d\x5a" + b"\x00" * 2048  # MZ header + padding
            info = tarfile.TarInfo(name=f"dxvk-fake/x64/{name}")
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return tarball
