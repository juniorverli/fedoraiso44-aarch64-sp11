# Sensors device test plan

Run during a live logged-in session on the next planned private debug ISO, before shutdown; M16 used an image-owned helper to seed the nested directory. Do not change ownership or contents of already-persisted registry files. These checks are read-only. Do not clear or edit `/var/lib/hexagonrpcd/registry`, stop or restart the daemon, or reset the ADSP; the existing evidence reports that resetting the ADSP can crash the SoC.

## Startup and registry layout

1. Let the system complete a normal boot and keep it running for at least two minutes. Preserve the existing registry contents.
2. Confirm `/dev/fastrpc-adsp` exists, ADSP is `running`, QRTR lists the sensor-core service, and `hexagonrpcd-sensors.service` has settled. Record `systemctl show -p NRestarts hexagonrpcd-sensors.service`.
3. Read the staged path without changing it:

   ```sh
   root=/usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11
   ls -ld "$root/sensors/registry" /var/lib/hexagonrpcd/registry/registry
   find /var/lib/hexagonrpcd/registry/registry -maxdepth 1 -type f | wc -l
   find /var/lib/hexagonrpcd/registry/registry -maxdepth 1 -type f -printf '%u:%g %m\n' | sort | uniq -c
   udevadm info --query=property --name=/dev/fastrpc-adsp | grep -E "^(IIO_SENSOR_PROXY_TYPE|SYSTEMD_WANTS|TAGS)="
   systemctl show hexagonrpcd-sensors.service iio-sensor-proxy.service -p ActiveState -p SubState -p Result -p MainPID -p NRestarts
   journalctl -b -u hexagonrpcd-sensors.service --no-pager
   ```

   M16 reported 293 installed seeds; check actual count, ownership and modes. The corrected standalone installer seeds the child only when absent; the image uses its own helper. Do not treat the 293 `sscregistrygen` files as accepted registry content: their names differ from the paths requested in the M15.1 journal. Check whether the ADSP creates or accepts the names it requests, without clearing existing state. Distinguish expected initial reads of absent ADSP state from failures to create/write: the current daemon diagnostic omits the requested open mode, so any `fstempfile` ENOENT needs more specific instrumentation before concluding that creation failed.
4. Capture the full daemon journal, particularly `Large (>256B)` and restart count. This listener limitation occurred on M16; do not infer that the initial successful exit means it completed its work. Run `/usr/libexec/sp11/sp11-sensors-test 30` in a logged-in user session. It masks sensor numbers and performs no service, registry, or remoteproc action. Record whether the proxy reports accelerometer, orientation and ambient light; also run `monitor-sensor` while rotating through distinct orientations and record transitions. Keep raw values local.

## Ambient light (diagnostics only; automatic brightness removed)

Automatic brightness is disabled by operator decision and locked in the image: `org.gnome.settings-daemon.plugins.power ambient-enabled=false` in `/etc/dconf/db/distro.d/92-sp11-display`, with the key listed in `/etc/dconf/db/distro.d/locks/92-sp11-display` (image commit `2ee4dbf`). Do not enable the key or edit any dconf file during this test.

1. Confirm the setting before observing the screen:

   ```sh
   gsettings get org.gnome.settings-daemon.plugins.power ambient-enabled
   gsettings writable org.gnome.settings-daemon.plugins.power ambient-enabled
   ```

   Expected: `false` and `false` (locked). Any other value is an image or session failure; record it and stop this section.
2. With the display awake, cover the ambient-light sensor completely, hold for 30 seconds, uncover, and hold for another 30 seconds. Repeat the cover/uncover cycle at least twice. If a read-only brightness value is available, record it before each step; never set it.
   Expected: **no brightness change** during or after any transition. The 30-second hold is the observation window; a change after it is still a failure.
3. Optional diagnostics (read-only): run `monitor-sensor` in another terminal and record sensor names, event names and timestamps, keeping raw illuminance values local; `ssccli` light readings are equally acceptable. A light event shows the ALS is readable through SSC. No light event is a registry/daemon gap to report, not evidence that the sensor is missing.
4. A brightness change while covering/uncovering fails the removal assertion and belongs to the image/session owner (locked key not applied, or another backlight writer), not to a sensors retest.

## Acceptance

- Registry files are available under the `registry/` child named by `sns_reg.conf`, with existing parent state files preserved.
- `sp11-sensors-test` reports accelerometer and orientation from iio-sensor-proxy; an ambient-light sensor in the proxy is diagnostic only and is not required for pass (the script's exit status treats it as required, so read its output rather than relying on the exit code).
- `ambient-enabled` reads `false` and is not writable.
- Over a 30-second cover and a 30-second uncover, the backlight does not change. An ambient-light event is diagnostic only; its absence is a registry/driver gap, not a failure of this acceptance, because the sensor's presence is already established from Windows.
- No ADSP reset, daemon restart, registry cleanup, or manual registry write is part of this test.
