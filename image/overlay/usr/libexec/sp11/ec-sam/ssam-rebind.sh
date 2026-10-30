#!/bin/sh
# R10: opt-in test; use the actual SAM-bound device name, never a guessed serial port.
case " $(cat /proc/cmdline) " in
    *" sp11.ssam_rebind "*|*" sp11.ssam_rebind=1 "*) ;;
    *) exit 0 ;;
esac
drv=/sys/bus/serial/drivers/surface_serial_hub
[ -d "$drv" ] || exit 0
for d in "$drv"/serial*; do
    [ -e "$d" ] || continue
    name=${d##*/}
    printf '%s\n' "$name" > "$drv/unbind" || exit 1
    sleep 2
    printf '%s\n' "$name" > "$drv/bind" || exit 1
done
