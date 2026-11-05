# Rev23: Type Cover, USB and SAM shutdown (2026-11-03)

Scope: private `out/device-logs/m16-20261103-final32/`, rev22, safe
`3edfc8b6-582e-4d5e-98bb-26e3cde07d52` and debug
`15c54307-6dd6-473d-8c41-6c4b7c8ad46e`. These are two individual boots,
not a controlled sequence with verified predecessor and successor. Reported
behavior is keyboard frozen in safe, working in debug after reboot; it is not
linked in the capture to a specific physical keyboard or a specific event node.
Raw captures stay private. **No REA used:** the available Linux source and
runtime observations already identify the missing discriminating evidence;
static Windows code cannot establish which physical input or transition failed.
No Windows binary was analyzed and there are no REA evidence IDs to claim.

## Observations

| Grade | Observation | Evidence and limit |
|:--|:--|:--|
| Verified | Both boots enumerate keyboard `045E:09AE` on SSAM `01:15:02:01:00`, and mouse/touchpad `045E:09AF` on `01:15:02:03:00`, under `surface_aggregator_platform_hub`; `045E:0C80` is SPI touchscreen/stylus. Descriptors and bindings do not establish key delivery. | Both `dmesg.txt.gz`, registration near +2.5 s; safe `extra-ec-sam.txt.gz` lists both HID bindings. |
| Verified | Safe USB tree has only root hubs and Ugreen `0bda:9210` mass storage, no USB keyboard at that snapshot. USB `3-1` address `-71` recovers to this storage device. Debug dmesg also names it mass storage; debug has no full USB tree captured. | Safe `usb-lsusb-tree.txt.gz`, `usb-devices.txt.gz`, `usb-dmesg.txt.gz`; debug `dmesg.txt.gz`. This describes the Ugreen endpoint, not necessarily every feature of a physical hub. A missing/failed or Bluetooth keyboard is not excluded. |
| Inference | If the reported keyboard is the attached `09AE` cover, its enumerated data path is SAM over UART, not USB-C; the observed Ugreen failure is not evidence of a failure in that path. Shared system/EC effects or an unenumerated external keyboard remain possible. | Device ancestry and USB tree above; operator confirmation and input test still required. |
| Verified | Both use firmware 27.201.139 and probe logs say `shutdown mode: default`. Safe rotor later chose **silent**, with sysfs readback `silent` and counter 1. Its journal records a reboot request at +94.22 s and continues through at least +118 s; it does not capture final `device_shutdown()` or the successor boot. No `sp11.ssam_shutdown` or `sp11.ssam_rebind` argument; rebind was skipped. | Safe `cmdline.txt.gz`, `extra-rotors.txt.gz`, `extra-ssam-shutdown-mode.txt.gz`, `journal.txt.gz`; probe message predates rotor. Silent is the **outgoing** policy if still set when shutdown executes; it does not describe the policy of the boot that preceded safe. |
| TBD | Debug runtime shutdown mode and its predecessor mode are unknown. Its collector stopped early, has no rotor or SSAM extra file, and live kmsg ends at ~64 s in an unexplained reset; it is not a controlled SAM shutdown. | Debug `STATUS`, `kmsg-live-15c54307-6dd6-473d-8c41-6c4b7c8ad46e.txt`; absence of a userspace rotor line from kmsg proves nothing. |
| Verified | Safe binds KIP hub, three KIP HID children, battery, AC and KIP tablet switch; serial runtime PM says `unsupported`, not suspended. SAM UART `b88000.serial` is active in both genpd snapshots. Safe pinctrl assigns GPIO 8–11 to UART and 91 to `serial1-0`; debug has no equivalent full TLMM pinctrl capture. | Safe `extra-ec-sam.txt.gz`, `pinctrl.txt.gz`, both `genpd_summary.txt.gz`. Snapshots neither identify shared rails nor exclude a transient loss. |
| Verified | Both enumerate KIP tablet switch; no current switch state or SSAM event stream was captured. No SAM timeout/error is apparent in the available dmesg, journal/session journals or debug live kmsg. Safe `sound.txt.gz` records a separately latched speaker fault; it does not identify keyboard cause. | `dmesg`, `journal`, `session-first-journal`, `session-user-journal`, `sound` (where present). Debug's early collection and normal log level mean absence is not proof that notifications were delivered. |

## Shutdown and competing hypotheses

- **Verified, source:** Linux probe sends D0-entry then display-on
  (`sources/linux/drivers/platform/surface/aggregator/core.c:694`); default
  shutdown disables registered event notifications, sends display-off, then
  D0-exit and continues after errors (`core.c:383`). Failed event disable
  rolls back earlier disables (`controller.c:2566`). The IRQ handler's queued
  event release is TODO (`controller.c:2674`). None demonstrates an actual
  failed notification in these boots.
