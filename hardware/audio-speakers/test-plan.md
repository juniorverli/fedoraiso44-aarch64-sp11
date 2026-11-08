# audio-speakers test plan

## 2026-11-08: install entry, pre-audible check

The following is an install-entry check; it does not itself authorize an audible step. The install entry boots the same m15-cl closed-loop configuration as the debug entry: kernel patch 0033 selects `SP11_MODE_CLOSED_LOOP` only with `sp11.allow_nominal=1` plus the SP module in the parsed topology, patch 0032 installs the 84/17 maxima only in that mode, and the amplifier unmute stays guard-gated on every playback start (SP, V/I stream, calibration identity, CPS policy, fault latch). The pre-audible precondition is therefore the live guard state, not a lower cap: before any audible step, confirm that the guard reports `CLOSED_LOOP` with SP, VI and matching calibration, that the Speaker sink and Mic source exist, and that a refused or failed parse would leave 81/6 and reject the 84 write. No `sp11.nospk` bypass, fault clearing, tone or audible test is authorized by this document.

After those changes are reviewed and built, the operator boots the **install entry**. From the active graphical user's session, without opening a playback PCM, record exit status and:

```bash
cat /proc/cmdline
tr -d '\0' </proc/device-tree/sound/model; printf '\n'
wpctl status
pw-dump > /tmp/sp11-install-pw.json
python3 - <<'PYGRAPH'
import json
with open('/tmp/sp11-install-pw.json') as f:
    for obj in json.load(f):
        p = (obj.get('info') or {}).get('props') or {}
        if p.get('media.class') in ('Audio/Sink', 'Audio/Source'):
            print(obj.get('id'), p.get('media.class'), p.get('node.name'),
                  p.get('node.description'), p.get('device.id'), p.get('api.alsa.pcm.card'))
PYGRAPH
wpctl get-volume @DEFAULT_AUDIO_SINK@
systemctl --user status sp11-audio-defaults.service sp11-audio-safety.service sp11-closed-loop-sense.service --no-pager
journalctl --user -b -u sp11-audio-defaults.service -u sp11-audio-safety.service -u sp11-closed-loop-sense.service --no-pager
sudo cat /sys/kernel/debug/sp11/guard
sudo journalctl -k -b --no-pager | grep -Ei 'sp11:|speaker protection|speaker volume caps|calibration|feedback|wsa884|fault'
amixer -c 0 cget name='SpkrLeft PA Volume'
amixer -c 0 cget name='SpkrRight PA Volume'
```

Require `sp11.entry=safe`, `sp11.allow_nominal=1`, the CL sound model, the actual selected m15-cl DTB, a **built-in Speaker Audio/Sink and Mic Audio/Source** (not MultiMedia5), verified by node properties and `wpctl inspect <id>`, and a muted built-in sink. Require the holder active and holding the identified MultiMedia5 capture without errors or restart loop; require guard `mode: closed-loop` (CLOSED_LOOP), `loaded: 1`, `caps_ready: 1`, `vi_streams` at least 1, `cal_mask: 0x3`, `cal_graph_matches_vi: 1`, `vi_ambiguous: 0`, `fault: 0`, `nospk: 0` and the expected nominal policy. Confirm SP is present from the selected CL topology and policy/loader evidence and VI is present from the active holder and guard; record the actual loaded firmware and calibration identities. Check all PA/RX/MIX maxima, not just the two commands above. If a field, node, evidence, cap, mute or service is missing or inconsistent, stop; use the speaker-off fallback and capture logs. A mode selection alone is not evidence that SP is active or VI data is valid. Before playback the SP graph may be down, `sp_enabled: 0` and `allowed: no`; do not force a playback graph or treat that idle state as a reason to bypass a gate. Any later audible step stays with the operator and must first establish active SP and VI, matching calibration, all guard gates and an operator-approved safe procedure. The checks do not prove protection efficacy or physical silence.

## 2026-11-04: next muted VI-only diagnostic (current)

This section supersedes all conflicting closed-loop instructions below, including the old request for `sp11.allow_nominal=1`, the old flags-0 supplement and any instruction to inspect or save capture bytes. It is a plan, not permission to bypass S1/D26. **No playback open, tone, automatic test, unmute, private samples or speaker output.** The rev25c private ISO now carries the kernel candidates, the `m15-safe-cl` DTB and the private CL files, and adds the nondefault `SP11 debug, safe, muted closed-loop VI` entry (`sp11.nospk=1`), so this is its first device plan; nothing has been run on the device yet. See [implementation evidence and integration prerequisites](evidence/2026-11-04-muted-vi-implementation.md).

