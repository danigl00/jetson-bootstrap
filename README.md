# jetson-bootstrap

Reproducible setup for a **Jetson Orin Nano Super Dev Kit** with a **Raspberry Pi Camera v2 (IMX219)**, using **uv** for Python project management.

Getting a Pi camera to work on JetPack 6 (Super) has initial issues: `jetson-io` is broken for the Super model, `OVERLAYS=` in `extlinux.conf` is silently ignored, the GNOME camera app can't display CSI cameras at all, pip's `opencv-python` wheel doesn't include GStreamer (so it can't open CSI cameras), and the system OpenCV needs `numpy<2`. This repo bundles the fixes, the docs, and a helper scripts to create projects with proper configurations.

## Overview

| File | Purpose |
|---|---|
| `install.sh` | One-shot install of the helpers into `~/.local/bin/` |
| `jetson-new` | Bootstrap a new uv project with all the camera/OpenCV gotchas pre-fixed |
| `healthcheck.py` | Verify the camera, OpenCV, and GPU are working in any venv |
| `test_cam.py` | Live preview / headless capture / video record from the CSI camera |
| `docs/01_camera_setup.md` | Step-by-step: get the IMX219 detected by the kernel |
| `docs/02_project_workflow.md` | Daily workflow with uv on this Jetson |
| `docs/03_troubleshooting.md` | Symptom → fix cheatsheet |

## Prerequisites

- Jetson Orin Nano Dev Kit (Super variant — i.e., `nvidia,p3768-0000+p3767-0005-super`)
- JetPack 6 flashed and booted (tested on L4T R39.2)
- Raspberry Pi Camera v2 (IMX219) wired to the **CAM0** CSI port
- `uv` installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`

If you're on a different Jetson model the camera setup will need different DTB filenames — the rest still applies.

## One-time machine setup

```bash
# 1. Install system OpenCV (the one built with GStreamer + the IMX219 pipeline)
sudo apt update
sudo apt install -y python3-opencv device-tree-compiler

# 2. Apply the camera device tree overlay
#    Detailed steps in docs/01_camera_setup.md
#    Short version (assuming CAM0):
sudo cp /boot/tegra234-p3768-0000+p3767-0005-nv-super.dtb \
        /boot/tegra234-p3768-0000+p3767-0005-nv-super.dtb.bak
sudo fdtoverlay \
  -i /boot/tegra234-p3768-0000+p3767-0005-nv-super.dtb.bak \
  -o /boot/tegra234-p3768-0000+p3767-0005-nv-super.dtb \
  /boot/tegra234-p3767-camera-p3768-imx219-A.dtbo

# 3. Add the FDT line to extlinux.conf (see docs/01_camera_setup.md for the exact file)
#    Then reboot
sudo reboot

# 4. After reboot, install this repo's helpers
git clone https://github.com/danigl00/jetson-bootstrap ~/jetson-bootstrap
cd ~/jetson-bootstrap
./install.sh
```

After step 4 you can verify the camera with:
```bash
ls /dev/video0                # should exist
python3 ~/.local/bin/healthcheck.py   # all green except cv2.cuda (N/A is fine)
```

## Workflow

```bash
jetson-new my_project       # creates a uv project with all the right config
cd my_project
source .venv/bin/activate
uv add package        # whatever your project needs
python healthcheck.py       # confirm camera + GPU
```

`jetson-new` handles three things you'd otherwise need to remember on every project:

1. `uv venv --system-site-packages --python /usr/bin/python3` (so system cv2 is visible)
2. `uv add "numpy<2"` (system cv2 has a NumPy 1.x ABI)
3. Adds `[tool.uv].override-dependencies` to `pyproject.toml` to block any transitive `opencv-python` install

After that, **use uv you normal** — `uv add`, `uv sync`, `uv remove`, etc. The only rule is: never `uv add opencv-python` on this machine.

More detail in `docs/02_project_workflow.md`.

## Checkup

Run `python healthcheck.py` first. Then check `docs/03_troubleshooting.md` — most symptoms map to a one-line fix.
