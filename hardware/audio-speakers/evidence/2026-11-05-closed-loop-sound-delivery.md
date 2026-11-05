# Closed-loop speaker sound: delivery path — 2026-11-05

Scope: the live ISO entry that plays sound through the speaker protection graph
with every guard gate in the loop. This note records the mechanism and the
commands; it is not device evidence. The device test still decides whether the
DSP accepts the graph.

## What plays the sound

Line 24 `SP11 debug, closed-loop audio (needs calibration)` boots the `m15-cl`
DTB (d26 speaker policy, `-CL` sound model) with `msm.skip_gpu=1` and
`sp11.allow_nominal=1`. The `-CL` model makes `audioreach_tplg_init()` request
`qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-CL-tplg.bin`; the private image
installs that topology together with `-CL-sp11cl.bin` (1 control link, 28
calibration records, flags 0 = CPS not required) and `-CL-sp11cal.bin`
(`SP11CA01`, 2 channels, flags 1 = nominal, R0 = the supplement's nominal Re,
T0 = 25 C, CRC valid).

The playback back end is `MFC -> SP -> LOG -> CODEC_DMA_RX -> WSA`; the sense
back end is `CODEC_DMA_TX -> LOG -> SP_VI` with no output. Playback is ordinary
PipeWire output; nothing else is started.

## What satisfies the guard

`sp11_guard_unmute_check()` runs on every `wsa884x_mute_stream(unmute)`. It
allows the amplifier only when all of these hold:

