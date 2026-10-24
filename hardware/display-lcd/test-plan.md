# Internal LCD acceptance plan (not executed on the device)

Expected timing and wiring values are graded and sourced in
[evidence/2026-10-24-edid.md](evidence/2026-10-24-edid.md) and
[evidence/2026-10-24-windows-backlight.md](evidence/2026-10-24-windows-backlight.md).

Prerequisites: orchestrator review, sources pinning of the upstream DT series,
integrated BTF kernel, ISO L0 and L1 checks. Q1/Q2 cross-check reconciliation
is complete; independent EDID timing/depth reproduction remains requested.
Keep an external display and persistent log destination available.
No TCON or other firmware update is part of these tests; suspend remains out
of phase-1 scope. Commands below are for a future authorized device boot only.

## Two boot stages and local validation

**M2 first integration: patches 0001/0002 only.** Collect DPCD and explicit
PMK8550 GPIO5 subtype evidence before adding 0003. This boot does not
establish the proposed PWM backlight; an absent backlight interface or a
dark internal screen is a recorded gap, not permission to try a new mux.
Use the external display and persistent logs to recover the evidence.

**Later backlight boot:** only after the M2 subtype/DPCD review releases 0003,
review channel-0 routing confidence, then run brightness acceptance below.
func3 is accepted only for LV/MV pads; actual GPIO5 subtype, channel routing,
and panel AUX capabilities are unknown offline. The LGD delay profile remains
provisional; the independently recovered Windows 500 ms wait is in power-down
ENTER, not power-up. See [reconciliation](evidence/2026-10-24-crosscheck-reconciliation.md).

Local checks run this session: panel-edp object build and
`make CHECK_DTBS=y qcom/x1p64100-microsoft-denali.dtb` passed for exactly
0001/0002 in Fedora 44 with BTF/BTF_MODULES=y. Checkpatch strict passed with
`--no-signoff` because operator DCO trailers were removed as instructed.
Commands, versions, scope and logs are in
[build validation](evidence/2026-10-24-build-validation.md). No full kernel,
ISO, boot or device acceptance result is claimed by these checks.

## Boot evidence

Use the project's verbose command line, plus `drm.debug=0x100`. The image
worker must supply `CONFIG_DRM_DP_AUX_CHARDEV=y` or `m`, Python 3, Fedora
`libdrm-tests` (modetest) and `v4l-utils` (edid-decode).

Set an already-mounted persistent log directory:

```bash
display_log=/path/to/persistent/logs/display-lcd
mkdir -p "$display_log"
sudo journalctl -b -k --no-pager > "$display_log/kernel.log"
modetest -M msm -c > "$display_log/connectors.txt"
uname -a > "$display_log/uname.txt"
cat /proc/cmdline > "$display_log/cmdline.txt"
for connector in /sys/class/drm/card*-eDP-*; do
    [ -d "$connector" ] || continue
    cat "$connector/status" > "$display_log/$(basename "$connector").status"
    cat "$connector/modes" > "$display_log/$(basename "$connector").modes"
    cat "$connector/edid" > "$display_log/$(basename "$connector").edid"
    edid-decode "$display_log/$(basename "$connector").edid" > "$display_log/$(basename "$connector").decoded.txt" 2>&1
done
```

Expected: internal eDP reports `connected`, native 2880×1920 exists, and
modetest's mode listing has approximately 120.000 and 60.000 Hz. The EDID
timings should have clock 715201 kHz and totals 2980×2000 / 2980×4000.
The sysfs `modes` file alone does not distinguish the two refresh rates.
Link training and the first valid picture must succeed without repeated
HPD timeouts or AUX errors. The active wire depth/rate/lane count must be
recorded, not inferred from a connector's maximum-bpc property.

Copy available connector debug files and PWM state into the same log directory:

