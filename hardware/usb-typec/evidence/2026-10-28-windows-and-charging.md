# Windows view of the USB-C ports, and how charging is seen on Windows and on Linux

Read-only. Nothing was written to Windows or to a device. Catalog first (`sources/binary-catalog.tsv`): every `.inf`, `.cat`, `.bin` (UCS0) and `.jsn` file below is text, signature or data, so it was read by its format. `qcusbcucsi8380.sys` is `PE ARM64`, `AARCH64:LE:64:v8A`; it was **not** decompiled, only its strings were read (`strings`). No REA run was needed. Paths are under `sources/windows/`. `live-inventory/acpi/dsdt.dsl` is decompiled from `dsdt.aml` (SHA-256 `7df886d8f79964f9b16f428fc889892d7706c8e6e59710f531537c2b003e4ea7`); line numbers refer to the `.dsl`.

## 1. DSDT facts (Verified)

| Fact | DSDT line | Meaning for Linux |
|:--|:--|:--|
| `URS0` (`QCOM0C8B`) at `0x0A600000`, `_STA = 0x0F`; `USB0` has `RHUB` with two ports; port 2 (`PRT1`, SS) carries `usb4-host-interface = UBF0.PRT0` | 63252-63330 | Same base as `usb_1_ss0` (port 0) |
| `URS1` (`QCOM0C8C`) at `0x0A800000`, `_STA = 0x0F`; SS port `usb4-host-interface = UBF0.PRT1` | 63709-63810 | Same base as `usb_1_ss1` (port 1) |
| `URS2` (`QCOM0D07`) at `0x0A000000`, `_STA = Zero` | 64178-64203 | Third port absent. Linux `usb_1_ss2` stays disabled, correct |
| `USB3` (`QCOM0D08`, "Qualcomm USB3 eXtensible Host Controller", multiport) at `0x0A400000`, `_STA = 0x0F`, root ports `MP0..MP3`; `MP0` and `MP2` are connectable, `_UPC` type `UPC3` (USB 3 Standard-A class), `_PLD` `PLDS` panel = right side | 64652-64910; `UPLD.PLDS` 63153-63160 | Hardware that Linux 7.3 does not enable (`usb_mp`). Right-side external USB 3 ports. Purpose is TBD (Q2): candidate is the Surface Connect port, **Hypothesis**, answer: collector USB tree on Windows is not available, a Linux `usb_mp` test would show it |
| `USB4` (`QCOM0D09`, `usb_2`) at `0x0A200000`, `_STA = Zero` | 64911-65063 | Absent |
| `UBF0` (`QCOM0C6D`, USB4 host router), three `ACPI0015` ports PRT0..2 | 65089-65210 | Component `usb4`; not USB-C data |
| `UCSI` (`USBC000`, "USB Type-C"), three connectors `UCN0..2`, mailbox at `0x81F20000` (`VERS`, `CCI`, `CTRL`, `MSGI`, `MSGO`), `_STA` returns `0x0F` only when `PMGK.LKUP > 0`; `_DEP` = `ABD`, `PMGK`, `UCS0` | 65213-65366 | Windows runs UCSI over the same ADSP glink path as Linux (`PMGK` is the ACPI pmic-glink client). `_PLD` for `UCN0`/`UCN1`: `PLD0`/`PLD1` |
| `_UPC` for ports = `UPCC {1, 0x09, 0x3D, 0}`: connectable, type 9 = Type-C with USB 2.0 and SuperSpeed and a switch | `UUPC` 63218-63245 | Both external USB-C ports are SS-capable Type-C |
| `_PLD` of the USB-C ports: `PLCZ`/`PLCO` panel = left, `PLD0`/`PLD1` (UCSI) panel = left | 63122-63220 | Matches the DT comments "Left-side" |
| `UCS0` (`QCOM0CA4`, "Qualcomm USB Type-C Device") resources: shared memory `0x81F20040`, GPIO `0x79` (121) and `0x7B` (123) shared inputs (the orientation pins in the DT), `0xB0` (176), `0xBA` (186), `0xBC` (188) outputs (retimer 1 reset and supplies in the DT), three PMIC GPIO outputs (`PM01` `0xD9`, `0xDA`, `0x1A1`), I2C `0x08` and `0x09` on `\_SB.I2C4` and `\_SB.I2C8` at 400 kHz | 65368-65520 (resource list: orientation 65390, 65453; retimer 1 pins 65489-65507), 65700-65780 (mailbox) | Cross-check of the DT: I2C4 (UID 4, `0xB8C000`, DSDT 51221) is DT `&i2c3`, I2C8 (UID 8, `0xB9C000`, DSDT 51372) is DT `&i2c7` (`hamoa.dtsi:2394, 2682`). Retimer address `0x8` matches; address `0x9` is also listed, purpose TBD |
| `GPIO 175` (the DT retimer-1 1.8 V enable, `vreg_rtmr1_1p8`) is **not** in the UCS0 resource list | whole DSDT has `0x00AF` nowhere | Windows controls only 176, 186, 188 for retimer 1. TBD whether 175 is a real enable on this board (Q4); the pad reads output-high on the device |
| `RTM0`, `RTM1`, `RTM2` all return `"PS8830"` | 65782-65794 | The retimer part is PS8830 |
| `PMGK` (`QCOM0C8E`, "PMIC GLink") `_DEP` = `GLNK`, `ABD`; `UPAN` copies port state from the ADSP into `UCS0` (orientation, mux, VID, SID, SVID) | 786-880 | ADSP drives port state on Windows too |
| `PMBM` (`QCOM0C2A`, PMIC battery manager) `_STA` returns **Zero on both branches** | 675-693 | Windows does **not** use the ADSP battery manager on this unit |
| `ABD` (`QCOM0427`) is the glink bus (`GenericSerialBus` region) | 319-333 | - |

