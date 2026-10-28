# bluetooth

## 1. Summary

WCN7850 Bluetooth uses UART14 and `hci_qca`; M5 completes both firmware downloads and UART setup, while the operator reports no working Bluetooth in GNOME. Status: `designed`: a checked Fedora BlueZ boot helper is ready for image integration, but the missing-public-address diagnosis and pairing still need device evidence.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CRD08380`, UART transport | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Transport | UART14, GENI SE6 in QUP wrapper 1, MMIO `0xa98000`, GPIO56–59 | Verified | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:2013`, `:6698`; ACPI `dsdt.dsl:51564` |
| Bluetooth enable | GPIO116, managed by WCN power sequencer | Verified | `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:351`; ACPI `dsdt.dsl:68635` |
| Controller | WCN7850, version `0x02000200`; runtime patch `BTFW.HAMILTON.2.0.1-00349-WOS_PATCHZ-2` | Verified | GPU-off M5 `dmesg.txt:2090-2097`, `:2138-2139`; [boot evidence](evidence/2026-10-28-linux-chain-and-m5-boot.md) |
| Public BD address | Not captured by M5; Windows-observed value exists only in private inventory | TBD (origin/OTP) | `sources/windows/live-inventory/sp11-mac.conf`; never quote its value |

`btqca` compares the controller address with the NVM address tag and sets `HCI_QUIRK_USE_BDADDR_PROPERTY` on equality (`sources/linux/drivers/bluetooth/btqca.c:683`). With no usable `local-bd-address`, the core marks it unconfigured (`sources/linux/net/bluetooth/hci_sync.c:5256`). An unconfigured controller is omitted from the normal management index list; a running bluetoothd can therefore expose no adapter to GNOME. This source chain is Verified; whether it happened on this unit is a Hypothesis.

Recommendation: retain a valid controller/OTP identity automatically. Otherwise read the Windows-observed address from an operator-provided file **at boot**, then use Fedora `btmgmt public-addr` only for a controller missing that option. Supply the file after DD-writing the stick, at `BOOT:/EFI/sp11/bt-address`; installed Fedora can use a root-owned `/etc/sp11/bt-address`. Neither the file nor its contents enter git, the ISO, a DTB or an RPM. See [options and design](evidence/2026-10-28-address-design.md).

## 3. Windows

| Package in `sources/windows/DriverStore/` | Role |
|:--|:--|
| `qcbluetooth8380.inf_arm64_7ba98f6549b1f227` | Active UART/HCI driver 1.0.4374.1301; loads rampatch/NVM, handles address provisioning. INF lines 98–105, 142; private `sar-query.txt` identifies `oem112.inf`. |
| `qcbtacx_transportdriver8380.inf_arm64_df989b0e55a3b198` | Aqstic BT ACX audio transport for `ACPI\QCOM0D04` and BLE render/capture children, version 1.0.4357.0100. INF lines 15, 27–29, 49–60. Active binding not established here. |
| `qcbtaddvscregistry8380.inf_arm64_5256c4520740d6f3` | Radio INF extending inbox `bth.inf`; sets Microsoft vendor opcode `0xFD70` and opts into LE features, version 1.0.4422.0300. INF lines 19, 34–70. Active binding not established here. |

Verified: Windows records `UserNvmFile=hmtnv20.b3b`; that file is byte-identical to its generic `hmtnv20.bin`, but differs from Fedora's generic NVM. Driver strings mention OTP, platform DPP, registry and random address paths; their control-flow order and this unit's selected source remain Inference/TBD. The Windows-observed address must not be called a proven factory/OTP address. [Windows and previous-project evidence](evidence/2026-10-28-windows-and-previous-project.md).

## 4. Linux 7.3

