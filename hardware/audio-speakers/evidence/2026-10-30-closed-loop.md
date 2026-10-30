# Closed-loop speaker protection: stages 2 and 3 (offline), plan for stage 4

Author: audio-speakers worker (Claude Sonnet 5.5), 2026-10-30. Continues `2026-10-30-d26-audio.md` (stages 0 and 1). Everything here is offline: nothing was built into a kernel image, nothing ran on the device, nothing is committed. Grades follow `agents/protocol.md` section 5: Verified (read in code or data in this session), Inference, Hypothesis, Unknown. Each Unknown is a hardware question; the guesses are named as guesses.

## 1. Result in one table

| Stage | Written | Checked offline | Needs the device |
|:--|:--|:--|:--|
| 2a amplifier | patches 0010, 0011, 0013 | compiles with `W=1`, checkpatch `--strict` clean (except Signed-off-by and MAINTAINERS, by project rule), applies with fuzz 0 | every register value on real silicon, sense scaling, interrupt bits |
| 2b machine driver | patch 0015 (V/I 8 kHz/32-bit/4 ch, CPS 24 kHz/32-bit/2 ch, guard check, mute on fault) | same | link negotiation, SoundWire stream start order |
| 2c AudioReach | patch 0014 (control links, calibration records, R0/T0, fault event) and `sound/soc/qcom/qdsp6/audioreach-sp11.c` | same | that the ADSP accepts the control links and parameters |
| 2d gate | patch 0012 (`sp11` guard module), used by 0015; replaces the refusal of 0009 | same, plus a read of every producer and consumer | the whole chain, fault injection |
| 2e DT | patch 0016 (`x1-microsoft-denali-audio-closedloop.dtsi`), included only by `m13-spk` | `m13-spk` compiles; `dt_binding_check` of the binding passes; `kernel-dtb-safety.py --profile d26` accepts it | port numbers of the SoundWire master, reset line to speaker assignment |
| 3 generator | `userspace/build-topology/sp11_closedloop.py`, `build-closedloop.sh`, `acdb_inspect.py` accessor | self-test decodes what it wrote; formats match the C structs by construction | loading by the kernel |
| 3 topology `.bin` | NOT generated (section 6) | none | design decision first |
| 4 hardware | plan (section 8) | none | everything |

Series order after 0009: 0010 binding, 0011 amplifier settings, 0012 guard, 0013 amplifier capture and faults, 0014 AudioReach, 0015 machine driver, 0016 DT. Composed tree used for the checks: `out/build/apply-closedloop` (v7.3, the 37 entries of `kernel/series`, 0006 to 0009, 0010 to 0016, all `patch --fuzz=0`); objects compiled in the Fedora container with `W=1`: `wsa884x.o`, `sp11-guard.o`, `x1e80100.o`, `q6apm.o`, `audioreach.o`, `audioreach-sp11.o`, `topology.o`. No full kernel build. The scratch tree with the commits is `out/linux/audio-closedloop` (branch `w/closedloop`). I did not take the build lock: a release build held it and the check is a seven-object compile with `-j3`.

## 2. What the REA session established (qcaucd8380.sys)

Binary: `sources/windows/DriverStore/qcaucd8380.inf_arm64_53bcc309a68aba55/qcaucd8380.sys`, SHA-256 `bd0c8276c51fc7a020c616e904dd613b6ccf187ec3e1fe6f94c2c811c8adc8bf`, equal to `sources/binary-catalog.tsv` (PE, ARM64, `AARCH64:LE:64:v8A`). Ghidra 12.1.4 through the REA MCP. The REA process did not have `REA_GHIDRA_LANGUAGE_ID` set (the profile reports `language_id auto-from-header`); the header says ARM64 and the catalog language is the one Ghidra picks for it, so the decode is the expected one, but it deviates from protocol 9.2 and is recorded here. One binary, one session, closed with `close_binary` (no snapshot). Only `qcaucd8380.sys` was opened; `qcadcm8380.sys` was not.

