# Suspend (s2idle), thermal and battery policy: reference review and design

Date: 2026-10-31. Inputs: Ubuntu SP11 reference (`out/ref/ubuntu-surface-pro-11`, commit `049b1ca`), M13 private log set (`out/device-logs/m13-20261031/<boot id>`, kernel `7.3.0-65.sp11.10`, entry `debug`; nothing identifying copied), Linux `v7.3` plus `kernel/series`, Windows ACPI and thermal inventory. REA was not used. Nothing built, run on the device or committed.

Grades follow `agents/protocol.md` section 5. Linux paths are relative to `sources/linux/`.

## 1. Their suspend fix, and whether we need it

### Verified

| # | Fact | Source |
|:--|:--|:--|
| V1 | The reference reports s2idle working: lid close, backlight off, 60 s, `systemctl suspend`, power-button resume. Their kernel is Jens Glathe's `7.1.3-jg-1`, on a **12-CPU** unit (`status` prints `0/12`). | `SUSPEND.md:1-8`, `README.md:108-122`, `scripts/sp11-fix-cpuidle-s2idle` |
| V2 | Their root cause: every real suspend reset the machine at `PM: suspend entry (s2idle)`; `pm_test` levels `freezer`, `devices`, `platform` pass, `none` crashes; disabling cpuidle `state1` (`cpu-sleep-0`, 500 us) makes s2idle use WFI and everything works. No pstore/ramoops region, so the failing point is invisible. | `SUSPEND.md:20-52` |
| V3 | Their own caveat: the crash "behaved as transient firmware state", appeared after instability, persisted across warm reboots and later cleared with `cpu-sleep-0` still enabled. They keep the workaround as a safety net. | `SUSPEND.md:50-55` |
| V4 | The fix is a `system-sleep` hook (`pre/suspend` disable, `post/suspend` enable) that writes `state1/disable` by **hard-coded index** on `cpu[0-9]*`. systemd 259 reads hooks only from `/usr/lib/systemd/system-sleep/`. | `system-sleep/sp11-cpuidle-s2idle`, `scripts/sp11-fix-cpuidle-s2idle` |
| V5 | Their other pieces: `HandleLidSwitch=ignore` plus a Python lid daemon (writes `/sys/class/backlight/dp_aux_backlight/brightness`, 60 s timer, disables every wake source except `pwrkey`), a `hexagonrpcd` hook condition fix (`ConditionFirmware=device-tree-compatible(qcom,x1e80100)` replacing `qcom,sdm670`), selective SSAM dynamic debug, kernel arguments `no_console_suspend pm_debug_messages mem_sleep_default=s2idle`. | `SUSPEND.md:57-130`, `scripts/sp11-lid-backlight`, `systemd/hexagonrpcd-condition-override.conf`, `grub/99-surface-pro-11.cfg` |
| V6 | Our cpuidle states equal theirs: one CPU state `cpu-sleep-0` (`ret`, PSCI param `0x4`, entry 180 + exit 320 = 500 us, residency 600 us); cluster states CL4 `0x01000044` and CL5 `0x01000054`; system state SS3 `0x0200c354`. The two cluster and the system state are **not** cpuidle states: they are genpd domain states. | `arch/arm64/boot/dts/qcom/hamoa.dtsi:278-313`, M13 `cpuidle.txt` (only `WFI` and `cpu-sleep-0` per CPU) |
| V7 | In s2idle the deepest enabled state with `enter_s2idle` is used, and it honours the per-state `disable` file. For hierarchical PSCI the **last cpuidle state carries the domain logic**: `enter_s2idle = psci_enter_s2idle_domain_idle_state`, which calls `dev_pm_genpd_suspend()` so the cluster and system genpd choose their idle states. Disabling `cpu-sleep-0` therefore removes retention **and** every cluster/system PSCI state at once. | `drivers/cpuidle/cpuidle.c:84-105`, `drivers/cpuidle/cpuidle-psci.c:64-95,115-120,266-272` |
| V8 | Our parity DT (patch `hardware/soc-boot/patches/0001`, in `kernel/series`) deletes `cpu7`, `cpu11` (MADT UID 7 and 11 disabled) and **removes the system domain's SS3 reference**; CPU C4, CL4 and CL5 remain. M13 shows 10 CPUs online, PSCI OSI mode, `power-domain-system` always `on` (no state), clusters 1 and 2 at `off-1` (CL5) during the session, cluster 0 `on`. | `hardware/soc-boot/README.md` section 2, M13 `genpd_summary.txt`, `dmesg.txt` (`psci: OSI mode supported`, `CPUidle PSCI: Initialized CPU PM domain topology using OSI mode`) |
| V9 | `cpu-sleep-0` retention works at runtime on all ten CPUs: 15,786 to 33,818 entries and 76 to 97 s residency per CPU in M13. | M13 `cpuidle.txt` |
| V10 | The kernel has `CONFIG_PM_DEBUG=y`, `CONFIG_PM_SLEEP_DEBUG=y`, `CONFIG_PSTORE=y`, `CONFIG_PSTORE_RAM=m`, `CONFIG_EFI_VARS_PSTORE=y` (default disabled), `CONFIG_RTC_DRV_PM8XXX=m`. No ramoops memory region exists in the DT (same as theirs). | `out/build/kernel/check/root/lib/modules/7.3.0-65.sp11.10.fc44.aarch64/config` |
| V11 | **s2idle rejects `pm_test` levels `processors` and `core`**; only none, freezer, devices, platform are supported. The requested ladder's last two rungs exist only for `mem_sleep=deep`. | `kernel/power/suspend.c:583-586` |
| V12 | The PMIC RTC alarm is owned by the ADSP: `qcom,no-alarm; /* alarm owned by ADSP */`. A timed wake (`rtcwake`) is therefore not available on Linux; real suspend steps need a manual wake. | `arch/arm64/boot/dts/qcom/hamoa-pmics.dtsi:223-230` |
| V13 | Our backlight is not theirs: `/sys/class/backlight/backlight` (pwm-backlight, `max_brightness` 4095, type raw), not `dp_aux_backlight`. Their lid daemon cannot be reused as is. | M13 `backlight.txt`; `hardware/display-lcd/patches/0003` |
| V14 | `hexagonrpcd` is not in our image (package list); `fastrpc` is loaded but CDSP FastRPC fails (dsp-subsystems M12). Our DT compatible list is `microsoft,denali-lcd`, `microsoft,denali`, `qcom,x1p64100`, `qcom,x1e80100`, so their `ConditionFirmware` string would match here. | M13 `pkgs.txt`, `lsmod.txt`; `arch/arm64/boot/dts/qcom/x1p64100-microsoft-denali.dts` (compatible property) |

