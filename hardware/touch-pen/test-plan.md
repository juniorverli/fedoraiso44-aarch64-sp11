# Touch and pen test plan

Status: **designed**. No device test ran. Earlier BTF/W=1 and DT results apply
to the unchanged v6 baseline and old disabled draft only. The current v7
baseline and revised RFCs remain unbuilt. [Session-2 evidence](evidence/2026-10-28-quad-firmware-sequencing.md)
and [validation](evidence/2026-10-28-validation.md) distinguish completed
checks from future gates.

## Next boot: controller state only

Use the exact image-worker request and read-only commands in
[README Requests](README.md#8-requests). Stage `collect-read-only.sh`, include
temporary RFC 0014, and use `touch-pen-state.dts` with the working LCD base.
There must be no enabled HID child, touch-supply consumer or QUP1
firmware-name. The normal SPI probe records clocked RO registers before
protocol dispatch; collection only reads its journal record and existing
sysfs/debugfs files. No module loading, bind/unbind, raw MMIO, GPIO requests,
runtime-PM control writes or firmware uploads are collector operations.

Expected evidence:

- Live DT status and platform binding explain whether SE2 probed at all.
- `touch-pen-diag` shows protocol, raw FW revision, interface-disable,
  clock-status and HW parameters before initialization/firmware loading.
- The full surrounding normal probe messages explain rejection/deferral.
- GPIO40–43/48–51/64 include actual mux/direction/level/pull/drive where debugfs
  exposes them. GPIO49/50 are observed before explicitly selecting their mux.
- Installed firmware package/hash/protocol metadata is distinguished from
  loaded engine state. A disabled DT or absent message means not sampled.

Preserve normal full private collector output and export only sanitized
component evidence. Interpret outcomes using `quad-design.md`; protocol 0
alone does not prove empty IRAM, and protocol 1 alone does not prove quad support.

## Software gates before touch integration

1. Sources pins v7, the posted Romulus spi-mem transport RFC, the Microsoft
   specification and exact controller/GPI research inputs. Identify the supported GENI QSPI transfer contract and,
   if the engine needs programming, a compatible authorized payload/load path.
2. Implement quad host/GPI support and port the posted spi-mem phases onto v7, preserving
   CS. Quad reads require four placeholder bytes for eight clocks. Verify
   failure when required lanes or GPI channels are absent; do not fall back
   to one-lane FIFO or overwrite a different programmed protocol.
3. Apply/review RFCs 0015, 0013, then 0012. The MSHW0484 match supplies eb/e2;
   v7 G6 defaults to 0b/02.
   The extra GPIO49/50 mux is evidenced,
   but electrical settings need independent decoding. Check that GPIO51
   remains the input IRQ. Keep wake-resource guesses out of the first image.
4. Run the project `scripts/kernel-dev.sh` commands and fragment from README.
   Build host/GPI/transport with both BTF symbols; verify `.BTF` in vmlinux and
   applicable modules. Run binding checks and DT schema validation on the
   final enabled board, not just a disabled draft. Inspect diagnostics as well
   as process exit codes.
5. Run full `checkpatch --strict` against the assembled tree. Resolve the
   unchanged upstream baseline findings and unsigned RFCs with the authors;
   this worker does not add a Signed-off-by. Commission Claude cross-check
   under protocol §5.1 before integration. Kernel/image owners run the final
   Fedora build and image gates before the operator's next touch boot.

The old `build-test.sh` remains a historical minimal compatibility reproducer,
not the required project dev/Fedora integration gate.

## First working-touch boot

Read-only initial inspection (as root where needed):

```sh
uname -r
test -s /sys/kernel/btf/vmlinux
journalctl -k -b --no-pager | grep -iE 'geni|spi|hid|touch|digitizer|firmware|invalid proto'
ls /sys/bus/spi/devices
libinput list-devices
```

Expected: controller and HID enumeration, no unsupported-mode warnings,
descriptor timeout loops or recurring unsolicited resets. Runtime SPI bus
numbers are dynamic; identify SE2 by its OF path/MMIO address. Record the
kernel journal before/after input and power tests. v7 drops
the v6 error-counter sysfs attributes, so do not request those paths as if
they exist. Separate startup resets from recurring errors in the log.

Select the touchscreen event node with `evtest`. Check ten contacts, slot and
tracking lifetimes, corners, orientation and lifting all fingers. In GNOME
check taps, dragging, scrolling and rotation. Record actual axis ranges and
maximum contacts, rather than deriving them from a Windows collection name.

Pen is optional for this milestone. If exposed, record actual pressure/tilt,
hover, barrel button and eraser capabilities in evtest and a drawing app;
report unsupported features without guessing. No firmware-update reports,
CFU tools, touch flashing or pen flashing are part of this plan.

## Recovery and power

Once ordinary touch works, test ten display blank/unblank cycles and ten
suspend/resume cycles, checking a gesture after each and recording kernel
errors/resets. These counts are proposed acceptance policy, not hardware values.
Expected: no reset storm, lost input, spurious contacts or power-reference
imbalance. Check pen recovery only if it is present. Test wake only after
its route/policy is established; the current proposal does not enable it.

Only the orchestrator can set pass after reviewing actual evidence.
