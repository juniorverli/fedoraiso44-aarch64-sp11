# power-thermal device test plan

Every boot replaces the operator's Windows session, so batch these captures. Nothing here writes a firmware, thermal or charging setting (S3, S6). Evidence design: [2026-10-31-suspend-thermal.md](evidence/2026-10-31-suspend-thermal.md).

## 0. Every boot (no risk)

Install `collector/power-thermal.sh` as `/etc/sp11-log-collector.d/power-thermal.sh`. Read `extra-power-thermal.txt` in the log set: suspend capability and `mem_sleep`, wake sources, per-CPU cpuidle states (names, `disable`, usage, s2idle counters), genpd domain residency, cpufreq (or the explicit "no cpufreq driver" line), thermal zones with trips and cooling bindings, hwmon (SAM fan and temperatures), power_supply (charge-control attributes flagged by file mode), backlight and eDP, remoteproc state and wake IRQ counts. Add `sp11.thermal_log=sam` to a test entry for the CSV sampler (`/run/sp11-thermal/thermal.csv`, tail in the collector).

## 1. Suspend ladder (opt-in, may hang or reset the device)

**Hard reset path:** hold the power button until the device is off (about 20 s on Surface; if it stays dead hold Volume Up and Power 15 s, release, wait 10 s). The boot stick survives. Keep the unit above 30 percent battery and on a table; do not run it with the Type Cover shutdown-mode experiments of ec-sam in the same boot.

Pick one GRUB entry whose kernel line adds `mem_sleep_default=s2idle no_console_suspend pm_debug_messages sp11.suspend_diag=N`:

1. **N=1** first. The service waits 150 s, then runs `freezer`, `devices`, `platform` (each resumes in 5 s). Expected: three `END ... rc=0`, `suspend_stats` fail count 0, keyboard and touchpad still listed, eDP `enabled`, backlight unchanged. Then reboot to read `extra-power-thermal.txt`.
2. **N=2** only if step 1 is clean. After a 20 s warning the device enters s2idle with `cpu-sleep-0` disabled. Wake with the power button or open the lid (a timed wake does not exist: the RTC alarm belongs to the ADSP). Expected: `END real-guard rc=0`, `wake_irq` set, panel back, cover input back.
3. **N=3** only if step 2 is clean. Same with the guard off. A reset here means our parity DT still needs the guard.
4. After a hang or reset: boot again with the same entry plus `sp11.suspend_diag_skip=<last BEGIN rung>`; the last durable `BEGIN` line in `extra-power-thermal.txt` without an `END` names it.
5. N=4 only if `/sys/power/mem_sleep` lists `deep` (not expected).

Normal use after a pass: `sp11.suspend_lid` (lid close suspends), `sp11.wakeup_policy` (power button and lid only), `sp11.suspend_cpuidle_guard=0` (guard off).

## 2. Wake sources

After N=2 passes: wake once by power button, once by lid open, once (with `sp11.wakeup_policy=cover`) by a Type Cover key. Record `wake_irq` and `/sys/class/wakeup` counters. Expected: power button and lid work; the cover wake is an experiment.

## 3. Thermal (read-only logging plus a lower abort ceiling)

`sp11.thermal_log=sam`. Install `stress-ng` (Fedora package). Run `stress-ng --cpu 10 --timeout 300s`, then `--cpu 10 --cpu-method matrixprod --timeout 600s` on AC and on battery. The sampler stops stress processes at 85 C (below every shipped trip). Record: max zone, cpufreq frequencies (when registered), fan RPM, `PassiveLimit`-equivalent behaviour. Expected: no zone near `hot` 90 C; fan RPM rises; with the cpufreq cooling patch later, the passive trip engages below 104 C. Windows comparison values: section 5.2 of the evidence.

## 4. Battery

With a charger on each port: `power_supply` listing shows `BAT1`, `ADP1`, one `ucsi-source-psy-*` online, no `charge_control_*`, no `qcom-battmgr-*`. UPower shows one battery. Nothing is written.
