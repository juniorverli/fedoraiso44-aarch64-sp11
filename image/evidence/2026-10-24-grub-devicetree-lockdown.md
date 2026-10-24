# GRUB 2 `devicetree` under Secure Boot lockdown (Fedora 44)

Question (image/README.md "Secure Boot"): does the Fedora 44 GRUB 2 refuse `devicetree` when UEFI Secure Boot is on?

## Verified (source reading)

Package: `grub2-2.12-66.fc44` (aarch64 binaries `grub2-efi-aa64-2.12-66.fc44`), source RPM SHA-256 `6f0f5737f4066257e41c8a2d5e80895d0af63ed2624d42d5ab04ec3848709b69`, fetched with `dnf download --source grub2` in `registry.fedoraproject.org/fedora:44`. The Fedora patches were grepped for the paths below; the upstream 2.12 tree in the SRPM is the base.

1. `grub-core/loader/efi/fdt.c:175`: the command is registered with `grub_register_command_lockdown ("devicetree", grub_cmd_devicetree, 0, N_("Load DTB file."))`.
2. `grub-core/kern/command.c:93-102`: `grub_register_command_lockdown()` replaces the handler with `grub_cmd_lockdown` when `grub_is_lockdown () == GRUB_LOCKDOWN_ENABLED`. `grub_cmd_lockdown` (`command.c:82-90`) returns `GRUB_ERR_ACCESS_DENIED` with the message `devicetree: the command is not allowed when lockdown is enforced`.
3. `grub-core/kern/efi/init.c:123-127`: `if (grub_efi_get_secureboot () == GRUB_EFI_SECUREBOOT_MODE_ENABLED) { grub_lockdown (); grub_shim_lock_verifier_setup (); }`. So lockdown is entered exactly when UEFI Secure Boot is enabled.
4. No Fedora patch touches this. Patches that mention `fdt.c` or `command.c`: 0056, 0081, 0213, 0375, 0376, 0395; none contains "lockdown" or "secureboot" in its fdt.c hunk (`grep -l "fdt.c\|command.c" *.patch`; 0081 only changes how the module is built).
5. The Fedora aarch64 GRUB binaries contain the command: `devicetree` and `Load DTB file` occur in `/boot/efi/EFI/fedora/gcdaa64.efi` and `grubaa64.efi` of `grub2-efi-aa64-2.12-66.fc44` (`grep -a -c`), so the `fdt` module is built in and no `insmod` is needed.

## Conclusion

With Secure Boot enabled, `devicetree` fails with "not allowed when lockdown is enforced" and the entry cannot load the SP11 DTB. Grade: **Verified** for the code path; **TBD** for a runtime demonstration (QEMU with `vars.secboot.json` was not run: the kernel is unsigned, so the boot would stop earlier at shim). The consequence in `plan/decisions.md` D9 stands: Secure Boot is off for test boots. Signing our kernel with a MOK key does not lift lockdown, so it does not help `devicetree`.
