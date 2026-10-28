# usb-typec

## 1. Summary

Two USB-C ports (left side) with DWC3 host controllers, PS8830 retimers, pmic-glink UCSI and altmode on the ADSP, DisplayPort Alt Mode and USB-C charging. On the M5 ISO both retimers probe, UCSI registers both connectors and USB 2.0 works on port 1, but the SuperSpeed path did not come up (the boot enclosure runs at 480M). Status: `testing`. One optional DT patch (`0001`, second retimer reset pinctrl) is built; no fix for the SS problem exists yet, it needs the tests in `test-plan.md`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Ports | Two Type-C, `_UPC` type 9 (USB 2 + SS with switch), `_PLD` panel left; UCSI lists three connectors, the third is not built | Verified | DSDT `UUPC`, `UPLD`, `UCSI` (`2026-10-28-windows-and-charging.md` §1) |
| Controllers | `URS0` `0x0A600000` (DT `usb_1_ss0`, port 0), `URS1` `0x0A800000` (DT `usb_1_ss1`, port 1); `URS2` `0x0A000000` and `USB4` `0x0A200000` have `_STA = 0` | Verified | DSDT 63252, 63709, 64178, 64911 |
| Multiport xHCI `QCOM0D08` `0x0A400000`, `_STA = 0x0F`, ports `MP0..MP3` with `MP0` and `MP2` connectable, `_PLD` right side | Present in Windows, not enabled in the Linux DT | Verified | DSDT 64652-64910. Purpose TBD (Q2) |
| Retimers | PS8830 (ACPI `RTM0..2` = `"PS8830"`), port 0 on DT `&i2c3` (ACPI `I2C4`, `0xB8C000`), port 1 on `&i2c7` (ACPI `I2C8`, `0xB9C000`), address `0x8` (and `0x9` listed by ACPI) | Verified | DSDT 65782, 51221, 51372; `hamoa.dtsi:2394,2682` |
| Retimer control | Reset: PMIC GPIO `pm8550 10` (port 0), TLMM 176 (port 1); supplies on PMIC GPIOs (port 0) and TLMM 175/186/188 (port 1); XO `RF_CLK3`/`RF_CLK4`. Windows lists 176, 186, 188 and the orientation pins 121, 123; 175 is not in its list | Verified (DT, ACPI); 175 TBD | `2026-10-28-link-map.md` §1, Windows note |
| Retimer firmware | Windows capsule 128.3.6.0 installed and current | Verified | `surfaceretimer0/1` INF, ESRT; never written from here (S3) |
| Orientation | TLMM 121 (port 0), TLMM 123 (port 1); port 1 read high (reverse) on M5 | Verified | DT, `gpio.txt` |
| HS path | eUSB2 PHY, SMB2360 repeaters at SPMI USID 7 and 0xa | Verified | `hamoa-pmics.dtsi:668,683` |
| Power delivery | In the ADSP (UCSI over glink), SMB2360 charger/repeater chips; PD policy not ours (S6) | Inference | Windows `PMGK`/`UCSI`; `ucsi-source-psy-*` present on Linux |
| Battery | Surface Aggregator (`BAT1`, `ADP1`); the ADSP also reports a second battery on Linux | Verified | Windows: `PMBM` disabled; device `power_supply.txt` |

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcusbcucsi8380` (active `..._d09abbfbe1453cf0`, 1.0.4338.2200) | Type-C platform driver on `QCOM0CA4`: retimer I2C target, URS role switch, USB4 enumeration mode, PEP table `UCS0.bin`. Inference from strings and INF |
| `surfaceucmucsihidclient` | UCM client for HID-attached UCSI PPMs (docks); not the internal UCSI |
| `qcxhcifilter8380` | Extension filter on the Microsoft xHCI stack for URS0/1/2, multiport `QCOM0D08`, `QCOM0D09` |
| `qcusbfnssfilter8380` | Function (gadget) mode filter for the URS controllers |
| `qcursext` | URS extension, `RoleSwitchMode = 6` |
| `surfaceretimer0`, `surfaceretimer1` | UEFI capsule payloads for the PS8830 retimers (128.3.6.0); never flashed (S3) |
| `surfaceude` | UDE device for the SDX62 modem; not USB-C (belongs to `wwan`) |

Details, DSDT lines and the charging comparison: `evidence/2026-10-28-windows-and-charging.md`.

## 4. Linux 7.3

Chain and `file:line` for every link, with what depends on the ADSP: `evidence/2026-10-28-link-map.md`. In short:

- `dwc3-qcom` host (`dr_mode = "host"`, `x1-microsoft-denali.dtsi:1277,1307`), eUSB2 PHY and `smb2360` repeater, QMP combo PHY (`phy-qcom-qmp-combo.c`), `ps883x` (`typec/mux/ps883x.c`), `pmic_glink` + `pmic_glink_altmode` + `ucsi_glink`, DP controllers `mdss_dp0/1`.
- Probe needs no ADSP. Putting the retimer into SS operation, orientation, UCSI, DP HPD and the charger supplies do.
- With DP0/DP1 enabled, the eDP panel binds only after both retimers and the altmode driver probed (`link-map` §2).
- Native coverage: **partial**. M5 device log: both retimers probe, UCSI registers two connectors, HS works, SS does not (`evidence/2026-10-28-m5-device-log.md`).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| SuperSpeed does not train on port 1 (reverse plug); normal orientation and port 0 untested | Tests T1-T5 in `test-plan.md`; hypotheses F1-F4 in `evidence/2026-10-28-failure-points.md`; a `ps883x` change is possible (direction 1 there) but waits for the data |
| Retimer 1 reset line has no pinctrl state | `patches/0001` (hygiene, not a boot fix) |
| Retimer is put into reset at the end of probe and switched on only by the ADSP notification, so a device present at boot may stay HS | Same tests; driver change only after T4 |
| Two batteries and writable charge thresholds from `qcom_battmgr` | Decision with `ec-sam`/orchestrator: keep `BAT1` only; candidate is not loading `qcom_battmgr`. S6: never write the thresholds |
| USB-C PD charging untested | T7; read-only |
| `QCOM0D08` multiport controller (right side) not enabled in the DT | Q2; separate DT work after the left ports work |
| `dr_mode` host only (no gadget; Windows has `RoleSwitchMode = 6`) | Not wanted until asked (Q3) |
| USB4 / Thunderbolt docks (no tunnels) | Component `usb4` |
| `msm` debugfs oops when `dp_debug` of an unconnected DP controller is read | Collector must skip `test_*` files (request below); awareness for `display-lcd` |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Retimer 1 reset pin state and supplies | Answered for reset and 186/188: Verified (ACPI 176, 186, 188; device shows them as GPIO outputs, high). 175: TBD | A Windows-side trace is not available; Linux: the retimer works with 175 high |
| Q2 | What is the `QCOM0D08` multiport xHCI connected to? | TBD; Hypothesis: the right-side Surface Connect port (ACPI: two connectable ports, right panel) | Enable `usb_mp` in a test DTB and read `lsusb -t` with a dock; or the DSDT `_PLD` group data |
| Q3 | Is device (gadget) mode wanted? | TBD | Operator |
| Q4 | Is GPIO 175 a real 1.8 V enable for retimer 1? | TBD (absent from the Windows resource list) | Windows `UCS0.bin` retimer-1 component decoded in full, or leave as is (works) |
| Q5 | Do the extra Windows LDO votes (`L1I`, `L1D`, `L1C`, `L2C`, `L15B`) matter for USB? | TBD | A boot where the retimer I/O fails with `vreg_l15b_1p8` unused; `UCS0.bin` format decode |
| Q6 | Why does SS not train on port 1 (F1-F4)? | Hypothesis | `test-plan.md` T1-T5 with the debug entry |
| Q7 | Which physical port is `port 0`, which is `port 1`? | Inference (DT comments: bottom, top) | First `typec` listing with a partner |
| Q8 | Which charge source does the unit prefer, and is a PD charger accepted? | TBD | T7 |

## 7. Acceptance

1. USB 3 storage at 5/10 Gbit/s on both ports, both orientations (`lsusb -t` shows 5000M or 10000M).
2. External monitor over DP Alt Mode.
3. Charging from a USB-C PD charger (read-only observation; S6).

## 8. Requests

- **kernel:** `hardware/usb-typec/patches/0001-arm64-dts-qcom-x1-microsoft-denali-add-the-second-re.patch` is optional: add it to `kernel/series` with the next series revision (it is not a boot fix). Built with `kernel-dev.sh --check usb-typec dtbs` (59 s, no dt-schema warning; the DTB carries the new state), `checkpatch --strict --no-signoff` clean. Never run on the device.
- **image:** (a) add the collector commands of `test-plan.md` section B; (b) skip the `test_active`, `test_data`, `test_type` files of `dp_debug` in `dp-link.txt` (kernel oops on an unconnected DP controller); (c) add the entry `sp11.entry=usbdbg` of `test-plan.md` section C; (d) in `image/expected-modules.txt` mark `ps883x`, `pmic_glink`, `pmic_glink_altmode`, `phy-qcom-qmp-combo`, `typec_ucsi`, `ucsi_glink` as `early` if they are in the initramfs (the M5 LCD binds early only because they are); (e) decide with the orchestrator whether to blacklist `qcom_battmgr` in the image (see Gaps); never ship a tool that writes `charge_control_*`.
- **dsp-subsystems:** record that the ADSP reaches `running` 3.3 s after kernel start in M5 and that pmic-glink, `qcom_battmgr` and UCSI come up (device log). The `charger_pd` domain in `battmgr.jsn` equals the in-kernel mapper entry (`qcom_pd_mapper.c:262-266`).
- **ec-sam:** the ADSP reports the same pack as `BAT1` through `qcom_battmgr`; Windows disables the ADSP battery manager (`PMBM`, DSDT 675-693). Please decide the single battery source with the orchestrator.
- **display-lcd:** awareness: with `mdss_dp0`/`mdss_dp1` enabled the eDP bind depends on both retimers and `pmic_glink_altmode` (`evidence/2026-10-28-link-map.md` §2); `msm_dp_test_active_show` and `msm_dp_test_data_show` dereference NULL on an unconnected DP controller (`dmesg` 18:16:57).
- **orchestrator:** S6 and S3 were respected; nothing in this dossier writes charge or PD settings or touches retimer firmware. Cross-check (protocol §5.1) of patch `0001`'s values is not needed for safety (the pad numbers are in both the DT and the Windows ACPI, the drive and bias are copied from `x1-crd.dtsi`); say if you want one anyway.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-28: link map with `file:line` and ADSP dependencies; Windows ACPI/INF/PEP view and charging comparison; M5 device log read (both retimers probe, UCSI up, port 1 HS only, second battery, DP debugfs oops); failure points; patch `0001`; test plan; status `testing`.
