#!/usr/bin/env python3
"""Generate the host-side (PipeWire) counterpart of the Windows audio processing. PRIVATE ONLY.

The Windows speaker sound is shaped host-side by the Dolby DAX3 APO whose per-device tuning is the
XML `dax3_ext_qc.../AUCD_DEV_0C29_SUBSYS_MSHW0486_REV_0D_ADCM_SUBSYS_MSHW0486.xml` (Windows data).
Linux has no Dolby engine. This tool replays the part that is a plain filter (the per-channel 20-band
"audio optimizer" speaker EQ) as a PipeWire filter-chain, and approximates the dynamics with a
limiter. Everything it writes carries Windows-derived numbers, so it goes to private out/ only
(S5); this script prints counts and file hashes, never tuning values.

  linux_chains.py --dolby-xml XML --out-dir out/firmware-private/audio/pipewire [--profile music]

Safety (S1 stays): this only builds a software filter graph in user space. It does not enable the
speakers and does not touch any mixer control. The generated speaker chain has a hard digital
ceiling: a preamp that cancels the largest boost of the curve (so the filter can only attenuate or
leave the level equal) and a final limiter at -3 dBFS. The kernel gate (0009) and the open-loop caps
stay underneath; this file never raises the level above what the user volume sets.

Replayed vs approximated (also in the evidence file):
  replayed   : 20 band centre frequencies and per-channel band gains (fs 48000 table of the XML)
  approximated: band filter shape (Dolby does not publish it; peaking biquads with Q from the band
                spacing), volume leveler / regulator / multiband compressor (one limiter), virtual
                bass and sliding bass, IEQ, dialog enhancer, virtualizer (not replayed)
"""

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

XML_SHA256 = None  # pinned by the caller through the evidence file; this tool only reports it
GAIN_UNIT_DB = 1 / 16  # Inference: the Dolby arrays are in 1/16 dB steps (-192 = -12 dB in the XML constants)
CLAMP_DB = 12.0
LIMIT_DB = -3.0
INF_MIC = {  # facts of surface_asdext8380.inf MicArray1 (REV_0D); geometry, not calibration
    "count": 2, "type": "linear", "y_mm": [20, -20], "spacing_mm": 40, "mic_kind": "subcardioid",
    "band_hz": [75, 20000], "default_gain_db": 14, "max_gain_db": 24,
}


def parse_speaker(xml_path, profile):
    root = ET.parse(xml_path).getroot()
    const = {c.tag: c.attrib for c in root.find("constant")}
    freqs = [int(x) for x in const["band_20_freq"]["fs_48000"].split(",")]
    ep = root.find("endpoint")
    prof = next(p for p in ep.findall("profile") if p.get("type") == profile)
    ao = prof.find("tuning-vlldp").find("audio-optimizer-bands")
    enabled = prof.find("tuning-vlldp").find("audio-optimizer-enable").get("value") == "1"
    chans = {}
    for ch in ao:
        if "value" in ch.attrib:
            chans[ch.tag] = [int(v) * GAIN_UNIT_DB for v in ch.get("value").split(",")]
        else:
            tgt = const.get(ch.get("preset"), {}).get("target")
            chans[ch.tag] = [int(v) * GAIN_UNIT_DB for v in tgt.split(",")] if tgt else None
    if len(freqs) != 20 or any(c is not None and len(c) != 20 for c in chans.values()):
        raise ValueError("unexpected band layout")
    return freqs, chans, enabled


def band_q(freqs, i):
    lo = freqs[i - 1] if i > 0 else freqs[i] / (freqs[i + 1] / freqs[i])
    hi = freqs[i + 1] if i < len(freqs) - 1 else freqs[i] * (freqs[i] / freqs[i - 1])
    bw_oct = math.log2(hi / lo) / 2
    return 1 / (2 * math.sinh(math.log(2) / 2 * bw_oct))


def speaker_conf(freqs, left, right, limiter):
    clamp = lambda g: max(-CLAMP_DB, min(CLAMP_DB, g))
    left, right = [clamp(g) for g in left], [clamp(g) for g in right]
    boost = max(0.0, max(left + right))
    nodes, links = [], []
    for side, gains in (("l", left), ("r", right)):
        prev = None
        nodes.append(f'            {{ type = builtin name = pre_{side} label = linear control = {{ Mult = {10 ** (-boost / 20):.6f} Add = 0.0 }} }}')
        prev = f"pre_{side}"
        for i, (f, g) in enumerate(zip(freqs, gains)):
            name = f"b{i:02d}_{side}"
            nodes.append(f'            {{ type = builtin name = {name} label = bq_peaking control = {{ Freq = {f} Q = {band_q(freqs, i):.4f} Gain = {g:.4f} }} }}')
            links.append(f'            {{ output = "{prev}:Out" input = "{name}:In" }}')
            prev = name
        if limiter:
            nodes.append(f'            {{ type = ladspa name = lim plugin = fast_lookahead_limiter_1913 label = fastLookaheadLimiter control = {{ "Input gain (dB)" = 0.0 "Limit (dB)" = {LIMIT_DB} "Release time (s)" = 0.5 }} }}') if side == "l" else None
    # The swh limiter is stereo; wire it after both channels
    last = {"l": f"b{len(freqs) - 1:02d}_l", "r": f"b{len(freqs) - 1:02d}_r"}
    if limiter:
        links += [f'            {{ output = "{last["l"]}:Out" input = "lim:Input 1" }}',
                  f'            {{ output = "{last["r"]}:Out" input = "lim:Input 2" }}']
        outs = ('lim:Output 1', 'lim:Output 2')
    else:
        outs = (f"{last['l']}:Out", f"{last['r']}:Out")
    return f'''# PRIVATE: generated from Windows data (S5). Never commit, never ship in a public image.
# Speaker quality chain: 20-band per-channel EQ (replayed) + limiter (approximation of the
# Dolby regulator / multiband compressor). Ceiling: preamp cancels the largest boost, limiter {LIMIT_DB} dBFS.
context.modules = [
  {{ name = libpipewire-module-filter-chain
    args = {{
      node.description = "SP11 speaker (Windows EQ curve)"
      media.name = "SP11 speaker"
      filter.graph = {{
        nodes = [
{chr(10).join(n for n in nodes if n)}
        ]
        links = [
{chr(10).join(links)}
        ]
        inputs  = [ "pre_l:In" "pre_r:In" ]
        outputs = [ "{outs[0]}" "{outs[1]}" ]
      }}
      audio.channels = 2
      audio.position = [ FL FR ]
      capture.props = {{ node.name = "sp11_speaker_quality_in" media.class = Audio/Sink }}
      playback.props = {{ node.name = "sp11_speaker_quality_out" node.passive = true }}
    }}
  }}
]
'''


