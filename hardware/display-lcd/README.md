# display-lcd

## 1. Summary

The internal LCD is an LG Display LP129WT342166 (`LGD`, product `0x077b`) on MDSS DP3/eDP, with native 2880×1920 modes at approximately 120 and 60 Hz. Status: `designed`: patches 0001/0002 passed the panel object build and CHECK_DTBS validation for first integration; patch 0003 remains held for M2 pad-subtype/DPCD evidence, with the Q1/Q2 independent cross-check reconciled.

## 2. Hardware

Every EDID value is cited by offset and SHA-256 in [EDID evidence](evidence/2026-10-24-edid.md); every Windows pin/configuration value is cited in [Windows/backlight evidence](evidence/2026-10-24-windows-backlight.md).

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Panel identity | LGD / 0x077b, LP129WT342166 | Verified | EDID evidence, bytes 0x08–0x0b, 0x6c descriptor |
| Capture structure | 384 captured bytes, 256 declared EDID bytes; final 128 bytes are zero padding | Verified | EDID evidence, 0x7e and 0x100–0x17f |
| Input / transport depth | DisplayPort RGB, base 10 bpc; DisplayID interface supports 8/10 bpc | Verified declarations | EDID evidence, 0x14 and block 0xc1 |
| Internal color depth | DisplayID declares native 12 bpc; not a 12-bpc transport claim | Verified declaration | EDID evidence, block 0xa1 |
| Native / refresh modes | 2880×1920 at 120.000168 and 60.000084 Hz | Verified | EDID evidence, 0xd0 and 0xe4 |
| Pixel clock | 715.201 MHz for **both** refresh modes | Verified | same; 60 Hz doubles vertical total to 4000 |
| Size | DisplayID 274×183 mm; base rounded 270×180 mm | Verified | EDID evidence |
| Controller | DP3/eDP, four lanes; DT permits rates through HBR3 | Verified DT configuration | `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:893`, `:920` |
| Panel logic supply | `vreg_edp_3p3`, TLMM GPIO70, 3.3 V | Verified existing DT; Windows pin corroborated | same `:128`; IDP offset 0x150b in Windows evidence |
| HPD | TLMM GPIO119, `edp0_hot` | Inference (strong, board mux) | Windows evidence, IDP 0x1568; `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:6110` |
| Backlight method | External PMIC PWM | Inference (strong) | Windows evidence: IDP/CRD difference + exact-board posted, LCD-tested patch |
| PWM pin | PMK8550 GPIO5 / func3 | Inference (strong); pad subtype TBD | Windows evidence: IDP 0x16e7 + exact-board patch; [cross-check reconciliation](evidence/2026-10-24-crosscheck-reconciliation.md) |
| PWM channel | Proposed Linux LPG PWM index 0 | Hypothesis after cross-check | Windows does not name a channel; Linux index mapping alone cannot prove routing; reconciliation |
| PWM mux support | func3 requires an LV/MV pad; this unit's GPIO5 subtype is unknown offline | Verified driver requirement / TBD hardware | `sources/linux/drivers/pinctrl/qcom/pinctrl-spmi-gpio.c:323`, `:866`; reconciliation |
| PWM period | Requested 5000000 ns (200 Hz) | Inference (strong) | Exact-board patch, linked and hashed in Windows evidence |
| PWM resolution | Actual Windows value TBD; Linux selects according to subtype and period | TBD / Verified Linux behavior | `sources/linux/drivers/leds/rgb/leds-qcom-lpg.c:452`; reference XML's 12 bits are not this unit's evidence |
| Backlight enable | PMC8380_3 GPIO4, active high | Inference (strong) | IDP 0x1656 + exact-board patch |
| Backlight supply enable | PMC8380_3 GPIO10, active high; supply voltage unknown | Inference (strong) / TBD voltage | IDP 0x15c5 + exact-board patch; DT does not invent a voltage |

The proposed interpretation assigns GPIO4 to LCD backlight enable, whereas the existing common DTS assigns it to panel enable. Held patch 0003 would move it to the backlight while preserving the OLED panel enable in its DTS. The reference `_ROM` XML describes B133HAN05.3/SDC14OLED, not LP129WT342166, and cannot verify the LCD's Windows PWM resolution or timing requirements.

## 3. Windows

