# Double-flip claim: verification and verdict (2026-10-31)

Claim under test: `evidence/2026-10-31-rea-double-flip.md` sections 1.2 and 6 (single analyst, Gemini REA report). Method: Linux v7.3 source plus the full `kernel/series` rev 12 (scratch tree `out/linux/m15-verify`), the Windows ACPI dump, the private M13/M14/M14b logs, and the upstream commit history (GitHub API; lore.kernel.org is blocked by an anti-bot page from this host). REA was not used. Grades: Verified, Inference, Unknown.

## Verdict: PLAUSIBLE-UNPROVABLE (low prior). The mechanism exists as described; the premise that it is a defect is contradicted by upstream boards with the same topology.

## 1. Verified

| # | Fact | Source |
|:--|:--|:--|
| V1 | `ps883x_sw_set()` calls `typec_switch_set(retimer->typec_switch, orientation)` first, then sets or clears `CONN_STATUS_0_ORIENTATION_REVERSED`. So a reverse attach flips the PHY (when it is a registered switch) and the retimer | `drivers/usb/typec/mux/ps883x.c:273-307` |
| V2 | `ps883x_set()`/`ps883x_configure()` do not depend on whether a PHY switch exists; the register tuple comes from `retimer->orientation` and the mode only | `ps883x.c:194-270`, `147-192` |
| V3 | Without `orientation-switch` on the PHY, `typec_switch_get()` returns NULL (not an error) and `typec_switch_set(NULL)` returns 0, so the retimer probes and works without a downstream switch | `drivers/usb/typec/mux.c:94-101`, `222-223`; `ps883x.c:413-416` |
| V4 | The PHY registers a typec switch AND a typec mux when `mode-switch` OR `orientation-switch` is present. The retimer finds the PHY switch only through the `orientation-switch` property of the PHY node (`typec_switch_match`, mux.c:50) and the PHY mux through `mode-switch` | `phy-qcom-qmp-combo.c:5252-5256`, `4903-4930`; `mux.c:35-71` |
| V5 | PHY orientation defaults to NORMAL; `SW_PORTSELECT_VAL` is written only for REVERSE; the switch callback ignores NONE and repeats | `phy-qcom-qmp-combo.c:5214`, `4064-4072`, `4776-4786` |
| V6 | `hamoa.dtsi` has `mode-switch` and `orientation-switch` on all three PHYs; Denali has `orientation-switch` on both retimers; the graph is PHY out -> retimer `port@1` -> retimer `port@0` -> pmic-glink `ss_in`, identical to the CRD | `hamoa.dtsi:2852-2853`, `2923-2924`, `2994-2995`; `x1-microsoft-denali.dtsi:1066`, `1084`, `1132`, `1150`; `x1-crd.dtsi:967`, `1025`, `1113`, `1769` |
| V7 | Upstream boards with PS8830 keep BOTH switches on every port that has a retimer (CRD, T14s, Slim 7x, Zenbook A14, Vivobook S15, XPS 13, Omnibook X14, Surface Laptop 7 `x1e80100-microsoft-romulus.dtsi:903,985,1493-1540`). The only `/delete-property/ orientation-switch` lines are on `usb_1_ss2_qmpphy` (DP-only third port, fixed `data-lanes`), never on a retimer port | grep of `arch/arm64/boot/dts/qcom` in v7.3 |
| V8 | The CRD and T14s retimer commits carry `Tested-by: Johan Hovold`; the Surface Laptop 7 commit "Enable DP over Type-C" says both ports work | commits `9db543299ec0`, `b7e331d18cd0`, `781621de1551` (GitHub API) |
| V9 | Device: every notification seen (M13 ports 0 and 1, M14, M14b) has raw orientation 1, which Linux maps to REVERSE; the retimer gets `0x23/00/00`; the PHY mux goes USB3-only. xHCI SS ports stay in RxDetect | M13/M14b `dmesg.txt`, `xhci-ports.txt`; `pmic_glink_altmode.c:403-409` |
| V10 | The v7.3 supplies fix (`vdda-phy` 0.8 V, `vdda-pll` 1.2 V) is already in the Denali DT, so the upstream "swapped supplies" bug is not the cause | `x1-microsoft-denali.dtsi:1660-1664`; upstream `4458dcd382` |

## 2. Findings against the report

