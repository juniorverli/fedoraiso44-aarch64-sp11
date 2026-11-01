#!/usr/bin/env bash
# Self-test of the M15 Linux-side experiment scripts as installed in an image root (or the overlay), against fake sysfs, command lines and a
# fake boot medium (SP11_STATE_ROOT). Nothing real is touched. Prints PASS/FAIL lines; exit 1 on any FAIL.
#   rotor-selftest.sh ROOT        ROOT = extracted image root (L0) or image/overlay
# Covers: sp11-boot-state (files, markers, S4 refusal), SAM rotor (order silent clean quiet default, counter file), CDSP experiment (variants,
# guards, once per boot, timeouts, restore of the loader path), cpufreq cap (marker, mid-range, never performance), identity switch (marker),
# operator notices, GPU hooks (kept for later).
set -u
R=${1:?root}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
T=$(mktemp -d); trap 'kill $(jobs -p) 2>/dev/null; rm -rf "$T"' EXIT
fails=0
ok() { echo "PASS $1"; }
bad() { echo "FAIL $1"; fails=$((fails + 1)); }
eq() { [ "$2" = "$3" ] && ok "$1" || bad "$1 (got '$2', want '$3')"; }
L=$R/usr/libexec
BSX=$L/sp11-boot-state
export SP11_STATE_ROOT=$T/medium SP11_BOOT_STATE=$BSX SP11_NOTICE_DIR=$T/notice SP11_NOTICE_FILE=$T/notice.txt SP11_NOTICE=$L/sp11/operator-notice
mkdir -p "$T/notice" "$T/medium"
bs() { bash "$BSX" "$@"; }

# --- sp11-boot-state: plain files, markers, validation, S4 refusal
bs set sp11_test=3; eq "boot-state: set/get" "$(bs get sp11_test)" 3
[ -f "$T/medium/sp11/state/sp11_test" ] && ok "boot-state: one plain file per value (no grubenv)" || bad "boot-state: no plain file"
bs set sp11_other=x; bs unset sp11_test
eq "boot-state: unset" "$(bs get sp11_test)" ""
eq "boot-state: list keeps the others" "$(bs list)" "sp11_other=x"
bs set 'bad name=1' 2>/dev/null; [ $? -ne 0 ] && ok "boot-state: rejects a bad name" || bad "boot-state: bad name accepted"
bs marker enable-cpufreq-cap; [ $? -ne 0 ] && ok "boot-state: marker absent" || bad "boot-state: marker present without file"
: >"$T/medium/sp11/enable-cpufreq-cap"; bs marker enable-cpufreq-cap && ok "boot-state: marker present" || bad "boot-state: marker not seen"
eq "boot-state: markers listed" "$(bs markers)" "enable-cpufreq-cap"
rm -f "$T/medium/sp11/enable-cpufreq-cap"; bs unset sp11_other
(unset SP11_STATE_ROOT; bash "$BSX" get x >/dev/null 2>&1; [ $? -ne 0 ]) && ok "boot-state: refuses without a resolvable boot medium (S4)" || bad "boot-state did not refuse"
! grep -qE 'grub2?-editenv|save_env' "$BSX" && ok "boot-state: no GRUB environment tool" || bad "boot-state uses editenv"

# --- SAM rotor
: >"$T/param"; echo "" >"$T/cmd"
export SP11_SAM_PARAM=$T/param SP11_SAM_ORDER=$R/usr/share/sp11/sam-mode-order SP11_SAM_STATE=$T/sam-state SP11_SAM_CMDLINE=$T/cmd
seq=
for i in 1 2 3 4 5 6; do bash "$L/sp11/sam-mode-rotor" 2>/dev/null; seq="$seq $(cat "$T/param")"; done
eq "SAM rotor order over six boots (silent, clean, quiet, default, wrap)" "$seq" " silent clean quiet default silent clean"
grep -q '^SAM shutdown mode for this boot: clean' "$T/sam-state" && ok "SAM rotor record line" || bad "SAM rotor record line"
grep -q 'SAM shutdown mode for this boot: clean' "$T/notice/10-sam.txt" && ok "SAM rotor notice text" || bad "SAM rotor notice text"
eq "SAM counter (plain file on the boot medium) advanced to 6" "$(bs get sp11_sam_counter)" 6
echo "root=x surface_aggregator.shutdown_mode=quiet" >"$T/cmd"; : >"$T/param"
bash "$L/sp11/sam-mode-rotor" 2>/dev/null
eq "SAM rotor: explicit kernel-line mode wins, parameter untouched" "$(cat "$T/param")" ""
eq "SAM rotor: counter not advanced by an override" "$(bs get sp11_sam_counter)" 6
grep -q 'SAM shutdown mode for this boot: quiet' "$T/sam-state" && ok "override recorded" || bad "override recorded"
bs unset sp11_sam_counter; echo "" >"$T/cmd"

