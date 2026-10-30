# usb-typec test plan

Every device test reboots the operator's own PC (the test device). All commands below are read-only: no write to sysfs, debugfs, I2C or any firmware path. S3: no retimer or PD firmware access; no `i2cdetect`/`i2cget`/`i2cset`. S6: no write to `charge_control_*` or to any current/voltage/PD file. S5: logs hold serials; they stay out of git.

Failure ids F1-F4 refer to `evidence/2026-10-28-failure-points.md`. Baselines already collected: M5 (`evidence/2026-10-28-m5-device-log.md`) and M8 (`evidence/2026-10-29-m8-superspeed.md`). M8 is port 0 **reversed**, not the port 1 setup of M5. Use section F for the next M9 capture.

## A. What the existing collector already gives (read these first)

`lsusb-tree.txt`, `lsusb.txt`, `devices_deferred.txt`, `regulator_summary.txt`, `gpio.txt`, `pinctrl-pins.txt`, `power_supply.txt`, `remoteproc.txt`, `dmesg.txt`, `lsmod.txt`.

Pass criteria that can already be checked from it:

| Check | Pass |
|:--|:--|
| `devices_deferred.txt` | empty |
| `regulator_summary.txt` | `1-0008-*` and `3-0008-*` consumers listed under `VREG_RTMR0_*` and `VREG_RTMR1_*` |
| `power_supply.txt` | `ucsi-source-psy-pmic_glink.ucsi.01` and `.02` present |
| `dmesg.txt` | no line with `ps883x`, `failed to setup retimer`, `failed to switch mux`, `timeout waiting for altmode`, `UCSI read`, `UCSI write` |

## B. Collector additions (request to `image`; exact commands, all read-only)

Same helpers as `sp11-log-collector` (`snap`, `shsnap`, `attrs`). Output names are suggestions.

```sh
attrs typec.txt        /sys/class/typec/*
attrs usb_role.txt     /sys/class/usb_role/*
shsnap typec-tree.txt  'ls -lR /sys/class/typec 2>&1'
shsnap usb-speed.txt   'for d in /sys/bus/usb/devices/*; do [ -r "$d/speed" ] && echo "$(basename $d) speed=$(cat $d/speed) ver=$(cat $d/version 2>&1) product=$(cat $d/product 2>&1)"; done'
shsnap xhci-ports.txt  'for f in /sys/kernel/debug/usb/xhci/*/ports/port*/portsc; do echo "== $f"; cat "$f" 2>&1; done'
shsnap usb-devices.txt 'cat /sys/kernel/debug/usb/devices 2>&1 | grep -v -i "^S:  SerialNumber"'
shsnap usb-drivers.txt 'ls -l /sys/bus/platform/drivers/dwc3-qcom /sys/bus/auxiliary/devices /sys/bus/auxiliary/drivers /sys/bus/rpmsg/devices /sys/bus/i2c/devices 2>&1'
shsnap usb-dmesg.txt   'dmesg --time-format=iso 2>&1 | grep -i -E "dwc3|xhci|ps883x|ucsi|pmic_glink|pmic-glink|altmode|qmp|eusb2|repeater|typec|pdr|charger_pd|battmgr|usb [0-9]|usb[0-9]|device link|dependency cycle" | grep -v -i serialnumber'
shsnap usb-regs.txt    'grep -E "rtmr|RTMR|l15b|l1i_|l1d_|l1j|l2j|l3j|l2b|l14b|l8b|l2d|l3d" /sys/kernel/debug/regulator/regulator_summary 2>&1; grep -E "gpio(121|123|170|175|176|186|188) " /sys/kernel/debug/gpio 2>&1'
shsnap charge.txt      'upower -d 2>&1 | grep -v -i -E "serial|model|vendor"'
```

Also: in the DP collection (`dp-link.txt`) skip the files `test_active`, `test_data`, `test_type` of each `dp_debug` directory: reading them oopses on a DP controller with nothing attached (`evidence/2026-10-28-m5-device-log.md` O5).

## C. Debug entry (request to `image`): driver debug lines

One extra GRUB entry, `sp11.entry=usbdbg`, same DTB and arguments as `debug`, plus these arguments (they only turn on `dev_dbg`; no hardware effect):