- F8 "Verified" is wrong: nothing in the logs shows the PHY lane registers or that the double flip is harmful. The PHY `TYPEC_CTRL` write is not logged (`writel` without dev_dbg), so the PHY orientation on the device is Inference.
- F9 "Windows never flips the PHY" is not Verified. The ACPI copies the ADSP orientation byte into `\_SB.UCS0.ECC0/ECC1` and returns it from `CCVL` on the USB controller children (`dsdt.dsl:846,857,63413-63415,63564-63566,63871-63873`), and `QcXhciFilter8380.sys` contains the string `CCVL`. So the Windows xHCI stack reads the orientation. What it programs with it is Unknown.
- The report states Windows orientation values 1=normal, 2=reverse. The DSDT only copies the byte (`dsdt.dsl:830,846`); no comparison exists there. Linux uses 0=normal, 1=reverse (`pmic_glink_altmode.c:403-409`). If Windows' reading were right, raw 1 would be NORMAL and Linux would set both flips wrongly. Unknown; see test A.
- Statistics: the attaches are few (M13 ports 0 and 1, M14, M14b), all raw 1 with the same stick plugged the same way by the same hand. "Normal never observed" is weak evidence for a systematic effect.
- The upstream topology works with both switches (V7, V8), so the retimer host side behaves as a lane-following element there. The report's model (host side fixed, PHY must not flip) contradicts that. It can hold on the Surface only if the Surface board wiring differs from the CRD, for which there is no data. The Surface Laptop 7 (same OEM, same SoC family) keeps both switches and its USB-C works.
- Seen in M13 port 0: `orientation: 2 -> 0` right after the mux set, restored `0 -> 2` 180 ms later. Something calls the switch with NONE; the PHY ignores NONE (V5) but `ps883x_sw_set()` clears the reversed bit while the partner is attached. Source of the NONE call is Unknown (UCSI path suspected). It may matter for any orientation experiment; read it in the next log.

## 3. What only the hardware can show

1. Test A (no kernel change, first): plug the stick the other way round on each port. Read the `notify:` raw value (0 = normal, 1 = reverse, other = the report's convention would be right), `typec/port*/orientation`, `xhci-ports.txt`. If normal trains SS and reverse does not, the failure is orientation specific (consistent with the claim AND with an orientation mapping error); if neither trains, the double flip is irrelevant.
2. Test B: the variant with patch 0003 on a reverse attach. SS training = claim confirmed. No change = claim refuted (restore old).
3. Test C (only if B fails and A shows reverse only): retimer reversed bit forced off with the PHY flip on (needs a diagnostic patch; not written).

## 4. Decision

PLAUSIBLE-UNPROVABLE. Patch `patches/0003-arm64-dts-qcom-x1p64100-microsoft-denali-drop-the-QMP-.patch` (DT only, LCD board file, `/delete-property/ orientation-switch;` on `usb_1_ss0_qmpphy` and `usb_1_ss1_qmpphy`). Results on `out/linux/m15-verify` (v7.3 plus the 72 series entries): `checkpatch --strict --no-signoff` 0 errors, 0 warnings; `git apply --check` clean; `CHECK_DTBS=y` build of `x1p64100-microsoft-denali.dtb`: no warning, identical to the build without the patch (0 warnings both); `dtc` of the built DTB shows `orientation-switch` only on the two retimers and `mode-switch` kept on both PHYs. A variant that re-adds `orientation-switch` after the delete builds and keeps both properties (so the re-add in `m15-safe` works).

Risk of the change: normal-orientation attaches are unaffected (neither side flips before or after). Reverse-orientation SuperSpeed is already dead on the device, so the variant cannot make observed USB3 worse. USB-C DisplayPort alt mode uses the same PHY orientation to place its lanes (`qmp_combo_com_init`, `phy-qcom-qmp-combo.c:4064-4072`): if the upstream model is right for this board, a REVERSE attach with DP will lose its lanes. No device evidence of DP alt mode on Denali was found in the logs read. Detect: a reverse-attached DP dongle or monitor, `dmesg` `mdss_dp` link training failure and `/sys/class/drm/*DP*/status`, plus the `typec_mux_set: switching from qmpphy mode` line (USB3DP/DP-only expected).

## 5. DTB variant plan

Default `m15` (combined diagnostic) gets the fix; `m15-safe` (automatic fallback) keeps the old behaviour. Reason: the LCD may be dark and USB-C DP is the documented recovery display (risks.md R1); the entry that must keep it working is the fallback, and the unmodified behaviour is known. One boot of each entry with the stick plugged reverse compares both.

- `m15-safe.dts`: re-add `orientation-switch;` in `&usb_1_ss0_qmpphy` and `&usb_1_ss1_qmpphy` (tested to build).
- `m15.dts` includes `m15-safe.dts`: delete them again with `/delete-property/ orientation-switch;` in both nodes.
- `m15-nosnd`, `m15-spk` include `m12.dts` (they inherit the fix); `m15-notouch` includes `m15-safe` (old). Recommend re-adding in nosnd and spk too, so only `m15` differs.

## 6. ps883x.c sequencing hygiene (report section 6.2): not implemented

The proposed 15 ms delay sits in `ps883x_configure()` after the reset line has been asserted for as long as the retimer was idle, so it settles nothing. The probe change from 4 ms to 15 ms is harmless but unjustified: the retimer answers I2C and accepts `0x23/00/00` (V9), and training never starts for seconds, so a short delay cannot be the cause. The Windows delays (15 ms assert, 60 ms release) are already covered by Linux' 60 ms `msleep()` after release (`ps883x.c:168`, `452`). Upstream added a 30 ms post-configure delay for DP hotplug reliability (`d9eadbba6663`, after v7.3's base); it is a DP matter, not an SS-link one. No patch.
