# Cameras test plan (rear OV13858 first)

One batched boot on the operator's own PC, live USB only (no install, S-rules in `plan/risks.md`).
Every step is read-only except binding the sensor driver, which reads the chip id. No `i2cdetect`
on the CCI buses (they carry an EEPROM and a lens actuator). The IR emitter and the flash are not
described in any DTB and must stay off (S2). Raw logs stay under `out/`.

## Contents required before boot

- Kernel with the five camera patches (`hardware/cameras/patches/0001`-`0005`), BTF on, and
  `CONFIG_VIDEO_QCOM_CAMSS=m`, `CONFIG_I2C_QCOM_CCI=m`, `CONFIG_VIDEO_OV13858=m`,
  `CONFIG_LEDS_GPIO=y`, `CONFIG_CLK_X1E80100_CAMCC=m`, `CONFIG_REGULATOR_QCOM_RPMH=y`
  (kernel worker to confirm against the Fedora config).
- The diagnostic DTB `x1p64100-microsoft-denali-cam-rear.dtb` (source
  `hardware/cameras/dtb-variants/`), selected as an extra boot entry. The packaged DTB keeps every
  camera node disabled.
- Fedora `libcamera`, `libcamera-tools` (`cam`, `qcam`), `v4l-utils`.

## Collector (before and after loading the modules)

```
dmesg | grep -i -E 'camss|cci|csiphy|camcc|ov13858|v4l2|media|privacy|led'
ls /sys/bus/i2c/devices; cat /sys/bus/i2c/devices/*/name 2>/dev/null | grep -i ov
ls /dev/media* /dev/video* /dev/v4l-subdev* 2>/dev/null
media-ctl -p 2>&1 | head -80
ls /sys/class/leds | grep -i -E 'indicator|camera'
cat /sys/kernel/debug/gpio | grep -E 'gpio(97|103|104|105|110|225) '
cat /sys/kernel/debug/regulator/regulator_summary | grep -i -E 'l[156]m|l[12]c'
cat /sys/kernel/debug/clk/clk_summary | grep -i -E 'cam_cc_mclk1|cam_cc_cci_0|cam_cc_csiphy1'
```

## Steps

1. Boot the variant DTB. Expected: `ov13858` probes on `cci0` bus 1 at `0x10` and reads the chip id
   (`0x300A`, value `0xD855` expected); if it reports `-ENODEV` or an I2C error, record the message
   and stop: the address, a rail or the reset polarity is wrong (see the open questions in
   `evidence/2026-10-30-camera-driver-reference.md`).
2. `media-ctl -p`: a CAMSS media graph with `msm_csiphy1`, a CSID, a VFE and the sensor entity.
3. RAW capture on the CAMSS RDI node (`v4l2-ctl --stream-mmap --stream-count=5`, SGRBG10 at 4224x3136).
4. While streaming, the LED `white:camera-indicator` (GPIO225) must light and go off when streaming
   stops. Record whether the physical LED beside the front camera lights (this decides the GPIO225
   and rear assumption).
5. libcamera: `cam -l` and a capture with the Software ISP; the result must be a coloured RGB or
   YUV picture, not RAW.
6. Record `/sys/kernel/debug/regulator` state before and after, to confirm all three rails return
   to off.

## Acceptance

- The rear sensor delivers RGB/YUV frames with correct colours through libcamera (RAW only does not count).
- The indicator LED follows streaming.
- IR emitter and flash never operated.
