# bluetooth

## 1. Summary

WCN7850 Bluetooth uses UART14 and `hci_qca`; M8 completes firmware setup but leaves hci0 unconfigured with only `public-address` missing. Status: `designed`: the M9 userspace fix soft-skips absent operator provisioning, with Windows provisioning traced in ARM64 REA; image refresh, independent cross-check and pairing evidence remain outstanding.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CRD08380`, UART transport | Verified | `sources/windows/live-inventory/pnp-present.json` |
| Transport | UART14, GENI SE6 in QUP wrapper 1, MMIO `0xa98000`, GPIO56–59 | Verified | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:2013`, `:6698`; ACPI `dsdt.dsl:51564` |
| Bluetooth enable | GPIO116, managed by WCN power sequencer | Verified | `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:351`; ACPI `dsdt.dsl:68635` |
| Controller | WCN7850, version `0x02000200`; runtime patch `BTFW.HAMILTON.2.0.1-00349-WOS_PATCHZ-2` | Verified | GPU-off M5 `dmesg.txt:2090-2097`, `:2138-2139`; [boot evidence](evidence/2026-10-28-linux-chain-and-m5-boot.md) |
| Public BD address | M8 lacks a configured public address; Windows-observed identity exists only in private inventory | Verified (missing configuration); TBD (Windows source selected) | M8 `extra-bluetooth.txt:10-23`; `sources/windows/live-inventory/sp11-mac.conf`; never quote its value |

`btqca` compares the controller address with the NVM address tag and sets `HCI_QUIRK_USE_BDADDR_PROPERTY` on equality (`sources/linux/drivers/bluetooth/btqca.c:683`). With no usable `local-bd-address`, the core marks it unconfigured (`sources/linux/net/bluetooth/hci_sync.c:5320`). An unconfigured controller is omitted from the normal management index list; M8 confirms this state and its missing public-address option. See [M8 and REA evidence](evidence/2026-10-29-m8-and-rea.md).

Recommendation: retain a valid controller/OTP identity automatically. Otherwise read the Windows-observed address from an operator-provided file **at boot**, then use Fedora `btmgmt public-addr` only for a controller missing that option. Supply the file after DD-writing the stick, at `BOOT:/EFI/sp11/bt-address`; installed Fedora can use a root-owned `/etc/sp11/bt-address`. Neither the file nor its contents enter git, the ISO, a DTB or an RPM. See [options and design](evidence/2026-10-28-address-design.md).

## 3. Windows

| Package in `sources/windows/DriverStore/` | Role |
|:--|:--|
| `qcbluetooth8380.inf_arm64_7ba98f6549b1f227` | Active UART/HCI driver 1.0.4374.1301; loads rampatch/NVM, handles address provisioning. INF lines 98–105, 142; private `sar-query.txt` identifies `oem112.inf`. |
| `qcbtacx_transportdriver8380.inf_arm64_df989b0e55a3b198` | Aqstic BT ACX audio transport for `ACPI\QCOM0D04` and BLE render/capture children, version 1.0.4357.0100. INF lines 15, 27–29, 49–60. Active binding not established here. |
| `qcbtaddvscregistry8380.inf_arm64_5256c4520740d6f3` | Radio INF extending inbox `bth.inf`; sets Microsoft vendor opcode `0xFD70` and opts into LE features, version 1.0.4422.0300. INF lines 19, 34–70. Active binding not established here. |

Verified in REA: device preparation reads `QCOM\BT.PROVISION` through `QcSOCPartitionDevice`, then the NVM path prioritizes an available DPP address, retains an OTP-valid path otherwise, or uses the enabled registry/random fallback (`Device Parameters\BdAddr`, four-byte DWORD). This unit's selected Windows source remains TBD; no Bluetooth UEFI-variable name or automatic Linux DPP accessor was established. The Windows-observed address must not be called a proven factory/OTP address. [M8 and REA evidence, including hashes and evidence IDs](evidence/2026-10-29-m8-and-rea.md).

Windows reads a nonempty `UserNvmFile` before board-ID selection; this unit records `hmtnv20.b3b`. That file equals Windows' generic `hmtnv20.bin` but differs from Fedora's NVM; the default address tag is equal in both. The recorded override does not prove board ID `0x3b`. ACX is an audio transport, and `qcbtaddvscregistry8380` is INF-only (no disassemblable driver). The [older comparison](evidence/2026-10-28-windows-and-previous-project.md) remains historical evidence; its strings-only ordering/board-ID inferences are superseded.

## 4. Linux 7.3

