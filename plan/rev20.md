# Revision 20 plan (2026-11-02, revised after independent review)

Input: device round 3, logs `C:\sp11-logs-2-5` (boots `393849d8` safe, `b1c603b5` debug), ISO `49bbf53d…`, kernel `7.3.0-65.sp11.19.fc44`. The operator reports: audio and microphone stopped working compared with the previous rev19 ISO; cameras still fail (black preview, no privacy LED, front camera not prioritised); debug still resets about 5 s after the desktop appears, with otherwise smooth graphics.

The raw round-3 capture is archived (git-ignored) at `out/device-logs/m16-20261102d/`. Component excerpts and hashes are in:
`hardware/cameras/evidence/2026-11-02-rev19-stream-oops-archive.md`,
`hardware/audio-speakers/evidence/2026-11-02-round3-audio-archive.md`,
`hardware/gpu/evidence/2026-11-02-round3-debug-archive.md`.

## 1. Baseline and what is proven

### 1.1 Camera: kernel oops at stream-on (verified defect in our DT)

Safe boot `393849d8` has a complete CAMSS graph: `ov13858 7-0010` linked to `msm_csiphy1`, `imx681 8-0010` linked to `msm_csiphy2`, both `ENABLED,IMMUTABLE`. The earlier belief that the front sensor does not probe is obsolete: with patch 0021 both sensors bind on CCI0/CCI1.

When `CameraManager` starts streaming, the kernel faults at 61 s:

```
Unable to handle kernel paging request at virtual address ffff800083aa6000
ESR = 0x96000047  EC = 0x25 (DABT)  FSC = 0x07 (level 3 translation)
WnR = 1  (write)
pc : csiphy_reset+0x30/0x78 [qcom_camss]
lr : csiphy_set_power+0x94/0x1b0 [qcom_camss]
x2 : ffff800083aa5000   x1 : ffff800083aa6000
```

`x2` is the CSIPHY ioremap base, the write is at `base + 0x1000`, and the mapping size is 0x1000. The mismatch is:

- `sources/linux/drivers/media/platform/qcom/camss/camss-csiphy-3ph-1-0.c:1242-1245` sets `regs->offset = 0x1000` for `CAMSS_X1E80100`.
- `csiphy_reset()` (`camss-csiphy-3ph-1-0.c:953-958`) writes `CSIPHY_3PH_CMN_CSI_COMMON_CTRLn(regs->offset, 0)` at `base + 0x1000`.
- `hardware/cameras/patches/0003-…` declared csiphy0/1/2 as `0x1000` bytes. All four X1E PHYs use `csiphy_ops_3ph_1_0` (`camss.c:4190-4258`); SM8550/SM8650 use `0x2000` windows.

The running DTB declared csiphy0/1/2 at `0x1000` and csiphy4 at `0x4000`. Patch 0003 (merged as `8a372c7`) now uses `0x2000` for all four CSIPHY windows and `0xf000` for the full VFE0/VFE1 windows; `0xf000` matches SM8550/SM8650 and the Hamoa reference, and the csiphy4 shrink matches the Hamoa reference. The camera worker compiled a standalone Denali DTB and checked all 17 CAMSS resource names/bases/sizes; integrated `CHECK_DTBS` and the six-variant build remain for the kernel worker. An independent cross-check of the register windows is still required before calling the value Verified (protocol §5.1).

The privacy LED is not a missing driver: Linux 7.3 gets it through `v4l2_subdev_get_privacy_led()` (`v4l2-fwnode.c:1275`, `v4l2-subdev.c:2735`) and the V4L2 core enables it only after the sensor's `s_stream()` returns 0 (`v4l2-subdev.c:173-186,490-500`). The DTB gives the front sensor `leds = <&camera_indicator>` (GPIO225) and the rear `leds = <&camera_indicator_rear>` (GPIO105); the runtime DTB has `camera-leds` status `okay`. REA of `qccamplatform8380.sys` (SHA-256 `836714ec…`, ARM64, Ghidra) confirms Windows drives the same indicators from the platform KMD (`Execute Privacy LED cmd: Privacy LED on GPIO index …`, `Privacy LED -- PMIC operation`). The LED stays off because the stream never reaches the sensor, not because the control path is absent.

