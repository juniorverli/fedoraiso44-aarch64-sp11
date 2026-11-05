# Cameras test plan: rev25 quality and rev24 matched controls

Revision 19 reached both RGB sensor links and oopsed at CSIPHY stream-on. Revision 20 corrected the mapping; revision 21 added patch 0023 for the previously observed C-PHY clock error. Rev24 safe now delivers both RGB streams; debug reset causality remains unproven. See [mapping evidence](evidence/2026-11-02-csiphy-mapping-oops.md) and [C-PHY clock evidence](evidence/2026-11-02-cphy-clock-fix.md). This is a plan, not a device result. Keep the IR sensor/endpoint excluded and the IR illuminator, flash and sensor strobe off (S2). Do not scan CCI buses with `i2cdetect`; retain raw logs and frames privately under `out/`.

The earlier rev21 bundles showed only rear enumeration; rev24 safe now supplies two streams, while debug still resets. See the [rev24 evidence](evidence/2026-11-03-rev24-quality-orientation.md). Stop testing on reset, camera fault or unlit physical privacy LED; preserve the data before another attempt. Do not change patch 0023 clock rates or CSID fields without observed active clock and IRQ data.

## Rev25-menu: prioritized green, dark and orientation measurements (2026-11-04)

This section supersedes the front-only wording in the historical rev25 plan
below. Both previews are now reported green and dark, but the displayed lenses
are not proven; [rev25 evidence](evidence/2026-11-04-rev25-green-dark.md)
records the two inferred configurations and the transient `cam -l` link-busy
failure. Keep the exact safe camera stack, private tuning and kernel/DTB as the
control. The following is a plan, not an observed fix.

### 1. Establish identity and preserve the baseline

Complete **Before any stream** below, including the independent LED wiring
cross-check. A person observes the appropriate physical privacy indicator during
every attempt and stops immediately if it is dark, on a fault, stall or reset.
Keep the IR sensor excluded, IR illuminator, flash and strobe off; never obscure
the indicator while covering a lens. Do not use `i2cdetect`, direct register
writes, or an LED override. Retain private frames and logs on a non-Windows
filesystem with sufficient free space. Record the ISO, effective DTB, kernel,
libcamera/IPA/helper and each installed YAML/blob **full SHA-256**, plus
package versions and actual loaded YAML path. A name or 16-digit hash prefix is
not sufficient. Keep the baseline packages and tuning for rollback.

With Snapshot and other camera clients closed and the collector finished,
run `cam -l` once and retain all stdout/stderr; if the rear link is busy or a
camera is missing, mark enumeration incomplete, release the competing client
and repeat **before** streaming. Note the full libcamera camera IDs, not just
indices. The sensor identity is the ID's CCI path and graph entity: front
`imx681 5-0010` at `ac16000`, rear `ov13858 4-0010` at `ac15000`. Record the
current `/dev/v4l-subdevN` from `media-ctl -p`; it can change. Observe active
route and formats in each run. During identified direct capture, separately
cover and uncover **only each lens**, without covering an indicator, and record
which marked target darkens. Then use the same occlusion test in Snapshot for
each menu selection, recording label, portal/PipeWire node and timestamp if
available. Compare saved output as well as preview. An enumeration or menu
label alone cannot prove the physical source.

### 2. Green on each sensor: one RAW data set, two offline CCM arms

Use an evenly illuminated, unsaturated neutral target with separately visible
red and blue patches; record light source, geometry, and a lux reading if a
meter is available, otherwise mark it unknown. Fix the scene and avoid flicker.
For each identified sensor capture in its logged mode: front 3840x2160
RGGB-10-CSI2P, rear 2112x1188 GRBG-10-CSI2P. Save, privately, a capped-lens
dark, neutral flat, red and blue target with centre and corner ROIs. Capture a
processed 1920x1080 view and RAW from the same requests if the installed simple
pipeline accepts both streams. Keep the same sensor mode and settings for all
four targets; record if that is not possible. The log's formats are negotiated
claims, not proof of CFA, sample values or stride integrity.

For a concrete attempt, set `CAMERA_ID` to the full observed ID, `RAW_WIDTH`
and `RAW_HEIGHT` to that sensor's dimensions above, and `CAPDIR` to a **new**
private directory on a writable non-Windows filesystem (or under `out/` on the
host); select one target for this invocation. Run
`cam --help` first and confirm the installed syntax. This finite example writes
all 60 frames of both streams and can use several gigabytes over the full test;
check capacity and stop the foreground command if the observer sees a problem.
Repeat for each target and sensor, preserving separate directories:

```sh
umask 077
if [ -z "$CAPDIR" ] || [ -e "$CAPDIR" ] || ! mkdir -m 700 -- "$CAPDIR"; then
  printf '%s\n' 'Set CAPDIR to a new private directory on a non-Windows filesystem.' >&2
else
  set -o pipefail
  stdbuf -oL -eL cam --info --camera "$CAMERA_ID" \
    --stream "role=raw,width=$RAW_WIDTH,height=$RAW_HEIGHT" \
    --stream 'role=viewfinder,width=1920,height=1080' \
    --capture=60 --metadata --file="$CAPDIR/frame-#.bin" 2>&1 | \
    stdbuf -oL tee "$CAPDIR/capture.log"
fi
```

