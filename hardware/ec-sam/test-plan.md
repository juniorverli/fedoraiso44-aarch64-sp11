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

## 7. Rev24: controlled reboot and posture comparisons

The prioritized rev25 procedure in §8 supersedes the order of tests here.
This refines §6; debug's unobserved reset is not the control. Use the same
safe GPU-off kernel/image configuration, cover in laptop position, charger,
USB topology, desktop session and ordinary reboot method throughout. Record
physical keyboard identity and independent keyboard/touchpad behavior. Disable
SAM rotor changes through explicit boot arguments and read back the outgoing
parameter immediately before reboot. Label each boot with boot ID, predecessor
ID, entry, kernel and DT hashes, cmdline, actual loaded modules, runtime SAM
mode, and observed outcome. Preserve the outgoing record before reboot and
associate it with the successor. If reboot completion, predecessor identity,
shutdown policy, or variable isolation cannot be established, mark the pair
inconclusive. Record any independently persisted late shutdown evidence;
live kmsg and pstore may miss the callback. Do not induce a crash.

Use a known, repeatable setup boot and fixed posture for each arm; alternate
and repeat arms rather than interpreting a single success. Stabilize and
capture the predecessor, then reboot once to the specified successor. For the
first and third comparisons, choose an identical KIP/default predecessor
(including DT, kernel, args, connections and reset method) for each arm;
the *successor* variable changes. For the second, predecessors have identical
KIP kernel/DT and connections and differ only in their explicit outgoing SAM
argument; both reboot to the same KIP/default successor. A setup boot that
itself has uncontrolled history is a limitation: repeat with matched prior
history, document it, and do not assert isolation if it affects the result.

| Pair | Arm A | Arm B | What the comparison can test |
|:--|:--|:--|:--|
| Posture | KIP/default predecessor → KIP/default successor | Same predecessor → POS/default successor (held 0002 only) | Whether switch client choice changes successor posture and input behavior. Verify loaded build; POS also changes SSAM notifier/query, so an outcome alone does not prove compositor filtering. |
| SAM policy | KIP/default predecessor → KIP/default successor | KIP/silent predecessor → same KIP/default successor | Effect of the outgoing policy bundle on the next boot. Default sends event-disable, display-off and D0-exit; silent skips all three in the handler. This cannot isolate an individual operation or prove EC persistence. |
| USB-C | KIP/default predecessor → original safe orientation DT successor | Same predecessor → otherwise identical safe DT with the two orientation-switch properties removed | Effect of the orientation properties on USB retry and cover behavior separately. Confirm byte-level DT diff and identical arguments, kernel and loaded modules. |

The kernel/image request for the POS and policy entries is
`patches/rev24-pos-test-request.md`. The existing §6 observations remain
applicable. In every successor collect before any detach, with no key payloads:

1. Capture SSAM and HID ancestry/bindings, switch driver's sysfs `state`, its
   input-device identity and actual `SW_TABLET_MODE` bit using an image-owner
   reviewed, read-only `EVIOCGSW` capability/state probe. Also collect POS
   source list and posture with §2's existing read-only helper if already
   available; distinguish unsupported/error from an inactive state. KIP and
   POS states come from different clients and must be labeled. Capture USB tree,
   errors and runtime mode as in §6.
2. Ask the operator to press one harmless, non-secret key over a short interval
   while an image-owner reviewed count-only probe reads **only the identified
   cover evdev node**, saving the number of key press events and device ancestry,
   never key codes or raw reports. Separately record whether the same key
   appears in a blank desktop field and whether touchpad works. If the probe
   is unavailable or loses events, mark input-layer distinction unknown.
3. Record the switch state in physical laptop posture before any other
   intervention. If incorrect, compare it with the POS query and actual input
   switch bit; repeat after a deliberate fold/return only after the initial
   outcome is preserved. Any disappearance, changed state or recovery following
   reattachment can involve both posture and cover reinitialization. Do not
   unbind/rebind, use clean mode, change firmware, or issue state-setting EC
   commands.

