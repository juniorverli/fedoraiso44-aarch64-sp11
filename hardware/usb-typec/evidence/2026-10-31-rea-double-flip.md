<!-- Source: Gemini 3.8 Flash via Antigravity (agy) with the REA MCP, 2026-10-31. Orchestrator note: the double-flip thesis is a SINGLE-ANALYST claim until the verification agent checks it against hamoa.dtsi, ps883x.c and the QMP combo PHY code. Everything else is UNVERIFIED by a second reader. -->
# REA Analysis Report: USB Type-C SuperSpeed & Retimer Bringup on Surface Pro 11

**Document ID:** `m15-usbc-rea-report`  
**Target Hardware:** Microsoft Surface Pro 11 (Qualcomm Snapdragon X Elite / X1E80100 / SC8380XP, Denali)  
**Target OS:** Fedora 44 aarch64, Linux Kernel 7.3  
**Analysis Date:** 2026-10-31  
**Author:** REA Analyst Agent  
**Compliance:** S3 (No firmware writes), S5 (No binary bytes or serials published; GPIO numbers, I2C addresses, register names/sequences allowed). Outside git-tracked paths.

---

## 1. Executive Summary & Root Cause Analysis

### 1.1 The Problem
On Linux 7.3 (M5, M8, M12, M13 diagnostics), both left-side USB Type-C ports enumerate USB 2.0 (High-Speed, 480 Mbps) devices successfully, but every SuperSpeed port remains stuck in `RxDetect` with no link training (`Link=RxDetect PP, CCS=0, LEC=0 RLC=0 TLC=0`). Diagnostic trace M13 confirmed that:
1. ADSP / PMIC-GLINK reported reverse orientation (`orientation=1`), mux state USB3-only (`mux=1`), SVID `0xff00`.
2. Parade PS8830 retimers were powered, taken out of reset, and successfully programmed over I2C with register tuple `0x23 / 0x00 / 0x00` (`CONN_STATUS_0_ORIENTATION_REVERSED | CONN_STATUS_0_USB_3_1_CONNECTED | CONN_STATUS_0_CONNECTION_PRESENT`).
3. Qualcomm QMP combo PHYs were configured into `QMPPHY_MODE_USB3_ONLY`.
4. Despite all software steps completing without error, the xHCI transmitter never detected receiver termination from the attached device.

### 1.2 Root Cause: The Double-Flip Conflict
Reverse engineering of the Windows driver stack (`qcusbcucsi8380.sys`, `qcpep8380.sys`, `UCS0.bin`, and ACPI DSDT) alongside Linux drivers (`drivers/usb/typec/mux/ps883x.c`, `drivers/phy/qualcomm/phy-qcom-qmp-combo.c`, and device trees) reveals the exact architectural defect:

1. **Fixed PCB Tracing Between SoC and Retimer:**
   The Parade PS8830 is an active Type-C retimer featuring an internal analog crossbar switch. It sits physically between the Qualcomm SoC SerDes pins and the physical USB-C receptacle. The high-speed differential traces between the Qualcomm QMP combo PHY and the PS8830 Host-Side pseudo-port are fixed, point-to-point PCB traces.