Check the accepted configuration, adjustment, mode, pixel format, row stride,
plane size, sequence, timestamps, bytes used and actual saved files: role and
requested size alone are not proof. If the paired request is rejected or
adjusted to a different mode, do not call the resulting frames matched; request
a diagnostic capture tool, or capture separately with stable light and proven
settings while explicitly marking the limitation. If 60 frames have not
converged, extend the capture only while safe and with enough private storage.
A RAW-only capture may not run the same SoftISP/3A path. `--capture` without
`--file` saves no frames.

Decode CSI-2 packed RAW10 with the **reported** row stride and check buffer
length, row boundaries, crop parity and all four pixel parities. Measure the
capped frame's per-parity pedestal/noise and each target's centre/corner means,
noise and clipped fraction. Red and blue targets identify physical R and B;
the neutral flat alone does not. Record per-frame ExposureTime, AnalogueGain,
SensorBlackLevels, ColourGains, ColourTemperature, ColourCorrectionMatrix,
Gamma, sequence and timestamp when exposed. `SensorBlackLevels` can be the
IPA's model, not a measured pedestal; the same-frame CCT can be newly estimated
while the reported CCM was latched earlier. Record the actual frame CCM and
missing fields; metadata can be delayed and is not independent readback.

For **the same** neutral/colour RAW, subtract the measured dark, demosaic and
apply one fixed WB derived from the neutral ROI. In two offline arms change
only the matrix: identity versus the CCM latched for that frame. Use the private
frame metadata, or reconstruct it from the identified tuning and the actual
latched interpolation state. The current frame's newly estimated CCT alone is
insufficient because of CCM hysteresis and pipeline delay. Hold black, WB,
demosaic, crop, gamma and display transform fixed; retain parameters privately.
Compare neutral-channel error, red/blue behaviour, clipping and centre/corner
differences against the target. If the CCM or applied fixed WB is unavailable,
mark that arm blocked and request a private diagnostic build; do not substitute
a Windows matrix or claim identity is colour accurate. A green cast already
present after the same measured WB and identity points upstream of the CCM;
a cast introduced only by the CCM supports a matrix/selection investigation.
Use a calibrated chart/reference before treating either arm as colour correct.

### 3. Dark on each sensor: separate capture from rendering

With a large neutral target and stable light, record first-to-converged frames
and compare each camera's RAW signal above measured black, processed luminance,
noise and clipping, plus exposure time/lines, analogue/digital gain if
observable, HBLANK, VBLANK, pixel rate, frame cadence and mode. Account for
field of view, binning and unknown optics; this is not a lens or quantum
sensitivity calibration. If manual controls are not exposed, request an
isolated diagnostic libcamera/IPA path that suspends its AGC loop and records
requested values, sensor readback **and frame delay**, without bypassing the
kernel LED gate. Do not race direct V4L2 controls against active AGC. Once
supported, use safe driver-supported common exposure times and gains, validate
actual response with a small stable-light sweep, and hold all other settings
fixed. Front line time and gain law remain unverified.

Only after these measurements consider the existing private, per-sensor
2.5-versus-3.5 AGC experiment below. It is a brightness experiment, not a
proven fix; changing the target cannot establish a colour correction. For a
rear experiment a separately identified, sensor-specific tuning arm and its
baseline would be needed. No global gain law, exposure cap or Bayer change.

### 4. Orientation after lens identification

Use readable asymmetric text with marked top and left. Compare the rear and front
in direct capture, Snapshot preview and saved output; distinguish mirror from
rotation. Candidate [0026](patches/0026-candidate-arm64-dts-qcom-denali-rear-camera-rotation.patch)
requires a separate reviewed kernel/DTB build and supplies rear 180-degree
metadata only. If the rear is still inverted, test a rear-only processed-frame
180-degree conversion or independently validated sensor flips with propagated
Bayer layout. Verify clients that honor metadata do not rotate twice. The front
must not be rotated by the rear correction.

### 5. Rev25c menu entries, rear rotation and an on-device tuning A/B

The rev25c private ISO adds two nondefault entries and keeps line 2 `SP11 debug,
safe (no GPU)` as the control:

- line 22 `SP11 debug, safe, rear rotation test` (`m15-safe-camrot`, `sp11.entry=safe`,
  `sp11.test=test-safe-camrot`). **In the rev25f build this DTB is byte-identical to
  `m15-safe`** (both SHA-256 `244d6e77…`), because camera patch 0026 is in kernel
  series rev25 and `rotation = <180>` is therefore already in every variant, line 2
  included. Booting line 22 can only show that the ISO carries the recorded DTB; it
  is not an A/B. The real check is on the plain safe boot: read
  `V4L2_CID_CAMERA_SENSOR_ROTATION` from the rear sub-device (`v4l2-ctl -d
  /dev/v4l-subdevN -L`), then compare the saved rear output. The simple pipeline
  rotates no pixels; if a client ignores the metadata the rear stays inverted and
  the next step is a rear-only processed-frame rotation or validated sensor flips
  with a propagated Bayer layout (neither is implemented). The duplicate entry is
  scheduled for removal in the next menu build.
