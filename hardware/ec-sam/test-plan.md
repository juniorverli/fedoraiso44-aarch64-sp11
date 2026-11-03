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

## 4. Buttons (volume: patch 0005; power: held 0004)

Volume (patch 0005): run `tools/collect-volume-buttons.sh` as root and follow
its two 10 s phases (press only up, then only down); pass criteria are in
`evidence/2026-10-31-volume-buttons.md`. The script reads only the
volume-keys device.

Power (held 0004):

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

## 6. Rev23: keyboard after safe reboot, debug control and USB parity

Use [rev23 evidence](evidence/2026-11-03-rev23-keyboard-parity.md). Do not
add `sp11.ssam_shutdown` or `sp11.ssam_rebind`: the DT unbind/rebind path is
not a proven cleanup. Fix the outgoing SAM policy in **every** test entry with
`surface_aggregator.shutdown_mode=default`; verify the runtime parameter just
before each reboot. An explicit argument bypasses the rotor. Do not change the
parameter or other EC state by hand. Record boot ID, entry/DTB, exact policy,
physical cover position and model, charger/USB connections, previous boot ID,
previous entry/policy, and whether the keyboard or touchpad works. Keep the
cover attached and in laptop posture; identify the tested physical keyboard.
No camera or other GPU workload is needed for this test.

1. On a safe boot, collect the state below, verify default, type harmless text
   in a blank field and report keyboard and touchpad separately. Reboot normally
   to the **same safe entry**, without detaching or changing USB connections.
   On the successor, repeat captures and physical typing. Do not assume the
   rotor's probe log reflects the policy in effect at reboot.
2. Repeat with the same USB devices and posture, using debug → reboot → debug
   as control. The debug entry has a known unexplained reset near 64 s: collect
   early, stop this arm if it resets, and report it as **inconclusive**, not a
   passing or failing keyboard test. Avoid extra workloads. Capture from the
   current boot before attempting reboot.
3. USB owner supplies a safe GPU-off variant differing only in the two
   orientation-switch properties, with byte-level DT diff and identical boot
   arguments. Compare safe → safe with parity → parity, fixed default SAM
   policy, same physical USB topology and equivalent predecessor conditions.
   Record both `-71` and separately observed cover and external USB keyboard
   behavior. Repeat any apparent effect with the same boot history; no effect
   from a single pair proves absence.
4. If cover input fails, capture **before** trying reattachment. Inspect KIP
   `state` against physical posture; then detach and reattach once and repeat
   captures, noting if keyboard and touchpad recover independently. No runtime
   unbind, EC reset or firmware write. If recovery coincides with a changed
   switch state, that alone does not distinguish posture from EC/cover reset.

For each boot, run the existing read-only component collector and the
capability collector from section 0. Also record these read-only snapshots on
private storage; do not commit raw output (some tools may disclose identities).
The image owner should incorporate them into the early collector so debug has
a chance to capture them before reset. Never record text, keyboard codes or
raw HID/SSAM payloads.

```bash
cat /proc/sys/kernel/random/boot_id /proc/cmdline
cat /sys/module/surface_aggregator/parameters/shutdown_mode
cat /run/sp11/sam-mode 2>/dev/null
for p in /sys/bus/surface_aggregator/devices/*; do
    [ -e "$p" ] || continue
    printf '%s driver=' "${p##*/}"
    readlink "$p/driver" || true
    [ ! -r "$p/state" ] || { printf 'state='; cat "$p/state"; }
done
for p in /sys/class/input/event*; do
    [ -r "$p/device/name" ] || continue
    printf '%s ' "${p##*/}"
    cat "$p/device/name"
    readlink -f "$p/device"
done
for p in /sys/bus/hid/devices/*; do
    [ -e "$p" ] || continue
    printf '%s driver=' "${p##*/}"; readlink "$p/driver" || true
done
libinput list-devices
lsusb -t
lsusb
sudo dmesg | grep -iE 'ssam|surface_|aggregator|surface_hid|serial1|ttyHS0|045e:09|usb .*error|not accepting address'
sudo journalctl -b -k --no-pager | grep -iE 'ssam|surface_|aggregator|surface_hid|serial1|ttyHS0|usb .*error|not accepting address'
```

SSAM notifier enable/disable and errors are represented by available kernel
messages and existing private trace metadata only; a quiet log does not prove
notifications were delivered. Ask the image owner to capture SSAM tracepoint
**metadata/counts** where available without payload bytes or key data, plus
wake IRQ and UART counters at fixed times, and report trace availability and
loss. Do not enable an unreviewed trace class: some tracepoints contain data.
Capture `state` in both laptop and folded positions; an absent sysfs file or a
failed command is unknown, not an inactive switch. Existing `ssam-ro.py`
queries may be used only as read-only requests if the cdev is already available;
no EC state-setting requests. For compositor versus input-layer diagnosis, an
image-owner reviewed count-only evdev probe may count key press events over a
short window after the operator presses one non-secret test key; save only the
count and device ancestry, never event codes or raw reports. Without such a
probe, GNOME typing failure cannot be attributed to either layer.

At each planned reboot, preserve the current boot's runtime SAM mode and boot
ID on the removable log medium before shutdown; record the next boot's ID and
mode separately. Capture live kmsg as long as possible and copy any existing
pstore on the next boot, without forcing a crash; either may stop before the
kernel shutdown callback, and an empty pstore does not prove success. A late
shutdown log or independently persisted marker is needed to establish that
`device_shutdown()` was reached and which operations failed. Do not mount or
write the Windows partition.

Interpretation: USB retry fixed but SSAM count/state and cover failure unchanged
supports separate USB and cover problems. A cover regression with identical
predecessor and SAM mode that reproducibly follows orientation alone supports
an indirect interaction, but needs a mechanism. Kernel key counts present but
GNOME ignores input with a wrong KIP posture supports compositor filtering;
no key counts despite a bound HID shifts investigation to HID/SSAM/cover, not
necessarily shutdown. If both parity variants fail, later compare a single
controlled outgoing SAM policy using the existing diagnostic modes and the
same reset type; do not infer that `silent` excludes other state or reset causes.