Prerequisites: integrate and review lifetime candidate kernel 0011 followed by audio 0024–0027; verify BTF and kernel/DT builds and failure-path cleanup. Boot a new private GPU-off safe-services diagnostic entry whose compiled `m15-safe-cl` DTB has the CL model, with mandatory `sp11.nospk=1`, **no** `sp11.allow_nominal`, and private CL-named topology plus the explicit `--vi-only-diagnostic --nominal-cal` supplement/calibration. Confirm public image absence and fail-closed missing topology, all caps, the fault latch, no automatic playback and an effective speaker-off fallback. The generated supplement sets CPS-required while no CPS graph exists: this is deliberate and capture-only. The old flags-0 supplement is not suitable.

On the planned boot, before capture, record boot ID, `/proc/cmdline`, booted kernel/DTB hashes, `/sound/model`, private firmware hashes, `wpctl get-volume @DEFAULT_AUDIO_SINK@`, all six cap logs and controls, complete guard and kernel journal. Require CL model, sink muted, `mode: closed-loop`, `loaded: 1`, `caps_ready: 1`, `nospk: 1`, `open_allowed: no`, `allowed: no`, `fault: 0`, no playback PCM/process, both WSA devices, and no faults. If any is missing, stop. `PA Volume=0` is not mute; a guard/sink report is not proof of analog silence. With no SP graph, `cps_required: 0` says nothing about CPS need.

Then identify the actual MultiMedia5 capture using `arecord -l` and `/proc/asound/card0/pcm4c/info`; use `hw:0,4` only if those confirm it. Run the following once, with an operator present, no other capture and no playback. The supervisor checks identity, negotiated FE format, RUNNING, XRUN and a two-second frame-progress deadline; it advances the pointer without reading or retaining samples. It may legitimately fail because the trigger has no data path; that is a result, not a reason to bypass the watchdog.

```bash
sudo timeout --signal=TERM --kill-after=2s 5s /usr/libexec/sp11/speaker-supervisor hw:0,4 > /tmp/sp11-vi-trigger.log 2>&1 &
trigger_pid=$!
sleep 1
cat /proc/asound/card0/pcm4c/sub0/status /proc/asound/card0/pcm4c/sub0/hw_params
sudo /usr/libexec/sp11/guard-report
sudo journalctl -k -b -o short-monotonic | grep -Ei 'graph |sp11:|feedback |wsa884|soundwire|fault|interrupt'
wait "$trigger_pid"; printf 'trigger exit=%s\n' "$?"
cat /tmp/sp11-vi-trigger.log
sudo /usr/libexec/sp11/guard-report
sudo journalctl -k -b -o short-monotonic | grep -Ei 'graph |sp11:|feedback |wsa884|soundwire|fault|interrupt'
```

During the run, record the FE state/negotiated channels, graph 106 OPEN/PREPARE/START results and raw errors, VI DMA media count/format/mask, VI speaker count and four map entries, each amplifier's requested feedback port/mask, and the VI `0x080011f5` SET_CFG status. If setup reaches them, the expected construction is two DMA channels, VI count two and map `[1,2,3,4]`; this expectation is a diagnostic comparison, not a verdict on physical packing. After successful start, inspect `vi_streams`, `cal_mask: 0x3`, `cal_nominal: 1`, `cal_graph_matches_vi: 1`, and `vi_ambiguous: 0`; after stop/close, calibration must clear and `allowed` must stay no. A successful 5-second hold exits 124 through `timeout`; early supervisor failure, timeout waiting on the DSP, XRUN or stall is not a pass. If no frame progress occurs, expect the watchdog to close the PCM and report a stalled trigger, not valid/invalid VI.

For each amplifier, the candidate's `feedback before-add PA global enable=0 (register)` and `before-free` direct reads are separate snapshots when available. A missing, inactive, failed or unknown read is **inconclusive**; an observed 1, fault, unexpected output or other error stops the attempt immediately. These snapshots do not prove continuous or physical mute. Do not retry a failed/timed-out graph in the same boot; collect the first error and reboot to the existing speaker-off fallback. No conclusion about VI sample validity, CPS, cross-graph control links, DSP protection, measured calibration or sound safety follows from this capture-only run.

## 2026-11-04: earlier closed-loop muted matrix (superseded)

This section supersedes any conflicting closed-loop instruction below and the rev25 plan's suggestion that host capture bytes prove V/I. **No playback open, playback PCM, tone, speaker-first-test, unmute or audible output is authorized here.** PA value 0, a muted sink, guard state and low gain do not independently prove physical PA-off. Keep S1/D26, the caps, fault latch, kill switch and a speaker-off fallback. The existing `speaker-first-test` can start tones and checks supervisor liveness only once; do not use it for this matrix.

