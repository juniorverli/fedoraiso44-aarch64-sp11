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
deferred devices, blob names with a SHA-256 prefix, bound I2C devices (no bus scan), `media-ctl -p` for every media
device, `v4l2-ctl --list-devices`, per-video-node `--list-formats-ext`, subdev media bus codes and controls, `cam -l`,
the LED class state, GPIO, pinmux, regulator and clock state. It only enumerates formats; it never streams or writes.
Graph and video-format enumeration runs first, has a 55-second aggregate budget and short per-command timeouts to fit
the log collector's 90-second drop-in deadline. Any timeout or exhausted budget is marked `INCOMPLETE`; the collector
must preserve those markers rather than truncate them silently.

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

Read-only graph and enumeration (save output through the collector):

```sh
for m in /dev/media*; do media-ctl -d "$m" -p; done
v4l2-ctl --list-devices
for v in /dev/video*; do v4l2-ctl -d "$v" --list-formats-ext; done
ls -l /dev/v4l-subdev*
cam -l
journalctl -k -b | grep -Ei 'camss|csiphy|csid|vfe|ov13858|imx681|cci'
```

Expected RGB graph after applying the no-IR exclusion: rear OV13858 (`cci0`, master 1, DT bus 1/address 0x10) has a
sensor source link to `msm_csiphy1` (four-lane D-PHY); front IMX681 (`cci1`, master 1, DT bus 1/address 0x10) links to
`msm_csiphy2` (one C-PHY trio). Both sensor entities, CAMSS CSIPHY/CSID/VFE entities, the CAMSS video nodes and V4L2
subdevice nodes should exist once the async notifier completes. The sensor-to-CSIPHY links are expected enabled and
immutable. CSIPHY-to-CSID and CSID-to-VFE RDI links are expected to exist but start disabled/configurable; userspace
must enable a complete route. There must be no IR sensor entity, CSIPHY0 sensor link, or IR endpoint. These expected
topology details derive from the camera DT patches 0005/0018 and exclusion patch 0022; they are not yet verified in the
rev18 runtime graph. TPG entity-type warnings were seen in rev18; by themselves they do not show a sensor path failure.
Linux I²C adapter numbers are assigned at runtime: rev18 logged the rear at `7-0010`, so do not assume the DT bus
number appears as the Linux device prefix.

If sensor entities or their immutable links are absent, collect `media-ctl -p` and notifier/async dmesg and stop
before streaming. A bound sensor and mode-table log proves probe/mode parsing only. A missing sensor-to-CSIPHY link
points first to the effective DT endpoint/exclusion or incomplete CAMSS notifier. If the links and subdevices exist,
query formats at each stage; C-PHY lane/rate setup (front only), CSID input configuration, disabled or mismatched
CSID-to-RDI routing, VFE format/stride, or a sensor mode whose PLL/link-frequency/lane data do not match the DT can
still produce no frame. CAMSS VFE680 is RDI-only and does not demosaic RAW Bayer; absent/unusable libcamera SoftISP,
IPA helper or tuning explains a black/unsupported application preview after RAW capture succeeds, not a missing raw
frame. Rev18 has no graph nor capture attempt, so none of these candidates can yet be selected as the cause.

For RAW debugging after the privacy gate, choose and configure the actual route from the graph. `media-ctl -p` gives entity names and pads; use its reported pad numbers to enable the CSIPHY-to-CSID and CSID-to-RDI links, and set matching sensor/subdevice formats before capture. Example shell variables must be filled from that graph, and the selected format must match the sensor and VFE:

```sh
media-ctl -d "$MEDIA" --get-v4l2 "'$SENSOR':$SENSOR_SOURCE"
media-ctl -d "$MEDIA" --set-v4l2 "'$SENSOR':$SENSOR_SOURCE [fmt:$MBUS_CODE/${WIDTH}x${HEIGHT}]"
media-ctl -d "$MEDIA" --set-v4l2 "'$PHY':$PHY_SINK [fmt:$MBUS_CODE/${WIDTH}x${HEIGHT}]"
media-ctl -d "$MEDIA" --set-v4l2 "'$CSID':$CSID_SINK [fmt:$MBUS_CODE/${WIDTH}x${HEIGHT}]"
media-ctl -d "$MEDIA" --links "'$PHY':$PHY_SOURCE -> '$CSID':$CSID_SINK [1]"
media-ctl -d "$MEDIA" --set-v4l2 "'$CSID':$CSID_SOURCE [fmt:$MBUS_CODE/${WIDTH}x${HEIGHT}]"
media-ctl -d "$MEDIA" --set-v4l2 "'$RDI':$RDI_SINK [fmt:$MBUS_CODE/${WIDTH}x${HEIGHT}]"
media-ctl -d "$MEDIA" --links "'$CSID':$CSID_SOURCE -> '$RDI':$RDI_SINK [1]"
media-ctl -d "$MEDIA" -p
media-ctl -d "$MEDIA" --get-v4l2 "'$SENSOR':$SENSOR_SOURCE"
media-ctl -d "$MEDIA" --get-v4l2 "'$PHY':$PHY_SINK"
media-ctl -d "$MEDIA" --get-v4l2 "'$CSID':$CSID_SINK"
media-ctl -d "$MEDIA" --get-v4l2 "'$RDI':$RDI_SINK"
v4l2-ctl -d "$VIDEO" --list-formats-ext
v4l2-ctl -d "$VIDEO" --set-fmt-video=width="$WIDTH",height="$HEIGHT",pixelformat="$PIXEL_FORMAT" --stream-mmap=4 --stream-count=5 --stream-to=/tmp/camera-test.raw --verbose
```

Set and check every intermediate pad as required by the graph. The pixel format is the fourcc listed by the selected video node, not the media-bus code. Check the configured graph and physical LED during capture; save kernel errors and negotiated format, count and byte size, then stop. Test the front only after the rear and use the same safety gate. RAW capture is diagnostic, not acceptance; use `cam`/qcam or Snapshot and SoftISP for RGB/YUV validation.

The capture command starts streaming and is a manual diagnostic only: do not run it until the camera-to-indicator
mapping is independently verified and the physical privacy LED is visibly on. If capture returns frames, compare
the output byte count with the negotiated size and verify the RAW mosaic is nonzero. A working RAW capture but black
libcamera preview directs investigation to the installed SoftISP, sensor helper, tuning, Bayer order and controls.
`cam -l` with no camera points back to graph completion or libcamera pipeline matching.

## Acceptance

- The rear and front sensors deliver RGB/YUV frames with correct colours through libcamera (RAW only does not count).
- The independently verified physical indicator LEDs follow every stream.
- IR emitter, flash and sensor strobe never operated.
