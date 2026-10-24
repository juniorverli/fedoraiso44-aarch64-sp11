# display-lcd

## 1. Summary

The internal LCD is an LG Display LP129WT342166 (`LGD`, product `0x077b`) on MDSS DP3/eDP, with native 2880×1920 modes at approximately 120 and 60 Hz. Status: `designed`: three uncommitted patches are prepared; PWM wiring is a strong Inference, panel timing requirements and the independent runtime cross-check remain open.

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
| PWM output | PMK8550 GPIO5 / func3, Linux LPG PWM index 0 | Inference (strong) | Windows evidence: IDP 0x16e7 + exact-board patch |
| PWM period | Requested 5000000 ns (200 Hz) | Inference (strong) | Exact-board patch, linked and hashed in Windows evidence |
| PWM resolution | Actual Windows value TBD; Linux selects according to subtype and period | TBD / Verified Linux behavior | `sources/linux/drivers/leds/rgb/leds-qcom-lpg.c:452`; reference XML's 12 bits are not this unit's evidence |
| Backlight enable | PMC8380_3 GPIO4, active high | Inference (strong) | IDP 0x1656 + exact-board patch |
| Backlight supply enable | PMC8380_3 GPIO10, active high; supply voltage unknown | Inference (strong) / TBD voltage | IDP 0x15c5 + exact-board patch; DT does not invent a voltage |

The existing common DTS incorrectly assigns GPIO4 to LCD panel enable. Patch 0003 moves it to the LCD backlight while preserving the OLED panel enable in its DTS. The reference `_ROM` XML describes B133HAN05.3/SDC14OLED, not LP129WT342166, and cannot verify the LCD's Windows PWM resolution or timing requirements.

## 3. Windows

| Package | Observed role / boundary |
|:--|:--|
| `qcdx8380` / `qcdxkm8380.sys` | Qualcomm display/GPU driver; contains backlight and eDP timing parser keys. REA procedure inventory and timing-key trace are recorded in power evidence; timing requirements are not recovered yet. |
| `surface_dxext_8380` | INF selects DENidp for this unit's IDP08380/REV_008A; serialized ACPI method overrides contain the display pin/rail setup. DENcrd has a different pin sequence. |
| `qcpep.wd8380` / `qcpep8380.sys` | PEP resource/IOCTL framework; target for delay-unit and GPIO-enum interpretation. |
| `surfaceoempanelcustomizationlcd` | Monitor INF for LGD077B and calibration data (not treated as a power-sequence source). |
| `surfacepaneldriver`, `surfacedisplayhardwaredriver`, `surfacesmfdisplayclient` | Panel/brightness/TCON/SMF stack; their necessity for basic scanout remains unverified. |
| `surfacetconwifionlylcd` | TCON firmware package; never flashed by this work (S3). |
| `qcdpps8380`, `surface_dppsext_8380` | Display post-processing packages; not used to derive GPIOs. |

Input hashes, offsets, method selection and blob format are in Windows evidence. Decompiled output and REA snapshots remain under `out/rea/display-lcd/`, outside git.

## 4. Linux 7.3

- `sources/linux/drivers/gpu/drm/panel/panel-edp.c:944` tries AUX backlight only when no explicit backlight exists. The LCD DT now proposes an explicit PWM backlight.
- The base lacks LGD 0x077b; the related LP129WT232166 uses the common LGD profile at `sources/linux/drivers/gpu/drm/panel/panel-edp.c:2188`. Patch 0001 adds the identity with those provisional family delays; EDID still supplies both modes.
- `sources/linux/drivers/gpu/drm/panel/panel-edp.c:1853` defines the proposed 200/500/200/200 ms profile. It is not a recovered LP129WT342166 datasheet specification.
- DP3, its panel port and PHY are enabled at `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi:893`, `:930`. Patch 0002 applies the existing HPD state.
- PMK8550 PWM is disabled by default at `sources/linux/arch/arm64/boot/dts/qcom/hamoa-pmics.dtsi:275`. Its index 0 maps to base 0xe800 in `sources/linux/drivers/leds/rgb/leds-qcom-lpg.c:1814`.
- `pwm_bl` supplies a default CIE1931 brightness table at `sources/linux/drivers/video/backlight/pwm_bl.c:182`; no guessed Windows duty table is added.

The 2026-10-17 posted Denali HPD/backlight series is the source of patches 0002/0003. See Windows evidence for message links, mirror hashes, attribution and source-pinning request. No claim that the series is merged upstream is made.