```
pmic_glink_altmode.dyndbg=+p ps883x.dyndbg=+p phy_qcom_qmp_combo.dyndbg=+p ucsi_glink.dyndbg=+p typec_ucsi.dyndbg=+p dwc3.dyndbg=+p dwc3_qcom.dyndbg=+p qcom_battmgr.dyndbg=+p
```

Expected useful lines: `typec_mux_set: switching from qmpphy mode ...` (QMP) and UCSI command traces. **Correction for M9:** successful PAN and PS8830 orientation/configuration handling has no debug messages in the base driver. Patch `0002-usb-typec-log-pmic-glink-and-ps8830-state.patch` supplies those sites; enabling `dyndbg` without that patch cannot reveal them. D23 omits `qcom_battmgr` from the image and from the actual `usbdbg` arguments. If `dyndbg` does not take effect for early modules, record that limitation; do not write to `/sys/kernel/debug/dynamic_debug/control` from the collector.

## D. Physical test matrix (operator)

Each row is one boot of entry `usbdbg` (or `debug` until the entry exists) with the stated hardware. Port 0 is the lower of the two left USB-C ports, port 1 the upper (DT comments; the DT says "Left-side bottom/top"; confirm which is which with the first run: the new `typec` attributes name the port that has a partner, and `usb-speed.txt` names its bus: port 0 = `xhci-hcd.1.auto`, port 1 = `xhci-hcd.2.auto`).

| Id | Setup | Looks at | Pass | Discriminates |
|:--|:--|:--|:--|:--|
| T1 | Enclosure (root device) on port 1, plug **normal** (flip the connector from M5) | `usb-speed.txt`, `lsusb-tree.txt`, `typec.txt` orientation, `xhci-ports.txt` | SuperSpeed (5000M or 10000M) | F1 if SS appears in this orientation but not in M5's reverse one |
| T2 | Enclosure on port 1, plug reversed (M5 repeat) with the debug entry | `usb-dmesg.txt` | The debug lines show the orientation, `mux_ctrl` value and the retimer write | F1 (which step differs), F4 |
| T3 | Enclosure on port 0, normal; then reversed (two boots) | same | SS in at least one orientation | Port 0 versus port 1, F1 |
| T4 | Boot from the enclosure on port 0 or 1; after login plug a USB 3 stick into the **free** port, both orientations, one at a time | `usb-speed.txt` after each plug | Stick enumerates at 5000M | F2 (hot-plug after the ADSP is up) |
| T5 | Same as T4 with a second, different USB-C cable | `usb-speed.txt` | - | F3 |
| T6 | USB-C to DisplayPort or HDMI adapter and an external monitor on the free port after login | `drm-connectors.txt`, `typec.txt`, DP in `usb-dmesg.txt` | A `DP-*` connector `connected`, picture on the monitor, mode listed | DP Alt Mode end to end; pin assignment seen in the debug lines |
| T7 | PD charger on the free port after login (S6: read only) | `charge.txt`, `power_supply.txt`, `typec.txt` | `ucsi-source-psy-*` `online` 1, `ADP1` online, `BAT1` `status` Charging, `usb_type` shows PD | Charging path. Record `current_max`, `voltage_now`; compare with the Windows adapter rating |

Expected data per attribute (`typec.txt`): `data_role` `[host] device` with `host` selected when a device is attached, `power_role` `[source] sink` with `source` for a bus-powered device, `orientation` `normal` or `reverse` (the `gpio121`/`gpio123` pins), `port*-partner` present. `/sys/class/usb_role/` is expected to be empty (no role switch is registered, `evidence/2026-10-28-link-map.md` §4).

## E. Acceptance mapping (from the dossier)

| Acceptance | Test | Today |
|:--|:--|:--|
| 1. USB 3 storage at 5/10 Gbit/s on both ports, both orientations | T1, T3, T4 (4 combinations) | Not met: HS on M5 port 1 reversed and M8 port 0 reversed; normal orientations untested |
| 2. External monitor over DP Alt Mode | T6 | Untested |
| 3. Charging from a USB-C PD charger | T7 | Untested; supplies exist |

## F. M9: one useful trace before another behavior change

Prerequisites for the image/kernel owners: include diagnostic patch `0002`,
ship the rebuilt `ps883x` and `pmic_glink_altmode` modules in the initramfs, and
retain the existing `usbdbg` entry and D23 battery blacklist. The patch changes
logging only. A successful build is not evidence that it fixes SS. The required
Windows runtime comparison remains blocked by R-S1; see the dossier.

