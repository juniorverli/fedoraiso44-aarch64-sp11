# Closed-loop speaker topology, the Qualcomm RFC, and what the M14 ISO can carry

Author: audio-speakers worker (Claude Sonnet 5.5), 2026-10-31. Continues `2026-10-30-closed-loop.md`. Grades follow `agents/protocol.md` section 5: Verified (read in code or run in this session), Inference, Unknown. Nothing here was run on the device. No kernel image was built for the ISO; the only kernel built is a scratch arm64 test kernel (section 3). REA was not used. Nothing is committed.

## 1. Result

| Question | Answer | Grade |
|:--|:--|:--|
| Can the Linux 7.3 topology express the SP, V/I chains with the Windows instance ids? | Yes. | Verified (parser source and run) |
| Is a host tap needed? | No. The sense chain ends in `SPEAKER_PROTECTION_VI` inside the DSP, as in Windows and in the Qualcomm topology. The 2026-10-30 reasons 1 to 3 for not generating the `.bin` were wrong or avoidable (section 2). | Verified |
| Topology generated? | Yes, locally, private: `out/firmware-private/audio/qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-tplg.bin`, SHA-256 `000b6d720640225657cdb08d26db738962bca7d5961a4be01c34c5a7778b6272`, deterministic (two builds). | Verified |
| Parsed by the real kernel parser? | Yes, 16 checks pass (section 3). | Verified |
| Will it work on the device with the M14 kernel? | Unknown: two DSP behaviours are open (H3, H10, section 4). A failure keeps the speakers muted, because the guard stays closed. | Unknown |
| RFC design B better than ours? | Better architecture, not proven on this SoC and not adoptable now (section 5). Decision: keep design A for M14, port B for M15 only if M14 shows A cannot start. | Inference from evidence |

## 2. How the Linux topology consumes AudioReach (Verified, `sound/soc/qcom/qdsp6/topology.c`, `audioreach.c` of the composed tree `out/build/apply-closedloop`)

- Module instance ids are not range checked. `audioreach_tplg_alloc_module()` uses `idr_alloc_u32(&apm->modules_idr, mod, &id, id)`: any non-zero id is taken as is, only a duplicate is refused (`Duplicate Module Instance ID`). The ranges `0x6000` and `0x7000` are only the convention of the public topology and the start of the dynamic allocator (id 0). Subgraph, container and module ids live in three separate IDRs; the public topology already reuses the number `0x4001` as subgraph and container id.
- The ids are forwarded verbatim: the harness decodes the real `APM_CMD_GRAPH_OPEN` and finds `0x4027`, `0x4024`, `0x4025`, `0x4026` in the module list, module properties and connections (section 3). The ADSP is the only judge of them.
- Links between modules of one graph need no host: each module widget carries `SRC_OP_PORT_ID`, `DST_INSTANCE_ID`, `DST_IN_PORT_ID`; they become the connection list. A module with `max_op_port` 0 simply ends the chain.
- A "graph" is the set of subgraphs that share `AR_TKN_DAI_INDEX`. A back end DAI opens the graph with its own DAI id (106 for `WSA_CODEC_DMA_TX_0`). A front end graph and a back end graph are joined only by a virtual mixer switch.
- What blocked the 2026-10-30 attempt, corrected: (1) there is no host tap problem. The previous report labelled module `0x0700101a` as MFC; Linux names it `DATA_LOGGING` (`audioreach.h:27`; MFC is `0x07001015`). The Windows sense chain is therefore `CODEC_DMA_SOURCE -> DATA_LOGGING -> SPEAKER_PROTECTION_VI`, the same chain the Qualcomm topology uses. `acdb_inspect.py` carried the wrong names (also repeated in the Argon report, which says MFC and `0x07001013` DATA_LOGGING); the table is fixed in this session. `0x07001011` and `0x07001013` have no Linux name and are labelled by id only. (2) Instance ids outside `0x6000`: accepted, see above. (3) The SP module goes between MFC and logger exactly as in the Qualcomm playback graph.
- What does block a V/I-only back end in the Linux model: DPCM opens a back end only for an active front end. This is the real problem of design A, answered in section 4.
- Parser weakness found (Verified by run): `audioreach_widget_ready()` ignores the return value of the widget loaders, so a duplicate instance id is logged (`dev_err`) and the topology still loads with return 0; the half-built widget has `dobj->private == NULL`. A generator mistake of that kind would not fail the load. `check_tplg_harness.py` therefore treats any parser `dev_err` as failure. Not patched here (not needed for the speaker work; candidate for a small upstream fix).

