# Revision 20 plan (2026-11-02)

Input: device round 3, logs `C:\sp11-logs-2-5` (boots `393849d8` safe, `b1c603b5` debug), ISO `49bbf53d…`, kernel `7.3.0-65.sp11.19.fc44`. The operator reports: audio and microphone stopped working compared with round 2; cameras still fail (black preview, no privacy LED, front camera not prioritised); debug still resets about 5 s after the desktop appears, with otherwise smooth graphics.

## 1. What the round-3 logs prove

### 1.1 Camera: kernel oops at stream-on (root cause verified)

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

`x2` is the CSIPHY ioremap base, the write is at `base + 0x1000`, and the mapping size is 0x1000. This is a driver/DT mismatch:

- `sources/linux/drivers/media/platform/qcom/camss/camss-csiphy-3ph-1-0.c:1217` sets `regs->offset = 0x1000` for `CAMSS_X1E80100`.
- `csiphy_reset()` (`camss-csiphy-3ph-1-0.c:953`) writes `CSIPHY_3PH_CMN_CSI_COMMON_CTRLn(regs->offset, 0)`, i.e. `base + 0x1000`.
- Our `hardware/cameras/patches/0003-arm64-dts-qcom-hamoa-describe-disabled-camera-blocks.patch` declares the CSIPHY regions as `0x1000` bytes each. Mainline 3-phase PHYs (sm8550/sm8650) use `0x2000`.

Consequence: the first camera stream-on writes outside the mapping, oopses, and the preview stays black; the sensor never streams, so the privacy LED (asserted on stream) never turns on. Fixing the region size is the first camera change of revision 20. The rear OV13858 is on a D-PHY and the front IMX681 on a C-PHY; both PHYs use the same 3-phase common block in this driver.

### 1.2 GPU: two GMU boots, then a reset with no kernel trace

Debug boot `b1c603b5`: GMU firmware and HFI start twice (30.3 s and 58.9 s), both return 0; there is no panic, oops or SMMU message in the 385 KiB `kmsg-live` capture, whose last write is at 61.2 s. The reset happens after the desktop appears, i.e. after the second GMU start, and is consistent with a hard reset (PMIC/PSU/firmware) rather than a kernel panic. The `power/control=on` discriminator is not proven to have run: nothing logs it and the second resume suggests the device still autosuspended.

### 1.3 Audio: 9 dB regression from the new late-probe caps; sink defaults are a second trap

- Round 2 (rev 18) amixer: `Speakers Volume` and both `SpkrLeft/Right PA Volume` had max 31 and value 6 (0 dB). The kernel cap log said `failed … : 1` because return 1 was misread as failure.
- Round 3 (rev 19): the caps really install. `WSA_RX*` clip 84 -> 81 (-3 dB) and `Spkr*.PA Volume` get `platform_max = 6` (0 dB). The PA value observed at boot is 0 (-9 dB), because `Surface11-SpeakerSeq.conf` never writes PA gain in `EnableSequence` and its `DisableSequence` writes 0. On rev 18 the hardware default 6 survived and gave 0 dB; on rev 19 it does not.
- `53-sp11-audio-ceiling.conf` also sets `device.routes.default-sink-volume = 0.0` (linear silence), and `sp11-audio-safety` mutes the sink at 5 % before the session. After the operator unmutes, the sink is still at 5 % (~-26 dB). Combined with the 9 dB PA loss this is effectively inaudible.
- Microphone: the UCM files are unchanged between rounds and the same DMIC path is selected (`VA DMIC MUX0=DMIC0`, `MUX1=DMIC1`, `VA_DEC0/1 Volume=100`). The round-3 snapshot was taken before the user session and the camera oops tainted the same boot, so there is no direct capture evidence yet. The next ISO must collect post-session capture state and an `arecord` RMS value.

## 2. Revision 20 work packages

### WP1 - cameras (owner: cameras; kernel integration by kernel)

1. Fix `hardware/cameras/patches/0003-…`: change every CSIPHY region from `0x1000` to `0x2000` (csiphy0/1/2/4), and audit every other CAMSS sub-block size against the X1E register map and mainline sm8550/sm8650 nodes. Add a comment naming the 3-phase common block at `+0x1000`.
2. Verify the fix at build time: DTB reg sizes, `CHECK_DTBS`, and a boot-time `dev_dbg` of the ioremap size versus `regs->offset` if useful. Keep the oops trace as evidence in `hardware/cameras/evidence/`.
3. Once streaming works, re-check the C-PHY link for IMX681 (lane count, settle, link frequencies) and the privacy LED (`cam_indicator_en`, TLMM 225): the LED must follow streaming, IR illuminator and flash stay off (S2).
4. Userspace: make the front IMX681 the first camera libcamera enumerates and the default for the portal; keep OV13858 as the second camera; SoftISP RAW->RGB with per-sensor tuning already shipped. The operator accepts libcamera and hardware acceleration for this first delivery.
5. Test plan: `media-ctl -p`, `cam -l`, `qcam` (front first), frame capture from both sensors, LED on while streaming, no oops.

