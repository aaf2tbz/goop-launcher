# Changelog

All notable changes to Goop Launcher are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-06-14

### Added
- Initial release.
- Self-contained **Wine 11.9** runtime, built from source on Ubuntu 22.04
  (`--enable-win64 --with-mingw`, new WoW64).
- **DXVK 2.6.1** staging into the per-user Wine prefix (D3D9/10/11 → Vulkan).
- GTK3 front-end (`goop`) with three actions: **Diagnose**, **Download & Install**, **Play**.
- Realistic system guards: CPU arch, kernel version, NVIDIA GPU detection,
  NVIDIA driver version, Vulkan tools + device + API version, disk space,
  staged Wine version.
- CLI: `goop version`, `goop diagnose`, `goop gui`.
- `.deb` packaging with `postinst`/`prerm`, desktop entry, scalable SVG icon.
- Two-stage release pipeline: `runtime-wine-*` (heavy Wine build) and `v*` (fast deb build).
- pytest suite (32 checks, fully headless via injectable probe runners).
- Roblox staged at runtime from the official Roblox CDN (never redistributed).