- line 23 `SP11 debug, safe, muted closed-loop VI` is the audio diagnostic; do not
  use it for camera work (its `-CL` sound model changes firmware selection only).

This image also installs the private per-sensor libcamera YAMLs with the Agc
`exposureTarget: 3.5` experiment and the measured `Adjust` gamma (front 1.882,
rear 2.288) on top of the device-derived CCM, black level and LSC data. It
also sets `Awb: maxGains` from the module's own calibrated white-balance
ladder (front 9.83/4.71, rear 4.07/4.00) because the stock Software ISP
clamps red and blue gains at 4.0 and the front calibration needs up to 8.93×
red; see [the AWB ceiling evidence](evidence/2026-11-04-awb-gain-ceiling.md).
That is a rendered-brightness and colour-cast candidate, not a measured
correction and not the RAW measurement of sections 2-3. The stock simple IPA
hardcodes 2.5 and 4.0; on the live system the YAMLs are
in `/usr/share/libcamera/ipa/simple/{imx681,ov13858}.yaml` on the writable
overlay, so an A/B needs no rebuild: copy the file aside, delete or change the
`exposureTarget` or `maxGains` line to return to the stock value, close every
camera client (PipeWire portal, Snapshot, `cam`), and open the camera again on
the same fixed scene. Record the file hash and the chosen value with each
capture.

### 6. One-command AWB report and measured correction

The image carries `/usr/libexec/sp11/camera-diagnostic/awb-report.sh`. On the
`safe` entry, with every camera client closed and an observer watching the
privacy indicator:

```
sudo /usr/libexec/sp11/camera-diagnostic/awb-report.sh
```

It enumerates both cameras, enables `IPASoftAwb` debug logging for one
10-frame capture per camera, parses the last applied gains and prints
`AWB_STUCK` (gains 1.0: estimator not updating), `AWB_CEILING` (a gain at the
tuning ceiling), `AWB_OK` (plausible gains) or `AWB_NO_LINE`, per sensor, with
the CCT and the ceiling in use. It saves nothing but a 0600 text report under
`/var/tmp`; it does not read samples, change controls or touch the LED.
`--self-test` checks the parser and the verdict without a camera.

### 6. Measured correction in one device cycle, if green persists

If the stock-versus-`maxGains` A/B still shows a cast, the deterministic path
is a grey-card measurement instead of another guess:

1. Run `camera-diagnostic/capture.py` once per sensor for a capped-lens dark
   frame and once for an evenly lit neutral target, keeping every file. The
   raw stream file is the large one (front 3840×2160 → 10,368,000 bytes per
   frame at stride 4800; rear 2112×1188 → 3,136,320 bytes at stride 2640);
   the 1920×1080 viewfinder file is smaller. Confirm the size before use.
2. Close every camera client and run, as root, for the front:
   `sudo /usr/libexec/sp11/camera-diagnostic/calibrate.py --sensor imx681
   --neutral <neutral-raw> --dark <dark-raw> --width 3840 --height 2160
   --stride 4800 --cfa RGGB --install`
   and for the rear the matching `--sensor ov13858 --width 2112 --height 1188
   --stride 2640 --cfa GRBG`.
3. The tool prints the per-channel black and the measured red/blue gains,
   refuses clipped or dark frames and writes `Awb: gains` into the private
   YAML, keeping a `.sp11-orig` backup. Reopen the camera on the same scene
   and compare the saved frame with the pre-calibration one.
4. `--restore` puts the original YAML back. Record both YAML hashes. This
   correction is per sensor and per lighting condition; it is not a
   production calibration and does not replace the sections 2-3 measurement.


## Historical rev25 camera quality plan (2026-11-03)

The control is the exact rev24 safe stack, including active-trio/CSID/VFE,
private blobs and sensor YAMLs, and the safe-only WirePlumber softpipe wrapper.
The new [quality evidence](evidence/2026-11-03-rev24-quality-orientation.md)
identifies front as exposure range 4–3550 lines / gain 1–15.5152, and rear as
4–3206 / 0–63.9922. Those are ranges, not observed settings. Keep the normal
safe boot available and run all quality experiments on safe; the GPU owner
separately owns the debug reset. No IR, flash, LED bypass or sensor/register
poking. An observer must watch the appropriate physical indicator and stop the
stream immediately if dark, on fault or reset, per the prerequisites below.

### 1. Verify rear orientation and front orientation

1. Obtain a separately identified kernel/DTB with only candidate [0026](patches/0026-candidate-arm64-dts-qcom-denali-rear-camera-rotation.patch)
   added to rev24, after kernel review, BTF build and DT schema checks. Record
   kernel/DTB/ISO hashes. Keep the rev24 DTB as rollback. On safe, enumerate
   with `cam -l`, `media-ctl -p`, and `v4l2-ctl --list-devices`. Find each
   sensor's actual `/dev/v4l-subdevN` from the media graph, then run
   `v4l2-ctl -d /dev/v4l-subdevN -L` for both and `cam --camera "$IDX" --list-properties`
   with each observed ID. Rear should report read-only camera sensor rotation
   180 and back location; front location should be front and rotation remains
   the 0 fallback. Preserve the output and warnings.
