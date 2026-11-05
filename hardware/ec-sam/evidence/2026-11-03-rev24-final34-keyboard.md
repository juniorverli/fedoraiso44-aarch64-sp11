# Rev24 final34: safe Type Cover evidence (2026-11-03)

Scope: private `out/device-logs/m16-20261103-final34/`, safe boot
`f736d653-ea76-4073-a5f7-08478e70b7d6` and debug boot
`e28d7229-c3d9-40c3-8bdd-3ab5635f13a8`. These are observations, not a
controlled predecessor/successor pair. The current report does not say whether
the keyboard was tried. Raw logs remain private. No REA or device commands
were used for this review.

## Findings

| Grade | Finding | Evidence and limit |
|:--|:--|:--|
| TBD | **Safe keyboard outcome:** the archive contains no identified cover key presses, count-only input capture, typing result or operator report of the keyboard on this boot. It therefore does not show that the earlier freeze recurred, nor that the keyboard worked or was fixed. A GNOME login, camera use and `09AE` binding cannot answer this. | Safe `session-first-journal.txt.gz`, `session-user-journal.txt.gz`, `journal.txt.gz`, `extra-ec-sam.txt.gz` and `libinput-device-names.txt.gz`; the full journal extends beyond the early session snapshots. The current report is silent on the keyboard. |
| Verified | Both boots enumerate `045E:09AE` keyboard and `045E:09AF` touchpad/mouse through SSAM; both enumerate a KIP tablet-mode input. Safe's collector lists the SSAM hub, `surface_hid` keyboard/touchpad bindings and the KIP switch driver. | Both `dmesg.txt.gz`; safe `extra-ec-sam.txt.gz`. These are registration and binding evidence, not continuing key delivery. There is no saved KIP `state`, `SW_TABLET_MODE` value or SSAM event stream. |
| Verified | During safe, GNOME's libinput logged five touch-jump detections for the `09AF` touchpad between +137.381 and +152.312 s, saying the jumps were discarded; it then rate-limited that warning. Thus touchpad reports reached libinput, but normal cursor movement, deliberate human touch and keyboard operation are not established. | Safe `journal.txt.gz`, decompressed lines 174158, 174176, 174178, 174266, 174268 and 174270. `session-user-loginctl.txt.gz` separately records an active Wayland user session. |
| Verified | Safe probe logged `shutdown mode: default` at +2.306 s. The userspace rotor subsequently selected **`clean`** at +46.922 s, and both the rotor snapshot and sysfs snapshot say `clean`; the counter was 2. The command line had no explicit mode override. | Safe `dmesg.txt.gz`, `journal.txt.gz` line 30389, `extra-rotors.txt.gz`, `extra-ssam-shutdown-mode.txt.gz` and `cmdline.txt.gz`. The prompt's `silent` assertion conflicts with these final34 records. `silent` is documented for the older final32 safe boot in the [rev23 evidence](2026-11-03-rev23-keyboard-parity.md); it cannot be substituted for the final34 snapshot. |
| TBD | The predecessor's mode and the value actually acted on by the final34 safe shutdown are unknown. A reboot request was logged at +165.325 s, and `STATUS` records a capture at +167.75 s, but no final SAM callback or verified successor is captured. Debug's runtime mode is not in its early collector snapshot, and its reset is not a normal controlled shutdown. | Safe `journal.txt.gz`, `STATUS` and the mode files above; debug `STATUS`, `cmdline.txt.gz`, session snapshots and live kmsg. Probe-time `default` is not the later runtime readback, and a selected mode is not proof that the shutdown handler ran. |
| Inference | Final34 provides no measured safe-versus-debug keyboard difference. The earlier safe-freeze/debug-working comparison remains an operator report from different, uncontrolled final32 boots; the report did not identify a physical keyboard or prove an event-layer failure. | [Rev23 evidence](2026-11-03-rev23-keyboard-parity.md) and the findings above. The final34 debug reset is assigned to the GPU worker; this review finds no evidence to attribute it to keyboard or SAM. |

The Type Cover's observed ancestry is SSAM over the serial hub, not the Ugreen
USB mass-storage path. The storage `-71` and an indirect USB/system effect
must be assessed independently; neither proves a cover-key fault. Preserve the
current USB-C orientation and DP recovery path for the first keyboard test.

