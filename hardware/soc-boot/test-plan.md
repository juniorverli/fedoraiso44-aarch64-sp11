# SoC boot acceptance

Status: static checks only; no new device test in this session. The test machine
is the operator's Windows PC, so collect this during the next planned image boot,
then accumulate evidence across three planned cold boots. Do not add a reboot
solely for these readings.

Before the ISO: complete R-O1/R-K1 in the dossier. The packaged LCD DT and every
device variant must have ten CPUs, no reference from `system_pd` to SS3, CPU C4
and cluster CL4/CL5 retained, `/sound` and `swr0` explicitly disabled, and no
effectively enabled WSA8845. Keep GPU off in device entries and BTF enabled.

Have the image collector run these exact read-only commands and capture their
output in its existing private log destination:

```bash
nproc --all
lscpu -e=CPU,ONLINE,SOCKET,CORE
for name in possible present online; do
    printf '%s: ' "$name"
    cat "/sys/devices/system/cpu/$name"
done
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    printf '\n%s\n' "$policy"
    for name in scaling_driver related_cpus affected_cpus scaling_governor \
                cpuinfo_min_freq cpuinfo_max_freq scaling_min_freq scaling_max_freq \
                scaling_cur_freq stats/time_in_state; do
        [ -r "$policy/$name" ] || continue
        printf '%s: ' "$name"
        cat "$policy/$name"
    done
done
for state in /sys/devices/system/cpu/cpu[0-9]*/cpuidle/state*; do
    [ -d "$state" ] || continue
    printf '\n%s\n' "$state"
    for name in name desc disable latency residency usage time; do
        [ -r "$state/$name" ] || continue
        printf '%s: ' "$name"
        cat "$state/$name"
    done
done
cat /proc/asound/cards
journalctl -b -k --no-pager | rg -i 'psci|smp:|smpboot:|failed to boot CPU|cpuidle|cpufreq|scmi'
```

Collect the policy and idle loops both at collector startup and during its
existing later sample. Do not change governors, online CPUs, idle-state disable
attributes, charging limits, thermal limits or audio controls. Keep raw journal
output private; it may contain identifying data. If debugfs is already mounted,
the collector may also read `/sys/kernel/debug/pm_genpd/pm_genpd_summary` for
cluster-domain residency; mounting or changing it is not part of these commands.

Expected results: ten possible/present/online logical CPUs (Linux logical IDs may
be renumbered after node removal); three SCMI policies covering 4, 3 and 3 CPUs;
frequency observations within existing policy limits; retained idle-state usage
advancing when idle; no PSCI CPU-start errors; no active sound card or speaker.
Single frequency/counter snapshots cannot prove scaling or idle correctness.
Report observations across repeated samples and three boots reaching GDM/GNOME.
SS3 remains an unreferenced DT state definition; its presence as a definition
alone is not a failure. Re-enabling it needs a separate isolated test decision.