2. With the device in normal landscape orientation, use an asymmetrical,
   readable target with marked top and left. For **each** camera compare direct
   libcamera capture, Snapshot preview and saved image, and another PipeWire
   client if available. Record exact camera ID, app, frame format, orientation,
   and whether text/left-right are mirrored. Rear 180 is an inference from the
   reported upside-down picture; confirm it physically. Front upright is still
   an observation to make, not an assumed fact. A mirror is not a 180 rotation.
3. The metadata-only DT patch cannot force a sensor flip in this libcamera
   simple pipeline. If a consumer still displays the rear upside down, image
   owner should test a separately marked rear-only 180° **processed-frame**
   transform and verify saved pictures and clients do not double-rotate. Do not
   alter raw CFA or front output. No production transform is claimed yet.

### 2. Front green: locate the failing stage

Use even, steady illumination, neutral grey/white and separately red and blue
patches in view; record the light source and setup. The same RAW and processed
frames are ideal; request both streams in a single libcamera configuration if
supported, otherwise record the limitation, exact active mode and settings and
capture in separate controlled runs. Record actual code, stride, packing,
width/height, crop, sequence and timestamps. Save private RAW samples and
processed images, not just screenshots. Use `cam --help` to select supported
RAW/viewfinder roles; `cam --camera "$FRONT" --capture=120 --metadata` logs
completed request metadata but does not save frames unless `--file` is used.
Do not assume request count proves a frame was saved.

- Capture a capped-lens dark RAW, uniform flat, and central/corner neutral and
  red/blue targets under the same measured light. Decode negotiated packed
  RAW10 using its stride; record R, Gr, Gb and B parity means, per-channel
  black, saturation fractions and noise. The red/blue targets, not a neutral
  flat alone, distinguish CFA positions. The reported RGGB is the negotiated
  format, not yet a physical measurement.
- Save per-frame exposure, analogue gain, ColourGains, ColourTemperature and
  ColourCorrectionMatrix when present. Verify actual file and IPA/helper
  hashes; the installed YAML path alone does not prove contents. Offline,
  compare the same RAW with measured fixed white balance and current versus
  identity CCM, then inspect centre and corners. This isolates a likely AWB or
  CCM problem from CFA/packing/black or lens shading. Any measured CCM/AWB
  candidate must be private, separately named, and vary one item at a time.

### 3. Front dark / rear brighter: measure before changing gain

Using the same stable illumination and a large neutral target filling both
fields of view, record each sensor's negotiated mode, frame rate, HBLANK,
VBLANK, reported pixel rate/line duration, exposure in lines and microseconds,
analogue and digital gain if observable, AWB/CCM metadata, RAW channel means,
black, noise, saturation and processed luminance. Record first-to-converged
frames and actual scene light; repeat for moderate and low light if safely
available. Account for different field of view, pixel area/binning, aperture and
sensor size. These optical properties are currently unknown; different image
brightness alone does not quantify them. Front exposure time depends on an
inferred line clock, so compare reported timing with measured frame cadence.

Check `cam --camera "$IDX" --list-controls` first. The v0.7.2 simple IPA's
AGC continuously drives exposure/gain and may not offer manual AE or AWB. Do
not race V4L2 writes against it. If fixed common settings cannot be requested,
report that limitation and have the image owner supply an isolated diagnostic
capture path that disables the AGC loop and records requested **and applied**
controls while preserving the LED gate. Then compare unsaturated RAW responses
to safe, driver-supported exposure and gain steps, with a stable scene and
latency/readback. Never increase a sensor limit, frame length or exposure cap,
or invert/remap gains, merely to brighten the front.

### 4. Private per-sensor AGC A/B, after baseline measurements

The image owner prepares a separately named private experimental libcamera IPA
using [the optional-target patch](userspace/quality/libcamera-sp11-rev25-agc-experiment.patch)
on the exact Fedora 0.7.2 RPM source, plus both existing SP11 patches. Preserve
all rev24 kernel/DT, helper, AWB/CCM/gamma, source YAML, blob, package and LED
behavior. Build and identify the IPA with matching signing/proxy provenance;
retain the unmodified RPM for rollback. Do not replace the production IPA.

On the private image build host run:

```sh
python3 hardware/cameras/userspace/quality/prepare-rev25-agc.py \
  --output-dir out/firmware-private/cameras/rev25-agc-ab
```

The new directory contains a manifest and separately named
`imx681-rev25-agc-2.5/simple/imx681.yaml` and
`imx681-rev25-agc-3.5/simple/imx681.yaml`; the second has exactly one extra
AGC target key. Keep both private. Verify their hashes and parse with the
Fedora libcamera YAML parser; do not substitute a different baseline. Put the
chosen variant root on the device as `$VARIANT_ROOT`. With other clients closed,
select the front ID and test both roots using the **same patched IPA**:

```sh
env -u LIBCAMERA_SIMPLE_TUNING_FILE \
  LIBCAMERA_IPA_CONFIG_PATH="$VARIANT_ROOT" \
  LIBCAMERA_LOG_LEVELS='*:INFO,IPASoftExposure:DEBUG' \
  cam --camera "$FRONT" --capture=120 --metadata
```

