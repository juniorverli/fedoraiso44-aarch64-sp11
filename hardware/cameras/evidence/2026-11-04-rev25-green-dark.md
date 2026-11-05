# Rev25-menu: two reported green, dark previews — 2026-11-04

## Scope and provenance

The operator reports that both the front IMX681 and the rear OV13858 now look
**green and dark** in Snapshot. The earlier rev24 report was a green/dark front
and a brighter, upside-down rear. These are visual reports, not image or
photometric measurements. No camera images, per-frame applied controls, RAW
statistics, lux, physical indicator observation, or Snapshot camera-selection
trace were supplied. Per the operator, rev25-menu has image-only audio changes
and the camera/kernel stack is unchanged from rev24. The safe boots below
identify kernel `7.3.0-65.sp11.24.fc44.aarch64`, Fedora libcamera
`0.7.2-2.sp11.fc44`, PipeWire libcamera plugin `1.6.11-1.fc44` and Snapshot
`50.0-1.fc44`. Do not infer a quality regression from an uncontrolled scene or
attribute the later report to a particular recorded boot.

The private sources are `out/device-logs/m16-20261104-menu/` and must remain
private. Compressed-file SHA-256 hashes, in journal / dmesg / extra-cameras
order, are:

- `c7139de9…`: `a7490e44bb505d93de987e13abf9558764f7999773e0e17333cc23ecb01be0be`,
  `e61893dc5f9512b6a6760eb1e5d408b9d504e48f54e9e7aadee137bbd4e6b1f2`,
  `c58063703a9a0b3166b2619f9da450627771731a032c572c0c4b67e705f08a26`.
- `e1f5555f…`: `e3d8a7b314fb41e66ac82062fbda585eaaa0d5ecfb11109663a7d0ddb9c02ad6`,
  `8a4552b8326783a1fe5b92895983405254f69a47b0557f5ce8c5bc48120314cc`,
  `5d49ad9869f2b1fcf55eaab14ce6cf3ebea364db2046eb4fd3100d931b496dc2`.

Both command lines say `sp11.entry=safe`, start `sp11-wireplumber-safe`, and
load the sensor-named YAMLs; EGL fails and SoftISP reports CPU debayer fallback.
The collector's blob SHA-256s are **only prefixes**: front
`095823de119975b7`, rear `ea677b2e20e8eef9`. A YAML filename or matching blob
prefix does not establish installed contents or IPA/helper binary identity.

## Sensor and stream attribution

In each boot the early, **idle** media graph binds `ov13858 4-0010` to
`msm_csiphy1` and `imx681 5-0010` to `msm_csiphy2`; their then-current pad
formats are 4224x3136 SGRBG10 and 3840x2640 SRGGB10 respectively. These are
not an active graph captured during Snapshot. In each boot the collector's
first `cam -l` encountered `EBUSY` setting rear `csiphy1 -> csid0` and listed
only the front as index 1; a second enumeration listed back as 1, front as 2.
WirePlumber was initializing at the same time, but the log does not establish
which process held the link. This is transient, incomplete discovery, not proof
that Snapshot substituted the front for the rear. Indices are not persistent
identifiers. The collector calls `cam -l` twice; the simple pipeline calls
`setupLinks()` during initialization (`out/ref/libcamera/src/libcamera/pipeline/simple/simple.cpp:635-649`).
Serialize discovery, retain errors and resolve IDs afresh before capture.

| Boot / monotonic time | Logged configuration and debayer input | Attribution and limits |
|:--|:--|:--|
| `c7139de9…`, journal through 122.64 s | No Snapshot launch, stream configuration, or debayer benchmark in the collected journal. Both cameras were added by WirePlumber. | Stream/application selection in this collected interval is **unknown**. Enumeration is not a stream. |
| `e1f5555f…`, 59.655 s | 1920x1080 XRGB8888/sRGB output; SoftISP input 3840x2160 RGGB-10-CSI2P, stride 4800 bytes; range 4–3550 lines / 1–15.5152 gain. At 61.861 s CPU debayer reports 30 frames. | **Strong inference: front IMX681**: size/code match its mode and reported range. |
| `e1f5555f…`, 66.817 s | Same processed output; input 2112x1188 GRBG-10-CSI2P, stride 2640 bytes; range 4–3206 lines / 0–63.9922 gain. At 68.998 s CPU debayer reports 30 frames. | **Strong inference: rear OV13858**: size/code match its built-in mode, `sources/linux/drivers/media/i2c/ov13858.c:1008-1015`, with per-mode code in camera patch 0013. |