For the operator's next scheduled device boot, choose **SP11 debug, USB + DSP
trace** (`sp11.entry=usbdbg`). Keep the boot enclosure/cable/port/orientation
the same as M8 where practical, and record any change in the setup. Never
unplug or reverse the boot medium while it is mounted. A known USB3 storage
device and known USB3 cable (established on Windows, with that cable) on the
free port give a separate comparison; after login insert it normally, collect,
then remove/reinsert it reversed and collect again. These are optional physical
steps for the operator, not automatic collector actions. A later second boot
can exchange boot/free ports and cover the remaining orientation combinations.
USB2-only or unverified cable/device results cannot establish a driver failure.

Keep the existing section B captures, plus `dmesg.txt`, `gpio.txt`,
`regulator_summary.txt`, `devices_deferred.txt` and `/proc/cmdline`. The following
additional hook command is read-only and distinguishes devices present in
sysfs from drivers actually bound (no I2C transfer):

```sh
shsnap usb-typec-bindings.txt 'for d in /sys/bus/i2c/devices/*-0008 /sys/bus/auxiliary/devices/pmic_glink.*; do [ -d "$d" ] || continue; printf "%s driver=" "${d##*/}"; if [ -L "$d/driver" ]; then readlink "$d/driver"; else printf "unbound\n"; fi; done'
```

For an on-device snapshot after each free-port insertion, the operator can run
this exact read-only command block. Its output remains private with the device
logs; output identifiers must be masked before quoting outside `out/`.

```sh
date --iso-8601=seconds
cat /proc/cmdline
lsusb -t
for d in /sys/class/typec/port*; do
    [ -d "$d" ] || continue
    printf '\n%s\n' "${d##*/}"
    for a in orientation data_role power_role usb_capability; do
        [ -r "$d/$a" ] || continue
        printf '%s: ' "$a"
        cat "$d/$a"
    done
done
for d in /sys/bus/usb/devices/*; do
    [ -r "$d/speed" ] || continue
    printf '%s speed=' "${d##*/}"
    cat "$d/speed"
done
sudo dmesg --time-format=iso | grep -i -E 'ps883x|pmic_glink|altmode|typec_mux_set|ucsi|usb [0-9]-' | grep -vi serial
```

Decoder (Verified source constants; expected observations are Inference):

| Trace/result | Interpretation and next step |
|:--|:--|
| `request: cmd=0x10 ... acknowledged` | PAN notification enable request completed; an acknowledgement alone does not show a port event |
| `notify: port=N orientation=0/1 mux=1 svid=0000` | ADSP reports plain USB3, normal/reverse; compare with that port's UCSI orientation and GPIO |
| `apply: ... orientation=1/2 ... switch_ret=0` | Linux normal/reverse orientation callback succeeded; enums differ from raw PAN values |
| `configure: conn_status=21/00/00` or `23/00/00`, followed by corresponding `set: ... in_reset=0 ret=0` | Plain normal/reverse USB3 requested and the driver's existing writes completed; this is not hardware readback or proof of a trained link |
| PAN missing, or mux=0 on the connected port | Investigate PAN enable/replay/notification delivery in Windows and Linux; UCSI partner presence alone does not resolve it |
| PAN/UCSI orientation disagree, or `switch_ret` is negative | Follow orientation source/callback failure before changing DT pins or polarity |
| Retimer I/O/configuration error or still in reset for USB3 | Compare the verified Windows power/reset sequence; no manual I2C, reset or regulator commands |
| USB3 request succeeds but xHCI SS stays RxDetect with known USB3 hardware | Retimer/QMP/link sequencing remains open; compare boot with hotplug and both orientations, then the Windows routine |
| Hotplug works at SS but boot enclosure remains HS | Boot handoff/reset/replay becomes the leading hypothesis; no need to reboot once per free-port orientation |
| `lsusb -t` child at 5000M/10000M on both ports/orientations | USB acceptance item 1; a 10000M **root hub** alone does not satisfy it |

The command block never rebinds a driver, writes sysfs/debugfs, scans I2C,
changes PD/charging policy or reads/writes firmware. Preserve the image's
debugfs allow-list; do not add recursive debugfs capture or DRM test readers.