Verify `IPAProxy` prints that root's `simple/imx681.yaml` and
`IPASoftExposure` prints target 2.5 or 3.5. Its rear lookup must continue to the
original rear YAML. For Snapshot, use the same environment only in a separate
private safe WirePlumber test instance and verify the actually loaded path;
changing a terminal's environment does not change an already running service.
Compare steady-scene convergence, actual exposure/gain, RAW/processed signal,
noise, highlight clipping and LED for both targets. A brighter but clipped or
noisier image is not an automatic pass. Separately confirm rear remains at 2.5.
Retain original private tuning and remove the experimental instance after test.

## Rev24 one-variable matrix (historical reset isolation, GPU owner)

This pre-result matrix is retained for the GPU owner's reset investigation; rev24 already includes 0024/0025 and streams both sensors in safe. Do not change the safe baseline to re-run historical camera candidates for quality work. The control is the exact rev23 image, kernel, DTB, private blob and tuning, with their full hashes and build IDs recorded. Rev23 includes the BW-vote backport and safe softpipe candidate; rev22 has neither, so it is a historical control, not a one-variable rev24 comparison. Each row below is a separate boot where stated; close camera clients, identify the sensor by `cam -l` rather than its index, verify observer/physical LED and all prerequisites below, and persist markers/live logs externally. Do not stream without the observed LED gate. An operator must stop immediately on an unlit LED, fault, stall or reset; no automatic retry. Never test IR or flash. See [reference and candidates](evidence/2026-11-03-rev24-reference-comparison.md).

| Order | Boot and single controlled action | Required outcome/evidence |
|:--|:--|:--|
| 0 | Exact rev23 debug, no camera or GPU workload: idle at least 150 s. Separate boot: GPU-only action, no camera. | Boot ID and monotonic markers, persistent live log; reset in either prevents attributing reset to camera. |
| 1 | Exact rev23 **safe rear**, explicit direct headless capture; no GUI. | LED physically on/off, callback entry/return, completed request sequence/bytes, active clocks/IRQs, video format; a headless SoftISP path can still load EGL. |
| 2 | Exact rev23 **safe front**, separate boot and same procedure. | Same evidence; active C-PHY clocks and PHY/CSID IRQ deltas during the marked attempt. Record if no active sampling overlaps. |
| 3 | Exact rev23 **debug rear**, separate boot after idle/GPU controls. | Explicit `BEFORE_START` and sensor/mode markers, persistent callback/clock/IRQ trace, LED on/off and completed requests; preserve reset/pstore. |
| 4 | Exact rev23 **debug front**, separate boot after previous results reviewed. | Same sensor-identified markers and evidence; stop on reset, no automatic retry. A front-only reproducible reset supports but does not by itself identify legacy PHY. |
| 5 | Only after control and active clock/IRQ data: test candidate 0024 alone against the same rev23 mode/boot; 0023 unchanged. | Match sensor, kernel/config except this patch, scene and command; observe CSID SOF/drop/EOF, IRQ delta and buffers. No inferred success from LED alone. |
| 6 | Separately test candidate 0025 atop a fixed, recorded baseline; specify whether 0024 is present on both A and B sides. | Compare only VFE mode, capture image violations, sequence/bytes/stride and canary/buffer bounds; repeat rear and front, full/lite paths when routed. |
| 7 | Only if stable front reception shows line loss/overflow, compare exact baseline private 3840x2160 blob versus private 8704 HTS experiment with everything else fixed. | Confirm sensor mode HTS metadata and line register both changed, VTS 3554 unchanged, hashes, HBLANK/pixel rate; capture SOF cadence, RAW line integrity, errors and controls. Report inferred vs measured line rate. |
| 8 | Quality and safe rendering A/B, after stable capture. | Same scene/mode/manual controls: save representative private RAW plus processed RGB/YUV, row stride/size/packing/offset, sequence/timestamp/bytes, exposure, analogue/digital gain, AWB and first-to-converged timing; measure dark/flat and per-channel colour target. Separately compare rev23 safe softpipe vs same image without only the wrapper, and later IPA 2.5 vs 3.5 AGC target with one change per comparison. |

For each attempt record full `clk_summary` immediately before/during/after (rates, enable counts and parents), `/proc/interrupts` deltas, active route/pad format and available PHY/CSID/VFE error/SOF/EOF counters. Missing, disabled or uninstrumented counters are missing evidence, not zeros; do not read camera MMIO via `devmem`, especially with clocks off. Instrument callback entry **and return**, preserve timestamps and physical LED observations; no callback/buffer means no proven streaming. If a result changes more than one thing, record it as exploratory and do not treat it as an A/B. Candidate boots require a separately built image with BTF and provenance; none is included by this document. The image/kernel owners coordinate GPU-only trials and independent indicator cross-check before the first stream.

## Rev23 discriminating matrix (2026-11-03)

