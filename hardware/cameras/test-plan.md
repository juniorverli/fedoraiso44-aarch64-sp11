# Cameras test plan: rear mapping first, then front C-PHY

Revision 19 reached both RGB sensor links and oopsed at CSIPHY stream-on. Revision 20 corrects the mapping and is expected to stop the front stream at the known C-PHY clock error; revision 21 adds patch 0023. See [mapping evidence](evidence/2026-11-02-csiphy-mapping-oops.md) and [C-PHY clock evidence](evidence/2026-11-02-cphy-clock-fix.md). This is a plan, not a device result. Keep the IR sensor/endpoint excluded and the IR illuminator, flash and sensor strobe off (S2). Do not scan CCI buses with `i2cdetect`; retain raw logs and frames privately under `out/`.

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