The rev25-menu private ISO f44ef has the corrected filenames and S16_LE/48 kHz/stereo supervisor but **does not have the calibration-lifetime fix**. On it the next allowed step is only the read-only baseline below; do not start a VI capture. Capture tests require an owner-integrated, reviewed kernel with the lifetime candidate and reviewed component patches 0024 and 0025 integrated, plus the candidate supervisor, with the exact files identified by hashes and the operator present. No new boot or test was performed by this worker.

| Test | Required observation | Proves / remains ambiguous |
|:--|:--|:--|
| Read-only baseline | Record boot ID, entry, DT model, kernel/DTB/firmware hashes, complete guard, all six caps, sink mute and errors. Expect no playback/capture PCM; `graph_up: 0` and `allowed: no`. | Identifies configuration and reported gate state only; physical PA-off and device protection remain unknown. |
| FE and backend graph open / prepare / start | After prerequisites, trigger **capture only** using verified MultiMedia5; collect ALSA status/hw_params, supervisor and timestamped GPR/APM OPEN/PREPARE/START return codes if actually available. | A returned success concerns that command only; timeout or missing instrumentation is inconclusive. It does not prove cross-graph H3, valid VI or protection. Playback graph test is blocked until a separately verified physical output inhibitor and reviewed no-output procedure exist. |
| VI / CPS stream | Record `vi_streams`, `cps_required`, `cps_streams`, both WSA ports and any actual backend setup/fault logs while held and after stopping. | A stream callback is not sample validity. MultiMedia5 has no host V/I connection; neither zeros nor nonzero bytes classify sense transport. Current supplement requires no CPS in software and the graph has no CPS chain; whether hardware needs CPS is unknown. |
| Channel counts and maps | Capture backend codec-DMA count, VI operation speaker count, four-element VI map and both SoundWire port/slot configurations, if instrumented. | Distinguishes two speakers from four V/I values but does not establish DMA packing or Windows parity. Current machine fixup is two while topology lists four; record actual values without changing them. |
| Nominal calibration | On the integrated private test configuration, check 36-byte file hash and nominal flag; record loader result, SET_CFG response, `cal_mask`, `cal_nominal`, `cal_graph_matches_vi`, `vi_ambiguous`. | File/schema checks and DSP ACK are not per-unit calibration or algorithm validation. A running VI identity is needed for graph match; `diagnostics_degraded=1` must reject nominal even with `allow_nominal=1`. |
| Calibration rejection | Separate fresh private boots/fixtures: absent file; corrupt CRC; valid CRC with an unknown flag; valid CRC with a nonzero reserved field. Record exact error, command outcome and full guard. | Each reached bad fixture must leave calibration mask 0 and `allowed: no`; missing file can return loader success. If setup fails before the file check, mark inconclusive. No fixture is measured calibration. |
| Guard preconditions | Read complete snapshot and use `guard-report` if staged; observe each field including graph match, ambiguity, caps, mode, fault, nominal, diagnostics and VI/CPS. | Reports the guard's inputs and decision, not actual PA state, live data, diagnostics coverage or thermal/excursion protection. Unknown/missing fields are not a pass. |
| Kill switch | Separate planned boot with `sp11.nospk`, no playback; record `nospk: 1`, `allowed: no`, `open_allowed: no` and reason if higher-priority gates permit. | Confirms reported decisions only. A real playback-open refusal needs a separately reviewed no-output setup. |
| Speaker-off fallback | Separately boot `nosnd`; inspect DT sound status and effective parent/bus statuses, cards, and both WSA paths. | Confirms fallback only if both speaker paths are absent/disabled; `nosnd` disables the whole sound card, so it is not a Mic/DP-capable fallback. |

### Exact next read-only baseline

On an already planned private `spk` boot with no PCM open and the sink muted, record command exit statuses and run:

```bash
cat /proc/sys/kernel/random/boot_id /proc/cmdline
tr -d '\0' </proc/device-tree/sound/model; printf '\n'
uname -r
cat /proc/asound/cards /proc/asound/pcm
wpctl get-volume @DEFAULT_AUDIO_SINK@
sudo cat /sys/kernel/debug/sp11/guard
sudo journalctl -k -b -o short-monotonic | grep -Ei 'sp11|speaker|calibration|wsa884|soundwire|tplg|graph|fault|interrupt'
fwdir=/usr/lib/firmware/qcom/x1e80100
sha256sum "$fwdir/X1E80100-Microsoft-Surface-Pro-11-CL-tplg.bin" "$fwdir/X1E80100-Microsoft-Surface-Pro-11-CL-sp11cl.bin" "$fwdir/X1E80100-Microsoft-Surface-Pro-11-CL-sp11cal.bin"
```