Found by searching the `mov w, #imm` encodings of the register addresses, then decompiling the callers. Evidence ids: amplifier init `FUN_140032e10` `ev_c6c6e536e4d7ba683fb646ddf38f6e3e34514d273f982be1934ea98d34c63509`; power up/down and sense gains `FUN_1400328b8` `ev_69ef3582207e2f8ab22a48aa8dc5b1162af9e3fa32f6389f69f740000acb58c5`; DC resistance measurement `FUN_140030790` `ev_60c6db07fb8997ccde803c1d286ee1a977a09f71b7cc31286a2f8435768e1962`, wrapper `FUN_140030ea0` (evidence id prefix `ev_4cb371e2`), the 48-byte range table read at `0x140012ec0`, the register search for `0x3020` (`ev_a8480bb5461a91ec`...) and the xrefs of `DAT_1400570cc` (prefix `ev_15822d91`). Full ids of the three short ones are in the REA session log; they are quoted as prefixes because they were copied by hand.

### 2.1 Initialisation, `FUN_140032e10` (Verified, code)

The driver selects a variant `v = min(DAT_1400570cc, value of register 0x3501)`. Everything below is what the code writes; the register names are the ones already in `sound/soc/codecs/wsa884x.c`.

| Register | Name in Linux | Variant 2 and 5 (two-cell set) | Variant 1 and 4 | Variant 3 and 6 |
|:--|:--|:--|:--|:--|
| 0x3003 | BOP1_PROG | 0x22 | 0x22 | 0x22 |
| 0x3004 | BOP2_PROG | 0x44 | 0x66 | 0x44 |
| 0x3005 | UVLO_PROG | 0x33 | 0x99 | 0x00 |
| 0x3006 | UVLO_PROG1 | 0x60 | 0x60 | 0x60 |
| 0x3045 to 0x3049 | DAC_VCM_CTRL_REG2 to 6 | 06, 14, 19, 1b, 1c | not written | 0b, 1e, 36, 3b, 6f |
| 0x306a | DAC_VCM_CTRL_REG7 | 0x02 | not written | 0x02 |
| 0x34d2 | CLSH_V_HD_PA | 0x13 | not written | 0x19 |
| 0x3504 | ANA_WO_CTL_0 | 0x9d | 0x55 | 0xe1 |

Written for every variant: `0x3040 TOP_CTRL1 = 0xd2` (Linux resets to 0xd3), `0x304c OCP_CTL = 0xf6` when the load class is 4 or 6 ohm, `0x30a5 = 0xf1`, `0x30a0 = 0xf8`, `0x3090 = 0x6a`, `0x30aa = 0xe3`, `0x3091 = 0xd4`, `0x38a6 = 0x08`, `0x38a8 = 0x20`, `0x300b = 0xd1`, the digital DSM coefficients (equal to the Linux table), `0x3581/0x3582 = 0xff/0x03` (interrupts masked) at power down. After that, if the slave connection type is 1 (internal boost) it writes `0x3091 = 0x44`; type 2 writes `0x309a = 0x45`. Variant 7 falls into an error path.

Inference, used in patch 0011 and the DT: this unit is variant 2 (two-cell stack), 4 ohm, internal boost. Basis: the Argon report states two cells, `SlaveConnectionType = 1` and 4 ohm, the code branches match those statements, and the ACDB nominal Re (4.9 and 4.8 ohm) is a 4 ohm class. What I could not read is `DAT_1400570cc` (set from a structure filled elsewhere; its writer was not found in the time available). Unknown until the first log: that `0x3501` returns the two-cell value. Patch 0011 does not read `0x3501`; it trusts the DT.

