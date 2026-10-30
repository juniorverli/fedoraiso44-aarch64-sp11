# Risks and safety

## 1. Safety rules (override everything)

| ID | Rule | Why |
|:--|:--|:--|
| S1 | Speaker output on the WSA8845 amplifiers stays disabled until speaker protection (SP with VI feedback) runs and is evidenced on the device. A volume cap is not protection. | Driving micro-speakers without thermal and excursion protection can destroy them Exception D26 (operator-authorised 2026-10-30): the main entry may enable the speakers with OPEN-LOOP protection only (gain/volume caps, muted by default); the Windows closed-loop protection is absent on Linux and the residual risk is accepted by the operator. A fallback entry keeps speakers off. |
| S2 | The IR illuminator and the camera flash stay disabled until their eye-safety limits are established. | IR exposure is invisible |
| S3 | No firmware is written to any device (UEFI, EC, TCON, retimers, touch, Type Cover, pen, NVMe) except through the vendor's signed path with explicit human approval. | Bricking |
| S4 | The Windows partition is read-only. Never mount it read-write; never touch it while hibernated or BitLocker-encrypted. | Data loss |
| S5 | No Windows binary, firmware, key, MAC address or serial number enters git, the kernel fork or any public place. Exception (operator-authorised, 2026-10-29): a `--private` image build for the operator's own device may embed that device's MAC addresses and locally derived Wi-Fi board data inside the ISO; the ISO is named `-private`, never shared, and records hold only hashes. | Licence and privacy |
| S6 | Battery charging limits and thermal limits are never raised above the Windows values. | Hardware damage |

## 2. Project risks

| ID | Risk | Impact | Mitigation |
|:--|:--|:--|:--|
| R1 | Dark LCD on boot hides everything | High | Logs to the stick's EFI partition on every boot; an external display over USB-C DP Alt Mode; a `nomodeset` entry |
| R2 | Backlight path unknown (DPCD/AUX or PMIC PWM) | High | `display-lcd` worker decides on evidence; vanilla boot (M2) reads DPCD first |
| R3 | GPU speed bin wrong for X1P64100 | Medium | `gpu` worker confirms fuse value and OPP table before enabling high frequencies |
| R4 | 11 GB RAM, one BTF build at a time | Medium | Build lock (`agents/protocol.md` §4.2) |
| R5 | `hamoa.dtsi` describes 12 CPUs; this SoC has 10 | Medium | `soc-boot` worker removes the absent nodes |
| R6 | Firmware names in Linux differ from Windows names | Medium | `firmware` worker owns one manifest with source and destination |
| R7 | Rebase burden when moving past 7.3 | Medium | Small upstream-style patches; send upstream where possible |
| R8 | Reverse-engineered values wrong | High | Grades and citations (`agents/protocol.md` §5); no value without a source |
| R9 | Surface UEFI refuses Fedora shim 16.1 (Secure Boot off), so an installed system does not boot | High | D18: stick boots GRUB directly; installer path must set the UEFI boot entry to `grubaa64.efi`; verify on the device |
