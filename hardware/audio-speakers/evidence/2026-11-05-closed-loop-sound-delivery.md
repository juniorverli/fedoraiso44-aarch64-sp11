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