# --- CDSP experiment against a fake sysfs with a tiny fake kernel (a loop that turns `stop` into offline and `start` into running)
mkcd() { # NAME-of-dir: build a fake sysfs under $T/sys
	rm -rf "$T/sys"; mkdir -p "$T/sys/class/remoteproc/remoteproc0" "$T/sys/class/remoteproc/remoteproc1" "$T/sys/module/qcom_q6v5_pas/parameters" "$T/sys/module/firmware_class/parameters"
	echo cdsp >"$T/sys/class/remoteproc/remoteproc0/name"; echo adsp >"$T/sys/class/remoteproc/remoteproc1/name"
	echo running >"$T/sys/class/remoteproc/remoteproc0/state"; echo running >"$T/sys/class/remoteproc/remoteproc1/state"
	echo qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn >"$T/sys/class/remoteproc/remoteproc0/firmware"
	echo -1 >"$T/sys/module/qcom_q6v5_pas/parameters/keep_proxy_pds"; : >"$T/sys/module/firmware_class/parameters/path"
	[ "${1:-}" = ro ] && chmod 444 "$T/sys/module/qcom_q6v5_pas/parameters/keep_proxy_pds"
	: >"$T/sys/class/remoteproc/remoteproc0/log"
}
fakekernel() { # runs until killed; also records the parameter values seen at the start of each cycle
	local st=$T/sys/class/remoteproc/remoteproc0/state
	while :; do
		case $(cat "$st" 2>/dev/null) in
		stop) echo offline >"$st" ;;
		start) touch "$T/dm2"; echo "keep=$(cat "$T/sys/module/qcom_q6v5_pas/parameters/keep_proxy_pds") path=$(cat "$T/sys/module/firmware_class/parameters/path")" >>"$T/sys/class/remoteproc/remoteproc0/log"
			if [ -e "$T/crash" ]; then echo crashed >"$st"; else echo running >"$st"; fi ;;
		esac
		sleep 0.05
	done
}
cat >"$T/fake-dmesg" <<X
#!/bin/sh
echo "[ 1.0] earlier line"
[ -e $T/dm2 ] && echo "[ 9.0] sp11-glink: rx OPEN_ACK name=IPCRTR lcid=1 rcid=1"
:
X
chmod +x "$T/fake-dmesg"
runcd() { # ARGS: cmdline text ; runs the script once, with the fake kernel
	echo "$1" >"$T/cdsp-cmd"; rm -rf "$T/run"
	rm -f "$T/dm2"; fakekernel & local k=$!
	SP11_SYS=$T/sys SP11_RUN=$T/run SP11_CDSP_CMDLINE=$T/cdsp-cmd SP11_CDSP_FWDIR=$T/fw46 SP11_KMSG=$T/kmsg SP11_DMESG=$T/fake-dmesg \
		SP11_CDSP_WAIT_UP=5 SP11_CDSP_WAIT_STATE=4 SP11_CDSP_SETTLE=0 SP11_CDSP_PRESETTLE=0 bash "$L/sp11/cdsp-experiment" 2>/dev/null
	kill $k 2>/dev/null; wait $k 2>/dev/null
}
R1=$T/sys/class/remoteproc/remoteproc0
mkcd; bs unset sp11_cdsp_counter
runcd "sp11.entry=debug"
grep -q 'variant: 0 (fw=c1-00078 keep_proxy_pds=0 forced)' "$T/run/cdsp-experiment" && ok "CDSP experiment: variant 0 first (shipped firmware, keep_proxy_pds forced 0)" || bad "CDSP variant 0 first"
grep -q '^keep=0 path=$' "$R1/log" && ok "CDSP experiment: keep_proxy_pds forced to 0 during start, default firmware path" || bad "CDSP keep=0 during start: $(cat $R1/log)"
eq "CDSP experiment: keep_proxy_pds restored to the default (-1) afterwards" "$(cat $T/sys/module/qcom_q6v5_pas/parameters/keep_proxy_pds)" -1
eq "CDSP experiment: remoteproc restarted (running again)" "$(cat $R1/state)" running
eq "CDSP experiment: counter advanced to 1 before the restart" "$(bs get sp11_cdsp_counter)" 1
grep -q 'rx OPEN_ACK lines 1' "$T/notice/20-cdsp.txt" && ok "CDSP experiment: result and OPEN_ACK count in the notice" || bad "CDSP result notice"
[ ! -s "$T/run/cdsp-experiment-dmesg.txt" ] && bad "CDSP: dmesg lines not recorded" || ok "CDSP experiment: sp11-glink lines recorded"
# second start on the same boot (same RUN dir): refused
echo "sp11.entry=debug" >"$T/cdsp-cmd"
SP11_SYS=$T/sys SP11_RUN=$T/run SP11_CDSP_CMDLINE=$T/cdsp-cmd SP11_KMSG=$T/kmsg bash "$L/sp11/cdsp-experiment" 2>/dev/null
grep -q 'second start on this boot' "$T/run/cdsp-experiment" && eq "CDSP experiment: never twice per boot (counter unchanged)" "$(bs get sp11_cdsp_counter)" 1 || bad "CDSP: second start not refused"
# keep_proxy_pds not writable and no alternate pair: only variant 3 (the default) is realisable
mkcd ro; bs set sp11_cdsp_counter=0; runcd "sp11.entry=debug"
grep -q 'variant: 3 (fw=c1-00078 keep_proxy_pds=default)' "$T/run/cdsp-experiment" && ok "CDSP experiment: no pair, keep not writable: only the default variant 3 realisable, the rest skipped" || bad "CDSP skip of unrealisable variants"
# writable keep, no pair: counter 1 skips 1 and 2 and lands on the default variant 3; the parameter is written -1 for the start
mkcd; bs set sp11_cdsp_counter=1; runcd "sp11.entry=debug"
grep -q 'variant: 3 (fw=c1-00078 keep_proxy_pds=default)' "$T/run/cdsp-experiment" && ok "CDSP experiment: counter 1 without the alternate pair lands on variant 3 (default)" || bad "CDSP variant 3 selection"
grep -q '^keep=-1 path=$' "$R1/log" && ok "CDSP experiment: keep_proxy_pds default (-1) during start, default firmware path" || bad "CDSP keep=-1 during start: $(cat $R1/log)"
eq "CDSP experiment: keep_proxy_pds restored afterwards" "$(cat $T/sys/module/qcom_q6v5_pas/parameters/keep_proxy_pds)" -1
eq "CDSP experiment: counter now 4" "$(bs get sp11_cdsp_counter)" 4
# alternate pair present: variant 1 (c1-00046.1, default keep) sets firmware_class.path for the start and restores it; FULL POWER-OFF text only when the NEXT variant is alternate
mkdir -p "$T/fw46/qcom/x1e80100/microsoft/Denali"; echo x >"$T/fw46/qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn"; echo x >"$T/fw46/qcom/x1e80100/microsoft/Denali/cdsp_dtb.mbn"
mkcd; bs set sp11_cdsp_counter=1; runcd "sp11.entry=debug"
grep -q "^keep=-1 path=$T/fw46\$" "$R1/log" && ok "CDSP experiment: variant 1 starts with firmware_class.path at the alternate directory and the default keep_proxy_pds" || bad "CDSP variant 1 path: $(cat $R1/log)"
eq "CDSP experiment: firmware_class.path restored to empty afterwards" "$(cat $T/sys/module/firmware_class/parameters/path)" ""
grep -q 'ALTERNATE firmware' "$T/notice/20-cdsp.txt" && ok "CDSP experiment: alternate firmware flagged in the notice" || bad "alternate firmware not flagged"
mkcd; bs set sp11_cdsp_counter=2; runcd "sp11.entry=debug"
grep -q "^keep=0 path=$T/fw46\$" "$R1/log" && ok "CDSP experiment: variant 2 is c1-00046.1 with keep_proxy_pds forced 0" || bad "CDSP variant 2: $(cat $R1/log)"
mkcd; bs set sp11_cdsp_counter=0; runcd "sp11.entry=debug"
grep -q 'FULL POWER-OFF' "$T/notice/20-cdsp.txt" && grep -q 'NOT a reboot' "$T/notice/20-cdsp.txt" && ok "CDSP experiment: variant 0 -> next 1 uses the alternate firmware: FULL POWER-OFF, NOT a reboot" || bad "power-off text missing for next=1"
# guards: other entry, marker, bad state, crash
mkcd; bs set sp11_cdsp_counter=0; runcd "sp11.entry=safe"
grep -q 'not run: entry' "$T/run/cdsp-experiment" && [ "$(bs get sp11_cdsp_counter)" = 0 ] && ok "CDSP experiment: not on a recovery entry, counter untouched" || bad "CDSP ran on a non-main entry"
: >"$T/medium/sp11/disable-cdsp-experiment"; mkcd; runcd "sp11.entry=debug"; rm -f "$T/medium/sp11/disable-cdsp-experiment"
grep -q 'marker sp11/disable-cdsp-experiment' "$T/run/cdsp-experiment" && ok "CDSP experiment: disabled by the marker" || bad "CDSP marker not honoured"
mkcd; echo crashed >$R1/state; runcd "sp11.entry=debug"
grep -q "not stable" "$T/run/cdsp-experiment" && ok "CDSP experiment: skipped when the CDSP state is not stable" || bad "CDSP unstable state not skipped"
mkcd; echo offline >$T/sys/class/remoteproc/remoteproc1/state; runcd "sp11.entry=debug"
grep -q 'not run' "$T/run/cdsp-experiment" && ok "CDSP experiment: skipped while the ADSP is not running (timeout, no restart)" || bad "ADSP guard"
mkcd; touch "$T/crash"; runcd "sp11.entry=debug"; rm -f "$T/crash"
grep -q 'result state: crashed' "$T/run/cdsp-experiment" && eq "CDSP experiment: a crash after start is logged, loader path restored" "$(cat $T/sys/module/firmware_class/parameters/path)" "" || bad "crash not logged"
# the stop that never completes: nothing else is touched
mkcd; echo "sp11.entry=debug" >"$T/cdsp-cmd"; rm -rf "$T/run"
SP11_SYS=$T/sys SP11_RUN=$T/run SP11_CDSP_CMDLINE=$T/cdsp-cmd SP11_KMSG=$T/kmsg SP11_DMESG=$T/fake-dmesg SP11_CDSP_WAIT_UP=3 SP11_CDSP_WAIT_STATE=2 SP11_CDSP_SETTLE=0 SP11_CDSP_PRESETTLE=0 bash "$L/sp11/cdsp-experiment" 2>/dev/null
grep -q 'stop did not reach offline' "$T/run/cdsp-experiment" && eq "CDSP experiment: a stop that hangs times out, keep_proxy_pds untouched" "$(cat $T/sys/module/qcom_q6v5_pas/parameters/keep_proxy_pds)" -1 || bad "stop timeout"

