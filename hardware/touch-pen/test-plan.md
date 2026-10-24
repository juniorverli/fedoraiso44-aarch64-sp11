# Touch and pen test plan

Current status: **designed**. All device steps below are future work for an
orchestrator-approved test image. This session ran only software checks.
Completed: the 11-patch application and BTF link builds, new-file `W=1`,
binding/example validation with YAML lint, and validation of the disabled
board draft against HID, regulator and TLMM schemas. Exact results and hashes
are in [build evidence](evidence/2026-10-24-spi-hid-v6.md#resumed-session-w1-and-dt-validation).
Strict checkpatch, cross-check and the functional gaps remain image gates.

## Software gates before an image

1. Sources owner pins spi-hid v6 and the public HID-over-SPI specification;
   orchestrator obtains an independent other-runtime cross-check of all
   addresses, GPIOs, delays, opcodes, flags and DT translations.
2. Keep patches 0001–0011 unchanged as the upstream baseline. Resolve
   checkpatch findings without inventing author sign-offs. Treat 0012 as
   an unsigned RFC containing disabled nodes, excluded from release integration.
3. Implement and build-test quad reads and writes with single-lane opcodes
   across the transport, controller/GENI personality and board pinctrl.
   Do not try to force single-lane mode by deleting the DT bus-width properties.
4. Resolve reset/power timing, second GpioInt and wake/panel policy; validate
   the final board DT. Determine whether protocol 0 really occurs before
   selecting a firmware-loading fix. Never infer this from the driver alone.
5. Reproduce the compatibility build from the project root:

   ```sh
   bash hardware/touch-pen/build-test.sh > out/build/touch-pen/rebuild.log 2>&1
   ```

   The script takes the shared kernel lock, uses Fedora 44, `-j4`, and checks
   both BTF config symbols and `.BTF` in vmlinux and all three SPI-HID modules.
   It then recompiles the new driver objects with `W=1`, including trace code.
   It builds a small ARM64 test configuration, not Fedora release RPMs.
6. Reproduce the binding and disabled-board checks with Fedora packages:

   ```sh
   flock out/.kernel-build.lock docker run --rm -i \
     --mount "type=bind,src=$(realpath out/linux/touch-pen),dst=/src,readonly" \
     --mount "type=bind,src=$(realpath out/build/touch-pen),dst=/build" \
     --env TP_CHECK_UID="$(id -u)" --env TP_CHECK_GID="$(id -g)" \
     --workdir /src sp11-kernel-fc44:latest bash -s <<'CHECK'
   set -euo pipefail
   dnf -y install dt-schema which yamllint
   setpriv --reuid="$TP_CHECK_UID" --regid="$TP_CHECK_GID" --clear-groups \
     env KBUILD_BUILD_USER=touch-pen bash -s <<'DT'
   set -euo pipefail
   schema=Documentation/devicetree/bindings/input/hid-over-spi.yaml
   dt-doc-validate "$schema"
   yamllint -f parsable -c Documentation/devicetree/bindings/.yamllint "$schema"
   make O=/build/kbuild ARCH=arm64 -j4 dt_binding_check \
     DT_SCHEMA_FILES=input/hid-over-spi.yaml
   make O=/build/kbuild ARCH=arm64 -j4 CHECK_DTBS=y \
     DT_SCHEMA_FILES='input/hid-over-spi.yaml:regulator/fixed-regulator.yaml:pinctrl/qcom,x1e80100-tlmm.yaml' \
     qcom/x1p64100-microsoft-denali.dtb
   DT
   CHECK
   ```

   Packages are installed only inside the disposable container; the kernel
   source mount is read-only and generation runs as the host user. Inspect
   validation diagnostics as well as exit codes: Kbuild can print schema or
   lint failures without failing `make`. The current disabled draft is clean;
   repeat these checks on the final enabled design and any controller binding.
7. Kernel owner merges the config requirements and runs the full Fedora
   aarch64 config/RPM build. Image owner passes L0/L1 before any device boot.

## Initial device evidence (future; read-only diagnostics)

After the transport/controller gaps are fixed and the final image is approved:

```sh
uname -r
test -s /sys/kernel/btf/vmlinux
journalctl -k -b | rg -i 'geni|spi|hid|touch|digitizer|firmware|invalid proto'
ls /sys/bus/spi/devices
libinput list-devices
```

Expected: the engine initializes, HID enumerates, and input devices appear;
no `Invalid proto 0`, unsupported mode-bit warnings, descriptor timeout loops,
or repeated unsolicited resets. Runtime SPI bus numbers are dynamic: identify
the device using its OF path/MMIO address rather than assuming `spi10.0`.
If protocol 0 occurs, preserve the complete surrounding resource/clock/probe
messages. Do not use devmem or load arbitrary firmware as a diagnostic shortcut.
For the identified SPI device, capture its `bus_error_count`,
`regulator_error_count` and `device_initiated_reset_count` sysfs attributes
before input testing and after each power-transition group. Record startup
resets separately; normal use must not produce growing errors or reset storms.

## Touch

Use `evtest` interactively to select the touch event node:

```sh
sudo evtest
```

Expected: multitouch slot/tracking events, accurate coordinates at all four
corners, and ten simultaneous contacts with stable tracking. Test GNOME taps,
drags, scrolling and orientation. Log the observed maximum contact count and
axis ranges; no range is assumed from the ACPI tables. Check that lifting all
fingers clears all contacts and that palm rejection while using the pen is usable.

## Pen

Select the pen event node in `evtest`, then test in a drawing application.
Expected: position and hover, smooth `ABS_PRESSURE` from light to firm normal
writing force, `ABS_TILT_X/Y` where advertised, pen tip/contact, barrel button,
eraser/tool changes. Record the capabilities actually advertised by the report
descriptor; do not assume a pressure maximum or pen feature from the package name.
Record an absent feature required by the dossier's acceptance criteria as an
unmet criterion. Touch and pen working in `evtest` alone does not establish
GNOME orientation, palm rejection or application pressure behavior.
No firmware-update feature reports, CFU tools, or pen/touch flashing are part
of these tests (S3).

## Power and regression

Once normal input works, repeat display blank/unblank and system suspend/resume
under the agreed panel/wake policy. Expected: input recovers without a reset
storm, spurious touches, lost pen, or wake-loop; no power-reference imbalance.
Run at least ten display blank/unblank cycles and ten suspend/resume cycles,
recording successful recoveries and elapsed time. These counts are a proposed
acceptance policy, not a value read from the hardware. At each recovery check
both a touch gesture and a pen pressure stroke. Test touch-to-wake only after
its route and policy have been approved, and record the selected wake source.
The public v6 panel-follower path disables wake capability, so explicitly record
whether touch-to-wake is expected for the chosen design. Do not claim that a
panel follower is already wired by the disabled draft.

Acceptance is the dossier's three criteria plus stable recovery across repeated
power transitions. Store only sanitized, relevant device logs and descriptor
facts in `evidence/`; no serials, MACs, firmware images or raw decompilation.
