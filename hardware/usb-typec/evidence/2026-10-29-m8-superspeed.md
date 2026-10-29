# M8 SuperSpeed failure and M9 diagnostic preparation

## Inputs and privacy

Private input directory: `out/device-logs/m8-20261029/4b6f080c-18f7-4235-9764-2e126b4d5a06/`.
The table hashes the compressed files, not their uncompressed contents. Only
derived hardware observations are recorded here; no raw device inventory,
serial, MAC/BD address or Windows bytes were copied into the dossier.

| Input | SHA-256 |
|:--|:--|
| `extra-usb-typec.txt.gz` | `3388642455c4836b65b1ba13e69aac8260f6a3d5016dbdcfedb551b45e6b2e22` |
| `lsusb-tree.txt.gz` | `017264f768ab1c741dbf14fd5c2e45412606875641b1d3e66b103c49738b88d5` |
| `usb-speed.txt.gz` | `4dec9f59ca5fce4d980fb990ec3381c3f14f7f3ee2e19b2d9cf470569cb4f6ba` |
| `typec.txt.gz` | `d683ed0c986ad60a48145561da5b6e1de148f218eb85ac26b726d3ca5d912f08` |
| `devices_deferred.txt.gz` | `b7f3a7362115627ce7ea25d972f7102161421541fd8341ef49b539f041d70c93` |
| `usb-dmesg.txt.gz` | `3a5c7e89158703eda4c047a9442effcfeb1c6ff617a4ebdbc63a630e8b97d1ce` |
| `dmesg.txt.gz` | `3753b5c97a558d772ef106c29aec1a2bfd76f316491e3da737da72052485d1d7` |
| `gpio.txt.gz` | `bfc4d51c68a34f6604bcaf79250e0df57a7983058598873adae9dc4017feb3ae` |
| `regulator_summary.txt.gz` | `964dc5966e482912749bb042f6a068a75bff3f468cfdfbef11cdc34a0267153f` |
| `xhci-ports.txt.gz` | `b00ad87128456297e2823cf68e20c4a14df27408941056050a7b60153703644b` |
| `lsmod.txt.gz` | `43f3e8bed55667539e535ace49f46881e54810b676f698ac8dccff511276ff11` |

## Verified device observations

1. **This is port 0, reverse orientation.** The connected UCSI partner belongs
   to `port0`, whose data role is host and orientation reverse. GPIO121 reads
   high, GPIO123 low. The enclosure is `1-1`, at 480 Mbit/s; port 1 has no
   partner. Both SuperSpeed root hubs advertise 10000 Mbit/s and have no child.
   The attached enclosure identifies as USB 2.10 in this enumeration, which
   does not establish its SuperSpeed capability or the cable's capability.
   M5 tested port 1 reversed; neither log establishes normal-orientation SS.
2. **SuperSpeed port state is RxDetect.** The first controller's USB2 port is
   U0 with a connected/enabled device. Its SS port is RxDetect, speed zero,
   with no connection. Both ports of the unused controller are RxDetect.
   A root hub's advertised 10000M speed is not evidence of a trained link.
3. **The active retimer is powered in the collected snapshot.** All six
   `1-0008` supply consumers have enable count 1. All six `3-0008` consumers
   have count 0, with GPIO175/176/186/188 low, consistent with unused port 1
   being powered down and held in reset. `vreg_l15b_1p8` is enabled.
   `ps883x`, `pmic_glink_altmode`, `ucsi_glink` and QMP combo modules are loaded.
   Supply counts do not establish the retimer's connection-status registers.
4. **The -71 is an initial USB2 enumeration failure.** At 19:45:49 the ADSP
   starts, charger PDR reports up and the enclosure initially fails SET_ADDRESS
   with -71. It enumerates successfully at high speed at 19:45:51. There is no
   corresponding successful SS enumeration. Timing correlation alone does not
   identify an ADSP, orientation, power or cable cause.
5. **There is no deferred-device backlog.** `devices_deferred.txt` is empty.
   The log contains repaired DT dependency cycles for the QMP/retimer/connector
   graph and four failed device-link additions, but no retimer I2C/configuration
   failure, altmode timeout or UCSI command error in the filtered USB log.
6. **No successful-path debug trace was requested.** The command line selects
   `sp11.entry=debug`, without the USB/DSP `dyndbg` arguments of `usbdbg`.
   `extra-usb-typec.txt` decompresses to zero bytes. This is expected: the
   image-owned hook calls `snap`/`shsnap`/`attrs`, which write separate files
   through `$OUT`; it has no normal stdout. The separate USB/typec captures
   are populated. See `image/overlay/etc/sp11-log-collector.d/usb-typec.sh:1`
   and `image/overlay/usr/libexec/sp11-log-collector:447`.

## Linux path and what the evidence does not prove

- The cycle message marks `FWLINK_FLAG_CYCLE`
  (`sources/linux/drivers/base/core.c:126`); fw_devlink relaxes cycles before
  attempting device links (`:2211`). The failed device-link addition is logged
  at `:2243`. **Inference:** these notices are not a sufficient explanation
  for SS failure given the working UCSI, powered retimer and empty deferred
  list. Removing the graph or disabling fw_devlink is unjustified.
