# 1. Camera setup — getting IMX219 detected on JetPack 6 Super

Only do once per Jetson (or after a re-flash). Goal: have `/dev/video0` exist and respond to `nvarguscamerasrc`.

## Why it's not just "plug in and go"

NVIDIA ships IMX219 device tree overlays in `/boot/`, but on the **Orin Nano Super** dev kit running JetPack 6 you can't just enable them the documented way:

- The official tool `/opt/nvidia/jetson-io/config-by-hardware.py` crashes with `RuntimeError: No DTB found for NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super!` — it doesn't recognise the "Super" model string.
- The fallback (adding `OVERLAYS=...` to `extlinux.conf`) is **silently ignored** by the UEFI bootloader on JetPack 6 Super.

The workaround is to **pre-merge the overlay into the base DTB** with `fdtoverlay`, so the kernel boots with the camera already in its device tree. That's what these steps do.

## Step-by-step

### 1. Confirm your hardware

```bash
cat /proc/device-tree/model
```
Should print something like `NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super`.

```bash
cat /proc/device-tree/compatible
```
Should include `nvidia,p3768-0000+p3767-0005-super`. **If your suffix is different** (e.g. `0001-super`, `0003-super`, `0004-super`), use the matching DTB filename in the steps below.

### 2. Confirm the camera is physically connected

Make sure the IMX219 ribbon is fully seated, contacts facing the right way, in **CAM0** (the connector closer to the DC barrel jack). The Orin Nano dev kit uses **22-pin** CSI connectors — a stock 15-pin Pi camera ribbon needs a 15-to-22 adapter.

### 3. Install the device tree compiler (provides `fdtoverlay`)

```bash
sudo apt update
sudo apt install -y device-tree-compiler python3-opencv
```

### 4. Pick the right overlay file

For a single IMX219 on CAM0:
```
/boot/tegra234-p3767-camera-p3768-imx219-A.dtbo
```

Other options in `/boot/`:
- `tegra234-p3767-camera-p3768-imx219-C.dtbo` — single camera on CAM1
- `tegra234-p3767-camera-p3768-imx219-dual.dtbo` — both CSI ports populated with IMX219

### 5. Back up the base DTB and merge the overlay

```bash
DTB=/boot/tegra234-p3768-0000+p3767-0005-nv-super.dtb
# Adjust the filename if your /proc/device-tree/compatible suffix differs

sudo cp "$DTB" "$DTB.bak"
sudo fdtoverlay \
  -i "$DTB.bak" \
  -o "$DTB" \
  /boot/tegra234-p3767-camera-p3768-imx219-A.dtbo
```

### 6. Point extlinux at this DTB

Edit `/boot/extlinux/extlinux.conf` to add an `FDT` line inside the `LABEL primary` block. If you don't have `nano`, use this one-shot rewrite (preserves your existing root partition UUID — copy it from the current file's `APPEND` line first):

```bash
sudo cat /boot/extlinux/extlinux.conf       # note the root=PARTUUID=... value
```

Then write the new file (substitute your PARTUUID):

```bash
sudo tee /boot/extlinux/extlinux.conf > /dev/null << 'EOF'
TIMEOUT 30
DEFAULT primary
MENU TITLE L4T boot options
LABEL primary
      MENU LABEL primary kernel
      LINUX /boot/Image
      FDT /boot/tegra234-p3768-0000+p3767-0005-nv-super.dtb
      INITRD /boot/initrd
      APPEND ${cbootargs} root=PARTUUID=<YOUR-PARTUUID-HERE> rw rootwait rootfstype=ext4 mminit_loglevel=4 console=ttyTCU0,115200 firmware_class.path=/etc/firmware fbcon=map:0 video=efifb:off efi_pstore.pstore_disable=1 pstore.backend=ramoops efi=runtime pci=pcie_bus_perf nvme.use_threaded_interrupts=1
EOF
```

### 7. Reboot

```bash
sudo reboot
```

### 8. Verify

```bash
ls /dev/video*
# expect: /dev/video0

ls /dev/i2c-*
# expect both i2c-9 and i2c-10 present

sudo dmesg | grep -iE "imx219|nvcsi"
# expect: "imx219 9-0010: tegracam sensor driver: ..."
# expect: "tegra-capture-vi: subdev imx219 9-0010 bound"
```

End-to-end capture test:
```bash
gst-launch-1.0 nvarguscamerasrc num-buffers=1 \
  ! 'video/x-raw(memory:NVMM),width=1920,height=1080' \
  ! nvjpegenc \
  ! filesink location=/tmp/test.jpg
ls -lh /tmp/test.jpg
```

## Rollback

If the system fails to boot after the changes, restore the backup from another Linux machine (mount the Jetson's root filesystem from its SD card / NVMe):

```bash
cp /boot/tegra234-p3768-0000+p3767-0005-nv-super.dtb.bak \
   /boot/tegra234-p3768-0000+p3767-0005-nv-super.dtb
```

## Notes

- **You won't be able to use the GNOME camera app (Cheese / Snapshot).** This is expected, not a bug. CSI cameras only expose raw Bayer over V4L2; the ISP processing happens in the Argus stack via `nvarguscamerasrc`. Use `gst-launch`, our `test_cam.py`, or any Python code using `cv2.VideoCapture(<gst pipeline>, cv2.CAP_GSTREAMER)`.
- **`apt upgrade` may overwrite the modified DTB.** Keep `*.dtb.bak` around. If an upgrade breaks the camera, re-run step 5.
- **The "dependency cycle" messages** in `dmesg` after this setup (`Fixed dependency cycle(s) with /bus@0/...`) are cosmetic and harmless on JetPack 6.