What patch 0011 applies, only when the DT says two cells: the table column "variant 2" (except 0x3003, equal to the Linux default), `TOP_CTRL1 = 0xd2` (the Linux file already carries this as a commented suggestion from the vendor sources), `OCP_CTL = 0xf6` for 4 and 6 ohm, `OTP_REG_38 BST_CFG_SEL` for the internal boost, and the boost current limit without override (`0x44`: override off, limit 0x11) in place of the `0xd4` the Linux power-up writes. Not applied because Linux equality was not compared: `0x30a0`, `0x3090`, `0x30aa`, `0x30a5`, `0x300b`, the `0x3504` bits other than the stack field. Argon table values for 0x3003 to 0x3006, 0x3040, 0x304c, 0x3504, 0x38a6 are now reproduced by the code read above; Argon's row for 0x3091 is reproduced as the order 0xd4 then 0x44.

### 2.2 Sense gains, `FUN_1400328b8` (Verified, code)

The system gain index is in 0.5 dB steps (`0x21` is +16.5 dB, `0x2a` is +21 dB). `0x3020` (voltage sense front end) depends on it:

| Gain index | Gain | 0x3020 | Attenuation |
|:--|:--|:--|:--|
| 0x00, 0x12, -6 | 0, 9 dB, -3 dB | 0x07 | -12 dB |
| 0x15, 0x18 | 10.5, 12 dB | 0x27 | -15 dB |
| 0x1b, 0x1e | 13.5, 15 dB | 0x47 | -18 dB |
| 0x21, 0x24 | 16.5, 18 dB | 0x67 | -21 dB |
| 0x2a | 21 dB | 0x87 | -24 dB |

`0x3021` (current sense) for a 4 ohm load: 12 dB (`0x27`) for every index below `0x1b` and for `0x1b`, `0x1e`, `0x21`; 6 dB (`0x07`) for `0x24`; index `0x2a` is an error for 4 ohm. So at the +16.5 dB point Windows uses -21 dB and +12 dB. Linux hard-codes -24 dB (`VSENSE_M24_DB`), which Windows uses only at +21 dB: a 3 dB difference, a factor 1.41 in the resistance the DSP derives. Patch 0011 reads both from the DT; patch 0016 sets 21 and 12.

Unknown, and the most important unknown of this stage: the relation between the Windows "system gain" and the Linux `PA Volume` scale. Linux caps `PA Volume` at 6 (0 dB on its own scale); the Argon report equates that with a 16.5 dB reduction against Windows, which I could not verify. If Linux's gain at the cap corresponds to a lower Windows system gain, the matching sense attenuation is different (-12 dB at 0 dB). The DT value 21 is therefore a guess at the calibration operating point. The safety net is the calibration range check (section 4.3) and the hardware procedure (section 8), not the DT value.

### 2.3 Amplifier DC resistance measurement (Verified code, semantics Inference)

`FUN_140030790` and `FUN_140030ea0`: configure `0x3124`, `0x3123`, `0x301f`, `0x3020`, `0x3021` from a 12-byte table entry (four entries at `0x140012ec0`, chosen by a first measurement range), set `0x3016` bit 5, wait, read `0x3017`/`0x3018` (14-bit value, range code in bits 7:6), poll up to 150 times, then clear. Inference: an amplifier-internal measurement of the speaker DC resistance that Windows runs as a check. Unknown: the conversion to ohm. Not implemented. It is an independent way to cross-check the Re that SPv5 reports and a candidate for the first-run calibration (section 5).

### 2.4 Interrupts (Verified code)

At power-up Windows writes `INTR_MASK0 = 0x90` and `INTR_MASK1 = 0` (equal to the Linux reset values), at power-down `0xff` and `0x03`. So the amplifier raises its interrupts to the host while the amplifier plays. Patch 0013 enables the SoundWire implementation-defined interrupt and reads `INTR_STATUS0/1`. The meaning of the individual bits is Unknown.

### 2.5 Port map and reset lines