- `hci_qca` / `btqca`, compatible `qcom,wcn7850-bt`; Denali `&uart14` Bluetooth node has no `local-bd-address` or NVM override (`sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:1244`).
- M5 and M8 request Fedora `qca/hmtbtfw20.tlv`, then **directly** `qca/hmtnv20.bin`; setup succeeds. A missing `b3b` is not an observed firmware-load failure. Board ID zero/ffff or a silently discarded reply explains the generic filename (`sources/linux/drivers/bluetooth/btqca.c:193`, `:715`, `:862`).
- Bluetooth daemon 5.87 starts successfully, initializes management 1.23, remains running until shutdown and exits 0. The previous worker's statement that the journal had no Bluetooth service lines was incorrect; it is corrected in [M5 evidence](evidence/2026-10-28-linux-chain-and-m5-boot.md).
- `units-state.txt` is an unlabelled shutdown snapshot, not Bluetooth service evidence. Initial systemd-rfkill saved state 0 means soft-unblocked then; the session's final soft/hard state remains unknown.
- Native address setting already exists: `sources/linux/net/bluetooth/mgmt.c:8376`, `sources/linux/drivers/bluetooth/hci_qca.c:2078`, `sources/linux/drivers/bluetooth/btqca.c:1005`. No kernel/DT patch or kernel build is needed for this fix.
- M8 starts the helper after hci0 creation; it reaches the missing-address branch and correctly identifies the absent operator file. M9 changes that expected case to a successful soft skip with a clear journal line. No bluetoothd ordering dependency is needed; the management event announces the configured index asynchronously. M8's component capture was during shutdown; its D-Bus abort/inactive daemon is not evidence of session-time daemon failure.
- The earlier project's reported working ISO included an address service and embedded address file. Its success is operator testimony, not a verified device log; the service is the strongest explanatory difference, while its build-time identity embedding is rejected here.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| Confirmed missing public address, no operator file in M8 | [Boot helper and unit](userspace/) soft-skip cleanly; supply the private file after writing the next stick to enable actual configuration. No derived/random fallback. |
| Automatic factory address source | DPP/registry flows traced; readable Linux backing store and unit-selected source remain TBD. Metadata-only collectors in [test-plan.md](test-plan.md); no UEFI writes or Windows mounting. |
| M8 helper reports failed for expected absence | M9 helper returns 0 and logs that the controller remains unconfigured; image owner must refresh its vendored component inputs. |
| Windows `b3b` versus Linux generic NVM selection/RF suitability | Keep Fedora NVM for the address test. Obtain board-ID dynamic-debug evidence before requesting an override or Windows NVM experiment. |
| Pairing, input, radio coexistence and address stability | Follow [test plan](test-plan.md), with speakers/GPU off as required. |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Why does Linux select generic NVM when Windows records `b3b`, and does generic NVM suffice for pairing/range? | TBD | Focused board-ID debug plus device pairing/range evidence. |
| Q2 | Can M9 configure and expose hci0 using the private operator file? | TBD; M8 missing public address Verified | Helper success plus normal management index and a session-time BlueZ capture. |
| Q3 | Which traced Windows source supplies this unit's identity, and is DPP readable from Linux? | TBD | Targeted metadata/registry-presence collectors; no BT UEFI variable was identified. REA verifies the code paths, not this unit's branch. |
| Q4 | Does power-on and pairing work once configured? | TBD; M8 Bluetooth rfkill unblocked Verified | Session-time capture and pairing; helper never overrides radio state. |

## 7. Acceptance

1. Without a source, the helper exits 0, logs `controller remains unconfigured; skipped`, makes no configuration call and does not enter failed state. This is service acceptance only. Functional acceptance requires a configured-controller no-op or successful configuration from the private operator file; no address is logged.
2. `btmgmt info` includes a normal hci0 and `bluetoothctl show` exposes the adapter. GNOME can enable Bluetooth when rfkill permits it.
3. Pair and use a mouse and headset; the internal speakers stay disabled. Record pairing/profile success separately from internal audio availability.
4. The controller matches the private source on two already-planned boots. Live images without persistence need fresh pairing; cross-boot bond retention is assessed only with persistent BlueZ storage.
5. No source address, Windows binary or firmware blob enters git or an image build artefact. No firmware-flash, charging or thermal operation is introduced.

## 8. Requests

- **image (M9):** refresh the M8-integrated helper/unit/collector copies under `image/component-inputs/bluetooth/` and their provenance, per [image-request.md](image-request.md). Preserve the hci0 trigger and Fedora Bluetooth startup; include the expanded masked collector, run L0/L1 and retain address-absence checks. Preserve GPU off, sound off and D23 battery policy.
- **orchestrator/operator:** review and commit this uncommitted work, then provision the private address file after DD-writing M9 for functional testing. Arrange the independent Claude cross-check required by protocol §5.1 before promoting beyond `designed`, especially DPP payload interpretation and WDF registry scope. Batch the exact read-only collectors in [test-plan.md](test-plan.md) with an already-planned boot; no standalone reboot.
- **sources/soc-boot (conditional):** if automatic recovery is pursued, establish a read-only Linux DPP backing store for GUID `f97b8793-3abf-4719-896b-7c3e9b85e104` and `QCOM\BT.PROVISION`; no such source or BT UEFI variable is established. Use local REA snapshots in `out/rea-bluetooth-m9/`; do not port vendor write IOCTLs.
- **firmware/sources (conditional):** if an addressed controller still fails pairing/range, pin and evaluate the Windows `hmtnv20.b3b` source and selection before changing RF parameters. Do not replace Fedora generic NVM as part of this address fix.

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: BD address path verified in btqca/hci_sync; plan for an unconfigured controller recorded.
- 2026-10-28: continued interrupted Claude work under D24; corrected M5 daemon/rfkill evidence, compared the previous project, replaced ISO/UUID address provisioning with a boot-time operator file, added checked BlueZ userspace, image request and masked test plan; status `designed` pending integration/cross-check/device evidence.
- 2026-10-29: M8 confirms only public-address missing and expected absent operator file; ARM64 REA traces DPP/OTP/registry fallback, NVM override and ACX role; prepared checked M9 soft-skip helper/collector refresh, corrected the Windows board-ID inference, retained Fedora NVM and recorded automatic-source limits; no git writes or device operations.
