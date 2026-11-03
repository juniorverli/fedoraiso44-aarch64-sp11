# Rev22 safe USB and keyboard comparison — 2026-11-03

Scope: private out/device-logs/m16-20261103-final32/, safe boot 3edfc8b6
and debug boot 15c54307, ISO rev22. Times are UTC. Verified means observed in
the named capture, not causation. Debug collection stopped at 33.03 s; live
kmsg ends at 64.349 s. Safe completed at 118.75 s. Debug USB sysfs tree,
port registers and Type-C snapshots were not captured.

## Topology and sequence

| Observation | Grade and source |
|:--|:--|
| Both boots enumerate 045E:09AE Keyboard at surface_aggregator_platform_hub/.../01:15:02:01:00; 045E:09AF is the mouse/touchpad at ...:03:00. 045E:0C80 is SPI touch/stylus. | Verified, both dmesg.txt.gz, safe 17:30:39 and debug 17:36:05. These are not USB children. Enumeration does not establish working input. |
| Safe USB tree has root hubs buses 1–4, and one non-root child: 3-1, 0bda:9210 Ugreen Storage Device, USB mass storage, 480M. No downstream USB hub or USB HID in this snapshot. | Verified, safe lsusb-tree.txt.gz, usb-devices.txt.gz, usb-speed.txt.gz and dmesg.txt.gz. The 10000M root hubs do not show a SuperSpeed child. |
| Debug dmesg shows the same 3-1 storage at high speed; no other USB child appears in initial dmesg or live kmsg. | Verified, debug dmesg.txt.gz and live kmsg; no debug lsusb tree exists, so later or unlogged topology is TBD. |
| Safe: new HS address 2 at 17:30:41.686, setup no response at 41.801 and 42.007, -71 at 42.211, new address 4 at 44.227, storage identified 44.361. | Verified, safe dmesg.txt.gz. This is a setup failure, not a diagnosis of its electrical origin (sources/linux/drivers/usb/core/hub.c:4773,5092). Retry success does not prove ongoing reliability. |
| Debug: PAN enable acknowledged 17:36:07.033; port 1 reverse and USB3 requested 07.278, retimer configuration succeeded 07.360, QMP mode changed 07.574, PAN ack 07.865; first HS address 2 at 09.403 and storage identified 09.531, without a logged address retry. | Verified, debug dmesg.txt.gz and live kmsg. Safe address attempt preceded PAN enable by 86 ms and retimer/QMP completion; debug attempt began 1.5 s after PAN ack. This is an association, not proof of cause. |
| Safe PAN port 1 raw orientation 1, mux 1, SVID ff00, Linux reverse 2, retimer tuple 23/00/00, return 0 and QMP USB3 mode 2. UCSI 1.2 registered; sysfs connected port reverse, host/source, other port unknown and device/sink; usb_role capture empty. | Verified, safe dmesg.txt.gz, typec.txt.gz and usb_role.txt.gz; diagnostic patch 0002 reports software status, not electrical readback. DWC3 nodes are host mode (sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1278,1308). An empty usb_role alone is not a role failure. |
| Safe xhci-hcd.2.auto HS port01 Speed=3 Link=U0 CCS PP PED; SS port02 RxDetect, no connected SS child. Other controller ports RxDetect. | Verified, xhci-ports.txt.gz; debug registers unavailable. Debug retimer orientation changes 2 -> 0 -> 2 before storage enumeration; safe ends 2 -> 2. No direct PHY orientation register readback. |
| Both pinctrl PMIC captures show port 0 reset pin claimed by 1-0008 and its 3.3 V pin by regulator; neither proves actual voltage or connected port 1 electrical state. Both LED snapshots have keyboard lock brightness 0 and camera indicators 0. | Verified, pinctrl-pmic.txt.gz and leds.txt.gz; snapshot only, no keyboard event history. Safe additionally captured pinctrl.txt.gz and pinctrl-pins.txt.gz. |
| Both SAM hubs and Surface keyboard register; no explicit causal keyboard error found in captured kernel and session journals. Reset-watchdog logs and debug live kmsg give no keyboard failure or USB-related reset diagnosis; debug live kmsg ends in Wi-Fi messages. | Verified within captures: both dmesg.txt.gz, session-first-journal.txt.gz, session-user-journal.txt.gz, reset-watchdog-dmesg.txt.gz, and debug kmsg-live file. A quiet log cannot disprove an input or system hang. |

Operator reports safe keyboard freeze and debug keyboard after reboot. TBD:
which physical keyboard, whether the whole desktop froze, time of failure, input
events, and whether another keyboard/hub was connected at failure. The named
Ugreen in these captures is an RTL9210 storage device, not a hub. The Surface
keyboard is the only keyboard identified in captured kernel logs, but it is not
proved to be the one tested. If it was the cover, its SSAM path has no
demonstrated dependency on external USB data. Shared power, firmware, system
freeze, or timing remains possible; none is proved. Refer to ec-sam.

## Mechanism and decision

Inference: address setup was attempted at USB 2 high speed. DT separates
usb_1_ss1_hsphy from the QMP USB3 PHY (sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:5376;
x1-microsoft-denali.dtsi:1295-1308). The QMP switch controls USB3/DP lane
orientation; ps883x_sw_set forwards orientation and the retimer gets its own
setting (sources/linux/drivers/usb/typec/mux/ps883x.c:273-307;
drivers/phy/qualcomm/phy-qcom-qmp-combo.c:4064-4072,4776-4786). A
SuperSpeed double flip does not directly explain this USB2 SET_ADDRESS error.
Indirect effects through timing or shared power are unproved. The setup failure
began before the safe port orientation notification; the comparison is one boot
per entry with GPU and timing also different. The dual-switch topology exists on
working upstream boards (2026-10-31-double-flip-verdict.md); that does not prove
Denali wiring.