```bash
sudo sh -c 'cat /sys/kernel/debug/pwm' > "$display_log/pwm.txt"
sudo sh -c 'cat /sys/kernel/debug/dri/*/state' > "$display_log/drm-state.txt"
sudo find /sys/kernel/debug/dri -type f -name dp_debug -print -exec cat {} \; > "$display_log/dp-link.txt"
sudo find /sys/kernel/debug/dri -path '*eDP*' -type f -print > "$display_log/edp-debug-files.txt"
sudo journalctl -b --no-pager -u gdm > "$display_log/gdm.log"
sudo cat /sys/kernel/debug/regulator/regulator_summary > "$display_log/regulators.txt" 2>&1
sudo sh -c '
for controller in /sys/kernel/debug/pinctrl/*; do
    [ -d "$controller" ] || continue
    for name in pins pinmux-pins pinconf-pins; do
        [ -f "$controller/$name" ] || continue
        printf "%s\n" "$controller/$name"
        cat "$controller/$name"
    done
done' > "$display_log/pinctrl.txt" 2>&1
```

The MSM `dp_debug` file reports active bpp, lane count and link clock
(`sources/linux/drivers/gpu/drm/msm/dp/dp_debug.c:65`). Preserve missing-file
errors as well.

Have the image collector copy readable files listed in `edp-debug-files.txt`,
with per-file errors logged. Do not indiscriminately read unrelated debugfs
files: several interfaces have side effects. Record pinctrl and regulator
summaries through the image worker's standard collector as well.

## M2 GPIO5 subtype gate

The kernel owner must provide an explicit subtype diagnostic from the driver's
existing probe read, or equivalent evidence that identifies the controller,
physical GPIO5 and subtype. Save the full kernel log first, then extract:

```bash
rg -n -i 'pmk8550|gpio5|subtype|func3/func4|pinctrl' "$display_log/kernel.log" > "$display_log/subtype-review.txt"
```

**Verified source values:** `sources/linux/drivers/pinctrl/qcom/pinctrl-spmi-gpio.c:41` defines the accepted LV/MV
subtype family as 0x10–0x15; `:866` reads the pad subtype and `:883`–`:903`
sets `lv_mv_type`. GPIO5's subtype is **TBD** until this log exists. The
driver returns `-EINVAL` for func3 on a non-LV/MV pad (`:323`); its literal
error text is `LV/MV subtype doesn't have func3/func4`, despite the rejecting
condition being non-LV/MV.

Expected gate evidence: an identified GPIO5 subtype in that accepted family,
plus the internal panel's readable DPCD backlight capabilities below, reviewed
before release of 0003. Missing diagnostics, unidentifiable AUX adapters,
or failed reads keep the gate closed. Pinctrl debugfs prints configuration
but no raw subtype (`:658`); absence of the error with 0003 absent proves
nothing. Do not unbind/rebind the PMIC, remux pins, or use register writes
to obtain the diagnostic.

## Q3: DPCD, read only

Ship `hardware/display-lcd/tools/collect-dpcd.py` in the log collector and run:

```bash
sudo python3 /path/to/collect-dpcd.py "$display_log/dpcd"
```

The helper opens AUX devices with `O_RDONLY` and reads exactly 0x000–0x0ff
and 0x700–0x7ff using `pread`. It records short reads and I/O errors, and saves
sysfs ancestry because all MSM adapters can be named `dpu_dp_aux`
(`sources/linux/drivers/gpu/drm/msm/dp/dp_aux.c:708`). Do not guess that aux0
is the internal connector. On an identified adapter the equivalent commands
are:

```bash
sudo dd if=/dev/drm_dp_auxN of="$display_log/dpcd-000.bin" bs=1 skip=0 count=256 status=none
sudo dd if=/dev/drm_dp_auxN of="$display_log/dpcd-700.bin" bs=1 skip=1792 count=256 status=none
```

Replace `N` after identifying the adapter. There are no DPCD writes. Review
revision at 0x000, maximum rate at 0x001, lanes at 0x002, supported-rate table
where applicable, PSR at 0x070, eDP revision at 0x700, backlight capabilities
at 0x701–0x703 and control mode at 0x721. Definitions are in
`sources/linux/include/drm/display/drm_dp.h:1030`. A read failure is evidence
of a failed read, not evidence that the panel lacks the capability.