1. mode closed-loop (topology has SP and the policy says d26);
2. PA/RX/MIX caps installed (the D26 UCM ceiling);
3. `sp11cl` loaded (the guard's `loaded`);
4. graph up (`SP` graph started);
5. SP module enabled (its SET_CFG and enable returned 0);
6. the V/I sense stream running (`SP_VI` graph started);
7. calibration applied, its mask full and its graph identical to the running
   VI graph, and, when nominal, `sp11.allow_nominal=1`;
8. no fault latch and, with degraded diagnostics, non-nominal calibration;
9. CPS not required (the supplement says flags 0).

Item 6 is what `sp11-closed-loop-sense.service` provides. The unit runs only
when the kernel command line has `sp11.allow_nominal=1 sp11.entry=debug` and not
`sp11.nospk`. It opens the MultiMedia5 trigger (the WSA sense capture PCM),
starts the back end and advances the application pointer with
`snd_pcm_forward()` without reading a single sample; when the PCM leaves
RUNNING the unit exits and systemd restarts it, which re-prepares the VI graph
and re-applies R0/T0. Before this unit existed nothing started the sense stream
on the sound path, so the guard refused every unmute and the closed loop could
never make sound.

## Device procedure

1. Boot line 24 (about 30 s to GNOME).
2. `systemctl status sp11-closed-loop-sense` — active (running), no restart
   loop. `journalctl -u sp11-closed-loop-sense -b` shows
   `holding hw:C,4 MultiMedia5 ... no sample is read`.
3. `cat /sys/kernel/debug/sp11/guard` (or `/usr/libexec/sp11/guard-report`):
   the V/I stream, graph, SP module and calibration must be read as MET.
   `dmesg | grep -i sp11` must show
   `closed-loop speaker protection data loaded` and
   `speaker calibration applied (nominal)`.
4. Play any sound at low volume. The amplifiers unmute on the first playback
   start after the sense stream is up; if the first login sound raced the
   service, stop and start playback once.
5. Kill switch: add `sp11.nospk` to the line (or power off). A diagnostics
   event from the DSP latches a fault and mutes until reboot, by design.

If any gate is unmet the speakers stay muted and the guard report names the
gate: that is the fail-closed result. The D26 entries 1 to 4 keep the public
sound path.

## Not claimed

- No device run has booted the `-CL` topology yet. The DSP may reject the SP
  module configuration or one of the 28 records; each failure is logged with
  its parameter id and leaves the guard closed.
- The nominal file is a test calibration, not a measurement of this unit. The
  measured path is kernel patch 0028 (`EVENT_ID_VI_CALIBRATION` 0x0800119f and
  `EVENT_ID_VI_PER_SPKR_CALIBRATION` 0x08001511 from the Windows parser).
- CPS (`0x4028`) is still absent from the topology; the supplement keeps the
  CPS-not-required flag set because the m4 container does not exist.
- Post-installation: the installed system gets the live root's private files,
  but its default boot entry uses the packaged DTB and public topology. A
  closed-loop installed entry needs the same DTB and arguments staged
  post-installation.

## Device result of the first closed-loop boot (2026-11-05)

Boot `94114431-7056-4703-8a14-7f17ff485d3d`, entry `spk`, kernel rev27. The CL
topology loaded under the `-CL` model, the card came up with MultiMedia1..5, and
the SP module accepted all 28 calibration records (`SET_CFG ... rc=0`) and
enabled (`SP module enable succeeded`). One command failed:

    Error (3) Processing 0x0100100e cmd
    DSP returned error[100100e] 3
    SP diagnostics unavailable; protection is degraded

`0x0100100e` is `APM_CMD_REGISTER_MODULE_EVENTS`. REA of qcadcm8380.sys
(`gsl_graph_register_custom_event`, 0x140062100) shows the Windows GSL client
sending that command with payload size **0x10** and rejecting anything smaller;
the kernel's `apm_module_register_events` carries two extra fields (24 bytes).
Kernel patch 0029 (rev28) sends the 16-byte form first and keeps the 24-byte one
as a fallback. With `diagnostics_degraded` set and a nominal calibration the
guard refuses by design, which is why that boot could not unmute.

The guard snapshot also shows what the `spk` entry does not do: it does not start
the V/I sense stream (`vi_streams: 0`), and on that entry the sense holder is not
enabled (it runs only with `sp11.entry=debug`). The closed-loop audio entry (line
24) is the one that holds the sense trigger and has `sp11.allow_nominal=1`.

## Boot-parameter defect found in the same boot (fixed in rev29)

The guard module stored its parameters with the prefix `sp11.`, but the module
loader splits `sp11.allow_nominal=1` at the dot, takes `sp11` as the module name
and matches the bare name. The boot log proves it:

    sp11: unknown parameter 'allow_nominal' ignored
    sp11: unknown parameter 'entry' ignored

so `allow_nominal` stayed false and the guard snapshot reported
`allow_nominal: 0`. The nominal calibration could therefore never unmute, and
the documented kill switch `sp11.nospk` was silently ineffective for the same
reason. Patch 0030 (rev29) uses an empty MODULE_PARAM_PREFIX for the module
build and keeps `sp11.` for built-in builds.

## Device confirmation of the two rev29 fixes (2026-11-05, 20:17)

Boot `a160e89a-e9fd-42bd-af2e-9510d6491c76`, entry `spk`, kernel
`7.3.0-65.sp11.29.fc44.aarch64`:

    sp11: selected closed-loop speaker mode
    closed-loop speaker protection data loaded: 1 links, 28 records
    SP module enable succeeded

- No `unknown parameter 'allow_nominal'` line; the guard snapshot reports
  `allow_nominal: 1`.
- No `Error (3) Processing 0x0100100e`; the 16-byte event registration was
  accepted and `diagnostics_degraded` stayed clear.
- The `safe` boot of the same ISO (`3b576987`) has zero failed units and the
  D26 open-loop mode, so rev29 did not regress the public path.

The `spk` entry still reports `vi_streams: 0`, by design: only the closed-loop
audio entry (line 24) starts the automatic sense holder.

## Measured-calibration binding (rev30)

The DSP delivers a module event with the graph that owns the receiving module.
The calibration events are registered on the SP module of the playback graph,
so `sp11_guard_vi_calibration()` bound `cal_graph` to the playback graph and a
measurement arriving during playback would have replaced a valid nominal
calibration with one the identity check rejects. Patch 0031 binds a measurement
to the unique running V/I graph (zero or several running V/I graphs stay
refused) so a real measurement can only strengthen the guard.
