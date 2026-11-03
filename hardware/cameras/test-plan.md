# Cameras test plan: rev24 matched controls and RGB cameras

Revision 19 reached both RGB sensor links and oopsed at CSIPHY stream-on. Revision 20 corrected the mapping; revision 21 added patch 0023 for the previously observed C-PHY clock error. Later active C-PHY behavior remains unproven. See [mapping evidence](evidence/2026-11-02-csiphy-mapping-oops.md) and [C-PHY clock evidence](evidence/2026-11-02-cphy-clock-fix.md). This is a plan, not a device result. Keep the IR sensor/endpoint excluded and the IR illuminator, flash and sensor strobe off (S2). Do not scan CCI buses with `i2cdetect`; retain raw logs and frames privately under `out/`.

The 2026-11-03 rev21 bundles show rear-only enumeration and incomplete debug snapshots, not a recorded stream or selected app mode. Follow the reset-resilient procedure below before treating any live preview, idle graph or GPU message as a stream result. See [evidence](evidence/2026-11-03-m16-camera-stream-quality.md). Stop testing on reset, camera fault or unlit physical privacy LED; preserve the data before another attempt. Do not change patch 0023 clock rates or CSID fields without observed active clock and IRQ data.

## Rev24 one-variable matrix (2026-11-03)

The control is the exact rev23 image, kernel, DTB, private blob and tuning, with their full hashes and build IDs recorded. Rev23 includes the BW-vote backport and safe softpipe candidate; rev22 has neither, so it is a historical control, not a one-variable rev24 comparison. Each row below is a separate boot where stated; close camera clients, identify the sensor by `cam -l` rather than its index, verify observer/physical LED and all prerequisites below, and persist markers/live logs externally. Do not stream without the observed LED gate. An operator must stop immediately on an unlit LED, fault, stall or reset; no automatic retry. Never test IR or flash. See [reference and candidates](evidence/2026-11-03-rev24-reference-comparison.md).

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
