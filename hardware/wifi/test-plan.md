# Wi-Fi M9 test plan

One batched boot on the operator's own PC. The image owner installs the
collector; the operator need not type commands. Touch, keyboard and touchpad
worked on M8, but every new test still requires rebooting Windows. All raw
logs and private images stay under `out/`; never paste addresses, serials or
SSIDs into evidence or git.

## Contents required before boot

- Rebuilt kernel/modules with patch 0002 (Surface WCN7850 hardware-rfkill
  workaround). Confirm `CONFIG_DEBUG_INFO_BTF=y`,
  `CONFIG_DEBUG_INFO_BTF_MODULES=y`, `CONFIG_ATH12K_DEBUG=y`.
- Every M9 device DTB includes patch 0003: reusable 128 MiB default CMA,
  `alloc-ranges = <0x0 0x80000000 0x0 0x80000000>`. Cross-check this before
  testing. Existing PCIe4 patch 0001 remains.
- Fedora `atheros-firmware >= 20261019`, plus the optional operator-provided
  F2 override at `/usr/lib/firmware/updates/ath12k/WCN7850/hw2.0/board-2.bin`
  (2520880 bytes, SHA-256
  `74d0f9f9f6a601265367698a97bc58a5e7c6e28fe1c323c815feb3d5e3026891`).
  If testing F2, keep the whole ISO private. Fedora's packaged file remains.
- Updated `collector/wifi.sh`; do not install `wifi-unblock-probe.sh`.
  `options ath12k debug_mask=0x70` before module load. The image collector
  must retain at least one first/session-active Wi-Fi snapshot alongside
  the final file; a final shutdown sample must not overwrite the only
  scan evidence.
- `sp11-rfkill-events.service` may run Type=simple for observation, without
  `Before=NetworkManager.service` or any dependency from NetworkManager.
- Current S1/D22/D23 guards remain: speakers off, default GPU off,
  `qcom_battmgr` blacklisted. No charging/thermal policy changes.

## Exact read-only evidence commands

`collector/wifi.sh` contains the complete commands, including DMA masks,
CMA counters, unit timestamps, link/power state, firmware hashes and
regulatory state. The key subset below is safe for the image collector to
run at each cycle (root for kernel logs). No radio toggle or active scan is
needed; NetworkManager owns its normal scanning. A fresh empty cache early
in boot is not a failure: inspect later pre-shutdown cycles as well.

```bash
rfkill --output ID,TYPE,DEVICE,SOFT,HARD --noheadings
nmcli -t -f DEVICE,TYPE,STATE device
nmcli -t -f WIFI-HW,WIFI,WWAN-HW,WWAN general
systemctl show sp11-rfkill-events.service NetworkManager.service \
  -p Id -p Type -p Before -p After -p ActiveState -p SubState \
  -p ExecMainStatus -p ActiveEnterTimestampMonotonic
for f in /sys/bus/pci/devices/0004:01:00.0/{dma_mask_bits,consistent_dma_mask_bits}; do
  [ -r "$f" ] && { echo "$f"; cat "$f"; }
done
grep -E '^Cma(Total|Free):' /proc/meminfo
for c in /sys/kernel/mm/cma/*; do
  [ -d "$c" ] || continue
  for f in "$c"/{total_pages,available_pages,alloc_pages_success,alloc_pages_fail,release_pages_success}; do
    [ -r "$f" ] && { echo "$f"; cat "$f"; }
  done
done
dmesg | grep -i -E 'created CMA|cma.*reserved|ath12k.*(rfkill|qmi.*mem|allocation|board api)|qmi.*(mem|alloc)'
for i in $(ls /sys/class/ieee80211/*/device/net 2>/dev/null); do
  echo "interface=$i"
  iw dev "$i" scan dump | awk '
    /^BSS /{n++}
    /^\tfreq:/{f=int($2); if(f<3000) b24++; else if(f<5900) b5++; else b6++}
    END{printf "bss_total=%d bss_2g4=%d bss_5g=%d bss_6g=%d\n", n,b24,b5,b6}'
done
```

The full collector masks MAC-shaped values and endpoint serial output;
raw core `journal.txt`/`lspci.txt` remain private. QMI debug DMA addresses
are memory addresses, not station identifiers. Do not copy raw log lines
without inspection.

## Expected results and failure interpretation

1. **Root-cause fix:** wlan `hard=0`, `soft=0` without an unblock probe;
   NetworkManager marks it disconnected or connected, rather than
   unavailable. No `mac rfkill_pin 48 ...` setup message or subsequent
   firmware-induced hard block. Software airplane mode remains supported.
   If hard=1 recurs, check that the rebuilt patched module and a matching
   `microsoft,denali` DTB actually booted before changing board policy.
2. **DMA fix:** CMA creation reports 128 MiB with both base and end below
   `0x100000000`; coherent mask stays 32. QMI logs show type-1 size 7274496
   receiving a segment allocation without `will try later with small size`.
   There must be no terminal allocation error or crash. If the warning
   persists, capture exact QMI sizes, DMA masks and pool location; never
   widen masks or add a guessed fixed firmware carveout. CMA sysfs success
   counters alone do not prove DMA reachability.
3. **Board data:** `updates/` override hash matches F2, runtime board request
   size is 2520880, exact id-255 name matches using board API 2, and REGDB
   `bus=pci` still succeeds. `board_id 0xff` is expected to stay unchanged.
   Missing `firmware-2.bin` followed by API 1 is expected with these Fedora
   files; no new wrapper firmware is required.
4. **Scanning:** later cached BSS counts are positive near known 2.4/5 GHz
   APs. 6 GHz depends on AP availability/regulatory state. A hard block is
   not explained by missing APs; empty early caches alone do not disprove
   hardware functionality. Read only samples before NetworkManager stops.
5. **Listener:** NetworkManager starts independently of the event listener.
   No start job waits for that service. Inspect timestamps rather than
   treating a transient systemd ordering message as a stuck job.
6. **No regression:** PCIe Gen3 x2, endpoint bound to ath12k, zero new AER
   faults; touch, backlight and SAM HID remain usable; speakers/GPU/charging
   guards stay as above. Moving the shared CMA pool also needs display
   sanity on this boot.

F2 and the DMA placement change are now intentionally batched with the
rfkill fix for M9 at the operator's request. A successful scan establishes
radio functionality, not which board-data difference improved reception.
If firmware rejects F2, rebuild from a fresh root without the private option
and retain the kernel rfkill fix. If low CMA prevents boot/display, retain
patch 0002 and compare the previous CMA DTB. Do not diagnose either by
writing firmware or changing thermal limits.

## Acceptance after the first M9 boot

The orchestrator sets `pass` only after the dossier acceptance criteria are
met. Cached scans are the first milestone. Connection and throughput need
an operator-approved AP/profile and test endpoint; no credentials are
requested or created here. Read-only follow-up commands are `iw dev <if>
link` and `iw dev <if> station dump`, masked before quoting. Factory-address
parity still needs a permanent-address hash because M8 sampled a
userspace-set address (assignment type 3).

Suspend/recovery testing belongs to phase 4 after basic connectivity. Keep
PERST#/WAKE# patch 0001 and capture the same read-only evidence on resume.
