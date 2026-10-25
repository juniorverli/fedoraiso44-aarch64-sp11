#!/usr/bin/bash
# dracut module sp11-initrd-log (image worker, M4, decision D19 follow-up).
#
# The log collector runs in the real root, so a failure before switch-root leaves no logs. This
# module installs a hook that, when dracut reaches an initqueue timeout or the emergency shell,
# copies the initramfs journal, dmesg and rdsosreport.txt to /EFI/sp11-logs/initrd-<boot-id>/ on
# the ESP (FAT label BOOT), with the collector's cap and gzip rules.
# Added explicitly by /etc/dracut.conf.d/92-sp11-initrd-log.conf; never pulled in by dracut itself.

# called by dracut
check() {
    return 255
}

# called by dracut
depends() {
    echo initqueue
    return 0
}

# called by dracut
installkernel() {
    # vfat for the ESP; the nls tables its default mount options need. Missing names are ignored.
    instmods vfat fat nls_cp437 nls_ascii nls_iso8859_1 nls_utf8
}

# called by dracut
install() {
    inst_multiple blkid mount umount gzip journalctl dmesg sync find du df sort head cat date \
        mkdir rm sed tr modprobe awk grep readlink basename lsblk
    [[ -f /etc/sp11-log-collector.conf ]] && inst_simple /etc/sp11-log-collector.conf
    [[ -f /etc/sp11-boot-medium ]] && inst_simple /etc/sp11-boot-medium
    inst_script "$moddir/sp11-initrd-log.sh" /usr/libexec/sp11-initrd-log
    # sourced by dracut: the emergency hook runs before the shell or the poweroff, the initqueue
    # timeout hook when the root has not shown up after two thirds of rd.retry
    inst_hook emergency 60 "$moddir/hook-emergency.sh"
    inst_hook initqueue/timeout 98 "$moddir/hook-timeout.sh"
}