## 3. Generated topology and the parser check

Files (git): `userspace/build-topology/m4/` (`module_sp11.m4`, `subgraph-sp11-wsa-playback.m4`, `subgraph-sp11-vi-capture.m4`, `subgraph-sp11-trigger-capture.m4`, `X1E80100-Microsoft-Surface-Pro-11-closedloop.m4`), `build-closedloop-topology.sh`, `sp11_closedloop.py --emit-ids`, `build-closedloop.sh` (`SP11_TOPOLOGY=1`), `harness/` (`run-harness.sh`, `check_tplg_harness.py`, `src/`). Base: `linux-msm/audioreach-topology` commit `aab5c37c4fb9` (PR 76), rebuilt here: public SP11 file SHA-256 `b192044f01e97eabe7f6df9ae0d394086badb3c30124573210bc781093da8c03` (matches the recorded value). The overlay carries no Windows data: the instance ids are written to a private `sp11-ids.m4` from the ACDB (`find_roles()` checks the chain shape: the VI module has no consumer, its predecessors are DATA_LOGGING and CODEC_DMA_SOURCE).

What the topology adds to the public SP11 file (merge = the overlay replaces the WSA playback subgraph and adds two pieces; every other graph is unchanged):
1. WSA playback (graph 105): `MFC 0x6041 -> SP 0x4027 -> LOGGER 0x6040 -> CODEC_DMA_SINK 0x6042`. The SP module has no calibration in the file.
2. Sense back end (graph 106, `WSA_CODEC_DMA_TX_0`, interface index 1): `CODEC_DMA_SOURCE 0x4026 -> DATA_LOGGING 0x4025 (code 0x1586) -> SP_VI 0x4024`.
3. Trigger front end MultiMedia5 capture (graph 4): the Qualcomm capture stream graph, fed in DAPM from `device106.sp_vi1` with a plain route (no mixer, no control). No data connection is ever made. Its only job is to let DPCM open graph 106 (section 4).
Not included: the CPS chain (optional in the guard), the Windows playback extras (SAL, splitter, `0x07001013`).

Parser check (`harness/run-harness.sh`, reproduced twice from scratch): the harness is a scratch tree (hard-link copy of the composed kernel tree) plus four small files: it builds a tiny arm64 kernel (tinyconfig, ASoC, the real `topology.c`, `audioreach.c`, `audioreach-sp11.c`, `sp11-guard.c`, stubs for `gpr_*`/`q6apm_send_cmd_sync`) with the topology and the sp11 files as built-in firmware, boots it in `qemu-system-aarch64` (TCG), calls the real `audioreach_tplg_init()` through a registered ASoC card (back end DAIs registered with the production stream names), and builds `APM_CMD_GRAPH_OPEN` for every graph with the real `audioreach_alloc_graph_pkt()`. Results (all PASS): public topology loads without any parser error (graphs 0 1 2 3 104 105 110 129); closed-loop topology loads without any error (graphs additionally 4 and 106) and logs `closed-loop speaker protection data loaded: 1 links, 28 records`; instance ids unique; packet 105 carries SP `0x4027` and one control link VI `0x4024` to SP (declared once, by the graph that holds peer 2); packet 106 carries `0x4026 -> 0x4025 -> 0x4024` and no control link; negative controls: the duplicate-id topology is reported (`Duplicate Module Instance ID 0x00004027 found`, load still returns 0, see section 2), a truncated file fails with -22.
Limits: this proves syntax, id handling and packet construction, not ADSP acceptance. The kernel tree is v7.3 plus the 37 series entries of the earlier composition and 0006 to 0016 (the current `kernel/series` has 74 entries; the files the harness uses are unchanged by the later ones, Inference). The harness does not run DPCM start (no card with real links).

## 4. Design A with a trigger front end: what it needs from the ADSP (Unknown)

