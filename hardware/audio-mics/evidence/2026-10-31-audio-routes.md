# Audio routes other than the built-in speakers: DisplayPort, USB audio, Bluetooth, capture gain, default policy

Date: 2026-10-31. Inputs: private device logs `m13-20261031/93b13406-...` and `m14b-20261031/ca890f35-...` (`extra-audio.txt.gz`, `devicetree.dts.gz`, `dmesg.txt.gz`; nothing from them is copied here except control names and numeric ranges), Fedora 44 containers (`alsa-ucm` 1.2.16.1, `alsa-ucm-utils` 1.2.16, `wireplumber` 0.5.18, `pipewire-libs` 1.6.11), the M14 image package list `out/image-work/20261031T133710Z/out-build/Fedora.aarch64-44.packages` (the build record). Not used: REA. No kernel patch touched, nothing built, nothing run on the device. Speakers: untouched on purpose (S1/D26); no file in this change writes a speaker control, a WSA mixer route or a speaker volume.

## What was added (all under `hardware/audio-mics/userspace/`)

| Item | File | What it does |
|:--|:--|:--|
| UCM hook | `overlay-ucm-fix/.../x1e80100.conf` (changed: one extra `True.Include` line inside `If.SURFACEPro11`; every other branch is Fedora's text) | After the Surface Pro 11 card file, includes `SP11-Audio.conf` |
| Verb replacement | `overlay-audio-routes/usr/share/alsa/ucm2/Qualcomm/x1e80100/SP11-Audio.conf`, `SP11-HiFi.conf` | A later `SectionUseCase."HiFi"` replaces the earlier one; the new verb file includes the speaker owner's `Surface11-HiFi.conf` first (microphones in the default profile, speakers only in the gated speaker entry) and our route layer second |
| Route layer | `SP11-Routes.conf` | `Mic` capture gain include; `HDMI0` and `HDMI1` included only if the card has the `DP0 Jack` / `DP1 Jack` controls (`ControlExists`) |
| Capture gain | `SP11-MicGain.conf` | `VA_DEC0 Volume` and `VA_DEC1 Volume` = 98 (+14 dB) after the base DMIC sequences |
| DP0 | `SP11-DP0.conf` | Device `HDMI0`: `DISPLAY_PORT_RX_0 Audio Mixer MultiMedia3` = 1, PCM `hw:${CardId},2`, priority 200, `JackControl "DP0 Jack"` |
| DP1 | `SP11-DP1.conf` | Device `HDMI1`: `DISPLAY_PORT_RX_1 Audio Mixer MultiMedia4` = 1, PCM `hw:${CardId},3`, priority 200, `JackControl "DP1 Jack"` |
| Selection policy | `overlay-audio-routes/usr/share/wireplumber/wireplumber.conf.d/52-sp11-audio-routes.conf` | Node priorities (below) |
| dconf | `overlay-audio-routes/etc/dconf/db/distro.d/91-sp11-audio-routes` | `volume-step=3` (not locked) |
| Collector | `overlay-audio-routes/etc/sp11-log-collector.d/audio-routes.sh` | Read-only snapshot to `extra-audio-routes.txt` |
| Tests | `tests/ucm-routes-test.sh`, `tests/mic-gain-check.sh`, `tests/va-dec-volume.fixture.txt` | See "Tests run" |

The DP devices mirror the `HDMI0`/`HDMI1` devices of Fedora's `T14s-HiFi.conf` (same device names, same `DISPLAY_PORT_RX_n Audio Mixer` control family, same jack control names, priority 200 against the speaker's 100). Differences: this card's front ends are `MultiMedia3` and `MultiMedia4` (PCM 2 and 3, from the device dump), not `MultiMedia1`; no `ConflictingDevice` (each port has its own front end, so both can play at once); no `RX_CODEC_DMA_RX_0` line (that is a headphone path this card does not have).

## Verified