**Readout:** Reproducible KIP wrong-tablet plus cover key counts with failed
desktop typing, followed in matched POS successors by correct laptop bit and
working typing, supports posture filtering; verify the desktop input mapping
and repeat. A correct switch bit with zero cover key counts points below the
desktop, but cannot by itself separate HID transport, event delivery, cover
or SAM state. A repeatable policy effect with identical successor supports an
outgoing-shutdown association, not a named EC command or physical reset domain.
An orientation-only effect with repeatable matched history supports an indirect
interaction; storage `-71` improving alone says nothing about cover recovery.
Multiple variables can coexist. A missing POS probe, unsupported source,
unstable boot, reset, event loss or unverified history is inconclusive; no
negative result proves all other hypotheses false. Suspend/resume remains a
separately scheduled test and is not inferred from this reboot experiment.

## 8. Rev25: safe keyboard and outgoing SAM policy

**Purpose:** first determine whether the *physical Type Cover* fails after an
ordinary safe-to-safe reboot; then compare the existing `default` and `silent`
outgoing SAM modes as one variable. Final34 captured no keyboard outcome and
its safe rotor/readback said `clean`, not `silent`. No new kernel, DT, image or
EC request is required for this first comparison. Do not select `clean`, use
`sp11.ssam_shutdown`/`sp11.ssam_rebind`, unbind drivers, change firmware, or
write EC state. Keep the current USB-C orientation switches and DP recovery
path unchanged; the Ugreen `-71` concerns storage. Stop at an unexpected reset
and preserve the logs; do not treat the debug reset as a keyboard result.

### Setup and boot sequence

Use one recorded ISO/kernel and its **same safe GPU-off entry and DT** for all
boots, normal laptop posture, the same charger, USB topology, session and
reboot method. Do not run camera or extra stress workloads. If another input is
needed to edit GRUB or run commands when the cover is frozen, have a touchscreen
or the same external keyboard connected throughout all arms; distinguish its
input from the `09AE` cover. Record the physical cover and each boot ID; retain
the ISO hash, kernel release, DT selection, cmdline and private logs. Recheck
input before detaching anything.

At GRUB, edit the safe entry's `linux` line for **that boot only**, appending
exactly one of the existing parameters below. Boot with the key shown by GRUB.
An explicit parameter makes the shipped rotor leave the choice alone; confirm
the runtime value anyway. Do not save a permanent GRUB change.

```text
surface_aggregator.shutdown_mode=default
surface_aggregator.shutdown_mode=silent
```

Perform these arms, recording the immediate predecessor and its mode every
time. The setup boot of each arm must itself use the same safe entry, `default`
and the same physical conditions. All arrows are ordinary reboots; the
successor is always booted with `default`.

| Arm | Known setup boot | Predecessor, before reboot | Successor to observe |
|:--|:--|:--|:--|
| A | safe / `default` | safe / `default` | safe / `default` |
| B | safe / `default` | safe / `silent` | safe / `default` |

Observe the cover, touchpad and KIP state on each predecessor and successor as
below, especially immediately after each successor starts. Immediately before
reboot, record the predecessor boot ID and actual module parameter on private
storage; after reboot, record the successor boot ID and actual parameter. The
predecessor's choice is the test variable: `default` attempts event-disable,
display-off and D0-exit in the SAM handler; `silent` skips those three there.
The argument has no claimed effect on the next boot's initial policy. Other
shutdown and firmware operations still occur, and actual callback execution is
unknown without independently persisted late-shutdown evidence.

Alternate and repeat A/B if a difference appears. A matched immediate setup is
not proof that all longer-lived EC or firmware history was reset; record longer
history and any deviations. An unexpected reset, unknown predecessor, mode
mismatch, changed connections/entry, missing observation or incomplete reboot
makes that pair inconclusive. If neither successor reproduces the failure,
report both observations and stop: they do not prove the issue is fixed.

### Observations on each boot

Run these in a terminal using the touchscreen or a consistent external input
if necessary. Save only the printed summaries in private logs; never save
typed text, key codes, raw evdev reports or SSAM payloads. Record a separate
operator yes/no/unknown for whether the Type Cover can type in a blank desktop
field and whether its touchpad moves the pointer. A registered device or an
active desktop alone is not a pass. The input probes below are read-only and
use Fedora's `evtest` and Python, both present in final34's package inventory.

