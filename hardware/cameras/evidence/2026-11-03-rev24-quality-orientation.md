# Rev24 camera quality and orientation — 2026-11-03

## Evidence and attribution

The operator reports rear upside-down and brighter, and front green and dark, in
Snapshot on safe boot `f736d653-ea76-4073-a5f7-08478e70b7d6`. This is a
reported visual observation; no image, chart, per-frame metadata, lux reading or
physical LED observation is in the bundle. Debug boot `e28d7229` reset; its
cause is for the GPU owner and is not attributed here. The local Orca runtime
reported `app.running=false`, so no direct worker message was delivered; the
GPU handoff is in README requests.

Safe `journal.txt.gz` SHA-256
`06f22c07697e9bb1d8508d4248edaa9dc95556ad50628b0f838a21ed60f77814`;
`devicetree.dts.gz` SHA-256
`917a0ece3e62a6615568545df9b69534159ce04435686e433d885cefdef03aba`.
The boot is `sp11.entry=safe`, kernel `7.3.0-65.sp11.24.fc44.aarch64`,
libcamera `0.7.2-2.sp11.fc44` and PipeWire `1.6.11-1.fc44`. WirePlumber
selects softpipe, EGL initialization fails and libcamera explicitly falls back
to **CPU debayer**. It adds both cameras, uses the named sensor YAMLs and
Snapshot requests 1920x1080 XRGB8888/sRGB. The log includes a 30-frame CPU
benchmark for each configuration. Together with the operator's preview report
this is evidence of working safe streams through the RGB path, not a colour or
LED acceptance test. Retain the rev24 active-trio/CSID/VFE stack and safe
wrapper; the separate effects of those kernel changes are not isolated.

| Safe stream, identified by immediately following SoftISP input | Input | Advertised IPA range, **not the selected frame value** |
|:--|:--|:--|
| Front IMX681 | 3840x2160 RGGB-10-CSI2P, stride 4800 | exposure 4–3550 **lines**, gain 1–15.5152, reported step 0.00195695 |
| Rear OV13858 | 2112x1188 GRBG-10-CSI2P, stride 2640 | exposure 4–3206 **lines**, gain 0–63.9922, reported step 0.0078125 |

The original report transposed these ranges. The nearby input format makes the
mapping above clear (`journal.txt.gz` at monotonic 91.356–91.357 s and
103.392–103.393 s, repeated later). `soft_simple.cpp:209-258` derives the
ranges from V4L2 control information and a sensor helper; neither exposure nor
gain in this log is a per-frame measurement. The reciprocal front range is
consistent with the IMX681 helper, but does not prove the precise installed
helper binary or its hardware response. The exposure endpoints are lines, not
microseconds, and the stated gain endpoints are not comparable sensor
sensitivity. The installed blob hashes in `extra-cameras.txt.gz` are only
prefixes: front `095823de119975b7`, rear `ea677b2e20e8eef9`. Full installed
tuning, helper, IPA and blob hashes remain to be collected.

The Fedora local build manifest identifies source RPM
`libcamera-0.7.2-2.fc44.src.rpm`, SHA-256
`fcdf4e1d5dea9e2820e3589b180885edcca1b66aedb06a49f6cebcede734cdb1`.
The matching `libcamera-debugsource-0.7.2-2.sp11.fc44.aarch64.rpm` contains
AGC, AWB, CCM, CameraSensor and simple-pipeline sources byte-identical to the
local v0.7.2 reference used below. Its `soft_simple.cpp` differs: it computes
the logged minimum gain step from helper gain differences at the endpoints,
whereas the local v0.7.2 file divides the range by 100. The logged front
0.00195695 and rear 0.0078125 are consistent with the **Fedora build source**;
neither proves a physical gain response. Do not use the local file's step
formula to interpret this boot. The running device's full IPA binary hash is
still not in the log.

## Orientation: candidate, not yet an end-to-end correction