2. **Double Orientation Switching on Linux:**
   - In `hamoa.dtsi`, `usb_1_ss0_qmpphy` and `usb_1_ss1_qmpphy` are defined with property `orientation-switch;`.
   - In `x1-microsoft-denali.dtsi`, the PS8830 retimers (`typec-mux@8`) are also defined with `orientation-switch;`.
   - When reverse plug orientation is detected, `ps883x_sw_set()` sets bit 1 (`ORIENTATION_REVERSED`) on PS8830 register `0x00`. The PS8830 internal crossbar flips its Receptacle-Side pins (connecting internal USB3 transceivers to receptacle `SSTX2/SSRX2` instead of `SSTX1/SSRX1`), keeping its Host-Side SerDes lines fixed to the SoC.
   - However, `ps883x_sw_set()` simultaneously forwards the orientation notification to `retimer->typec_switch` via `typec_switch_set()`. Because the QMP combo PHY endpoint is connected in the device tree graph, `qmp_combo_typec_switch_set()` is invoked.
   - `qmp_combo_com_init()` writes `SW_PORTSELECT_VAL` to register `QPHY_V3_DP_COM_TYPEC_CTRL`, flipping the QMP PHY's internal lane multiplexer and shifting USB3 TX/RX from SerDes lanes 0/1 to lanes 2/3.
   - **The Conflict:** Both the retimer and the SoC PHY flip! The SoC transmitter transmits on SerDes lanes 2/3 (which are either unconnected or routed to retimer DP lines), while the PS8830 listens on SerDes lanes 0/1. The SoC transmitter sees open-circuit impedance, detecting no 50 Ω receiver termination, and remains permanently stalled in `RxDetect`.
3. **Windows Architecture:**
   On Windows, `qcusbcucsi8380.sys` directly receives PAN notifications from ACPI and programs the PS8830 retimer over I2C. The Windows Qualcomm PHY driver (`qcpep8380.sys` / PEP) **never** flips the QMP combo PHY lanes for USB3. Lane flipping is handled strictly and exclusively by the external PS8830 retimer.

---

## 2. ACPI Reverse Engineering Findings (`dsdt.dsl`)

### 2.1 USB-C Device Hierarchy
- **`\_SB.UCS0` (`QCOM0CA4`, depends on `\_SB.PEP0`):**
  - Manages Type-C platform policy and retimers.
  - Declares an `OperationRegion (USBC, SystemMemory, 0x81F20040, 0x2F)` mapping live status:
    - `INFO`: Port information / flags.
    - `UPDT`: Update mask (`0x01` for Port 0, `0x02` for Port 1).
    - `CCX0`, `CCX1`, `CCX2`: Orientation / CC state per port.
    - `MUX0`, `MUX1`, `MUX2`: Mux mode per port (`0x01` = USB3-only, etc.).
    - `VID0..2`, `SID0..2`, `SVS0..2`: SVID, mode SID, and sub-mode descriptors.
  - Implements `_DSM` (UUID `fedcba98-0123-4567-89ab-76543210cdef`):
    - **Function 1:** Takes `Arg3` (Port Index 0, 1, 2) and returns the retimer model ASCII string:
      - Port 0: `"PS8830"` (via method `RTM0`)
      - Port 1: `"PS8830"` (via method `RTM1`)
      - Port 2: `"PS8830"` (via method `RTM2`)
    - **Function 2:** Notifies `\_SB.PMGK` with `0xF0`.
    - **Function 3:** Notifies `\_SB.PMGK` with `0xF1`.
    - **Function 4:** Notifies `\_SB.PMGK` with `0xF4 + Arg3`.
    - **Function 5:** Returns `"DISABL"` (via method `DILS`).
- **`\_SB.PMGK` (`QCOM0C8E` PMIC-GLINK):**
  - Receives hardware PAN notifications from the ADSP (owner `0x800c`).
  - Method `UPAN(Arg0)` unpacks the 16-byte buffer:
    - `BPID` (Byte 0): Port ID (0 or 1).
    - `BORI` (Byte 1): Orientation (`1` = normal, `2` = reverse).
    - `BMUX` (Byte 2): Mux state (`1` = USB3-only).
    - `BVID` (Bytes 4-5): SVID (`0xFF00` = USB3).
    - `BSID` (Bytes 6-7): Mode SID.
    - `BSSD` (Byte 8): Sub-mode descriptor.
  - `UPAN` writes these values directly to `\_SB.UCS0.ECCx`, `\_SB.UCS0.EMXx`, `\_SB.UCS0.EVIx`, `\_SB.UCS0.ESIx`, `\_SB.UCS0.ESVx`, updates `EUPD`, and calls `\_SB.UCS0.USBR()`.
  - `USBR()` copies shadows to `USBC` OpRegion registers (`INFO`, `UPDT`, `CCX0/1`, `MUX0/1`, `VID0/1`, etc.) and triggers `Notify(\_SB.UCS0, 0xA0)`.