Verified from Linux source: `hamoa.dtsi` swr0 has `qcom,dout-ports = <9>` and `qcom,din-ports = <4>`, so the master has ports 1 to 13; ports 10 to 13 are the capture side, and only port 13 is configured as a 24-bit, 24 kHz port (`ports-word-length`, `ports-sinterval` index 12). The Argon claim that the right speaker's CPS uses master port 14 cannot be right for this controller (there is no port 14). Hypothesis (kept in the DT): the left and right CPS share master port 13 with different channel masks (patch 0013 uses `BIT(unique_id)`); VISENSE uses ports 10 and 11 (as the existing map). Verified by the Argon report from the DSDT (not re-read): two reset pins `tlmm 204` and `205`, which the pin controller source maps to `lpass_tlmm 12` and `13`; patch 0016 uses 12 for the left and 13 for the right speaker. Unknown: which physical speaker each pin resets; both are released before the bus enumerates, so the assignment does not matter for bring-up.

## 3. The reference series and what I took from it

`out/audio-speakers-spv5-references/` held three mails of a Qualcomm RFC (`[RFC PATCH 00/23] ASoC: qcom: AudioReach Active speaker protection for WSA884x`, 2026-10-23). I fetched the whole thread (23 patches) into the scratchpad and read patches 5, 7 and 13. The cover letter says the series was tested on a ThinkPad T14s Gen 7 (two WSA8845) and a Glymur CRD (four WSA8845). I wrote my own code; what I used are interface facts (Verified as quoted from that thread, not re-verified on a device):

- the graph property for control links is `0x08001061` and the intent list property is `0x08001062` (both also seen in the ACDB, so Verified twice);
- `PARAM_ID_SP_TH_VI_R0T0_CFG = 0x080011f5` with `{u32 num_ch; {s32 r0_q24; s16 t0_q6; u16 reserved}[]}`. This resolves a loose end of the Argon report: `0x080011f5` is a runtime parameter, not an ACDB value, so "not in the file" was expected;
- VISENSE is a SoundWire source port with `ch_mask 0x3` and the V/I stream is 8 kHz, 32-bit, one V/I pair per speaker;
- their tested setup carries no CPS feedback. Inference: CPS (class-H tracking) is not needed for the protection loop to work. The guard therefore makes CPS optional (`SP11CL_FLAG_CPS`, off by default in the generator).

Design difference to decide (open question for the orchestrator): the RFC puts the V/I capture DAIs on the playback back-end link, with an ASoC core flag (`multi_direction_codecs`), so the sense stream always runs with playback. My patches follow the task text: separate back-end links for V/I and CPS, and the guard refuses playback unless those streams already run. That needs a user-space supervisor that opens the capture streams first (section 8) and relies on the ADSP matching a control link across two graphs. The RFC design removes both problems and has hardware testing behind it, at the price of a core change. Recommendation: evaluate adopting the RFC design for the V/I link before the first hardware test; the guard, the supplement format, the amplifier patches and the calibration path are independent of that choice.

## 4. The gate (patch 0012 and 0015)

Playback on `WSA_CODEC_DMA_RX_0/1` of `microsoft,denali` is allowed only when all of this holds:

1. `sp11.nospk` is not on the command line;
2. no fault is latched;
3. the graph that holds the speaker protection module was started. The control links of the supplement are declared in that graph's open command, and the guard knows only that the commands succeeded, not what the ADSP did with them; the flag is set at graph start and cleared at stop;
4. the V/I stream is running (a graph with the VI module is started), and the CPS stream when the supplement says CPS is required;
5. a calibration was applied to both speakers: the VI module accepted `PARAM_ID_SP_TH_VI_R0T0_CFG` from a valid, range-checked unit file;
6. a nominal (not measured) calibration is accepted only with `sp11.allow_nominal=1`.

Otherwise `startup` and `prepare` return `-EOPNOTSUPP` before any SoundWire or DAPM power-up. Default state (no supplement, no calibration, no feedback stream): refused. Fail-safe by construction: every missing input closes the gate.

