# M12 device log: what the USB-C diagnostics say

Date: 2026-10-30. Boot: M12 private ISO, kernel `7.3.0-65.sp11.9`, entry `debug` (private log set `m12-20261030/<boot id>`; serials and addresses are not copied here). Setup: the boot stick (an RTL9210 NVMe enclosure, see U1) in port 0, a power source in port 1, nothing else. No USB 3 test device was used.

## Headline

Patch `0002` produced **no output**. The boot command line is the `debug` entry (`sp11.entry=debug`) and carries only `qcom_pd_mapper.dyndbg` and `pdr_interface.dyndbg`; the `ps883x.dyndbg=+p pmic_glink_altmode.dyndbg=+p` arguments exist only in `usbdbg`. `dmesg` has no `notify:`, `apply:`, `configure:` or `set:` line, and `extra-usb-typec.txt` is empty (the known wrapper; the data is in the separate files). So the PAN orientation, mux state, pin assignment and the PS8830 status tuple are **not** observed. The questions that needed the trace are still open. What can be said comes from sysfs, debugfs, GPIO and regulator state.

## Verified

| # | Fact | Source (log file in the private set) |
|:--|:--|:--|
| V1 | Both retimers are bound (`1-0008`, `3-0008` `ps883x_retimer`), `pmic_glink_altmode` and `ucsi_glink` bound, power-supply aux unbound (D23). No probe errors, no deferred USB device | `usb-typec-bindings.txt`, `dmesg.txt` |
| V2 | Port 0: partner present, data role host, power role source, UCSI orientation **reverse**, `usb_capability: usb2 [usb3]`, 1.5 A, no PD. Port 1: partner supports PD, power role **sink**, data role device, orientation **reverse**, 0 alternate modes (a charger or power-only partner) | `typec.txt`, `usb-typec-partner.txt` |
| V3 | Orientation GPIOs: 121 and 123 both read high (pull-down configured, driven by the ADSP side), agreeing with the two `reverse` sysfs values | `gpio.txt` |
| V4 | Both retimers are out of reset with all three supply rails enabled (use counts 3, 2, 1 on 1P15, 3P3, 1P8 for both retimers; reset GPIO 176 reads high with `GPIO_ACTIVE_LOW`, pm8550 GPIO 10 reads out-high likewise; 175, 186, 188 out-high). The driver leaves the retimer in reset with supplies off after probe (`ps883x.c:454-455` in the tree, `ps883x_reset()`) and only `ps883x_configure()` with `reset == false` re-enables the supplies. So `ps883x_set()` ran with a non-reset state on **both** ports | `usb-regs.txt`, `regulator_summary.txt`, `gpio.txt`; source |
| V5 | Both QMP combo PHYs are active: `fd5000.phy` and `fda000.phy` power domains active, `gcc_usb3_prim_phy_pipe_clk` and `gcc_usb3_sec_phy_pipe_clk` enabled at 125 MHz, owned by the PHYs (`usb3_pipe`) | `genpd_summary.txt`, `clk_summary.txt` |
| V6 | xHCI: bus 1 (`a600000`, port 0) HS port `U0 CCS PED`, speed 3 (high); its SS port `RxDetect`, no CCS. Bus 2 (`a800000`, port 1) and its SS port `RxDetect`; HS port empty. Root hubs for SS are 10000M (controller capability, not a link) | `xhci-ports.txt`, `usb-speed.txt` |
| V7 | The stick is **not** USB 2-only. Descriptor `0bda:9210` ("RTL9210 M.2 NVME Adapter", `bcdUSB 2.10`, negotiated 480M) has a BOS with a SuperSpeed capability (`wSpeedsSupported 0x000e`: FS/HS/5 Gbit/s) and a SuperSpeedPlus capability (10 Gbit/s). `bcdUSB 2.10` is what a SS-capable device reports at HS | `lsusb.txt` (device 3 on bus 1) |
| V8 | `usb 1-1: can't set config #1, error -71` occurs once, at HS, 0.05 s after the device descriptor and strings were read successfully (`new high-speed device number 2`). The device is disconnected, then re-enumerates 2.3 s later as device number 3 at HS and stays up and mounted | `dmesg.txt` lines near 21:31:58.4 and 21:32:00.7 |
| V9 | The collected "SS" root hubs and PHYs show no error: no `xhci`, `dwc3`, `qmp`, `phy` or `eusb2` error or warning in `dmesg`. The only USB-C noise is "Failed to create device link" (flagged supplier cycles) that M8 already showed | `dmesg.txt` |
| V10 | Every attached partner observed in M5, M8 and M12 (four ports/boots) reports orientation reverse. Normal orientation has never been observed. The bound `lsusb` data does not allow a "both orientations" claim | `typec.txt` in M5, M8, M12 |
| V11 | Reference tree and Windows comparison: identical USB-C code (`2026-10-29-reference-port.md`), the Windows UCSI client has no retimer logic (`2026-10-29-rea-windows.md`) | existing evidence |