### Inference

| # | Statement | Rests on |
|:--|:--|:--|
| I1 | Their `pm_test` bisection localises the fault to "idle entry", but cannot separate **retention** from **cluster/system domain states** (V7). The most likely culprit on their kernel is the deepest requested composition (cpu + CL5 + SS3, the hamoa default), not retention itself. | V6, V7 |
| I2 | Our parity DT avoids the **system-level** request (SS3) by construction, so the most likely crashing composition is not requested. It does **not** prove that "all three clusters off at once with only CL5" is safe: at runtime cluster 0 always stays up (the collector runs on it) and the system domain has never been tested, so s2idle is the first time every cluster idles together. | V8, V9 |
| I3 | With SS3 removed, s2idle will be correct but may use more power than Windows modern standby, because the OS never asks for system-level sleep. Power draw in s2idle is a separate, later question (SS3 re-enable is soc-boot Q2). | V8 |
| I4 | The guard is cheap insurance: during suspend only, `cpu-sleep-0` is disabled and restored to the exact previous values. It is applied by default in our hook until `real-noguard` passes. By-name lookup (not `state1`) is needed because a different DT can reorder states. | V4, V7 |
| I5 | Their "transient firmware state" remark (V3) means one pass or one fail is weak evidence: the ladder records every boot's result with the kernel and boot id so repeats can be compared. | V3 |

### Decision

Do **not** treat `cpu-sleep-0` as proven bad on our DT. Ship the guard as a default-on suspend-only safety net (`sp11-cpuidle-guard`, `system-sleep/sp11-suspend`) and let the opt-in ladder decide: rung `real-guard` (guard on) must pass first; rung `real-noguard` (guard off, `sp11.suspend_cpuidle_guard=0` for normal use) shows whether our parity DT needs it. If `real-noguard` resets, keep the guard and record the failing composition for soc-boot. A later experiment re-adds SS3 (separate DTB variant) only after both pass.

## 2. What suspend and resume depend on

### 2.1 DSPs

