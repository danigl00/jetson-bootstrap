#!/usr/bin/env python3
"""
Jetson healthcheck — verifies the camera and GPU are usable from Python.

Run:
    python healthcheck.py

Exits 0 if everything works, 1 otherwise. Prints a short report.
"""

import shutil
import subprocess
import sys
import time


def section(title: str):
    print(f"\n=== {title} ===")


def ok(msg: str):
    print(f"  [OK]   {msg}")


def fail(msg: str):
    print(f"  [FAIL] {msg}")


def warn(msg: str):
    print(f"  [WARN] {msg}")


def check_cv2_build() -> tuple[bool, "cv2 module | None"]:
    section("OpenCV")
    try:
        import cv2
    except ImportError as e:
        fail(f"cv2 not importable: {e}")
        fail("On Jetson: sudo apt install python3-opencv, and create venv with --system-site-packages")
        return False, None

    ok(f"cv2 version: {cv2.__version__}")
    ok(f"cv2 path:    {cv2.__file__}")

    build = cv2.getBuildInformation()
    gst_line = next((l for l in build.split("\n") if "GStreamer" in l), "")
    if "YES" in gst_line:
        ok(f"GStreamer support: yes ({gst_line.strip()})")
    else:
        fail("OpenCV was built WITHOUT GStreamer — CSI camera won't work")
        fail("You're likely using pip's opencv-python. Remove it and use system cv2.")
        return False, cv2

    cuda_line = next((l for l in build.split("\n") if "CUDA" in l and ":" in l), "")
    if "YES" in cuda_line:
        ok(f"CUDA support:      yes ({cuda_line.strip()})")
    else:
        warn("OpenCV built without CUDA (not required for basic capture)")

    return True, cv2


def check_camera(cv2_mod) -> bool:
    section("CSI Camera (IMX219)")
    if cv2_mod is None:
        fail("skipped — cv2 not available")
        return False

    pipeline = (
        "nvarguscamerasrc sensor-id=0 num-buffers=10 ! "
        "video/x-raw(memory:NVMM),width=1920,height=1080,framerate=30/1 ! "
        "nvvidconv ! video/x-raw,format=BGRx ! "
        "videoconvert ! video/x-raw,format=BGR ! appsink drop=true max-buffers=2"
    )

    cap = cv2_mod.VideoCapture(pipeline, cv2_mod.CAP_GSTREAMER)
    if not cap.isOpened():
        fail("could not open CSI camera pipeline")
        fail("check: ls /dev/video0 ; sudo systemctl status nvargus-daemon")
        return False
    ok("pipeline opened")

    # Warm-up — first frames from Argus can be empty
    for _ in range(3):
        cap.read()

    t0 = time.time()
    n = 0
    last_frame = None
    for _ in range(10):
        got, frame = cap.read()
        if got and frame is not None:
            n += 1
            last_frame = frame
    dt = time.time() - t0
    cap.release()

    if n == 0:
        fail("opened but grabbed 0 frames")
        return False

    fps = n / dt if dt > 0 else 0.0
    ok(f"grabbed {n}/10 frames at ~{fps:.1f} fps")
    ok(f"frame shape: {last_frame.shape}, dtype: {last_frame.dtype}")
    return True


def check_gpu_cv2(cv2_mod) -> bool | None:
    """Returns True/False if cv2 has CUDA support, or None if it doesn't (not a failure)."""
    section("GPU — via OpenCV CUDA (optional)")
    if cv2_mod is None:
        warn("skipped — cv2 not available")
        return None
    try:
        n = cv2_mod.cuda.getCudaEnabledDeviceCount()
    except Exception as e:
        warn(f"cv2.cuda not available: {e}")
        return None
    if n == 0:
        warn("cv2 was built without CUDA (Ubuntu's python3-opencv package on JetPack ships this way)")
        warn("not a problem — only matters if you use cv2.cuda.* kernels")
        return None
    ok(f"{n} CUDA device(s) visible to OpenCV")
    try:
        cv2_mod.cuda.printShortCudaDeviceInfo(0)
    except Exception:
        pass
    return True


def check_gpu_torch() -> bool:
    section("GPU — via PyTorch (optional)")
    try:
        import torch
    except ImportError:
        warn("torch not installed in this env (skip if not needed)")
        return True  # not a failure
    ok(f"torch {torch.__version__}")
    if not torch.cuda.is_available():
        fail("torch.cuda.is_available() = False")
        return False
    ok(f"CUDA device: {torch.cuda.get_device_name(0)}")
    # Tiny end-to-end sanity op
    x = torch.randn(1024, 1024, device="cuda")
    y = (x @ x).sum().item()
    ok(f"matmul on GPU produced finite value: {bool(abs(y) < 1e30)}")
    return True


def check_tegrastats() -> bool:
    section("System (tegrastats one-shot)")
    if not shutil.which("tegrastats"):
        warn("tegrastats not found")
        return True
    try:
        proc = subprocess.Popen(["tegrastats", "--interval", "500"], stdout=subprocess.PIPE, text=True)
        line = proc.stdout.readline()
        proc.terminate()
        proc.wait(timeout=2)
        ok(line.strip()[:200])
    except Exception as e:
        warn(f"could not read tegrastats: {e}")
    return True


def main() -> int:
    print("Jetson healthcheck")
    print("------------------")

    cv2_ok, cv2_mod = check_cv2_build()
    cam_ok = check_camera(cv2_mod)
    gpu_cv2_ok = check_gpu_cv2(cv2_mod)
    gpu_torch_ok = check_gpu_torch()
    check_tegrastats()

    section("Summary")
    results = [
        ("OpenCV with GStreamer", cv2_ok),
        ("CSI camera capture",    cam_ok),
        ("GPU (cv2.cuda)",        gpu_cv2_ok),
        ("GPU (torch)",           gpu_torch_ok),
    ]
    for name, v in results:
        if v is True:
            label = "OK  "
        elif v is False:
            label = "FAIL"
        else:
            label = "N/A "
        print(f"  {label}  {name}")

    # camera + cv2 build are the hard requirements; torch is optional
    critical_ok = cv2_ok and cam_ok
    return 0 if critical_ok else 1


if __name__ == "__main__":
    sys.exit(main())