## 2. Windows drivers (role column for the dossier)

Active package of `qcusbcucsi` is `qcusbcucsi8380.inf_arm64_d09abbfbe1453cf0` (1.0.4338.2200, 2025-06-02): `live-inventory/usb4/q1-pnp.raw.txt` lines 34-49 (`oem76.inf`).

| Package | Class and version | Role (grade) |
|:--|:--|:--|
| `qcusbcucsi8380` | USBDevice, 1.0.4338.2200; binds `ACPI\QCOM0CA4` | Qualcomm Type-C platform driver (KMDF with DMF). Strings show an I2C target, an ACPI target, `\_SB.URS0/1/2`, `RoleSwitchMode`, `OSDefaultRoleSwitchMode`, `USB4HREnumMode`, and a `Resources\BinaryPath` registry value pointing at `UCS0.bin`. Inference: it drives the retimers and the per-port power sequence, and arbitrates the USB role switch; the UCSI core on top is Microsoft's |
| `UCS0.bin` (SHA-256 `c9797336...2150c`) | `AeoB` data, read by format | PEP resource table for the `UCS0` device: components with PMIC LDO votes (`LDO3_D`, `LDO1_I`, `LDO1_J`, `LDO2_B`, `LDO2_J`, `LDO3_J`, `LDO1_D` for port 0; `LDO3_D`, `LDO1_I`, `LDO2_D`, `LDO14_B`, `LDO2_J`, `LDO1_C`, `LDO1_D`, `LDO2_C`, `LDO3_J` for port 1), the GCC USB30 prim/sec clocks and GDSCs, the USB PHY GDSCs, and one retimer component per port: port 0 `LDO15_B` + `CLK3_A` + three PMIC GPIO outputs each followed by a `DELAY`; port 1 `LDO15_B` + `CLK4_A` + three `DELAY` steps. Inference (Verified names, structure not fully decoded): the retimer clocks `CLK3_A`/`CLK4_A` are the DT `RPMH_RF_CLK3`/`RPMH_RF_CLK4`, and the repeater supplies match the DT (L3D, L2B, L14B, L2D, L1J, L3J, L2J). Windows additionally votes `L1I`, `L1D`, `L1C`, `L2C` and `L15B`, which no DT USB node lists (Q5) |
| `qcxhcifilter8380` | Extension, 1.0.4338.2200 | Filter on the Microsoft xHCI stack for `URS\QCOM0C8B&HOST`, `URS\QCOM0C8C&HOST`, `URS\QCOM0D07&HOST`, static host `QCOM0CA1`, multiport `QCOM0D08`, `QCOM0D09`; sets `CM_SERVICE_USB_DISK_BOOT_LOAD` (Verified, INF) |
| `qcusbfnssfilter8380` | USBDevice, 1.0.4160.6000 | Function (device) mode filter for `URS\...&FUNCTION` (gadget side; Linux has none, Q3) |
| `qcursext` | Extension, 1.0.4160.6000 | Extension on `QCOMFFE1` (URS controllers); sets `RoleSwitchMode = 6` (`HKR,,RoleSwitchMode,0x10001,6`). The Enum keys of `QCOM0C8B\0` and `QCOM0C8C\1` read the same value (`q2-registry.raw.txt:80-91`). Linux keeps `dr_mode = host` |
| `surfaceucmucsihidclient` | UCM, 2.57.16.0 | UCM client for HID-attached UCSI PPMs (`HID\VID_045E&UP:FF00_U:F900`), i.e. Surface docks. **Not** the internal UCSI |
| `surfaceretimer0`, `surfaceretimer1` | Firmware, 128.3.6.0 (`0x80030600`, 2024-05-15) | UEFI capsule payloads for "Surface USB4 Retimer (Port 0/1)" (`UEFI\RES_{05575d61-...}`, `{59b50971-...}`). Never flashed from here (S3). The installed version equals the bundled one (ESRT in the live inventory) |
| `surfaceude` | USB, 1.0.14.0 | "Qualcomm UDE Device SDX62": USB device emulation for the SDX62 modem. Not a USB-C driver; belongs to `wwan` (Inference from the INF string) |
| `surfacebattery` | Battery, 2.135.6.0 | Battery miniclass on the Surface Aggregator (`{BFD21D0B-...}\SurfaceBattery`, `ACPI\MSHW0146`) |
| `ROOT\CAD` "Charge Arbitration Driver" | present in `pnp-present.json`, no package in the DriverStore | Inbox Windows component that arbitrates between charging sources (Inference); not reverse engineered |
| `qcpmicglink8380` (`QCOM0C8E`) | - | glink client on the ADSP; owned by `dsp-subsystems` |

