# ec-sam device acceptance plan

Use the next image's default GPU-off entry, with speakers disabled (S1).
Every boot replaces the operator's Windows session, so batch these captures
into that boot. No firmware, charge limit, thermal limit or Windows-volume
write is authorized. The commands read hardware state and write only their
capture files under `/run`; the image collector owns exporting them safely.
Never copy raw device logs or identities into git.

The M5 GPU-off boot established enumeration and **unplugged** SAM battery
properties. It did not establish keyboard usability, early input, correct
posture, plugged-in charging or UPower output. Status stays `designed` until
the build/cross-check gates are satisfied; only the orchestrator can set pass.

## 0. Image preparation and one read-only capture

Image owner stages `tools/collect-input-capabilities.sh`, `collect-power.sh`
and `ssam-ro.py` at `/usr/libexec/sp11/ec-sam/`, with Fedora `libinput-utils`,
`evtest` and Python 3. The keyboard chain must already be loaded; this
collector does not load modules or change configuration. If SSAM cdev is
needed, the image owner enables it in advance; it is unnecessary for input
or battery operation.

Run as root:

```bash
capture_dir=/run/sp11-ec-sam
mkdir -p "$capture_dir"
/usr/libexec/sp11/ec-sam/collect-input-capabilities.sh > "$capture_dir/input-capabilities.txt" 2>&1
/usr/libexec/sp11/ec-sam/collect-power.sh > "$capture_dir/power-initial.txt" 2>&1
for dev in /sys/bus/surface_aggregator/devices/*; do
    test -d "$dev" || continue
    printf '%s driver=%s\n' "${dev##*/}" "$(basename "$(readlink "$dev/driver")")"
    cat "$dev/modalias" 2>/dev/null
done > "$capture_dir/ssam-devices.txt"
lsmod | awk 'NR == 1 || /surface|hid|qcom_battmgr|pmic_glink|ucsi/' > "$capture_dir/modules.txt"
if test -r /dev/surface/aggregator; then
    python3 -I /usr/libexec/sp11/ec-sam/ssam-ro.py all > "$capture_dir/ssam-reads.txt" 2>&1
fi
```

Input collection runs `libinput list-devices` and the evtest capability
header for SAM/gpio-keys/pmic input nodes only. evtest has no dedicated
capabilities option: the tool stops header output at `Testing ...` and
terminates the producer within 2 s. It never saves `Event:` lines, grabs a
device or queries key state. No `libinput debug-events`, event capture or
keystroke recording is permitted. Do not type while collecting headers.

Power collection uses an explicit attribute allowlist, and a filtered
UPower snapshot; it reads neither identity/serial fields nor
`charge_control_*` attributes. Capture failures and missing tools are
failures to collect, not evidence that the hardware is absent.

## 1. Type Cover keyboard and touchpad (D22 priority)

| Check | Expected and evidence |
|:--|:--|
| Attached at boot | SSAM TID 2/IIDs 1 and 3 bind `surface_hid`; capability headers identify `045E:09AE` keyboard and `045E:09AF` touchpad/mouse; libinput lists keyboard and touchpad capabilities |
| Probe cleanup with patch 0001 | No `01:15:01:06:00` or `01:15:02:02:00` client in ssam-devices; no descriptor-length failure for these endpoints in the image's private dmesg capture |
| Ordinary use | With all collectors stopped, operator types non-secret text in GNOME and checks pointer motion, tap, physical click and two-finger scroll. Record only a success/failure report, not keys or motion |
| Reattach | Detach/re-attach once, repeat capability capture and ordinary use. KIP child devices disappear/reappear without an oops |
| Fn/media keys | Operator reports GNOME response; speakers remain disabled, including during volume-key tests |
| Initramfs | Image-owned diagnostic entry `rd.break=pre-mount`: attached keyboard can type a harmless shell command such as `echo early-input-ok`. No event recorder. A real LUKS unlock can be tested later, with all collectors stopped and no password capture |

The required early chain is UART/serdev/providers → `surface_aggregator`
→ `surface_aggregator_registry` → **`surface_aggregator_hub`** →
`surface_hid`/`surface_hid_core` → `hid`/`hid_generic`/input, with built-in
parts accepted. HID transport alone cannot instantiate KIP children.

Before device boot, image owner runs this exact read-only inventory on the
extracted next-image initramfs (replace the file path):

```bash
lsinitrd /path/to/next-image-initramfs.img | awk '/surface_aggregator|surface_hid|hid_generic|hid_multitouch|qcom_geni_serial|qcom_battmgr/ { print }'
```

Assert every modular early-keyboard dependency is present and, where
needed, preloaded by dracut. `hid_multitouch` is required early for an
initramfs touchpad; text LUKS/emergency input needs the keyboard chain.
The inspected shipped config builds `HID_GENERIC`, `SERIAL_QCOM_GENI` and
`SERIAL_DEV_BUS` in; do not require nonexistent `.ko` files for those. The
Surface hub/HID transports remain modular. The prior inventory predates M5; do not treat its missing hub as an exact
inventory of M5. Boot timing alone does not prove module contents.

## 2. Tablet mode and lid

Collect capability headers once, then fixed posture snapshots, without
recording input events. For each posture (laptop, folded back, detached),
operator runs:

```bash
python3 -I /usr/libexec/sp11/ec-sam/ssam-ro.py pos-sources
python3 -I /usr/libexec/sp11/ec-sam/ssam-ro.py pos-posture
python3 -I /usr/libexec/sp11/ec-sam/ssam-ro.py kip-cover
```

