# Type Cover frozen at the start of Windows after a Linux session (2026-10-30)

New operator fact (2026-10-30): after a Linux session the Type Cover keyboard freezes at the start of Windows. The M12 Linux session ran with `sp11-ssam-shutdown` off, so the kernel default shutdown handler was the only SAM shutdown code. Logs: `out/device-logs/m12-20261030/19f802a7-.../` (private, nothing copied here). Source: Linux 7.3 plus the full `kernel/series`, scratch tree outside the repository. Not used: REA. Nothing built, nothing run on the device.

## 1. Verified

| Fact | Source |
|:--|:--|
| The M12 Linux boot is healthy: SAM firmware 27.201.139 at +2.2 s, keyboard, touchpad and KIP switch enumerate, 3 kernel errors none from SAM | M12 `extra-ec-sam.txt.gz`, `dmesg.txt.gz` |
| Command line was `debug` entry, no `sp11.ssam_shutdown`, no `sp11.ssam_rebind` | M12 `cmdline.txt.gz` |
| The shutdown of that session is not in any log (live system, no persistent journal), so errors from the shutdown requests are unknown | M12 `STATUS` (uptime 166 s, cycle 2) |
| `.shutdown` sends, in this order: `ssam_notifier_disable_registered()`, display-off, D0-exit; errors are only logged | `drivers/platform/surface/aggregator/core.c:383-409` |
| `ssam_notifier_disable_registered()` stops at the first failing event-disable and re-enables every event it had already disabled, then returns the error. Shutdown ignores the error and still sends display-off and D0-exit. One failing disable therefore leaves all events enabled in the EC | `controller.c:2566-2593` |
| On DT the platform hub `surface_aggregator_platform_hub` is registered by hand without a parent. The registry registers every client (hub, `surface_hid`, tablet switch, battery, AC) as a child of that hub. `ssam_serial_hub_remove()` calls `ssam_remove_clients(&serdev->dev)`, which only walks direct children of the serdev device, so it removes none of them. The clients' notifiers are then torn down by `ssam_controller_shutdown()` (`WARN_ON(!ssam_notifier_is_empty())`, then `ssam_notifier_unregister_all()` disabling each event) | `core.c:754-761`, `:776-`; `surface_aggregator_registry.c:558`, `:568-572`; `controller.c:1349-1356`, `:2656-2669` |
| Consequence: the opt-in `sp11-ssam-shutdown.service` never was the orderly path described in `2026-10-30-keyboard-reboot.md` section 5 on this DT system; it equals default plus a flush. The flash-review verdict 4 ("after removing clients") is wrong on this point | same |
| D0-exit and D0-entry are sent only when `caps.d3_closes_handle` is set. On DT it is forced to true; on the Windows ACPI side `_DSM` function 8 of `MSHW0084` returns 1, so Windows uses D0-exit too. Function 5 returns `SSHP`, 6 returns 0x1388 (5000), 7 returns 0x1E (30), 9 returns 0x30 (48) as the DT defaults use | `controller.c:1100-1190`; `sources/windows/live-inventory/acpi/ssdt.dsl:577-615` |
| Display-off makes the EC hold the wake GPIO high and keep events queued until the host releases them or sends display-on. The wake IRQ handler does not release them (source TODO) | `controller.c:2019-2040`; `core.c` `ssam_irq_handle`, `controller.c:2674-2700` |
| The hibernation poweroff comment documents that on some models the EC itself disables events at poweroff and that the driver must restore them on the next start | `core.c:557-570` |
| Events Linux enables: KIP hub (TC 0x0e), tablet switch (TC 0x0e), `surface_hid` per instance (TC 0x15), battery and AC (TC 0x02). Fan and temperature register none | `surface_aggregator_hub.c:333`, `surface_aggregator_tabletsw.c:313`, `surface_hid.c:212`, `surface_battery.c:734`, `surface_charger.c:187` |
| Windows registry dump has no Fast Startup value (`HiberbootEnabled`) | `sources/windows/live-inventory/sam/reg-sam.txt` |

## 2. Inference

1. The default shutdown is wire-wise the Windows hibernation-poweroff shape (events off, display-off, D0-exit), so the freeze is not explained by D0-exit alone being sent. Rests on `core.c:557-570` and the `_DSM` function 8 value.
2. Hypothesis 1 (events left enabled) has a concrete path in the default code: the roll-back in `ssam_notifier_disable_registered()`. It needs one event-disable to fail at shutdown, which is plausible for KIP and battery sources and invisible in our logs. Rests on `controller.c:2566-2593` and the missing shutdown log.
3. Hypothesis 3 (ordering of HID clients versus D0-exit) is weakened: default never removes clients, and the unit did not either (section 1), so no past test has covered it. `clean` is the first test of it.
4. Hypothesis 4 (sending nothing) predicts that the EC stays in D0 with Linux's event set enabled, including events Windows never registers (KIP hub with the sequenced flag, battery, AC). A starting Windows driver that assumes a clean register state would not like that. Weakly against hypothesis 4.
5. A hybrid-boot (Fast Startup) Windows resumes its driver stack without a full initialisation. If it does, the EC must match what that stack remembers, and the Windows side never sees what Linux changed. A Windows boot type probe separates this case (see test step 6).

