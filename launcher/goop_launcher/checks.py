"""Realistic system guards for Goop Launcher.

Every probe returns a :class:`Check` (ok/fail + message). :class:`Diagnostics`
collects them and decides whether launch is safe. The probes shell out to real
tools (``lspci``, ``nvidia-smi``, ``vulkaninfo``) but accept injectable
``runner`` callables so the suite is fully unit-testable headless.

Nothing here overclaims. If Vulkan is missing we say so plainly; we do not
silently fall back to OpenGL (Roblox would crawl).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import config

# A runner executes a command and returns (returncode, stdout, stderr).
Runner = Callable[[list[str]], "tuple[int, str, str]"]


def _real_runner(cmd: list[str]) -> "tuple[int, str, str]":
    """Default runner: actually exec the command."""
    proc = subprocess.run(
        cmd, check=False, capture_output=True, text=True, timeout=30
    )
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class Check:
    name: str
    ok: bool
    message: str
    severity: str = "blocker"  # "blocker" | "warning"

    def __bool__(self) -> bool:
        return self.ok


@dataclass
class Diagnostics:
    checks: list[Check] = field(default_factory=list)

    def add(self, check: Check) -> None:
        self.checks.append(check)

    @property
    def blockers(self) -> list[Check]:
        return [c for c in self.checks if not c.ok and c.severity == "blocker"]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if c.severity == "warning"]

    @property
    def passed(self) -> list[Check]:
        return [c for c in self.checks if c.ok]

    @property
    def launchable(self) -> bool:
        """True only when zero blockers fired."""
        return not self.blockers

    def summary(self) -> str:
        lines = [f"Diagnostics: {len(self.passed)} passed, "
                 f"{len(self.warnings)} warning(s), "
                 f"{len(self.blockers)} blocker(s)."]
        for c in self.checks:
            mark = "✓" if c.ok else ("!" if c.severity == "warning" else "✗")
            lines.append(f"  {mark} {c.name}: {c.message}")
        return "\n".join(lines)


# ── Individual probes ────────────────────────────────────────────────────────

def check_arch(runner: Runner = _real_runner) -> Check:
    import platform
    arch = platform.machine()
    if arch in config.SUPPORTED_ARCHES:
        return Check("arch", True, f"CPU architecture is {arch}.")
    return Check(
        "arch", False,
        f"Goop needs {'/'.join(config.SUPPORTED_ARCHES)}; found {arch}. "
        "Wine-on-ARM is not supported for Roblox.",
    )


def check_kernel(runner: Runner = _real_runner) -> Check:
    import platform
    rel = platform.release()
    # Mint 21 ships 5.15; Mint 22 ships 6.8. Accept 5.15+.
    m = re.match(r"(\d+)\.(\d+)", rel)
    if not m:
        return Check("kernel", False, f"Unparseable kernel release: {rel}")
    major, minor = int(m.group(1)), int(m.group(2))
    if (major, minor) >= (5, 15):
        return Check("kernel", True, f"Kernel {rel} is supported.")
    return Check("kernel", False, f"Kernel {rel} is too old (need >= 5.15).")


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def check_vulkan_tools(runner: Runner = _real_runner) -> Check:
    """``vulkaninfo`` from vulkan-tools is the canonical Vulkan probe."""
    if not _have("vulkaninfo"):
        return Check(
            "vulkan-tools", False,
            "vulkaninfo not found. Install `vulkan-tools`.",
            severity="blocker",
        )
    return Check("vulkan-tools", True, "vulkaninfo is installed.")


def check_vulkan_device(runner: Runner = _real_runner) -> Check:
    """Run ``vulkaninfo --summary`` and look for a usable physical device."""
    if not _have("vulkaninfo"):
        return Check("vulkan-device", False, "vulkaninfo missing; cannot probe.")
    rc, out, _ = runner(["vulkaninfo", "--summary"])
    if rc != 0:
        return Check("vulkan-device", False,
                     "vulkaninfo failed to enumerate a device.")
    # Look for deviceType = DISCRETE_GPU or INTEGRATED_GPU and apiVersion.
    has_gpu = re.search(r"deviceType\s*=\s*\w*GPU", out) is not None
    m = re.search(r"apiVersion\s*=\s*(\d+)\.(\d+)\.(\d+)", out)
    if not has_gpu:
        return Check("vulkan-device", False,
                     "No Vulkan-capable GPU exposed. DXVK cannot translate D3D.")
    if m:
        major, minor = int(m.group(1)), int(m.group(2))
        if (major, minor) < config.MIN_VULKAN_API_VERSION:
            return Check(
                "vulkan-device", False,
                f"Vulkan {major}.{minor} is below the "
                f"{config.MIN_VULKAN_API_VERSION[0]}."
                f"{config.MIN_VULKAN_API_VERSION[1]} required by DXVK "
                f"{config.DXVK_VERSION}. Update your NVIDIA driver.",
            )
        return Check("vulkan-device", True,
                     f"Vulkan {major}.{minor} device present.")
    return Check("vulkan-device", True, "Vulkan GPU present (version unparsed).")


def check_nvidia_gpu(runner: Runner = _real_runner) -> Check:
    """Look for an NVIDIA dGPU via lspci. The 3060 Ti is the happy path."""
    if not _have("lspci"):
        return Check("nvidia-gpu", False, "lspci not found (install pciutils).",
                     severity="blocker")
    rc, out, _ = runner(["lspci", "-nn"])
    nvidia_lines = [l for l in out.splitlines() if "VGA" in l and "NVIDIA" in l]
    if not nvidia_lines:
        return Check("nvidia-gpu", False,
                     "No NVIDIA VGA device found. Goop targets NVIDIA + Vulkan.",
                     severity="warning")  # not fatal: AMD/Intel Vulkan may work
    primary = nvidia_lines[0]
    if config.TARGET_GPU.lower() in primary.lower():
        return Check("nvidia-gpu", True,
                     f"Detected target GPU ({config.TARGET_GPU}): {primary}")
    return Check("nvidia-gpu", True,
                 f"NVIDIA GPU detected: {primary}", severity="warning")


def check_nvidia_driver(runner: Runner = _real_runner) -> Check:
    """``nvidia-smi`` reports the driver version."""
    if not _have("nvidia-smi"):
        return Check("nvidia-driver", False,
                     "nvidia-smi not found. Install the proprietary NVIDIA driver.",
                     severity="blocker")
    rc, out, _ = runner(["nvidia-smi", "--query-gpu=driver_version",
                         "--format=csv,noheader"])
    if rc != 0 or not out.strip():
        return Check("nvidia-driver", False,
                     "nvidia-smi could not report a driver version.")
    ver_str = out.strip().splitlines()[0]
    m = re.match(r"(\d+)", ver_str)
    if not m:
        return Check("nvidia-driver", False, f"Odd driver version: {ver_str}")
    major = int(m.group(1))
    if major < config.TARGET_DRIVER_MIN:
        return Check("nvidia-driver", False,
                     f"NVIDIA driver {ver_str} is below "
                     f"{config.TARGET_DRIVER_MIN} (Vulkan 1.3 incomplete).")
    return Check("nvidia-driver", True, f"NVIDIA driver {ver_str}.")


def check_disk_space(path: Optional[Path] = None,
                     runner: Runner = _real_runner) -> Check:
    target = path or config.DATA_DIR
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        return Check("disk-space", False,
                     f"Cannot create data dir {target}.")
    # os.statvfs is POSIX; frsize * bavail = bytes available to user.
    import os as _os
    sb = _os.statvfs(target)
    free_mb = (sb.f_frsize * sb.f_bavail) // (1024 * 1024)
    if free_mb < config.MIN_DISK_MB:
        return Check("disk-space", False,
                     f"Only {free_mb} MB free at {target}; need "
                     f"{config.MIN_DISK_MB} MB for the prefix + Roblox.")
    return Check("disk-space", True,
                 f"{free_mb} MB free at {target} (need "
                 f"{config.MIN_DISK_MB} MB).")


def check_wine_version(runner: Runner = _real_runner) -> Check:
    """Confirm the staged Wine 11.9 is actually invocable."""
    wine = _find_wine_binary()
    if wine is None:
        return Check("wine-version", False,
                     "Wine 11.9 is not staged. Run the installer first.",
                     severity="blocker")
    rc, out, _ = runner([str(wine), "--version"])
    if rc != 0:
        return Check("wine-version", False, f"`{wine} --version` failed.")
    ver = out.strip().splitlines()[0] if out.strip() else ""
    if config.EXPECTED_WINE_VERSION not in ver:
        return Check("wine-version", False,
                     f"Expected {config.EXPECTED_WINE_VERSION}, got {ver}.")
    return Check("wine-version", True, f"Staged Wine reports {ver}.")


def _find_wine_binary() -> Optional[Path]:
    """Prefer the system staging dir, then the per-user one."""
    for base in (config.SYSTEM_WINE_DIR, config.USER_WINE_DIR):
        candidate = base / "bin" / "wine64"
        if candidate.exists():
            return candidate
    return None


# ── Orchestrator ─────────────────────────────────────────────────────────────

def run_all(runner: Runner = _real_runner) -> Diagnostics:
    """Run every guard and return a Diagnostics bundle."""
    d = Diagnostics()
    d.add(check_arch(runner))
    d.add(check_kernel(runner))
    d.add(check_nvidia_gpu(runner))
    d.add(check_nvidia_driver(runner))
    d.add(check_vulkan_tools(runner))
    d.add(check_vulkan_device(runner))
    d.add(check_disk_space(runner=runner))
    d.add(check_wine_version(runner))
    return d