The physical camera-to-indicator wiring and polarity remain an inference. The operator checklist must complete an independent wiring cross-check (idle system, no stream) and abort the first stream if the watched LED stays dark. The V4L2 core's shared-LED accounting is patch 0020.

### 1.2 GPU: two GMU boots, then a reset with no kernel trace

Debug boot `b1c603b5`: GMU firmware and HFI start twice (30.3 s and 58.9 s), both return 0; there is no panic, oops or SMMU message in the 385 KiB `kmsg-live` capture, whose last write is at 61.2 s. The reset happens after the desktop appears. The second start runs through the GPU runtime-resume path (`a6xx_gmu_pm_resume` -> `a6xx_gmu_resume`); recovery is not excluded by timestamps alone, but no `hangcheck recover!` appears. The GPU's configured inactivity delay is 66 ms (`a6xx_catalog.c:1580`, `adreno_gpu.c:1247`), so a service ordered only before GDM can miss earlier idle intervals. The existing pin targets only `3d00000.gpu`, has no proven readback, and does not touch `3d6a000.gmu`. The GMU is a supplier of the GPU: `a6xx_gmu_resume` takes `pm_runtime_get_sync(gmu->dev)` (`a6xx_gmu.c:1322`) and `a6xx_gmu_stop` drops it (`:1515`); it has no independent autosuspend timer. Pinning the GPU alone blocks `a6xx_gmu_stop` and is the correct discriminator; pinning the GMU as well is a different power-domain experiment and is not part of this round. The GMU `power/control` and `runtime_status` are read-only telemetry.

A silent reset is not proof of a hardware/firmware event, and one clean boot is not proof of a fix. Revision 20 must add a positive-control instrument, pin and log both devices, run a paired control boot, and repeat both conditions.

### 1.3 Audio and microphone: baseline correction

- The operator's **working** audio/microphone report was on the rev19 D28 ISO (`journal/2026-11-02.md`, "Device test round 2 and final ISO"), not on the rev18 capture. The failing round 3 is also rev19, with the same kernel and lazy IOMMU, but a later image (ceiling 1.0 instead of 0.251) and a camera oops in the same boot.
- The rev18-vs-rev19 amixer difference is real: rev18 `Speakers Volume`/PA max 31, value 6 (0 dB); rev19 max 6, value 0 (-9 dB). The late-probe cap clips to 6 but cannot lower a value of 6 to 0; the UCM `DisableSequence` writes 0 and the `EnableSequence` does not restore it. Adding PA 6 on enable is a correct restoration, but it is **not proven** to be the cause of the round-2-to-round-3 silence.
- The round-3 snapshot was taken before the user session. In the same boot, `CameraManager` oopsed at 61 s, so the audio/microphone failure is confounded by that oops. The microphone UCM files are identical between the compared images, and both snapshots select DMIC0/DMIC1 with DEC 100.
- The D28 ceiling is `api.acp.max-volume = 0.251` (-12 dBFS), the route default is `0.0` (fail-safe), and the startup helper must mute first and then set 30 %. The 1.0 ceiling in the round-3 image is full scale and conflicts with D26/D28.
- `IOMMU_DEFAULT_DMA_LAZY` is retained in revision 20. It was present on the working rev19 ISO, so it cannot explain the round-2-to-3 loss, and it is the configuration of the failing GPU round. A strict-IOMMU comparison, if wanted, is a separate boot variable, not bundled here.

The audio and microphone test must be the **first** action on a clean safe boot, with no camera application, before any camera stream.

## 2. Revision 20 changes

### WP1 - cameras (owner: cameras; kernel integration by kernel)

