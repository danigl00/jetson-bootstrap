#!/usr/bin/env python3
"""
IMX219 camera test for Jetson Orin Nano.

Usage:
    python3 test_camera.py              # live preview window
    python3 test_camera.py --headless   # capture N frames, save samples, no window
    python3 test_camera.py --record 10  # record 10 seconds to test.mp4

Press 'q' or ESC to quit preview. 's' saves a snapshot.
"""

import argparse
import sys
import time
from pathlib import Path

import cv2


def gst_pipeline(
    sensor_id: int = 0,
    capture_width: int = 1920,
    capture_height: int = 1080,
    display_width: int = 960,
    display_height: int = 540,
    framerate: int = 30,
    flip_method: int = 0,
) -> str:
    """Build a GStreamer pipeline string for nvarguscamerasrc -> BGR appsink."""
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width=(int){capture_width}, height=(int){capture_height}, "
        f"framerate=(fraction){framerate}/1 ! "
        f"nvvidconv flip-method={flip_method} ! "
        f"video/x-raw, width=(int){display_width}, height=(int){display_height}, format=(string)BGRx ! "
        f"videoconvert ! "
        f"video/x-raw, format=(string)BGR ! appsink drop=true max-buffers=2"
    )


def open_camera(args) -> cv2.VideoCapture:
    pipeline = gst_pipeline(
        sensor_id=args.sensor_id,
        capture_width=args.width,
        capture_height=args.height,
        display_width=args.display_width,
        display_height=args.display_height,
        framerate=args.fps,
        flip_method=args.flip,
    )
    print(f"[info] GStreamer pipeline:\n{pipeline}\n")
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    if not cap.isOpened():
        print("[error] Failed to open camera. Check:", file=sys.stderr)
        print("  - nvargus-daemon running?  sudo systemctl status nvargus-daemon", file=sys.stderr)
        print("  - OpenCV built with GStreamer?  python3 -c \"import cv2; print(cv2.getBuildInformation())\" | grep -i gstreamer", file=sys.stderr)
        print("  - /dev/video0 exists?  ls /dev/video*", file=sys.stderr)
        sys.exit(1)
    return cap


def preview(args):
    cap = open_camera(args)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames = 0
    t0 = time.time()
    fps_display = 0.0
    win = "IMX219 preview (q/ESC quit, s snapshot)"

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[warn] frame grab failed")
                break

            frames += 1
            if frames % 30 == 0:
                dt = time.time() - t0
                fps_display = 30.0 / dt if dt > 0 else 0.0
                t0 = time.time()

            cv2.putText(
                frame,
                f"{frame.shape[1]}x{frame.shape[0]}  {fps_display:5.1f} fps",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
            )
            cv2.imshow(win, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("s"):
                path = out_dir / f"snap_{int(time.time())}.jpg"
                cv2.imwrite(str(path), frame)
                print(f"[info] saved {path}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"[info] {frames} frames total")


def headless(args):
    cap = open_camera(args)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Warm-up — first frames from argus can be black
    for _ in range(5):
        cap.read()

    t0 = time.time()
    saved = 0
    grabbed = 0
    target = args.headless

    while grabbed < target:
        ok, frame = cap.read()
        if not ok:
            print("[warn] frame grab failed")
            break
        grabbed += 1
        # Save every Nth frame so we get a spread, not 100 near-identical ones
        if grabbed % max(1, target // 5) == 0 or grabbed == target:
            path = out_dir / f"frame_{grabbed:04d}.jpg"
            cv2.imwrite(str(path), frame)
            saved += 1
            print(f"[info] saved {path}  ({frame.shape[1]}x{frame.shape[0]})")

    dt = time.time() - t0
    fps = grabbed / dt if dt > 0 else 0.0
    print(f"[info] grabbed {grabbed} frames in {dt:.2f}s ({fps:.1f} fps), saved {saved}")
    cap.release()


def record(args):
    cap = open_camera(args)
    out_path = Path(args.out_dir) / "test.mp4"
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    # Read one frame to know the actual size
    ok, frame = cap.read()
    if not ok:
        print("[error] could not read initial frame", file=sys.stderr)
        sys.exit(1)
    h, w = frame.shape[:2]

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, float(args.fps), (w, h))
    if not writer.isOpened():
        print(f"[error] could not open VideoWriter at {out_path}", file=sys.stderr)
        sys.exit(1)

    duration = args.record
    print(f"[info] recording {duration}s to {out_path} at {w}x{h}")
    t0 = time.time()
    frames = 0
    while time.time() - t0 < duration:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(frame)
        frames += 1

    writer.release()
    cap.release()
    dt = time.time() - t0
    print(f"[info] wrote {frames} frames in {dt:.2f}s ({frames/dt:.1f} fps) -> {out_path}")


def main():
    p = argparse.ArgumentParser(description="IMX219 camera test for Jetson Orin Nano")
    p.add_argument("--sensor-id", type=int, default=0, help="CSI sensor id (0=CAM0, 1=CAM1)")
    p.add_argument("--width", type=int, default=1920, help="capture width")
    p.add_argument("--height", type=int, default=1080, help="capture height")
    p.add_argument("--display-width", type=int, default=960)
    p.add_argument("--display-height", type=int, default=540)
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--flip", type=int, default=0, help="nvvidconv flip-method 0..7 (2=180deg)")
    p.add_argument("--out-dir", default="./camera_test_out")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--headless", type=int, metavar="N", help="grab N frames, no GUI")
    g.add_argument("--record", type=int, metavar="SEC", help="record SEC seconds to mp4")
    args = p.parse_args()

    if args.headless:
        headless(args)
    elif args.record:
        record(args)
    else:
        preview(args)


if __name__ == "__main__":
    main()