Also record selected DTB, actual booted kernel/DTB hashes and all PA/RX/MIX cap controls and their maxima. Record missing files/fields rather than replacing them. This baseline does not require or justify opening a PCM. Stop on unexpected output or a fault.

After the prerequisites are integrated and verified, the capture-only case is a bounded `sudo timeout --signal=TERM 5s /usr/libexec/sp11/speaker-supervisor hw:0,4` **only after** `arecord -l` and `/proc/asound/card0/pcm4c/info` identify that device as MultiMedia5. During the hold, read `/proc/asound/card0/pcm4c/sub0/{status,hw_params}`, the complete guard and the journal; afterwards record exit status and guard again. Timeout 124 is expected if it stayed running; an earlier exit/XRUN is a stop, not a pass. The candidate discards host trigger bytes to avoid buffer overrun and reports PCM state loss; it never treats bytes as sense data. If the kernel reports no APM return code for a stage, record **not observed**, not success.

## 2026-11-03 closed-loop audit: muted checks only

This section supersedes T4 and the old closed-loop stages A-D. **No playback PCM, tone, speaker-test, `speaker-first-test`, unmute or audible output in this procedure.** Keep S1/D26, all caps, the fault latch, and a verified speaker-off fallback. A mute or `PA Volume` value alone does not establish that the physical PA is off. The operator runs a planned boot only; we have not run these commands on the device.

Before a VI capture attempt, the kernel owner must resolve and test the calibration lifetime defect in [the audit](evidence/2026-11-03-closed-loop-audit.md); the image must also stage the two CL-named supplements and use a supervisor compatible with the actual MultiMedia5 front end. These are prerequisites, not verified fixes. Until then collect only the read-only baseline below and stop: do not retry a failed VI prepare in the same boot, swap a calibration file, or infer safety from the mask.

1. **Read-only baseline on the already selected private `spk` entry.** With no player or capture process, confirm the graphical sink is muted with `wpctl get-volume @DEFAULT_AUDIO_SINK@`, and record exit status. Record the complete output and failures of:

   ```bash
   cat /proc/sys/kernel/random/boot_id /proc/cmdline
   tr -d '\0' </proc/device-tree/sound/model; printf '\n'
   uname -r
   cat /proc/asound/cards /proc/asound/pcm
   arecord -l
   sudo cat /sys/kernel/debug/sp11/guard
   sudo journalctl -k -b -o short-monotonic | grep -Ei 'sp11|speaker protection|calibration|wsa884|soundwire|tplg|graph|fault|interrupt'
   amixer -c 0 contents
   ```

   Read the boot command line for `sp11.entry=spk`, `sp11.allow_nominal=1`, and the actual DT `/sound/model` for `X1E80100-Microsoft-Surface-Pro-11-CL`. Record the chosen GRUB entry/DTB and hashes of the booted kernel, DTB and the following installed files; record missing files, do not manufacture replacements:

   ```bash
   fwdir=/usr/lib/firmware/qcom/x1e80100
   sha256sum "$fwdir/X1E80100-Microsoft-Surface-Pro-11-CL-tplg.bin" \
             "$fwdir/X1E80100-Microsoft-Surface-Pro-11-CL-sp11cl.bin" \
             "$fwdir/X1E80100-Microsoft-Surface-Pro-11-CL-sp11cal.bin"
   ```

   The topology currently generated offline hashes to `000b6d720640225657cdb08d26db738962bca7d5961a4be01c34c5a7778b6272`; the expected supplement and nominal file hashes are in the audit. Check any initramfs or firmware-path override too; a file hash alone does not prove which bytes the firmware loader used. Require `mode: closed-loop`, `caps_ready: 1`, `loaded: 1`, `fault: 0`, `nospk: 0` and the exact `closed-loop speaker protection data loaded: 1 links, 28 records` loader line before proceeding. With no graph or VI stream, expect `open_allowed: yes`, `allowed: no`, and `reason: the closed-loop graph is not up`; the first means only that a PCM may be opened/prepared, while the second is the amplifier unmute decision. If a prerequisite has not been met, record its first reported reason and stop. The current image is expected to show `loaded: 0` because of the name mismatch; that is a finding, not an instruction to bypass the gate. Check all six cap lines and maxima (PA 6, RX/MIX 81) and report both amplifier devices and any error/latch.