Hypothesis: early boot timing or a transient eUSB2, repeater, device, cable,
power or controller condition caused this one retry. Repeat boots and
controlled hotplug/port/orientation tests can distinguish a recurring effect;
no capture selects a mechanism. Double-flip remains unproved for SuperSpeed
and cannot be credited as the keyboard or USB2 fix. No corrected quirk is
supported.

Recommendation: retain existing m15-safe orientation switches for the recovery
entry. Do not declare debug's deletion a fix or roll it into safe. For a
controlled experiment create a separate GPU-off parity entry with only the
same two deletions as debug; keep existing safe as fallback and compare both
against debug. The PHY serves DP as well as USB3 (hamoa.dtsi:5779): removing
its switch may break reverse-orientation DP lane selection. Even the preserved
safe DP path is not device-verified. Test both orientations with a known DP
adapter and retain an independent recovery path; never unplug mounted boot
media. No new DT patch is justified as a production fix or marked sw-ready.

## Windows comparison / REA

Protocol §9 order was followed through existing Linux, ACPI and INF dossiers;
2026-10-28-windows-and-charging.md cites DSDT where PMGK UPAN forwards
orientation/mux to UCS0, and 2026-10-31-double-flip-verdict.md identifies CCVL
to the Windows xHCI stack. These show data flow, not Windows PHY/retimer
ordering. The old single-analyst claim that Windows never flips the PHY has no
independently reproducible function/evidence ID and is not accepted.

Catalogued targets, paths under sources/windows/, Ghidra language for each
AARCH64:LE:64:v8A:

| Binary | SHA-256 | Role / disposition |
|:--|:--|:--|
| DriverStore/qcusbcucsi8380.inf_arm64_d09abbfbe1453cf0/qcusbcucsi8380.sys | 01987fb04ef1528af9591da4a31d62efe93cae649c67a1fc00aa7884eedcea06 | active Type-C platform, priority target |
| DriverStore/qcpmicglink8380.inf_arm64_283fc4d99dc4bd56/qcpmicglink8380.sys | 00a73e2b050d2299a33ee6823756dc94ce2a5f9e70948fc563a05938803cae2b | GLINK transport, active version TBD |
| DriverStore/qcpmicglink8380.inf_arm64_a1a10dfa522d558c/qcpmicglink8380.sys | 68b201a0b49a99d551c05dd3968800b90cb95e490d98227877c57aec0f71fe46 | alternate GLINK candidate |
| DriverStore/qcxhcifilter8380.inf_arm64_a75d050d659a0b1f/QcXhciFilter8380.sys | 85aab013ed04ca37e26ca66a96c62a0468d6b46c29acfcec28b41b7cb3a1db95 | xHCI filter, CCVL consumer candidate |
| DriverStore/qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkm8380.sys | 46237eba1c2c0a51d700cdf14730aae3f41b0a55775a185b87e618cab8285814 | GPU, no demonstrated USB orientation role; GPU worker lead |

On 2026-11-03 REA MCP binary_session({}) again returned “MCP tool call requires
approval, but approval policy is never”. No target opened and server language
cannot be established. Function address and evidence_id: none; no new REA
runtime sequence is claimed. UCS0.bin is catalogued data, not code; retimer
capsules are not disassembled. Sources must restore authorized REA access, set
forced language in the server process, lock, list procedures first, and record
path/hash/language/address/evidence ID per result. See
2026-10-29-rea-access.md R-S1. Do not infer behaviour from missing results.

## Public evidence (checked 2026-11-03)

- [linux-surface-pro-11](https://github.com/dwhinham/linux-surface-pro-11),
  maintained alongside [linux-sp11](https://github.com/dwhinham/linux-sp11):
  its X1E OLED test model reports partial USB3, working DP Alt Mode and
  attached Flex Keyboard; also warns that its ADSP firmware can disrupt USB
  boot. Model and configuration differ; it does not establish our mechanism.
- [Fedora Snapdragon WoA installation](https://fedoraproject.org/wiki/Snapdragon_WoA_Laptop_Install)
  documents Fedora 44 aarch64 and a USB-boot DSP blacklist workaround; this is
  generic platform guidance, not proof for this device or a request to change
  the image.
- [Ubuntu Snapdragon thread, 2026-08-22](https://discourse.ubuntu.com/t/ubuntu-concept-snapdragon-x-elite/48800?page=105)
  reports SP11 OLED downstream DP/DWC3 work; does not validate this X1P LCD.
  [Surface discussion, 2026-05-14](https://github.com/linux-surface/linux-surface/discussions/2128)
  reports boot/keyboard issues and disputed firmware explanations, different
  from an established Linux input freeze. Treat claims as reports.
- Searches of postmarketOS device wiki and package sources found no indexed
  SP11 Snapdragon orientation/double-flip fix as of this date; no conclusion
  about unindexed work. Searches of the above projects found no matching
  Ugreen RTL9210 SET_ADDRESS -71 fix or proof that a QMP switch causes a
  Type Cover freeze. This is a bounded negative search, not proof of absence.

