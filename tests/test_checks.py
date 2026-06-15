"""Tests for the system guard probes in goop_launcher.checks.

Every probe takes an injectable ``runner`` so we can simulate a healthy and a
broken machine without needing real lspci / nvidia-smi / vulkaninfo binaries.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from goop_launcher import checks, config


# ── Runner helpers ───────────────────────────────────────────────────────────

class FakeFS:
    """Stubs shutil.which for chosen commands."""

    def __init__(self, available: set[str]) -> None:
        self._available = available
        self._orig = shutil.which

    def __enter__(self):
        shutil.which = lambda cmd: "/usr/bin/" + cmd if cmd in self._available else None
        return self

    def __exit__(self, *exc):
        shutil.which = self._orig


def runner_from(table: dict[tuple[str, ...], tuple[int, str, str]]):
    """Build a runner that looks up commands by their argv tuple."""
    def _run(cmd):
        return table.get(tuple(cmd), (127, "", f"not found: {' '.join(cmd)}"))
    return _run


# ── Diagnostics bundle ───────────────────────────────────────────────────────

def test_diagnostics_launchable_when_all_pass():
    d = checks.Diagnostics()
    d.add(checks.Check("a", True, "ok"))
    assert d.launchable and not d.blockers


def test_diagnostics_blocked_when_blocker_fails():
    d = checks.Diagnostics()
    d.add(checks.Check("a", False, "nope", severity="blocker"))
    d.add(checks.Check("b", True, "ok"))
    assert not d.launchable
    assert len(d.blockers) == 1


def test_diagnostics_warning_does_not_block():
    d = checks.Diagnostics()
    d.add(checks.Check("a", False, "warn", severity="warning"))
    assert d.launchable  # warnings don't block
    assert len(d.warnings) == 1


# ── Arch + kernel (deterministic, no runner needed) ──────────────────────────

def test_check_arch_passes_on_x86_64(monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    assert checks.check_arch().ok


def test_check_arch_fails_on_arm(monkeypatch):
    monkeypatch.setattr("platform.machine", lambda: "aarch64")
    c = checks.check_arch()
    assert not c.ok and "aarch64" in c.message


def test_check_kernel_accepts_modern(monkeypatch):
    monkeypatch.setattr("platform.release", lambda: "6.8.0-41-generic")
    assert checks.check_kernel().ok


def test_check_kernel_rejects_ancient(monkeypatch):
    monkeypatch.setattr("platform.release", lambda: "4.15.0-1-generic")
    assert not checks.check_kernel().ok


# ── nvidia-smi driver version parsing ───────────────────────────────────────

def test_check_nvidia_driver_passes_on_recent():
    with FakeFS({"nvidia-smi"}):
        r = runner_from({("nvidia-smi", "--query-gpu=driver_version",
                          "--format=csv,noheader"): (0, "550.120\n", "")})
        c = checks.check_nvidia_driver(r)
        assert c.ok and "550" in c.message


def test_check_nvidia_driver_fails_on_old():
    with FakeFS({"nvidia-smi"}):
        r = runner_from({("nvidia-smi", "--query-gpu=driver_version",
                          "--format=csv,noheader"): (0, "525.85\n", "")})
        c = checks.check_nvidia_driver(r)
        assert not c.ok and "below" in c.message


def test_check_nvidia_driver_blocks_when_missing():
    with FakeFS(set()):
        c = checks.check_nvidia_driver()
        assert not c.ok and c.severity == "blocker"


# ── Vulkan device probe ──────────────────────────────────────────────────────

_GOOD_VULKAN = """\
apiVersion = 1.3.280
deviceName = NVIDIA GeForce RTX 3060 Ti
deviceType = PHYSICAL_DEVICE_TYPE_DISCRETE_GPU
"""


def test_check_vulkan_device_passes_with_13_discrete():
    with FakeFS({"vulkaninfo"}):
        r = runner_from({("vulkaninfo", "--summary"): (0, _GOOD_VULKAN, "")})
        c = checks.check_vulkan_device(r)
        assert c.ok and "1.3" in c.message


def test_check_vulkan_device_fails_on_old_api():
    with FakeFS({"vulkaninfo"}):
        r = runner_from({("vulkaninfo", "--summary"):
                         (0, _GOOD_VULKAN.replace("1.3.280", "1.2.200"), "")})
        c = checks.check_vulkan_device(r)
        assert not c.ok and "below" in c.message


def test_check_vulkan_device_fails_without_gpu():
    with FakeFS({"vulkaninfo"}):
        r = runner_from({("vulkaninfo", "--summary"):
                         (0, "apiVersion = 1.3.0\n", "")})
        c = checks.check_vulkan_device(r)
        assert not c.ok and "No Vulkan-capable" in c.message


# ── NVIDIA GPU detection ─────────────────────────────────────────────────────

def test_check_nvidia_gpu_flags_target():
    with FakeFS({"lspci"}):
        r = runner_from({("lspci", "-nn"):
                         (0, "01:00.0 VGA compatible controller: NVIDIA "
                          "Corporation GA104 [GeForce RTX 3060 Ti]\n", "")})
        c = checks.check_nvidia_gpu(r)
        assert c.ok and config.TARGET_GPU in c.message


def test_check_nvidia_gpu_warns_on_amd():
    with FakeFS({"lspci"}):
        r = runner_from({("lspci", "-nn"):
                         (0, "01:00.0 VGA: Advanced Micro Devices Navi\n", "")})
        c = checks.check_nvidia_gpu(r)
        assert not c.ok and c.severity == "warning"  # AMD may still work


# ── run_all orchestration ────────────────────────────────────────────────────

def test_run_all_collects_every_probe(monkeypatch, tmp_path):
    """Stub the fs-dependent probes so run_all completes without real tools."""
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    monkeypatch.setattr("platform.release", lambda: "6.8.0-41-generic")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "goop")
    monkeypatch.setattr(checks, "_find_wine_binary", lambda: None)

    with FakeFS(set()):  # nothing installed → probes fail loudly
        d = checks.run_all()
    # We expect one Check per probe (8 probes).
    assert len(d.checks) == 8
    # Without tools staged, it must NOT be launchable.
    assert not d.launchable