Unforgeable from user space: the state lives in the `sp11` module and is written only by kernel callers (`audioreach-sp11.c`, `wsa884x.c`). The module parameters are 0444, so they can be set on the command line and not at run time. There is no sysfs, ioctl, debugfs write or mixer control that changes the state; debugfs `sp11/guard` is read only. A latched fault is never cleared except by reboot. Residual: `root` can unload or replace modules, or write amplifier registers through a debug interface if one is built in; that is outside what a kernel gate can stop. The machine driver pins the module (symbol dependency).

Fault handling: the SPv5 diagnostics event `0x0800138c` and any enabled amplifier interrupt while the amplifier plays latch a fault; the guard then schedules the machine driver's mute (digital mute of the amplifiers) and later opens are refused. The event payload layout is Unknown (Argon: `condition 3` DC, `4` temperature, unverified). Therefore every such event latches, which can be a false positive if the module reports status events periodically. That is the safe direction; the first test shows it (section 8).

### 4.3 The range check as a sense-scaling check

The unit calibration must lie within 80 to 125 percent of the ACDB nominal Re (`audioreach-sp11.c`). A 3 dB error of the voltage sense scaling changes a measured resistance by 1.41 or 0.71, so the check refuses a calibration measured with the wrong front end. It does not catch smaller errors. It checks only the file; the DSP does not report Re back (no readback path is implemented).

## 5. Calibration (R0/T0) and the safe default

Windows keeps R0 and T0 per speaker (`R0CalQ24`, `T0CalQ6`) and re-measures after a 180 s silence (Argon, one value cross-checked by the orchestrator). The ACDB gives the nominal Re (Verified): 4.924 and 4.758 ohm (Q24 words 1 and 9 of parameter `0x08001535` on instance `0x4024`).

- Safe default: no `...-sp11cal.bin`, or one that fails the checks: the speakers stay muted. This is the state of every image until someone provides the file.
- Per-unit file, private, never in git: `qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-sp11cal.bin` (36 bytes: magic `SP11CA01`, flags, two channels of `{r0_q24, t0_q6}`, CRC-32). Written by `build-closedloop.sh --nominal-cal` (R0 from the ACDB, T0 25 C, flag NOMINAL) or `--measured R0L R0R T0L T0R`.
- Nominal start: allowed only with `sp11.allow_nominal=1` on the command line. Risk, honest: a real R0 that is 10 percent above the nominal makes the thermal estimate wrong by about 25 K (the temperature coefficient in the ACDB is 0.00406 per degree, Argon, unverified). The ACDB thermal limits are used unchanged. For the first audible test the volume stays at the minimum step regardless.
- Measured start (not implemented in the kernel): the DSP has a calibration mode (the RFC drives it with a mixer control and per-speaker events; this series does not implement it). Until it exists, the measured R0 can come from the amplifier DC measurement (section 2.3) once its scale is known, or from a meter on the speaker terminals; neither is available offline.

## 6. Stage 3: files and the topology

Written, private (`out/firmware-private/audio/qcom/x1e80100/`, mode 0600, git-ignored; only hashes are printed): `X1E80100-Microsoft-Surface-Pro-11-sp11cl.bin` (7180 bytes: one control link, 28 calibration records of instances `0x4024`, `0x4027`, `0x4028`, nominal Re). The file name is derived from what the kernel requests: `qcom/<card->driver_name>/<card->name>-sp11cl.bin`, the same pair as the topology `qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin` (`topology.c`, `audioreach_tplg_init`).

Content decisions, each from the ACDB (Verified as data, `0xb0000001`, keyless calibration set):
- links: only those with both peers in the subgraph: `0x4024:0x80000000 <-> 0x4027:0x80000000`, intent `0x08001204`; the CPS link `0x4028 <-> 0x4027:0x80000001` (intent `0x08001537`) only with `--with-cps`; the third link (`0x4157` to `0x40df`) leaves the subgraph and is dropped;
- calibration records: all 28 records of the three module instances. Records of the other instances (`0x4001` SAL, `0x4026`, `0x402b`, `0x4157` endpoints) are not sent: the topology will not use those instance ids;
- the Windows payload is sent as is; the driver sends its own `PARAM_ID_SP_VI_CHANNEL_MAP_CFG` afterwards, which overrides the ACDB channel map record.

