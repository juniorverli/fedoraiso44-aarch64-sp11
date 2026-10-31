# Image request: identity experiment (does the hardware give its own addresses?)

Owner: image worker. Raised 2026-10-31 by the wifi worker; the Bluetooth half is in `hardware/bluetooth/image-request.md` (section "Identity experiment"). Question from the operator: after D25 private mode copies the Windows Wi-Fi MAC and Bluetooth address into the ISO, does the hardware give its own factory addresses WITHOUT that copy? The experiment is one boot of the same private ISO with the injection off, plus a read-only collector that never prints an address (S5).

The wifi worker does not own `scripts/image-build*.sh` or `image/tools/private-stage.py`; everything below is a request for the image owner. Nothing here changes public mode.

## 1. Files to install (private and public ISOs alike; they are inert unless private mode wrote the marker)

| Source | Destination | Mode |
|:--|:--|:--|
| `hardware/wifi/collector/identity.sh` | `/etc/sp11-log-collector.d/wifi-identity.sh` | 0644 |
| `hardware/wifi/userspace/sp11-wifi-identity` | `/usr/libexec/sp11-wifi-identity` | 0755 |
| `hardware/wifi/userspace/sp11-wifi-identity.service` | `/usr/lib/systemd/system/sp11-wifi-identity.service`, enabled in the SP11 preset | 0644 |
| `hardware/bluetooth/collector/*` | see the Bluetooth request | |

Only the private build installs `sp11-wifi-identity.service` if the image owner prefers that; the unit does nothing useful in public mode (no copy exists).

## 2. Private-mode builder changes (`image/tools/private-stage.py`, `scripts/image-build.sh --private`)

Public builds write none of these files.

1. **Mode marker, not secret.** Write `/usr/share/sp11/image-mode` (0644) containing the single word `private`. The collectors decide public/private from this file alone; public builds omit it.
2. **Reference hashes, secret.** Write `/usr/share/sp11/identity-ref.sha256`, root-owned, mode 0600, two lines, never in git, never in a public build, never in a log or the build record:

   ```
   wifi=<first 16 hex of sha256 of the lower-case colon-form WIFI_MAC>
   bt=<first 16 hex of sha256 of the lower-case colon-form BT_MAC>
   ```

   In `cmd_stage` (the same hash the existing `check-mac.sh` uses):

   ```python
   def h16(addr: str) -> str:
       return hashlib.sha256(addr.lower().encode()).hexdigest()[:16]
   write(root, "usr/share/sp11/image-mode", b"private\n", 0o644)
   write(root, "usr/share/sp11/identity-ref.sha256",
         f"wifi={h16(wifi)}\nbt={h16(bt)}\n".encode(), 0o600)
   ```

   `verify` and `leaks` must treat these two files as expected content; the hashes are not addresses, but `repo-clean` must still prove neither file exists in git.
3. **The switch, Wi-Fi udev part.** Change the `LINK` text so that the `.link` is skipped when the kernel argument is `sp11.identity=none` (`systemd.link(5)`: `KernelCommandLine=` is a `[Match]` key, negatable with `!`, added in systemd 211):

   ```diff
    "[Match]\n"
    f"Driver={DRIVER_GLOB}\n"
    "Type=wlan\n"
   +"KernelCommandLine=!sp11.identity=none\n"
   ```

   The NetworkManager part cannot be conditional, so `sp11-wifi-identity.service` (Before=NetworkManager.service) bind-mounts `/dev/null` over `90-sp11-wifi-mac.conf` for that boot when the argument is `none`. Nothing on disk changes.
4. **The switch, Bluetooth part.** `/usr/libexec/sp11-bt-address` (updated in `hardware/bluetooth/userspace/`) reads the same argument; with `none` it makes no `btmgmt` call and does not apply `/etc/sp11/bt-address`. Default and any other value: `inject`, as today.
5. Update the `verify` checks that assert the `.link` content (the new `KernelCommandLine=` line) and add: `image-mode` equals `private`; `identity-ref.sha256` mode 0600 root-owned with two hash lines; neither file present in a public build.

## 3. The exact switch

Kernel argument `sp11.identity=none` on the `linux` line. Absent, `inject` or any other value means inject (today's behaviour). Units log one line each:

```
sp11-wifi-identity: mode=none; NetworkManager address copy neutralised for this boot
sp11-bt-address: identity mode=none
```

and write `/run/sp11/identity-wifi-mode` and `/run/sp11/identity-bt-mode`; both collectors print them.

## 4. Where the switch lives: rotor proposal

I found no `rotor` or `grubenv` in this repository (searched `image/`, `scripts/`, `kiwi/`), only the entry table (D19) with `sp11.entry=<id>` per entry. So propose, in order of preference:

1. **A dedicated GRUB entry** `SP11 debug, no identity copy (private)`, `--id sp11-idnone`, `sp11.entry=idnone`, same DTB and arguments as the main private entry plus `sp11.identity=none`. Appears only in private builds. One boot of it answers the question.
2. If the image already has a grubenv one-shot rotor in a branch not merged here: add the same argument as a third rotor state (`next_entry=sp11-idnone`, cleared after one boot) or fold it into the SAM rotor schedule as one slot; the argument is the only contract the units rely on.

Either way the experiment is one boot; GPU and speakers stay off as in the main entry, D23 stays.

## 5. How to read the result (collector lines, no addresses)

Wi-Fi, file `extra-wifi-identity.txt`: `wifi.ref_match.permanent=MATCH|NO MATCH`, `wifi.current_equals_permanent`, `addr_assign_type=0(permanent)`. Bluetooth, file `extra-bluetooth-identity.txt`: pre-injection snapshot `bt.state=configured|unconfigured`, `bt.ref_match`. Decision table: `evidence/2026-10-31-identity-experiment.md` section 4 of each component.

## 6. Tests the image owner should add

L0 host tests: public build has neither `image-mode` nor `identity-ref.sha256`; private build has them with the right modes; `leaks` finds no address and no hash in the build record or log; `.link` contains the `KernelCommandLine=` line; unit enabled. The component tests run without hardware: `hardware/wifi/tests/identity-test.sh`, `hardware/bluetooth/tests/identity-test.sh`, `hardware/bluetooth/userspace/check.py`.