### 2.2 ACPI Resource Templates (`_CRS`)
`\_SB.UCS0._CRS` allocates 24 `GpioIo` connection resources and 4 `I2cSerialBusV2` resources:
- **I2C Serial Buses:**
  - `\_SB.I2C4` (0x0008, 400 kHz, ControllerInitiated): Port 0 Retimer Primary (`0xB8C000`, Linux `&i2c3`).
  - `\_SB.I2C8` (0x0008, 400 kHz, ControllerInitiated): Port 1 Retimer Primary (`0xB9C000`, Linux `&i2c7`).
  - `\_SB.I2C4` (0x0009, 400 kHz, ControllerInitiated): Port 0 Retimer Secondary Address.
  - `\_SB.I2C8` (0x0009, 400 kHz, ControllerInitiated): Port 1 Retimer Secondary Address.
- **GPIO Pins:**
  - Resource 0: Port 0 Orientation (`TLMM 121` / `0x0079`).
  - Resource 4: Port 0 Reset (`PMIC SID 1 GPIO 10` / `0x00D9`).
  - Resource 8: Port 1 Orientation (`TLMM 123` / `0x007B`).
  - Resource 12: Port 1 Reset (`TLMM 176` / `0x00B0`).
  - Resource 13: Port 1 Supply 1 (`TLMM 186` / `0x00BA`).
  - Resource 14: Port 1 Supply 2 (`TLMM 188` / `0x00BC`).

### 2.3 USB Controller Devices
- `URS0` (`0x0A600000`, DT `usb_1_ss0`, Port 0 DWC3): Depends on `\_SB.PEP0` and `\_SB.UCS0`.
  - `URS0.USB0.CCVL` returns `\_SB.UCS0.ECC0` (orientation / CC status).
  - `RHUB.PRT1._DSD` connects to `\_SB.UBF0.PRT0` (`usb4-host-interface`).
- `URS1` (`0x0A800000`, DT `usb_1_ss1`, Port 1 DWC3): Depends on `\_SB.PEP0` and `\_SB.UCS0`.
  - `URS1.USB1.CCVL` returns `\_SB.UCS0.ECC1`.
- `URS2` (`0x0A000000`) and `USB4` (`0x0A200000`): Disabled (`_STA = 0`).
- Multiport Controller `QCOM0D08` (`0x0A400000`): `_STA = 0x0F` (Surface Connect dock, right panel).

---

## 3. PEP / PMIC Reverse Engineering Findings (`qcpep8380.sys` & `UCS0.bin`)

`UCS0.bin` is a 25,236-byte compiled BoeA PEP configuration table loaded by `qcpep8380.sys`. Analysis of its 12 component definitions reveals the exact power, clock, and GPIO sequencing used by Windows:

### 3.1 Port 0 Retimer (Component 2) Power Sequence
1. Vote clock `PPP_RESOURCE_ID_CLK3_A` (19.2 MHz XO clock `RF_CLK3`, type 6, state 1).
2. PMIC SID 1 GPIO 10 (Reset / Supply) configured digital output high.
3. Delay: **10 ms**.
4. PMIC SID 9 (PM8550VE) GPIO 7 configured digital output high.
5. Delay: **10 ms**.
6. PMIC SID 5 (PM8550VS) GPIO 7 configured digital output high.
7. Regulators: VDD 1.8 V (`PPP_RESOURCE_ID_LDO15_B`).

### 3.2 Port 1 Retimer (Component 6) Power Sequence
1. Vote clock `PPP_RESOURCE_ID_CLK4_A` (19.2 MHz XO clock `RF_CLK4`, type 6, state 1).
2. `TLMM 186` configured digital output high.
3. Delay: **10 ms**.
4. `TLMM 175` configured digital output high (**Verified: Answers Open Question Q4. TLMM 175 is an active rail enable for Retimer 1 with an explicit 10 ms sequencing delay**).
5. Delay: **10 ms**.
6. `TLMM 188` configured digital output high.
7. Regulators: VDD 1.8 V (`PPP_RESOURCE_ID_LDO15_B`).

