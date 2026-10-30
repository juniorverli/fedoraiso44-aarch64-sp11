# GPU reset at session start: Windows driver REA and device logs

Date: 2026-10-30. Static analysis plus private M5 logs (boot `3f0e2cc1` GPU off,
stable; boot `0ee2fa1a` GPU on, reset at session start). No kernel build, no
device access. Builds on, and does not repeat, the
[2026-10-24 speed-bin evidence](2026-10-24-speedbin.md) and
[firmware evidence](2026-10-24-firmware-mesa.md).

## Inputs

| Item | SHA-256 (catalog-checked) | REA |
|:--|:--|:--|
| `DriverStore/qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkm8380.sys` | `46237eba1c2c0a51d700cdf14730aae3f41b0a55775a185b87e618cab8285814` | Ghidra 12.1.4, architecture arm64, opened and closed once |
| `.../qcdxkmsuc8380.mbn` (zap) | `950f17eb439326548cba20603b30cda653d612d1564feb397ddbd92987f0e8ac` | read as data with Python, not in REA |

REA evidence IDs: strings `ev_b4c15387962dd5ac6c9e60d35b4a1e8b4e24613e4df5e01cacb5fdf2c1703cbe`,
zap loader `ev_6d193f3e5efa902aa5b337e37c3365616bd2581db41bb6a251d1c91e8ec26bf2`,
GMU image loader `ev_1487c4ee2d64acaa2c41a4f200b5a65ab7fc0c69432bf954d795926ca5ff8d8e`,
GMU boot `ev_572f4bf01a7e2df3d4971454b2cb063b8d787d84e0aece9dfb2b33f664cc099a`,
region table `ev_27aeb00511bc19a565c712013c14acf20c7de3ab9e2a655dab35c341053bf40d`.

**Process deviation (Verified):** the returned analysis profile reports
`language_id: auto-from-header`, not a forced language. The target is a native
ARM64 PE and the output decodes sanely (no wrong-decode markers), but protocol
section 9.2 was not met literally; the REA server environment needs
`REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A` (sources worker request). No REA
timeout occurred. All other Windows binaries were not opened.

## Device facts (from logs)

- **Verified:** with GPU on, `adreno 3d00000.gpu` binds, DRM registers `msm`,
  and `gen70500_sqe.fw` fails with error -2 at probe (rootfs firmware not yet
  visible in the early environment). `gpu_gx_gdsc`, `gpu_cx_gdsc` and `gfx` are
  off, devfreq `cur_freq` 0, `max_freq` 1250000000, 11 OPPs. dmesg ends in
  unrelated audio messages; no GPU line precedes the reset. The reset is silent.
- **Verified:** the speed-bin read of 2 bytes at cell offset 0x119 fails in both
  boots (empty read), so the 1.25 GHz ceiling does not come from a fuse read.
  Treat the failed read as unexplained, not as proof of an alignment fix.
- **Verified:** `gpu-microcode` reserved memory is 8 KiB; the zap file is 12088
  bytes but its single loadable segment is 0x430 bytes (relocatable flag set),
  so it fits. Header-level fit is unchanged from the earlier evidence.
- **Verified:** `sbsa_gwdt` is loaded, so a hang can also appear as a reset.
- **Inference:** SoC is X1P64100 (Hamoa/Denali); Windows names the GPU
  "Adreno X1-85" and the Windows driver takes its chip 0x88 branch (below).
  The brief's "X1-45" is the Purwa part (Linux chip 0x43030c00, Windows 0x9a
  branch, separate `qcdxkmsucpurwa.mbn`); it does not apply here.

## 1. How Windows brings the GPU up

| Finding | Grade | Basis |
|:--|:--|:--|
| Zap file is chosen by chip enum: 0x88 selects `qcdxkmsuc8380.mbn`, 0x9a selects the Purwa file. Function `0x1404872b0` (called from `0x14048d9f8`, `0x1404999c8`). | Verified | decompile |
| The load request carries the constant 13 next to the image GUID: PAS id 13, same as Linux. The image path is built from the driver's own directory. | Verified (constant); Inference (field meaning) | decompile |
| Windows does not call SCM itself: it sends two requests (load, then authenticate-and-reset) to a platform PIL/TZ interface at a driver context pointer, retrying the load up to 20 times with 100 ms sleeps while the status has error bits. If all retries fail it calls a `SecureUcodeLoad` callback, and on authenticate failure a `SecureUcodeAuthenticate` callback. | Verified | decompile |
| Zap memory region and PIL sequencing are chosen by the Windows PIL driver, not by qcdxkm. Whether it uses the same 0x2000 region Linux reserves is not visible here. | Unknown | not in this binary |
| GMU firmware: registry value `GmuFwFile` (absent in the captured class key) overrides; otherwise an image embedded in the .sys is used. `DisableGmuACD` also exists. Function `0x1404a12a0`. | Verified | strings, decompile, class-key grep |
| Embedded GMU image is a stream of (address, size, type, value) blocks, same shape as Linux `block_header`. Region table: ITCM at 0 (16 KiB), DTCM at 0x10004000 (16 KiB), icache at 0x4000 (16 MiB minus 16 KiB), dummy at 0x60000000. These equal Linux `a6xx_gmu_fw_load` and `a6xx_gmu_memory_probe` for a7xx. | Verified | decompile plus region table vs `a6xx_gmu.c:876-918, 2337-2347` |
| GMU image version word is read from the same DTCM offset Linux reads through `GMU_CORE_FW_VERSION`. Value deliberately not recorded; comparing it with the Fedora `gen70500_gmu.bin` was not possible because that RPM is not in the workspace. | Unknown | firmware not available locally |
| GMU boot function `0x1404a2088` (X1-85 and Purwa only): sets `BOOT_CONFIG` to 2, clears `FW_INIT_RESULT`, writes the GMU chip id into `GMU_GENERAL_10`, releases `CM3_SYSRESET`, polls `FW_INIT_RESULT` (timeout 100000), then sets `HFI_CTRL_INIT` and polls `HFI_CTRL_STATUS`. Register offsets match `a6xx_gmu.xml`. Order and values match `a6xx_gmu_fw_start` for those registers. | Verified | decompile vs `a6xx_gmu.xml`, `a6xx_gmu.c:929-1060` |
| GDSC, regulator and clock ordering: Windows drives them through opaque callbacks and names `GmuPwrRequestPowerOn`, `GmuPwrQueryGxPowerState`, `GmuPwrGetCurVote` (GMU-managed GX). Concrete order not recovered. | Unknown | strings only |
| Speed-bin or fuse register: no fuse, QFPROM or bin string in qcdxkm; frequency ceiling comes only from the selected base file. | Verified (absence of strings); Unknown (any other mechanism) | string search |
| Frequency table of the selected base file: 1250, 1100, 1000, 925, 800, 744, 687, 550, 390, 300 MHz and an idle zero state. It has no voltage field, only `CORE_CLOCK`; voltage is not set by this file. | Verified (data); Inference (voltage by RPMh and GMU) | `tools/read-clock-table.py` plus field-name scan |

