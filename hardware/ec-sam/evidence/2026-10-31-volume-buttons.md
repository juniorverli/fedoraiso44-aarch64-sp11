# Volume buttons: ACPI MSHW0040 mapping to Linux (patch 0005)

Date: 2026-10-31. Operator requirement: the Surface Pro 11 volume up/down buttons (ACPI `MSHW0040`, Windows driver `surfacebutton`) must work in Linux, integrated. Method: ACPI data only (decompiled tables in `sources/windows/live-inventory/acpi/`, plus the Linux 7.3 sources). Not used: REA, Windows driver binaries. Nothing was run on the device. Sources are cited as `ssdt.dsl`/`dsdt.dsl` (same directory) with line numbers of the decompiled text.

## Verified (from ACPI data and Linux source)

| # | Fact | Source |
|:--|:--|:--|
| V1 | Device `\_SB.MSBT`, `_HID` "MSHW0040", `_STA` 0x0F (present), `_DEP` on `\_SB.PM01` and `\_SB.GIO0`. Windows has it bound ("Surface Button", status OK) with a "Surface Button VHF HID Device" and two "Converted Portable Button Device" children | `ssdt.dsl:646-662`; `live-inventory/pnp-present.json` (Surface Button entries) |
| V2 | `_CRS` has six resources in this order: (1) GpioInt on `\_SB.GIO0`, pin 0x03C0, Edge, ActiveBoth, SharedAndWake, PullNone, debounce 0; (2) GpioIo on `\_SB.GIO0`, pin 0x0013 (TLMM GPIO 19), Shared, PullNone, InputOnly; (3) GpioInt on `\_SB.PM01`, pin 0x00D5, Edge, ActiveBoth, **Shared**, PullUp, debounce 0, vendor data `01 FF FF FF`; (4) GpioIo `\_SB.PM01` pin 0x00D5, Shared, PullUp, InputOnly, same vendor data; (5) GpioInt `\_SB.PM01` pin 0x00D7, same attributes as (3); (6) GpioIo `\_SB.PM01` pin 0x00D7, same attributes as (4). So three buttons, each an interrupt plus an input-only I/O pair | `ssdt.dsl:660-713` |
| V3 | The two PMIC pairs are Shared, not SharedAndWake: **the volume buttons are not ACPI wake capable**. Only the first pair (GIO0) is SharedAndWake. No GPIO output resource exists: all are input only | `ssdt.dsl:667,676,685,694,703,712` |
| V4 | Pull: volume pins PullUp (both GpioInt and GpioIo); GIO0 pair PullNone. Debounce field is 0 for every resource: **ACPI carries no debounce time**; the 15 ms of the held draft is not in ACPI | `ssdt.dsl:660-713` |
| V5 | There is no `_DSD`, no button names, no keycodes and no third GIO0/PM01 pair. `_DSM` (UUID `6fd05c69-cde3-49f4-95ed-ab1665498035`, revision 1) answers only function 0 (bitmap 0x0F), 1 (returns 0x00), 2 (returns `OMPR`, "OEM Platform Revision") and 3 (returns `SBFF`, 32-bit flags in MNVS memory, runtime value not in the dumps). Linux `surfacepro3_button.c` uses the same UUID and function 2 only to check the platform revision | `ssdt.dsl:715-768`; `sources/linux/drivers/platform/surface/surfacepro3_button.c:21-27,156-165` |
| V6 | No Windows button resource exists: the device has exactly three pins (one TLMM, two PMIC). The Surface Pro 11 has power and volume up/down only | `ssdt.dsl:660-713` |
| V7 | `\_SB.PM01` is the `QCOM0C2D` PMIC GPIO controller (Windows service `qcpmgpio`, "System Manager PMIC GPIO Framework Extension Device"), UID 1, depends on `\_SB.PMIC`. `\_SB.GIO0` is the `QCOM0C0C` TLMM (memory 0x0F100000, 0x00F00000 long; the lid pin 2 and the SAM pin 91 are here) | `dsdt.dsl:569-585,55516-55545`; `live-inventory/buttons/registry-QCOM0C2D.txt` |
| V8 | GIO0 GpioInt pin numbers are not TLMM GPIO numbers but wake-interrupt slots 64 apart: lid GpioInt 0x0340 pairs with GpioIo 2, SAM GpioInt 0x0380 pairs with GpioIo 0x5B (91, the same GPIO the Denali DT uses). The GpioIo pin is the real GPIO, so the first pair is **TLMM GPIO 19** (0x13), wake slot 0x03C0 | `dsdt.dsl:55524-55532,55641`; `ssdt.dsl:525-545`; `x1-microsoft-denali.dtsi` SAM `GPIO 91` and lid `tlmm 2` |
| V9 | The PM01 pin numbers form one linear Windows pin space that is not the Linux per-PMIC GPIO number. Calibration inside the tables: the USB-C retimer device `UCS0` (`QCOM0CA4`) has output pins PM01 0x00D9 and 0x00DA (and 0x01A1). The Denali DT (upstream, verified against Windows by its authors) uses PM8550 GPIO 10 (retimer reset) and GPIO 11 (3.3 V enable) for the same retimer, and the x1e80100 CRD uses the same two. So 0xD9 = GPIO 10 and 0xDA = GPIO 11: Windows pin = 0xCF + Linux GPIO number (1-based) | `dsdt.dsl:65368-65440`; `x1-microsoft-denali.dtsi:217,1051,1299-1311`; `x1-crd.dtsi:417,1019,1321-1345` |
| V10 | On the Qualcomm CRD (same SoC and PMIC) PM8550 GPIO 6 is the volume up key with exactly this electrical setup: `GPIO_ACTIVE_LOW`, `function = "normal"`, `power-source = <1>` (1.8 V), `bias-pull-up`, `input-enable` | `sources/linux/arch/arm64/boot/dts/qcom/x1-crd.dtsi:52-62,1321-1328` |
| V11 | Linux PMIC GPIO numbers in DT are 1-based (`<&pm8550_gpios 6 ...>` is pin name `gpio6`). `pm8550_gpios` is an interrupt controller (12 GPIOs) so gpio-keys can request the edge interrupt | `hamoa-pmics.dtsi:428-436`; `x1-crd.dtsi` |
| V12 | Neither PM8550 GPIO 6 nor 8 is used elsewhere in the composed tree (v7.3 plus the 69-patch series, `x1p64100-microsoft-denali.dts`); gpio8 of `pm8550ve_9` and `pmc8380_5` are different controllers | grep of the composed tree |