2. **VI capture presence and trigger, after the prerequisites above are fixed.** Verify `arecord -l` lists MultiMedia5 capture and that its actual PCM index is 4 before using the command below; confirm no other capture or playback PCM is open. The corrected supervisor must use the advertised front end S16_LE, 48 kHz, one or two channels; its backend has separate fixup parameters. While the sink remains muted, run only the capture trigger for a bounded interval:

   ```bash
   sudo timeout --signal=TERM 5s /usr/libexec/sp11/speaker-supervisor hw:0,4 >/tmp/sp11-vi-trigger.log 2>&1 &
   trigger_pid=$!
   sleep 1
   cat /proc/asound/card0/pcm4c/sub0/status /proc/asound/card0/pcm4c/sub0/hw_params
   sudo cat /sys/kernel/debug/sp11/guard
   wait "$trigger_pid"; printf 'trigger exit=%s\n' "$?"
   cat /tmp/sp11-vi-trigger.log
   sudo cat /sys/kernel/debug/sp11/guard
   sudo journalctl -k -b -o short-monotonic | grep -Ei 'sp11|calibration|graph|wsa884|soundwire|fault|interrupt'
   ```

   A timeout exit of 124 after a successful hold is expected; an earlier failure, XRUN, missing state, fault or error ends the attempt. If the backend starts, `vi_streams` should rise and fall; with no playback graph, `graph_up: 0` and `allowed: no` must remain. A calibration SET_CFG response may set `cal_mask: 0x3` during prepare; on successful stop it must clear. Record timestamps and the first failing command. These observations test graph/callback progress, **not** the presence, ordering, scaling or quality of V/I samples. MultiMedia5 is an unconnected trigger; even nonzero host bytes would not prove V/I. A real muted V/I data check remains blocked until a separately reviewed and validated sense-data tap or readback exists. Do not record this PCM as V/I data or claim that H3, sample flow or thermal/excursion protection works.

3. **Calibration acceptance and rejection, capture only.** After the kernel lifetime fix and corrected filenames/supervisor, use separate private test configurations and a fresh boot for each case; preserve the original file and do not change a mounted image, rebind drivers, fabricate measured values or force graph success. In the normal configuration, start the same bounded VI trigger and record `speaker calibration applied (nominal)` or `(measured)`, `cal_mask`, `cal_nominal`, `vi_streams`, all guard fields and failures. The staged file is nominal, so `cal_nominal: 1` is expected if accepted. The message and mask establish that the host accepted the file and the DSP replied to SET_CFG; they do not establish per-unit measurement, the correct signal scale or DSP algorithm behavior. In degraded-diagnostics mode 0021 requires non-nominal calibration even when `allow_nominal: 1`.

   On a separate private boot whose **only** changed fixture is an absent `...-CL-sp11cal.bin`, keep the CL topology and supplement intact and repeat the bounded trigger. Require the exact `no speaker calibration (...)` warning, `cal_mask: 0x0` and `allowed: no`; missing calibration returns success in the loader, so a PCM return code alone is insufficient. On another fresh private boot use an intentionally corrupt-CRC copy under the same name: require `checksum mismatch`, a failed VI preparation, `cal_mask: 0x0` and `allowed: no`. Preserve only the fixture hash and log. If H10 or an earlier error prevents reaching the relevant file check, mark that case **inconclusive**, not passed. Test valid measured calibration only when a separately evidenced per-unit file exists. On any fault, stop; never clear it or change gain, mask, mode or port mapping.

4. **Kill switch and speaker-off fallback.** On a planned private `spk` boot, use the existing GRUB edit to add `sp11.nospk`; do not start playback. Record `/proc/cmdline` and the complete guard. With caps and mode initialized, require `nospk: 1`, `open_allowed: no`, `allowed: no` and reason `sp11.nospk is set`; a higher-priority missing-cap/mode reason makes the reason test inconclusive, although the `nospk` field remains evidence the parameter was read. This checks reported guard decisions without exercising a playback-open path; an open/prepare refusal still needs a separately reviewed no-trigger test. Power off on a fault or unexpected output.

   Separately select the existing `nosnd` fallback, record its boot ID, cmdline, actual DT `/sound/status`, `/proc/asound/cards` and SoundWire amplifier enumeration. Require the speaker sound node/bus and both WSA8845 paths absent or disabled; if their effective parent status cannot be established, report inconclusive. The source `m15-nosnd` disables the sound card as well, so it is not evidence for a microphone/DP-capable fallback. The current `m15-safe` source includes the speaker fragments; do not label it speaker-off without a changed DTB and evidence.

These checks leave ADSP cross-graph link acceptance (H3), H10, genuine V/I/CPS data and scaling, DSP fault semantics and per-unit R0/T0 open. Do not convert them into an audible test or a closed-loop protection claim.

**Current rev20 procedure:** [PA regression evidence](evidence/2026-11-02-pa-gain-regression.md) supersedes conflicting historical steps below. Rev19 logs confirm D26 open-loop and late-probe caps; the revised UCM, actual startup mute, effective digital gain and microphone signal still require validation. D26 is an operator-authorised open-loop exception, not closed-loop thermal/excursion protection. Keep a speaker-off fallback. Any audible test requires the operator present.

