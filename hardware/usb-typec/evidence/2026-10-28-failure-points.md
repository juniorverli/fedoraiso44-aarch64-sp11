# Likely failure points, ranked from code, Windows data and the M5 device log

Inputs: `2026-10-28-link-map.md`, `2026-10-28-windows-and-charging.md`, `2026-10-28-m5-device-log.md`, `journal/2026-10-24.md` (the boot reaches userspace; the ADSP moved into the initramfs in M4). "F" ids are used by `test-plan.md`.

## SuperSpeed versus HS-only

**F1. SS never trains on port 1, which was plugged reversed (gpio123 high). Hypothesis, most likely.** Evidence: the enclosure is USB 3.1 Gen2 and sits at 480M; retimer 1 is powered (so the altmode worker ran `typec_retimer_set` for port 1, `ps883x.c:152-167`); there is no I2C error; UCSI sees the partner. Candidate links in the SS path that nothing has exercised on this unit: (a) the order and effect of the orientation change, which power-cycles the QMP PHY (`phy-qcom-qmp-combo.c:4776-4802`) while DWC3 holds it; (b) the retimer's reversed bit and USB 3.1 flag written in `ps883x_set()` (`ps883x.c:194-266`); (c) the ADSP reporting a mux state other than `USB3_ONLY` (for example `TUNNELING`, which sends the retimer into USB4 mode and the QMP mux into USB3-only, `pmic_glink_altmode.c:378-382`, `phy-qcom-qmp-combo.c:4835-4838`). What would kill it: SS works on the same port with the plug flipped, or on port 0 in either orientation. What would confirm it: SS fails in the reverse orientation on both ports and works in the normal one.

**F2. The retimer is enabled too late for this device. Hypothesis.** With the ADSP in the initramfs (M4) it is up 3.3 s after kernel start in boot `3f0e2cc1` (the enclosure's first HS enumeration follows 45 ms later) and 8.7 s in boot `0ee2fa1a`, where the enclosure had already been enumerated at HS at +3.2 s. A USB 3 device that has connected at HS does not necessarily retry SS when the retimer comes up later. Kill it: a hot-plug after boot (ADSP up, retimer in its idle reset state) gives SS. Confirm it: hot-plug gives SS on the same port and cable. This one matters for the live medium: the stick or enclosure is plugged before Linux starts, so the root file system would stay on USB 2.0 until a fix. A fix is not a DT change (see "Fix directions" below).

**F3. Cable or enclosure limits it to USB 2.0. Hypothesis.** The cable is unidentified. Kill it: another cable, or another SS device (a USB 3 stick) on the same port.

**F4. VBUS and role handling by the ADSP at Linux start. Hypothesis.** The enclosure drops and returns about 2.4 s later (O2), before the ADSP is up. If the PD hardware or UEFI-side state renegotiates when the controller is reset, the same can happen again when the ADSP's PD stack starts. The risk is a root device that disappears mid-boot. Evidence for: O2. Against: no disconnect after `adsp is now up` in either boot. Discriminator: `dyndbg` on `ucsi_glink`, `pmic_glink_altmode`, `ps883x`, `phy_qcom_qmp_combo`, `dwc3` plus the kernel log around the second enumeration.

## Both orientations

Port 1 was tested reversed only (gpio123 high). Port 0: nothing attached. HS works in the reverse orientation, as expected: the USB 2.0 pair does not go through the retimer (`ps883x.c:244` comment) and needs no orientation. SS in the normal orientation is **untested on both ports**. Two orientation sources exist (UCSI plus orientation GPIO, ADSP notify); both end in the same `qmp_combo_typec_switch_set()`, which ignores a repeat of the current value (`phy-qcom-qmp-combo.c:4782`), so a double notification is harmless.

## The second port

Port 1 and port 0 differ only in: the reset line has no pinctrl state (patch `0001`; the pad works without it, `pinctrl-pins.txt:819`), the supplies are on TLMM instead of PMIC GPIOs, and the QMP/HS PHY refs come from the TCSR clock controller instead of RPMh (`hamoa.dtsi:2892,2906`; `CONFIG_CLK_X1E80100_TCSRCC=y`). Port 1 works for HS. Port 0 is untested with a device.

## Retimer probe

Verified fine on both retimers (O-section 1). Residual risks: (a) GPIO 175, the DT 1.8 V enable of retimer 1, is not in the Windows UCS0 resource list (Q4); it reads output-high and the retimer answered on I2C, so it did no harm on this unit; (b) Windows also holds `LDO15_B` for the retimer component, which the DT does not model; in M5 `vreg_l15b_1p8` has one user (the WCN7850 power sequencer), so a boot without that user could leave the retimer I/O unpowered. Hypothesis; the collector lists the L15B users. With the speakers off (M5) the user count is 1.

## UCSI timeouts when the ADSP is late

Code: nothing is sent before the glink channel and the PDR service are up (`pmic_glink.c:213-264`, `ucsi_glink.c:313-330`), so a late ADSP delays UCSI but does not time out. When the ADSP is up but the `charger_pd` domain is missing, the clients never get UP and USB-C PD stays dead without an error line: check `qcom_pd_mapper` (loaded in the initramfs since M4) and `charger_pd` in the PDR traffic. Device: no UCSI timeout in M5. The case "ADSP restarts (recovery enabled)" makes `pmic_glink_rpmsg_remove` send DOWN to all clients; `ucsi_register` then runs again. Untested.

## Cross-component risks found on the way

- **LCD gating.** With DP0 and DP1 enabled, the eDP panel needs both retimers, both QMP PHYs, `pmic_glink` and `pmic_glink_altmode` to probe (`2026-10-28-link-map.md` §2). Any I2C or regulator trouble on a retimer gives a dark LCD. `image/expected-modules.txt` marks `ps883x`, `pmic_glink` and `pmic_glink_altmode` as `late`, but the M5 log shows the LCD bound at 0.7 s after the DWC3 probe, so they are in the initramfs; the file should say `early` to keep an L0 check on it (request to `image`).
- **Two batteries and writable charge thresholds** from `qcom_battmgr` (S6). See the Windows and charging note.
- **`msm` debugfs oops** from reading `dp_debug` on unconnected DP controllers (O5).
- **USB4 and docks.** A USB4 or Thunderbolt dock gives no tunnels (component `usb4`). A plain USB-C hub works as USB 3.

## Fix directions (none is built; each needs the test results first)

1. F2/F4 (retimer or SS enable at the moment of Linux start): keep the retimer powered from probe until the first ADSP notification. This is a change in `ps883x.c` (do not reset at the end of probe when the retimer reports a connection already present: the driver already tests `CONN_STATUS_0_CONNECTION_PRESENT` at `ps883x.c:428-431`, but then resets anyway at `:455`). It is a driver patch with a power cost; wait for the F1/F2 test. S3 is not touched: no retimer firmware is read or written.
2. F1: only after the debug log shows which step differs.
3. `0001` (already built): pinctrl for the second retimer reset. Not a boot fix.