```bash
printf 'boot_id='; cat /proc/sys/kernel/random/boot_id
printf 'kernel='; uname -r
printf 'cmdline='; cat /proc/cmdline
printf 'runtime_shutdown_mode='; cat /sys/module/surface_aggregator/parameters/shutdown_mode
cat /run/sp11/sam-mode 2>/dev/null || true
printf 'KIP_state='; cat /sys/bus/surface_aggregator/devices/01:0e:01:00:01/state 2>/dev/null || echo unknown

for e in /sys/class/input/event*; do
    [ -r "$e/device/name" ] || continue
    name=$(cat "$e/device/name")
    case "$name" in
        'Microsoft Surface 045E:09AE Keyboard'|'Microsoft Surface KIP Tablet Mode Switch')
            printf '/dev/input/%s  %s  %s\n' "${e##*/}" "$name" "$(readlink -f "$e/device")" ;;
    esac
done
```

Pick the *current boot's* keyboard node only if its ancestry includes
`surface_aggregator_platform_hub` and `01:15:02:01:00`; pick the KIP node by
its exact switch name. Event numbers can change at every boot. Replace `N` and
`M` below with those numbers; if either node is absent or ambiguous, report it
as unknown and do not guess. Check the KIP bit with `evtest --query`, which
returns 0 for off, 10 for on and another status for error:

```bash
cover=/dev/input/eventN
kip=/dev/input/eventM
sudo evtest --query "$kip" EV_SW SW_TABLET_MODE
rc=$?
case "$rc" in
    0)  echo 'SW_TABLET_MODE=0 (not tablet)' ;;
    10) echo 'SW_TABLET_MODE=1 (tablet)' ;;
    *)  printf 'SW_TABLET_MODE=unknown (evtest exit %s)\n' "$rc" ;;
esac
```

In physical laptop posture, `KIP_state=laptop` and switch bit 0 are expected
from the driver's mapping. An absent or failed query is unknown, not bit 0.
Capture these initial values before deliberately folding or reattaching the
cover.

To count input without saving key codes, open a blank desktop field, start the
following read-only probe from a terminal, then after its prompt tap the blank
field and press the same harmless **non-Enter** key on the Type Cover five
times. Record how many characters appeared, without recording the characters.
The probe reads only the selected cover evdev node and prints only a count and
loss status. It never grabs the device or prints or saves raw events.

```bash
sudo python3 - "$cover" <<'PY'
import os
import select
import struct
import sys
import time

event = struct.Struct('@llHHi')  # 64-bit Linux input_event
if event.size != 24:
    sys.exit('unsupported input_event ABI')
try:
    fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NONBLOCK)
except OSError as error:
    sys.exit(f'probe open failed: {error}')

presses = dropped = 0
deadline = time.monotonic() + 25.0
print('Tap the blank field and press the cover key five times now.', flush=True)
try:
    while (remaining := deadline - time.monotonic()) > 0:
        readable, _, _ = select.select([fd], [], [], remaining)
        if not readable:
            continue
        data = os.read(fd, event.size * 64)
        if not data or len(data) % event.size:
            raise RuntimeError('input device closed or incomplete event')
        for _, _, kind, code, value in event.iter_unpack(data):
            if kind == 0 and code == 3:  # EV_SYN / SYN_DROPPED
                dropped = 1
            elif kind == 1 and value == 1:  # EV_KEY / press
                presses += 1
except (OSError, RuntimeError) as error:
    sys.exit(f'probe incomplete: {error}')
finally:
    os.close(fd)
print(f'cover_presses={presses} dropped={dropped}')
PY
printf 'probe_exit=%s\n' "$?"
```

Expected completion is `probe_exit=0` and `dropped=0`. Any other result,
inability to confirm the five physical presses, or an incomplete test is
**inconclusive**. A zero count records that this probe saw no evdev presses;
the probe cannot rule out an exclusive grab by another process, or distinguish
cover, HID or SSAM causes. A positive count with no desktop characters and an
incorrect tablet bit supports investigating posture/compositor filtering; it
is not proof. Repeat outcomes before drawing a causal conclusion.

If A/B shows a repeatable difference, it is an association with the outgoing
policy bundle, not proof of a particular EC command. If keyboard counts and
incorrect KIP posture support a switch hypothesis, ask the kernel/image owners
for the held, matched **opt-in POS** candidate in
`patches/rev24-pos-test-request.md`; the public evidence covers resume, not
this reboot symptom. Do not combine that later comparison with a mode or USB-C
orientation change. USB-C orientation testing and DP recovery are the USB
owner's separate decision.
