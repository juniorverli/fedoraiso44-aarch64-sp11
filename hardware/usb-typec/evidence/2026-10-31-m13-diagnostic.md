# M13 device log: the printed USB-C trace

Date: 2026-10-31. Boot: M13 private ISO, kernel `7.3.0-65.sp11.10`, entry `debug`; the command line already carries `pmic_glink_altmode.dyndbg=+p ps883x.dyndbg=+p ...`, 21 USB-C call sites enabled, so patch `0002` and the dynamic debug are live (private log set `m13-20261031/<boot id>`; nothing identifying copied). Setup as M12: the boot stick (RTL9210 NVMe enclosure `0bda:9210`, "Ugreen Storage Device") on port 0, a power source on port 1. No USB 3 test device, no flipped plug. Not used: REA. Nothing built or run.

## Verified (timeline of the trace, dmesg seconds)

| t (s) | Event | Meaning |
|:--|:--|:--|
| 20.52 / 20.56 | `ps883x_retimer 1-0008` and `3-0008`: "assert reset and disable supplies" | probe leaves both retimers in reset |
| 20.83 to 21.28 | xHCI `a600000` (bus 1/2) and `a800000` (bus 3/4) start; `usb 1-1: new high-speed device number 2` (the stick) | the stick enumerates at HS before UCSI/altmode exist: the ADSP/UEFI left port 0 attached |
| 21.648 | `usb 1-1: USB disconnect`; `ucsi_glink`: registered UCSI 1.2.0; PAN `request: cmd=0x10 arg=0 acknowledged` (port 0 enable) | the HS link drops exactly when the ADSP altmode service starts |
| 21.85 | `notify: port=0 orientation=1 mux=1 svid=ff00` | fw orientation 1 (`pmic_glink_altmode_orientation`: reverse), `mux_ctrl` 1 = `MUX_CTRL_STATE_USB3_ONLY`, svid `ff00` (not DP, not TBT) |
| 22.03 | retimer 1-0008 `orientation: 0 -> 2`; `apply: port=0 orientation=2 mux=1 svid=ff00 switch_ret=0` | switch, QMP PHY and retimer got REVERSE |
| 22.03 | `configure: conn_status=23/00/00 reset=0 in_reset=1` | tuple 0x23 = CONNECTION_PRESENT + ORIENTATION_REVERSED + USB_3_1_CONNECTED; retimer leaves reset |
| 22.105 | `set: mode=1 svid=0000 orientation=2 in_reset=0 ret=0` | `TYPEC_STATE_USB`, I2C writes succeeded |
| 22.106 | `qcom-qmp-combo-phy fd5000.phy: typec_mux_set: switching from qmpphy mode 0 to 2` | PHY goes `USB3DP` to `USB3_ONLY` and re-initialises lanes |
| 22.106 and 22.28 | `1-0008 orientation: 2 -> 0`, then `0 -> 2` | transient NONE from the typec core while the partner is re-registered (see Inference I3) |
| 22.27 to 22.99 | the same chain for port 1: `notify` (orientation 1, mux 1), `apply` reverse, `configure 23/00/00`, `set ... ret=0`, PHY `fda000` switch to mode 2; a second `notify`/`apply` after `PAN_ACK` (`request: cmd=0x11 arg=1`) ends in "same qmpphy mode, bail out" | port 1 is configured for SS too |
| 23.97 | `usb 1-1: new high-speed device number 3`, then stays up | the stick comes back at HS only |

| Fact | Source |
|:--|:--|
| No altmode (`number_of_alternate_modes` 0 on port 1; no DP SVID anywhere), no DP pin assignment (none exists in USB-only notifications), no `typec` error, no `dwc3`, `xhci`, `qmp`, `phy` or `ps883x` error line in the whole log | `usb-dmesg.txt.gz`, `usb-typec-partner.txt.gz` |
| Port 0: data role host, power role source, 1.5 A, `usb_capability usb2 [usb3]`, orientation reverse; partner present, no PD. Port 1: data role device, power role sink, `usb_power_delivery`, orientation reverse; partner with PD, 0 alternate modes (a charger or power-only source) | `typec.txt.gz` |
| PS883x: both retimers bound (`1-0008`, `3-0008`), all `VREG_RTMR*` rails on, reset GPIO and the supply GPIOs at their active levels; orientation GPIO 121 and 123 high (agree with reverse) | `usb-typec-bindings.txt.gz`, `usb-regs.txt.gz` |
| SS PHY: both QMP combo PHYs switched to USB3-only after the retimer was configured (above). xHCI: bus 1 HS port `U0 CCS PED` at speed 3; **every SS port, including the port-0 one, reads `0x0a0002a0 Link=RxDetect PP`, `CCS` clear, `LEC=0 RLC=0 TLC=0`** (no link training was ever attempted: the receiver termination of the partner is not seen) | `xhci-ports.txt.gz` |
| The stick is SS capable (V7 of the M12 note: BOS has SuperSpeed and SuperSpeedPlus capabilities; `bcdUSB 2.10`) | M12 `lsusb`; M13 `usb-devices.txt.gz` |
| `usb-typec-config` shows only the command line; `extra-usb-typec.txt` is empty (known wrapper) | the files |