Order for a test: the supervisor opens the capture on MultiMedia5 (it never reads data), DPCM opens back end 106, the kernel sets 8 kHz, 32 bit, 4 channels (patch 0015), `GRAPH_OPEN` 106 carries the VI module, the guard sees the stream; then playback on MultiMedia1 opens graph 105 with SP and the control link whose peer already exists.
- H3: the control link is declared in graph 105 and its peer 1 is in graph 106, opened earlier. Unknown whether the ADSP accepts it. (The Qualcomm topology avoids this by opening both subgraphs in one `GRAPH_OPEN`.)
- H10 (new): the MultiMedia5 front end graph has a shared-memory capture endpoint with an unconnected input. Unknown whether the ADSP starts it.
- H4 still open: whether the V/I back end starts alone.
Fallbacks that stay firmware-only: connect the trigger through a mixer from a module with an output port (not possible, SP_VI has none in the Windows graph); or a splitter in the sense chain (module `0x07001011` is not named in Linux; unverified, not done). If H3 or H10 fails, A cannot work without kernel changes.

## 5. The Qualcomm RFC

Pinned (all fetched from lore.kernel.org on 2026-10-31; raw mails in `out/audio-speakers-spv5-references/sp-NN.eml`, thread mbox `t.mbox.gz` of the cover letter, 30 messages, SHA-256 of the decompressed thread `d1582fa10c854119333346cb56230fafdeb2c223af3641c08260d7c4dc294194`). Series `[RFC PATCH 00/23] ASoC: qcom: AudioReach Active speaker protection for WSA884x`, Srinivas Kandagatla and Ravi Hothi, 2026-10-23. Message-Ids (first 16 hex of the SHA-256 of each mail file):

| N | Message-ID | SHA-256 |
|:--|:--|:--|
| 00 | <20261023171433.820092-1-srinivas.kandagatla@oss.qualcomm.com> | 882cf2b6f81c7d94 |
| 01 | <20261023171433.820092-2-srinivas.kandagatla@oss.qualcomm.com> | a9d1adad83fbccd6 |
| 02 | <20261023171433.820092-3-srinivas.kandagatla@oss.qualcomm.com> | a5661198b10eefa8 |
| 03 | <20261023171433.820092-4-srinivas.kandagatla@oss.qualcomm.com> | d3fc9bbc5edd3bc3 |
| 04 | <20261023171433.820092-5-srinivas.kandagatla@oss.qualcomm.com> | f5f9f0a331fc18ca |
| 05 | <20261023171433.820092-6-srinivas.kandagatla@oss.qualcomm.com> | 44d44decc3900c57 |
| 06 | <20261023171433.820092-7-srinivas.kandagatla@oss.qualcomm.com> | 050960b4f49ceb98 |
| 07 | <20261023171433.820092-8-srinivas.kandagatla@oss.qualcomm.com> | 239d4182728fcab4 |
| 08 | <20261023171433.820092-9-srinivas.kandagatla@oss.qualcomm.com> | d95a3a023d7c1f5d |
| 09 | <20261023171433.820092-10-srinivas.kandagatla@oss.qualcomm.com> | dda484aa0cc2ee1e |
| 10 | <20261023171433.820092-11-srinivas.kandagatla@oss.qualcomm.com> | f4ef1c2360ad4571 |
| 11 | <20261023171433.820092-12-srinivas.kandagatla@oss.qualcomm.com> | 4f298614361853af |
| 12 | <20261023171433.820092-13-srinivas.kandagatla@oss.qualcomm.com> | 6f58176e3d928bec |
| 13 | <20261023171433.820092-14-srinivas.kandagatla@oss.qualcomm.com> | 6840504b082a3210 |
| 14 | <20261023171433.820092-15-srinivas.kandagatla@oss.qualcomm.com> | 74f9cc978195341d |
| 15 | <20261023171433.820092-16-srinivas.kandagatla@oss.qualcomm.com> | 6a1f94de977510e8 |
| 16 | <20261023171433.820092-17-srinivas.kandagatla@oss.qualcomm.com> | 809756fd08df7f27 |
| 17 | <20261023171433.820092-18-srinivas.kandagatla@oss.qualcomm.com> | e9dab1d701202b0d |
| 18 | <20261023171433.820092-19-srinivas.kandagatla@oss.qualcomm.com> | cba1ef80970e24c6 |
| 19 | <20261023171433.820092-20-srinivas.kandagatla@oss.qualcomm.com> | 06e577ab7fe795d1 |
| 20 | <20261023171433.820092-21-srinivas.kandagatla@oss.qualcomm.com> | b71b712ea6e1b1b6 |
| 21 | <20261023171433.820092-22-srinivas.kandagatla@oss.qualcomm.com> | 383c58ca2b839d3c |
| 22 | <20261023171433.820092-23-srinivas.kandagatla@oss.qualcomm.com> | 6b5608206e4140e1 |
| 23 | <20261023171433.820092-24-srinivas.kandagatla@oss.qualcomm.com> | 8f806202c4fc075e |