## Inference

| # | Statement | Rests on |
|:--|:--|:--|
| I1 | The ADSP delivered PAN notifications for both ports, with a mux state that led `ps883x_set()` to leave reset (not `NO_CONN`, not USB2). Port 0 most likely received `USB3_ONLY` (mux 1) and port 1 either USB3 or `USB3_ONLY` for the power-only partner | V4; source `ps883x.c` set/configure; `pmic_glink_altmode.c` worker. Not proven: `SAFE` with a non-NONE orientation would reset, `USB_STATE` and DP states would not |
| I2 | The failure is not "lane absent in the PHY driver" and not "PHY not initialised": the PHY is powered and its pipe clock runs. It is also not "retimer never started" or "supplies off" | V4, V5 |
| I3 | `-71` is a USB 2 (HS) enumeration fault, not an SS lane fault. The USB 2 pair does not pass the PS8830 (`ps883x.c` comment at `TYPEC_MODE_USB2`) and the SS lanes cannot raise a protocol error on an HS device descriptor exchange. A failed first attempt plus a successful second one fits a transient at host bring-up (HS reset right after xHCI start with the live-boot stick already attached, eUSB2 repeater settling, or bus-powered device inrush), not a permanent cable fault | V8, V7, source comment |
| I4 | The stick falling back to HS is expected whenever the host SS receiver does not detect termination (`RxDetect`). It does not tell whether the cause is the host lanes, the retimer, the cable or the plug orientation | V6, V7 |
| I5 | "SS fails in both orientations" is **not** established; only reverse has been seen (V10). Orientation-specific handling (PS8830 `ORIENTATION_REVERSED` bit, QMP lane swap through the typec switch, PAN orientation versus the GPIO) is as plausible as a generic fault until normal orientation is seen | V10 |
| I6 | The first -71 and the 2.3 s re-enumeration coincide with ADSP/PAN activity but the order cannot be proven without the `notify`/`apply` timestamps | V8; trace was off |

## Unknown (each with what answers it)

| # | Unknown | Answer |
|:--|:--|:--|
| U1 | PAN orientation raw value, mux, pin assignment, svid, and whether `PAN_ACK` completes | `usbdbg` boot: `notify:`, `apply:`, `request:` lines |
| U2 | PS8830 status tuple actually written (`21/00/00`, `23/00/00`), `ret`, and whether reset was released in the notification path | `configure:` and `set:` lines |
| U3 | Whether the cable (not just the stick) carries SS lanes | A cable and device proven SS on Windows, same stick at a known SS cable |
| U4 | Behaviour in normal orientation, and on port 1 with a data device | Flip the plug; test port 1 with the stick |
| U5 | PHY lane state (`USB3_PCS` status), SS partner detection internals | Not readable with the read-only stack; compare U1-U4 first |
| U6 | Why the first enumeration failed and why 2.3 s elapsed before the retry | Trace with dwc3/xhci dyndbg and `usb 1-1` timing in `usbdbg` |
| U7 | PS8830 DT supply or reset timing sufficiency (4-14 ms delay between VDDIO enable and reset release exists in probe, not in `ps883x_configure()`) | Only if U1-U4 show `set ret=0` in reverse and normal and SS still absent; then a delay patch is a testable hypothesis, not before |

## Decision on patch 0003

No behavioural patch. The log contains no value that identifies a wrong mapping, an orientation inversion, a missing typec-mux call or a reset-timing fault, because the diagnostics were off. A reset-delay or mode-mapping change written now would be a guess against evidence V4/V5, which show the retimer powered and the PHY running. See the next test matrix in `test-plan.md` section G.