Rev22 safe Snapshot configured **front**, then WirePlumber crashed in an llvmpipe thread and Snapshot reported a failed PipeWire target. A zero exit did not establish a capture. Debug app and sensor are unknown. See [final32 evidence](evidence/2026-11-03-rev23-final32-camera.md). Tests below are separate boots or isolated attempts, with a human watching the mapped physical LED and another ready to stop the process. Stop immediately on an unlit LED, fault or reset; no automatic retries. No IR/flash and no stream if the observer or LED gate is unavailable. Preserve the independent wiring cross-check requirement below.

| Attempt | Action | Evidence and interpretation |
|:--|:--|:--|
| Safe rear | After prerequisites, list cameras; run the headless command below with the **observed rear index**. | A lit LED confirms physical indicator operation during the attempt, not buffer delivery. An instrumented successful sensor stream callback is start evidence; completed requests with increasing sequence and nonzero bytes prove delivery through libcamera. LED dark requires immediate stop and blocks further streams. Errors before callback mean stream start is unproven. |
| Safe front | Separate attempt with the **observed front index**, same scene and collection. | A successful front callback plus buffers tests IMX681/C-PHY; failure without SOF/buffers requires active IRQ/clock/error evidence. Neither an idle clock nor `cam -l` proves C-PHY works. |
| Debug marked camera | Coordinate with GPU owner after the GPU-only control; one explicit sensor per boot. Persist boot ID, sensor ID, `BEFORE_START` marker, monotonic output, live kmsg/trace and physical LED timestamps externally; stop at first reset. | Compare to matched GPU-only and safe headless trials. A reset reproducibly after a marked selected stream while controls survive supports a camera-trigger hypothesis; timing, selected callback and frame/IRQ state determine its strength. A reset in GPU-only weakens that hypothesis. An absent post-reset log is inconclusive. |

For each row first run `cam --help` and `cam -l` and write down the mapping (rev22 was rear 1, front 2; indices can change). Close Snapshot and other clients. Put `CAMLOG` on a tested, private, writable non-Windows filesystem and keep a second terminal's continuously flushed live kernel log/trace. After setting `IDX` to the **observed** camera index, use:

```sh
LIBCAMERA_LOG_LEVELS='*:INFO,IPASoftExposure:DEBUG' \
  stdbuf -oL -eL cam --camera "$IDX" --capture=120 --metadata 2>&1 | \
  stdbuf -oL tee "$CAMLOG/cam-${IDX}.log"
```

`cam` without `--display` is headless, but a processed SoftISP stream may still initialize EGL/llvmpipe; it removes the app preview window, not necessarily all GPU or software rendering. Check the actual renderer and SoftISP logs. Run it foreground so Ctrl-C immediately stops it on LED failure. A finite frame count is not a timeout if no frames arrive; the operator must stop a stalled attempt. Use the sampler and capture procedure below. During a sustained attempt, log active sensor pad code/dimensions and route; compare with mode list, not the earlier idle graph. Use the installed `cam --help` to specify a supported RAW stream and save representative RAW to a private destination only after the initial LED-gated test; verify output size/format/packing/stride, and make a separately saved processed RGB/YUV capture for acceptance. Do not assume `--capture` alone saves frames. For GUI comparison, only after the same sensor works headlessly, explicitly select it in `qcam` if installed and record selection and renderer. A qcam preview or Snapshot launch is not proof of completed requests without frames.

For start/return evidence, kernel owner should provide existing tracepoints or instrument `ov13858_set_stream` and the IMX681 start/stop callback with sensor identity, entry and return status and timestamps, without changing stream or LED ordering. If using function tracing, first confirm exact un-inlined symbols in `available_filter_functions` and both entry and return events; record missing instrumentation rather than equating a function entry, a log marker or LED with a successful return. Enable before the attempt and persist trace externally. Capture per-request sequence, bytes, timestamps, exposure, analogue gain and AWB when present. The active graph and clock/IRQ sampler may miss short streams; record gaps. For C-PHY save before/during `/proc/interrupts`, complete clk_summary with enable counts/rates, receiver errors and frame start/end when available; no 0023 changes without that evidence.

For quality after stable streaming, use a steady neutral/colour target with a fixed field of view. Save first-to-converged metadata for hundreds of frames if safe and feasible, FPS and scene illumination; compare manual exposure/gain if supported at matched settings, then one dark RAW and a flat-field RAW and processed RGB/YUV. Establish CFA from colour-target pixel parity for each mode, and compare a similarly framed Windows image. Hash private installed YAML and confirm the exact IPA/helper build. Changes to crop, gamma, black level, gain law or HDR require a measured causal discrepancy.

## Before any stream

- Use the correct kernel/DTB and RGB-only camera graph; verify the four CSIPHY windows are `0x2000` and full VFE windows `0xf000`. For rev21, integrate 0023 **after** the complete rev20 camera series. Retain BTF in the packaged kernel.
- Complete the independent camera-to-indicator wiring/polarity cross-check first. On a camera-disabled boot, blacklist `imx681,ov13858` and separately turn the two gpio-leds on and off to map each physical indicator, as in `plan/rev20.md` §3. Reboot with drivers enabled. This idle wiring check must not be mistaken for a streaming LED test.
- Verify each RGB sensor's effective DT references its own privacy LED. Observe the mapped physical indicator during every stream and stop immediately if it stays dark; verify it goes off after the last stream. The V4L2 core controls the indicator after successful sensor `s_stream`; never force it to simulate streaming.
- Check the installed private sensor blobs, Fedora libcamera SoftISP, IMX681/OV13858 sensor helpers, IPA and their matching tuning files. Record package versions and actual file coverage; presence is not evidence of correct colour. Keep the read-only collector and its timeout markers.