Topology source of the series (public, BSD-3-Clause): `github.com/Srinivas-Kandagatla/audioreach-topology`, branch `glymur`, commit `b94d118dff5f334b8633338268ccf148a482b1d2`; the T14s file carries SP and SP_VI with a cal blob of their unit.

What the series does (Verified from the mails): two ASoC core patches add a link flag `multi_direction_codecs` (codec DAIs of the other direction get `hw_params`/`hw_free` and stream events, with a params fixup); the SDW layer gets per-direction stream runtimes; the wsa884x gets a VI sense capture DAI and a thermal zone; AudioReach parses control links from the topology, runs the VI module in a calibration mode with per-speaker events, caches and restores R0/T0, exposes mode, R0/T0, live T0 and calibration state as mixer controls; the machine driver puts the VI DAIs on the WSA Playback link; the topology puts the SP chain in the playback graph and the VI chain in a graph registered under the same DAI id, so ONE `GRAPH_OPEN` carries both subgraphs and the control link. Patch 16 pins the VI chain to 8 kHz, 32 bit in C.

Review state (Verified from the thread): Mark Brown 2026-10-28, "please resend this once it applies directly against my tree" (the series needs the prerequisite series `20261023171316.819857-1-srinivas.kandagatla@oss.qualcomm.com`, "AudioReach and WSA88xx fixes", not in our tree). Konrad Dybcio asks for DT comment changes only. Fabian Renn-Giles reported on a Yoga Slim 7x (X1E80100, the same SoC family as ours, 4 amplifiers): the card probes and normal playback through the SP graph runs, but calibration times out waiting for V/I and R0/T0 stay 0; the amplifier stays gated; Hamoa din ports are 10 and 11. The author replied that a SoundWire runtime-PM issue also caused such timeouts and asked to try with runtime PM disabled. He also reported the `audioreach_get_module_priv_data()` over-read (`struct_size` counts `__le32` elements, `mod_array->size` is bytes). Our tree has the same expression in `topology.c` (`kzalloc_flex(*pdata, data, le32_to_cpu(mod_array->size))`) and is exposed to the same over-allocation and over-read when a module carries a config blob; our topology has no such blob (the calibration travels in the sp11cl file), so we are not exposed today. (Inference from reading both.)

Evaluation, design A (ours, 0013 to 0015) against design B (RFC):

| Criterion | A: separate links + guard | B: V/I on the playback link | Basis |
|:--|:--|:--|:--|
| Starts V/I with playback, no supervisor | no, needs a trigger FE and a supervisor | yes | RFC patches 02, 20; our 0015 |
| Control link across graphs (H3) | yes, unproven | no, one `GRAPH_OPEN` | topology reading |
| Needs a dummy front end (H10) | yes | no | section 4 |
| ASoC core change | none | yes (`soc-pcm.c`, `sdw`), RFC, flag gated | patches 02, 03 |
| Hardware evidence on X1E80100 | none | none positive: Hamoa report fails at V/I; T14s Gen7 (Mahua) is the tested machine | cover letter, Fabian mail |
| Upstream state | ours, local | RFC, not accepted, does not apply to a plain tree | Mark Brown mail; `patch --dry-run` on the composed tree: 01 and 03 apply, 02 hunk 6 fails, 04 and 05 fail against our 0010, 0011, 0013 |
| Features we lack | no live T0 or calibration mode | calibration mode, R0/T0 cache, T0 readback, thermal zones | patches 08, 11, 17 to 19, 21 |
| Our guard | built in | would need rework: the V/I stream starts with playback, so the check "V/I running" must move from `startup`/`prepare` to the amplifier unmute | 0015 code |

