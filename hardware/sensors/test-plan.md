# Sensors device test plan

Run on the next private debug ISO after the image owner updates composition to place new seeds in the nested registry directory with target service ownership and mode 0640. Do not change ownership or contents of already-persisted registry files. These checks are read-only. Do not clear or edit `/var/lib/hexagonrpcd/registry`, stop or restart the daemon, or reset the ADSP; the existing evidence reports that resetting the ADSP can crash the SoC.

## Startup and registry layout

1. Let the system complete a normal boot and keep it running for at least two minutes. Preserve the existing registry contents.
2. Confirm `/dev/fastrpc-adsp` exists, ADSP is `running`, QRTR lists the sensor-core service, and `hexagonrpcd-sensors.service` has settled. Record `systemctl show -p NRestarts hexagonrpcd-sensors.service`.
3. Read the staged path without changing it:

   ```sh
   root=/usr/share/qcom/x1e80100/Microsoft/Surface-Pro-11
   ls -ld "$root/sensors/registry" /var/lib/hexagonrpcd/registry/registry
   find /var/lib/hexagonrpcd/registry/registry -maxdepth 1 -type f | wc -l
   find /var/lib/hexagonrpcd/registry/registry -maxdepth 1 -type f -printf '%u:%g %m\n' | sort | uniq -c
   journalctl -b -u hexagonrpcd-sensors.service --no-pager
   ```

   The existing installer places seeds in the parent directory. The next ISO needs the proposed composition update to put newly staged files in the configured nested directory. Do not treat the 293 `sscregistrygen` files as accepted registry content: their names differ from the paths requested in the M15.1 journal. Check whether the ADSP creates or accepts the names it requests, without clearing existing state. Distinguish expected initial reads of absent ADSP state from failures to create/write: the current daemon diagnostic omits the requested open mode, so any `fstempfile` ENOENT needs more specific instrumentation before concluding that creation failed.
4. Run `/usr/libexec/sp11/sp11-sensors-test 30` in a logged-in user session. It masks sensor numbers and performs no service, registry, or remoteproc action. Record whether the proxy reports accelerometer, orientation and ambient light.

## Ambient light and brightness

1. With the display awake and automatic brightness enabled, observe the screen while covering and uncovering the ambient-light sensor. Allow up to 30 seconds per transition.
2. In another terminal, run `monitor-sensor` and record event names and timestamps, keeping raw illuminance values local. Repeat the cover/uncover cycle at least twice.
3. Record whether the backlight changes, the approximate response delay, and whether the direction is consistent. Coordinate with the display-lcd owner if the proxy reports light but the backlight does not respond.

## Acceptance

- Registry files are available under the `registry/` child named by `sns_reg.conf`, with existing parent state files preserved.
- `sp11-sensors-test` reports accelerometer and ambient light from iio-sensor-proxy; orientation is also observed if supported by the current session.
- Cover/uncover causes a repeatable ambient-light event and automatic-brightness response. No response or a slow response remains a measured gap, not a pass.
- No ADSP reset, daemon restart, registry cleanup, or manual registry write is part of this test.