### WP2 - GPU (owner: gpu; kernel integration by kernel)

1. Make the reset observable before changing the driver:
   - add a `ramoops` reserved-memory node and `CONFIG_PSTORE`, `CONFIG_PSTORE_RAM`, `CONFIG_PSTORE_CONSOLE`, `CONFIG_PSTORE_PMSG`; `systemd-pstore` saves dmesg-ramoops after reboot and the collector copies it;
   - change `sp11-kmsg-tail` to sync immediately on `KERN_ERR` and on lines matching `adreno|msm|gmu|arm-smmu|qcom_scm|panic`, not only every 10 s;
   - log `power/control`, `runtime_status` and `runtime_suspended_time` for `3d00000.gpu` every cycle; make `sp11-gpu-no-runtime-pm` write a kmsg line with the path and resulting value, or fail visibly.
2. With runtime PM pinned on, repeat the debug boot. If the reset disappears, the bug is in the GPU/GMU runtime suspend-resume path and the fix belongs in `msm` power management; if it persists, it is in the command/GMU path.
3. Enable GPU/IOMMU diagnostics for the experiment (`msm.debug`, IOMMU fault logging, GMU HFI message traces) and compare the X1E GPU OPP, power domains, interconnects and reset sequence with the `linux-sp11` tree. Use REA on the Windows GPU miniport only if the programming sequence is needed.
4. Test plan: debug entry, time of reset, pstore contents on next boot, four GMU start markers, no frequency above the Windows SKU limit.

### WP3 - audio and microphone (owners: audio-speakers, image)

1. Restore the 0 dB PA operating point: write `SpkrLeft PA Volume 6` and `SpkrRight PA Volume 6` in the Speaker `EnableSequence` (after the DAC/BOOST switches), and `Speakers Volume 6` as the stereo alias; keep `DisableSequence` at 0. The kernel cap remains 6, so the write is legal and the D26 ceiling is unchanged.
2. Fix the startup sink state: `device.routes.default-sink-volume` must not be 0.0; use 0.5 (about -6 dB), and change the safety service to leave the sink at a usable level (for example 30 %) while keeping it muted until the operator unmutes. The kernel caps and the startup mute remain the protection.
3. Microphone: after the session, collect `wpctl status`, `wpctl inspect` of the default source, `amixer -c 0` for VA/DMIC controls, `alsaucm dump`, and a 2-second `arecord` with its RMS/peak. Verify `VA DMIC MUX0/1`, `VA_DEC0/1 Volume`, `CaptureChannels 2` and the default source. No UCM change unless the evidence shows one is needed.
4. Re-run the D28 safety checks: caps ready, open-loop selected, no PA value above 6, no full-scale ceiling.

### WP4 - image and kernel integration (owners: image, kernel)

1. Image: move the audio/camera collection to a post-session unit (after `graphical-session.target`) with a bounded wait, keep the early snapshot too, add the pstore copy and the immediate kmsg sync, and collect the camera graph after a stream attempt (read-only, no LED/flash control).
2. Kernel: add the pstore/ramoops configuration, assemble `kernel/series` revision 20 from the camera and GPU patches (plus the audio UCM is image-only), build once under `flock` with BTF, run `kernel-check`, publish all DTB variants, rebuild the Spectra module if its kernel dependency changes.
3. Image: rebuild the private ISO, L0 must stay at 0 failures, L1 must pass with the new collector deadlines.
4. Device test order: safe entry for camera graph, front-first enumeration, LED, audio and microphone; debug entry for GPU pstore and reset timing.

## 3. Acceptance for the next device round

- Safe: no `csiphy_reset` oops; `cam -l` lists IMX681 first and OV13858 second; a frame is captured from both; privacy LED on while streaming and off otherwise.
- Safe: audio plays at the round-2 level or louder after unmute; microphone records non-zero RMS; UCM caps remain installed and the sink starts muted.
- Debug: either no reset, or a pstore/kmsg record identifying the fault; `power/control` state is logged in every capture.

## 4. Risks and open questions

- Fixing the CSIPHY mapping may reveal the next CAMSS/C-PHY failure; the graph and oops are the starting point, not the end.
- A PMIC/PSU hard reset may not leave a ramoops record; immediate kmsg sync is the fallback, and a reset with no trace will be treated as a hardware/firmware power event.
- The 9 dB audio regression is inferred from the two amixer snapshots and the cap code; the UCM PA write is the safe correction either way.
- The microphone has no post-session evidence yet; WP3 closes that gap before any further kernel change.