## 3. Charging, Windows versus Linux

Windows (Verified): the battery is the **Surface Battery** (SAM, class Battery, `pnp-present.json`); the ADSP battery manager device `PMBM` is disabled in ACPI (above). USB-C power delivery runs through UCSI on the ADSP (`PMGK`/`UCSI`/`UCS0`) and `ROOT\CAD` arbitrates. The ADSP still publishes the `charger_pd` protection domain (`surfacepro_ext_adsp8380.inf_arm64_3cc952aaca3564ae/battmgr.jsn`: domain `msm/adsp/charger_pd`, `qmi_instance_id 74`, service `tms/servreg`), which is also what Linux's in-kernel mapper serves (`qcom_pd_mapper.c:262-266`).

Linux (Verified on the device, `power_supply.txt`, M5 GPU-off boot, battery, no charger):

| Supply | Source | State seen |
|:--|:--|:--|
| `BAT1`, `ADP1` | Surface Aggregator (`surface_battery`, `surface_charger`) | `BAT1`: capacity 37, `energy_full` 44780000, `cycle_count` 141, Discharging; `ADP1` offline |
| `qcom-battmgr-bat` | ADSP via `pmic_glink` | Reports the same pack (`energy_full` 44780000, `energy_now` 17016000 against 17000000 on `BAT1`) but `cycle_count` 0, `manufacture_year` 2014, `voltage_max_design` 0, and `charge_*` return `ENODATA`. It exposes writable `charge_control_start_threshold` and `charge_control_end_threshold`, both 0 |
| `qcom-battmgr-ac`, `-usb`, `-wls` | ADSP | all offline |
| `ucsi-source-psy-pmic_glink.ucsi.01` / `.02` | UCSI (`typec_ucsi`) | `.01`: no partner, `current_max` 0. `.02`: `current_max` 1500000 uA, 5 V, Discharging, `usb_type` `[C] PD PD_PPS`, `online` 0: the unit sources 5 V, 1.5 A to the attached storage enclosure on connector 1 |

Findings:

1. Two batteries are visible (`BAT1` and `qcom-battmgr-bat`) with partly bogus data from the second. A desktop that lists both, or acts on the wrong one, misbehaves. The Windows choice (SAM only) is the safe one. Decision needed (orchestrator, with `ec-sam`): keep `BAT1` as the only battery. Candidate: do not load `qcom_battmgr` (modprobe blacklist in the image). That also removes the two writable charge thresholds. `ucsi-source-psy-*` and `ADP1` remain for AC detection. Inference; needs a charger test to confirm that `ADP1` and `ucsi-source-psy` both turn online with a PD charger.
2. S6: the investigation is read-only. Nothing in this dossier writes a charge threshold, a PD current limit or a PD power policy. The two `charge_control_*` files must stay untouched; no userspace tool shipped in the image may write them.
3. Whether a USB-C PD charger is accepted and raises `ADP1`, and how fast the pack charges, is TBD until a charger test (collector commands in `test-plan.md`, section C). The PD policy lives in the ADSP firmware and in the PMIC hardware; Linux only reads UCSI state.