| Package | Observed role / boundary |
|:--|:--|
| `qcdx8380` / `qcdxkm8380.sys` | Qualcomm display/GPU driver; contains backlight and eDP timing parser keys. REA procedure inventory and timing-key trace are recorded in power evidence; panel-specific requirements remain unknown. |
| `surface_dxext_8380` | INF selects DENidp for this unit's IDP08380/REV_008A; serialized ACPI method overrides contain the display pin/rail setup. DENcrd has a different pin sequence. |
| `qcpep.wd8380` / `qcpep8380.sys` | PEP resource/IOCTL framework; independent REA establishes milliseconds for DELAY. The IDP 500 ms record is in power-down ENTER, after the panel supply pin is parked; relation to panel T12 is Inference. |
| `surfaceoempanelcustomizationlcd` | Monitor INF for LGD077B and calibration data (not treated as a power-sequence source). |
| `surfacepaneldriver`, `surfacedisplayhardwaredriver`, `surfacesmfdisplayclient` | Panel/brightness/TCON/SMF stack; their necessity for basic scanout remains unverified. |
| `surfacetconwifionlylcd` | TCON firmware package; never flashed by this work (S3). |
| `qcdpps8380`, `surface_dppsext_8380` | Display post-processing packages; not used to derive GPIOs. |

Input hashes, offsets, method selection and blob format are in Windows evidence. Decompiled output and REA snapshots remain under `out/rea/display-lcd/`, outside git.

## 4. Linux 7.3

- `sources/linux/drivers/gpu/drm/panel/panel-edp.c:944` tries AUX backlight only when no explicit backlight exists. First integration leaves that behavior intact; only held patch 0003 proposes an explicit PWM backlight.
- The base lacks LGD 0x077b; the related LP129WT232166 uses the common LGD profile at `sources/linux/drivers/gpu/drm/panel/panel-edp.c:2188`. Patch 0001 adds the identity with those provisional family delays; EDID still supplies both modes.
- `sources/linux/drivers/gpu/drm/panel/panel-edp.c:1853` defines the proposed 200/500/200/200 ms profile. It is not a recovered LP129WT342166 datasheet specification.
- DP3, its panel port and PHY are enabled at `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:893`, `:930`. Patch 0002 applies the existing HPD state.
- PMK8550 PWM is disabled by default at `sources/linux/arch/arm64/boot/dts/qcom/hamoa-pmics.dtsi:275`. Its index 0 maps to base 0xe800 in `sources/linux/drivers/leds/rgb/leds-qcom-lpg.c:1814`.
- `pwm_bl` supplies a default CIE1931 brightness table at `sources/linux/drivers/video/backlight/pwm_bl.c:182`; no guessed Windows duty table is added.
- `sources/linux/drivers/pinctrl/qcom/pinctrl-spmi-gpio.c:323` rejects func3/func4 on non-LV/MV pads. GPIO5's subtype must be established on M2 before 0003 is used; ordinary pinctrl debugfs does not print the raw subtype (`:658`).

The 2026-10-17 posted Denali HPD/backlight series is the source of patches 0002/0003. See Windows evidence for message links, mirror hashes, attribution and source-pinning request. No claim that the series is merged upstream is made.

## 5. Gaps

| Gap | Current answer |
|:--|:--|
| Missing panel identity | Patch 0001 for first integration; object compile passed, provisional LGD-family delays retained |
| HPD state not applied | Patch 0002 for first integration, adapted from exact-board submission; CHECK_DTBS passed |
| LCD PWM backlight / GPIO4 ownership | Patch 0003 held: M2 pad subtype + DPCD backlight caps first, then review PWM/channel evidence |
| Actual panel power timings | Windows power-down wait is Verified 500 ms; T12 relationship Inference, T3/T8/T9/T10 requirements TBD; [power evidence](evidence/2026-10-24-power-timing.md) |
| DPCD / negotiated link never observed | Read-only collector and exact future-device commands in `test-plan.md` |
| Independent reproduction | Q1/Q2 pins/method/sequence agree; channel downgraded to Hypothesis, actual 12-bit resolution unsupported, LGD fallback field labels corrected from Linux source; [comparison](evidence/2026-10-24-crosscheck-reconciliation.md). EDID was outside this cross-check's scope. |
| Full integrated build / device behavior | Kernel and image owners integrate after review; no device tests run here |

## 6. Open questions