Expected: valid, nonempty 256-byte dumps for the internal panel. Four HBR3
lanes are needed for uncompressed RGB 10 bpc at either EDID refresh mode;
RGB 8 bpc nominally fits four HBR2 lanes. Actual advertised capabilities and
negotiated settings are still unknown.

## Brightness and handover

For both stages, record whether a visible picture survives firmware
framebuffer → MSM → GDM, including any blackout and recovery. **Only on the
released-0003 boot**, perform the brightness sweep; on M2 capture existing
backlight state without requiring PWM to be present. Define this snapshot
helper in the same shell as `display_log`:

```bash
snapshot_brightness() {
    snapshot_label=$1
    {
        date --iso-8601=seconds
        for backlight in /sys/class/backlight/*; do
            [ -d "$backlight" ] || continue
            printf '%s\n' "$backlight"
            for field in type brightness max_brightness actual_brightness; do
                printf '%s: ' "$field"
                cat "$backlight/$field"
            done
        done
    } > "$display_log/brightness-$snapshot_label.txt" 2>&1
    sudo cat /sys/kernel/debug/pwm > "$display_log/pwm-$snapshot_label.txt" 2>&1
}
snapshot_brightness initial
```

Use GNOME's brightness slider at its lowest selectable level, 25%, 50%, 75%
and maximum, logging sysfs brightness and `/sys/kernel/debug/pwm` after each
step with `snapshot_brightness minimum`, `snapshot_brightness 25`,
`snapshot_brightness 50`, `snapshot_brightness 75` and
`snapshot_brightness maximum`, respectively. Expected: monotonic visible
response, a nonblack minimum user level,
and normal panel content at maximum. The kernel value 0 intentionally turns
the PWM backlight off; it is not an acceptable minimum user level. No verified
Windows minimum-duty calibration exists yet; stop the sweep if the picture
becomes unusable and restore the previous visible slider position.

The patch requests a 5 ms PWM period. The realized period and resolution must
be observed from driver/hardware state; they are not guaranteed to be exactly
the requested value. The CIE brightness curve is generated by `pwm_bl`
(`sources/linux/drivers/video/backlight/pwm_bl.c:182`), not copied from Windows.

## Refresh and stability

Select 120 Hz in GNOME Settings → Displays, confirm the active mode in DRM
state, and use the desktop for ten minutes. Capture state and timestamp
immediately after selecting each mode, and again after the ten-minute period:

```bash
snapshot_mode() {
    mode_label=$1
    date --iso-8601=seconds > "$display_log/mode-$mode_label.time"
    sudo sh -c 'cat /sys/kernel/debug/dri/*/state' > "$display_log/mode-$mode_label.txt" 2>&1
    sudo journalctl -b -k --no-pager > "$display_log/kernel-$mode_label.log"
}
snapshot_mode 120-start
```

After ten minutes at 120 Hz, run `snapshot_mode 120-ten-minutes`; select
60 Hz and run `snapshot_mode 60`, then return to 120 Hz and run
`snapshot_mode 120-return`. Expected: no flicker, corruption, link retraining loop
or loss of brightness control. Repeat a cold boot three times and collect
kernel, connector, PWM and GDM logs on each boot. Do not use suspend as a
substitute for a cold boot.

Failure triage: preserve logs, the selected mode, DPCD, regulator/pin state,
and the last visible brightness. Unverified panel delays remain a specific
possible cause of HPD/first-frame failures. Do not change GPIO numbers,
voltages or timings on the device to experiment.

For each of the three cold boots, use a distinct persistent directory and
record the visible handover result, refresh selection, ten-minute start/end
times and brightness observations alongside these logs. Final component
acceptance requires the later backlight boot's full results; M2 capability
collection alone is not a pass.