## What the source supports

- The pinned registry selects KIP for SP11 and the tablet driver exposes its
  cached `state`, reports `SW_TABLET_MODE`, and queries KIP on probe
  (`sources/linux/drivers/platform/surface/surface_aggregator_registry.c:408`,
  `sources/linux/drivers/platform/surface/surface_aggregator_tabletsw.c:70`,
  `:143`, `:220`, `:244`). The [upstream POS patch](https://lists.openwall.net/linux-kernel/2026/09/18/2759)
  addresses an author's reported **resume** posture problem. Held local 0002
  substitutes the POS switch registration; neither source nor final34 shows that
  a reboot freeze on this unit is caused by KIP. Keep it opt-in and deferred
  until the baseline has been measured.
- Existing integrated patch 0007 makes `default` attempt notification disable,
  display-off and D0-exit; `silent` returns without those three operations in
  the SAM shutdown handler. Its `clean` mode additionally changes client
  lifetime. This is a bundle comparison, not an experiment on a specific EC
  command or proof of a reset domain. Do not select `clean`, unbind/rebind or
  add EC state-setting requests for the rev25 test.
- The shipped `image/overlay/usr/libexec/sp11/sam-mode-rotor` honors an
  explicit `surface_aggregator.shutdown_mode=` kernel argument without advancing
  its rotor. Verify the current parameter immediately before every reboot;
  the probe log and a previous boot's mode are insufficient.

The smallest next comparison uses the existing safe image, with matched setup
and `default` versus `silent` **outgoing** policy as the sole intended
variable and the same `default` successor. It also measures cover key presses,
desktop typing, touchpad behavior and KIP state. The exact procedure and
inconclusive cases are in `../test-plan.md` §8. If the symptom is not observed,
that result is a single negative observation, not proof of a fix.

## Local validation

In a temporary copy of the pinned Linux registry file, patches 0001 and 0003
followed by held 0002 applied with zero fuzz; the held patch's only resulting
line change was KIP to POS. This is not an integration build or a device test.
The rev25 command blocks passed `bash -n`, and the count-only Python probe was
exercised with simulated events for five presses, repeat/release filtering,
`SYN_DROPPED`, and an unavailable input device. The simulations check the
probe, not the hardware. `python3 scripts/index.py --check` returned
`21 components, 0 errors`.

## Capture integrity

SHA-256 is over the compressed files as stored. Safe:

| File | SHA-256 |
|:--|:--|
| `dmesg.txt.gz` | `1cd260f038dbfb4b663a9ba7715cc2e632065ec54b98eec03a61c751bfff9549` |
| `journal.txt.gz` | `06f22c07697e9bb1d8508d4248edaa9dc95556ad50628b0f838a21ed60f77814` |
| `extra-ec-sam.txt.gz` | `a5e133d7775b69a772389fecc5a70a33fade0335782fe1dceec40df1fb41685d` |
| `extra-ssam-shutdown-mode.txt.gz` | `a6cbe80394628a6144d52320bd7492935d40576458e33d20662092b19c4e6512` |
| `extra-rotors.txt.gz` | `9cabd49d7f8e3dd3e3cf0baa1fb970bac689c9bb1c0b0ad1cea2809890ef1a9d` |
| `libinput-device-names.txt.gz` | `c9376c3f2e0d2816a2213f88667d08a6fc69a895949bc670282553ce9f446949` |
| `session-first-journal.txt.gz` | `6ee1f31f834283a157adced476673f13169c07a6cb1b469bc78cfa5f1521b53f` |
| `session-user-journal.txt.gz` | `5ef65fc9ebf9d91f7fb5709c1371410367a2f3703866315b04e34b4ba6054813` |
| `cmdline.txt.gz` | `6be6364942c38fae8f6336dc1c870aa8e2520446242202f89e4477f7a6f1c952` |

Debug `dmesg.txt.gz` is
`5ccfb8cad3880e90223e3530b8fc250e48e8792c5dca8773824034dd5ddcef3b`;
`kmsg-live-e28d7229-c3d9-40c3-8bdd-3ab5635f13a8.txt` is
`bf36d57a3538c60d3738efb8cf21cb8c936e542a202d582b7d608a4ad78d2490`.