| Item | Fact | Grade |
|:--|:--|:--|
| ADSP/CDSP PM | `qcom_q6v5_pas.c` has no `dev_pm_ops`; its only PM code is `device_init_wakeup(pas->dev, true)` at `:886`. `qcom_glink_native.c`, `fastrpc.c`, `pmic_glink.c`, `ucsi_glink.c`, `qcom_battmgr.c` define no system-sleep ops either. Both remote processors keep running through s2idle. | Verified (grep); "keep running" Inference |
| ADSP role | Charger and UCSI transport (`pmic-glink`), audio PDR, sensors PD, and the owner of the RTC alarm (V12). No battery role on our image: D23 uses SAM. A UCSI event during sleep has no wake flag; USB wake would come from the PDC IRQs of the USB PHYs (`dp_hs_phy_irq`, `dm_hs_phy_irq`, `ss_phy_irq` in M13 `interrupts.txt`). | Verified (code, M13); wake behaviour Unknown |
| CDSP "stall" | M13: CDSP `running`, IPCRTR/FastRPC open fails (dsp-subsystems M12). `genpd_summary` shows the `nsp` domain `off-0` while its child `32300000.remoteproc` is `suspended`. The watchdog IRQ `q6v5 wdog` is a PDC (wake-capable) line, count 0. dsp-subsystems hypothesis C4: proxy votes dropped at handover. | Verified (M13 state); effect on suspend Hypothesis: a CDSP watchdog bite could wake s2idle or trigger remoteproc recovery on resume. Observation: the ladder records `remoteproc` state and wdog/glink IRQ counts before and after every rung |
| `hexagonrpcd` | Their suspend hooks stop the sensor daemon so that `/dev/fastrpc-adsp` is not held across suspend. Not shipped by us. If the sensors worker ships it and the Fedora package carries the same suspend/resume units, apply their one-line condition fix (our DT matches `qcom,x1e80100`, V14). | Inference; Fedora package contents Unknown |
| Stopping a DSP for the test | An experiment arm (stop CDSP before the real rung, start it after) is **not** implemented: dsp-subsystems forbids collectors from restarting a DSP. It is a request to that worker if the ladder shows a CDSP-related wake or hang. | Request |

### 2.2 Type Cover (SAM) and the keyboard freeze at Windows start

| Item | Fact | Source |
|:--|:--|:--|
| Suspend path | `.prepare`: display-off (an **error aborts the whole suspend**); `.suspend`: D0-exit, then arm the EC wake IRQ if the device may wake, then `ssam_controller_suspend`. Resume: `ssam_controller_resume`, disarm, **D0-entry**; `.complete`: display-on. Children (keyboard, touchpad HID) suspend before and resume after the parent. | `drivers/platform/surface/aggregator/core.c:410-505` |
| Shutdown path | display-off, D0-exit, **no D0-entry**. The operator's keyboard freeze at Windows start follows this path (ec-sam `2026-10-31-m13-keyboard.md`). | `core.c:793-800` |
| Wake | `device_set_wakeup_capable(dev, true)` only; default **disabled** (spurious wakes upstream). So the Type Cover cannot wake the machine unless `power/wakeup` is set to `enabled`; the EC line is TLMM 91, PDC 157 (`ssam_wakeup`, count 0 in M13). | `core.c:729-738`, `drivers/pinctrl/qcom/pinctrl-x1e80100.c:1819`, M13 `interrupts.txt` |

Inference (important for the ec-sam experiments):

1. A suspend, even `pm_test=devices`, performs the **display-off, D0-exit, D0-entry, display-on** round trip from Linux and returns to a working keyboard if the EC accepts it. That is the first safe, no-reboot experiment on the EC's D0 state machine: if the cover is dead after the `devices` rung, the freeze mechanism reproduces inside Linux and `silent`/`clean` shutdown experiments can be judged without rebooting into Windows.
2. Conversely, a ladder run confounds the ec-sam shutdown experiments if both happen in the same boot. **Do not run `sp11.suspend_diag` and a `sp11.ssam_*` shutdown-mode cycle in the same boot**; the ladder collector line records `sp11.suspend_diag` so the log set shows which kind of boot it was.
3. If SAM display-off fails at `.prepare`, suspend aborts and `suspend_stats` shows `failed_prepare` with `last_failed_dev` = the serial hub. The ladder prints exactly this.

### 2.3 Wake sources

