#!/bin/sh
# R10: orderly client removal before D0-exit. No firmware or policy writes.
case " $(cat /proc/cmdline) " in
    *" sp11.ssam_shutdown "*|*" sp11.ssam_shutdown=1 "*) ;;
    *) exit 0 ;;
esac
drv=/sys/bus/serial/drivers/surface_serial_hub
[ -d "$drv" ] || exit 0
for d in "$drv"/serial*; do
    [ -e "$d" ] || continue
    printf '%s\n' "${d##*/}" > "$drv/unbind"
done
exit 0
