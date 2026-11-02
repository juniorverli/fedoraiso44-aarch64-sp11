# Cameras test plan (rear OV13858 first, then front IMX681, IR node inert)

The revised next-boot procedure and safety gate are in `evidence/2026-11-02-m16-safe-camera-probe.md`. Do not follow the streaming steps below until the camera-to-indicator wiring has been independently cross-checked and the physical indicator is visibly on throughout every stream.

One batched boot on the operator's own PC, live USB only (no install, S-rules in `plan/risks.md`).
Every step is read-only except binding the sensor drivers, which read the chip id and, when the user asks,
stream. No `i2cdetect` on the CCI buses (they carry an EEPROM and a lens actuator). The IR emitter, the PMIC
flash and the sensor strobe are not described in any DTB and must stay off (S2). Raw logs stay under `out/`.

## Contents required before boot

- Kernel with the camera patches `hardware/cameras/patches/0001`-`0021`, plus the integrated RGB-only exclusion (CAMSS C-PHY 0006-0010, register blob parser
  0011, OV13858 blob modes 0012-0014, IMX681 0015-0016, VD55G0 binding 0017, front and IR DT 0018-0019), BTF on, and
  `CONFIG_VIDEO_QCOM_CAMSS=m`, `CONFIG_I2C_QCOM_CCI=m`, `CONFIG_VIDEO_OV13858=m`, `CONFIG_VIDEO_IMX681=m`,
  `CONFIG_CRC32=y`, `CONFIG_LEDS_GPIO` (m or y), `CONFIG_CLK_X1E80100_CAMCC=m`, `CONFIG_REGULATOR_QCOM_RPMH=y`,
  `CONFIG_DMABUF_HEAPS_SYSTEM=y` (kernel worker to confirm against the Fedora config).
- The revised RGB-only diagnostic DTB `x1p64100-microsoft-denali-cam-all.dtb` and its `x1-microsoft-denali-camera-no-ir.dtsi` include, or the corrected `...-cam-rear.dtb` for isolation. Confirm the effective DT graph and statuses after integration.
- Private image mode only: the local register blobs `ov13858-mshw0491.bin` and `imx681-mshw0490.bin` in
  `/usr/lib/firmware/updates/` (generated with `hardware/cameras/userspace/build-camera-firmware.py`; never in git, never
  in a public image). Without the OV13858 blob the rear camera runs on its built-in modes; without the IMX681 blob the
  front driver refuses to probe before it touches the hardware, with a clear message.
- Fedora `libcamera`, `libcamera-ipa`, `libcamera-tools` (`cam`), `libcamera-qcam`, `libcamera-gstreamer`,
  `pipewire-plugin-libcamera`, `snapshot`, `v4l-utils`.
- The collector `hardware/cameras/collector/cameras.sh` (read-only) installed in the log collector.

## Collector

The log collector sources `cameras.sh` and writes `extra-cameras.txt`: kernel configuration, modules, kernel log,
deferred devices, blob names with a SHA-256 prefix, bound I2C devices (no bus scan), the media graph (`media-ctl -p`),
`v4l2-ctl --list-devices`, subdev media bus codes and controls, `cam -l`, the LED class state, GPIO, pinmux, regulator and
clock state. Nothing in it streams or writes.

## Steps

1. Boot the revised RGB-only `cam-all` variant (IR endpoint removed). Expected, rear: `ov13858` probes on `cci0` bus 1 at `0x10` and reads the chip id (`0x300A`,
   `0xD855` expected); with the blob it logs `3 modes loaded from ov13858-mshw0491.bin`. If it reports `-ENODEV` or an
   I2C error, record the message and stop: the address, a rail or the reset polarity is wrong.
2. Front: confirm that `imx681` binds and inspect blob errors. A chip-ID mismatch is logged if the blob specifies an ID; successful binding produces no ID success log and the ID check is skipped when the blob has no ID. The IR node and its bus are disabled; the IR endpoint is absent from the CAMSS graph.
3. `media-ctl -p`: a CAMSS media graph with `msm_csiphy1` (rear), `msm_csiphy2` (front), CSIDs, VFEs and the sensor entities.
4. After independent indicator wiring cross-check and confirmation of physical LED operation, test rear first, then front. The sensor must illuminate its physical privacy LED throughout each stream; stop immediately if it does not. Do not operate the flash, IR strobe or illuminator. Patch 0020 provides shared LED accounting but its KUnit suite remains unexecuted.
5. Configure a complete sensor → CSIPHY → CSID → VFE RDI route and matching formats using `media-ctl`, or let libcamera configure them. Select actual entity names, pad numbers, format, dimensions and video node from the newly printed graph; they may differ between boots. Run the commands below after substituting the chosen route and checking the graph. Never use the old video-number mapping as a guarantee.
6. The rear built-in 4224x3136 mode is SGRBG10; Windows blob modes are SBGGR10. The front Windows data is SRGGB10. Verify each negotiated mode and Bayer order with a colour target; no stream has yet established it on this device.
7. libcamera: `cam -l` and a capture with the Software ISP; the result must be a coloured RGB or YUV picture, not RAW. Confirm which tuning and sensor helper are actually installed; uncalibrated processing and incomplete control support may give poor colour or exposure.
8. Record `/sys/kernel/debug/regulator` state before and after, to confirm all rails return to off.

### Commands for the next boot

Read-only graph and enumeration (save output in `out/device-logs/m16-20261102/` via the collector):

```sh
media-ctl -d /dev/media0 -p
v4l2-ctl --list-devices
ls -l /dev/v4l-subdev*
cam -l
journalctl -k -b | grep -Ei 'camss|csiphy|csid|vfe|ov13858|imx681|cci'
```

Expected: each RGB sensor has an immutable enabled link to its CSIPHY, and subdevice nodes exist. If not, stop and collect notifier diagnostics; use the rear-only DT if one RGB probe fails.

For RAW debugging after the privacy gate, choose and configure the actual route from the graph. `media-ctl -p` gives entity names and pads; use its reported pad numbers to enable the CSIPHY-to-CSID and CSID-to-RDI links, and set matching sensor/subdevice formats before capture. Example shell variables must be filled from that graph, and the selected format must match the sensor and VFE:

```sh
media-ctl -d /dev/media0 --links "'$PHY':$PHY_SOURCE -> '$CSID':$CSID_SINK [1]"
media-ctl -d /dev/media0 --links "'$CSID':$CSID_SOURCE -> '$RDI':$RDI_SINK [1]"
media-ctl -d /dev/media0 --set-v4l2 "'$SENSOR':$SENSOR_SOURCE [fmt:$MBUS_CODE/${WIDTH}x${HEIGHT}]"
media-ctl -d /dev/media0 -p
v4l2-ctl -d "$VIDEO" --list-formats-ext
v4l2-ctl -d "$VIDEO" --set-fmt-video=width="$WIDTH",height="$HEIGHT",pixelformat="$PIXEL_FORMAT" --stream-mmap=4 --stream-count=5 --stream-to=/tmp/camera-test.raw --verbose
```

Set and check every intermediate pad as required by the graph. The pixel format is the fourcc listed by the selected video node, not the media-bus code. Check the configured graph and physical LED during capture; save kernel errors and negotiated format, count and byte size, then stop. Test the front only after the rear and use the same safety gate. RAW capture is diagnostic, not acceptance; use `cam`/qcam or Snapshot and SoftISP for RGB/YUV validation.

## Acceptance

- The rear and front sensors deliver RGB/YUV frames with correct colours through libcamera (RAW only does not count).
- The independently verified physical indicator LEDs follow every stream.
- IR emitter, flash and sensor strobe never operated.
