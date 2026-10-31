# 2026-10-31 identity experiment: does the Bluetooth controller give its own address?

Scope: design and host tests only; nothing was run on the device. No address appears here or in any collector output (S5). Collector: `hardware/bluetooth/collector/` (`sp11-identity-bt`, `sp11-identity-bt-pre.service`, `identity.sh`); switch in `hardware/bluetooth/userspace/sp11-bt-address`; request: `image-request.md` (section "Identity experiment") and `hardware/wifi/image-request-identity.md`.

## 1. Verified

- M8: hci0 unconfigured, `public-address` the only supported and missing option (`2026-10-29-m8-and-rea.md`). In M8 the helper found no operator file, so that state is what the hardware presented without any copy. Grade: Verified for M8 (one boot, Fedora generic NVM).
- `btqca` flags the controller as using the DT address property when its address equals the NVM default tag (`sources/linux/drivers/bluetooth/btqca.c:683`); without a usable `local-bd-address` the core marks it unconfigured (`sources/linux/net/bluetooth/hci_sync.c:5320`).
- Windows: device preparation reads `QCOM\BT.PROVISION` through `QcSOCPartitionDevice`; DPP address first, OTP-valid path next, NVM default last; this unit's selected source stays TBD (`2026-10-29-m8-and-rea.md`). So "Windows shows an address" does not prove the OTP holds it.
- Host tests: `hardware/bluetooth/tests/identity-test.sh` (fake `btmgmt`, fake sysfs, fake `hciconfig`) and `hardware/bluetooth/userspace/check.py` (17 tests, 3 skipped for lack of CAP_MKNOD, includes the new `sp11.identity` cases) pass. Covered: no fake address in any spelling in any output or in the `/run` snapshot, snapshot dir 0700 and file 0600, pre snapshot kept across a simulated injection, public mode passes no argument naming the reference to any tool (spy, with a private-mode control), reference not root-owned 0600 refused, `none` makes zero `btmgmt` calls and logs its mode, default/invalid values still inject, shellcheck 0.10.0 clean for the collector and helper.

## 2. What the collector records

`bt.controller_hci0` (wcn7850, other, absent), configuration state with option names, `bt.addr.sha256_16` when an address is readable (`btmgmt info`, `hciconfig` fallback), scope, cast, sentinel and `default_nvm_sentinel` (the known default NVM value is a class flag, not an identity), `bt.ref_match=MATCH|NO MATCH` in private mode only, the mode the unit logged, and an interpretation line. Two snapshots: `pre` (before `sp11-bt-address`) and `now` (at collector time).

## 3. Inference and Unknown

- **Inference.** In an inject boot, the `pre` snapshot is what the hardware offered; `now` shows the injected result (`MATCH` after injection). A `none` boot makes `now` equal `pre` and is the end-to-end check that nothing else configures the controller.
- **Inference.** `btmgmt info` refuses while the controller is unconfigured (M8 showed the config reply only), so no hash is expected in that state; the state itself answers.
- **Unknown.** Whether this unit's OTP holds a valid address: M8 (unconfigured, missing public-address) suggests the controller reported the default/invalid address, but it ran with Fedora generic NVM whereas Windows reads `hmtnv20.b3b`; the NVM could change what the controller reports. This is the main way the experiment may mislead; the experiment keeps Fedora NVM, as the address test requires.
- **Unknown.** The Windows-side source (DPP vs OTP vs registry). The other agent's reader result (`image/tools/read-windows-bt-address.ps1`, REA of `QcSOCPartition`) answers it.
- **Caveat (privacy).** Same as Wi-Fi: a 16-hex SHA-256 prefix of a 48-bit address is enumerable; the hashes are for private logs only and none is in this file.

## 4. Decision table

| Observation (`extra-bluetooth-identity.txt`, `pre` snapshot) | Decision |
|:--|:--|
| `bt.state=configured` and `bt.ref_match=MATCH` | Controller gives the factory address. Remove the Bluetooth injection from private mode (the helper already does nothing when configured). |
| `bt.state=configured`, `NO MATCH`, address valid | Controller has its own valid address that is not the Windows one. Keep injection off by default for now; ask the operator which address should be used and whether the Windows source (DPP) differs. |
| `bt.state=unconfigured` (missing `public-address`), or `default_nvm_sentinel=yes`, or sentinel `yes` | Hardware does not supply an address. Keep injection and ask for the other agent's reader result (Windows DPP/OTP source) before any change. |
| `bt.state=unavailable`, `hci0` absent or other controller | Inconclusive; repeat once; do not change private mode. |
