# Reference-project comparison: dwhinham/linux-sp11 versus our Linux 7.3 USB-C stack

Date: 2026-10-29. Reference: `https://github.com/dwhinham/linux-sp11`, branch
`v7.2.11-arch1-sp11`, tip `d6333a45f9bc` (blobless clone in
`out/ref/linux-sp11`). Our side: `sources/linux` at `v7.3`
(`c03c1a14507d`) plus the current main-checkout `kernel/series`, which already
contains `hardware/usb-typec/patches/0001` and `0002`.

## Result in one sentence

The reference tree contains **no USB-C commit of its own**; its USB-C behavior
comes from unmodified upstream Linux 7.2.11 code, and every USB-C driver and
Denali USB DT node it uses is byte-identical to, or older than, what we already
have in v7.3. There is therefore nothing to port, and no patch `0003`/`0004`
was written. Writing one anyway would be a guess, not a port.

## What was checked (all verified by source or by git object identity)

1. **Commit range.** `git log a2de78ee6ed8..HEAD` (`Linux 7.2.11` to the
   reference tip) lists 49 commits (including section markers): the Arch packaging commit, DP audio,
   microphone, volume keys, IRIS, eDP HPD pinmux, PWM backlight, ath12k rfkill,
   pwrseq-wcn, SAM registry, spi-hid, QSPI/GPI, SCMI autoload, cpufreq, X1P64100
   dtsi, 5G variants, MHI. Path-limited logs over `drivers/usb`,
   `drivers/phy/qualcomm`, `drivers/soc/qcom`, `hamoa*.dtsi`, `x1-*` against
   this base and against the older branches `v7.2.6-arch2-sp11`,
   `v7.2.7-arch1-sp11`, `v7.2.8-arch1-sp11` and `-dev` return only Denali DT
   commits for audio, microphone, keys, IRIS, touch and backlight. None touches
   a USB, retimer, orientation, PHY or pmic-glink node.
2. **Driver identity.** Git blob hashes of these files are identical between the
   reference at `v7.2.11` and our `v7.3`: `drivers/usb/typec/mux/ps883x.c`,
   `drivers/usb/typec/mux.c`, `drivers/usb/typec/ucsi/ucsi_glink.c`,
   `drivers/soc/qcom/pmic_glink.c`, `drivers/soc/qcom/pmic_glink_altmode.c`,
   `drivers/phy/qualcomm/phy-qcom-eusb2-repeater.c`,
   `drivers/usb/typec/mux/Kconfig`.
3. **Files that differ are newer on our side.** `phy-qcom-qmp-combo.c` differs
   only by SM8475 and v10 (Glymur) tables and layouts. `dwc3/core.c` differs by
   a power-supply notifier. `dwc3-qcom.c` differs by one `static`. The
   `dwc3_power_off_all_roothub_ports()` logic in `dwc3/host.c` is in both
   `v7.2` and `v7.3` (upstream commit `5ed9cc71432a`, 2025-10); `v7.3` only adds
   a cosmetic xHCI macro change (`6d45e9556d4a`). Upstream commits between v7.2
   and v7.3 that touch `drivers/usb/typec` are fixes (for example
   `6c51f09c6db5` maps UCSI connectors by `reg`, which our DT already satisfies
   with `connector@0` and `connector@1`); none touches `ps883x`,
   `pmic_glink_altmode` or `ucsi_glink`.
4. **Denali DT.** Reference `x1-microsoft-denali.dtsi` versus ours (v7.3): no
   difference in any line containing usb, typec, retimer, ps883, phy, dwc,
   ucsi, glink, orientation, eusb or repeater. The retimer nodes (`&i2c3`,
   `&i2c7`, `typec-mux@8`, `retimer-switch`, `orientation-switch`), the
   `orientation-gpios = <&tlmm 121>, <&tlmm 123>` pmic-glink property and the
   eUSB2 repeater wiring are the same. Our `0001` (retimer 1 reset pinctrl) is an
   addition the reference does not have, and the reference still reports the
   ports working.
5. **hamoa.dtsi.** The only USB-adjacent differences are (a) v7.3 adds
   interconnect votes on `usb_1_ss0` (`hamoa.dtsi:5274`) that the reference
   lacks, and (b) the reference carries extra `no-map` reserved regions
   (`usb_ucsi_shared_mem@81f20000` and others) that v7.3 does not.
   Device `iomem` (M8) shows EFI already reserves `81f00000-81f37fff`, so (b) is
   covered by the firmware memory map. (a) only adds bandwidth votes and was
   absent on port 1, which also failed in M5. Neither is a credible SS fix.
6. **Reference status text.** The Arch project README rates USB3 "Partially:
   USB-C ports are working" and DP alt mode "working". It does not claim
   SuperSpeed in both orientations, and it names no USB-C patch.