# --- cpufreq cap
mkpol() { rm -rf "$T/cpu"; for p in 0 4 8; do d=$T/cpu/policy$p; mkdir -p "$d"; echo "$p" >"$d/related_cpus"; echo "400000 800000 1200000 1600000 2000000 2400000 3400000" >"$d/scaling_available_frequencies"
	echo "performance schedutil ondemand" >"$d/scaling_available_governors"; echo "${1:-schedutil}" >"$d/scaling_governor"; echo 400000 >"$d/cpuinfo_min_freq"; echo 3400000 >"$d/cpuinfo_max_freq"; echo 3400000 >"$d/scaling_max_freq"; done; }
cfenv() { SP11_CPU_DIR=$T/cpu SP11_RUN=$T/run2 SP11_CPUFREQ_WAIT=2 bash "$L/sp11/cpufreq-cap" 2>/dev/null; }
mkpol; cfenv
eq "cpufreq: the cap applies BY DEFAULT (median, index 3 of 7)" "$(cat $T/cpu/policy0/scaling_max_freq)" 1600000
grep -q 'scaling_max_freq 3400000 -> 1600000' "$T/run2/cpufreq-cap" && ok "cpufreq: default cap recorded" || bad "cpufreq default cap record"
mkpol performance; cfenv
eq "cpufreq: governor performance replaced by schedutil" "$(cat $T/cpu/policy8/scaling_governor)" schedutil
: >"$T/medium/sp11/cpufreq-uncapped"; mkpol; cfenv
eq "cpufreq: marker sp11/cpufreq-uncapped lifts the cap" "$(cat $T/cpu/policy4/scaling_max_freq)" 3400000
grep -q 'cap NOT applied' "$T/run2/cpufreq-cap" && ok "cpufreq: recorded and reported with the marker" || bad "cpufreq marker report"
rm -f "$T/medium/sp11/cpufreq-uncapped"
mkdir -p "$T/emptycpu"; SP11_CPU_DIR=$T/emptycpu SP11_RUN=$T/run3 SP11_CPUFREQ_WAIT=1 bash "$L/sp11/cpufreq-cap" 2>/dev/null; grep -q 'no cpufreq policy' "$T/run3/cpufreq-cap" && ok "cpufreq: no policy is reported, nothing written" || bad "cpufreq no-policy path"
grep -q '^scmi_cpufreq$' "$R/etc/modules-load.d/sp11-cpufreq.conf" && ok "modules-load.d loads scmi_cpufreq" || bad "modules-load.d scmi_cpufreq missing"
! grep -E 'printf +(performance|ondemand)' "$L/sp11/cpufreq-cap" >/dev/null && ok "cpufreq: never writes performance or ondemand" || bad "cpufreq writes a forbidden governor"

