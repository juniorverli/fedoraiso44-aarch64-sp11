# Q1/Q2 independent cross-check reconciliation

Compared the existing dossier with
`git show main:hardware/display-lcd/crosscheck/claude-2026-10-24.md`
(Git blob `b507e8d4c0b02f6b10f230a27d203b0b7e7a065b`). The cross-check is
read-only and is not copied or edited here. This session re-read the pinned
data and Linux source; the completed independent PEP trace is cited as such,
without claiming a new REA run.

Input aliases IDP, CRD, INF, DSDT and PEP refer to the full paths and SHA-256
values in [Windows evidence](2026-10-24-windows-backlight.md). Additional
catalogued text inputs re-read here:

| Alias | Path under `sources/windows/` | SHA-256 |
|:--|:--|:--|
| Registry | `live-inventory/panel/gpu-class-key.txt` | `4cb8a9c2a2a8233512c2951549bf5de369d37f89d3d76255807e54ad3e6ed81a` |
| ROM0 | `live-inventory/panel/gpu0-rom-0.xml` | `f3195d2116a0f43ae11a28d8899f11bcf81d144b62c1c88d226ea0bd151901ba` |

## Agreement and differences

| Value | Reconciled answer / grade | Comparison and source resolution |
|:--|:--|:--|
| Selected blob | DENidp, **Verified** | Agree. INF line 63 / 132; Registry `AcpiExtFile` confirms the exact IDP blob. |
| Method | External PMIC PWM, **Inference (strong)** | Agree. IDP adds the three PMIC GPIO records, versus only the enable in CRD. AUX capability remains TBD until DPCD; PWM wiring and AUX capability can coexist. |
| PWM pin / enable / supply | PMK8550 GPIO5 func3; PMC8380_3 GPIO4 / GPIO10, **Inference** | Agree on mapping. Raw IDP records 0x16e7 / 0x1656 / 0x15c5 are Verified; zero-based Windows indices and field meanings remain Inference. No voltage is added. |
| Linux PWM channel | Proposed index 0, **Hypothesis** | Confidence differs: previous dossier called it strong Inference from the exact-board posted patch; cross-check found no channel number in Windows. Downgrade under protocol §5.1. Linux's channel-0 base 0xe800 is Verified (`sources/linux/drivers/leds/rgb/leds-qcom-lpg.c:1814`), but that alone does not establish this board's routing. Hold 0003; obtain device PWM/routing evidence or a direct PMIC mapping trace. |
| Requested period | 5000000 ns / 200 Hz, **Inference** | Agree numerically. The exact-board posted patch supports the proposal; ROM0's matching frequency at line 81 is a reference-panel value, not a measurement of LGD077B. |
| Actual Windows resolution | **TBD** | Disagree with treating 12 bits as this panel's resolution. ROM0 line 4 names B133HAN05.3; line 80 declares 12 bits for that reference. No proof that this unit selects that template. Retain TBD for the actual panel; Linux selects its own resolution from subtype/period (`sources/linux/drivers/leds/rgb/leds-qcom-lpg.c:417`, `:452`). |
| DELAY list | G0MD, FSTATE 1 **ENTER**, power-down | Agree after interpreting the list name. Raw list identity is Verified; direction is Inference from zero rail votes and parked GPIOs versus nonzero EXIT votes. It is not a panel power-up delay. Source details below. |
| DELAY unit / amount | **Verified 500 ms Windows wait**, from independent REA | Cross-check resolves the previous unit TBD: PEP executor `FUN_140128170`, evidence below. |
| T12 relationship | **Inference**, compatible with off dwell | Agree with that limited interpretation. The wait occurs during GPU power-down after the panel supply pin is parked. Neither a panel specification nor a complete timing diagram has been recovered. |
| T3 / T8 / T9 / T10 | Panel requirements **TBD** | Agree: pin configuration and timing key names do not recover these requirements. No DELAY in the IDP G0MD power-up list. |
| Linux LGD fallback | `hpd_absent=200`, `unprepare=500`, `enable=200`, `disable=200` ms, **Verified source**; applicability **Inference** | Cross-check's final sentence instead calls them HPD reliable/absent 200/500. The initializer at `sources/linux/drivers/gpu/drm/panel/panel-edp.c:1853` resolves it: no `hpd_reliable` initializer, 500 belongs to `unprepare`. Patch 0001 uses the unchanged family profile. |

