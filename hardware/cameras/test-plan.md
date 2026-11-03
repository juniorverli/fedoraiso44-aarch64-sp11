# Cameras test plan: rear mapping first, then front C-PHY

Revision 19 reached both RGB sensor links and oopsed at CSIPHY stream-on. Revision 20 corrects the mapping and is expected to stop the front stream at the known C-PHY clock error; revision 21 adds patch 0023. See [mapping evidence](evidence/2026-11-02-csiphy-mapping-oops.md) and [C-PHY clock evidence](evidence/2026-11-02-cphy-clock-fix.md). This is a plan, not a device result. Keep the IR sensor/endpoint excluded and the IR illuminator, flash and sensor strobe off (S2). Do not scan CCI buses with `i2cdetect`; retain raw logs and frames privately under `out/`.

The 2026-11-03 rev21 bundles show rear-only enumeration and incomplete debug snapshots, not a recorded stream or selected app mode. Follow the reset-resilient procedure below before treating any live preview, idle graph or GPU message as a stream result. See [evidence](evidence/2026-11-03-m16-camera-stream-quality.md). Stop testing on reset, camera fault or unlit physical privacy LED; preserve the data before another attempt. Do not change patch 0023 clock rates or CSID fields without observed active clock and IRQ data.

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

For each sensor find its subdevice from the media graph and run `v4l2-ctl -d /dev/v4l-subdevN -L` directly, substituting the actual node. Record exposure, analogue/digital gain, VBLANK, HBLANK, pixel rate, link frequency and their ranges. Do not rely on the old collector's `Card type` match, which returned no sensor controls in these boots. Save the full SHA-256 and size of both installed private blobs and the tuning files and package versions; keep hashes/logs private if appropriate. Front enumeration will continue to fail until a regenerated three-control blob is staged and the driver reprobed on a later boot. See R23 for the generator command and the required private manifest check.

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
2. Select the front IMX681 explicitly. On revision 20, record the expected `Pixel clock is too high for CSIPHY` error and stop; do not count a front frame. On revision 21, enable CAMSS dynamic debug as below, then start the stream while watching the front indicator and sample clocks while it remains active. Stop immediately if the LED stays dark. Save RGB/YUV through libcamera, format, size, frame count and colour; RAW capture alone is a diagnostic, not acceptance. Verify LED off after stop.
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
