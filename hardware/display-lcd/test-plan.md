# Internal LCD acceptance plan (not executed on the device)

Expected timing and wiring values are graded and sourced in
[evidence/2026-10-24-edid.md](evidence/2026-10-24-edid.md) and
[evidence/2026-10-24-windows-backlight.md](evidence/2026-10-24-windows-backlight.md).

Prerequisites: orchestrator review, sources pinning of the upstream DT series,
independent runtime cross-check of patch values, integrated BTF kernel, ISO L0
and L1 checks. Keep an external display and persistent log destination available.
No TCON or other firmware update is part of these tests; suspend remains out
of phase-1 scope. Commands below are for a future authorized device boot only.

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
for connector in /sys/class/drm/card*-eDP-*; do
    cat "$connector/status"
    cat "$connector/modes"
    cat "$connector/edid" > "$display_log/$(basename "$connector").edid"
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
```

The MSM `dp_debug` file reports active bpp, lane count and link clock
(`sources/linux/drivers/gpu/drm/msm/dp/dp_debug.c:65`). Preserve missing-file
errors as well.

Have the image collector copy readable files listed in `edp-debug-files.txt`,
with per-file errors logged. Do not indiscriminately read unrelated debugfs
files: several interfaces have side effects. Record pinctrl and regulator
summaries through the image worker's standard collector as well.

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

Confirm a visible picture survives firmware framebuffer → MSM → GDM. Then
log every available backlight before changing it:

```bash
for backlight in /sys/class/backlight/*; do
    printf '%s\n' "$backlight"
    cat "$backlight/type" "$backlight/brightness" "$backlight/max_brightness" "$backlight/actual_brightness"
done
```

Use GNOME's brightness slider at its lowest selectable level, 25%, 50%, 75%
and maximum, logging sysfs brightness and `/sys/kernel/debug/pwm` after each
step. Expected: monotonic visible response, a nonblack minimum user level,
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
state, and use the desktop for ten minutes. Switch to 60 Hz, verify DRM state,
then return to 120 Hz. Expected: no flicker, corruption, link retraining loop
or loss of brightness control. Repeat a cold boot three times and collect
kernel, connector, PWM and GDM logs on each boot. Do not use suspend as a
substitute for a cold boot.

Failure triage: preserve logs, the selected mode, DPCD, regulator/pin state,
and the last visible brightness. Unverified panel delays remain a specific
possible cause of HPD/first-frame failures. Do not change GPIO numbers,
voltages or timings on the device to experiment.