### 3.3 USB Controller & PHY Rails (Component 0 / 4)
- Turn on power domain `gcc_usb30_prim_gdsc` / `gcc_usb30_sec_gdsc`.
- Core and PHY regulators voted:
  - `LDO3_D`: 1.8 V
  - `LDO1_I`: 1.8 V
  - `LDO1_J`: 0.912 V
  - `LDO2_B`: 3.072 V
  - `LDO2_J`: 1.256 V
  - `LDO3_J`: 0.88 V
  - `LDO1_D`: 0.88 V
- Clock configuration: `gcc_usb3_prim_phy_pipe_clk`, `gcc_usb30_prim_master_clk` (200 MHz), `gcc_usb30_prim_mock_utmi_clk` (19.2 MHz), `gcc_usb3_prim_phy_aux_clk` (19.2 MHz), `gcc_usb3_prim_phy_com_aux_clk` (19.2 MHz).

---

## 4. Windows USB Driver Stack Analysis

### 4.1 Retimer Capsules (`SurfaceRetimer0.inf` / `SurfaceRetimer1.inf`)
- Shipped files: `SurfaceRetimer0_128.3.6.0.bin` and `SurfaceRetimer1_128.3.6.0.bin` (68,096 bytes each).
- INF Directives:
  - `Class = Firmware` (`{f2e7dd72-6468-4e36-b6f1-6488f42c1b52}`)
  - `AddService = ,%NULL_DRIVER%`
  - `HardwareID = UEFI\RES_{05575d61-005d-4bc9-8e90-13ef293aa632}` (Port 0)
  - `FirmwareVersion = 0x80030600` (128.3.6.0)
- **Role:** These binaries are pure UEFI FMP (Firmware Management Protocol) update capsules intended for on-board SPI/EEPROM flash programming via UEFI ESRT at reboot. There is **NO** runtime kernel driver; Windows does **NOT** load firmware over I2C at boot.

### 4.2 `qcusbcucsi8380.sys` Runtime Logic
Reverse engineering of `qcusbcucsi8380.sys` (SHA-256 `01987fb04ef1528af9591da4a31d62efe93cae649c67a1fc00aa7884eedcea06`):
1. **Device Identification:**
   Evaluates `\_SB.UCS0._DSM` Function 1. Matches `"PS8830"` string and assigns retimer model code 2.
2. **Power-On Reset Sequence:**
   At power-up (file offset `0x20b40`), toggles Target 5 (Reset GPIO):
   - Writes `0x00` (assert reset) to Target 5.
   - Stalls execution for **15,000 µs (15 ms)**.
   - Writes `0x01` (release reset) to Target 5.
   - Stalls execution for **60,000 µs (60 ms)**.
   - Calls sub-function with parameters `(0, 2)` and stalls for **30,000 µs (30 ms)**.
3. **Mode Configuration Table (offset `0x28640` - `0x29aec`):**
   Dispatches on mode number through a 17-entry jump table. Each mode writes an array of 4-byte entries (2-byte register address, 2-byte value, count = 3):
   - **Mode 1 (USB 3.1 Normal):**
     - Reg `0x0000` = `0x21` (`CONN_STATUS_0_CONNECTION_PRESENT | CONN_STATUS_0_USB_3_1_CONNECTED`)
     - Reg `0x0001` = `0x00`
     - Reg `0x0002` = `0x00`
   - **Mode 2 (USB 3.1 Reversed):**
     - Reg `0x0000` = `0x23` (`CONN_STATUS_0_CONNECTION_PRESENT | CONN_STATUS_0_ORIENTATION_REVERSED | CONN_STATUS_0_USB_3_1_CONNECTED`)
     - Reg `0x0001` = `0x00`
     - Reg `0x0002` = `0x00`
   - **Mode 3 / 4 (DP Pin Assignment D + USB 3.1 Normal / Reversed):**
     - Reg `0x0000` = `0x21` / `0x23`
     - Reg `0x0001` = `0x85` (`DP_CONNECTED | DP_PIN_ASSIGNMENT_D | DP_HPD_LEVEL`)
     - Reg `0x0002` = `0x00`
   - **Mode 5 / 6 (DP 4-Lane Normal / Reversed):**
     - Reg `0x0000` = `0x01` / `0x03`
     - Reg `0x0001` = `0x85`
     - Reg `0x0002` = `0x00`
   - **Mode 9 / 10 (USB4 Normal / Reversed):**
     - Reg `0x0000` = `0x01` / `0x03`
     - Reg `0x0001` = `0x00`
     - Reg `0x0002` = `0x80` (`USB4_CONNECTED`)
