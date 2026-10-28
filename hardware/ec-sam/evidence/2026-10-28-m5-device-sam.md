# M5 SAM, HID and power evidence

The observations below use only the GPU-off boot `3f0e2cc1…` in
`out/device-logs/m5-20261028/`, kernel `7.3.0-65.sp11.3.fc44`. It reached
GNOME for 234 s. The GPU-on boot `0ee2fa1a…` reset at session start and
has no equivalent complete power capture. Neither boot tested our patches.
Raw logs stay outside git; no pack serial or device address is reproduced.

## Provenance

| Input | SHA-256 | Locator |
|:--|:--|:--|
| GPU-off `dmesg.txt` | `2afe5df265e037dddb773bfba792a3b3ef53f9b6df869e66c1afed2489940382` | lines 1173, 1196, 2005, 2016, 2022, 2057–2063 |
| GPU-off `power_supply.txt` | `02b5a08ca0d66d8ff66be0bbaeecdbdf9fec89c1c674b50f011c6bc6f2ccc142` | sections BAT1, ADP1, qcom-battmgr-bat |
| GPU-off `journal.txt` | `28fd8fdf72a86c2d02313e826479c8eed4b241e08b878eea42e7e490a34e9901` | SAM and HID monotonic timestamps |
| `sources/windows/live-inventory/acpi/ssdt.dsl` | `95ee103a7ad5d9b55cc84ff09065171d638b6de9d1aafcde6efc69ce6a824f1b` | SHPS at lines 397–500; SSH at 504 onward |
| `sources/windows/live-inventory/acpi/dsdt.dsl` | `8a7b849b9ac2148a9806d967612eb0d5195020c3e29ffd834b837767256a8ede` | PMBM at 675–694; SEN2/SEN3 at 62969–63064 |
| `sources/windows/live-inventory/sam/pnp-sam-tree.tsv` | `c2e00cff966968fa8d0789db32c6c5e8cad399c65ef9d3c9a3790f6f4eba1085` | mini-driver PDO rows 18, 43, 65; pen row 22; sensors rows 8, 35 |
| `sources/windows/live-inventory/sam/reg-sam.txt` | `0000732ad40dcc87aa770d2c856c858e3ff7600a5e072f94336948cff875e6c2` | Enum and Services parameter sections |
| `sources/windows/live-inventory/pnp-present.json` | `7c6c4ab8a82ee2b5b1df32407ff69e1f7bf72fdda8ba4fe4c8adc550006e772b` | Target_KIP HID and Battery-class entries |
| `sources/windows/DriverStore/surfacehidminidriver.inf_arm64_70f4ca553fda1292/SurfaceHidMiniDriver.inf` | `b5611c275ddaf7b7167fbe6a5bbddced9431818eec3782e701f5d5dd5ba7e5ac` | Vendor.NTARM64 and SurfaceHidMini_ParametersHW_AddReg |
| `sources/windows/DriverStore/surfacehotplug.inf_arm64_526521aec65d5cc2/SurfaceHotPlug.inf` | `76e5200fb8ea2ae22db18c257b9df57d8b9b1e8c17fa4bf53945e42fae995eeb` | Standard.NTARM64 and service sections |

Windows inputs were checked against `sources/binary-catalog.tsv`: DSL/TSV/INF
are text and PnP JSON is config. None was disassembled. No Windows binary
or predecessor REA result is needed for the conclusions below.

## 1. Working enumeration (Verified)

SAM reports firmware **27.201.139** at about +3.3 s. At about +26.5 s the
KIP hub registers keyboard `045E:09AE` (IID 1, `hid-generic`), touchpad and
mouse `045E:09AF` (IID 3, ultimately `hid-multitouch`), and firmware-update
HID `045E:09D4` (IID 5). The KIP tablet switch also registers. Enumeration
is established; actual typing, pointer use and correct posture transitions
remain untested by the operator.

Driver path: DT UART → `surface_aggregator` (driver name `surface_serial_hub`)
→ `surface_aggregator_registry` (platform hub) → `surface_aggregator_hub`
(KIP child hub) → `surface_hid`/`surface_hid_core` → HID input drivers.
The KIP hub registers its child devices only after a successful connection
query (`sources/linux/drivers/platform/surface/surface_aggregator_hub.c:97`,
`:293`, `:350`). Thus including the HID transport without the KIP hub
cannot provide a Type Cover keyboard in the initramfs.

The inherited initramfs inventory at
`out/image-work/l0-sp11-fedora44-aarch64-kiwi-20261025T160856Z/initrd-ko.txt`
contains the transport but lacks the hub. That inventory predates M5;
it is supporting evidence of the image recipe's omission, not proof of
M5's exact initramfs contents. The delayed registration alone does not
prove why udev loaded a module late. Request an `lsinitrd` assertion on
the next image and an initramfs shell check.

## 2. Failing endpoints and what they mean

The SSAM name is domain:category:TID:IID:function, in hexadecimal.
Domain `01` denotes a physical SSAM client. Function `00` selects the
generic HID client, not a particular HID usage or pen report.

| Name | Identity from the Linux registry (Verified) | Windows comparison |
|:--|:--|:--|
| `01:15:01:06:00` | TC `15` HID, TID `01` SAM, IID `06`, function `00`; `ssam_node_hid_sam_sensors`, a HID sensor collection (`surface_aggregator_registry.c:134`) | No Target_SAM/Category_HID PDO in the captured PnP tree. ACPI SEN2/SEN3 (`MSHW048A/B`) instead depend on ADSP/ARPC; PnP names them Qualcomm sensor platforms. This is not evidence that sensors themselves are absent. |
| `01:15:02:02:00` | TC `15` HID, TID `02` KIP, IID `02`, function `00`; `ssam_node_hid_kip_penstash`, pen taken/stashed notifications (`surface_aggregator_registry.c:200`) | KIP mini-driver PDO ordinals are 1, 3 and 5 only; no 2. The captured pen device is `HID\MSHW0484&COL07`, parent `ACPI\MSHW0484`, separate from KIP. This failure does not identify a missing pen digitizer. |