| Source | State | Grade |
|:--|:--|:--|
| Lid (`gpio-keys`, TLMM 2, PDC 70) | `wakeup-source`, `wakeup-event-action = EV_ACT_DEASSERTED` (wake on lid **open**); IRQ `gpio_keys` registered, count 0 (the lid was never toggled in M13). | Verified (DT `x1-microsoft-denali.dtsi:20-32`, map `pinctrl-x1e80100.c:1812`, M13) |
| Power button (`pmic_pwrkey`) | `pon_gen3_pwrkey_data.wakeup_source_default = true`; IRQ registered. | Verified (`drivers/input/misc/pm8941-pwrkey.c:452`, M13) |
| Type Cover (SAM) | Disabled by the driver (2.2). | Verified |
| PCIe (Wi-Fi `0004:00:00.0`, `0006:00:00.0`) | `*:wakeup` GPIO 148/154, PDC 97/100. Wi-Fi/NVMe wake is not wanted. | Verified (M13) |
| USB PHY IRQs (PDC), touch (`spi0.0`), pen | Reference reports spurious wake from touchscreen, pen and `gpio-keys`. Our touch uses SPI HID (`spi0.0`, GPIO 51), wake state Unknown. | Unknown |

The collector lists every `power/wakeup` file with its state before a ladder run, and the ladder refuses a real rung if neither the power button nor the lid wake source is enabled.

### 2.4 Display and backlight

| Item | Fact | Grade |
|:--|:--|:--|
| Path | pwm-backlight on PMIC PWM, enable GPIO and supply GPIO, eDP panel through `panel-edp`; DPU/eDP controller clocks and `mdss_gdsc`. | Verified (display-lcd dossier and patches, M13 `genpd_summary` `mdss_gdsc on`) |
| Resume risk | eDP link retraining after the panel power sequence (500 ms wait), HPD mux (display-lcd patch 0002), backlight PWM restore. A dark panel after resume would hide everything (risk R1). | Inference |
| Evidence | The ladder records, before and after each rung, `backlight/brightness`, `bl_power`, the eDP connector `status/enabled/dpms`, and the PM-filtered dmesg slice (`panel`, `msm`, `ssam`, `psci`, ...). | Design |
| Lid-close policy | Our units do not blank the panel from a daemon. Fedora-native: logind `HandleLidSwitch`, with GNOME/mutter doing the DRM disable at `PrepareForSleep`. The default image keeps `ignore` (`50-sp11-lid.conf`) until suspend is evidenced; `sp11.suspend_lid` turns on the stock "lid close suspends". | Design |

## 3. Design: Fedora-native suspend integration

All files are under `hardware/power-thermal/userspace/overlay/` and mirror their install paths.

| Piece | Path | Purpose |
|:--|:--|:--|
| Sleep policy | `usr/lib/systemd/sleep.conf.d/50-sp11.conf` | `SuspendState=freeze`, hibernation, hybrid and suspend-then-hibernate off (no swap; S4) |
| Lid policy default | `usr/lib/systemd/logind.conf.d/50-sp11-lid.conf` | `HandleLidSwitch*=ignore` until suspend is evidenced |
| Lid opt-in | `sp11-suspend-policy.service` + `sp11-suspend-policy.sh lid` | `sp11.suspend_lid`: writes `/run/systemd/logind.conf.d/60-sp11-lid-suspend.conf` before logind starts |
| Wake policy | `sp11-wakeup-policy.service` + `sp11-suspend-policy.sh wakeup` | `sp11.wakeup_policy[=cover]`: keep only power button and lid; `cover` also enables the SAM wake line |
| cpuidle guard | `usr/libexec/sp11/power-thermal/sp11-cpuidle-guard` | by-name disable/restore of `cpu-sleep-0`, restores prior values |
| Sleep hook | `usr/lib/systemd/system-sleep/sp11-suspend` | pre/post records to `/run/sp11-suspend-diag/hook.log`; applies the guard unless `sp11.suspend_cpuidle_guard=0` |
| Ladder | `usr/libexec/sp11/power-thermal/sp11-suspend-diag` + `sp11-suspend-diag.service` | opt-in only, `sp11.suspend_diag=1..4`, see section 4 |
| Kernel arguments (image GRUB, debug entries only) | `mem_sleep_default=s2idle no_console_suspend` (add `pm_debug_messages` for the ladder boot) | s2idle is the mode; console output survives suspend |
| Collector | `collector/power-thermal.sh` | read-only capture for every log set |
| Thermal sampler | `sp11-thermal-sample` + `sp11-thermal-sample.service` | `sp11.thermal_log=1|sam`, read-only CSV |

Not adopted from the reference: the Python lid daemon (wrong backlight name, bypasses logind and GNOME inhibitors, disables all wake sources including the lid), `/usr/local/sbin` installs, the 60 s delay (a Fedora logind setting would need `HandleLidSwitch=ignore` plus a timer; not needed to learn where suspend breaks), unconditional SSAM dynamic debug (cheap to add later through the `sp11.entry` GRUB lines: `ssam_controller_suspend`, `ssam_ctrl_notif_*` with `dyndbg`).