1. Patch 0003 (merged): csiphy0/1/2 `0x1000 -> 0x2000`; csiphy4 `0x4000 -> 0x2000` (shrink to the Hamoa/SM8550 window); VFE0/VFE1 `0x4000 -> 0xf000`; comment naming the 3-phase common block at `+0x1000`. The kernel worker must run integrated `CHECK_DTBS` and verify the six DTBs.
2. Independent cross-check of the corrected windows before the device boot; no safety claim from a single source.
3. Camera test order: graph (no stream), then front IMX681 first with the LED gate, then rear OV13858. Do not stream until the wiring cross-check is complete. IR illuminator and flash stay off (S2).
4. Front-first mechanism: libcamera's `simple` pipeline registers cameras in media-graph order; there is no upstream "default camera" switch. Try the pipewire/portal default by `Location::Front`; if no mechanism exists, the acceptance is "front listed first and selectable", not "portal always opens front".
5. RAW-to-RGB: the image ships Fedora libcamera 0.7.2 with the local IMX681 helper and per-sensor tuning under `/usr/share/libcamera/ipa/simple/`; verify those files are installed in the built image. CAMSS only delivers RAW; libcamera Software ISP performs demosaic/black level/WB/CCM/gamma. A RAW frame is an intermediate test, not acceptance.
6. Test plan: `media-ctl -p`, `v4l2-ctl --list-devices`, `cam -l`, `qcam`, saved RGB/YUV frames from both sensors, LED on during stream and off after the last stream, no oops.

### WP2 - GPU (owner: gpu; kernel integration by kernel)

1. Instrument first:
   - `CONFIG_PSTORE=y`, `CONFIG_PSTORE_CONSOLE=y`, `CONFIG_PSTORE_PMSG=y`, `CONFIG_EFI_VARS_PSTORE=y`; **no ramoops node** at the unverified `0x84000000` candidate. Prove the EFI backend with a pmsg sentinel and a warm reboot; only then qualify a fixed DDR range against the EFI map and independent cross-check.
   - `sp11-kmsg-tail`: immediate publication for severity <= 3 and for `adreno|msm|gmu|gpu|arm-smmu|qcom_scm|power/control|runtime|panic`, with durable sync.
   - Pin and log `3d00000.gpu` at the earliest udev add event (debug only) and in the service; read back the value, log path/written/readback to `/dev/kmsg`, fail visibly. Do **not** write `3d6a000.gmu/power/control`; log its `power/control` and `runtime_status` read-only. Add a `sp11.gpu_pin=0` control marker that skips the pin without changing the ISO.
   - Collector: `power/control`, `runtime_status`, `runtime_suspended_time` for the GPU and read-only GMU state; `/sys/kernel/debug/dri/*/gmu_log`; `sbsa_gwdt` bootstatus/status/timeleft; PMIC PON/reset reason (`qcom_pon`, boot reason) on the next boot; power-supply state.
   - Use `drm.debug=0x1ff`, dynamic debug for `drivers/gpu/drm/msm/*` and `drivers/iommu/arm/arm-smmu/*`, and ftrace `power:*`/`msm_gpu:*` if needed. **There is no `msm.debug` parameter**; do not add it. Available MSM parameters include `msm.hang_debug` and `msm.snapshot_debugbus`.
2. Experiment: debug with the GPU pinned versus a paired control boot with `sp11.gpu_pin=0`, repeated at least three times each on the same ISO. Record the GMU start/HFI sequence relative to the reset, the PON reason, the watchdog bootstatus, the AC/battery state, and whether pstore/kmsg survived. Use an outcome table; a reset with the pin does not prove the runtime-PM path, and a clean boot without a trace does not prove hardware. If the camera C-PHY stream can also hang the SoC, keep the camera and GPU experiments on separate boots.
3. Only if the pin changes the outcome, design the `msm` power-management fix; do not add a speculative GPU patch in revision 20.
4. Keep the GPU frequency limits at the Windows SKU; pinning is diagnostic and increases idle power.

### WP3 - audio and microphone (owners: audio-speakers, image)

