# display-lcd worker

**Owns:** `hardware/display-lcd/` (write). Everything else is read-only.
**Phase:** 1. **Kernel worktree:** yes (`out/linux/display-lcd`, branch `w/display-lcd`).

## Mission

Make the internal LCD show a stable picture at 2880x1920, at 120 Hz and 60 Hz, with working brightness control, on vanilla Linux 7.3 plus the smallest correct patch set. Every value in the patches is Verified or a justified Inference.

## Start

1. Read `hardware/display-lcd/README.md`, `component.toml`, and `hardware/soc-boot/README.md`.
2. Decode the full EDID (`sources/windows/live-inventory/panel/edid-LGD077B.bin`), including the DisplayID extension: native mode, both refresh modes, pixel clock, porches, bpc. Write `evidence/<date>-edid.md`.
3. Answer the dossier's open questions in order. Q1 (backlight method) decides the shape of the DT patch and is the priority.

## Specific leads

- **Backlight (Q1).** Find where the Windows display driver decides the backlight type for this board. Start with the Surface extension blobs in `surface_dxext_8380.inf_arm64_69910c8aa1a39011/` (`qcdxkmext8380_DEN*.bin`): identify their format and the entries for the LCD (`DENidp`?) versus OLED (`DENcrd`?) variant. Then, in REA, the code in `qcdx8380.inf_arm64_34a2c09c0e5b25ac/qcdxkm8380.sys` that reads `BacklightType`, `BacklightPmic*` and the PWM settings. The GPU ROM XMLs in `live-inventory/panel/` show the keys but for reference panels only.
- **PMIC side.** If PWM: PMK8550 LPG channel and its pin (`hamoa-pmics.dtsi`, `leds-qcom-lpg.c`), enable and supply GPIOs (PMC8380_3), frequency and resolution. Cross-check against the PMIC GPIO settings applied by `qcpmicgpio8380` / `qcpep8380.sys` for the display power-on sequence.
- **Power sequence (Q2).** The panel power-up/down delays in `qcdxkm8380.sys` or the PEP (`qcpep.wd8380`). Fall back to the LGD defaults used in `panel-edp.c` only with a written reason.
- **Upstream.** Search lore for `0x077b`, `LP129WT342166`, "Surface Pro 11" panel and backlight patches before writing new ones.
- **DPCD (Q3).** Write the commands for the log collector to read DPCD `0x000`-`0x0FF` and `0x700`-`0x7FF` through `/dev/drm_dp_aux*` and hand them to the image worker as a request.

## Deliver

1. `patches/`: at most these, each upstream-style: `drm/panel: edp: add LGD 0x077B`, `arm64: dts: qcom: x1p64100-microsoft-denali: mux eDP HPD`, `arm64: dts: qcom: x1p64100-microsoft-denali: add backlight` (only once Q1 is Verified or a strong Inference).
2. Patches build in your worktree; `checkpatch.pl --strict` clean; `make CHECK_DTBS=y qcom/x1p64100-microsoft-denali.dtb` clean. Use the build lock (`agents/protocol.md` §4.2).
3. `test-plan.md`: exact commands for the acceptance list in the dossier, with expected outputs.
4. Dossier and `component.toml` updated; status `designed` or `sw-ready`.

## Do not

- Add a backlight node on a guess. A wrong PWM pin mux can leave the panel dark (see dossier §6).
- Touch the TCON firmware (risk S3).
- Copy values from other machines' DTs without proving the wiring is the same.
