# 2. Daily project workflow

Once the camera is set up at the system level, this is how you work day-to-day. The whole goal is: **use uv exactly like normal** — with three small things handled for you.

## The three things that differ from a normal uv project

1. **Venv created with `--system-site-packages`** so the project can see the system OpenCV at `/usr/lib/python3/dist-packages/cv2*`. Pip's `opencv-python` wheel lacks GStreamer support and can't open CSI cameras, so we deliberately use the system one instead.
2. **`numpy<2` is pinned.** System cv2 (4.6.0 on JetPack 6) was compiled against NumPy 1.x and crashes at import time with NumPy 2.x.
3. **`opencv-python` is overridden in `pyproject.toml`** so any dep that depends on it (ultralytics, supervision, mmcv, etc.) doesn't sneakily pull pip's broken wheel into `.venv/` and shadow the system one.

That's all. `jetson-new` does these three things for you. Everything else is plain uv.

## New project (the easy way)

```bash
jetson-new my_project
cd my_project
source .venv/bin/activate

uv add ultralytics torch torchvision
uv add pandas matplotlib

python healthcheck.py
```

## New project (the manual way, if `jetson-new` isn't installed)

```bash
uv init my_project
cd my_project
uv venv --system-site-packages --python /usr/bin/python3
uv add "numpy<2"
cat >> pyproject.toml << 'EOF'

[tool.uv]
override-dependencies = [
    "opencv-python ; sys_platform == 'never'",
    "opencv-python-headless ; sys_platform == 'never'",
]
EOF
source .venv/bin/activate
```

## Cloning an existing Jetson project (from this repo's pattern)

If `pyproject.toml` already has the override block, you just need:

```bash
git clone <project-url>
cd <project>
uv venv --system-site-packages --python /usr/bin/python3
uv sync
```

The `--system-site-packages` flag isn't in `pyproject.toml` — it's a venv-level setting in `.venv/pyvenv.cfg` — so you have to apply it manually when recreating the venv.

## What you do every day

```bash
cd ~/path/to/project
source .venv/bin/activate
# write code, run scripts
python my_script.py
# add deps as needed
uv add some-library
```

That's a normal uv flow. No special commands. No flag to remember.

## The one rule

**Never `uv add opencv-python`** on this Jetson. The system cv2 is already importable. If you accidentally do, your camera code will stop working — see `docs/03_troubleshooting.md`.

## PyTorch caveat

The standard pip torch wheel imports and runs on the GPU on this Jetson, but it isn't compiled for Orin's compute capability (sm_87). You'll see a warning at import time. Simple workloads (matmul, basic conv) work fine; some less-common CUDA kernels may fall back to slow paths or fail.

For maximum performance you'd use NVIDIA's Jetson-specific PyTorch wheel, but at the time of writing there isn't a stable one for the Python 3.12 + CUDA 13 combination shipped with this JetPack. For prototyping and most coursework, the pip wheel is fine.

## Reproducibility caveat

The setup is Jetson-specific. If you clone a project to a laptop or other non-Jetson machine, **don't use `--system-site-packages`** — just `uv add opencv-python` normally, and skip the override block. There's no system cv2 to share off-Jetson.