`pos-posture` defaults to Linux-supported source IDs 0 and 3; if
`pos-sources` reports another source, record it and request driver work.
Do not infer support from an empty/error reply. KIP switch must advertise
`SW_TABLET_MODE`; ordinary keyboard/touchpad behavior must recover when
returning to laptop posture. Fold/detach must not leave GNOME ignoring the
keyboard after reattachment. Lid must advertise `SW_LID` and behave correctly
when the cover is closed/opened (operator report only).

Held 0002 changes the KIP switch to POS. An upstream fix reports KIP stuck
folded after suspend/resume; test resume only when the image owner has
scheduled it with the operator. Compare POS and KIP fixed snapshots before
and after that transition. No event logger is needed to decide the patch.

## 3. SAM battery, UPower and charging (D23 already decided)

**Precondition:** `qcom_battmgr` is blacklisted and excluded from initramfs.
`modules.txt` must not list it; `/sys/class/power_supply/` must contain no
`qcom-battmgr-*`. Keep UCSI power supplies. Do not re-enable the driver if
any check below fails: report a SAM/AC gap for a D23 revisit without writable
charging thresholds.

Capture unplugged first, then plug a suitable charger into USB-C port A,
unplug it, repeat on USB-C port B, then Surface Connect if the operator has
that charger. Label each connector unambiguously in the operator report.
Only one charger input at a time. No automatic charge/discharge workload
and no settings changes are needed.

For each stable state, run the following exact command; change `state` to
`usb-c-a`, `usb-c-b`, `surface-connect`, or `unplugged`:

```bash
state=usb-c-a
capture_dir=/run/sp11-ec-sam
for wait_s in 0 10 50; do
    sleep "$wait_s"
    /usr/libexec/sp11/ec-sam/collect-power.sh
done > "$capture_dir/power-$state.txt" 2>&1
```

Samples are at 0, 10 and 60 seconds. The driver caches battery data for
1 s and schedules a battery refresh 5 s after external-power change;
judge the settled samples, not only the first one. Repeat `unplugged` after
each disconnect to verify the transition back. The collector timestamps
samples; no `upower --monitor-detail` or unfiltered serial-bearing output
is saved.

| Required check | Unplugged | Charger attached, settled |
|:--|:--|:--|
| BAT1 presence/type | Present system Battery | Same BAT1, no duplicate system battery |
| Status and charging state | Discharging during use | Charging below the existing firmware limit when charging is allowed; Full or Not charging at a firmware limit is valid and must be recorded, not overridden |
| Capacity | Present, 0–100%; consistent with energy_now/energy_full to rounding | Still present; sensible trend, not required to change within one minute |
| Energy/rate | energy_now/full/full_design in uWh and power_now in uW | Fields remain readable; energy should trend upward during sustained Charging when charger power exceeds load; do not require an increase at a full/limited pack |
| ADP1 AC state | Mains, online=0 | online=1 for each working charger input; returns to 0 after unplugging |
| UPower BAT1 | native-path identifying BAT1, present, percentage, energy/full/design and energy-rate; state agrees with sysfs | Matching settled status and values (UPower energy Wh = sysfs uWh / 1,000,000); health capacity should track energy_full/energy_full_design, distinct from percentage; time-to-full may need time to stabilize |
| UPower AC/display | ADP1 online=no; on-battery=yes | ADP1 online=yes, on-battery=no; DisplayDevice state/percentage/energy consistent with the one BAT1, no doubled energy |
| UCSI | Capture online values separately | Port supply may identify the active connector; it is not another system battery |

If a firmware limit prevents Charging in every capture, the plugged-in AC
and limited state can pass, but actual Charging remains explicitly untested.
Wait for ordinary discharge during normal use for that check; never change
charge thresholds or thermal limits. Missing UPower fields, stale online
state, duplicates or disagreement after settling are acceptance failures.
M5 did not include these plugged-in or UPower checks.

## 4. Buttons (held 0004)

Do not ship the candidate until its electrical parameters and key orientation
are independently reproduced and cross-checked. On the current image,
collect capabilities for existing gpio-keys lid and pmic_pwrkey only.
After release approval, the same capability-only collector must show
KEY_POWER, KEY_VOLUMEUP and KEY_VOLUMEDOWN; operator reports each button's
GNOME action and whether up/down are swapped. No evtest event recording.

## 5. Fan candidate 0003

Read only, no fan control:

```bash
python3 -I /usr/libexec/sp11/ec-sam/ssam-ro.py fan-rpm
for hwmon in /sys/class/hwmon/hwmon*; do
    test "$(cat "$hwmon/name" 2>/dev/null)" = surface_fan || continue
    cat "$hwmon/fan1_input"
done
```

Expect a valid two-byte RPM reply and a plausible corresponding hwmon value;
zero is valid for a stopped fan. An error is not proof of a stopped fan.
No thermal or performance-profile write is authorized.

## 6. Off-device release gates

See `evidence/2026-10-28-validation.md` for actual command outcomes. Require
`kernel-dev.sh` under its build lock with both BTF options, strict checkpatch
without a sign-off requirement, and DT schema validation where DT changes
are considered. Candidate validation does not authorize held patches or
replace the independent protocol §5.1 cross-check. Run `scripts/index.py
--check`; do not create a commit (D24).
