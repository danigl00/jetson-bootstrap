# 3. Troubleshooting

Run `python healthcheck.py` first. Then match the symptom below.

## `ModuleNotFoundError: No module named 'cv2'`

The venv was created without `--system-site-packages`. Fix:

```bash
rm -rf .venv
uv venv --system-site-packages --python /usr/bin/python3
uv sync
```

## `cv2.__file__` points to `.venv/lib/...` (not `/usr/lib/python3/dist-packages/...`)

A dependency pulled in pip's `opencv-python` wheel, which is missing GStreamer and shadows the system cv2. Fix:

```bash
uv pip uninstall opencv-python opencv-python-headless
uv sync
```

Then check that `pyproject.toml` has the override block (without it, the next `uv sync` will reinstall the bad wheel):

```toml
[tool.uv]
override-dependencies = [
    "opencv-python ; sys_platform == 'never'",
    "opencv-python-headless ; sys_platform == 'never'",
]
```

## `A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x`

A dep upgraded NumPy past 2.0 and broke cv2's ABI. Fix:

```bash
uv add "numpy<2"
```

## `Failed to open camera` / `Cannot open device /dev/video0`

Several possible causes:

```bash
# Does the device exist?
ls /dev/video0
```

- **No `/dev/video0`** → the device tree overlay isn't applied. Re-do the camera setup in `docs/01_camera_setup.md`. After an apt upgrade that touched `/boot/`, you may need to re-run the `fdtoverlay` merge.
- **`/dev/video0` exists but pipeline still fails** → something else is using the Argus camera. Only one process can hold it.
  ```bash
  sudo fuser -v /dev/video0
  ps aux | grep -E "gst-launch|nvargus|python.*cam" | grep -v grep
  sudo systemctl restart nvargus-daemon
  ```

## OpenCV opens, but `cap.read()` returns `False`

Often the first few frames from Argus are empty during sensor warm-up. Discard 3–5 frames after opening the pipeline before checking success. The healthcheck and test scripts already do this.

If it persists, look at the `nvargus-daemon` log while you try to capture:

```bash
journalctl -u nvargus-daemon -f
```

## Cheese / GNOME Camera app opens and closes immediately

Expected. The CSI camera only exposes raw Bayer over V4L2, which standard camera apps can't display. Use `gst-launch`, the included `test_cam.py`, or any Python code using `cv2.VideoCapture(<gst pipeline>, cv2.CAP_GSTREAMER)`.

Live preview via `gst-launch`:
```bash
gst-launch-1.0 nvarguscamerasrc \
  ! 'video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1' \
  ! nvvidconv ! nvegltransform ! nveglglessink
```

## PyTorch warning: `Found GPU0 Orin which is of compute capability (CC) 8.7`

The pip torch wheel wasn't compiled for sm_87. Code still runs but may be slower or hit fallbacks on certain kernels. For most prototyping work this is acceptable. See `docs/02_project_workflow.md` for context.

## `uv add torch` fails with `No solution found ... nvidia-cusparselt-cu13`

The dep resolution is conflicting with a previously-installed torch and a missing piece from the Jetson AI Lab index. Easiest reset:

```bash
uv pip uninstall torch torchvision triton
uv add torch torchvision
```

## After re-flashing the Jetson, nothing works

Expected — the whole machine state is gone. Re-run the one-time machine setup in the main README, then re-install `jetson-new` and `healthcheck.py`:

```bash
./install.sh
```
