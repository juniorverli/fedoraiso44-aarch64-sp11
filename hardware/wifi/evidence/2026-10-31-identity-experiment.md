# 2026-10-31 identity experiment: does the Wi-Fi hardware give its own address?

Scope: design and host tests only; nothing was run on the device. No address, OUI or vendor name appears here or in any collector output (S5). Collector: `hardware/wifi/collector/identity.sh`; switch and request: `hardware/wifi/image-request-identity.md`.

## 1. Verified

- ath12k takes the station address from the firmware WMI ready event and reads no DT or nvmem property: `sources/linux/drivers/net/wireless/ath/ath12k/wmi.c:7066` (README MAC section) and no `of_get_mac_address` in the driver directory.
- The wiphy permanent address is set from that value: `sources/linux/drivers/net/wireless/ath/ath12k/mac.c:14870` (`SET_IEEE80211_PERM_ADDR(hw, mac_addr)`). sysfs `macaddress` of the phy shows `wiphy.perm_addr`: `sources/linux/net/wireless/sysfs.c:37`. mac80211 copies it into the netdev permanent address at creation: `sources/linux/net/mac80211/iface.c:1490-1491`.
- A udev `.link` `MACAddress=` or a NetworkManager cloned address changes only the current address (`dev_addr`), not `perm_addr`. Grade: Inference from the lines above (those paths write `dev_addr`; nothing writes `perm_addr` afterwards). Confirmed on the device only when the collector shows `wifi.current_equals_permanent=no` together with a permanent hash in an inject boot.
- `systemd.link(5)` on this host: `[Match] KernelCommandLine=` exists, negatable with `!` (man page, "Added in version 211"). The `.link` of D25 can therefore be skipped by `sp11.identity=none`.
- M8 comparison was DIFFERENT with `addr_assign_type=3` (userspace-set) (`2026-10-29-m8-wifi.md`, Q3): that compared the injected current address, so it did not test the hardware address. NetworkManager's random scan MAC is a separate mechanism (`README` MAC section).
- Host tests: `hardware/wifi/tests/identity-test.sh` passes (fixtures with fake sysfs, `ethtool`, `ip`, `iw`, `dmesg`, `systemd-hwdb`): no fake address in any spelling appears in any output, a tool that prints an address is masked by the final filter, public mode passes no argument naming the reference file to any tool (spy wrappers; a private-mode control run proves the spy is sensitive), a reference file not root-owned 0600 is refused, shellcheck 0.10.0 is clean.

## 2. What the collector records

Per station interface: SHA-256 prefix (16 hex of the lower-case colon form) of the permanent address (sysfs, cross-checked with `ethtool -P` and `ip` permaddr), of the current address and of the first address-shaped token in ath12k MAC log lines; `addr_assign_type`; scope (universal or locally administered), cast, sentinel; `oui_class=registered|not-registered-or-db-missing|not-applicable` (class only, from `systemd-hwdb`); private mode only: `MATCH`/`NO MATCH` for permanent and current against `/usr/share/sp11/identity-ref.sha256`; the mode the unit logged and which injection files exist.

## 3. Inference and Unknown

- **Inference.** Because `perm_addr` is the firmware value in every boot, the permanent-hash line answers the factory-address question even in an ordinary inject boot. The `sp11.identity=none` boot is the end-to-end confirmation: the interface itself must come up with that address, type `0(permanent)`.
- **Inference.** `oui_class` cannot distinguish "unregistered" from "hwdb missing the entry"; a registered class says only that the vendor range exists in the Fedora database, not that it is the Windows address. The reference MATCH is the real test.
- **Caveat (privacy).** A 16-hex prefix of SHA-256 over a 48-bit address is not secret: with a known vendor range the space is about 2^24 candidates and can be enumerated. The hashes are pseudonyms for private logs only; they never go to git or public evidence (this file contains none). A salted reference (`salt` line in the 0600 file) would fix that but breaks comparison with the existing `check-mac.sh`; not done.
- **Unknown.** Whether the chip OTP of this unit holds the factory address or a placeholder (Q3). Answered by the next boot with the collector.
- **Unknown.** Whether NetworkManager on the ISO keeps `cloned-mac-address=preserve` in `none` mode; irrelevant to the permanent hash, relevant to the current-address line (`addr_assign_type`).

## 4. Decision table

| Observation (`extra-wifi-identity.txt`) | Decision |
|:--|:--|
| `wifi.ref_match.permanent=MATCH` (inject or none boot) and, in the none boot, `current_equals_permanent=yes`, type `0(permanent)` | The hardware gives the factory address. Remove the Wi-Fi MAC injection (`.link` and NetworkManager copy) from private mode; keep the `wifi=` reference hash only for future verification. |
| `wifi.ref_match.permanent=NO MATCH`, permanent address valid (universal, unicast, not sentinel, class registered) | Hardware address is a valid chip-OTP address that is not the Windows one. Keep injection; record that Windows uses another address (open question for the operator: which one should Linux use). |
| `NO MATCH` and permanent address sentinel, multicast or locally administered | OTP holds no usable address. Keep injection. |
| `unavailable`, or permanent sources `DIFFER` | Inconclusive; do not change private mode; repeat once. |

Bluetooth decision table: `hardware/bluetooth/evidence/2026-10-31-identity-experiment.md`.