# --- identity switch (marker file replaces sp11.identity=none)
echo "root=live:CDLABEL=X rd.live.image" >"$T/idcmd"; export SP11_ID_CMDLINE=$T/idcmd SP11_MOUNT=true SP11_RUN=$T/run4
bash "$L/sp11/identity-switch" 2>/dev/null; grep -q 'no marker' "$T/run4/identity-switch" && [ ! -e "$T/run4/cmdline-effective" ] && ok "identity switch: no marker, nothing mounted (inject)" || bad "identity switch without marker"
: >"$T/medium/sp11/identity-none"; bash "$L/sp11/identity-switch" 2>/dev/null
tail -c 24 "$T/run4/cmdline-effective" | grep -q 'sp11.identity=none' && grep -q 'root=live:CDLABEL=X' "$T/run4/cmdline-kernel" && ok "identity switch: marker appends sp11.identity=none to the effective command line, real one kept" || bad "identity switch with marker"
grep -q 'identity-none' "$T/notice/15-identity.txt" && ok "identity switch: operator notice" || bad "identity notice"
rm -f "$T/medium/sp11/identity-none"; unset SP11_ID_CMDLINE SP11_MOUNT SP11_RUN

# --- thermal sampler: enabled by a marker file (drop-in), not by a kernel argument
grep -q '^ConditionKernelCommandLine=$' "$R/usr/lib/systemd/system/sp11-thermal-sample.service.d/10-sp11-marker.conf" && grep -q 'ExecCondition=/usr/libexec/sp11-boot-state marker enable-thermal-sample' "$R/usr/lib/systemd/system/sp11-thermal-sample.service.d/10-sp11-marker.conf" && ok "thermal sampler: marker drop-in resets the cmdline condition and reads sp11/enable-thermal-sample" || bad "thermal drop-in"
bs marker enable-thermal-sample; [ $? -ne 0 ] && ok "thermal sampler: off without the marker" || bad "thermal marker present"
: >"$T/medium/sp11/enable-thermal-sample"; bs marker enable-thermal-sample && ok "thermal sampler: on with the marker" || bad "thermal marker not seen"; rm -f "$T/medium/sp11/enable-thermal-sample"