**Verified:** effective safe DT has `orientation = <1>` on rear and `<0>` on
front, and no `rotation` on either sensor. The media binding
`sources/linux/Documentation/devicetree/bindings/media/video-interface-devices.yaml:33,390`
distinguishes rotation from location. The v7.3 OV13858
`sources/linux/drivers/media/i2c/ov13858.c:1629-1638` and our IMX681 patch
`0016:420-424` both parse fwnode properties and create controls; no new
sensor control implementation is needed. The kernel fwnode parser
`sources/linux/drivers/media/v4l2-core/v4l2-fwnode.c:831-857` reads them
separately, and `v4l2-ctrls-core.c:2897-2902` creates read-only
`V4L2_CID_CAMERA_SENSOR_ROTATION` from `rotation`. This is **not** the generic
`V4L2_CID_ROTATION` video-processing control. Its direction and meaning are in
`sources/linux/Documentation/userspace-api/media/v4l/ext-ctrls-camera.rst:544-550`.

Libcamera v0.7.2 `out/ref/libcamera/src/libcamera/sensor/camera_sensor_legacy.cpp:598-620`
reads that control or warns and assumes 0. Both warnings occur in safe logs.
**Inference:** rear 180 is the smallest candidate for the reported upside-down
rear, subject to confirming that the image is a pure rotation rather than a
mirror and that no app already transforms it. Candidate
`patches/0026-candidate-arm64-dts-qcom-denali-rear-camera-rotation.patch`
adds only `rotation = <180>` to rear. Front default zero has not been
independently checked with an asymmetric target; no front value is asserted.

Crucially, libcamera v0.7.2 checks for **both writable sensor flips**
(`camera_sensor_legacy.cpp:360-371`); neither sensor driver supplies them.
`computeTransform()` then returns identity and adjusts the requested
orientation to the mounting orientation (`:937-967`), while the simple
pipeline calls it during validation (`pipeline/simple/simple.cpp:1144-1147`).
The DT patch should expose accurate metadata but does **not** by itself
rotate the pixels for Snapshot. Verify whether each consumer honors it; if
not, image/userspace must provide a tested rear-only 180-degree processed-frame
conversion or validated sensor flip support with correct Bayer-layout
propagation. Do not invent OV13858 register bits or rotate the front. Avoid
double rotation for consumers that honor the metadata. Validate both mirror
and rotation using readable asymmetric text in preview **and saved output**.

## Front green versus front dark

The local private generated YAML has SHA-256
`62abff64c40df86b06fdf1ce5600d94c8040b49de9e567e986e201679e51a72b`;
it has BlackLevel, generic Awb, four CCT CCM entries, Adjust gamma and an empty
Agc node. The device log names the installed file but does not prove it has that
hash. No Windows-derived coefficients are copied here. The generator selects
the first non-identity CCM variant and one lux bin; the chosen front use case,
black-level scale and matrix semantics remain unverified
(`2026-10-31-quality-parity.md`, inferences 3, 4, 6 and 7). The reference
`out/ref/sp11-imx681-linux/userspace/libcamera/smiapp-windows.yaml` also uses
Windows-derived CCMs, but targets a different stack and is not a validated
replacement. Its soft-IPA patch is based on v0.7.0 and changes a **global**
histogram MSV target 2.5 to 3.5; the comment says 3.1 but the code says 3.5.
It also tunes gamma/contrast/saturation; the existing v0.7.2 local patch tunes
only gamma and rear helper black. Do not import reference matrices or change
several adjustments together.

**Green hypotheses:** incorrect actual CFA/packing or stride, black pedestal,
generic grey-world AWB or its CCT/CCM selection, an unsuitable CCM, or colour
shading. Configured RGGB does not physically prove RGGB. The v0.7.2 AWB
(`out/ref/libcamera/src/ipa/simple/algorithms/awb.cpp:43-92`) uses black-
subtracted global colour sums with R/B gains capped at 4 and an estimated CCT;
CCM interpolation uses that CCT (`ccm.cpp:30-67`). A neutral RAW flat plus
separate red and blue targets, central and corner channel means, dark frame,
and per-frame ColourGains/ColourTemperature/ColourCorrectionMatrix can
separate CFA, AWB and CCM effects. Compare the *same* RAW offline with fixed
measured WB and identity versus current CCM; only then design a separately
named measured CCM/AWB trial. RAW green imbalance can also be physical spectral
response; processed colour neutrality is the meaningful target.

