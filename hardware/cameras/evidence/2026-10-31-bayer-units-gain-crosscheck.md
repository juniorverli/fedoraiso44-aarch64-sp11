# Cameras: Bayer correction, line and frame length units, gain laws (cross-check of the Flash findings)

Date: 2026-10-31. Inputs: `2026-10-31-rea-bayer-poll-units.md` (Gemini Flash REA, only the Bayer map re-derived by the orchestrator),
the three Windows module files read by `hardware/cameras/userspace/parse-camera-module.py` and the builder, and the upstream
`vd55g1.c` of Linux 7.3. No REA was used in this session. Structure and ratios only: no register address, value or table is
quoted (S5). Grades follow `agents/protocol.md` section 5.

## 1. Bayer order and the generator

Verified (orchestrator, jump table of `CamX::ImageSensorData::TranslateColorFilterArrangement` in `QcDeviceMFT8380.dll`): module
colour code 0 is BGGR, 1 GBRG, 2 GRBG, 3 RGGB, 4 monochrome.

| Sensor | Module code | Order | Media bus code for the 10 bit data the modes state | Grade |
|:--|:--|:--|:--|:--|
| Rear OV13858 | 0 | BGGR | `MEDIA_BUS_FMT_SBGGR10_1X10` | Verified |
| Front IMX681 | 3 | RGGB | `MEDIA_BUS_FMT_SRGGB10_1X10` | Verified (was an unverified default) |
| IR VD55G0 | 4 | monochrome | `MEDIA_BUS_FMT_Y10_1X10` | Verified |

`build-camera-firmware.py` now reads the code from every mode record, requires one code per module and requires the code the profile
expects, derives the bus code from the order and the bit depth of the stream configuration (8, 10 or 12 bit, consistent with its MIPI
data type), and stops on anything else. `--bayer` and `--bayer-imx681` remain only as an override of a colour sensor: a value that
differs from the verified order prints a loud note and the manifest records `OVERRIDE`. A Bayer override for the monochrome IR is
refused. The manifest records for each sensor `bayer`, `bayer_source` ("Verified REA 2026-10-31: module code N = order") and
`module_color_code`. The IMX681 media bus code is the same as before (the old default happened to be right); the OV13858 code changed
from GRBG to BGGR; the IR code is unchanged.

### 1.1 Why the earlier GRBG inference was wrong, and a consistency check

The earlier survey argued "even window origins and the same flip bits as the Linux full mode, so the Windows order equals the Linux
order GRBG". Re-reading both sides:

- Linux `ov13858.c` reports `MEDIA_BUS_FMT_SGRBG10_1X10` only (`sources/linux/drivers/media/i2c/ov13858.c:1161`, `:1284`). The
  statement that BGGR matches the upstream driver does not hold for this tree: the 7.3 driver reports GRBG.
- Linux's own modes program an **odd** vertical window origin (low byte of the Y offset odd in all four modes,
  `ov13858.c:247`, `:438`, `:629`, `:820`). The Windows modes program an **even** one in all three modes (parity read from the module,
  value not recorded). An odd vertical shift swaps the two row pairs of a Bayer pattern, which turns BGGR into GRBG.
- So the two facts agree: native or even-origin output is BGGR (Windows), the Linux odd Y origin gives GRBG. Grade: Inference (a
  consistency check of the verified table, not an independent proof of it). The horizontal origin parity is even on both sides.
- Bits 3 and 4 of the first flip/format register differ between every Windows mode and the Linux full mode; bits 0 to 2 are equal. The
  meaning of bits 3 and 4 is not established. Unknown.