- `hci_qca` / `btqca`, compatible `qcom,wcn7850-bt`; Denali `&uart14` Bluetooth node has no `local-bd-address` or NVM override (`sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1244`).
- M5 requests Fedora `qca/hmtbtfw20.tlv`, then **directly** `qca/hmtnv20.bin`; setup succeeds. A missing `b3b` is not an observed firmware-load failure. Board ID zero/ffff or a silently discarded reply explains the generic filename (`sources/linux/drivers/bluetooth/btqca.c:193`, `:715`, `:862`).
- Bluetooth daemon 5.87 starts successfully, initializes management 1.23, remains running until shutdown and exits 0. The previous worker's statement that the journal had no Bluetooth service lines was incorrect; it is corrected in [M5 evidence](evidence/2026-10-28-linux-chain-and-m5-boot.md).
- `units-state.txt` is an unlabelled shutdown snapshot, not Bluetooth service evidence. Initial systemd-rfkill saved state 0 means soft-unblocked then; the session's final soft/hard state remains unknown.
- Native address setting already exists: `sources/linux/net/bluetooth/mgmt.c:8376`, `sources/linux/drivers/bluetooth/hci_qca.c:2078`, `sources/linux/drivers/bluetooth/btqca.c:1005`. No kernel/DT patch or kernel build is needed for this fix.
- The earlier project's reported working ISO included an address service and embedded address file. Its success is operator testimony, not a verified device log; the service is the strongest explanatory difference, while its build-time identity embedding is rejected here.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| No captured management configuration or BlueZ adapter state | Install [masked collector](userspace/sp11-bt-collect); collect before/after service progress in the next existing device boot. |
| Possible missing public address | [Boot helper and unit](userspace/), explicit operator file, no derived/random fallback. Checked locally; device confirmation outstanding. |
| Windows `b3b` versus Linux generic NVM selection/RF suitability | Keep Fedora NVM for the address test. Obtain board-ID dynamic-debug evidence before requesting an override or Windows NVM experiment. |
| Pairing, input, radio coexistence and address stability | Follow [test plan](test-plan.md), with speakers/GPU off as required. |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Why does Linux select generic NVM when Windows records `b3b`, and does generic NVM suffice for pairing/range? | TBD | Focused board-ID debug plus device pairing/range evidence. |
| Q2 | Does hci0 lack a usable public address in M5? | Hypothesis | `btmgmt config`, indexed info and helper journal reporting missing option then configured state. |
| Q3 | Is the Windows-observed identity OTP, DPP, registry-persisted or generated? | TBD | A documented local provisioning source or targeted Windows read-only export; not needed for the explicit-file fix. |
| Q4 | Is any later rfkill block preventing GNOME power-on? | TBD | Collector soft/hard fields and `bluetoothctl show`; helper never overrides the user's radio state. |

## 7. Acceptance

1. Helper logs a no-op for an already configured controller, or a missing public address followed by successful configuration from the operator file; no address is logged.
2. `btmgmt info` includes a normal hci0 and `bluetoothctl show` exposes the adapter. GNOME can enable Bluetooth when rfkill permits it.
3. Pair and use a mouse and headset; the internal speakers stay disabled. Record pairing/profile success separately from internal audio availability.
4. The controller matches the private source on two already-planned boots. Live images without persistence need fresh pairing; cross-boot bond retention is assessed only with persistent BlueZ storage.
5. No source address, Windows binary or firmware blob enters git or an image build artefact. No firmware-flash, charging or thermal operation is introduced.

## 8. Requests

- **image:** integrate [image-request.md](image-request.md): install helper/unit/collector, add a systemd preset and collector hook, keep the address absent from every image layer, and run L0/L1 checks. Preserve GPU off, sound off and D23 battery policy. No standalone reboot request.
- **orchestrator/operator:** provision the private address file after DD-writing the next stick; review this uncommitted work. Arrange the independent Claude cross-check required by protocol §5.1 before promoting beyond `designed`; the resumed implementation is Codex work under D24.
- **firmware/sources (conditional):** if an addressed controller still fails pairing/range, pin and evaluate the Windows `hmtnv20.b3b` source and selection before changing RF parameters. Do not replace Fedora generic NVM as part of this address fix.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: BD address path verified in btqca/hci_sync; plan for an unconfigured controller recorded.
- 2026-10-28: continued interrupted Claude work under D24; corrected M5 daemon/rfkill evidence, compared the previous project, replaced ISO/UUID address provisioning with a boot-time operator file, added checked BlueZ userspace, image request and masked test plan; status `designed` pending integration/cross-check/device evidence.