## 2026-11-03: UCM, volume and fault timeline (current)

This supersedes the revision-20 instruction to write/test `Speakers Volume` in the Speaker cset sequence; retain that alias as the PipeWire playback mixer. The candidate removes only this cset and must first be integrated by the image owner. Keep D26 open-loop policy, caps and readiness, startup mute, first-test 5% marker, kill switch and speaker-off fallback. No independent proof of closed-loop protection is claimed. Do not create audible output for this investigation without the operator and all existing D26 gates; stop on an unexpected fault, repeated parity or distortion/heat. Do not reset a fault or change amplifier register masks.

1. On the already planned first-test boot, record boot ID, monotonic and wall time, command line, installed file hashes (including all four D28 UCM files and `x1e80100.conf`), kernel/topology hashes, six cap lines, and `cat /sys/kernel/debug/sp11/guard`. Require open-loop, `caps_ready: 1`, no fault, all caps and the fallback. Collect the complete system and user journal with monotonic timestamps and full error text from boot onwards; record user/session and command exit codes. Identify both amps and stream openers; do not claim that a list of available UCM devices is the active state.
2. In the active graphical user's environment, before opening any player, capture `wpctl status`, `wpctl inspect @DEFAULT_AUDIO_SINK@`, `wpctl get-volume @DEFAULT_AUDIO_SINK@`, `pw-dump`, active UCM verb/devices, and both `amixer -D hw:0 contents` and `amixer -c 0 contents`. Confirm helper/default-route mute, the 5% first-test setting, and that `hw:0` has the two PA controls but no userspace-only `Speakers Volume` alias. The remapped mixer should show the alias. Record exact PA L/R and alias, RX0/RX1 and both MIX values/maxima, digital mute, WSA mode, DAC/COMP/BOOST/PBR/VISENSE/CPS, WSA RX muxes and INP0, WSA_CODEC_DMA mixer and the active PCM. Take a monotonic timestamp immediately before each collection, and keep raw output and errors. Confirm expected RX/MIX cap <=81, PA <=6 and no out-of-range values. Do not equate PA value 0 with a software mute.
3. Obtain a **muted**, exclusive diagnostic of `alsaucm` and WirePlumber sequences, with a single UCM manager at a time: arrange a test session that keeps the sink muted and has no competing UCM user, player or PCM; instrument ALSA UCM logging or ioctl control tracing so each cset, target handle, return/errno, and PA state is recorded. With the original configuration, reproduce only if the already scheduled boot still uses it; do not reinstall it just to make a failure. Record verb `HiFi`, `_enadev Speaker` return and `_enadevs` from the same UCM manager, then before/after PA L/R, macro route and guard. Determine whether `name='Speakers Volume' 6` fails on `hw` after the physical PA writes or a different command fails. Stop on a fault or any missing mute/cap. Repeat on the candidate image, then disable/re-enable and reselect the verb while muted, and record return codes, actual active devices, both PA values (6 after enable, 0 after disable), alias, routes and guards each time. Test whether BootSequence or session management subsequently overwrites the physical PA values. WirePlumber should enable Speaker without the warning, and the selected sink should use the mapped mixer; otherwise retain logs and do not infer success. UCM operations modify controls: perform them only under the existing safety gates and restore the muted state after diagnostic handoff.
4. Before any sound, confirm the current default sink and stream software volumes, mutes, route, target node and the full hardware state above. Record these again **during** the same short known stereo signal and immediately after, with timestamp and `wpctl`/`pw-dump` stream values, app volume, stream peak if available, `/proc/asound/card0/pcm0p/sub*/status`, guard and journal. Begin at the specified 5% with the operator present after step 3 passes, then stop. Any subsequent controlled comparison of ordinary user sink/stream volume must stay within the existing D26 policy, use the same known signal and record each setting; do not change PA/RX/MIX caps, UCM 72, speaker mode or route as a loudness experiment. Preserve startup mute. Correlate the operator's observation with these times, and stop on a latch or repeated errors.
5. For the already scheduled end of session/reboot, record user command time, stream closure, UCM device transitions, guard state and a continuous `journalctl -b -o short-monotonic -f` through collector shutdown. Capture raw interrupt bytes, device, driver PA state, first latch, reboot request and WirePlumber/PipeWire shutdown times; also record runtime PM, clocks and regulator summaries at each feasible stage without forcing a resume or changing votes. The two debug boot `kmsg-live` streams previously ended near 61 s, so absence later is not evidence. Test separately in an idle interval before shutdown; do not deliberately force a fault or clear status. An interrupt during ordinary idle/active playback is materially different from one only during reboot. Classify status1 bit 1 only after an authoritative source or independent REA cross-check; maintain fail-closed behavior while unknown.

