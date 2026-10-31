# Missed taps with iptsd 3.1.0 on 045E:0C80

Date: 2026-10-31. Operator report: touch works, "sometimes you have to tap more than once".
Inputs: device logs M13 and M14b (private, only counts and generic text quoted here), iptsd v3.1.0 source
(`out/image-work/iptsd/SOURCES/v3.1.0.tar.gz`, unpacked in scratch), `image/iptsd/iptsd.spec`, patches
v7/0005, 0019, 0020, reference `out/ref/ubuntu-surface-pro-11`. No REA, no kernel build, no device access.

## 1. What the logs show

| Fact | Grade |
|:--|:--|
| iptsd connects to 045E:0C80, "Running in Touchscreen mode", loads `/etc/iptsd.conf` only | Verified (iptsd journal, both boots) |
| No `/etc/iptsd.d` file and no 0C80 preset, so compiled defaults apply | Verified (journal lists one config; v3.1.0 `etc/presets` has no 0C80) |
| Touch IRQ is `msmgpio 51 Edge`, 1147 (M13) and 3339 (M14b) counts, all on CPU0; GPIO51 reads high at idle, no pull | Verified (interrupts.txt, TLMM dump) |
| No spi-hid, GENI or GPI error in the journal; no reset or rebind line | Verified (grep of journal and dmesg) |
| hid-generic binds the device and creates a kernel single-touch node `spi 045E:0C80 Touchscreen` (ABS_X/ABS_Y, BTN_TOUCH) next to iptsd's `IPTSD Virtual Touchscreen 045E:0C80` | Verified (dmesg, evtest capabilities) |
| iptsd used 170 ms and 241 ms CPU over 94 s and 163 s | Verified; consistent with iptsd processing frames, not proof |
| Heatmap dimensions and report layout of this unit | Unknown; not in the logs. The collector prints report ids and lengths |

## 2. iptsd 3.1.0 facts that matter (Verified in source)

- **No debug logging.** `src/apps/daemon/main.cpp` only sets the log pattern; there is no `Logging.Level` key
  (`src/core/linux/config-loader.hpp` reads none), no env level loader, default level info. The contact decision
  cannot be logged by iptsd 3.1.0. The only offline route is `iptsd-dump`, which writes raw heatmap frames
  (effectively touch positions); not used by the collector, operator consent needed.
- **Compiled defaults** (`src/core/generic/config.hpp`): Neutral mode, NeutralValue 0, Activation 40,
  Deactivation 36, SizeThreshold 0.1/0.5 cm, PositionThreshold 0.04/2 cm, OrientationThreshold 1/15 deg,
  SizeMin 0.2, SizeMax 2.0, AspectMin 1.0, AspectMax 2.5, DisableOnPalm false, DisableOnStylus false,
  backoff 16 frames (fixed). The comments in the shipped `etc/iptsd.conf` say 24/20/5 for
  Activation/Deactivation/OrientationMax: that text is stale against the code; the code wins.
- `StabilityThreshold`, `TemporalWindow`, `Cone` and `Touch.Disable-on-palm` do not exist in 3.1.0. The stability
  keys are the Size/Position/OrientationThreshold pairs; palm handling is `DisableOnPalm` (off).
- **Sticky validity** (`src/contacts/validation/validator.hpp`, `src/apps/daemon/touch.hpp`): `track_validity` is on.
  A contact whose first frame fails the size (major axis 0.2 to 2.0 cm) or aspect (1.0 to 2.5) test stays invalid
  for its whole life, and an invalid contact is lifted, never sent as a touch-down. A light or brief tap whose first
  frames are small is lost completely, with no log line. Frames marked unstable (jump above the Max thresholds) are
  skipped, but that does not lose the tap.
- Device-specific presets are matched on `[Device] Vendor/Product` in `/usr/share/iptsd` and `/etc/iptsd.d`
  (sorted by name, later wins). Only one Microsoft 045E preset resembles this generation: Surface Laptop Studio 2
  (045E:0C46): Neutral average, NeutralValue 10, Activation 20, Deactivation 16, OrientationThresholdMax 90.
- Configuration source: the metadata feature report gives width, height and inversion
  (`src/ipts/device.hpp:135-160`). libinput reports the kernel node as 273x181 mm and the kernel stylus as 274x185 mm.

## 3. Causes ranked

| # | Cause | Grade | Why / what decides it |
|:--|:--|:--|:--|
| 1 | Generic Activation 40/36 (and Neutral mode) too high for this panel, so a light tap never reaches a contact | Inference | No 0C80 preset exists; the nearest newer Microsoft preset uses 20/16 with Neutral average. Decided by profile B versus A |
| 2 | Sticky validator drops a tap whose first frames fail SizeMin 0.2 or AspectMax 2.5 | Inference (mechanism Verified) | Collector: reports during a touch present but no touch-down. Step C, not enabled, no upstream value to borrow |
| 3 | Two touch sources for one panel: hid-generic's single-touch node and iptsd's node both reach GNOME | Hypothesis | Whether the device goes silent on the standard HID touch report after iptsd selects heatmap mode is Unknown. Collector counts touches on both nodes for the same taps |
| 4 | Frames lost between device and iptsd (kernel driver or hidraw) | Unknown, low | Section 4. Collector: IRQ delta against delivered reports and report spacing |
| 5 | Resume or reset losing heatmap mode (F-04, rebind path) | Unknown, low | No reset or rebind in the logs; suspend was not part of the touch test. Test touch after `s2idle` |
| 6 | Compositor behaviour (tap versus slight movement, per-application pointer emulation) | Hypothesis | Not testable here; compare against the collector's down/up durations and the operator's account |

## 4. Kernel side (Verified from the patches)

