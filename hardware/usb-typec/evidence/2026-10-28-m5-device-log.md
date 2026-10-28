# M5 device log, USB-C and charging view (2026-10-28)

Source: `out/device-logs/m5-20261028/` (not in git; contains serials, none copied here). Two boots: `3f0e2cc1` (entry `debug`, `m5` DTB, kernel `7.3.0-65.sp11.3.fc44`, `clk_ignore_unused pd_ignore_unused rootdelay=10`) and `0ee2fa1a` (entry `gpu`, `dmesg` only). The unit ran on battery; no charger. Boot medium: a USB-C NVMe enclosure (Realtek `0bda:9210`, a 1 TB NVMe inside) holding the live ISO and the `BOOT` ESP (`boot-medium.txt`). Everything below is **Verified (device)** unless marked.

## 1. What works

| Observation | Evidence |
|:--|:--|
| Both DWC3 controllers probe as host; both xHCI instances report "Host supports USB 3.1 Enhanced SuperSpeed"; roots: bus 1 (480M) and bus 2 (10000M) for `a600000` (port 0), bus 3 (480M) and bus 4 (10000M) for `a800000` (port 1) | `lsusb-tree.txt`; `dmesg` 18:15:59.62-.73 |
| ADSP and CDSP running, ADSP up 3.3 s after kernel start | `remoteproc.txt`; `dmesg` `adsp is now up` 18:15:59.92 |
| `devices_deferred` empty. Both PS8830 retimers (I2C clients `1-0008` on `b8c000`, `3-0008` on `b9c000`) probed | `devices_deferred.txt`; `regulator_summary.txt` lists their `vdd`, `vdd33`, `vddio` consumers |
| The three DP controllers (DP0, DP1, eDP) bind to `msm_dpu` together, so the retimer and altmode chain is complete | `dmesg` 18:16:00.295-.299; the dependency is in `2026-10-28-link-map.md` §2 |
| UCSI is registered with two connectors | `power_supply.txt`: `ucsi-source-psy-pmic_glink.ucsi.01` and `.02`, `usb_type [C] PD PD_PPS` |
| The enclosure is on port 1 (`xhci-hcd.2.auto` at `0x0a800000`), seen by UCSI as a partner we source: `.02` shows 5 V, `current_max` 1.5 A | `lsusb-tree.txt`, `power_supply.txt` |
| Orientation GPIOs: `gpio121` low (port 0, nothing attached), `gpio123` **high** (port 1: reverse per `ucsi_glink.c:221-226`) | `gpio.txt` lines 219 and 221 |
| Retimer 1 is powered and out of reset (`VREG_RTMR1_*` in use, TLMM 176 output high); retimer 0 is off (`VREG_RTMR0_*` use count 0), as the driver intends for an unused port | `regulator_summary.txt`, `gpio.txt` |
| Pinctrl: TLMM 176 is claimed as a plain GPIO (no pinctrl owner), 175, 186, 188 by the fixed regulators | `pinctrl-pins.txt:818-831` |

## 2. What does not work, or is odd

| # | Observation | Grade | Discussion |
|:--|:--|:--|:--|
| O1 | The enclosure (USB 3.1 Gen2 capable) enumerates only as **high-speed** (480M) on port 1; no device on bus 4 (10000M) in either boot. The root file system therefore runs over USB 2.0 | Verified | SS never trained although retimer 1 is powered and UCSI sees the partner. Candidates in `2026-10-28-failure-points.md` F1-F3 |
| O2 | The enclosure enumerates twice: `new high-speed USB device number 2` then `number 3` about 2.4-2.5 s later (boot `3f0e2cc1`: 18:15:59.97 and 18:16:02.48; boot `0ee2fa1a`: 18:24:00.91, `USB disconnect, device number 2` 18:24:01.40, number 3 at 18:24:03.84). In boot `0ee2fa1a` the disconnect and the new device come **before** `adsp is now up` (18:24:06.35) | Verified | So the re-enumeration is not caused by the ADSP altmode path. Hypothesis H1: Linux resets the HS PHY and the xHCI while the firmware had the device enumerated; the device drops and returns after its power-up delay. Hypothesis H2: a VBUS or PD event on port 1 during the controller reset. Discriminator: `dyndbg` plus the `xhci` port registers, see the test plan |
| O3 | `qcom_pmic_glink pmic-glink: Failed to create device link (0x180) with supplier a600000.usb`, `a800000.usb`, `1-0008`, `3-0008` for `connector@0/1`, and `Fixed dependency cycle(s)` lines for `phy@fd5000`/`phy@fda000` with `typec-mux@8`, `usb@a600000`/`a800000`, `connector@0/1` | Verified; benign is Inference | They are fw_devlink cycle messages from the graph `DWC3 - QMP - retimer - connector`. All the devices bound and `devices_deferred` is empty, so they cost nothing visible. The mapping of the two retimer I2C clients to the buses is Verified by the cycle lines: `i2c@b8c000/typec-mux@8` pairs with `phy@fd5000`, `i2c@b9c000/typec-mux@8` with `phy@fda000` |
| O4 | A second battery supply with bogus fields (`qcom-battmgr-bat`) next to `BAT1`; two writable charge thresholds (S6) | Verified | `2026-10-28-windows-and-charging.md` §3 |
| O5 | A kernel oops at 18:16:57 in `msm_dp_test_active_show` and `msm_dp_test_data_show` (NULL dereference, address `0xa8`) triggered by `head` reading `dp_debug` files of the DP controllers that have nothing attached | Verified | Cause: the log collector reads every `dp_debug` file (`dp-link.txt`). It is an `msm` debugfs bug on unconnected DP0/DP1, not a USB bug, but it is DP Alt Mode territory. Request to `image`: skip `test_active`, `test_data`, `test_type`; request to `display-lcd` for awareness |
| O6 | `dmesg` has no `ps883x`, `ucsi`, `altmode`, `typec` or `dwc3` line other than the above (the drivers are silent unless `dev_dbg` is on or an error occurs) | Verified | No error means no failed retimer write (`ps883x.c:170-185`), no `failed to setup retimer`, no `timeout waiting for altmode request ack`, no `UCSI` read or write timeout. Does **not** show that the altmode worker ran: the regulator state implies it did for port 1 (retimer powered) |

## 3. Answers to the questions raised by the previous project

The previous project's 2026-10-23 status (`~/repositories/surface/docs/status.md:13`) lists "PCIe and USB errors were seen" as an operator report relayed in chat, "not checked against `/EFI/sp11-logs/`". The repository holds no target log for that boot; its `docs/evidence` contain QEMU serial logs and 7.2.11 builds only. So "USB errors" was never characterised. Its handling of USB-C was: stock 7.3 Denali DT, no USB patch in the final 28-patch series (`out/agents/surface-compare/report.md` §3, §4), `rootdelay=10`, the USB, PHY, repeater, retimer and Type-C modules in the initramfs, and (7.2.11 only) a USB4 stub so that `pmic_glink_altmode` did not defer forever (`docs/status.md:2319`). Its deferred 7.2.11 patch `0101` added the missing `rtmr1_default` pinctrl, the same change as patch `0001` here.

Candidate causes for "USB errors" on that boot, unproven: the O2 re-enumeration (a `usb ... disconnect` line reads as an error), the fw_devlink messages (O3), or the oops of a collector reading `dp_debug` (O5). Only a log of that boot could say.