## Revision 20: muted safety and PA sequence

1. Use a clean safe boot with no camera application or stream; append `sp11.audio_first_test=1` for the first audible test. On the speaker-off fallback verify the WSA speaker path is disabled. On each speaker entry record boot ID, DTB, topology hash, mode and cap logs; require D26 open-loop, all six PA/RX/MIX cap successes and `speaker volume caps ready`, plus `caps_ready: 1`. No sound yet.
2. Verify global and per-device `device.routes.default-sink-volume = 0.0`. In the graphical session identify the built-in sink and use `wpctl get-volume` to verify the helper muted it and set 5% on the first-test boot; normal boots must be muted at 100%. The helper must mute before setting volume. WirePlumber 0.5.19 does not implement `api.acp.max-volume`; do not treat it as a ceiling.
3. Complete muted T2c before unmuting. Inspect UCM and `amixer -c 0`: PA max 6 (0 dB), both WSA RX and RX MIX maxima 81 (-3 dB), and UCM digital initialization 72 (-12 dB). Read left/right PA and stereo `Speakers Volume` after UCM enable, after verb re-selection, and after disable/enable: each must read 6; on disable they must read 0. Verify WsaInit BootSequence does not overwrite PA after enable; record failed csets and reattach behavior. Measure digital values and `wpctl`/`pw-dump` at 100% while muted: if digital rises from 72 to 81, require an implemented and verified real clamp before accepting the path. Fail any missing mute, cap, fallback or sequence gate.
4. With the operator present and T2c passed, unmute at 5%, play a short known stereo tone, check both channels and stop. Stop immediately on distortion or heat. Only after that test passes, boot normally, start from minimum and raise stepwise; record effective sink and hardware values and temperatures. This tests playback, not closed-loop SP/VI.

## Revision 20: post-session microphone evidence

Run in the active graphical user's environment, with a bounded wait for PipeWire/WirePlumber; record boot ID, timestamps and command failures. Avoid simultaneous applications using the capture device. Record `wpctl status`, `wpctl inspect @DEFAULT_AUDIO_SOURCE@`, `wpctl get-volume @DEFAULT_AUDIO_SOURCE@`, and `alsaucm -c hw:0 dump` (plus `alsaucm -c hw:0 get CaptureChannels/Mic/HiFi`). Confirm the default source resolves to the built-in microphone, is unmuted, and capture channels are 2. Record `amixer -c 0 contents`, including `MultiMedia2 Mixer VA_CODEC_DMA_TX_0`, `VA DEC0/1 MUX`, `VA DMIC MUX0/1`, `VA_AIF1_CAP Mixer DEC0/1`, and `VA_DEC0/1 Volume`; repeat while capture is active. Expected routes are VA_DMIC, DMIC0/DMIC1 and both AIF switches on. Record gains as found: snapshots show 100 while the staged gain layer requests 98; do not silently normalize the discrepancy.

With the operator speaking at a normal level, capture two seconds of stereo S16_LE at 48 kHz directly from `hw:0,1` and calculate each channel's RMS and peak; record exit status and contemporaneous kernel/user errors. A nonzero RMS in both channels correlated with speech is required, not merely a nonzero noise floor. Do not retain the speech sample in collected logs. Example, from a shell running as the graphical user:

```bash
sample=$(mktemp /tmp/sp11-mic-XXXXXX.wav)
trap 'rm -f "$sample"' EXIT
arecord -D hw:0,1 -f S16_LE -r 48000 -c 2 -d 2 "$sample" &
record_pid=$!
amixer -c 0 contents
wait "$record_pid"
record_status=$?
printf 'arecord exit=%s\n' "$record_status"
if [ "$record_status" -eq 0 ]; then
  python3 - "$sample" <<'PYRMS'
import math, struct, sys, wave
with wave.open(sys.argv[1], 'rb') as wav:
    assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (2, 2, 48000)
    data = wav.readframes(wav.getnframes())
samples = struct.unpack('<%dh' % (len(data) // 2), data)
for channel in range(2):
    values = samples[channel::2]
    if not values:
        raise SystemExit('empty capture')
    rms = math.sqrt(sum(x*x for x in values) / len(values)) / 32768
    peak = max(abs(x) for x in values) / 32768
    print(f'channel {channel}: RMS={rms:.8f}, peak={peak:.8f} (fraction of full scale)')
PYRMS
fi
rm -f "$sample"
trap - EXIT
```

Also test the selected PipeWire default source, e.g. `arecord -D pipewire -f S16_LE -r 48000 -c 2 -d 2` with the same metrics, and record its exit status. Direct ALSA success alone does not prove the default source works. Do not alter UCM until the collected state and capture isolate a fault.

