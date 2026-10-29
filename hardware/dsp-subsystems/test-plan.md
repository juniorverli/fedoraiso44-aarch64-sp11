# DSP M9 evidence plan

Run this only as part of the next already scheduled device boot. Every device
boot interrupts the operator's Windows PC. All commands below are read-only:
no module load, rebind, remoteproc start/stop/crash, tracing write, firmware write,
charge threshold write or thermal/charging limit change. Speakers stay off.

## 1. Image preparation (request to image owner)

Refresh `collector/dsp-subsystems.sh` as
`/etc/sp11-log-collector.d/dsp-subsystems.sh`. The existing image collector
sources this drop-in and saves `extra-dsp-subsystems.txt` privately on the log
partition. Its reads have timeouts. Keep D23 module policy and the existing
sound-off DT assertions.

Use the existing `SP11 debug, USB + DSP trace` (`usbdbg`) entry for the next
planned DSP capture, or add these arguments to the entry that will be tested:

```text
qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink trace_buf_size=8M
```

The image must configure this before boot; a read-only collector cannot turn on
tracing retrospectively. Syntax: `sources/linux/Documentation/admin-guide/kernel-parameters.txt:7725-7737`.
The buffer size is per CPU (`:7700-7701`). Keep the default GPU-off/speaker-off
policy. No extra reboot or PAS ordering experiment is requested.

## 2. Exact read-only collector commands

The installed drop-in already runs these. If an operator shell is available in
the same scheduled session, the exact command to repeat its complete snapshot
is:

```sh
sudo sh /etc/sp11-log-collector.d/dsp-subsystems.sh
```

No interactive shell is needed for normal collection. For an attached charger,
repeat a snapshot after the operator connects the normal charger to an available
port, without moving the root stick. The read-only subset below is sufficient
for charging evidence and never prints a serial field:

```sh
for p in /sys/class/power_supply/*; do
    [ -d "$p" ] || continue
    printf '\n== %s\n' "${p##*/}"
    for a in type status online present capacity voltage_now current_now power_now energy_now usb_type charge_type; do
        [ -r "$p/$a" ] || continue
        printf '%s: ' "$a"
        timeout 3 cat "$p/$a"
    done
done
timeout 8 systemctl show upower.service -p LoadState -p ActiveState -p SubState -p Result -p ExecMainStatus
timeout 8 journalctl -b -u upower.service --no-pager -n 60
```

Keep command output in private device logs under `out/`; summarize only
non-identifying facts in git. Do not infer charging from port capability values
alone or from a UPower connection failure.

## 3. Expected results and interpretation

| Check | Expected | M8 and meaning of failure |
|:--|:--|:--|
| Remoteproc | ADSP/CDSP `running`, Denali image names, no DSP fatal/watchdog/recovery | M8 passes state only; state does not establish service health |
| ADSP services | IPCRTR bound to `qcom_smd_qrtr`; PMIC bound to `qcom_pmic_glink_rpmsg`; charger PDR UP; QRTR node 5 service 66/v1/74 and 43/v2/20 | M8 passes. Neither battery nor UCSI depends on CDSP |
| CDSP services | IPCRTR and FastRPC bound, `/dev/fastrpc-cdsp*`, QRTR services including SSCTL/servreg | M8 fails; `driver=unbound` is now explicit |
| Early trace present | Command line has tracing arguments, `tracing_on=1`, requested GLINK event enables are 1, handshake rows start near DSP start; examine per-CPU overruns | M8 default has no tracing arguments. An empty trace cannot prove the remote never ACKed |
| GLINK handshake | VERSION negotiation, remote OPEN, local OPEN_ACK/OPEN, remote OPEN_ACK for IPCRTR and FastRPC; match edge, channel and LCID/RCID | CDSP control rows are separate from ADSP. Missing RX ACK after TX OPEN narrows transport/remote handling but does not prove Windows's missing step |
| Interrupt counts | Separate CDSP/ADSP IPCC GLINK counts and SMP2P ready/handover | M8: CDSP GLINK 6, ADSP 631. Counts alone cannot establish APPS-to-CDSP TX consumption |
| D23 | Only `BAT1` is a Battery supply; SAM `ADP1` plus UCSI supplies; no `qcom_battmgr` module or `qcom-battmgr-*` supply; modprobe dry run resolves to false | M8 device policy passes. The unbound power-supply auxiliary device is expected |
| Actual charging | With a normal charger attached, SAM `ADP1 online=1` and BAT1 charging/full state consistent with SAM power; record UCSI online/role/USB type at the same time | M8 is only Discharging, ADP1 offline; no charging conclusion. A full battery or firmware-held charge may report Full/Not charging and needs contextual interpretation, never a limit write |
| UPower | Readable service state and successful enumeration if the service is available | M8 `charge.txt` has only connection refused; inspect unit/journal, do not start/restart from collector |
| ADSP audio | Report any APM timeout and later successful SPF query if present; no audio playback | M8 opcode `1001021` times out despite audio PDR UP; audio owners retain S1 gate |

## 4. Host validation and release gate

The collector is a sourced shell drop-in; validate syntax with `sh -n` and
`bash -n`. Check its driver-link helper against bound, missing-driver and dangling
links, and its trace filter against both edges. Reproduce firmware header/hash
checks with `python3 -I hardware/dsp-subsystems/tools/mdtcheck.py sources/windows`.
Run `scripts/index.py --check` after metadata changes.

No kernel build is required for collector/documentation changes. If a functional
patch is later justified by REA, leave it under this component's `patches/`,
compile through `scripts/kernel-dev.sh` under its `out/.kernel-build.lock`, retain
both BTF options, run strict checkpatch and applicable DT validation, and request
the independent other-runtime hardware-value cross-check before `sw-ready`.

`pass` is the orchestrator's decision. This session remains blocked for the CDSP
fix until R-S1 and actual handshake evidence are resolved; M9 diagnostics alone
are not a working-CDSP claim.