- Consequence for the kernel: built-in Linux modes stay GRBG (their register tables are Linux's, odd origin); every blob mode is BGGR.
  A driver that enumerates and accepts only GRBG (`ov13858.c:1280-1284`, patches 0002 and 0013) mislabels blob frames.

## 2. Line length and frame length units (Flash section 3.5)

Cross-check from the module (per mode, ratios only). Let `K = hts x vts x fps`, with `hts` at +0x24, `vts` at +0x28, `fps` the double at
+0x40, and `pix` the output pixel clock at +0x34.

| Claim | Check | Result | Grade |
|:--|:--|:--|:--|
| `lineLength` (+0x24) is the sensor's own line-length register value | the mode's register sequence writes the sensor line-length register (OV13858 hts pair, IMX681 CCS line length pair, VD55G0 line-length pair at the same address as `VD55G1_REG_LINE_LENGTH`, `vd55g1.c:47`); compared with +0x24 | equal for all 3 OV13858 modes, IMX681 modes 0 to 4, the VD55G0 mode; IMX681 mode 5 (the dropped presence mode) differs | **Verified** (unit = the sensor register unit) |
| that unit is "pixel clock cycles" of the module's pixel clock | `pix / K` | not 1: 4.3837 (OV13858), 0.7620 (IMX681, modes 0 to 4; 4K at 60 and at 30 fps differ by exactly 2 in `hts x vts`), 0.5968 (VD55G0). Constant per sensor across modes | **Refuted as stated** for the +0x34 clock; the clock the cycles refer to is **Unknown** (IMX681 mode 5 has a third ratio, 0.9107, so it is not a sensor constant either) |
| `frameLength` (+0x28) is an integer line count | `fps x hts x vts` is mode independent per sensor (above); `vts` exceeds the height in every mode; VD55G1 sibling default frame length of 1860 lines for 60 fps (`vd55g1.c:126`) is within 5 percent of the VD55G0 module frame length | consistent | **Inference** (the frame-length register is not written by the IMX681 mode sequences, so it is not cross-checked against a register) |

What each claim would change:

- imx681 (patch 0016, amend later). The generator passes `hts` unscaled and `pix` as `pixel_rate`; a consumer that computes line time or
  frame rate as `hts x vts / pixel_rate` gets 0.762 of the true frame rate (22.9 fps for a 30 fps mode). Options, all to be decided by the
  kernel worker: (a) report `HBLANK` read-only and never derive a frame interval from `pixel_rate`; (b) have the builder emit
  `K`-consistent values, that is a pixel rate equal to the line clock `K / (vts per second)`, which is exact arithmetic on Verified data
  but changes the meaning of the SRB `pixel_rate` field (CAMSS must still take the link frequency from `V4L2_CID_LINK_FREQ`, not from
  the pixel rate). Until one is chosen libcamera line-time estimates for the IMX681 are wrong by that factor.
- The OV13858 builder uses `hts_scale = 4`; the ratio above is 4.3837 / 4 = 1.096, so the derived frame rate of a blob mode is 9.6
  percent above its Windows rate. The OV13858 driver keeps its own `hts` limits; flagged, not changed.
- VD55G0 handling. The line length is a sensor register in the same unit family as the VD55G1 (`vd55g1.c:47`, minimum `:122`, the
  module value exceeds that minimum); the VD55G1 driver derives hblank from `pixel_clock = sys_clk / pixel_div` (`vd55g1.c:829`), which
  is the line clock, not the MIPI pixel clock, consistent with the finding. No change to the VD55G1 hblank logic is implied; the
  generator's `pixel_rate` for the IR is not the line clock either.

## 3. Gain register laws (Flash section 3.6)

| Claim | Cross-check | Grade |
|:--|:--|:--|
| VD55G0 analogue gain: `G = 32 / (32 - code)`, code 0 to 28 (cap 0x1c), `G` 1.0 to 8.0 | upstream `vd55g1.c` uses the same law (`vd55g1.c:973`), the same range (`:1608-1609`, 0 to 0x1c) and a default code of 19 (`:119`) | the law on the VD55G1 sibling is **Verified** in Linux source; for the VD55G0 it is **Inference, strong** (Flash read the Windows function, not re-read here) |
| the VD55G0 module sets the gain | the module's mode and init sequences write no gain register (the VD55G1 manual-gain and digital-gain addresses are absent) | **Verified**: gain is set at run time, not in the module |
| IMX681 analogue gain is MIPI CCS code `0x0204`, linear `G = code / M` | the module's mode sequences write the CCS analogue-gain pair, the CCS digital-gain pair, the CCS line-length pair; the survey named the CCS digital-gain and short-exposure addresses; the digital default is the 8.8 fixed-point unity (0x0100); the analogue default code written is 0 in every mode | the register map is CCS-compatible: **Inference, strong** (4 CCS addresses match). `code / M` with M positive and a default code of 0 would mean zero gain at start: the claim is **not supported as stated**; a law with an offset, or a reciprocal law as on the VD55G0, fits a default of 0. The law and M are **Unknown** |
| `imx681.cpp` has only mode selection | consistent with `realToRegGain` and `regToRealGain` being stubs in the module (earlier survey); the generic CamX CCS gain path may hold the law | **Inference** |

What each claim would change:

- imx681 (0016): nothing may hardcode a gain law. The gain control stays in code units and exists only if the blob lists it
  (`--ccs-controls --again-range`, whose min, max and step are Unknown). The default analogue code is not a usable AE start value.
  libcamera has no gain helper for the IMX681 until the law is measured or found.
- VD55G0: `vd55g1.c` already implements the law and range; if the VD55G1 driver is extended to the VD55G0 (patch 0017) the gain control
  needs no change. A libcamera `CameraSensorHelper` for the IR needs `32 / (32 - code)`.

## 4. Still Unknown

1. The clock the line length is counted in (IMX681, VD55G0, OV13858).
2. The IMX681 analogue gain law, range and step.
3. The meaning of flip/format bits 3 and 4 in the OV13858 Windows modes.
4. IMX681 frame-length register and whether its mode sequences rely on a default.

## 5. Requests

- kernel (patches 0002 and 0013, ov13858): report and accept `MEDIA_BUS_FMT_SBGGR10_1X10` for blob modes while keeping
  `MEDIA_BUS_FMT_SGRBG10_1X10` for the built-in Linux modes (per-mode code in `enum_mbus_code`, `set_fmt` and try format). The builder
  already writes BGGR into every OV13858 blob mode.
- kernel (patch 0016, imx681): confirm the driver takes the bus code only from the blob (RGGB now Verified, no hardcoded GRBG or RGGB
  default); decide the hblank, pixel-rate and frame-interval policy of section 2; no gain law; gain control only from blob records.
- kernel (patch 0017 and `vd55g1.c`): confirm the mono path advertises Y10 for the VD55G0 blob (the blob code is `Y10_1X10`); the gain
  control needs no change.
- image (libcamera and tuning): OV13858 SoftISP tuning and any `uncalibrated.yaml` must assume BGGR for blob modes (GRBG for built-in
  modes); IMX681 RGGB; IR Y10 without debayer; IR gain helper `32 / (32 - code)`; no IMX681 gain helper yet.
- orchestrator: `README.md` section 2 table row for the OV13858 and the log (Verified GRBG is wrong for blob modes); `test-plan.md` lines
  42 to 46 (expected `SGRBG10` for built-in, `SBGGR10` for blob modes); close the IMX681 Bayer question of R5 (`rea-seven-questions.md` Q6
  and U1 of `front-ir-rgb.md`); REA slot: where `hts` is counted (line clock), and the CamX IMX681 gain conversion.

## 6. Generator run and parser test (this machine, 2026-10-31)

Three blobs regenerated into `out/firmware-private/cameras/` (mode 0600, outside the repository): OV13858 3 modes bus code BGGR,
IMX681 4 modes RGGB, VD55G0 1 mode Y10 with 7 polls; all SRB v2, manifest records the source of each order. The real, unmodified
`sensor-regblob.h` of patch 0011 was compiled with `-fsanitize=address,undefined` against a small kernel header shim (exact-size heap
buffers; scratchpad, not in git). Per blob: parsed as v2, every mode accessor and operation list run against a fake device (the VD55G0
polls complete, `apply = 0`); every truncation rejected; every payload byte flip rejected (stale CRC); 6000 random mutations with the
CRC repaired and 30 percent truncated gave about 2100 accepted, about 3900 rejected, no ASAN or UBSAN report, no leak. Header-byte
flips are accepted for 14 to 23 of 64 positions per blob because the CRC covers only the payload and those bytes (identification
register and value, reserved bytes) are valid in any value; this was already the case for the earlier blobs.

## 7. Patch amendment (2026-10-31, cameras worker, for kernel build M15)

No REA used. Patches 0013 and 0016 and the libcamera helper were amended in place; 0001 to 0012, 0014, 0015 and 0017 to 0019 are byte for byte unchanged.

| Item | Change | Grade of the underlying fact |
|:--|:--|:--|
| 0013 ov13858 | `struct ov13858_mode` gets `code` (0 = built-in, reported as SGRBG10). Blob modes carry the blob code (BGGR for the Windows modes), any RAW10 Bayer code is accepted, none = SGRBG10. `enum_mbus_code` lists the distinct codes, `enum_frame_size` indexes the modes of the requested code, `set_fmt` picks the nearest mode of the requested code (any mode when no mode has it) and reports the code of the selected mode; `get_fmt`, the try format and `open` follow `cur_mode`. The binding (0012) is not affected | Verified (blob BGGR); odd Y origin of the Linux modes: Inference (section 1.1) |
| 0016 imx681 gain | Analogue gain control codes 0..479, step 1, default 0 (law `512 / (512 - code)`, 1.0x to 15.5x); new `V4L2_CID_DIGITAL_GAIN`, Q8, 256..1024, register 16 bit `0x020e`. The analogue register still comes from the blob record, the digital register is a driver constant. Both controls exist only when the blob lists a gain register | Per Windows analysis, unconfirmed on hardware (law and register named by `2026-10-31-rea-tuning-layouts.md` 4.2; the CCS global digital gain address and the unity default 0x0100 the mode sequences write agree with it) |
| 0016 imx681 clock | `V4L2_CID_PIXEL_RATE` now reports the line-length clock, `pixel_clock * 1000 / 762` (module clock over the constant 0.7620 of section 2), a documented driver constant: the blob header has no field for it and the evidence supports a per-sensor constant (constant over IMX681 modes 0 to 4), so the blob format is unchanged. Hblank, vblank and exposure limits stay in the blob units (line length and frame length equal the sensor registers, exposure in lines), so they do not depend on the clock; only frame time derived from the pixel rate changes (30 fps is no longer read as 22.9 fps). Probe rejects a pixel rate that overflows 32 bits after the conversion | Inference (ratio verified on module arithmetic, the clock it refers to is still Unknown) |
| 0016 imx681 colour | Header comment updated: RGGB Verified, the driver has no default code and still rejects a blob without a RAW10 Bayer code | Verified |
| libcamera | `userspace/quality/libcamera-sp11-imx681-helper.patch` replaces the `.in` template: `AnalogueGainLinear{ 0, 512, -1, 512 }` (same model as the imx219 helper, gain = 512 / (512 - code)), no black level (scale not established, quality-parity U6) | Per Windows analysis, unconfirmed on hardware |

Checks, all on the full composed tree (v7.3, the 50 non-camera series patches, ec-sam 0005, then 0001 to 0019): all 19 camera patches apply in order with `git am`; `ov13858.o` and `imx681.o` build with `W=1` in the Fedora 44 container without a warning; `checkpatch.pl --strict` on the two amended patches reports only the Signed-off-by error; the libcamera helper applies to a clean v0.7.2 and after `libcamera-sp11.patch`, and the simple pipeline and IPA build (meson/ninja, Fedora 44 container) with `imx681` registered. The blob format and `sensor-regblob.h` are untouched, so the ASAN/UBSAN parser harness was not rerun. Not exercised: a probe with a blob (no device), enumeration with a mixed GRBG/BGGR mode list (read-checked only).