## G. Next boot (M13): one boot that decides (from the M12 diagnostic, `evidence/2026-10-30-m12-diagnostic.md`)

M12 ran the `debug` entry, so patch `0002` printed nothing. Boot **SP11 debug, USB + DSP trace** (`sp11.entry=usbdbg`) and verify before anything else that the trace is live (read-only):

```sh
cat /proc/cmdline | tr ' ' '\n' | grep -E 'dyndbg|sp11.entry'
grep -E 'ps883x|pmic_glink_altmode|phy_qcom_qmp_combo|dwc3' /sys/kernel/debug/dynamic_debug/control | grep -c '=p'
dmesg | grep -E 'notify: port=|apply: port=|configure: conn_status|set: mode=|request: cmd'
```

The last command must print lines. No lines means the module in the initramfs lacks patch `0002`; stop and report.

Test matrix (the same SS-proven cable and stick for every row; the stick must be proven at 5/10 Gbit/s on Windows with that cable first):

| Row | Boot medium | Port under test | Orientation | Why |
|:--|:--|:--|:--|:--|
| 1 | boot stick in port 0 (as M12), no other device | port 1 | normal, then reversed | Port 1 shows both orientations without touching the boot medium. Insert the proven stick, collect, unplug 5 s, flip, collect |
| 2 | same boot | port 0 | already reverse | Compare the live trace with row 1 reversed |
| 3 | second boot, boot stick in port 1 | port 0 | normal, then reversed | Port 0 normal has never been seen |
| 4 | optional | either | normal with the boot stick's own cable replaced by a known SS cable | Separates cable from orientation |

Per insertion, after about 10 seconds, run (all read-only; output private):

```sh
date --iso-8601=seconds
for p in /sys/class/typec/port?; do echo "== $p"; grep -H . $p/{orientation,data_role,power_role,usb_capability,power_operation_mode} 2>/dev/null; done
lsusb -t
for f in /sys/kernel/debug/usb/xhci/*/ports/port*/portsc /sys/kernel/debug/usb/xhci/*/ports/port*/portli; do echo "$f: $(cat $f)"; done
grep -E 'gpio(121|123|176) ' /sys/kernel/debug/gpio
grep -E 'RTMR' /sys/kernel/debug/regulator/regulator_summary
dmesg --time-format=iso | grep -E 'ps883x|pmic_glink_altmode|usb [0-9]-[0-9]' | grep -vi serial | tail -40
```

Decision table (use the `usbdbg` lines):

| Observation | Meaning |
|:--|:--|
| `notify:` shows mux=0 or no line for the connected port | ADSP path (PAN enable, replay, ack); do not touch the retimer |
| `notify:` orientation 1 but `typec` orientation `normal`, or the reverse, or `apply:` shows the other enum | Orientation source mismatch; candidate for a minimal mapping patch |
| `configure: 23/00/00` (reverse) or `21/00/00` (normal), `set: ... ret=0`, SS still `RxDetect` in **both** orientations with the SS-proven cable | PS8830 or QMP sequencing; next work is reset/delay (U7) and the PHY, with a hotplug versus boot comparison |
| SS works in normal and fails in reverse (or the opposite) | Orientation-specific; compare the tuple bit and QMP lane swap |
| SS works on port 1 hotplug but not the boot-attached port 0 | Boot-handoff or reset/replay ordering |
| `-71` repeats with the SS cable at every insertion | HS signalling, repeater or power issue, separate from retimers |
| `-71` only once at boot with the stick already attached | Host bring-up transient (V8, I3); not a USB-C lane fault |

A 10000M root hub is not SS; only a child of the SS bus at 5000M or 10000M counts.

Collector improvements requested of the image owner (R-I1, read-only): add `portli` to the `xhci-ports.txt` loop, add `grep -E 'ps883x|pmic_glink_altmode|phy_qcom_qmp_combo|dwc3' /sys/kernel/debug/dynamic_debug/control` as `usb-typec-dyndbg.txt` (shows whether patch `0002` is active), copy `/proc/cmdline` into `usb-typec-config.txt`, and add `usb-pd-partner.txt` listing `/sys/class/typec/port*-partner/*` including `number_of_alternate_modes`, `/sys/class/typec/port*-cable` when it exists, and `/sys/class/usb_power_delivery/*` names only. Do not read dwc3 `link_state` or any `test_*` debugfs file.