Snapshot opens the camera portal immediately before these two configurations.
Their input formats and distinct ranges are evidence against *both logged
configurations* being the same front mode. The configuration log does not print
the unique camera ID or app/portal node ID; no sensor-identified active route,
frame contents or app selection were retained. The actual identity of either
preview the operator judged therefore remains unproved; another client or a
selection mismatch cannot be ruled out. CPU debayer's benchmark surrounds
actual buffer processing in `out/ref/libcamera/src/libcamera/software_isp/debayer_cpu.cpp:1068-1126`,
so 30 frames were processed for each inferred configuration; it does not prove
which physical lens was visible, that Snapshot displayed/saved them, or their
colour. Output stride, actual physical CFA/packing, bytes used, frame timestamps
and applied exposure/gain remain unknown. The numerical exposure and gain
ranges are advertised control limits, not per-frame settings.

Both boots log missing OV13858 selection rectangles and default the pixel array
and active area to 4224x3136. They also report unavailable sensor rotation for
both, no static IMX681 properties, and unverified sensor delays for both. A
rear `get_selection` implementation requires measured or independently sourced
native dimensions and mode crops; the current defaults do not prove the cause
of green or darkness.

## Colour path and hypotheses

The local, privately generated `imx681.yaml` and `ov13858.yaml` have SHA-256
`62abff64c40df86b06fdf1ce5600d94c8040b49de9e567e986e201679e51a72b` and
`9e3bcb8611792a0be89b97ec771e35ce2937a5eb0e4624044bada4b2cd56a9fa`.
Each contains a single BlackLevel, generic Awb, four CCT CCM entries, an Adjust
gamma key and an empty Agc. Their black and gamma entries differ, and both
local gamma keys differ from stock 2.2. Re-running the existing generator in
`--check-only --no-lsc-sidecar` mode and comparing its generated text in memory
shows both local YAMLs match its output from the catalogued private data:
front tuned-container SHA-256
`2c1c7fd9090e0bf338f44bd9de785509c1fbebc975facc5286f12865cf675f1d`;
rear `4858ccb297eeecbc8e9b6d673f7ab4b0ead559adf16e3fe717eea9e40ccef635`.
These are data containers and were not disassembled. The rear parser reports one
non-identity CCM variant with eight leaves reduced to four CCT entries; front
reports four non-identity variants among fourteen, with the selected variant's
four leaves mapped to four entries. This structural comparison does not prove
the chosen variants or transformations are correct. The logged installed YAML
paths do not prove these local files were installed. No private matrix is
reproduced here.

- The generator averages four interpreted black channels, takes a median over
  variants and assumes a conversion from an internal 14-bit scale to the
  16-bit libcamera YAML scale. The scale, selected use case and front nonzero
  `bls12` semantics are unverified. `blc.cpp:26-46` shifts to an 8-bit common
  level and a YAML value overrides helper fallback. For the local rear YAML,
  the quantized level equals the rear helper fallback; for front it differs.
  An incorrect pedestal can affect both brightness and AWB, especially in dim
  scenes. It is not an observed applied black level.
- `awb.cpp:46-93` uses black-subtracted global grey-world sums, caps red and
  blue gains at 4 and estimates CCT generically. `ccm.cpp:44-67` interpolates
  the sensor's table by that estimate, updating after 100 K changes. The
  generator chooses the first non-identity Windows-data variant and, where
  present, one presumed lux bin; band-centre mapping, matrix semantics and
  sensor use case are not validated. Its public reference is a lead, not a measured replacement.
  AWB metadata's CCT is calculated during statistics processing; record the
  frame's actual `ColourGains` and `ColourCorrectionMatrix` too, rather than
  assuming that CCT alone names the CCM already applied to that same frame.
- The existing SP11 `libcamera-sp11.patch` makes a YAML gamma usable and adds a
  rear black helper fallback; without that installed gamma patch the stock IPA
  ignores the gamma key. The generator fits the first tone LUT to a global
  power law. Gamma/contrast and clipping can alter perceived brightness or
  colour, but cannot be assigned a causal role from these logs. SoftISP lacks
  the private blobs' multi-illuminant lens shading and Windows processing.

**Priority, not probability:** (1) identify the two lenses and measure the
shared AWB/CCT/CCM path with fixed offline WB; (2) measure black pedestal and
its effect on RAW and colour, then tone/gamma; (3) compare centre and corners
for colour shading. Per-mode CFA, stride, packing and line integrity remain
checks for each sensor, not a reason to change the global Bayer order. A
neutral flat alone cannot establish red/blue pixel parity. No common code
failure, matrix, numerical tuning value, or app substitution is established.