## Inference

| # | Statement | Rests on |
|:--|:--|:--|
| I1 | Linux did everything the code path defines, with the values the ADSP gave: orientation, USB3-only, the retimer tuple for "USB 3.1 reverse", the PHY in USB3-only. None of the three data points printed is inconsistent with another (fw orientation, UCSI orientation, GPIO 121/123, tuple bit 1, `apply` enum 2 all say reverse) | table above; `pmic_glink_altmode.c`, `ps883x.c:193-258` |
| I2 | A software error in `ps883x`/`pmic_glink_altmode` sequencing is therefore not shown. What remains: the far end does not terminate SS lanes (cable, plug or stick adapter without SS lanes in this orientation), or the lane/flip mapping between PHY, retimer and connector is wrong for this board in one orientation, or the retimer needs something Windows does that Linux does not (`UCS0.bin`, capsule-configured equalisation) | I1; M12 U3, U7 |
| I3 | The `orientation 2 -> 0 -> 2` flap on port 0 clears and re-sets the retimer FLIP bit (`ps883x_sw_set` writes it on a live retimer) while the QMP switch ignores NONE; the final state is consistent (reverse in both, last write 22.28 s). It is a transient and is not the cause of a permanent RxDetect, but it does flip the retimer after the SS mode was set | `ps883x.c:285-310`; `phy-qcom-qmp-combo.c:4776-4783` |
| I4 | "Reverse on every port in every boot" (M5, M8, M12, M13: six plug events) is either habit of the operator (same side up) or an inverted orientation reading. Both fit all evidence; only a flipped plug separates them | V10 of M12 |
| I5 | The HS drop at 21.648 and the HS return at 23.97 are the ADSP re-arming the port (PAN enable), not a Linux fault | timeline |

## Unknown

| # | Unknown | What answers it |
|:--|:--|:--|
| U1 | Behaviour with a flipped plug (normal orientation) on port 0 and on port 1 | next test below |
| U2 | Whether the cable and plug on the stick carry SS lanes | the same stick and cable proven at 5/10 Gbit/s on Windows (the stick has 10 Gbit/s capability); a known SS device in port 1 |
| U3 | What Windows writes to the retimer (the exact tuple, equalisation, a firmware-side mode) | REA is not used here; the Windows ACPI/INF data has no retimer logic (M12 V11) |

## Decision on patch 0003: none

The trace shows no wrong value, no wrong mapping and no failed call, so any behavioural patch would be a guess against evidence that the retimer was given the correct tuple and the PHY the correct mode. Candidates considered and rejected for now:

- inverting the FLIP bit or the PHY orientation: only justified if normal orientation works with the same tuple inverted, or reverse never works; one orientation has been seen;
- a settling delay after `msleep(60)` or ordering the PHY switch after the retimer: the tuple is written 73 ms after the reset release in the log, `ret=0`; no sign of a race;
- ignoring `TYPEC_ORIENTATION_NONE` in `ps883x_sw_set` (the I3 flap): a harmless-looking hygiene change, but it cannot explain RxDetect, so it is not offered as a fix and adds risk to a driver we do not own.

## Next test (one boot, same ISO; no new build)

The M12 matrix (`test-plan.md` section G) stays valid; the first two rows decide:

1. Row 1: leave the boot stick in port 0 (it is the root medium; do not touch it). Insert a USB 3 device proven at 5 Gbit/s on Windows with its own cable into **port 1**, both orientations: insert, wait 10 s, run the section G commands, unplug 5 s, rotate the plug 180 degrees, insert, run again. Port 1 has a charger today: move the charger to the free side or use a charger-only run first.
2. Decision: if `typec` orientation changes to `normal` and `configure` prints `21/00/00` and SS comes up (`lsusb -t` 5000M/10000M, `xhci portsc` `U0`) in one orientation only, the other mapping is wrong: patch candidate is lane/flip inversion for that orientation. If SS fails in both orientations with correct tuples, the cause is cable/retimer configuration: next test is the same device on Windows with the same cable, then a Windows-side retimer register read plan (U3).
3. Keep `debug` entry if the cmdline shows `ps883x.dyndbg=+p` (it does); add `typec` and `portsc` snapshots immediately after each insertion (the log collector only snapshots at boot).