| # | Question | Grade / current answer | What answers it |
|:--|:--|:--|:--|
| Q1 | AUX or PMIC PWM; wiring, frequency, resolution? | **Inference (strong):** GPIO5 func3, requested 200 Hz; PMC8380_3 GPIO4 enable, GPIO10 supply. PWM channel 0 **Hypothesis**; Windows resolution and GPIO5 subtype **TBD**. | M2 explicit subtype + DPCD evidence gates 0003; channel routing/device PWM evidence, PMIC enums and actual resolution remain open |
| Q2 | T3, T8, T9, T10, T12? | **Verified 500 ms Windows power-down wait**; T12 relation / LGD fallback **Inference**; panel-specific requirements **TBD** | DX timing destination/default trace, panel specification or device sequencing evidence; no repeat of the completed PEP DELAY-unit trace needed |
| Q3 | DPCD revision, maximum rate, lanes, PSR, backlight capabilities? | TBD | `tools/collect-dpcd.py`, ranges 0x000–0x0ff and 0x700–0x7ff |
| Q4 | 120 Hz at 10 bpc? | **Inference:** both EDID modes need four HBR3 lanes at 10 bpc; both nominally fit four HBR2 at 8 bpc | DPCD and active link/bpp logs; 60 Hz has the same pixel clock |
| Q5 | Firmware framebuffer → MSM → GDM handover stable? | TBD | Future M2 logs and visible picture |
| Q6 | TCON/Windows panel-stack action needed for basic picture? | TBD | Future M2; focused panel driver analysis if needed, without firmware writes |

## 7. Acceptance

Use [test-plan.md](test-plan.md). First boot 0001/0002 to collect subtype, DPCD, link and handover evidence; after review releases 0003, require connected eDP, both native refresh modes, successful link training, stable framebuffer handover and GDM, monotonic brightness with a visible minimum user level, and ten minutes at 120 Hz plus switching to 60 Hz and back. Suspend is out of scope; no device test has been run.

## 8. Requests

- orchestrator: review and commit these uncommitted changes on `worker/display-lcd`. First integration is **0001/0002 only**; hold 0003 until M2 GPIO5 subtype and DPCD backlight caps are reviewed, then resolve channel-0 confidence before release. Q1/Q2 comparison is recorded; EDID timing/depth reproduction on the other runtime remains requested (protocol §5.1). Request a `plan/risks.md` entry for the func3 subtype/dark-panel risk; this worker cannot edit plan files.
- sources: pin the 2026-10-17 `sp11-lcd-fixes-v1` messages (IDs and hashes in Windows evidence) before integrating patches 0002/0003. Lore raw access previously returned HTTP 403; original messages were read through the Openwall archive mirror.
- kernel: integrate only 0001/0002 for M2; retain BTF and BTF_MODULES=y and panel-edp/pwm_bl/leds-qcom-lpg availability, enable `CONFIG_DRM_DP_AUX_CHARDEV`, and perform the full integrated kernel/module/BTF build. Provide a narrow boot diagnostic logging PMK8550 GPIO5's subtype from the existing successful `PMIC_GPIO_REG_SUBTYPE` read (`pinctrl-spmi-gpio.c:866`), or equivalent explicit read-only evidence. Pinctrl debugfs and absence of an error with 0003 absent do not establish the subtype.
- image: include `tools/collect-dpcd.py`; run it as root against all AUX adapters into persistent logs, retaining ancestry/errors. Capture DPCD 0x000–0x0ff / 0x700–0x7ff, subtype diagnostic, eDP link/DRM/PWM/backlight/pinctrl/regulator summaries. Do not add 0003 before this evidence is reviewed. Exact collection and acceptance commands are in `test-plan.md`.

## 9. Log

- 2026-10-23: dossier created from the static survey; EDID base block decoded.
- 2026-10-24: decoded all declared EDID/DisplayID blocks and capture padding; decoded DENidp/DENcrd ACPI argument containers; correlated backlight/HPD pins with DSDT and exact-board posted patches; drafted three patches, checked style and replay, compiled panel object with BTF options enabled; timing requirements and independent cross-check remain open. Changes intentionally uncommitted per session instructions.
- 2026-10-24 (resumed): removed AI-added operator DCO sign-offs, added `Assisted-by: Codex gpt-6.1-sol`; reconciled Q1/Q2 with the Claude cross-check, identified ENTER as power-down with a 500 ms wait, corrected fallback field labels, held 0003 for pad-subtype/DPCD evidence, and build-tested 0001/0002 with CHECK_DTBS in Fedora 44. Final validation and exact commands are in `evidence/2026-10-24-build-validation.md`; changes left uncommitted for orchestrator review.