- DT (0020:68) has `interrupts-extended = <&tlmm 51 IRQ_TYPE_EDGE_FALLING>`. ACPI is Edge/ActiveLow (see
  [ACPI evidence](2026-10-24-acpi.md)); the reference DT (`0004-arm64-dts-qcom-x1-denali-Add-touchscreen-node.patch:114`)
  is identical. The driver requests the IRQ with `IRQF_ONESHOT` only and no trigger flag
  (v7/0003, v7/0005:1036), so DT decides. The trigger type is not wrong.
- One IRQ-thread run reads one report: header, then body (v7/0005:900-960; 0019 turns each into a single combined
  TX/RX GPI transfer). If the device raised a second edge while the thread was running, the genirq thread wake is
  coalesced (Inference from genirq; not read from the 7.3 source this session), so a burst could leave a report
  waiting until the next edge. Nothing in the logs shows it; the IRQ count is healthy.
- Reset and rebind: no reset worker activity in the logs. 0019 returns early after a reset and relies on the reset
  worker to recreate HID, which reconnects iptsd (Verified in the patch; behaviour on device Unknown).
- **No kernel patch is justified.** A 0022 would change a verified, reference-identical trigger without
  evidence of a lost edge, and level-low (the Surface Laptop 7 variant) is unverified for this unit. No 0022 written.
  Revisit only if the collector reports a large positive "IRQ delta minus hidraw reports" with no kernel errors.

## 5. Reference (denisix/ubuntu-surface-pro-11)

`TOUCHSCREEN.md`/`README.md`: single-touch only (tap, drag, select, scroll) through hid-generic in standard
mode, PID 0C83 on their unit, multi-touch "not working", no iptsd for touch, and a custom pen daemon for pen
(`PEN.md`). Missed taps are not mentioned anywhere. Their path never uses heatmap contact detection, so
the contact-detection causes 1 and 2 are specific to our iptsd setup and cannot be compared with the reference.

## 6. A/B plan

- Profile A: stock, no file in `/etc/iptsd.d`.
- Profile B: [`userspace/iptsd-sp11.conf`](../userspace/iptsd-sp11.conf), four Contacts values copied from the
  upstream Surface Laptop Studio 2 preset, scoped to 045E:0C80.
- Selection: marker `sp11_touch_conf` (A or B) in the boot medium's GRUB environment block, set from Linux with
  `/usr/libexec/sp11-esp-env set sp11_touch_conf=B`; read at iptsd start by
  [`userspace/sp11-touch-conf-select`](../userspace/sp11-touch-conf-select), run as `ExecStartPre` by the drop-in
  [`10-sp11-touch-conf.conf`](../userspace/10-sp11-touch-conf.conf) (a Fedora systemd drop-in). B installs the file
  as `/etc/iptsd.d/50-sp11.conf`; A removes it. The GRUB command line stays static. Unknown values mean A.
  Open item (Inference): GRUB's `save_env` keeps variable names it does not write; the image owner confirms with the
  existing rotor self-test. Fallback with no image change: the operator copies the file to `/etc/iptsd.d/` by hand and
  restarts `iptsd@*.service`, which does not survive a reboot of the live image.
- Procedure per boot: log in, run `sudo /usr/libexec/sp11-touch-tap-diag 30`, tap about 30 times with one finger,
  about one second apart, in one region of the screen, counting taps by hand. Success measure: collector
  "touches" divided by taps made. Do 30 taps in each of the two profiles, one boot each, and repeat once to see
  noise. Taps lost in A and not in B support cause 1; equal loss in both moves to causes 2 to 4.
- Decision table from the collector: reports during taps but few touches: causes 1 or 2 (iptsd); reports absent
  while the finger is down: device or driver (cause 4); kernel node counts touches that the iptsd node lacks: cause 3.

## 7. Collector

[`collector/sp11-touch-tap-diag`](../collector/sp11-touch-tap-diag), Python 3, on demand as root (stage at
`/usr/libexec/sp11-touch-tap-diag`, 0755; not a periodic `/etc/sp11-log-collector.d` hook because it needs the
operator to tap during the window). Read-only: it reads `/proc/interrupts`, opens the touch hidraw node and the two
touch event nodes with `O_RDONLY` (hidraw reports reach every open client; no grab), and reads the iptsd journal and
dmesg. It stores report id and length, arrival time, and touch down/up times only, never coordinates, report bytes,
serials or addresses. Output: IRQ before/after, report spacing and burst counts, per-node touch counts, tap-like
durations, gaps between touches, reports per touch, new spi-hid/GENI/GPI kernel lines, iptsd warnings, config
profile and file hashes. `--selftest` checks the analysis on synthetic data. Verified: selftest passes; not yet run
on the device (needs root and the touch hardware).

## 8. REA question for later (not run)

What does the Windows touch stack do for contact thresholds on 045E:0C80: does `hidspi_km` or the Surface
touch/pen processor package (`surfacetouchpenprocessor0c80update`, `surfacetouchg6fwupdateextnpackage0c80`) switch
the digitizer into heatmap mode and compute contacts on the host, or does the device report on-chip contacts
(Tip Switch, Contact Count) in standard mode? Where do activation, size and palm limits live (INF/registry values,
firmware, a processor binary), and what are their values? Look first in INF and registry data under
`sources/windows/`, and only then in the binary, with the Ghidra language from `sources/binary-catalog.tsv`.

## 9. Requests

- Image: stage the collector; adopt the selector, drop-in and `/usr/share/sp11/touch/iptsd-sp11.conf` for the A/B
  test; confirm the grubenv round trip. Remove them once a profile wins.
- Orchestrator: after the A/B run, review the numbers; a winning profile B becomes an image default only after
  the 30-tap runs agree.
