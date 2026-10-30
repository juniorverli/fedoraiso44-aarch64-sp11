# Cameras test plan (rear OV13858 first, then front IMX681, IR node inert)

One batched boot on the operator's own PC, live USB only (no install, S-rules in `plan/risks.md`).
Every step is read-only except binding the sensor drivers, which read the chip id and, when the user asks,
stream. No `i2cdetect` on the CCI buses (they carry an EEPROM and a lens actuator). The IR emitter, the PMIC
flash and the sensor strobe are not described in any DTB and must stay off (S2). Raw logs stay under `out/`.

## Contents required before boot

- Kernel with the camera patches `hardware/cameras/patches/0001`-`0019` (CAMSS C-PHY 0006-0010, register blob parser
  0011, OV13858 blob modes 0012-0014, IMX681 0015-0016, VD55G0 binding 0017, front and IR DT 0018-0019), BTF on, and
  `CONFIG_VIDEO_QCOM_CAMSS=m`, `CONFIG_I2C_QCOM_CCI=m`, `CONFIG_VIDEO_OV13858=m`, `CONFIG_VIDEO_IMX681=m`,
  `CONFIG_CRC32=y`, `CONFIG_LEDS_GPIO` (m or y), `CONFIG_CLK_X1E80100_CAMCC=m`, `CONFIG_REGULATOR_QCOM_RPMH=y`,
  `CONFIG_DMABUF_HEAPS_SYSTEM=y` (kernel worker to confirm against the Fedora config).
- The diagnostic DTB `x1p64100-microsoft-denali-cam-all.dtb` (source `hardware/cameras/dtb-variants/`), selected as an
  extra boot entry; `...-cam-rear.dtb` stays available for a rear-only boot. The packaged DTB keeps every camera node
  disabled.
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

1. Boot the `cam-all` variant. Expected, rear: `ov13858` probes on `cci0` bus 1 at `0x10` and reads the chip id (`0x300A`,
   `0xD855` expected); with the blob it logs `3 modes loaded from ov13858-mshw0491.bin`. If it reports `-ENODEV` or an
   I2C error, record the message and stop: the address, a rail or the reset polarity is wrong.
2. Front: `imx681` logs either the missing/invalid blob, or the chip id the sensor returned (`chip id 0x..., the register
   blob expects 0x...`). The read value is the first hard evidence of the front bus, address and power sequence; record it
   even when it mismatches. The IR node at `0x60` has no driver: nothing is read, only the rails exist.
3. `media-ctl -p`: a CAMSS media graph with `msm_csiphy1` (rear), `msm_csiphy2` (front), CSIDs, VFEs and the sensor entities.
4. RAW capture on the CAMSS RDI node of the rear camera (`v4l2-ctl --stream-mmap --stream-count=5`, `SGRBG10` at 4224x3136
   built-in mode, then each of the three blob modes 4076x2806, 4064x2286, 3736x2802). Check the Bayer order of the blob
   modes against a coloured target (U1).
5. Front RAW capture (3840x2640 and the other three sizes). Check dmesg for CSIPHY or CSID errors first: this is the first time
   a C-PHY link runs (U2). Read the Bayer order from a coloured target; if red and blue are swapped in the Software ISP
   picture, rebuild the blob with the other `--bayer` value.
6. Indicators: while the rear streams, the LED `white:indicator-1` (GPIO105) must light and go off when streaming stops.
   While the front streams, `white:indicator` (GPIO225) must light and go off. Record which physical LED lights. Do not
   stream the front and the IR sensor together (the shared LED has no use count, U9; the IR sensor cannot stream anyway).
7. libcamera: `cam -l` and a capture with the Software ISP; the result must be a coloured RGB or YUV picture, not RAW. With the
   `uncalibrated` tuning only grey-world white balance applies; the front has no sensor helper, so automatic exposure may be
   poor.
8. Record `/sys/kernel/debug/regulator` state before and after, to confirm all rails return to off.

## Acceptance

- The rear and front sensors deliver RGB/YUV frames with correct colours through libcamera (RAW only does not count).
- The indicator LEDs follow streaming.
- IR emitter, flash and sensor strobe never operated.
