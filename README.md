# Goop Launcher

A tiny **Wine 11.9** launcher for **Roblox** on **Linux Mint Cinnamon**, packaged as a `.deb`.

It stages a self-contained Wine 11.9 build with **DXVK → Vulkan** (ideal for
NVIDIA GPUs), runs the official Roblox client under it, and ships a small
GTK3 front-end that diagnoses your system, stages Roblox from `roblox.com` at
first run, and launches it.

> **Target hardware:** NVIDIA RTX 3060 Ti + a slightly older CPU. The launcher
> is tuned for Vulkan 1.3 on the proprietary NVIDIA driver (≥ 535), with
> `fsync`/`esync` enabled.

## What this is — and isn't

- ✅ **Is:** a clean, inspectable, scriptable installer + launcher that pins a
  known-good Wine build and a known-good DXVK, with realistic guards so it
  *tells you* when your system isn't ready.
- ❌ **Isn't:** a Roblox redistributable. Roblox binaries are **never** bundled —
  they're fetched at install/run time from the official Roblox CDN. Roblox's
  Hyperion anti-cheat periodically changes its Wine compatibility story; if a
  given Wine build stops working, that's a Roblox decision and the launcher
  surfaces it honestly rather than silently failing.

## Install (end user)

1. Download the latest `.deb` from [Releases](../../releases).
2. Install it:
   ```bash
   sudo apt install ./goop-launcher_0.1.0_amd64.deb
   ```
   This pulls in `python3-gi`, `gir1.2-gtk-3.0`, `vulkan-tools`, `pciutils`, `curl`.
3. Open **Goop Launcher** from your applications menu, or run `goop`.
4. Press **Diagnose** (runs the guards), then **Download & Install** (fetches
   Roblox + initialises the Wine prefix), then **Play**.

## System requirements

| Requirement | Why |
|---|---|
| **x86_64** Linux (Mint 21/22, Ubuntu 22.04+) | Wine 11.9 is built for x86_64 against glibc 2.35. |
| **NVIDIA GPU** + proprietary driver ≥ 535 | Goop targets DXVK→Vulkan; the 3060 Ti is the happy path. AMD/Intel Vulkan may work (warning, not blocker). |
| **Vulkan 1.3+** (`vulkaninfo` must find a discrete GPU) | DXVK 2.x requires it. |
| **~5 GB free disk** | Wine prefix + Roblox staging. |
| Kernel ≥ 5.15 | Mint 21 ships 5.15; Mint 22 ships 6.8. |

The **Diagnose** button (or `goop diagnose`) checks all of the above.

## Architecture

```
launcher/goop_launcher/        # Python launcher (PyGObject/GTK3 front-end)
  config.py                    #   pinned versions + URLs + resolved paths
  checks.py                    #   realistic system guards (GPU/driver/vulkan/disk/wine)
  wine.py                      #   prefix init + DXVK staging
  roblox.py                    #   official-CDN Roblox staging + launch
  app.py                       #   GTK3 window (the ONLY module importing `gi`)
  __main__.py                  #   CLI: `goop [version|diagnose|gui]`

scripts/                       # Shell backbone
  lib/common.sh                #   shared logging + fetch + verify helpers
  build-wine.sh                #   compile Wine 11.9 from source (sha512-verified)
  package-wine.sh              #   tar.xz the built Wine tree (+ sha256 sidecar)
  stage-wine.sh                #   download+verify+extract Wine tarball to /opt/goop
  stage-dxvk.sh                #   stage DXVK 2.6.1 x64 DLLs into the prefix
  goop-setup.sh                #   user-facing installer (guards → wine → prefix → dxvk)
  build-deb.sh                 #   assemble the .deb from repo + Wine tarball

package/                       # .deb payload
  postinst / prerm             #   apt lifecycle hooks
  goop.desktop                 #   applications-menu entry
  goop-launcher.sh             #   /usr/bin/goop wrapper
  assets/icons/goop.svg        #   scalable icon

tests/                         # pytest suite (32 checks, fully headless)
.github/workflows/             # ci.yml + wine-release.yml + release.yml
```

## Release pipeline

Two decoupled releases, mirroring how production Wine-on-Linux projects work:

1. **`runtime-wine-11.9`** — tag `runtime-wine-*` → `wine-release.yml` compiles
   Wine 11.9 from source on Ubuntu 22.04 and uploads `wine-11.9-goop-x86_64.tar.xz`
   (with a SHA-256 sidecar). This is the heavy step; it rarely needs to re-run.
2. **`v*`** — tag `v0.1.0` etc. → `release.yml` *downloads* that Wine tarball
   and builds the `.deb` from it. Fast, so you can re-tag the launcher without
   rebuilding Wine.

The `ci.yml` workflow runs on every push/PR: shellcheck (warnings+errors) +
pytest + a deb-structure sanity check.

## Develop

```bash
# Run the test suite headless (no display, no gi needed for non-app modules)
pip install -r requirements-dev.txt
python -m pytest -v

# CLI diagnostics (no GUI)
PYTHONPATH=launcher python -m goop_launcher diagnose

# Lint shell scripts
shellcheck -x scripts/*.sh
```

Wine is built on Ubuntu 22.04 **in CI**, not on your dev box. To build Wine
locally, use the same container:

```bash
docker run --rm -v "$PWD":/work -w /work ubuntu:22.04 bash -c '
  apt-get update && apt-get install -y build-essential flex bison \
    gcc-mingw-w64-x86-64 g++-mingw-w64-x86-64 libfreetype-dev libx11-dev \
    libvulkan-dev vulkan-headers libgl1-mesa-dev pkg-config xz-utils curl &&
  GOOP_WINE_PREFIX=/work/dist/wine-11.9 ./scripts/build-wine.sh'
```

## License

MIT — see [LICENSE](LICENSE). Wine and DXVK retain their own licenses
(LGPL-2.1 and zlib respectively); this project only builds and stages them.
Roblox is a trademark of Roblox Corporation; this project is unaffiliated and
redistributes nothing of theirs.