Windows ACPI defines two hotplug instances: `\_SB.SHPS` (`MSHW0153`, `_DSM`
function 6 = `080e`) and `\_SB.WSID.SHPS` (`_ADR` `9086e8da`, feature word
`060c`), both dependent on SSH (`ssdt.dsl:397`). The hotplug INF maps these
to KIP and SAM HostRegister. The HID INF supports both targets and enables
multiple-instance IDs (`ComboHardwareIdV2Enabled=1`). An INF match lists
possible devices; the captured PnP children establish which were present.
`reg-sam.txt` has no per-endpoint enable mask. Do not claim that its generic
`FirmwareIdentified=1` values enumerate HID functions or decode the feature
word bits without a source.

Both endpoints log `unexpected descriptor length: got 0, expected 9` and
fail with `-EPROTO` (-71). The request is TC `15`, the endpoint TID/IID,
CID `04`, descriptor entry `00`. `surface_hid_core.h:20` defines that entry
and the nine-byte structure; `surface_hid_core.c:39` requests it.
`surface_hid.c:42` assembles chunks (maximum data slice `76` hex) and at
`:104` reports a final assembled offset of zero. This is not a timeout
or an observed USB transaction; the products merely use HID vendor/product IDs.

**Inference:** these optional endpoints are unimplemented on this firmware
and attached cover, so the static registry asks for descriptors that do not
exist. Working IIDs 1/3/5 on the same link and absent Windows children make
this stronger than a general transport or descriptor-format failure. We
have no raw SSAM exchange: the log proves zero assembled descriptor bytes,
not the precise wire reply or the firmware's internal reason.

**Fix proposed:** patch 0001 omits both from this project's Denali registry.
Keep HID length validation unchanged; do not fabricate an empty valid HID
or hide all probe errors. This preserves the working keyboard, touchpad,
update endpoint and tablet switch. The pen-stash deletion is local to the
tested cover; recheck it before claiming support for interchangeable covers.
Pen storage notifications could matter on another cover.

The sensor deletion independently matches Dale Whinham's
[upstream v2 patch](https://lkml.iu.edu/2609.2/08839.html). Upstream also
[proposes POS tablet mode](https://lkml.iu.edu/2609.2/08840.html) to fix a
post-resume KIP posture issue. Our held patch 0002 therefore deserves a
posture/resume test, but is not required to fix these HID probe failures.
The linux-next branch could not be fetched during this session; do not
claim a verified next-tree revision. External patches are references,
not newly pinned inputs under `sources/`.

## 3. Battery and AC

The GPU-off capture was **on battery**, with no charger. Values below exclude
pack identity. They verify that SAM already supplies the required discharge
properties; they do not verify plugged-in charging or UPower behavior.

| Property | SAM BAT1 | ADSP qcom-battmgr-bat |
|:--|:--|:--|
| energy_full / energy_full_design, uWh | 44,780,000 / 46,530,000 | 44,780,000 / 46,530,000 |
| energy_now, uWh | 17,000,000 | 17,016,000 |
| voltage_now, uV | 7,323,000 | 7,323,000 |
| power_now, uW | 16,813,000 | -15,224,000 |
| status | Discharging | Discharging |
| capacity / capacity_level | 37 / Normal | not exposed |
| cycle_count | 141 | 0 |

SAM ADP1 and qcom-battmgr-ac both report Mains/online `0`. Matching pack
energy and voltage strongly support a duplicate physical battery (Inference).
Windows PMBM `_STA` returns zero on both paths (`dsdt.dsl:675`), and its
Battery-class path uses SurfaceBattery. D23 has already selected SAM and
blacklisted `qcom_battmgr`; charger collection is an acceptance check of
that decision, not permission to defer it or re-enable the duplicate.
UCSI supplies remain available independently of qcom_battmgr.

Linux `surface_battery.c:446` exposes STATUS, CAPACITY, ENERGY_NOW/FULL/
FULL_DESIGN, POWER_NOW, voltage and presence for the energy-unit battery.
`:464` distinguishes Discharging, Charging, Full, Not charging and Unknown;
`:508` calculates percentage from remaining/full energy. Values are scaled
to micro-units at `:599`. `surface_charger.c:140` exposes ONLINE from the
SAM platform-power-source request (CID `0d`, `:41`), with type Mains and
`supplied_to` BAT1/BAT2 (`:182`). Battery and AC events call
`power_supply_changed`; AC changes trigger a battery refresh after 5 s
(`surface_battery.c:408`, delay `:153`). These provide the kernel interface
UPower needs. No additional battery driver patch is justified by M5.
The [UPower device interface](https://upower.freedesktop.org/docs/Device.html)
distinguishes remaining Percentage from health Capacity and provides Online,
State, Energy and EnergyRate; the device test must check their populated
values, not only the presence of a kernel driver.

**TBD:** with a charger on each USB-C port and Surface Connect (if available),
ADP1 must become online, BAT1 status and UPower state must agree, percentage
and energy must remain present, and the display device must use only one
system battery. Full/Not charging at a firmware-imposed limit is legitimate;
never change that limit to force Charging. See test-plan section 3 for the
allowlisted, read-only capture and timing.
