# display-lcd

## 1. Summary

The internal 13" LCD, an LG Display panel (EDID `LGD`, product `0x077B`, name `LP129WT342166`) on the SoC's eDP controller (MDSS DP3). Linux 7.3 has the display pipeline and a generic eDP panel node, but no entry for this panel, no HPD pin mux and no backlight. Status: `survey`.

## 2. Hardware

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| Panel identity | `LGD` / `0x077B`, EDID 1.4 + 1 extension (384 bytes) | Verified | `sources/windows/live-inventory/panel/edid-LGD077B.bin`, SHA-256 `37b722fa103c8ecd8fd14356c0fdad153f9d6b6699dbe7c7b9b4c66f1d3d9e62` |
| Name strings | `LGD_DV1.0_`, `LP129WT342166` (0xFE descriptors) | Verified | same, base block |
| Input | digital, 10 bpc, DisplayPort (byte 20 = `0xB5`) | Verified | same |
| Vertical range | 24 to 120 Hz (range descriptor) | Verified | same |
| Detailed modes | none in the base block; modes are in the extension block | Verified | same |
| Native mode, refresh modes, pixel clock | TBD: decode the DisplayID extension (expected 2880x1920 at 60 and 120 Hz) | TBD | same |
| Controller | MDSS DP3 as eDP, 4 lanes, link rates up to 8.1 Gbit/s in DT | Verified | `sources/linux/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi` (`&mdss_dp3`) |
| Panel supply | `vreg_edp_3p3`, TLMM GPIO 70 | Verified (DT) | same, `regulator-edp-3p3` |
| Panel enable | PMC8380_3 GPIO 4 (`enable-gpios` of the panel) | Verified (DT) | same, `panel` |
| HPD | TLMM GPIO 119, function `edp0_hot` | Verified (pin state exists) | `sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi` (`edp0_hpd_default`) |
| TCON | `MSHW0380`, own firmware capsule 161.33.0.19 (Wi-Fi LCD variant) | Verified | `pnp-present.json`; `Firmware/{82E97D6D-...}/` |
| Backlight method | **TBD** | TBD | §6 Q1 |

The GPU ROM XMLs in `live-inventory/panel/gpu0-rom-*.xml` describe **reference panels** (`B133HAN05.3` with `BacklightType 1`, PMIC PWM 12 bit at 200 Hz; `SDC14OLED` with `BacklightType 5`), not this panel. They are hints for the LCD reference design, not facts about this unit.

## 3. Windows

| Package | Role (to confirm) |
|:--|:--|
| `qcdx8380` (`qcdxkm8380.sys`) | Qualcomm display + GPU kernel driver: eDP link, panel power sequence, backlight |
| `surface_dxext_8380` | Surface extension blobs for `qcdxkm` (`qcdxkmext8380_DEN*.bin`): board-specific panel and backlight configuration |
| `surfaceoempanelcustomizationlcd` | Monitor INF for `LGD077B`, calibration data |
| `surfacepaneldriver` | User-mode panel driver: brightness interface |
| `surfacedisplayhardwaredriver` | `MSHW0380`, talks to the TCON |
| `surfacesmfdisplayclient` | SMF display client |
| `surfacetconwifionlylcd` | TCON firmware capsule (never flashed by us, risk S3) |
| `qcdpps8380`, `surface_dppsext_8380` | Display post-processing service |

## 4. Linux 7.3

- `sources/linux/drivers/gpu/drm/msm/disp/dpu1/catalog/dpu_9_2_x1e80100.h`: DPU catalogue for this SoC.
- `sources/linux/drivers/gpu/drm/msm/dp/`: DP/eDP controller; lowers bpp until a mode fits the link; no VRR.
- `sources/linux/drivers/gpu/drm/panel/panel-edp.c`: generic eDP panel; has `LGD 0x06b2 LP129WT232166` (same family), not `0x077b`.
- `x1-microsoft-denali.dtsi`: `&mdss`, `&mdss_dp3` with `aux-bus/panel` (`compatible = "edp-panel"`), `&mdss_dp3_phy`.

## 5. Gaps

| Gap | Planned answer |
|:--|:--|
| No `panel-edp` entry for `0x077B` | New patch: `EDP_PANEL_ENTRY('L', 'G', 'D', 0x077b, <delays>, "LP129WT342166")`; delays from Windows power sequence (REA of `qcdxkm8380.sys` / `surface_dxext_8380` blobs) |
| HPD pin not muxed | DT patch: `pinctrl-0 = <&edp0_hpd_default>` on `&mdss_dp3` |
| No backlight | Decide on evidence (Q1), then DT patch: either nothing (panel-edp uses DPCD backlight) or `pwm-backlight` on the PMK8550 LPG with the right pins and frequency |
| DPCD unread | Read it on the vanilla boot (M2) |

## 6. Open questions

| # | Question | Grade | What answers it |
|:--|:--|:--|:--|
| Q1 | Backlight: DPCD/AUX or PMIC PWM? Which PMIC, LPG channel, pin, frequency, resolution, enable and supply GPIOs? | TBD | REA of `qcdxkm8380.sys` and the `surface_dxext_8380` blob for the Denali LCD board; DPCD register `0x701`-`0x703` (backlight caps) on the device |
| Q2 | Panel power-on/off delays (T3, T8, T9, T10, T12) | TBD | REA of the panel power sequence; panel-edp default for LGD as fallback |
| Q3 | eDP revision, max link rate, lanes, PSR support | TBD | DPCD `0x000`-`0x00F`, `0x070` on the device |
| Q4 | Does 120 Hz fit at 10 bpc on the link the panel advertises? | Inference pending Q3 | Arithmetic once the pixel clock is decoded |
| Q5 | Does the screen survive the firmware-framebuffer handover (`simpledrm` to `msm`)? | TBD | M2 boot log |
| Q6 | Is anything from the TCON (`MSHW0380`, I2C) needed for a picture? | TBD | REA of `SurfaceDisplayHardwareDriver` |

## 7. Acceptance

On the device, with logs in `evidence/`:

1. `/sys/class/drm/card*-eDP-1/status` is `connected`; `modes` lists 2880x1920 at 120 and 60 Hz.
2. `drm.debug=0x100` shows link training success at the chosen rate.
3. Picture stays on after the firmware framebuffer handover and through a GDM login.
4. `/sys/class/backlight/*/brightness` changes from minimum to maximum visibly, never fully dark at the minimum user level.
5. GNOME runs at 120 Hz for 10 minutes with no flicker or artefact; switching to 60 Hz and back works.
6. Suspend is out of scope for phase 1.

## 8. Requests

- kernel: keep `CONFIG_DRM_PANEL_EDP`, `CONFIG_BACKLIGHT_PWM`, `CONFIG_LEDS_QCOM_LPG` as modules (already in `kernel/config/sp11.config`).
- image: log collector must dump `/sys/kernel/debug/dri/*/eDP-1/*`, `/dev/drm_dp_aux*` DPCD `0x000`-`0x0FF` and `0x700`-`0x7FF`, and `/sys/class/backlight`.

## 9. Log

- 2026-10-23: dossier created from the static survey; EDID base block decoded.