The independent read reproduces Q1/Q2 pins and the sequence; it is not an
independent EDID decode or direct proof of LPG channel routing. Component
status stays `designed` while backlight gating and panel requirements remain.

## Which power list holds the delay

Re-ran `python3 hardware/display-lcd/tools/decode-static.py` and inspected
selected parsed records, without disassembling these catalogued data blobs.
All offsets in this table refer to IDP, SHA-256
`581d11553cc9961da63b301ee81228f9495acad16983218b45d6329b1982fa47`.

| List / record | Verified content |
|:--|:--|
| G0MD FSTATE 1 ENTER, 0x0bc0 | Zero LDO2_J / LDO3_J votes (records 0x0e64 / 0x0eee), TLMM70 parked at 0x0f78, DELAY integer 500 at 0x0fd5, TLMM119 parked at 0x0ff3, PMIC pins set as inputs at 0x1050 / 0x10c8 / 0x1140. |
| G0MD FSTATE 1 EXIT, 0x11b8 | LDO2_J / LDO3_J voltage integers 1256000 / 880000 at 0x1437 / 0x14c1, TLMM70 high at 0x150b, HPD mux at 0x1568, PMIC digital outputs at 0x15c5 / 0x1656 / 0x16e7; no DELAY in this list. |

**Inference:** zero votes and GPIO parking identify ENTER as power-down;
restored rail votes and outputs identify EXIT as power-up. The corresponding
DSDT IDP1 FSTATE EXIT sequence also enables rails/clocks and these GPIOs
(DSDT SHA in Windows evidence, lines 4898–5234). Entering a low-power state
and enabling a component are opposite directions; the old literal `ENTER`
label did not mean power-up.

For the unit, the cross-check used PEP
`sources/windows/DriverStore/qcpep.wd8380.inf_arm64_eb671871f8fef501/qcpep8380.sys`,
SHA-256 `e5bdeb8c0fb8823990f7520a19c00807711cf909f91f8d67db78ffb18c1b2277`,
catalog row 476, `AARCH64:LE:64:v8A`. Its executor `FUN_140128170` converts
the node integer to microseconds by multiplying by 1000 for
`KeStallExecutionProcessor`; evidence_id
`ev_bcb8b29ca707b96c265cdb35655a0ae1f184eed1f63d8b1150bf4f1b54978dd6`.
The dispatcher is `FUN_140400f20`, evidence_id
`ev_ae628ab49279aea8cddc3561eaeb07f1e94070ccad3cab600a70b13bbb366b6e`.
Thus milliseconds are **Verified by independent REA**. The active PEP
version and the older PEP copy's behavior remain **TBD**, as in the cross-check.

## New risk and integration gate

**Verified source behavior:** `sources/linux/drivers/pinctrl/qcom/pinctrl-spmi-gpio.c:323`
rejects func3/func4 for `!pad->lv_mv_type`, returning `-EINVAL`. The diagnostic
literally says `LV/MV subtype doesn't have func3/func4`, despite the condition
rejecting **non-LV/MV** pads. Subtype comes from a hardware register read at
`:866`; the LV/MV cases set the flag at `:883`–`:903`.

**TBD hardware:** PMK8550 GPIO5's subtype on this unit is unknown offline.
Other boards requesting the same mux do not prove this unit's pad type.
**Inference risk:** an unsupported subtype makes the requested backlight
pinctrl fail and may leave the panel dark.

First integration: **0001 + 0002 only**. Patch **0003 stays held** pending M2
logs establishing GPIO5's pad subtype and panel DPCD backlight capabilities;
then review the channel hypothesis and the requested PWM configuration.
Do not release 0003 merely because no pinctrl error occurred when it was
absent. Pinctrl debugfs prints decoded configuration, not the raw subtype
(`sources/linux/drivers/pinctrl/qcom/pinctrl-spmi-gpio.c:658`). Request a
narrow boot diagnostic of the existing subtype read from the kernel owner;
do not unbind/rebind the PMIC or write registers to obtain this evidence.