Not written: the topology `.bin`. Reasons, in order of weight:
1. The V/I and CPS chains (`CODEC_DMA_SOURCE -> MFC -> SPEAKER_PROTECTION_VI`, ... `CPS_DATA_ROUTER`) end in a module that has no output in the ACDB graph. In the Linux topology model a capture back end is started from a front-end capture stream whose graph connects to the end of the chain. I did not find a tap point that keeps the ACDB graph intact; the vendor graph is a single subgraph with a splitter. This needs the design choice of section 3 (RFC style link, or an extra front end).
2. Instance ids: the ACDB module ids (`0x4024` and so on) must be used in the topology so the calibration records and links address the right modules; they lie outside the `0x6000` range the public topology uses for module instances. Whether the kernel or the ADSP rejects that is Unknown.
3. The speaker protection module in the playback chain needs a `src`-type widget between the logger and the MFC; I have the edit planned (text patch of the generated conf: logger destination to `0x4027`, new module section, one route line) but no way to test DAPM behaviour without the device.

The hook is `build-closedloop.sh`; the install contract for the image worker is in the README Requests.

## 7. Parameter table of the changes (what a reviewer can check)

| Item | Value | Grade | Source |
|:--|:--|:--|:--|
| 2S thresholds UVLO/BOP | 0x33/0x60, 0x22/0x44 | Verified (code) | `FUN_140032e10`; applying them to this unit is Inference |
| TOP_CTRL1 | 0xd2 | Verified | same |
| OCP_CTL for 4 and 6 ohm | 0xf6 | Verified | same |
| ANA_WO_CTL_0 two-cell | +0x80 (VPHX field 2) | Verified code, Inference mapping to the field | 0x9d = 0x1d + 0x80 |
| Boost limit, internal boost | 0x44 after 0xd4 | Verified | same |
| Sense front end at 16.5 dB | -21 dB, +12 dB | Verified code; operating point Inference | `FUN_1400328b8` |
| VISENSE port | source, ch_mask 0x3, 8 kHz | Verified in the RFC thread, consistent with Argon | RFC 05 |
| CPS port | source, one channel per speaker | Hypothesis | Linux DT port counts |
| WSA TX_0 and TX_2 DMA indexes | 1 and 3 | Verified in Argon only, not re-read | Argon section 3.1 |
| R0/T0 parameter | 0x080011f5 | Verified in the RFC thread | RFC 13 |
| Control link properties | 0x08001061, 0x08001062, one intent | Verified (ACDB, RFC 07) | ACDB decode |
| Fault payload layout | any event latches | Unknown | needs a device log |

## 8. Stage 4 plan: first hardware test

Prerequisites: a kernel containing 0001, 0002, 0004 to 0016; the `m13-spk` DTB (D26 marker plus the closed-loop fragment); private image mode with `...-sp11cl.bin` installed; no `sp11cal` file yet; the kill switch known. Per `no-install-until-components-done` it is a live USB only. Operator present, quiet room, volume UI at the minimum, no music in the supervisor.

Kill switch: `sp11.nospk` on the kernel command line (boot entry argument). The guard then refuses every WSA playback open, and the mute callback is registered but never needed. Add it to a dedicated safe entry (`SP11 speakers kill`) next to `SP11 speakers (gated)`. A power-off is the second kill switch.

Step A, silent bring-up (no sound possible): boot `m13-spk`. Read: `dmesg` for the closed-loop file ("closed-loop speaker protection data loaded: 1 links, 28 records"), the card, both `wsa884x` probes, the amplifier init (no errors), `/sys/kernel/debug/sp11/guard` (expect `allowed: no`, reason "the closed-loop graph is not up" and later "no R0/T0 calibration"), `aplay -D hw:0,0 /dev/zero -d 1` must fail with `Operation not supported`.

