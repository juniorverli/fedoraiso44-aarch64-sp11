# usb-typec

## 1. Summary

Two left-side USB-C ports use DWC3, PS8830 retimers and ADSP pmic-glink UCSI/altmode for USB, DisplayPort and charging; M8 has port 0 reversed at 480M with powered retimer supplies and SS in RxDetect (M5 likewise had port 1 reversed at 480M). Status: `blocked` on REA MCP access for the required Windows comparison; patch `0001` is integrated reset-pinctrl hygiene and new patch `0002` adds M9 diagnostics only, with no functional SuperSpeed fix claimed.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Ports | Two Type-C, `_UPC` type 9 (USB 2 + SS with switch), `_PLD` panel left; UCSI lists three connectors, the third is not built | Verified | DSDT `UUPC`, `UPLD`, `UCSI` (`2026-10-28-windows-and-charging.md` §1) |
| Controllers | `URS0` `0x0A600000` (DT `usb_1_ss0`, port 0), `URS1` `0x0A800000` (DT `usb_1_ss1`, port 1); `URS2` `0x0A000000` and `USB4` `0x0A200000` have `_STA = 0` | Verified | DSDT 63252, 63709, 64178, 64911 |
| Multiport xHCI `QCOM0D08` `0x0A400000`, `_STA = 0x0F`, ports `MP0..MP3` with `MP0` and `MP2` connectable, `_PLD` right side | Present in Windows, not enabled in the Linux DT | Verified | DSDT 64652-64910. Purpose TBD (Q2) |
| Retimers | PS8830 (ACPI `RTM0..2` = `"PS8830"`), port 0 on DT `&i2c3` (ACPI `I2C4`, `0xB8C000`), port 1 on `&i2c7` (ACPI `I2C8`, `0xB9C000`), address `0x8` (and `0x9` listed by ACPI) | Verified | DSDT 65782, 51221, 51372; `hamoa.dtsi:2394,2682` |
| Retimer control | Reset: PMIC GPIO `pm8550 10` (port 0), TLMM 176 (port 1); supplies on PMIC GPIOs (port 0) and TLMM 175/186/188 (port 1); XO `RF_CLK3`/`RF_CLK4`. Windows lists 176, 186, 188 and the orientation pins 121, 123; 175 is not in its list | Verified (DT, ACPI); 175 TBD | `2026-10-28-link-map.md` §1, Windows note |
| Retimer firmware | Windows capsule 128.3.6.0 installed and current | Verified | `surfaceretimer0/1` INF, ESRT; never written from here (S3) |
| Orientation | TLMM 121 (port 0), TLMM 123 (port 1); port 1 high on M5, port 0 high on M8 (both reverse) | Verified | DT; M5/M8 `gpio.txt` and M8 `typec.txt`; M8 evidence below |
| HS path | eUSB2 PHY, SMB2360 repeaters at SPMI USID 7 and 0xa | Verified | `hamoa-pmics.dtsi:668,683` |
| Power delivery | In the ADSP (UCSI over glink), SMB2360 charger/repeater chips; PD policy not ours (S6) | Inference | Windows `PMGK`/`UCSI`; `ucsi-source-psy-*` present on Linux |
| Battery | Surface Aggregator (`BAT1`, `ADP1`); D23 blacklists the duplicate ADSP battery manager | Verified | Windows: `PMBM` disabled; `plan/decisions.md` D23 |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcusbcucsi8380` (active `..._d09abbfbe1453cf0`, 1.0.4338.2200) | Type-C platform driver on `QCOM0CA4`: retimer I2C target, URS role switch, USB4 enumeration mode, PEP table `UCS0.bin`. Inference from strings and INF |
| `qcpmicglink8380` | PMIC GLINK transport on `QCOM0C8E`; Windows ACPI forwards PAN orientation/mux state to `UCS0`. Runtime PAN enable/ack and replay sequencing still require REA (R-S1) |
| `surfaceucmucsihidclient` | UCM client for HID-attached UCSI PPMs (docks); not the internal UCSI |
| `qcxhcifilter8380` | Extension filter on the Microsoft xHCI stack for URS0/1/2, multiport `QCOM0D08`, `QCOM0D09` |
| `qcusbfnssfilter8380` | Function (gadget) mode filter for the URS controllers |
| `qcursext` | URS extension, `RoleSwitchMode = 6` |
| `surfaceretimer0`, `surfaceretimer1` | UEFI capsule payloads for the PS8830 retimers (128.3.6.0); never flashed (S3) |
| `surfaceude` | UDE device for the SDX62 modem; not USB-C (belongs to `wwan`) |

Details, DSDT lines and the charging comparison: `evidence/2026-10-28-windows-and-charging.md`. Catalog hashes, capsule classification and the exact REA access failure: `evidence/2026-10-29-rea-access.md`. No Windows binary was opened or decompiled in this session, so no REA function/evidence_id or runtime initialization sequence is claimed.

## 4. Linux 7.3

Chain and `file:line` for every link, with what depends on the ADSP: `evidence/2026-10-28-link-map.md`. In short:

- `dwc3-qcom` host (`dr_mode = "host"`, `x1-microsoft-denali.dtsi:1277,1307`), eUSB2 PHY and `smb2360` repeater, QMP combo PHY (`phy-qcom-qmp-combo.c`), `ps883x` (`typec/mux/ps883x.c`), `pmic_glink` + `pmic_glink_altmode` + `ucsi_glink`, DP controllers `mdss_dp0/1`.
- Probe needs no ADSP. Putting the retimer into SS operation, orientation, UCSI, DP HPD and the charger supplies do.
- With DP0/DP1 enabled, the eDP panel binds only after both retimers and the altmode driver probed (`link-map` §2).
- Native coverage: **partial**. M8 confirms port 0 reversed at HS with its retimer supplies enabled, no deferred devices and SS RxDetect; it booted `debug`, without the `usbdbg` trace (`evidence/2026-10-29-m8-superspeed.md`). Graph-cycle notices alone do not justify DT graph removal.
- Patch `0002` logs existing PAN/retimer state without extra I2C reads or power changes. Dynamic debug was previously insufficient: `ps883x` had no `dev_dbg` sites, and PAN logged only errors/undefined ports. M9 needs the successful-path trace before selecting a behavior change.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| SuperSpeed absent in M8 port 0 reversed and M5 port 1 reversed; normal orientations untested | M9 `usbdbg` with patch `0002`, known-good cable/device, boot versus free-port hotplug; no functional fix established |
| Required Windows initialization comparison cannot start | R-S1: REA MCP rejected the session query because approval is required while policy is never; sources owns setup |
| Retimer 1 reset pinctrl | `patches/0001` already in `kernel/series`; hygiene, not an SS fix; independent cross-check remains required |
| Retimer probe resets inherited state; later reset release has no explicit VDDIO settling delay | Hypotheses only: M8 active supplies disprove permanent power-off in that snapshot; compare Windows and capture boot trace before changing reset/delays |
| Two batteries and writable charge thresholds from `qcom_battmgr` | Resolved by D23: blacklist it; retain SAM and UCSI; never write thresholds |
| USB-C PD charging untested | T7; read-only |
| `QCOM0D08` multiport controller (right side) not enabled in the DT | Q2; separate DT work after the left ports work |
| `dr_mode` host only (no gadget; Windows has `RoleSwitchMode = 6`) | Not wanted until asked (Q3) |
| USB4 / Thunderbolt docks (no tunnels) | Component `usb4` |
| `msm` debugfs oops when `dp_debug` of an unconnected DP controller is read | Collector must skip `test_*` files (request below); awareness for `display-lcd` |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Retimer 1 reset pin state and supplies | Reset and 186/188: Verified in ACPI; high on active M5 port 1, low on unused M8 port 1. 175: TBD | Windows sequence via R-S1; M5 establishes I2C access with 175 high, not SS operation |
| Q2 | What is the `QCOM0D08` multiport xHCI connected to? | TBD; Hypothesis: the right-side Surface Connect port (ACPI: two connectable ports, right panel) | Enable `usb_mp` in a test DTB and read `lsusb -t` with a dock; or the DSDT `_PLD` group data |
| Q3 | Is device (gadget) mode wanted? | TBD | Operator |
| Q4 | Is GPIO 175 a real 1.8 V enable for retimer 1? | TBD (absent from the Windows resource list) | Windows retimer-1 driver/PEP sequence decoded; do not infer GPIO175 correctness from successful I2C probing |
| Q5 | Do the extra Windows LDO votes (`L1I`, `L1D`, `L1C`, `L2C`, `L15B`) matter for USB? | TBD | A boot where the retimer I/O fails with `vreg_l15b_1p8` unused; `UCS0.bin` format decode |
| Q6 | Why does SS not train on either reverse-oriented port in M5/M8 (F1-F4)? | Hypothesis; active M8 port 0 retimer is powered | R-S1 Windows comparison; patch `0002` plus `usbdbg`; T1-T5 with known USB3 hardware |
| Q7 | Which physical port is `port 0`, which is `port 1`? | Inference (DT comments: bottom, top) | First `typec` listing with a partner |
| Q8 | Which charge source does the unit prefer, and is a PD charger accepted? | TBD | T7 |
| Q9 | Does PAN mux/orientation agree with UCSI GPIO orientation and request USB3 on M8 hardware? | TBD; UCSI alone does not answer it | M9 trace, decoder in test-plan F |

## 7. Acceptance

1. USB 3 storage at 5/10 Gbit/s on both ports, both orientations (`lsusb -t` shows 5000M or 10000M).
2. External monitor over DP Alt Mode.
3. Charging from a USB-C PD charger (read-only observation; S6).

## 8. Requests

- **kernel (R-K1):** patch `0001` is already in `kernel/series` (its earlier DT build/checkpatch remain recorded in the 2026-10-28 Log). For M9 consider `patches/0002-usb-typec-log-pmic-glink-and-ps8830-state.patch` as a diagnostic patch only; it adds successful-path dynamic debug without register reads or hardware configuration changes. Validation is in the M8 evidence: both changed objects compile and prerequisite vmlinux has BTF, but the standalone `.ko` link lacks dependency exports; integrated module linking/BTF remains required. No DT change in `0002`. Do not label it an SS fix. Rebuild both `ps883x` and `pmic_glink_altmode` and ship matching early modules in the initramfs.
- **image (R-I1):** existing collector B and `usbdbg` entry are present; the M8 empty extension wrapper is expected and separate files contain the data. For the next M9 device test select `SP11 debug, USB + DSP trace` (`sp11.entry=usbdbg`) with patch `0002` and retain `dmesg.txt`, `usb-dmesg.txt`, `typec.txt`, `usb-speed.txt`, `xhci-ports.txt`, `gpio.txt`, `regulator_summary.txt` and `devices_deferred.txt`. Add the read-only `usb-typec-bindings.txt` command in test-plan F to the image-owned hook. Batch free-port stick orientations in that same boot where practical; exact read-only captures and decoding are in test-plan F. Keep the existing debugfs allow-list and D23 blacklist. No new collector that reads retimer registers or writes dynamic-debug controls is requested.
- **sources (R-S1, blocking):** repair REA MCP availability within the authorized read-only scope: `binary_session({})` returned `MCP tool call requires approval, but approval policy is never`. No target was opened, no decompilation or evidence_id exists, and forced language cannot yet be verified. The server must run Ghidra with `REA_GHIDRA_LANGUAGE_ID=AARCH64:LE:64:v8A`; analysis must hold `flock out/.ghidra.lock`. Exact target hashes and resume steps are in `evidence/2026-10-29-rea-access.md`. Do not disassemble SurfaceRetimer capsules or `UCS0.bin`.
- **dsp-subsystems:** record that the ADSP reaches `running` 3.3 s after kernel start in M5 and that pmic-glink, `qcom_battmgr` and UCSI come up (device log). The `charger_pd` domain in `battmgr.jsn` equals the in-kernel mapper entry (`qcom_pd_mapper.c:262-266`). M8 again reaches ADSP/PDR UP alongside UCSI; the remaining SS failure is not evidence of a missing charger PD.
- **ec-sam:** the single-battery choice is resolved by D23 (SAM only); USB-C charger acceptance remains a read-only T7 test.
- **display-lcd:** awareness: with `mdss_dp0`/`mdss_dp1` enabled the eDP bind depends on both retimers and `pmic_glink_altmode` (`evidence/2026-10-28-link-map.md` §2); `msm_dp_test_active_show` and `msm_dp_test_data_show` dereference NULL on an unconnected DP controller (`dmesg` 18:16:57).
- **orchestrator (R-O1):** arrange the independent Claude cross-check of patch `0001`'s GPIO/pinctrl values and of any future behavior patch under protocol §5.1 before `sw-ready`; this corrects the prior dossier's claim that cross-check was optional. Patch `0002` introduces no hardware value. Required Windows comparison is blocked by R-S1; no unsupported power/reset/DT routing fix was substituted. S1/S3/S5/S6 remain respected and all work is uncommitted (D24).

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-28: link map with `file:line` and ADSP dependencies; Windows ACPI/INF/PEP view and charging comparison; M5 device log read (both retimers probe, UCSI up, port 1 HS only, second battery, DP debugfs oops); failure points; patch `0001`; test plan; status `testing`.
- 2026-10-29: M8 port 0 reverse/480M/SS RxDetect evidence, powered-retimer and cycle analysis; D23 request cleanup; REA MCP access blocker with catalog hashes; diagnostic patch `0002` and M9 capture/decoder requests. Strict checkpatch and index/shell checks pass; both changed objects compile, prerequisite vmlinux has BTF, standalone module linkage blocked on unbuilt dependencies (details in M8 evidence). No behavioral SS fix or device test. Status `blocked` on R-S1. No git writes.