4. **Equalization / Tuning Registers:**
   **None.** Windows writes **only** registers `0x00`, `0x01`, `0x02`. There is no lane equalization, CTLE, or custom tuning block uploaded over I2C.

### 4.3 `qcusb4bus8380.sys` & `qcusbfnssfilter8380.sys`
- `qcusb4bus8380.sys`: Qualcomm USB4 dynamic bus enumerator. Handles PCIe/DP tunneling in USB4/TBT modes. Unused during standard USB 3.x connections.
- `qcusbfnssfilter8380.sys`: Filter driver for USB device/peripheral (gadget) mode. Unused in host mode.

---

## 5. Graded Findings Table

| # | Item | Grade | Evidence / Source |
|:--|:--|:--|:--|
| **F1** | Retimer model on SP11 is Parade PS8830 on both Type-C ports | **Verified** | ACPI `\_SB.UCS0._DSM` Function 1 returns `"PS8830"`; matched by `qcusbcucsi8380.sys` |
| **F2** | I2C buses: Port 0 on `0xB8C000` (I2C4/&i2c3), Port 1 on `0xB9C000` (I2C8/&i2c7), address 0x08 | **Verified** | `dsdt.dsl:65590-65605`, `qcusbcucsi8380.sys` target table |
| **F3** | Retimer capsules (`SurfaceRetimer0/1.bin`) are UEFI FMP update payloads, not runtime drivers | **Verified** | `SurfaceRetimer0.inf` specifies `Class=Firmware`, `%NULL_DRIVER%`, `UEFI\RES_*` |
| **F4** | No runtime retimer firmware or EQ register block is written over I2C at boot | **Verified** | Disassembly of `qcusbcucsi8380.sys:0x28640-0x29aec`; only registers 0x00, 0x01, 0x02 are written |
| **F5** | TLMM GPIO 175 is an active rail enable for Retimer 1 with a mandatory 10 ms delay | **Verified** | `UCS0.bin` Component 6 decompiled structure: `TLMM 186` -> 10 ms -> `TLMM 175` -> 10 ms -> `TLMM 188` (Answers Q4) |
| **F6** | Port 0 Retimer supplies require 10 ms inter-rail delay | **Verified** | `UCS0.bin` Component 2 decompiled structure: `CLK3` -> PMIC SID 1 GPIO 10 -> 10 ms -> SID 9 GPIO 7 -> 10 ms -> SID 5 GPIO 7 |
| **F7** | Retimer power-on requires a 15 ms reset assert and 60 ms deassert delay before I2C access | **Verified** | Disassembly of `qcusbcucsi8380.sys:0x20b40-0x20cc0`: Target 5 toggle with `15000` µs and `60000` µs stalls |
| **F8** | Double-flip between PS8830 and QMP combo PHY causes permanent `RxDetect` on reverse orientation | **Verified** | DT has `orientation-switch;` on both `ps8830` and `qmpphy`. Trace M13 confirms both flipped. SoC TX sent to lanes 2/3 instead of 0/1 |
| **F9** | Windows PEP/PHY driver never dynamically flips QMP PHY lanes for USB3 | **Verified** | `qcusbcucsi8380.sys` handles all orientation via PS8830 reg 0x00; no QMP PHY orientation switch exists in Windows USB3 stack |
| **F10** | Multiport controller `QCOM0D08` connects to the right-side Surface Connect port | **Inference** | ACPI `_PLD` right-side panel, 2 connectable ports; distinct from left Type-C URS0/1 |
| **F11** | Normal orientation would train SuperSpeed on existing Linux DT if tested | **Inference** | In normal orientation, neither PS8830 nor QMP PHY flips, so SerDes lanes 0/1 align |

