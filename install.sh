#!/usr/bin/env bash
# install.sh — install jetson-bootstrap helpers into ~/.local/bin
#
# Run once per machine:
#   ./install.sh
#
# This does NOT do the system-level camera setup (DTB overlay, apt installs).
# See README.md and docs/01_camera_setup.md for those steps.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${HOME}/.local/bin"

echo "Installing helpers to ${TARGET}"
mkdir -p "${TARGET}"

install -m 0755 "${SCRIPT_DIR}/jetson-new"   "${TARGET}/jetson-new"
install -m 0644 "${SCRIPT_DIR}/healthcheck.py" "${TARGET}/healthcheck.py"
install -m 0644 "${SCRIPT_DIR}/test_cam.py"    "${TARGET}/test_cam.py"

echo "  + ${TARGET}/jetson-new"
echo "  + ${TARGET}/healthcheck.py"
echo "  + ${TARGET}/test_cam.py"

# Make sure ~/.local/bin is on PATH
if ! echo "$PATH" | tr ':' '\n' | grep -qx "${HOME}/.local/bin"; then
    echo
    echo "NOTE: ${HOME}/.local/bin is not on your PATH."
    echo "Adding it to ~/.bashrc..."
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "${HOME}/.bashrc"
    echo "Run 'source ~/.bashrc' or open a new terminal to pick it up."
fi

# Quick sanity check on the camera side
echo
echo "Sanity checks:"
if command -v fdtoverlay >/dev/null 2>&1; then
    echo "  [OK]   fdtoverlay available"
else
    echo "  [WARN] fdtoverlay not found — sudo apt install device-tree-compiler"
fi

if /usr/bin/python3 -c "import cv2" 2>/dev/null; then
    echo "  [OK]   system python3-opencv installed"
else
    echo "  [WARN] system OpenCV not found — sudo apt install python3-opencv"
fi

if [[ -e /dev/video0 ]]; then
    echo "  [OK]   /dev/video0 exists"
else
    echo "  [WARN] /dev/video0 missing — see docs/01_camera_setup.md"
fi

echo
echo "Done. Try: jetson-new my_project"