## 2. Differences from Linux 7.3

1. **GMU chip id (Inference, low risk):** Windows writes 0x7050001 when the
   chip revision field is 2, else 0x7050000. Linux hardcodes 0x7050001
   (`a6xx_catalog.c`, `gmu_chipid`). Equal for a v2 part ("C512v2"); unverified
   for this unit.
2. **AHB fence ranges (Inference, unproven):** Windows programs range 0 with
   upper field 0x28 and lower 0x8a0, plus a conditional range 1 (upper 0x8,
   lower 0x886) gated by a feature bit. Linux programs only range 0 with upper
   0x32 (`a6xx_gmu.c:977-991`) and never writes `GMU_AHB_FENCE_RANGE_1`.
   Whether a host access outside the fence while GX is collapsed can hang the
   bus here is Unknown. Register names for 0x886 to 0x88d are not in
   `a6xx.xml`.
3. **Linux-only 1175 MHz OPP (Verified, no reset link):** Windows has no
   1175 MHz state; Linux `hamoa.dtsi` `opp-1175000000` has mask 0x07. The other
   Linux OPPs up to 1250 MHz match Windows.
4. **DT (Verified):** `hamoa.dtsi` gpu, gmu, zap-shader memory-region and the
   Denali `firmware-name` match the Windows file selection and PAS id. GMU
   compatible is `qcom,adreno-gmu-x185.1`, correct for X1-85. No DT mismatch was
   found against Windows.
5. **PIL retry (Verified):** Windows tolerates early load failures by retrying;
   Linux only checks `qcom_pas_is_available()`.

## 3. Ranked likely reset causes and next step

The only Verified fact about the trigger is that it is the first DRM open
(`a6xx_pm_resume` boots the GMU, then `hw_init` loads the zap and calls PAS 13).
Both stages sit behind that one open, so the log cannot separate them. Rank:

1. **TZ/PAS authentication of PAS 13 resets or faults (Inference).** Gunyah/TZ
   aborts on the secure transition can reset the SoC without a kernel log.
   Windows uses the same file and PAS id, so a wrong file is unlikely; a wrong
   memory region (Windows PIL picks its own) or a region not mapped as the
   firmware expects is possible. Diagnostic: run the two stages separately.
   Stage 1: with a persistent log (`journalctl -f` to disk, `sync`), write
   `on` to `/sys/devices/platform/soc@0/3d00000.gpu/power/control` only
   (GMU boot, no zap). Stage 2: only if stage 1 survives, open `renderD128`
   once (`vulkaninfo --summary`). Reset in stage 2 points at PAS 13.
2. **GMU boot hang from the Linux gen70500 GMU image or register differences
   (Inference).** Reset in stage 1 points here, via watchdog. Diagnostic: also
   boot with `drm.debug=0x1e`, `printk.synchronous=1`, and read the Fedora
   `gen70500_gmu.bin` version word against Windows (needs the RPM staged).
3. **AHB fence mismatch (Inference, weakest).** Only worth a patch after 1 and 2
   are excluded and a bus-hang signature is seen.
4. **Speed-bin read failure (Unknown, unlikely).** A failed read selects the
   1.5 GHz-capable mask only for an unknown fuse; cur_freq is 0 at the reset, so
   it is not the trigger.
5. **Missing firmware at first open (Excluded by logs for the reset).** The
   -2 on `gen70500_sqe.fw` is at early probe only; a later open reloads it.

## Patch status

No minimal behavioral Linux patch is established: no Windows-versus-Linux
difference found is shown to cause the reset. No file added under
`hardware/gpu/patches/`.

## Requests

- **sources:** set `REA_GHIDRA_LANGUAGE_ID` in the REA server environment.
- **firmware / image:** stage the Fedora `gen70500_gmu.bin` so its version word
  can be compared; keep a persistent log path for stage runs.
- **orchestrator:** schedule the two-stage test above (S3, no firmware writes).