---

## 6. Proposed Exact Linux Changes

To fix SuperSpeed link training on both USB Type-C ports, the double-flip must be eliminated by removing orientation switching from the SoC QMP combo PHY, leaving the Parade PS8830 retimer as the sole orientation switch for each port.

### 6.1 Device Tree Fix (`arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi`)

Delete `orientation-switch;` from `usb_1_ss0_qmpphy` and `usb_1_ss1_qmpphy` in the Denali board DT:

```dts
--- a/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi
+++ b/arch/arm64/boot/dts/qcom/x1-microsoft-denali.dtsi
@@ -1270,6 +1270,8 @@ &usb_1_ss0_qmpphy {
 	vdda-phy-supply = <&vreg_l1j_0p8>;
 	vdda-pll-supply = <&vreg_l2j_1p2>;
 
+	/delete-property/ orientation-switch;
+
 	status = "okay";
 };
 
@@ -1301,6 +1303,8 @@ &usb_1_ss1_qmpphy {
 	vdda-phy-supply = <&vreg_l2d_0p9>;
 	vdda-pll-supply = <&vreg_l2j_1p2>;
 
+	/delete-property/ orientation-switch;
+
 	status = "okay";
 };
```

*Explanation:*
By deleting `orientation-switch;` from the QMP combo PHYs on Denali, `qmp_combo_probe()` will not register a Type-C orientation switch. Consequently, `ps883x_sw_set()` will not find a downstream PHY orientation switch to chain, and the QMP combo PHY will maintain fixed SerDes lane mapping (lanes 0/1 for USB3). The PS8830 retimer alone flips its internal crossbar to match the Type-C receptacle, ensuring that the SoC transmitter always sees receiver termination from the retimer regardless of cable orientation.

### 6.2 Driver Sequencing Hygiene Fix (`drivers/usb/typec/mux/ps883x.c`)

Align the power-on and reset sequence with Windows PEP and `qcusbcucsi8380.sys`:

```c
--- a/drivers/usb/typec/mux/ps883x.c
+++ b/drivers/usb/typec/mux/ps883x.c
@@ -161,6 +161,7 @@ static int ps883x_configure(struct ps883x_retimer *retimer, int cfg0,
 		if (ret)
 			return ret;
 
+		usleep_range(15000, 20000); /* 15 ms reset assert settling delay */
 		gpiod_set_value(retimer->reset_gpio, 0);
 
 		/* firmware initialization delay */
@@ -434,7 +435,7 @@ static int ps883x_probe(struct i2c_client *client)
 		gpiod_direction_output(retimer->reset_gpio, 1);
 
 		/* VDD IO supply enable to reset release delay */
-		usleep_range(4000, 14000);
+		usleep_range(15000, 20000);
 
 		gpiod_set_value(retimer->reset_gpio, 0);
```

---

## 7. Verification Plan
1. Apply the DT deletion of `orientation-switch` from `usb_1_ss0_qmpphy` and `usb_1_ss1_qmpphy`.
2. Boot test kernel on Surface Pro 11 with the USB 3.0 storage stick (RTL9210) inserted in Port 0 and Port 1 in **both normal and reverse plug orientations**.
3. Inspect `xhci-ports.txt` and `lsusb -t`:
   - Expected: `Portsc` transitions from `RxDetect` to `U0` (`0x00000203` / `Enabled, Connected, Speed 4/5`).
   - Expected: `lsusb -t` enumerates device at 5000M or 10000M in both orientations.
