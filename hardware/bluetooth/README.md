# bluetooth

## 1. Summary

Bluetooth of the WCN7850, on UART14, handled by `hci_qca`. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Windows device | `ACPI\VEN_QCOM&DEV_0C6B&SUBSYS_CRD08380 (UART transport)` | Verified | `sources/windows/live-inventory/pnp-present.json` |

### BD address

- `btqca` reads the controller's address; if it equals the default address inside the NVM file, it sets `HCI_QUIRK_USE_BDADDR_PROPERTY` (`sources/linux/drivers/bluetooth/btqca.c:683-708`). The core then wants a `local-bd-address` DT property; without a valid one the controller stays **unconfigured** and BlueZ does not use it until userspace sets an address (`sources/linux/net/bluetooth/hci_sync.c:5265-5296`). Grade: Verified (source).
- Whether this unit's controller has a factory address or the NVM default is TBD until M2 (`btmgmt info`, `dmesg | grep -i bluetooth`).
- Plan if it is unconfigured: the image worker generates, at ISO build time and on this machine only, `/etc/sp11/bt-address` from `BT_MAC` in `sources/windows/live-inventory/sp11-mac.conf`, and a boot unit runs `btmgmt --index 0 public-addr <addr>` only when the controller reports unconfigured. The address is not put in the shared DTB, git or any published file (risk S5).

## 3. Windows

| Package (`sources/windows/DriverStore/<name>.inf_arm64_*`) | Role |
|:--|:--|
| `qcbluetooth8380` | TBD |
| `qcbtacx_transportdriver8380` | TBD |
| `qcbtaddvscregistry8380` | TBD |

## 4. Linux 7.3

- Driver: `bluetooth/hci_qca (qcom,wcn7850-bt)`
- DT: `x1-microsoft-denali.dtsi &uart14 bluetooth`
- Native coverage: **full** (static read, untested).

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| per-board NVM (hmtnv20.b3b and variants) selection | TBD |
| BD address source | TBD |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Which NVM file (`hmtnv20.*`) matches this board? | TBD | INF registry and `qcbluetooth8380.sys`; `dmesg` on the device |
| Q2 | Where does the BD address come from? | TBD | Device log; UEFI variable or NVM |

## 7. Acceptance

1. Pairs with a headset and a mouse; stable address across boots

## 8. Requests

- none yet

## 9. Log

- 2026-10-23: dossier created from the static survey.
- 2026-10-24: BD address path verified in btqca/hci_sync; plan for an unconfigured controller recorded.