## Graph and enumeration

Before starting any camera application, save output and failures:

```sh
for m in /dev/media*; do [ -e "$m" ] && media-ctl -d "$m" -p; done
v4l2-ctl --list-devices
for v in /dev/video*; do [ -e "$v" ] && v4l2-ctl -d "$v" --list-formats-ext; done
cam -l
journalctl -k -b | grep -Ei 'camss|csiphy|csid|vfe|imx681|ov13858|cci|privacy|oops|fault'
```

Confirm IMX681 has an enabled immutable sensor link to `msm_csiphy2` and OV13858 to `msm_csiphy1`; adapter numbers may change. CSIPHY-to-CSID and CSID-to-VFE links may initially be disabled. No IR endpoint or sensor link may be present. Record camera order, `Location::Front`, portal/default selection and actual application behavior; a universal portal default is not assumed. Stop before streaming if the graph or privacy prerequisite fails.

For each sensor find its subdevice from the media graph and run `v4l2-ctl -d /dev/v4l-subdevN -L` directly, substituting the actual node. Record exposure, analogue/digital gain, VBLANK, HBLANK, pixel rate, link frequency and their ranges. Do not rely on the old collector's `Card type` match, which returned no sensor controls in these boots. Save the full SHA-256 and size of both installed private blobs and the tuning files and package versions; keep hashes/logs private if appropriate. Rev22 enumerates both cameras with the three-control front blob; verify full installed hashes and controls, rather than repeating the old rev21 regeneration request.

## Preserve state before a possible reset

Use a separate trusted host receiving a live log if available, or a known writable removable filesystem with ample space, never the Windows partition. Verify persistence with an actual write, `sync`, and readback before the attempt. Define `CAMLOG` as a private directory on that filesystem, for example `/run/media/liveuser/DIAGNOSTIC/camera-test`; create it with restrictive permissions. These commands are a device test plan, not commands run in this session. Keep an operator watching the real LED continuously and a second operator at the terminal; if either cannot stop the capture immediately when the LED fails, do not start. An LED sysfs value or a forced LED does not replace physical verification.

1. Before opening any app, save boot ID, monotonic time, command line, package versions, sensor controls, full media graph, `/proc/interrupts`, relevant `clk_summary`, current GPU state and both LED brightness values. Save results and run `sync -f "$CAMLOG"` if supported, otherwise `sync`. Record whether each read succeeded. Pre-enable available CAMSS dynamic debug and the `IPASoftExposure` debug category; record unavailable facilities. Start a live monotonic kernel journal in a separate terminal, for example `sudo journalctl -kf -o short-monotonic | stdbuf -oL tee -a "$CAMLOG/kernel-live.log"`; periodically flush with `sync -f "$CAMLOG/kernel-live.log"` from another terminal. An external serial/network log collector is preferable because a sudden reset can lose local buffered data. The collector does not itself establish app state.
2. Run an explicit rear-only **headless** libcamera diagnostic with no preview renderer, after checking `cam --help` and `cam -l` on the installed version. For the version whose help exposes these options, use `LIBCAMERA_LOG_LEVELS='*:INFO,IPASoftExposure:DEBUG' stdbuf -oL -eL cam --camera 1 --capture=120 --metadata 2>&1 | stdbuf -oL tee "$CAMLOG/rear-cam.log"`; select the observed rear index or ID, not a hardcoded assumption. The `cam` reference prints a line for each completed request including timestamp, sequence and bytes used, followed by metadata. Record the negotiated sensor and output format and any configuration/start/error lines; request completion with increasing sequence and nonzero bytes is evidence of buffers, not by itself proof of correct RGB. Missing logs after a reset are inconclusive. If the LED stays dark, immediately interrupt the capture, record that failure, and do not repeat until fixed.
3. Start the following bounded sampler in another terminal **before** the headless attempt, then launch the capture. It records even if the reset happens before a later manual snapshot. It takes read-only samples for up to 90 seconds; interrupt it once capture stops. Root permission may be required for clock debugfs; a missing/denied read is saved as a limitation. `$CAMLOG` must be set in this terminal too.

   ```sh
   for i in $(seq 1 90); do
       { date -u --iso-8601=ns; cat /proc/uptime
         media-ctl -d /dev/media0 -p
         cat /proc/interrupts
         cat /sys/kernel/debug/clk/clk_summary
         for f in /sys/class/leds/white:indicator*/brightness; do
             [ -e "$f" ] && printf '%s: ' "$f" && cat "$f"
         done
       } >> "$CAMLOG/state-live.log" 2>&1
       sync -f "$CAMLOG/state-live.log" || sync
       sleep 1
   done
   ```

   Substitute the CAMSS media node determined by enumeration if it is not `/dev/media0`. Each iteration takes longer than one second if the reads or sync are slow; use timestamps, not iteration number, for IRQ deltas. Note enabled sensor→PHY→CSID→VFE→video links, each pad's active format, selected video node, IRQ deltas and sensor/PHY/CSID errors; static `stream:0` and a link alone are not stream-on evidence. Read back actual clock rates and counts rather than assuming requested votes. If no snapshot overlaps capture, record that and use the completed request logs; do not restart automatically. The physical observer timestamps LED on/off and any reset.