**Dark hypotheses:** actual scene, aperture/optics and sensor area, exposure,
analogue/digital gain response, frame length/line-time, black pedestal, AGC
target, gamma or tone mapping. Sensor dimensions, f-number and transmission
for these modules are not established here; do not assert the rear's apparent
brightness is physically inevitable. Compare a stable, unsaturated neutral
scene at identical illumination and geometry, first with their own auto
settings and then fixed, verified common exposure time and gains where supported.
Record per-frame ExposureTime, AnalogueGain, digital-gain readback if available,
AWB/CCT/CCM, sensor mode, line time, VBLANK, frame rate, RAW channel means,
noise and clipped fractions, and processed output. Correct for different
fields of view and pixel/area binning; this comparison is not a calibrated
quantum-efficiency or lens-transmission measurement. ExposureTime uses the
driver's reported line duration, whose front clock is inferred; confirm with
frame timing. No values for actual exposure or gain are present in this bundle.

Do not assume the v0.7.2 simple IPA exposes manual AE/AWB controls: its Agc
has no request-control handler and continuously writes sensor exposure/gain
(`agc.cpp`; `soft_simple.cpp:299-328`). Confirm runtime controls; if manual
capture is unsupported, request an isolated diagnostic path that suspends the
IPA loop and records applied controls without bypassing the stream/LED gate.
Do not race direct V4L2 writes against AGC or raise limits. Our helper assumes
`512/(512-code)` from prior analysis; the public reference's gain statements
conflict (`2026-11-03-rev24-reference-comparison.md`). A measured safe V4L2
control sweep with latency/readback and fixed light is required before any
change to Bayer, analog gain law, digital gain or sensor timing.

## Private AGC trial and validation

`userspace/quality/libcamera-sp11-rev25-agc-experiment.patch` adds an optional
per-sensor `Agc.exposureTarget`; missing means unchanged 2.5. It rejects
non-finite or out-of-1–5 MSV values and logs the target. The separate
`prepare-rev25-agc.py` copies a *private* existing IMX681 YAML to two private
variant roots, adding only `exposureTarget: 3.5` to one; it records hashes,
uses restrictive permissions, refuses existing output and accepts paths only
under private camera staging. Both roots contain `simple/imx681.yaml` because
libcamera looks up `<IPA name>/<sensor model>.yaml`
(`out/ref/libcamera/src/libcamera/ipa_proxy.cpp:34-74`). The rear YAML is not
in either override, so it falls back to the system file. This is a private
experiment, not a claim that 3.5 fixes colour or darkness. With the *same*
patched IPA in both arms, compare 2.5 to 3.5 only after baseline colour and
metadata collection; check convergence, clipped highlights, noise, exposure,
gain and LED. The implementation preserves the sensor-driver limits; it does
not establish that long exposures or an arbitrary target are desirable.

Local checks: both candidate diffs apply in dry-run to the assembled rev21 DT
and clean libcamera v0.7.2, respectively; `checkpatch --no-tree --no-signoff`
is clean on 0026. The assembled Denali DTS preprocesses and compiles with and
without 0026; decompilation shows rear rotation 180 and the front unchanged. In
both builds dtc emits the same 30 existing `unique_unit_address` warnings; this
does not substitute for integrated rev24 DT or schema validation. The AGC
source passes `g++ -fsyntax-only` with warnings as errors against generated
v0.7.2 headers. A host harness links the patched AGC
to libcamera, supplies the same synthetic middle histogram for each target,
and observes the expected decrease at 2.5 and increase at 3.5; malformed and
out-of-range targets fail. The generator's transformation preserves the local
private baseline byte-for-byte except the intended new key and rejects
missing, preconfigured, duplicate and CRLF Agc inputs. A synthetic private
staging run verifies both files, hashes, permissions, refusal to overwrite and
path containment. These are host-level checks only: no full rebuilt RPM, DT
schema validation, running device IPA, camera capture, application orientation
or device quality test was done.
