# Type Cover dead after reboot (M10 report, 2026-10-30)

Report: after a reboot the Type Cover keyboard looks frozen until detached and re-attached. No serials or addresses are copied here. "M10" is boot `f7939948` (kernel sp11.7), "M8" is boot `4b6f080c` (kernel sp11.5), both under `out/device-logs/`. Not used: REA.

## 1. What the logs show

| Fact | Grade | Source |
|:--|:--|:--|
| M8 enumerates SAM firmware 27.201.139, keyboard 09AE, mouse/touchpad 09AF, update HID 09D4, KIP tablet switch | Verified | M8 `dmesg.txt.gz`, `libinput-device-names.txt.gz` |
| M10 enumerates the same set at the same relative time (+2.2 s SAM version, +2.5 s keyboard) | Verified | M10 `dmesg.txt.gz`, `libinput-device-names.txt.gz` |
| M10 has no SAM, serdev, `surface_hid`, `-71` or timeout line. Its only `-110` lines are GLINK (dsp-subsystems) and ath12k | Verified | M10 `dmesg.txt.gz` filtered for ssam/surface/serial1/ttyHS0 |
| The only `-71` in M8 is `usb 1-1`, a USB device, not SAM | Verified | M8 `dmesg.txt.gz` |
| Both captures are cycle 2 of a single boot id and the live system keeps no journal across boots. Whether M10 followed a Linux reboot, a Windows boot or a cold start is not recorded | Verified (absence) | `STATUS`, `SEQ` |
| The kernel never logged a failure on the boot where the operator saw a dead keyboard, or that boot was not captured | Inference | the two rows above |
| Enumeration succeeds (descriptor read works) yet input may not arrive. Event enable or EC state after a reboot is not observable in these logs | Unknown | no input-event or event-enable capture exists |

## 2. Linux 7.3 code paths (Verified, `sources/linux` at v7.3)

- Transport shutdown: `ssam_serial_hub_shutdown()` (`drivers/platform/surface/aggregator/core.c:383`) calls `ssam_notifier_disable_registered()`, display-off and D0-exit and ignores errors; the source comment says it is not established that this is useful. It runs from `serdev_drv_shutdown()` (`drivers/tty/serdev/core.c:418`). Clients (hub, `surface_hid`) are not removed and not suspended on reboot.
- Probe (`core.c:637` onward) sends D0-entry and display-on after reading the firmware version, so a prior D0-exit is undone on the next boot.
- Hibernation poweroff comment (`core.c:557`): after the EC disables events at poweroff, keyboard, touchpad and AC events stay gone unless the driver restores them. Shutdown disables registered notifiers the same way but nothing restores them; on a fresh boot the notifier refcount starts at zero, so registration should re-enable them.
- `surface_hid` is suspended only through PM callbacks (`surface_hid_core.c:239-279`), never on `.shutdown`.
- `ssam_serial_hub_remove()` (`core.c:776`) removes clients first (HID unregisters its notifier, event disable per event), then display-off and D0-exit, then controller shutdown. This is the more orderly path.

## 3. Reference project (`out/ref/linux-sp11`, `out/ref/archiso-aarch64-sp11`)

Verified: the only SAM-related commits are registry ones (remove sensors node, KIP tablet mode, performance profile and fan). No serdev, shutdown or `surface_hid` change, and no image unit or hook that handles SAM. The reference does not mitigate this problem.

## 4. Conclusion

- Unknown: the root cause. No evidence of the dead state exists in the captures.
- Hypothesis H1: the EC keeps a stale session after the Linux shutdown path (events disabled, D0-exit) and the next boot's enable requests are ignored or de-duplicated. A silent failure fits: enumeration works, input does not.
- Hypothesis H2: the cover itself needs a power cycle after a warm reset, independent of the SAM driver. Distinguish by the next-boot tests in section 6.
- No kernel patch is proposed: with no logged error, any change in `core.c` would be a guess against a shared upstream driver. Patch 0005 is reserved if section 6 shows event enable errors or a missing D0-entry reply.

## 5. Image-level mitigation (Requests for image owner, untested)

Run the orderly `remove()` path before shutdown by unbinding the serdev device, and offer an opt-in rebind at boot to test H1 at the next boot.

`/usr/lib/systemd/system/sp11-ssam-shutdown.service`

```ini
[Unit]
Description=SP11 clean SAM shutdown (unbind surface_serial_hub)
DefaultDependencies=no
After=sp11-log-collector.service
Before=shutdown.target umount.target final.target
Conflicts=shutdown.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/true
ExecStop=/usr/libexec/sp11/ec-sam/ssam-unbind.sh
TimeoutStopSec=10

[Install]
WantedBy=sysinit.target
```

`/usr/libexec/sp11/ec-sam/ssam-unbind.sh` (mode 0755)

```bash
#!/bin/sh
# Unbind the SAM serdev driver; ssam_serial_hub_remove() removes clients, then D0-exit.
drv=/sys/bus/serial/drivers/surface_serial_hub
[ -d "$drv" ] || exit 0
for d in "$drv"/serial*; do
    [ -e "$d" ] && echo "${d##*/}" > "$drv/unbind"
done
exit 0
```

`/usr/lib/systemd/system/sp11-ssam-rebind.service` (opt-in test, enabled only for a GRUB entry with `sp11.ssam_rebind`)

```ini
[Unit]
Description=SP11 SAM rebind test
ConditionKernelCommandLine=sp11.ssam_rebind
After=multi-user.target systemd-udev-settle.service

[Service]
Type=oneshot
ExecStart=/usr/libexec/sp11/ec-sam/ssam-rebind.sh

[Install]
WantedBy=multi-user.target
```

`ssam-rebind.sh`: unbind as above, `sleep 2`, then `echo serial1-0 > /sys/bus/serial/drivers/surface_serial_hub/bind` (use the name read from `/sys/bus/serial/devices/`).

## 6. Next-boot test and collector

`hardware/ec-sam/collector/ec-sam.sh` is a read-only drop-in for `/etc/sp11-log-collector.d/ec-sam.sh`: SAM dmesg lines, driver binding, Surface input nodes, runtime PM and interrupt counts, boot markers. It reads no events.

Operator sequence, one reboot each, reporting for each whether the keyboard works without re-attaching:

1. Reboot from the ISO into the same ISO, no mitigation (reproduces; collector captures the state).
2. Same with `sp11-ssam-shutdown.service` enabled (tests H1).
3. Same with `sp11.ssam_rebind` (tests whether a reload revives a dead cover without re-attach).
4. Cold start vs Windows then ISO, to learn whether the failure needs a prior Linux session.

If 1 fails and 3 revives it, the EC state is recoverable in software; if neither 2 nor 3 helps, H2 (cover power) holds and the next step is a cover power-cycle request through SAM or a firmware limitation to document.