dracut/udev: nothing is needed in the initramfs for suspend. A udev rule is not needed because the wake policy is a boot-time opt-in; the units are ordered after `multi-user.target`.

## 4. Diagnostic ladder (`sp11-suspend-diag`)

**Warning.** The real rungs can hang the device or reset it, and a driver hanging in a suspend callback hangs even a `pm_test` rung. **Hard-reset path:** hold the power button until the device is off (Microsoft's published Surface procedure is about 20 s; if still dead, hold Volume Up and Power for 15 s, release, wait 10 s; not verified on this unit). The boot USB stick survives a hard reset. The ladder is never automatic: it needs `sp11.suspend_diag=N` on the kernel line (a GRUB entry the operator picks), waits 150 s after boot for the collector's first snapshots, and writes `/run/sp11-suspend-diag/done` so it runs once per boot.

| Rung | `sp11.suspend_diag` | What it exercises | Resumes by itself |
|:--|:--:|:--|:--|
| `freezer` | 1 | task freezer | yes (5 s) |
| `devices` | 1 | all driver `.suspend`/`.resume` including the SAM D0-exit/D0-entry round trip, display, NVMe, Wi-Fi, USB | yes |
| `platform` | 1 | noirq stage and platform hooks | yes |
| `processors`, `core` | 4 | CPU offline/syscore; **only** with `mem_sleep` listing `deep` (V11) | yes |
| `real-guard` | 2 | real s2idle, `cpu-sleep-0` disabled | **no**: power button or lid open |
| `real-noguard` | 3 | real s2idle, `cpu-sleep-0` enabled | **no** |

Before each rung it records `suspend_stats`, cover input devices, SAM device count and error count, backlight and eDP state, `remoteproc` state, guard state and the hottest zone. It writes `BEGIN` before and `END` after, then copies everything to the boot medium (S4) through `sp11-log-collector once` (the collector's own boot-disk-only logic). After a hang or reset the last durable line in `extra-power-thermal.txt` is `BEGIN <rung>` with no `END`: that rung is where suspend breaks. Skip it on the next boot with `sp11.suspend_diag_skip=<rung>` or resume the ladder with `sp11.suspend_diag_from=<rung>`.

Reading the result: pm_test rungs pass and `real-guard` hangs = domain/retention independent of the guard (report to soc-boot, try `sp11.suspend_diag_skip`-style isolation with SS3 absent); `real-guard` passes and `real-noguard` resets = our DT still needs the guard; both pass = the guard can become opt-in. `END` with `rc=0` and `slept_wallclock` near zero = immediate spurious wake: see `wake_irq`.

Known limit: the flush runs the full collector snapshot, which shares `/run/sp11-logs` with the running collector. A lock-free `publish-extra` subcommand would be better (request R-I2).

## 5. Thermal

### 5.1 What Linux 7.3 provides (Verified from M13 and source)

| Item | Fact |
|:--|:--|
| Zones | 58 thermal zones from tsens and PMIC temp alarms: `aoss0-3`, `cpu{0,1,2}-{0..3}-{top,btm}`, `cpuss{0,1,2}-{top,btm}`, `mem`, `video`, `nsp0-3`, `gpuss-0..7`, `camera0/1`, `pm8550`, `pm8550ve-2/8/9`, `pmc8380-3..6` (`thermal.txt`). The zones for the two absent CPUs remain; their sensors read normally. |
| Trips | CPU, CPUSS: one `critical` at 115000 mC. `aoss`, `mem`, `video`, `nsp`, `camera`: `hot` 90000 (hyst 2000) and `critical` 115000. `gpuss`: `passive` 95000 and `critical` 115000. PMIC: `passive` 95000 and `hot` 115000. `hamoa.dtsi:9099-` |
| Governor | `step_wise`; no CPU passive trip and **no CPU cooling-map**. `cooling-maps` exist only in the eight `gpuss` zones (`hamoa.dtsi:9645-`). |
| Cooling devices at runtime | Only `PCIe_Port_Link_Speed_0004:00:00.0` and `ath12k_thermal` (M13). **No cpufreq cooling.** |
| cpufreq | **Not registered in M13**: `/sys/devices/system/cpu/cpufreq` is empty, `scmi_cpufreq` is not loaded (`lsmod`), only `scmi-perf-domain: Initialized 3 performance domains` appears. The module exists in the kernel (`CONFIG_ARM_SCMI_CPUFREQ=m`) and `image/expected-modules.txt` lists it as `late`. The cause of the missing load is Unknown. Consequences: no frequency scaling under Linux control and no cpufreq cooling. soc-boot acceptance ("cpufreq scaling on all three clusters") is therefore **not met**. |
| LMh | `CONFIG_QCOM_LMH=m`, but `hamoa.dtsi` has no LMh node: no Limits Management hardware mitigation is configured by Linux. |
| Fuel-gauge BCL | No Linux handler (qcom_battmgr is blacklisted, D23; no BCL driver for SAM). |
| SAM sensors | `surface_temp` (TC_TMP) and `surface_fan` are bound (`ec-sam` log); the kernel reports `hwmon4 temp1..3 not attached to any thermal zone`. Fan RPM is a read-only SAM request (TC 5, TID 1, IID 1, CID 1; patch ec-sam 0003); M13 did not read hwmon, so RPM validity is Unknown. |

### 5.2 What the Windows policy has (Verified from ACPI, with limits)

Static defaults from `acpi/dsdt.dsl` (SHA-256 `8a7b849b...a8ede`), unit deci-Kelvin, converted to Celsius. Zones marked dyn also contain methods that may rewrite values at run time; the effective numbers need the REA pass.

| Zone (`_SB.`) | HID | Covers (`_TZD`) | `_PSV` | `_CRT` | `_TC1/_TC2/_TSP` |
|:--|:--|:--|:--|:--|:--|
| TZ1, TZ3, TZ5 | QCOM0C58, 0C59, 0D01 (temperature) | PEP0 | 3780 = 104.85 C | none | 0 / 1 / 5 s, 0.1 s, 0.1 s |
| TZ99 | QCOM0C5A | 12 CPUs, PEP0, GPU0, WLTM, PMBM, CSW0 | 3780 = 104.85 C | 3880 = 114.85 C | 4 / 3 / 1 s |
| TZ32 (dyn) | QCOM0C5F | 12 CPUs | dynamic | 3880 = 114.85 C | 0 / 1 |
| TZ31 (dyn; present only when `SDFE == 0x88`) | QCOM0C5E | PEP0, GPU0 | 3630 = 89.85 C | 3830 = 109.85 C | 0 / 20 / 3 s |
| TZ33 (dyn) | QCOM0C60 | GPU0 | dynamic | 3830 = 109.85 C | 3 / 2 |
| TZ6 | QCOM0C91 | GPU0 | 3680 = 94.85 C | none | 1 / 2 |
| TZ35, TZ36, TZ37 (dyn) | QCOM0C62-0C64 | MSKN, MJCT, MBJ0; MBS1; MBS2 | 3680 = 94.85 C | 3880 = 114.85 C | 0 / 20 |
| TZ11 | QCOM0CBF | CSW0 | 3780 = 104.85 C | none | 0 / 1 |
| TZ51-TZ57 | OEM2UPDX65TS01, 75TS1-6 | MPA, TMD1-9 | 3680 = 94.85 C | 3930 = 119.85 C | 1 / 2 |
| TZ15-TZ24 (dyn) | QCOM0CF2-0CFC (CPU core parking, per cluster, GPU, NSP, MSKN, MBCL, WLTM) | as named | dynamic | dynamic | Unknown |
| FAN0 (`PNP0C0B`, `_STR "SAM FAN"`) | | `_DEP SSH` | | | **only `_STA`**: no `_FST/_FSL/_FIF` |
| TPOL (MSHW0187), TZ01-TZ0C (MSHW0188) | SurfaceThermalPolicy, SurfaceSmfClient | Surface thermal policy and nine SAM zone sensors | not in ACPI | not in ACPI | policy lives in the SMF stack |

Other Verified Windows data: `ThrottleReasons=0` and `PassiveLimit=100%` in `tz-samples.txt` for all zones (the sampling conditions are unknown); the TZ31-TZ37 samples read 2552 and 2330 dK (-17.95 and -40.0 C), which are sentinel values for inactive ADC zones, so the effective limits probably come from TZ1/TZ3/TZ5/TZ99; the FGBCL live registry values (5.4). `TZ51-TZ57` depend on `TMDx` devices whose `_STA` requires `PSUB == "CRD08380"` (the reference design): inactive on a Surface (Inference).

### 5.3 Delta Linux versus Windows and a lowering-only alignment (S6)

The comparison needs the sensor-to-zone mapping, which is Unknown (REA/Windows). The table uses the closest functional match and is only valid as an upper-bound rule: **every Linux value must be less than or equal to the Windows value.** Proposed values round the Windows number down to a whole degree.

| Linux zone group | Linux now | Windows closest | Delta | Proposal (lower or equal only) |
|:--|:--|:--|:--|:--|
| cpu*, cpuss* `critical` | 115.0 C | TZ99/TZ32 114.85 C | **Linux +0.15 K** | `critical` 114000 mC (or lower) |
| cpu*, cpuss* passive | none | TZ99 / TZ1 104.85 C | Linux has **no** passive mitigation; the first action is the emergency critical | add `passive` 104000 mC (or lower) with a cpufreq cooling map; **requires a registered cpufreq driver** |
| gpuss `passive` | 95.0 C | TZ6 94.85 C | Linux +0.15 K | 94000 mC |
| gpuss `critical` | 115.0 C | TZ33 109.85 C | **Linux +5.15 K** | 109000 mC (GPU is off: D22; gpu worker owns it) |
| aoss, mem, video, nsp, camera `hot` 90.0 / `critical` 115.0 | | TZ31 89.85 / 109.85 C (inactive on this unit per samples) | `hot` +0.15 K, critical +5.15 K against TZ31 | `hot` 89000, `critical` 109000 if TZ31 maps here; otherwise 114000 |
| PMIC `passive` 95.0 / `hot` 115.0 | | no zone found | Unknown | keep; add nothing |
| Skin-like zones (MSKN, MJCT, MBJ0, MBS1/2) | no Linux zone | TZ35-37 94.85 / 114.85 C | none present in Linux | the SAM hwmon sensors are not zones; adding them as zones with the same limits is a design option, not a need |

No patch is written: the mapping is Inference, a passive trip with no cooling device does nothing, and cpufreq is not registered. The design is: (1) get `scmi_cpufreq` registered (soc-boot, image); (2) once it is, one DT patch adds `cooling-maps` from the three clusters' cpufreq to `passive` trips on `cpu*` and `cpuss*` zones and lowers the criticals; (3) verify with a stress run (`test-plan.md` section 3) that the passive trip engages below 104 C and that nothing exceeds the sampler's 85 C abort ceiling. Nothing is ever raised; any raise is refused by S6.

### 5.4 Fan

Verified: Windows ACPI has no fan control methods; the fan is managed inside the EC. Linux exposes only the RPM read (patch ec-sam 0003, no write). Hypothesis: the EC regulates the fan autonomously from its own sensors, with the Windows thermal policy (TPOL/SMF) as a performance-profile client. Unknown: whether the EC needs host-supplied temperatures (some ECs fall back to a safe high-fan default without them, which would be audible, not dangerous). No platform-profile client is added (ec-sam gap, S6).

## 6. Battery and charging policy (D23)

### Verified

| # | Fact | Source |
|:--|:--|:--|
| B1 | M13 shows exactly one battery, `BAT1` (SAM, `surface_battery`), `ADP1` (`surface_charger`, online 1), and two `ucsi-source-psy-*` supplies. No `qcom-battmgr-*` supply; `qcom_battmgr` is not loaded; the command line carries the blacklist. D23 behaviour confirmed. | M13 `power_supply.txt`, `lsmod.txt`, `cmdline.txt` |
| B2 | `BAT1` exposes read-only status, capacity, `energy_now/full/full_design`, voltage, `power_now`, `cycle_count` (145), manufacturer, model, serial, `capacity_level`. **No `charge_control_*`, no `charge_behaviour`, no `charge_types`, no termination current.** The driver defines none (`drivers/power/supply/surface_battery.c:446-462`). Battery full: 42.2 of 46.53 Wh design (90.7 percent), state `Full` at 100 percent on AC. | M13 `power_supply.txt` |
| B3 | UCSI supplies expose negotiated current (`current_now` 2250000 uA on the charging port) and role; nothing writable. | M13 `power_supply.txt` |
| B4 | Windows FGBCL (battery current limiting) live values: `BCLCapability 7` (vph_pwr, fg vbatt and fg ibatt monitoring on), `OCPCurrent 17000` mA, `IBATTHi 85` and `IBATTTooHi 88` percent (level 1 at 14.45 A, level 2 at 14.96 A), `PollTimer 600` s, battery percent notification on, low 10, normal 12, faster timer below 20 percent. The INF defaults differ (capability 0, percent notification 0), so the live ACPI-supplied values are the ones in force. These are protection thresholds, not a charge-percentage limit. | `thermal-query.txt` (registry `QCOM0C77` section; SHA-256 `d088dce5...adfa`), `DriverStore/qcfgbcl8380.inf_arm64_84dabc650ac1bff8/qcfgbcl8380.inf` |
| B5 | Linux has no BCL handler and no instantiated LMh (5.1). | source, M13 |

### Inference and Unknown

- Inference: nothing in the image can raise a charging or current limit, so S6 holds by absence of a control. The charge-percentage limit, if any, lives in EC/UEFI.
- Unknown: whether Windows on this unit offers a battery-health option. The Windows registry and INF evidence contains no charge-limit key. Surface UEFI and the Surface app are known on other models to offer a battery limit or smart charging; whether SP11 does is **not established here**. A read-only Windows pass is requested (section 8, Q-W).

## 7. Unknown and REA questions (not asked yet)

| # | Question | Needed for |
|:--|:--|:--|
| Q-R1 | Effective `_PSV/_CRT` after the run-time methods of TZ31-TZ37 and TZ15-TZ24 (the `dyn` zones) and the PEP0 thermal tables: which sensors feed which zone, what each passive trip throttles and to what limit | Thermal mapping; alignment patch |
| Q-R2 | `qcpep8380.sys` / `qcSubsysThermalMgr.sys` / `qcfgbcl8380.sys`: tables and constants behind `QCOM0CF2-0CFC` `LimitsConfig` (AeoB blobs `CCPC`, `OCPC`, `CCDC`, `CGLC`, `CNLC`, ...), CPU parking and DCVS limits, NSP and GPU limits | `npu` and `gpu` limit requests |
| Q-R3 | `SurfaceThermalPolicy.sys` and `SurfaceSmfClient.sys` (+ `Surface.SMF.117.0.*.bin`): thermal modes, what they send to the EC, whether the EC needs host temperatures | Fan and fallback behaviour |
| Q-R4 | Windows battery-health or charge-limit controls (Surface UEFI, SMF charge policy) | Section 6 |
| Q-R5 | Windows system-sleep path: what Windows does to SAM and to the ADSP/CDSP around Modern Standby | SAM D0/DSP alignment |
| Q-D1 | Why `scmi_cpufreq` did not load in M13 | cpufreq, thermal cooling |

## 8. Requests (also in the dossier)

See `README.md` section 8. Per worker, exactly:

- **kernel:** (a) keep the pm-debug options (`CONFIG_PM_DEBUG`, `CONFIG_PM_SLEEP_DEBUG`) and add nothing else for the ladder; (b) when `scmi_cpufreq` is understood (Q-D1), no patch is needed from this dossier yet; (c) later, a DTB variant that re-adds SS3 (inverse of the soc-boot parity deletion) for the controlled SS3 experiment, only after `real-noguard` passes.
- **image:** install the overlay tree as is; add `/etc/sp11-log-collector.d/power-thermal.sh` from `collector/power-thermal.sh`; add a GRUB entry `SP11 debug, suspend ladder 1` with `sp11.suspend_diag=1` plus `mem_sleep_default=s2idle no_console_suspend pm_debug_messages` (and entries for levels 2 and 3 that are marked as risky in the menu text); enable the units in the preset (they test the kernel line); add a collector subcommand `publish-extra` (R-I2); fix or explain `scmi_cpufreq` not loading.
- **soc-boot:** explain the missing cpufreq registration (acceptance item); confirm cpuidle expectations and that the system domain without SS3 is intended; own the later SS3 experiment.
- **ec-sam:** do not combine a `sp11.suspend_diag` boot with a shutdown-mode cycle; consider the `devices` rung as the no-reboot D0-exit/D0-entry experiment; read hwmon `surface_fan`/`surface_temp` values from the new collector.
- **dsp-subsystems:** review the ladder's DSP observations (remoteproc state and wake IRQ counts); decide whether a CDSP-stop arm is acceptable if the ladder shows a CDSP wake or hang.
- **display-lcd:** the ladder records eDP and backlight state around each rung; a dark panel after `devices` or a real rung is your signal; suspend is out of your current scope, this is evidence only.
- **sensors:** if `hexagonrpcd` is packaged, apply the one-line `ConditionFirmware=device-tree-compatible(qcom,x1e80100)` fix to its suspend/resume units.
- **gpu, npu:** thermal limits stay Windows-or-lower; GPU `passive`/`critical` proposals in 5.3 apply when the GPU is enabled.
- **sources:** REA questions Q-R1 to Q-R5 for a later pass.