## 3. Unknown

- Which event-disable, if any, fails at Linux shutdown, and whether display-off or D0-exit gets a reply.
- Whether the Windows start is a full boot or a hybrid resume.
- Whether a Windows shutdown followed by a Windows boot leaves the keyboard working on this unit (assumed, not recorded).
- Whether detaching and re-attaching the cover revives the keyboard in Windows (decides EC versus cover state).
- Whether the cause is in the SAM shutdown at all: a Linux session leaves other state (cover HID modes from `hid-multitouch`, UART/GPIO state).

## 4. Patch and modes

`hardware/ec-sam/patches/0007-platform-surface-aggregator-add-a-shutdown_mode-param.patch`: parameter `surface_aggregator.shutdown_mode`, writable at `/sys/module/surface_aggregator/parameters/shutdown_mode`, logged at probe (`shutdown mode: <name>`).

| Mode | Sent at poweroff or reboot | Tests |
|:--|:--|:--|
| `default` | disable events, display-off, D0-exit (unchanged) | baseline, known to fail |
| `quiet` | disable events only | hypothesis 2: is D0-exit/display-off the poison |
| `silent` | nothing | hypothesis 4 |
| `clean` | from a reboot notifier: unregister the platform hub and its clients (each driver disables its own events, with reference counting), then display-off and D0-exit; `.shutdown` then sends nothing | hypotheses 1 and 3 |

`clean` keeps display-off, as the remove path does, so it differs from `default` in one thing: the clients are removed first. Applies to v7.3 and to v7.3 plus the full `kernel/series`; `checkpatch.pl --strict` reports only the missing Signed-off-by (by project rule). Not compiled. It will conflict textually with held `0006` in `remove()` and `probe()` context; rebase one of them when both move. The clean path unregisters the hub by name, so 0006 is not needed for it.

## 5. Image plan (for the image owner; nothing written here)

Add after `SP11 debug` in `image/kiwi/overlay/grub-arm.cfg.iso-template` (and the lorax template if it is still built), same arguments as `SP11 debug` plus the parameter and a distinct `sp11.entry`:

```
menuentry 'SP11 debug, SAM shutdown quiet' --id sp11-ssam-quiet ... {
	linux ... <SP11 debug arguments> surface_aggregator.shutdown_mode=quiet sp11.entry=ssam-quiet
	devicetree ... m12.dtb
	initrd ...
}
menuentry 'SP11 debug, SAM shutdown clean' --id sp11-ssam-clean ... {
	linux ... <SP11 debug arguments> surface_aggregator.shutdown_mode=clean sp11.entry=ssam-clean
	...
}
menuentry 'SP11 debug, SAM shutdown silent' --id sp11-ssam-silent ... {
	linux ... <SP11 debug arguments> surface_aggregator.shutdown_mode=silent sp11.entry=ssam-silent
	...
}
```

`surface_aggregator` is built as a module (`CONFIG_SURFACE_AGGREGATOR=m`); kmod and dracut read `surface_aggregator.shutdown_mode=` from `/proc/cmdline` when the module loads, so the argument works from the initramfs. The log collector must record the `shutdown mode:` line and the sysfs value. The kernel needs the patch in `kernel/series`, so this needs a new kernel build and image (kernel worker request).

## 6. Test procedure (one cold cycle per mode)

Run order: `silent`, `quiet`, `clean`. Between modes, boot Windows normally and confirm the keyboard works.

1. Boot Windows from the internal disk, confirm the Type Cover keyboard works at the lock screen, then Start, Shut down. Optional control, once: long-press the power button instead of shutting down Linux (no SAM shutdown at all) and boot Windows.
2. Boot the test USB with the entry for the mode under test.
3. In Linux: `dmesg | grep 'shutdown mode'` and `cat /sys/module/surface_aggregator/parameters/shutdown_mode` must show the mode. Type on the cover to confirm Linux input. Let the collector run.
4. `systemctl poweroff` (not reboot). Wait until the screen and power light are off. Do not touch the cover.
5. Remove the USB. Boot Windows (power button).
6. Observe and write down: keyboard at the Windows boot logo / PIN screen (types or not); after 60 s still frozen or recovered; detach and re-attach the cover (revives or not); touchpad working or not. In Windows PowerShell: `Get-WinEvent -FilterHashtable @{ProviderName='Microsoft-Windows-Kernel-Boot';Id=27} -MaxEvents 1 | Select-Object -ExpandProperty Message` (boot type 0 full, 1 Fast Startup, 2 resume from hibernate). Repeat step 5 once with Windows Fast Startup disabled (`powercfg /h off`) for the first failing mode only.
7. Boot Windows once more normally before the next mode.

| Result | Reading |
|:--|:--|
| `silent` works | sending any of the three requests is the problem; `quiet` then separates events from display-off/D0-exit |
| `silent` fails, `quiet` works | D0-exit/display-off is poison, events-off is needed or neutral |
| only `clean` works | events left enabled or client ordering (hypotheses 1, 3); make `clean` the default |
| all fail, cover re-attach revives | state is in the cover or EC session independent of shutdown requests; try a SAM request that power-cycles the cover, or document the limit |
| all fail, Fast Startup off fixes it | Windows hybrid resume issue; document "disable Fast Startup" |