4. If headless capture succeeds and the reset investigation permits, repeat under the same sensor/mode and lighting with the GUI app; retain its live application, PipeWire and kernel logs with timestamps. Comparing the two helps isolate rendering, but a different mode or workload prevents a definitive GPU attribution. Save only private representative RGB/YUV frames; record exact app, selected camera, format, dimensions, measured frame cadence, frame count and exposure/analogue gain/AWB metadata from the first frame onward. Capture a neutral/colour chart and flat field under controlled steady light; compare equal framing, exposure and output sizes with Windows. Test convergence from a fixed dark-to-light transition and note cap saturation. Manual exposure/gain comparisons require supported libcamera controls and the same LED gate; do not issue raw register writes.
5. After each attempt, flush logs, save the post-stop graph/IRQs/clocks, LED-off observation and full logs; after a reset recover pstore and the previous boot's complete journal if they exist, without overwriting either. Mark missing snapshots and their capture times. A completed headless test does not validate the front; test it separately only after front enumeration succeeds, with identical safety and evidence gates.

## Rear stream, then front stream

1. Select the rear OV13858 explicitly first. Watch the mapped rear indicator, capture an RGB/YUV frame through libcamera, and stop immediately if the LED is dark. Record app, command, format, dimensions, frame count, colour and logs; check the LED turns off after stopping. This tests the revision-20 mapping fix on D-PHY. Stop on a fault or oops.
2. Select the front IMX681 explicitly. For rev23, enable CAMSS dynamic debug as below, then start the stream while watching the front indicator and sample clocks while it remains active. Stop immediately if the LED stays dark. Save RGB/YUV through libcamera, format, size, frame count and colour; RAW capture alone is a diagnostic, not acceptance. Verify LED off after stop.
3. Re-run the graph, `cam -l` and kernel log checks; collect the camera log after each attempt. There must be no CSIPHY reset oops, translation fault or new camera oops. Use the image's installed `cam --help`/`qcam` interface to select cameras and save frames, and record exact commands. For colour diagnosis use a colour target: front Windows mode data indicates SRGGB10, while rear built-in mode uses SGRBG10 and Windows blob modes use SBGGR10. Physical Bayer output and SoftISP tuning still require verification.

## Revision 21 C-PHY clock and CSID checks

With debugfs and dynamic debug available, before starting the front stream enable the module's debug statements and preserve the kernel log. `qcom_camss` is the module name; if it is built in or dynamic debug is absent, record that limitation rather than assuming the lines exist.

```sh
sudo sh -c 'echo "module qcom_camss +p" > /sys/kernel/debug/dynamic_debug/control'
journalctl -kf
# In a separate terminal, while the observed front stream is active:
sudo grep -E 'cam_cc_(cphy_rx_clk_src|csiphy2_clk|csi2phytimer_clk|csid_clk|csid_csiphy_rx_clk)' /sys/kernel/debug/clk/clk_summary
```

The configured link frequency is 1.2 GHz, corresponding to 2.4 Gsym/s and approximately 5.472 Gbit/s per trio using Qualcomm's 2.28 approximation. Patch 0023 requests `csiphy2` **480 MHz**, `csiphy2_timer` **400 MHz**, and `csid` and `csid_csiphy_rx` **480 MHz**. Compare dynamic-debug request lines with active `clk_summary` rates, clock parent and enable counts. `csiphy2` and `csid_csiphy_rx` share the CPHY RX source; a debug line is a request, not a rate readback. Save the full summary if naming or rate differs. Check for rate/clock errors and absence of the old pre-reset `Pixel clock is too high for CSIPHY` failure.

Record the negotiated RAW data type and VC. For VC 0 and RAW10 (`0x2b`), the C-PHY capture-control debug write is expected to be `0x2b002b5`; disable writes zero. These are header diagnostic selectors, not the RDI payload routing or proof of a register readback. Verify the media route and incoming frame counters separately. Do not use `devmem` or write CSID/PHY registers to perform this check. Also record any PHY/CSID IRQ, lane, settle, ECC or CRC errors and sensor `s_stream` errors. Repeat the rear D-PHY stream after the front test to check for regressions; concurrent front/rear streaming and shared-clock arbitration are separate, currently unproven tests.

## Acceptance

- Wiring/polarity cross-check completed; privacy indicator on throughout every sensor stream and off after the last stream.
- Both cameras are selectable, front is identified as front, and both deliver saved RGB/YUV frames with sensible colours through libcamera. Record actual enumeration and portal behavior; RAW alone does not count.
- Revision 21 front requests and observed active clocks match the rates above or any difference is explained by clock readback and shared-parent state; CSID C-PHY header selector and route are recorded.
- No CSIPHY reset or other new camera oops; IR endpoint remains excluded and IR illuminator and flash remain off.