# --- touch profile selector (default B, A by marker sp11/touch-conf-A)
mkdir -p "$T/touchshare"; cp "$REPO/hardware/touch-pen/userspace/iptsd-sp11.conf" "$T/touchshare/b.conf"
tsel() { SP11_TOUCH_CONF_B=$T/touchshare/b.conf SP11_TOUCH_DEST=$T/touch50.conf SP11_RUN=$T/trun bash "$L/sp11-touch-conf-select" 2>/dev/null; }
tsel; cmp -s "$T/touchshare/b.conf" "$T/touch50.conf" && grep -q 'profile B' "$T/trun/touch-conf" && ok "touch: profile B installed by default (no marker)" || bad "touch default B"
: >"$T/medium/sp11/touch-conf-A"; tsel
[ ! -e "$T/touch50.conf" ] && grep -q 'profile A' "$T/trun/touch-conf" && ok "touch: marker sp11/touch-conf-A selects A (no config file)" || bad "touch marker A"
rm -f "$T/medium/sp11/touch-conf-A"; tsel; [ -e "$T/touch50.conf" ] && ok "touch: removing the marker returns to B" || bad "touch back to B"

# --- GPU hooks (the two-step runs on line 1 only, through sp11.gpu_diag=1)
(
	set -u
	OUT=$T/gpuout; RUN=$T/gpurun; STATE=$T/state.log; BOOT_ID=bootB; mkdir -p "$OUT"
	say() { :; }
	CMD=$T/gcmd; echo "" >"$CMD"
	cmdline_has() { tr ' ' '\n' <"$CMD" | grep -qx -- "$1"; }
	sed "s|/run/sp11/gpu-test|$T/gpu-test|g; s|mkdir -p /run/sp11 2>/dev/null|mkdir -p $T 2>/dev/null|" "$REPO/image/component-inputs/gpu-state-hooks.sh" >"$T/hooks.sh"
	. "$T/hooks.sh"
	SP11_NOTICE_BIN=$L/sp11/operator-notice
	echo "boot bootA: previous boot died during step 2 (last marker: STEP2_SUB open-call; uptime 40 s, epoch 1)" >"$OUT/previous-boot-report.txt"
	sp11_gpu_hook_report
	grep -q '^GPU test: died during step 2' "$OUT/gpu-test-result.txt" && echo "PASS GPU hook: reports 'GPU test: died during step 2'" || echo "FAIL GPU hook died report"
	grep -q 'may RESET THE MACHINE' "$T/gpu-test" && grep -q "line 2" "$T/gpu-test" && echo "PASS GPU hook: the reset warning and line 2 are in the notice text" || echo "FAIL GPU reset warning"
	: >"$OUT/gpu-test-result.txt"; echo "boot bootA: ended normally (DONE)" >"$OUT/previous-boot-report.txt"; sp11_gpu_hook_report
	grep -q '^GPU test: survived' "$OUT/gpu-test-result.txt" && echo "PASS GPU hook: reports 'GPU test: survived'" || echo "FAIL GPU survived report"
	bs set sp11_gpu_state=failed; echo "sp11.gpu_retry=1" >"$CMD"; sp11_gpu_hook_report
	[ -z "$(bs get sp11_gpu_state)" ] && echo "PASS GPU hook: sp11.gpu_retry=1 clears the state (plain file)" || echo "FAIL gpu_retry"
	echo "" >"$CMD"; sp11_gpu_hook_arm
	[ "$(bs get sp11_gpu_state)" = testing ] && echo "PASS GPU hook: armed before step 1 (testing)" || echo "FAIL arm"
	cat >"$T/boot-state-fail" <<'EOF'
#!/usr/bin/env bash
exit 5
EOF
	chmod +x "$T/boot-state-fail"
	SP11_ESPENV=$T/boot-state-fail
	if (sp11_gpu_hook_arm); then echo "FAIL GPU hook: arm failure was accepted"; else
		grep -q 'GPU test: ABORTED before GPU power-up' "$OUT/gpu-test-result.txt" && echo "PASS GPU hook: refuses to start GPU test without a persisted boot marker" || echo "FAIL GPU arm failure has no abort result"
	fi
	SP11_ESPENV=$BSX
	: >"$STATE"; sp11_gpu_hook_ok
	[ "$(bs get sp11_gpu_state)" = testing ] && echo "PASS GPU hook: no ok without both step ends" || echo "FAIL ok without ends"
	printf 'T=1 UP=1 BOOT=bootB EVENT=STEP1_END\nT=2 UP=2 BOOT=bootB EVENT=STEP2_END\n' >"$STATE"; sp11_gpu_hook_ok
	[ "$(bs get sp11_gpu_state)" = ok ] && echo "PASS GPU hook: ok after both ends" || echo "FAIL ok after ends"
	: >"$OUT/gpu-test-result.txt"; bs set sp11_gpu_state=testing; echo "sp11.entry=debug sp11.gpu_dtb=skip" >"$CMD"
	sp11_gpu_hook_skip && echo "PASS GPU hook: skip with sp11.gpu_dtb=skip" || echo "FAIL skip"
	[ "$(bs get sp11_gpu_state)" = failed ] && echo "PASS GPU hook: testing becomes failed in Linux" || echo "FAIL testing not settled"
) 2>&1 | tee "$T/gpu.out"
fails=$((fails + $(grep -c '^FAIL' "$T/gpu.out")))
bash "$L/sp11/gpu-retry" >/dev/null 2>&1; : 
[ "$fails" = 0 ] && exit 0 || exit 1