- **Verified, source:** patch `0007` is in `kernel/series`, and `silent` returns
  from the SAM shutdown handler without these three operations. On DT, the
  separately registered platform hub is not a child of serdev (`core.c:741`);
  unbind's `ssam_remove_clients(&serdev->dev)` (`core.c:776`) therefore does
  not provide the assumed orderly child removal. Do not use the old unbind or
  rebind proposal as a recovery. Existing diagnostic `clean` also changes
  client lifetime and remains unproven; do not make it the default.
- **Verified, source:** arm64 restart invokes EFI ResetSystem first if runtime
  services are enabled (`sources/linux/arch/arm64/kernel/process.c:130`);
  default EFI reset is cold, subject to quirks and capsules
  (`sources/linux/drivers/firmware/efi/reboot.c:13`). The actual final
  firmware action, any EC interaction, and completed reboot are not captured.
- **Hypothesis: EC/cover state across reboot.** Stale notifications, D0,
  reset ordering or cover state could leave a bound device with no key events.
  Fixed predecessor policy plus next-boot counts, switch state and shutdown
  evidence would discriminate; enumeration alone cannot.
- **Hypothesis: posture filtering.** KIP may report folded in laptop posture,
  causing a compositor to ignore a functioning cover. The public SP11
  [POS tablet-switch patch](https://patchew.org/linux/20260829-surface-pro-11-aggregator-registry-fixes-v1-0-ebf5cca9d205%40gmail.com/20260829-surface-pro-11-aggregator-registry-fixes-v1-2-ebf5cca9d205%40gmail.com/)
  reports this after suspend/resume, not after reboot. Measure KIP state and
  kernel input counts before applying held patch 0002; neither applicability
  to this freeze nor an erroneous state has been established.
- **Hypothesis: USB-C parity.** An orientation-only DT variant might cure the
  Ugreen `-71`; it could affect an external USB keyboard, or have an indirect
  system effect, but a cover improvement would require an observed causal
  link. Keep predecessor, SSAM mode, connection and GPU fixed across that A/B.
  Debug versus safe by itself changes GPU and orientation and is confounded.

The older M13 note's claims that a `silent` failure excludes all shutdown
requests, that all earlier boots used default mode, and that Windows Fast
Startup is the most likely modifier are too strong: silent still leaves prior
runtime state, other shutdown operations and firmware reset uncontrolled, and
no causal probability or Windows boot type was measured. Treat them as
hypotheses. No speculative EC/PMIC operation or new shutdown patch is justified.

## Public comparison (accessed 2026-11-03)

- [linux-sp11/Arch image](https://github.com/dwhinham/archiso-aarch64-sp11)
  reports attached Flex keyboard support; the [upstream author patch](https://patchew.org/linux/20260829-surface-pro-11-aggregator-registry-fixes-v1-0-ebf5cca9d205%40gmail.com/20260829-surface-pro-11-aggregator-registry-fixes-v1-2-ebf5cca9d205%40gmail.com/)
  identifies a KIP/POS problem after resume, not this reboot failure. Earlier
  local reference inspection is in `2026-10-30-keyboard-reboot.md`.
- [Fedora SP11 guide](https://github.com/rjindael/fedora-surface-pro-11)
  reports attached keyboard working; [Ubuntu SP11 guide](https://github.com/denisix/ubuntu-surface-pro-11)
  describes tablet mode via SAM. Neither establishes a fix for this boot pair.
  [Ubuntu/Denali discussion](https://github.com/jglathe/linux_ms_dev_kit/discussions/57)
  discusses separate GRUB/keyboard initialization and experimental aggregator
  sleep recovery; reports are not evidence that this kernel has the same fault.
- Targeted postmarketOS searches found no specific SP11 Type Cover reboot-fix
  source; this is a search limitation, not evidence none exists. No external
  code or firmware is adopted. Public reports do not prove a device-specific
  power sequence or justify a firmware write.

## Capture integrity

SHA-256 is over compressed files as stored. Safe: dmesg
`7d6a1534a9a5ab2ea466a04de0e393b5579b69da1c3b5e0bb81bebd679278ebf`, journal
`f47efc556034c9ac5dbcfdeefdf09c1c3997b56f83e0721da9ce921e10fe9b7c`,
extra-ec-sam `445bb25b9ce9861b1fd5ffb72770d2223195002575e4354f4c07a76386a2e921`,
extra-rotors `942f4121e5e5c0ae1afb111278ab9a2cb9d53d8894645a273eb4a449c2fd9da1`,
extra-ssam-shutdown-mode `89a49b83e60b1f283f296ff76ff68434cdc74eaf8d0751d87f89bf6cbecf6797`,
usb-devices `1cdb828788eb2028ec3b169f348cff3a4f9d47e68982325d5c8379531d759d5b`,
pinctrl `011689fa644297a1f72c97107b2f27461252389adb99b33df8ffdbbbff67ebcd`,
genpd `7caab728435d0b7f02b3ecec2c2f1cfc844902fce36e7677463b15b1d8936b5e`.
Debug: dmesg `f33032e2148c6b04e7e47c284fafc2473030ba7cc6d40e4b4d41e10aa8947169`,
genpd `4a957e5fa13997cfb318385f28e75fbaf18d133804d8582f19c0fdf8dc578693`,
live kmsg `9bcb1a7a2ca947969dd47435846cf0c377c6ac828a9f94bed96d953c577510d2`.

## Rev24 follow-up: POS series and reboot-state analysis

**Public report, not a device observation:** Whinham's [v1 series](https://lore-kernel.gnuweeb.org/platform-driver-x86/20260829-surface-pro-11-aggregator-registry-fixes-v1-0-ebf5cca9d205%40gmail.com/T/) removes the SAM sensor HID, substitutes POS for the KIP tablet switch, and adds fan and performance-profile clients. The [v2 tablet patch](https://lists.openwall.net/linux-kernel/2026/09/18/2759) retains the one-line KIP-to-POS substitution and adds a Fixes tag. The author reports KIP stuck folded after **suspend/resume**, causing desktop environments to ignore cover keyboard and mouse; POS corrected that case. A [maintainer reply](https://lore-kernel.gnuweeb.org/platform-driver-x86/20260918-surface-pro-11-aggregator-registry-fixes-v2-1-c4ed9335814a%40gmail.com/T/) reports the series applied to a local review branch; that alone is not proof of a particular release or of behavior on this unit.

- **Verified, source:** v7.3's SP11 registry group uses KIP while the POS node and driver are already present (`sources/linux/drivers/platform/surface/surface_aggregator_registry.c:408`; `surface_aggregator_tabletsw.c:323`). Probe queries the selected switch, publishes initial `SW_TABLET_MODE`, then registers a notifier and schedules a further query (`surface_aggregator_tabletsw.c:143`, `:158`, `:166`, `:182`). KIP marks folded, disconnected, book and unknown as tablet (`:244`); its state is readable through sysfs (`:70`). Thus, **inference**: a wrong initial KIP result after a reboot could cause desktop filtering while HID remains bound and still produces keys. No KIP state, key-event count or compositor decision was captured here; the upstream resume report does not establish a reboot fault. POS changes the posture client, not HID delivery, EC reset, or the KIP hub. POS can also fail to probe or report an unknown/tablet state; its driver selects the first source and warns on multiple sources (`:513`).
- **Verified, source and patch:** `kernel/series` includes local 0001 and 0003, but not held 0002. Local 0001 removes the upstream series' sensor node and also the pen-stash node for this cover; 0003 adds the fan node but deliberately excludes the upstream performance-profile node. Held 0002 makes exactly the upstream POS substitution, with context adapted to both local removals. Applying 0001, 0003, then held 0002 to a temporary copy of the pinned registry with `patch --batch --fuzz=0 -p1` succeeded. This is a patch-application check, not a full-series build or test. 0007 is separately integrated in `core.c`.
- **Decision:** A targeted backport is justified as an opt-in diagnostic and as a candidate for the independently reported resume defect. Use held 0002 rather than create a duplicate patch; pin/review the upstream source and preserve its attribution if the kernel owner adopts it. No unconditional release for this reboot symptom until local posture/input checks and normal project gates pass. Do not import the performance-profile hunk; S6 and the current dossier exclude that policy change. A concrete owner request is in `patches/rev24-pos-test-request.md`.

**What might persist (hypotheses, not findings):** Linux allocates new controller/hub software state at probe (`aggregator/core.c:654`; `surface_aggregator_hub.c:167`), so the old Linux hub flag/refcount does not itself survive reboot. The KIP hub registers a notifier, queries connection and adds child clients; disconnection marks children hot-removed and schedules their removal (`surface_aggregator_hub.c:67`, `:127`, `:155`, `:293`). Enumeration establishes sufficient connection/descriptor response for binding, not continuing HID notifications. Controller event registrations are reference-counted and sent to the EC (`aggregator/controller.c:2467`); default shutdown attempts to disable them, then sends display-off and D0-exit, while 0007 silent skips that shutdown handler work (`aggregator/core.c:383`; patch 0007). A failed disable rolls earlier disables back (`controller.c:2545`); non-D0 queued-event release is unimplemented (`controller.c:2674`). Probe sends D0-entry/display-on (`core.c:700`). EC-side event enablement, power/posture or cover state **might** persist across a restart or be cleared by a reset; neither persistence, the final shutdown callback, nor the reset domain of the debug crash is known. A normal default-versus-silent comparison changes a bundle of three operations, not a specific command or a proven hardware reset. No justification for EC commands, callback implementation or hub lifecycle edits follows.

Rev24 controlled comparisons and interpretation are in `test-plan.md` §7. The Ugreen retry and the SSAM cover are separate observed paths; neither the storage `-71` nor the crash establishes a causal mechanism for the cover. A reproducible correlation may still reflect a shared state, and a negative test does not exclude all SAM/USB interactions.

**Final34 follow-up:** the `silent` observation above belongs to the older
final32 safe boot. The later final34 safe boot reports rotor selection and
sysfs readback `clean`, while its keyboard outcome remains unknown. See
[final34 evidence](2026-11-03-rev24-final34-keyboard.md) and the prioritized
rev25 test in `../test-plan.md` §8.