Decision (Inference, honest): B is the better architecture and removes H3, H10 and the supervisor. It is not "clearly" better today, because its only X1E80100 report fails exactly at V/I delivery and it conflicts with four of our patches. Therefore: M14 keeps design A with the generated topology as an experiment (the guard keeps the speakers muted if it fails); M15 adopts B, as follow-up patches 0017 and up, only if M14 shows H3 or H10 or H4 fail. I did not write 0017+ in this session: a port needs the prerequisite fixes series, the replacement of our 0013 DAI layout by the RFC's one-cell binding, and a guard rework, each testable only with a kernel build and the device; shipping unbuilt ports would be a guess. Plan for M15 if needed, in order: prerequisite fixes (including the `priv_data` size fix), RFC 01 to 03 and 16 on top of 0009, our 0013 reduced to the RFC DAI layout plus sense registers, RFC 07 replaced by our file-based control links (keep the guard input), RFC 20 and DT of 0016 changed to put the VI DAIs on the playback link, guard check moved to unmute, then RFC 08 to 19 as needed. Every patch keeps `Assisted-by: Claude Sonnet 5.5`, no Signed-off-by from us; imported RFC patches keep their upstream authorship and tags.

## 6. R0/T0 for the first run and the nominal policy (Inference)

Facts: the ACDB gives Re 4.924 and 4.758 ohm (Q24, parameter `0x08001535` of instance `0x4024`); T0 25 degC assumed; the thermal coefficient 0.00406 per degree is from the Argon report, unverified. A real Re 10 percent above nominal makes the DSP temperature estimate off by about 25 K. The generator writes the nominal file only on request (`build-closedloop.sh --nominal-cal`); this session did not write one into `out/firmware-private/audio` (a copy exists only inside the harness work directory).
Recommendation: the first test boot may allow nominal calibration (`sp11.allow_nominal=1`) on a dedicated entry that is not the default, under these limits: (1) only after step B of `2026-10-30-closed-loop.md` section 8 passes (V/I data are real, not zero); (2) the volume stays at the minimum step; the 0001, 0002, 0004, 0005 caps stay; (3) tones of at most 2 s with 3 minutes of silence between them, at most 10 tones; (4) the ADSP diagnostics event latches the guard; any latch ends the session (power off); (5) the measured Re from the V/I recording must lie within 80 to 125 percent of nominal; if it does not, do not continue and treat it as the sense scaling error of H2; (6) the nominal file is deleted after the test; a measured file replaces it once the calibration mode exists (M15 or the manual meter measurement). The kill entry `sp11.nospk` stays next to it.

## 7. What the M14 ISO can contain for speakers, and what needs M15

M14 kernel (already carries 0010 to 0016), firmware and user space only, all private-mode (S5, D25), the public ISO carries none of it:
- `X1E80100-Microsoft-Surface-Pro-11-tplg.bin` from `build-closedloop.sh` with `SP11_TOPOLOGY=1`, installed over the public file of the same name in the private image only (the kernel asks for this one name). Hash above.
- `...-sp11cl.bin` (SHA-256 `2eb5a1144d7718422210fd634d2b29f3c318025d56959b501e2c7a7c501ab280`), and `...-sp11cal.bin` only on the first-test entry.
- Boot entries `speakers (gated)` (`m13-spk`) and `speakers kill`; `sp11.allow_nominal` only on the dedicated first-test entry.
- User space: a supervisor that opens the MultiMedia5 capture (device index 4, any format, no read) before any playback, then runs the playback; UCM must not start playback by itself. Collector additions: `/sys/kernel/debug/sp11/guard`, `dmesg | grep sp11`, the card PCM list (MultiMedia5 capture must exist), hashes.
What may happen with this: speakers stay muted (guard closed) or, if H3, H4 and H10 are favourable, play at the minimum step. It cannot be promised without a device run.
Needs M15 (kernel): design B if A fails; calibration mode and R0/T0 and T0 readback; the `priv_data` size fix; the parser error propagation; moving the guard check to the unmute. Nothing in the generated firmware needs a kernel rebuild to be used.

## 8. Unknown and guesses

H3 and H10 (section 4); the SPv5 diagnostics event layout; the sense front end gain (H2); the port map; whether the V/I stream of the Windows ADSP image carries data on Linux; `0x07001011`, `0x07001013`, `0x07001098` module names. The choice of the order MFC, SP, LOGGER follows the Qualcomm graphs, not the Windows order (SAL, logger, SP, splitter, logger, sink); calibration records are per module and do not depend on it (Inference).