1. PA gain restoration: write `SpkrLeft PA Volume 6`, `SpkrRight PA Volume 6` and stereo alias `Speakers Volume 6` in the Speaker `EnableSequence` after the DAC/BOOST switches; keep `DisableSequence` at 0. The kernel cap remains 6. Stage the audible test after the muted cap/sequence check (T2c).
2. Safety state: keep `device.routes.default-sink-volume = 0.0` as the fail-safe; the helper mutes first, then sets the usable level to 100 %, so a failed helper leaves silence and an unmute gives the maximum the kernel caps allow. **Remove `api.acp.max-volume`**: WirePlumber 0.5.19's ALSA plugin does not implement it (the image's `libspa-alsa.so` exposes only auto-port, auto-profile, hidden-ports, hidden-profiles, probe-rate, pro-channels, disable-pro-audio and use-eld-channels), so the 0.251 value was a no-op. The enforced ceiling is the kernel: PA <= 6 (0 dB), WSA RX/MIX <= 81 (-3 dB), with the UCM digital volume at 72 (-12 dB) and the startup mute. `api.acp.disable-pro-audio = true` is real and stays.
3. Microphone: on a clean safe boot, after the session, collect `wpctl status`, `wpctl inspect @DEFAULT_AUDIO_SOURCE@`, `amixer -c 0` for VA/DMIC/PA/RX, `alsaucm dump`, and a 2-second stereo `arecord` with per-channel RMS/peak and exit status. Verify DMIC0/DMIC1, `VA_DEC0/1 Volume`, `CaptureChannels 2`, default source and channel order. No UCM change unless the evidence shows one is needed. Do not retain speech samples.
4. Re-run D28 checks: open-loop selected, caps ready, PA <= 6, RX/MIX <= 81, the UCM digital volume at 72, sink starts muted at 0, and no nonexistent `api.acp.max-volume` property is claimed as the ceiling.

### WP4 - image and kernel integration (owners: image, kernel)

1. Image: keep the early collector; add the post-session collector (already implemented) and a documented manual "collect now" trigger (`systemctl --user start sp11-post-session-collect.service` or equivalent); run the camera collector after a stream attempt; copy both `/sys/fs/pstore` and `/var/lib/systemd/pstore`; add a `systemd-pstore` drop-in (`Storage=external`, `Unlink=no`) or verify the archive path; add the kmsg urgent markers to the regression test.
2. Kernel: series rev20 with the corrected camera patch; `CONFIG_PSTORE*` and `EFI_VARS_PSTORE`; keep `CONFIG_IOMMU_DEFAULT_DMA_LAZY=y`; build once under `flock` with BTF and `CHECK_DTBS=y`; run `kernel-check`; publish six DTBs; **rebuild the Spectra module unconditionally** against kernel-devel 20 and verify its vermagic (the release changes with series_rev 20). No ramoops node.
3. Image: extend the build/static gates to series_rev 20; update the DTB/UCM/JSON pins; add L0 checks for CSIPHY/VFE sizes and non-overlap, the new UCM PA 6, default 0.0, the real kernel ceiling (no `api.acp.max-volume`), helper mute-before-volume, the post-session unit, pstore copy, kmsg urgent match and the GPU-only pin helper with GMU read-only telemetry; update L1 for the new unit and the manual trigger; keep the allow-list evidence.
4. Build the private ISO, L0 zero failures, L1 PASS. Keep the rev19 ISO and RPMs for rollback. Add a fallback entry or document the re-flash rule if the rev20 safe entry does not reach GDM.

## 3. Execution contract for the next device round

One variable per boot, in this order, stopping at the first failure:

0. **Camera-disabled LED map (before any stream):** boot the safe entry with `module_blacklist=imx681,ov13858` so the gpio-leds are not claimed by the V4L2 privacy path. Set each LED's brightness to 1 and 0 (`/sys/class/leds/white:indicator` and `white:indicator-1`) and record which physical indicator lights (front near the user camera vs rear). This is the independent camera-to-indicator wiring cross-check; no stream and no manual simulation of a streaming LED. Reboot without the blacklist afterwards.
1. **Safe baseline:** no camera app, no audio test. Confirm boot, caps, collector, kmsg debug-only, no oops.
2. **Safe audio/microphone only:** clean boot, no camera app. Verify muted state, caps_ready, PA 6, ceiling; unmute and play a known tone; record the stereo microphone RMS/peak and channel order.
3. **Safe camera graph only:** no stream; collect media graph, video nodes, formats, `cam -l`, camera collector.
4. **Safe front stream:** only after the indicator wiring cross-check; watch the front LED; save an RGB/YUV frame; stop if the LED is dark.
5. **Safe rear stream:** repeat the LED/RGB checks.
6. **Debug GPU with pin:** both devices pinned, full kmsg/pstore/PON capture.
7. **Debug GPU control:** same ISO with `sp11.gpu_pin=0`, repeated; compare the outcome table.

Before the GPU boots, prove pstore with a pmsg sentinel and a warm reboot. Before any stream, complete the wiring cross-check. Archive every boot under `out/device-logs/<date>/<boot-id>/` with ISO hash, kernel NEVTA, entry, timestamps and excerpts; write the component evidence file and journal entry before triage. Never leave the only copy on the operator's Windows disk. Keep raw microphone/camera samples out of the repository; retain only RMS/peak, format and size.

### Rollback and gates

- Keep the rev19 ISO `49bbf53d…` and the rev19 RPMs; if the rev20 safe entry does not reach GDM, re-flash rev19 rather than debugging on the only boot medium.
- L0 must stay at 0 failures and L1 PASS; the new post-session unit, kmsg markers and pstore copy need their own checks and a positive control.
- A hardware value (CSIPHY window, PA 6, ceiling, sink default) needs an independent cross-check per protocol §5.1 before `sw-ready`; the device test is the final gate.

## 4. Acceptance (measurable)

- **Camera:** complete graph; front IMX681 listed first and selectable (or portal default by Location::Front if implemented); RAW frame as an intermediate; RGB/YUV frame with sensible colour through libcamera from both sensors; privacy LED on for every stream and off after the last; no `csiphy_reset` or other camera oops; IR illuminator/flash off.
- **Audio:** safe boot with no camera app and no camera stream; `speaker volume caps ready`, `caps_ready: 1`, PA 6, RX/MIX <= 81; sink starts muted at 0 and unmute gives the kernel-capped maximum (no `--limit 0.30`); a known tone is audible on both channels, undistorted, at least the rev19 working level and never above the kernel-capped maximum; no full-scale path. Report the effective `wpctl`/`pw-dump` volume and the hardware PA value, because percent-to-dB mapping is implementation-dependent.
- **Microphone:** stereo capture with correct channel order, speech-correlated signal and per-channel RMS above a defined threshold (record the threshold in the test plan), default source identified; no speech retained.
- **GPU:** outcome table with three pinned and three control boots; a reset is recorded with time, GMU start/HFI sequence, `power/control` readback, PON reason and pstore/kmsg survival; no reset over the matched observation window is only evidence, not proof. No silent reset is reported as a hardware conclusion.

## 5. Risks and open questions

- Fixing the CSIPHY mapping may reveal the next CAMSS/C-PHY failure; the graph and oops are the starting point, not the end.
- EFI-vars pstore may be unavailable or cleared by firmware; a silent reset may leave no record. The kmsg tail and PON reason are the fallback, and the result is inconclusive without a positive control.
- The round-3 audio/microphone loss is unproven; the clean audio-first boot is the discriminator. The PA 6 restoration is correct but not the proven cause.
- `IOMMU_DEFAULT_DMA_LAZY` is retained; a strict-IOMMU comparison is a separate experiment.
- Front-first libcamera enumeration has no upstream default; if no portal mechanism is available, the acceptance is "listed first and selectable".
- The camera indicator wiring is still an inference; the stream gate depends on the physical cross-check.