def mic_conf(gain_db):
    mult = 10 ** (gain_db / 20)
    return f'''# PRIVATE (derived from Windows INF data; geometry is a hardware fact, the rest is policy).
# Microphone chain for the internal 2-mic linear array (spacing {INF_MIC["spacing_mm"]} mm, subcardioid):
#  1. 75 Hz high-pass per channel (the array's declared low band edge)
#  2. broadside delay-and-sum to mono: for a talker in front both capsules are equidistant, so the
#     plain average is the broadside beam (approximation of the ADSP beamforming, not a replay)
# Noise suppression / echo cancellation: libpipewire-module-echo-cancel is configured separately
# (see sp11-mic-echo-cancel.conf); Windows used ADSP modules (ffecns, fluence) that cannot run here.
context.modules = [
  {{ name = libpipewire-module-filter-chain
    args = {{
      node.description = "SP11 microphone (array to mono)"
      filter.graph = {{
        nodes = [
          {{ type = builtin name = hp_l label = bq_highpass control = {{ Freq = 75.0 Q = 0.7071 }} }}
          {{ type = builtin name = hp_r label = bq_highpass control = {{ Freq = 75.0 Q = 0.7071 }} }}
          {{ type = builtin name = sum label = mixer control = {{ "Gain 1" = 0.5 "Gain 2" = 0.5 }} }}
          {{ type = builtin name = gain label = linear control = {{ Mult = {mult:.6f} Add = 0.0 }} }}
        ]
        links = [
          {{ output = "hp_l:Out" input = "sum:In 1" }}
          {{ output = "hp_r:Out" input = "sum:In 2" }}
          {{ output = "sum:Out" input = "gain:In" }}
        ]
        inputs  = [ "hp_l:In" "hp_r:In" ]
        outputs = [ "gain:Out" ]
      }}
      audio.channels = 2
      audio.position = [ FL FR ]
      capture.props = {{ node.name = "sp11_mic_in" node.passive = true }}
      playback.props = {{ node.name = "sp11_mic_mono" media.class = Audio/Source audio.channels = 1 audio.position = [ MONO ] }}
    }}
  }}
]
'''


ECHO_CANCEL = '''# PRIVATE-mode template; no Windows numbers inside.
# Closest equivalent to the Windows communications chain that this host can run: WebRTC audio
# processing (echo cancel, noise suppression, gain control). The two-mic geometry is given in
# case the installed webrtc-audio-processing supports beamforming (Unknown: the 1.x library that
# Fedora ships dropped it); otherwise the module runs single-channel on the mono source.
context.modules = [
  { name = libpipewire-module-echo-cancel
    args = {
      library.name = aec/libspa-aec-webrtc
      node.description = "SP11 microphone (echo cancel + noise suppression)"
      capture.props = { node.name = "sp11_mic_ec_capture" target.object = "sp11_mic_mono" }
      source.props  = { node.name = "sp11_mic_ec" }
      aec.args = {
        webrtc.gain_control = true
        webrtc.noise_suppression = true
        webrtc.high_pass_filter = true
        webrtc.voice_detection = true
        webrtc.extended_filter = true
        webrtc.delay_agnostic = true
        # webrtc.beamforming = true
        # webrtc.mic-geometry = [ 0.0 0.020 0.0  0.0 -0.020 0.0 ]
      }
    }
  }
]
'''


def write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o600)
    return hashlib.sha256(text.encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--dolby-xml", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--profile", default="music", help="Dolby profile (music, movie, voice, dynamic, game)")
    ap.add_argument("--limiter", choices=("swh", "none"), default="swh")
    ap.add_argument("--mic-gain-db", type=float, default=0.0,
                    help="software capture gain; Windows default endpoint gain is +14 dB but the ADSP "
                         "applies its own: measure on the device before raising this")
    a = ap.parse_args()
    freqs, chans, enabled = parse_speaker(a.dolby_xml, a.profile)
    left, right = chans.get("ch_00"), chans.get("ch_01")
    if left is None or right is None:
        raise SystemExit("channels 0 and 1 carry no band data")
    out = {
        "sp11-speaker-quality.conf": speaker_conf(freqs, left, right, a.limiter == "swh"),
        "sp11-mic-quality.conf": mic_conf(a.mic_gain_db),
        "sp11-mic-echo-cancel.conf": ECHO_CANCEL,
    }
    hashes = {n: write_private(a.out_dir / n, t) for n, t in out.items()}
    print(json.dumps({"profile": a.profile, "audio_optimizer_enabled_in_profile": enabled,
                      "bands": len(freqs), "channels_with_curve": sum(c is not None for c in chans.values()),
                      "max_boost_cancelled": bool(max(left + right) > 0), "files": hashes}, indent=1))


if __name__ == "__main__":
    main()
