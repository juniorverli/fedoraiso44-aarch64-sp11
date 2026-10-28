# usb-typec test plan

Every device test reboots the operator's own PC (the test device). All commands below are read-only: no write to sysfs, debugfs, I2C or any firmware path. S3: no retimer or PD firmware access; no `i2cdetect`/`i2cget`/`i2cset`. S6: no write to `charge_control_*` or to any current/voltage/PD file. S5: logs hold serials; they stay out of git.

Failure ids F1-F4 refer to `evidence/2026-10-28-failure-points.md`. Baseline (M5, already collected): `evidence/2026-10-28-m5-device-log.md`.

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

Expected useful lines: `typec_mux_set: switching from qmpphy mode ...` (QMP), orientation and `mux_ctrl` handling in the altmode worker, UCSI command traces. If `dyndbg` does not take effect for modules loaded from the initramfs, rely on `usb-dmesg.txt` and the `typec` attributes; do not write to `/sys/kernel/debug/dynamic_debug/control` from the collector.

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
| 1. USB 3 storage at 5/10 Gbit/s on both ports, both orientations | T1, T3, T4 (4 combinations) | Not met: HS only on port 1 reversed; the other three untested |
| 2. External monitor over DP Alt Mode | T6 | Untested |
| 3. Charging from a USB-C PD charger | T7 | Untested; supplies exist |
