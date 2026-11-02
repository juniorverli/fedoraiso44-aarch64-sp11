# Cameras test plan: front first, rear second

Revision 19 safe boot already reported a complete RGB graph but oopsed at CSIPHY stream-on; see [mapping evidence](evidence/2026-11-02-csiphy-mapping-oops.md). Test the revision 20 kernel with corrected patch 0003 and the RGB-only, no-IR graph. Do not scan the CCI buses with `i2cdetect`. The IR sensor and endpoint remain excluded; the IR illuminator, flash and sensor strobe must stay off (S2). Use the operator's live USB, and retain raw logs and frames privately under `out/`.

Before any stream, independently cross-check the camera-to-indicator wiring and its polarity (dossier request R11); confirm the effective DT assigns the privacy LED to both sensors. The V4L2 core already obtains and controls this LED on stream (`v4l2-fwnode.c:1275`, `v4l2-subdev.c:173-186,490-500`); patch 0020 adds shared-LED accounting. Observe the physical indicator throughout each stream and stop immediately if it is not on. Verify it turns off after the last stream. Do not manually force LED brightness to simulate this test.

## Before boot

- Integrate the corrected camera patch series including 0003, 0020, 0021 and the IR exclusion 0022; use the camera-enabled safe entry and verify effective DT endpoints and statuses. Keep BTF enabled. Confirm the four CSIPHY `reg` sizes are `0x2000` and full VFE sizes `0xf000` in the compiled image DTB.
- Include both private sensor register blobs, Fedora libcamera with SoftISP, sensor helpers and tuning, `cam`, `qcam`, PipeWire/portal integration, `media-ctl` and `v4l2-ctl`. Report exact tuning/helper coverage; presence of a blob does not prove image quality.
- Install the read-only camera collector and preserve its timeout/incomplete markers. Record the kernel/DTB/image revisions and the capture application versions.

## Graph and enumeration

Run before starting a camera application; save output and failures:

```sh
for m in /dev/media*; do [ -e "$m" ] && media-ctl -d "$m" -p; done
v4l2-ctl --list-devices
for v in /dev/video*; do [ -e "$v" ] && v4l2-ctl -d "$v" --list-formats-ext; done
cam -l
journalctl -k -b | grep -Ei 'camss|csiphy|csid|vfe|imx681|ov13858|cci|privacy|oops|fault'
```

Confirm `imx681 8-0010` has an enabled immutable sensor link to `msm_csiphy2` and `ov13858 7-0010` to `msm_csiphy1`, as seen in revision 19. Adapter numbers may change on another boot: identify by sensor and link, not number alone. CSIPHY-to-CSID and CSID-to-VFE links can start disabled until libcamera configures a route. There must be no IR sensor link or endpoint. `cam -l` must list the front IMX681 first and the rear OV13858 second; confirm the portal/default app also selects the front. If graph links, enumeration, ordering or the LED safety prerequisite fail, collect evidence and stop before streaming.

## Stream and capture

1. Start `qcam` and open its first/default camera, IMX681. Verify the physical privacy LED remains on throughout the stream. Capture an RGB/YUV frame through libcamera and save it privately. Record resolution, format, frame count, timing, exposure and whether the image has sensible colours. Check that the portal/default app opens this same front camera. If preview, LED or capture fails, stop and save the error and kernel log.
2. Stop the stream, check the LED turns off, then use `qcam` or `cam` to explicitly select the second camera, OV13858. Repeat the LED, RGB/YUV preview and saved-frame checks. Inspect `cam --help` for the installed release's camera-selection and file-output syntax; preserve the commands actually used. RAW alone is diagnostic and does not satisfy acceptance.
3. Re-run `media-ctl -p`, `cam -l` and `journalctl -k -b` after the attempts. There must be no `csiphy_reset` oops, translation fault or other new camera-related oops. Save graph, complete kernel messages, application output, negotiated formats and captured frame metadata. Record regulator state before and after if debugfs is available.
4. If front streams but has no frame or incorrect colours, inspect its C-PHY trio, negotiated lane/settle/link frequency, sensor mode and SoftISP helper/tuning. For rear, compare negotiated Bayer code with the actual mode: built-in OV13858 mode uses SGRBG10, Windows blob modes use SBGGR10; front Windows data indicates SRGGB10, but physical Bayer order still needs capture verification. Use a colour target. Capture diagnosis must not bypass the indicator gate.

If needed for RAW diagnostics, use `media-ctl` to inspect actual entity names and pad numbers, enable the chosen CSIPHY → CSID → VFE RDI path and set matching pad formats; use `v4l2-ctl` only on the corresponding video node and record the negotiated pixel format. Device numbers and pad routes are not stable. Do not operate IR or flash.

## Acceptance

- Front IMX681 enumerated first and selected by default in libcamera/portal; rear OV13858 second.
- Both cameras deliver saved, correctly coloured RGB/YUV frames through libcamera, front tested first.
- The physical privacy indicator is on for every stream and off after the last stream; wiring cross-check completed.
- No CSIPHY reset oops or other new camera oops; the IR node/endpoint is excluded, and the IR illuminator and flash stay off.