| # | Fact | Source |
|:--|:--|:--|
| V1 | Card `x1e80100`: capture PCMs `MultiMedia2` (device 1) and `MultiMedia5` (device 4); playback PCMs `MultiMedia1`, `MultiMedia3`, `MultiMedia4` (devices 0, 2, 3) | `extra-audio.txt.gz` `arecord -l`, `aplay -l`, PCM list (M14b) |
| V2 | The mixer has `DISPLAY_PORT_RX_0 Audio Mixer MultiMedia3` and `DISPLAY_PORT_RX_1 Audio Mixer MultiMedia4` (boolean, 2 values, off), plus `stream2.vol_ctrl2 MultiMedia3 Playback Volu` and `stream3.vol_ctrl3 ...MultiMedia4...` (0..65535, boot value 8192) | same dump, numids 35, 37, 33, 34 |
| V3 | The dump has `Headphone Jack` and `Mic Jack` (CARD controls) but **no `DP0 Jack` or `DP1 Jack`** | same dump, numids 9, 10 |
| V4 | The sound node of the running DTB has only `va-dai-link` ("VA Capture"); there is no DisplayPort dai link | `devicetree.dts.gz` `/sound` (M14b) |
| V5 | The kernel creates the `DPn Jack` only for a dai link whose CPU dai is `DISPLAY_PORT_RX_n`: `sc8280xp.c:176-208` and `x1e80100.c:31-66` call `qcom_snd_dp_jack_setup` from the link init; the widget names are `common.c:16-20`. Upstream boards declare the links in the DT: `hamoa-iot-evk.dts:628-658` (`dp0-dai-link` with codec `&mdss_dp0`, CPU `&q6apmbedai DISPLAY_PORT_RX_0`, platform `&q6apm`, same for 1), `x1e80100-crd.dts:233-237` | `sources/linux/...` |
| V6 | Our DT has `&mdss_dp0` and `&mdss_dp1` enabled (the two USB-C ports) and they carry `#sound-dai-cells = <0>` from `hamoa.dtsi:5693` and `:5782`; `&mdss_dp3` (the eDP panel) deletes it | `x1-microsoft-denali.dtsi:877-893`, `hamoa.dtsi` |
| V7 | `VA_DECn Volume`: integer 0..124, `dBscale-min=-84.00dB,step=1.00dB,mute=1`, boot value 84 on DEC2/3 and 100 once the old UCM ran. Source: `SOC_SINGLE_S8_TLV("VA_DEC0 Volume", CDC_VA_TX0_TX_VOL_CTL, -84, 40, digital_gain)` with `DECLARE_TLV_DB_SCALE(digital_gain, -8400, 100, -8400)`, so dB = step - 84, step 0 = mute, step 124 = +40 dB | `extra-audio.txt.gz` numids 1, 2, 3; `sound/soc/codecs/lpass-va-macro.c:174`, `:1312-1315` |
| V8 | Windows endpoint `MicArray1`: microphone volume +14.0 dB default, +24.0 dB maximum, 2 PDM digital microphones on `VA_CODEC_DMA_TX_0` | `hardware/audio-speakers/evidence/2026-10-30-argon-rea-report.md` lines 8 and 34 (INF `surface_asdext8380`, not re-read by a second reader) |
| V9 | Fedora's DMIC enable sequences write `VA_DEC0/1 Volume 100` (+16 dB), above the Windows default | `ucm2/codecs/qcom-lpass/va-macro/DMIC0EnableSeq.conf` in `alsa-ucm` 1.2.16.1 |
| V10 | The image already has: `pipewire`, `pipewire-libs`, `pipewire-alsa`, `pipewire-pulseaudio`, `pipewire-utils` 1.6.11; `wireplumber` 0.5.18; `bluez` 5.87; `libsbc` 2.1; `fdk-aac-free` 2.0.3; `liblc3` 1.1.3; `libldac` 2.0.2.3; `spandsp`; `soxr`; `gnome-bluetooth` 47.2; `alsa-lib`, `alsa-ucm`, `alsa-utils` 1.2.16; `pulseaudio-utils` (`pactl`); `gnome-settings-daemon` 50.1; `dconf` | M14 package list |
| V11 | `pipewire-libs` 1.6.11 ships the Bluetooth SPA plugin and codecs: `libspa-bluez5`, `sbc`, `aac`, `ldac`, `lc3`, `faststream`, `g722`, `opus`, `opus-g`, `hfp-cvsd`, `hfp-msbc`, `hfp-lc3-a127`, `hfp-lc3-swb` (so A2DP SBC/AAC/LDAC/LC3 and HFP CVSD/mSBC/LC3). No separate `libspa-bluetooth` package exists in Fedora 44 | `rpm -ql pipewire-libs` in the Fedora 44 container; `rpm -qR` lists `libsbc`, `libfdk-aac`, `liblc3`, `libldacBT_*` |
| V12 | **`alsa-ucm-utils` (package of `alsaucm`) is not in the image.** `audio.sh` and the new collector call `alsaucm`; on the device the call fails with "command not found" | package list (no row), `rpm -qf /usr/bin/alsaucm` in the container |
| V13 | Merge behaviour of alsa-lib 1.2.16 UCM (tested with `alsaucm`): a second `SectionUseCase."HiFi"` pulled in by a later `Include` replaces the earlier one without error; a second `Syntax` key in an included file is a merge error ("compound type expected"); a `SectionDevice` of a later include is merged after the nested-include sequences of an earlier one; `ControlExists` needs a real card (on a virtual card: "cannot determine control device") | `userspace/tests/ucm-routes-test.sh` and the experiments behind it |
| V14 | WirePlumber 0.5.18 ranks default nodes by `priority.session` (or `priority.driver`), then by device group, then by route priority, then by serial; a node with no `priority.session` ranks 0 unless the ALSA/Bluetooth monitor sets one. `monitor.alsa.rules` and `monitor.bluez.rules` accept `update-props` and are merged from `wireplumber.conf.d` drop-ins (Fedora's own `alsa-vm.conf` does it) | `/usr/share/wireplumber/scripts/lib/node-utils.lua`, `default-nodes/find-best-default-node.lua`, `monitors/alsa.lua`, `monitors/bluez/name-node.lua` |
| V15 | `wireplumber.conf` defaults: `device.routes.default-source-volume` 1.0 (0 dB, so the PipeWire layer adds no gain on top of the hardware step), `device.routes.default-sink-volume` 0.064 (the speaker overlay lowers it to 0.05), `bluetooth.autoswitch-to-headset-profile` true | `/usr/share/wireplumber/wireplumber.conf` |

## Capture gain: derivation

`VA_DECn Volume` step = dB + 84 (V7). Windows default +14.0 dB gives step **98**; Windows maximum +24.0 dB gives step **108**; the control's own maximum, step 124, would be +40 dB. The previous profile wrote 100 (+16 dB, V9). `SP11-MicGain.conf` now writes 98 on both decimators after the base sequences; `tests/mic-gain-check.sh` derives 98 and 108 from the control dump (the fixture, or any `amixer contents` dump, gzip accepted) and fails if the UCM file writes anything else or more than the cap. UCM cannot cap a control a user sets by hand, so +24 dB is the ceiling of this file, not of the control (kernel-side cap: request below, optional).

## Selection policy (WirePlumber)

| Direction | Node | `priority.session` | Reason |
|:--|:--|:--|:--|
| Output | Bluetooth `bluez_output.*` | 3000 | plugged/connected beats built-in |
| Output | USB audio `alsa_output.usb-*` | 2500 | same |
| Output | Built-in card `alsa_output.platform-sound.*` (DisplayPort 1000; the speaker does not exist in the default profile) | 1000 | within the card the route priority orders them: DisplayPort 200 over speaker 100 |
| Input | Built-in `alsa_input.platform-sound.*` | 2000 | default capture stays the built-in microphones |
| Input | USB `alsa_input.usb-*`, Bluetooth `bluez_input.*` | 1000 | selectable, never taken by default; also keeps a Bluetooth headset in A2DP (V15 autoswitch only reacts to a recording client) |

USB class audio needs no UCM; the rule above is the only thing that touches it. The DisplayPort sinks exist only while the jack control reports a cable, so an unplugged port offers no sink.

## Inference

| # | Statement | Rests on |
|:--|:--|:--|
| I1 | **DisplayPort audio cannot work on the current DTBs.** The front-end PCMs and mixer controls exist (V1, V2) because the topology defines them, but without a `dp0-dai-link`/`dp1-dai-link` the card has no backend for `DISPLAY_PORT_RX_n`, no `DPn Jack`, and the DP codec of the controller is never bound. The UCM layer is therefore dormant by design (the `ControlExists` gate) until the kernel owner adds the two links | V3, V4, V5, V6 |
| I2 | The two links to add, copied from the EVK/CRD shape: `dp0-dai-link { link-name = "DP0 Playback"; codec { sound-dai = <&mdss_dp0>; }; cpu { sound-dai = <&q6apmbedai DISPLAY_PORT_RX_0>; }; platform { sound-dai = <&q6apm>; }; }` and the same with `mdss_dp1` and `DISPLAY_PORT_RX_1`. Not applied (kernel and DT are not this worker's, and the kernel DTB safety profile has a narrow microphone exception that must be widened to allow DP links without any WSA link) | V5, V6 |
| I3 | Front end to backend pairing is taken from the mixer control names (`...RX_0... MultiMedia3`, `...RX_1... MultiMedia4`); PCM index = FE number - 1 (`MultiMedia3` is device 2) | V1, V2 |
| I4 | The Windows +14 dB endpoint gain maps to the VA decimator digital gain because the microphones are PDM digital and the VA macro decimator is the only gain stage in the capture path of the topology (stream sub-graph without processing modules, `2026-10-30-mics-plan.md`); an ACDB graph gain on top, if any, is not visible here | V7, V8, mics plan Q2 |
| I5 | WirePlumber node name stems: the built-in card is the platform device `sound`, hence `alsa_{input,output}.platform-sound.*` (the usual name of a Qualcomm platform sound card); if the real name differs, the built-in rules do not match and the USB/Bluetooth priorities still hold over whatever ACP assigns | usual Fedora/Qualcomm naming; V14 |
| I6 | Without a `Speaker` device and with no DP cable, the profile has no playback device, so the default sink is WirePlumber's fallback until a DP, USB or Bluetooth sink appears. That is intended for S1 and costs nothing: the speaker path is controlled elsewhere | V1, UCM content |
| I7 | A Bluetooth headset connects and plays (A2DP) and, when chosen as input, uses mSBC/LC3 HFP, from the package set alone (V10, V11) | V10, V11 |

## Unknown (only the device can answer)

| # | Unknown | What answers it |
|:--|:--|:--|
| U1 | Whether the DP backend binds on this SoC once the two links exist (DP audio over the retimer/USB-C DP alt mode, jack plug detection, sample rates the monitor's EDID offers) | Boot a DTB with the links; `aplay -l`, `amixer -c 0 cget iface=CARD,name='DP0 Jack'` with and without a monitor; `speaker-test` is **not** used (the speakers are off, but a DP monitor can be loud: play `aplay -D hw:0,2` at the minimum level) |
| U2 | Whether the measured level with step 98 is sane: clipping, noise floor, left/right balance, the Windows level at the same sound pressure | `arecord -D hw:0,1 -f S16_LE -r 48000 -c 2 -d 5`, then `sox ... stats`: peak of normal speech at 30 cm should sit around -12 to -6 dBFS; adjust step by the measured offset, never above 108 |
| U3 | Whether `stream2/3.vol_ctrl` (default 8192 of 65535) is unity for the DP streams. The UCM does not write it (upstream does not); WirePlumber's 5 % software volume starts every new sink low regardless | First DP play: read the control, compare the level with 8192 and with 65535 |
| U4 | The real `node.name` values (platform-sound stem, `HiFi__HDMI0__sink` style) and the resulting `priority.session` | `extra-audio-routes.txt` on the next boot (the collector prints `pw-dump` priorities) |
| U5 | USB-C headset/dongle: that a USB class audio device appears and beats DP/built-in as intended | Plug one; `wpctl status`, `pactl get-default-sink` |
| U6 | Bluetooth A2DP/HFP end to end (needs the Bluetooth controller to work, `bluetooth` component, and a peer) | Pair a headset on the device |
| U7 | Whether WirePlumber accepts a UCM profile whose only playback devices are conditional (no `Speaker`) without logging errors | `journalctl --user -u wireplumber` after the first boot with this overlay |
| U8 | The aggregate effect of `ControlExists` on a real card (it only fails on a virtual one) | `alsaucm -c hw:0 list _devices/HiFi` on the device (the collector prints it) |

## Tests run (offline, Fedora 44 container, 2026-10-31)

- `sh /hw/audio-mics/userspace/tests/ucm-routes-test.sh`: ALL PASS (25 checks). Case A (no DP jack controls): only `Mic`, no `Speaker` (S1), and a Surface Pro 12in DMI string still gets Fedora's profile with no `HDMI`. Case B (jack condition true): `Mic`, `HDMI0`, `HDMI1`; PCMs `hw:<card>,1`, `,2`, `,3`; jack names; priority 200; the Mic enable log ends with `VA_DEC0 Volume=98`, `VA_DEC1 Volume=98` after Fedora's 100; DP enable logs contain exactly the `DISPLAY_PORT_RX_n ... MultiMedia3/4=1` routes and no WSA, `Spkr`, `PA Volume`, `RX_CODEC` or `MultiMedia1` line. Case C (the gated speaker verb of `overlay-speakers`): the speaker entry keeps its `Speaker` device and gets the same gain and DP layer. (`cset` lines were turned into `exec` logging in the test copies, so the order is observed, not assumed.)
- `sh tests/mic-gain-check.sh` (fixture, and the private M14b dump): derives 98 and 108, PASS.
- `shellcheck -s sh` on the three new scripts: clean (the older `ucm-syntax-test.sh` has two info notes, not changed).
- `spa-json-dump` parses the WirePlumber drop-in; `dconf compile` accepts the dconf file; `gnome-settings-daemon` 50.1 schema has `volume-step` (default 6, range 1..20).
- Collector: `bash -n` clean; the address/serial mask was tested with a Bluetooth address, a USB node name and a serial string.

## Requests (also in the README)

- **image:** install `overlay-audio-routes/` and the changed `overlay-ucm-fix/` x1e80100.conf; re-pin the `x1e80100.conf` hash in `check-m14-payload.py` and pin the seven new files; keep the `fix.count('MICROSOFT-Surface-Pro-11.conf') == 1` assertion (still true). Add package `alsa-ucm-utils` (V12). Install `audio-routes.sh` into `/etc/sp11-log-collector.d/`. Run `dconf update` (already done by `config.sh` for the speaker overlay). L0 check: run `ucm-routes-test.sh` and `mic-gain-check.sh` against the ISO tree.
- **kernel (DT):** add `dp0-dai-link` and `dp1-dai-link` (I2) to a DTB variant, and widen the DTB safety exception to allow DP links with no WSA link. Optional: a `snd_soc_limit_volume` for `VA_DEC0/1 Volume` at 108 in `x1e80100.c` so +24 dB is a hard ceiling.
- **audio-speakers owner:** nothing is edited in their files; `SP11-HiFi.conf` includes their `Surface11-HiFi.conf` by name, so that file name must stay.
- **orchestrator:** `hardware/audio-mics/userspace/quality/acdb_usecases.py` is untracked in this worktree and not from this session; it was left alone.