## What this means for the M8 failure

Same code and same DT already run on the reference with USB-C working, so the
M8 symptom (port 0 reversed, 480M, SS in RxDetect, retimer supplies on) is not
explained by a missing reference patch. The remaining differences are outside
the kernel source we can compare:

| Candidate | Grade | How it is settled |
|:--|:--|:--|
| Reverse orientation is a genuine upstream gap in the PS883x/QMP/PAN path; reference works in normal orientation only | Hypothesis | Test the same stick in both orientations in one boot |
| Cable or enclosure is not SuperSpeed (M8 partner is USB 2.10, no PD) | Hypothesis | Known USB3 cable and device; `lsusb -v` bcdUSB and `speed` of the partner |
| Arch kernel `.config` or userspace (systemd-boot UKI, module loading order) differs | Hypothesis | Not visible from the reference sources; compare `/proc/config.gz` symbols below |
| Retimer reset/probe transient (README F2/Q6) | Hypothesis, unchanged | M9 `usbdbg` trace from patch `0002` |
| PAN notification never delivers `USB3_ONLY`, or orientation disagrees with GPIO | Hypothesis, unchanged | M9 trace |

Patch `0002` (diagnostic logging) remains the right next step; this comparison
adds no behavioral patch to it.

## Patches

None added. `hardware/usb-typec/patches/` still contains `0001` (integrated) and
`0002` (diagnostic, in `kernel/series`). No `Assisted-by` patch, `git apply
--check`, `checkpatch` or `dt-validate` run applies because no patch was
produced.

## Not verifiable without hardware

- Whether the reference actually trains SuperSpeed in reverse orientation.
- Whether PAN delivers `USB3_ONLY` on our unit, and in which orientation.
- Whether the SS PHY reaches `U0` once the retimer reports connection.
- Anything about the Arch kernel config; no config file is in the reference
  repositories.

## Read-only collector commands for the next boot

Boot `SP11 debug, USB + DSP trace` (`sp11.entry=usbdbg`) with patch `0002`.
Run with the same stick in port 0 normal, port 0 reversed, port 1 normal, port 1
reversed, each after a fresh boot or a full unplug of 5 s. Replace `X` with the
port. None of these writes to hardware or to debugfs controls.

```bash
# kernel configuration relevant to this path
zcat /proc/config.gz | grep -E 'CONFIG_(TYPEC_MUX_PS883X|TYPEC_UCSI|UCSI_PMIC_GLINK|QCOM_PMIC_GLINK|DRM_AUX_HPD_BRIDGE|PHY_QCOM_QMP_COMBO|PHY_QCOM_EUSB2_REPEATER|USB_DWC3_QCOM|USB_XHCI_PLATFORM|DEBUG_INFO_BTF)='

# Type-C state and partner capability
for p in /sys/class/typec/port*; do echo "== $p"; grep -H . $p/{data_role,power_role,orientation,usb_capability,power_operation_mode} 2>/dev/null; done
for p in /sys/class/typec/port*-partner; do echo "== $p"; grep -H . $p/{accessory_mode,supports_usb_power_delivery} 2>/dev/null; ls $p; done

# USB speeds and root hubs
grep -H . /sys/bus/usb/devices/*/{speed,version,product} 2>/dev/null | grep -v serial
lsusb -t

# xHCI port link states (debugfs read-only; skip any test_* files elsewhere)
for f in /sys/kernel/debug/usb/xhci/*/ports/port*/portsc; do echo "$f: $(cat $f)"; done 2>/dev/null

# Orientation pins, retimer reset and supplies
grep -E 'gpio(121|123|170|175|176|186|188) ' /sys/kernel/debug/gpio
grep -E 'RTMR|l15b' /sys/kernel/debug/regulator/regulator_summary

# Patch 0002 successful-path trace (pmic_glink_altmode and ps883x), plus PHY lines
dmesg | grep -E 'pmic_glink_altmode|ps883x|qmp|combo|ucsi|typec' | cut -c1-200

# Binding state
for d in /sys/bus/i2c/devices/*-0008 /sys/bus/auxiliary/devices/pmic_glink.*; do [ -d "$d" ] || continue; printf '%s driver=' "${d##*/}"; [ -L "$d/driver" ] && readlink "$d/driver" || echo unbound; done
```

Decode the trace with test-plan section F: compare PAN orientation (0 normal, 1
reverse), the Linux orientation enum (1 normal, 2 reverse), and the requested
PS8830 status tuple (expected `21/00/00` normal, `23/00/00` reverse for plain
USB3). If PAN never reports `USB3_ONLY`, the failure is in the ADSP path; if it
does and the tuple is correct yet SS stays in RxDetect, the QMP PHY or the cable
is next.