Step B, feedback streams, still no calibration: start the V/I capture stream (a `arecord` on the V/I front end, once the topology offers one: section 6) and check `guard`: `vi_streams: 1`. Collect: `dmesg`, `/proc/asound/cards`, `amixer -c 0 contents`, the SoundWire slave status in `/sys/bus/soundwire/devices/*/`, and that the V/I stream carries data (record 5 s of the 4-channel 8 kHz stream; the channels must show a pilot-tone level and noise, not zeros).

Step C, calibration at minimum volume: install a NOMINAL `sp11cal` file (`build-closedloop.sh --nominal-cal`) and boot with `sp11.allow_nominal=1`; or install a measured file. Start the V/I stream, then open the playback stream with silence (`aplay -D hw:0,0 /dev/zero`). Expect: `speaker calibration applied (nominal)`, `guard` allowed. If the supervisor starts playback before the V/I stream: refused (by design).

Step D, first sound, lowest step: `speaker-test` or a quiet tone at the minimum, 1 s, then stop. Stop at once at distortion, buzzing, heat, or any kernel message from the amplifier. Never raise the controls; the caps of 0001, 0002, 0004, 0005 stay.

What to read, during A to D:
- `dmesg | grep -E 'sp11|wsa884x|audioreach|q6apm'`: fault lines (`speaker fault latched`), `amplifier interrupt 0x.. 0x..` with the PA state, `speaker protection diagnostics event` with its first two words, calibration messages;
- `/sys/kernel/debug/sp11/guard` before, during and after each step;
- the amplifier temperature: `cat /sys/class/hwmon/*/temp1_input` (the amplifier die; read when the PA is off per the driver);
- V/I levels: the recorded V/I stream. Compute the apparent resistance of silence plus pilot tone offline: V/I scaled by the front-end gains; compare with 4.9 and 4.8 ohm (a meter measurement of the speaker terminals first, with the tablet off, is better);
- temperature estimate of the coil: not available (no readback implemented). The calibration range check and the V/I levels are the only indications; this is a gap, listed in the Requests as a follow-up (RFC patches 17 and 18 show how a live T0 and a calibration state can be exposed).

What to collect (private, hashes in git only): the collector set of `d26-audio.md` section 7, plus `dmesg` complete, `guard` snapshots, the recorded V/I stream (private), `amixer` dump, `lsmod`, the SHA-256 of both private files, `cat /proc/cmdline`, the DTB name, and the answers to the open questions below.

Pass for step A: no playback possible, no amplifier output. Pass for B: V/I data on the stream. Pass for C: calibration applied. Pass for D: a quiet, clean tone with no fault for 10 s and `guard` still allowed. A fault latch at any step is a finding, not a failure: read the words, power off.

## 9. Open questions that only the device answers

| # | Question | Grade now | Answer from |
|:--|:--|:--|:--|
| H1 | does `0x3501` read as the two-cell value, and is the variant 2 table the right set | Inference | amplifier register dump at probe (read-only), compare with 2.1 |
| H2 | the relation between the Windows system gain and the Linux PA scale; the sense attenuation to use | Unknown | Re from the V/I stream against a meter; try -21 and -12 dB at silence |
| H3 | does the ADSP accept a control link declared by one graph while the peer is in another | Unknown | graph open result in dmesg |
| H4 | is a V/I capture back end startable without extra topology work | Unknown | step B |
| H5 | SoundWire master DAI index for the feedback links (9 and 12 in the DT), CPS master port and channel masks | Hypothesis | probe and stream start logs |
| H6 | amplifier interrupt bits, and whether any bit fires at idle | Unknown | step A logs |
| H7 | the SPv5 diagnostics payload and whether it is periodic | Unknown | event log |
| H8 | does the ADSP use R0/T0 as given and report the thermal state | Unknown | needs a readback (not implemented) |
| H9 | does the Windows module-instance range (0x4000) load in the Linux topology | Unknown | topology load log |