## Darkness and orientation

Under a stable neutral scene, first compare each camera's converged RAW signal
and processed output with its actual exposure/gain and timing; then, if the
runtime can hold safe settings, compare common verified exposure times and
gains. Distinguish scene, field of view and optics from exposure/analogue gain,
AGC convergence/target, black subtraction and tone. Optical transmission,
aperture and physical sensor response are unmeasured. Libcamera metadata can
reflect delayed controls or an inferred line time; it is not independent sensor
readback. The front helper gain law and its line clock, and both sensors'
control delays, need measured response and timing. The advertised rear minimum
gain of zero is not a measured frame setting or evidence that zero gain was
applied. Do not invert or globally remap gain, increase limits, or change Bayer
based on apparent brightness.

The optional per-sensor 2.5-to-3.5 AGC patch and front private A/B generator
already exist, but are unbuilt and untested on the device. A brighter image
would not prove the root cause or a colour fix; prioritize RAW/metadata first,
then compare one sensor at a time only if indicated, tracking clipping and noise.

Candidate 0026 is a rear-only 180-degree **DT metadata** property, absent from
the rev24 kernel. With no writable sensor flips the simple pipeline returns an
identity transform; metadata alone does not force rotated pixels. If an
asymmetric, lens-identified target confirms the rear remains upside-down, test
a rear-only processed-frame 180-degree transform or a separately validated
sensor flip with correct Bayer propagation. Check direct capture, Snapshot
preview and saved images for mirroring and double rotation; do not rotate front.

## Targeted Windows REA: ISP path, not calibration

Both catalogued PE/ARM64 binaries were inspected read-only with REA 6.7.0,
Ghidra 12.1.4 and `REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A`; procedures
were listed before decompilation. Snapshots and pseudocode remain outside git.
The result is static Windows code evidence, not a Linux frame measurement:

- `sources/windows/DriverStore/qccamisp8380.inf_arm64_068a5d125dcec104/qccamisp8380.sys`,
  SHA-256 `64463b4d78894fdeee01ce87b51e3153662243e3fdf16f87596579b58617c21c`:
  procedure inventory `ev_0df24676440c2a635c3c5dacc8319e7fde546aca5cb62f230dfe8d6e58b21003`;
  IPE/BPS frame-process diagnostic string at `0x140031a28`, search
  `ev_c423836a32328643939329bc79ac295a3234f9adbb2cf28bbeb04f370c7e7400`,
  reference from `0x14000ab50`, xrefs
  `ev_daa37f43d6db47503f40580005d9be7932eb2c3a968bac7066d9f425cfa5d43f`;
  listed function `0x14000a650`, decompile
  `ev_f0c016a82facb21563397baf0d8ca9e91a5f4b5540b899563f8cc9aba4c42720`.
  The function contains IPE/BPS frame-process message handling and branches
  logging missing context and error conditions. This locates part of the Windows
  ISP request path; it does not resolve CCM ordering, AWB, black scale or gain.
- `sources/windows/DriverStore/surfacecamavs8380.inf_arm64_2b9eaefcbe9d3342/QcDeviceMFT8380.dll`,
  SHA-256 `c241b7fbb2ec54e439752a1ea7ad25da10ca740012a54bd0e7a87ea94a141c35`:
  procedure inventory `ev_b96c531207ca1261c20a373f5d2ce493128d3fb2a9755dcee617aa26e528a0a9`.
  The large DLL includes AWB/CCT and chromatix diagnostic strings, but this
  inventory alone does not establish their consumers or numerical semantics.

Ghidra reports unknown PDB load state, many function names/types are missing,
indirect references can be absent and the decompiler's inferred calling
conventions may be incomplete. No bad-instruction markers were seen in the
one decompilation; that is not an independent correctness check. The Windows
CCM consumer/axis order, front black scale and `bls12`, 3A-to-CCT mapping and
mode-to-tuning selection remain open. Do not convert the above observation into
coefficients or hardware settings.

## Next action

The [test plan](../test-plan.md) gives the ordered, LED-gated lens-identification,
RAW dark/flat/red/blue and fixed-WB identity/current-CCM experiment, followed by
exposure/tone and orientation checks. The [README requests](../README.md)
distinguish collector/diagnostic work, private libcamera/tuning, and kernel/DTB
work. No tuning fix or device acceptance is claimed from these logs.