## Historical procedures

The procedures below describe prior stages and do not override the current rev20 gates above.

## T0, historical speaker-off entry (S1 off)

1. `cat /proc/asound/cards` on the default entry: "no soundcards". `ls /sys/bus/soundwire/devices`: no such directory.
2. `dmesg | grep -E 'CMD timeout|q6apm|tplg'`: record whether `GET_SPF_STATE` (`1001021`) still times out.
3. H1: `sudo modprobe -r snd_q6apm_dai snd_q6apm_lpass_dais q6prm_clocks q6prm snd_q6apm; sudo modprobe snd_q6apm; dmesg | tail -20`. An answer (no timeout) means a timing problem. Speakers cannot start: `/sound` is disabled.

## T1, entry `SP11 audio, microphones` (S1 off)

1. `ls /sys/bus/soundwire/devices` must not exist or be empty. `dmesg | grep -i wsa884`: no `wsa884x` probe.
2. `cat /proc/asound/cards`: card `X1E80100-Microsoft-Surface-Pro-11`. `dmesg | grep tplg`: topology loaded, no error.
3. Expect `aplay -l` to list no WSA device; playback is not part of this stage.
4. `amixer -c 0 contents | grep -i 'PA Volume'` must print nothing.

## T2, speaker variant, silent bring-up (only after S1 changes)

1. Both `sdw20217020400` devices enumerate; `wsa884x` probes without error; `cat /sys/class/hwmon/*/temp1_input` plausible.
2. `amixer -c 0 cget name='SpkrLeft PA Volume'` shows `max=6`; same for Right. `WSA WSA_RX0 Digital Volume`, `WSA_RX1`, and the two `_MIX` controls show `max=81`. `amixer -c 0 cset name='SpkrLeft PA Volume' 7` must fail.
3. Force a SoundWire re-attach (runtime suspend then resume of the card, or a stream start after 10 s idle) and read `PA Volume` again: at most 6 (patch 0001).
4. Historical pre-rev20 expectation was PA 0; use the current rev20 enable/disable checks above.

## T2c, D28 muted public-entry test (after patch and image integration)

1. Verify model `X1E80100-Microsoft-Surface-Pro-11`, marker `d26-open-loop-v1`, public topology filename/hash, and guard mode `open-loop`; parsed graph has no SP module.
2. Before opening audio, confirm the software sink is muted and the applicable startup level and kernel caps match the current procedure. After codec binding/card late probe and before opening audio, confirm there are no `speaker volume cap failed` lines; require `speaker volume cap installed for <control>: 0` or `: 1` for each of the six required WSA RX/RX MIX and left/right PA controls, plus `speaker volume caps ready`. Read PA (max 6), WSA RX digital and RX MIX caps (max 81), and confirm `caps_ready: 1` in guard debugfs. Check optional WSA2 and Woofer/Tweeter success lines when those controls are present.
3. Open and prepare/start the speaker PCM while the sink remains muted. Expect successful muted prepare/start without `-22`; the PCM must not appear until late-probe cap installation has completed. `sp11_guard_check` admits the stream, while the amplifier remains muted until the user unmutes; the unmute gate then reports open-loop allowed without VI/CPS, calibration, SP enable or diagnostics prerequisites. Confirm no SP diagnostics registration request or unsupported response and verify silence at both speakers while muted.
4. Capture journal timestamps, guard state before and after, active UCM verb/device, PCM, sink mute/volume and all hardware mixer values. Fail if any cap is missing, mode is unknown/refused, a diagnostic event is attempted, or sound is audible. Do not unmute during this test.

## T3, first sound (only with the operator present)

After T2c proves muted prepare with `caps_ready: 1` and all caps present, unmute deliberately and play a short, low-level tone. Confirm both speakers are audible at the 5% first-test level within the hardware caps, then stop. Stop immediately on distortion or warmth. Log `hwmon` temperature before, during and after. Acceptance items 1 to 3 of the dossier apply.

## T2b, M13 gated speaker variant (D26)

Entry `m13-spk`, no volume, nothing playing. Expect: card registers, both WSA8845 enumerate, no `CMD timeout for [1001021]`, `aplay -D hw:0,0` fails with `Operation not supported` (gate, patch 0009), microphones record. Power off at once if any playback starts. Details: `evidence/2026-10-30-d26-audio.md` section 7. T3 stays blocked until the closed-loop protection (evidence section 8.4, stages 2 to 5) is validated.

## T4, historical closed-loop procedure

Superseded by the muted closed-loop audit at the top of this file. In particular, the trigger PCM is not a V/I data tap, the mask can be stale, and the old instruction to produce a tone is not part of the current task.

