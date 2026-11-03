# SoC boot acceptance

On each of three planned cold boots, capture the following read-only output in
the private collector, including boot ID, entry, timestamps and whether the
system reached GDM. Sample the policy and idle loops again later in the same
boot. Do not add a reboot solely for these readings.

```bash
nproc
nproc --all
lscpu
lscpu -e=CPU,ONLINE,SOCKET,CORE
for name in possible present online; do
    printf '%s: ' "$name"; cat "/sys/devices/system/cpu/$name"
done
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
    [ -d "$policy" ] || continue
    printf '\n%s\n' "$policy"
    for name in scaling_driver related_cpus affected_cpus scaling_governor \
        cpuinfo_min_freq cpuinfo_max_freq scaling_min_freq scaling_max_freq \
        scaling_cur_freq stats/time_in_state; do
        [ -r "$policy/$name" ] || continue
        printf '%s: ' "$name"; cat "$policy/$name"
    done
done
for state in /sys/devices/system/cpu/cpu[0-9]*/cpuidle/state*; do
    [ -d "$state" ] || continue
    printf '\n%s\n' "$state"
    for name in name desc disable usage time; do
        [ -r "$state/$name" ] || continue
        printf '%s: ' "$name"; cat "$state/$name"
    done
done
journalctl -b -k --no-pager | rg -i 'psci|smp:|smpboot:|cpuidle|cpufreq|scmi|rcu.*stall|watchdog|lockup|CPU.*(offline|online|failed)'
```

Expect ten possible/present/online CPUs; `nproc` can be lower under affinity or
CPU quotas, so interpret it with `nproc --all` and the sysfs lists. Check for
three SCMI policies covering 0–3, 4–6 and 7–9, observed scaling within current
limits, advancing idle counters, and no CPU-start or related errors. M16's
safe capture showed only the first policy, so determine whether the other two
appear later and record absence explicitly. A single counter snapshot proves
neither scaling nor sustained idle behavior. Three successful boots and repeated
samples are required for acceptance; reset causation needs separate evidence.
Leave CPU online state, frequencies, idle settings and command line unchanged.
Maintain existing speaker and thermal safety rules.