- UCSI derives orientation from the GPIO and publishes it
  (`sources/linux/drivers/usb/typec/ucsi/ucsi_glink.c:207`). Its reverse
  attribute does not prove that the ADSP's independent PAN notification
  agrees. PAN orientation/mux/SVID are decoded separately
  (`sources/linux/drivers/soc/qcom/pmic_glink_altmode.c:461`), then applied in
  `:348`. A USB3-only notification selects `TYPEC_STATE_USB` (`:295`).
- PS8830 USB3 setup sets connection-present and USB3 bits in status register 0
  (`sources/linux/drivers/usb/typec/mux/ps883x.c:190`, `:248`), adds the reverse
  bit at `:200`, and writes registers 0, 1 and 2 at `:169`. For plain USB3 the
  expected requested tuple is **Inference from these constants**: normal
  `21/00/00`, reverse `23/00/00` (hexadecimal). These are decoder expectations,
  not measured values and not a proposal to write registers from userspace.
- QMP orientation changes reset/reinitialize the combo PHY
  (`sources/linux/drivers/phy/qualcomm/phy-qcom-qmp-combo.c:4776`); USB3 mode
  changes also do so (`:4804`). Its default mode is USB3+DP (`:5250`). The M8
  log does not reveal which transition happened or whether PAN and GPIO
  orientation agree.
- **F2 revised:** port 0 did not stay permanently unpowered after probe in M8.
  The probe's unconditional reset (`ps883x.c:455`) can still cause an early
  interruption; the snapshot cannot rule out that transient. Do not remove
  reset handling or force USB3 based on this snapshot alone.
- **Hypothesis:** reset-release settling could matter. The cold-probe path
  waits after VDDIO enable (`ps883x.c:437`); the later wake-from-reset path
  releases reset immediately (`:156`). The Windows sequence and a controlled
  comparison would be needed before treating that asymmetry as this failure's
  cause. No timing or power change is proposed in patch 0002.

## Upstream survey

Searches for PS8830/PS883x boot reset, Surface SuperSpeed and PMIC GLINK USB3
did not identify a ready-made fix for this observation. The inspected
[Torvalds source snapshot](https://code.googlesource.com/linux/torvalds/linux/+/4edcdefd4083ae04b1a5656f4be6cd83ae919ef4/drivers/usb/typec/mux/ps883x.c)
also resets at the end of probe. Direct linux-next and lore query URLs were
unavailable through the browsing tool. This is a limited survey, not proof
that linux-next/lore has no fix; no external patch/input was imported.

## M9 diagnostic patch

`patches/0002-usb-typec-log-pmic-glink-and-ps8830-state.patch` adds dynamic
debug messages only. It records validated PAN notifications, the worker's
applied state and orientation callback result, PAN request acknowledgement,
PS8830 reset, orientation, requested status bytes and configuration result.
The status tuple is a **request**, and `ret=0` reports completion of the
existing operation; neither is a hardware register readback. Raw PAN orientation
uses 0=normal/1=reverse, whereas Linux's orientation enum uses
0=none/1=normal/2=reverse (`sources/linux/include/linux/usb/typec.h:87`).

It adds no I2C transaction, GPIO, voltage, delay, PD command or firmware
operation. It is not a functional SS fix, and does not establish Windows
parity. The existing `usbdbg` arguments enable it. Validation and hand-back
are recorded in the dossier. No device test was run by this worker.

## Validation and limits

- `perl sources/linux/scripts/checkpatch.pl --strict --no-signoff` on patch
  `0002`: 0 errors, 0 warnings, 0 checks (66 patch lines checked).
- The patch reverses cleanly in the worker's edited kernel tree. A dry-run
  application to the read-only v7.3 input is also checked before hand-back.
- All three shell blocks in `test-plan.md` pass `bash -n`; they were not
  executed against a device. `scripts/index.py --check`: 21 components,
  0 errors. Project `git diff --check` passes.
- All kernel compilation ran through `scripts/kernel-dev.sh`, which holds
  `out/.kernel-build.lock`, in its Fedora container. Both
  `CONFIG_DEBUG_INFO_BTF=y` and `CONFIG_DEBUG_INFO_BTF_MODULES=y` remained set;
  the prerequisite `vmlinux` built and `readelf -S` shows `.BTF` and `.BTF_ids`.
- The initial invocation stopped at config validation because this older
  worker tree lacked the current SPI-HID symbols. Existing
  `hardware/touch-pen/patches/v7/0001..0011` were applied **only to the local
  `out/linux/usb-typec` build tree** as build dependencies. They are not part
  of USB patch `0002`; no other owner's project files were changed.
- `scripts/kernel-dev.sh usb-typec module drivers/usb/typec/mux/ps883x.ko`
  compiled the changed `ps883x.o` without compiler warnings, but failed at
  modpost on missing exports from unbuilt Type-C/bridge module dependencies.
  Local log: `out/build/usb-typec-m9-module-check.log`. This is not a successful
  `.ko` link or module-BTF validation.
- `scripts/kernel-dev.sh usb-typec module drivers/soc/qcom` passed (4 s),
  compiling the changed `pmic_glink_altmode.o` without warnings. Local log:
  `out/build/usb-typec-m9-soc-objects.log`. The directory target compiles
  objects; it does not establish a linked `pmic_glink_altmode.ko`.

**Required kernel-owner follow-up:** link both changed modules with their
integrated dependencies, check module BTF and package/initramfs consistency
before shipping the diagnostic patch. No RPM, ISO, device DTB or firmware was
produced or altered by this session. Status stays `blocked`, not `sw-ready`.