## Inference

| # | Statement | Rests on |
|:--|:--|:--|
| I1 | The two buttons are **PM8550 GPIO 6 (0xD5) and GPIO 8 (0xD7)**. Pin 0xD5 = 0xCF + 6 and 0xD7 = 0xCF + 8; the offset is calibrated by two independent points (V9) and agrees with the inherited draft (which came from the Windows driver's pin table), so two routes meet at the same pins. Not proven: the calibration assumes the PM8550 block of the Windows pin space is contiguous | V2, V9 |
| I2 | **Volume up = GPIO 6, volume down = GPIO 8.** ACPI does not name the buttons. Evidence: resource order (first PM pair is 0xD5), GPIO 6 is the volume up key on the CRD (V10), and the SoC-button convention (up before down) | V2, V10 |
| I3 | The first GIO0 pair (TLMM GPIO 19, SharedAndWake) is the power button: it is the only wake pair and the only TLMM one. Not named in ACPI; not part of patch 0005 (see section "Power button") | V2, V3 |
| I4 | Polarity: active low (pressed pulls the pin to ground against the pull-up). ACPI says ActiveBoth edge and PullUp only; PullUp implies an idle-high pin and thus a press to low. Same as the CRD | V2, V10 |
| I5 | Supply: 1.8 V (`power-source = <1>`). ACPI has no voltage field; every PM8550 GPIO consumer of the Denali and CRD DTs uses it | V10 |
| I6 | Debounce 15 ms: taken from other Qualcomm DTs (sm8550-qrd) because the ACPI debounce is 0. It only affects contact bounce; a wrong value does not make a button dead | V4 |
| I7 | No `wakeup-source`: ACPI marks the volume pairs not wake capable (V3), so waking from suspend on a volume button is not claimed | V3 |

## Unknown

| # | Question | What answers it |
|:--|:--|:--|
| U1 | Real up/down orientation and polarity on this unit | The device test below (phase UP and phase DOWN) |
| U2 | The meaning of vendor data `01 FF FF FF` on the PM01 resources | Not needed if the test passes. Probably PMIC/bank selector; it matches `PM01` UID 1 and the PM8550 SPMI USID 1 |
| U3 | The value behind `SBFF` and `OMPR` (MNVS, runtime) | A live ACPI call, not needed for pins |
| U4 | Whether PMK8550 PON `pwrkey` (enabled in `hamoa-pmics.dtsi:210`, no override in the Denali files) is also a power button path | Test plan power capture; separate from volume |

## Patch

`patches/0005-arm64-dts-qcom-x1p64100-microsoft-denali-Add-the-vol.patch` (Denali LCD board file only). A separate `volume-keys` gpio-keys node (no change to the shared `x1-microsoft-denali.dtsi` lid node): `KEY_VOLUMEUP` on `<&pm8550_gpios 6 GPIO_ACTIVE_LOW>`, `KEY_VOLUMEDOWN` on `<&pm8550_gpios 8 GPIO_ACTIVE_LOW>`, `debounce-interval = <15>`, pinctrl states `vol_up_n` and `vol_down_n` (`function = "normal"`, `power-source = <1>`, `bias-pull-up`, `input-enable`). No output driving, no `wakeup-source`, no `linux,can-disable`. `Assisted-by: Claude Sonnet 5.5`, no Signed-off-by.

Validation in the scratch composed tree `out/linux/ec-sam-vol` (v7.3 + the 69 patches of `kernel/series`, applied with `git apply`; `git am` fails on an empty author of one series patch, unrelated):

- `git apply --check` of the patch on the series tree: ok.
- `scripts/kernel-dev.sh --check ec-sam-vol dtbs` (`CHECK_DTBS=y`, `x1p64100-microsoft-denali.dtb`): rc 0, no dt-schema warning. The decompiled DTB shows `volume-keys` with codes 0x73 and 0x72 on `pm8550_gpios` 6 and 8, flags 1 (active low), debounce 15.
- `checkpatch.pl --strict`: only "Missing Signed-off-by" (by design for an Assisted-by patch; the orchestrator signs at merge). 0 warnings, 0 checks.
- A clean schema build does not verify wiring. Patch 0004 in `patches/hold/` stays held (it also describes the power button and carries the unreproduced 15 ms and power-key claims); 0005 replaces it for the volume keys only.

## Power button

Power is also in this ACPI device (TLMM GPIO 19, SharedAndWake, PullNone, I3). It is intentionally not in 0005: the PMK8550 PON power key node exists in `hamoa-pmics.dtsi:210` and double-describing the same physical button would give two `KEY_POWER` sources. Decide from the device capture: if the PON key reports the physical power button, nothing is needed; if not, a `key-power` on `<&tlmm 19 GPIO_ACTIVE_LOW>` with `wakeup-source` is the candidate (polarity unknown).

## Device test (read-only, operator needed, 10 s per phase)

Tool: `tools/collect-volume-buttons.sh` (stage under `/usr/libexec/sp11/ec-sam/`, run as root, output into the log set). Steps, on a kernel with patch 0005 and `CONFIG_KEYBOARD_GPIO=m` loaded (the module is not needed in the initramfs):

1. Boot the test entry, wait for the desktop, run `sudo /usr/libexec/sp11/ec-sam/collect-volume-buttons.sh > volume-buttons.txt 2>&1`.
2. Phase UP, 10 s: press only the volume up button about five times. Phase DOWN, 10 s: press only the volume down button about five times.
3. The script prints: the bound `gpio-keys` devices and the `volume-keys` input device with its key capability bitmap; kernel gpio-keys/PMIC lines; the pm8550 pinconf for pins 6 and 8 (debugfs); the GPIO state (`/sys/kernel/debug/gpio`, pins named `key-volume-up/down`) every time it changes; `libinput debug-events --device <volume-keys device>` limited to that device (key names visible, keyboard never read); `/proc/interrupts` counts before and after.

Pass: PHASE UP shows `KEY_VOLUMEUP` pressed/released and only the up pin toggling; PHASE DOWN the same for down; interrupt counts rise in the matching phase; the desktop volume changes. Swapped codes: swap the two `gpios` lines (U1). Pin toggles but no event: polarity (flip to `GPIO_ACTIVE_HIGH`) or debounce. No pin change: pin number (I1) wrong; widen the capture with the neighbouring pins 5, 7 and 9 on `pm8550_gpios` (read only).