## 5. Gaps

| Gap | Current answer |
|:--|:--|
| Missing panel identity | Patch 0001; provisional LGD-family delays, pending timing evidence and cross-check |
| HPD state not applied | Patch 0002, adapted from exact-board upstream submission |
| LCD PWM backlight / GPIO4 ownership | Patch 0003, adapted from exact-board upstream submission; Q1 strong Inference meets this session's drafting threshold |
| Actual panel power timings | Still open: see [power evidence and fallback rationale](evidence/2026-10-24-power-timing.md) |
| DPCD / negotiated link never observed | Read-only collector and exact future-device commands in `test-plan.md` |
| No independent reproduction of patch values | Orchestrator must start the other-runtime cross-check before `sw-ready` |
| Full integrated build / device behavior | Kernel and image owners integrate after review; no device tests run here |

## 6. Open questions

| # | Question | Grade / current answer | What answers it |
|:--|:--|:--|:--|
| Q1 | AUX or PMIC PWM; wiring, frequency, resolution? | **Inference (strong):** PMK8550 PWM index 0, GPIO5 func3, requested 200 Hz; PMC8380_3 GPIO4 enable, GPIO10 supply. Windows resolution **TBD**. | Independent interpretation of IDP offsets/PEP enums; Windows runtime configuration or PMIC state for resolution; DPCD for caps |
| Q2 | T3, T8, T9, T10, T12? | **TBD hardware requirements**; common LGD delay profile is an explicitly provisional **Inference** | Trace timing destination globals/initialization in DX and PEP DELAY units; panel timing specification or device sequencing evidence |
| Q3 | DPCD revision, maximum rate, lanes, PSR, backlight capabilities? | TBD | `tools/collect-dpcd.py`, ranges 0x000–0x0ff and 0x700–0x7ff |
| Q4 | 120 Hz at 10 bpc? | **Inference:** both EDID modes need four HBR3 lanes at 10 bpc; both nominally fit four HBR2 at 8 bpc | DPCD and active link/bpp logs; 60 Hz has the same pixel clock |
| Q5 | Firmware framebuffer → MSM → GDM handover stable? | TBD | Future M2 logs and visible picture |
| Q6 | TCON/Windows panel-stack action needed for basic picture? | TBD | Future M2; focused panel driver analysis if needed, without firmware writes |

## 7. Acceptance

Use [test-plan.md](test-plan.md). On the device, preserve logs proving connected eDP, both native refresh modes, successful link training, stable framebuffer handover and GDM, monotonic brightness with a visible minimum user level, and ten minutes at 120 Hz plus switching to 60 Hz and back. Suspend is out of scope. No device acceptance result is claimed in this session.

## 8. Requests

- orchestrator: independently reproduce EDID timing/depth fields, IDP/CRD selection and pin mappings, PWM channel/period, HPD mux and the provisional panel delays on the other runtime (protocol §5.1). Keep status below `sw-ready` until this is complete; Q2 remains open.
- sources: pin the 2026-10-17 `sp11-lcd-fixes-v1` messages (IDs and hashes in Windows evidence) before integrating patches 0002/0003. Lore raw access returned HTTP 403; the original messages were read through the Openwall archive mirror.
- kernel: review/apply `patches/0001`–`0003` in order; retain BTF and BTF_MODULES=y, panel-edp/pwm_bl/leds-qcom-lpg modules, and enable `CONFIG_DRM_DP_AUX_CHARDEV` for evidence collection. Perform the full integrated kernel/module/BTF build; this worker's object compile is not a full image build.
- image: include `tools/collect-dpcd.py` and run it as root against all `/dev/drm_dp_aux*` adapters into persistent logs. Record sysfs ancestry, short reads and errors; collect DPCD 0x000–0x0ff / 0x700–0x7ff, eDP debug files, DRM state, PWM/backlight state, pinctrl and regulator summaries. Exact commands and expected observations are in `test-plan.md`.

## 9. Log

- 2026-10-23: dossier created from the static survey; EDID base block decoded.
- 2026-10-24: decoded all declared EDID/DisplayID blocks and capture padding; decoded DENidp/DENcrd ACPI argument containers; correlated backlight/HPD pins with DSDT and exact-board posted patches; drafted three patches, checked style and replay, compiled panel object with BTF options enabled; timing requirements and independent cross-check remain open. Changes intentionally uncommitted per session instructions.
