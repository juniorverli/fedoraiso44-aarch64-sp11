#!/usr/bin/env bash
# Self-test of the M14 rotor, notice and GPU-hook scripts as installed in an image root (or the overlay), against fake sysfs, command lines
# and a fake boot medium. Nothing real is touched. Prints PASS/FAIL lines; exit 1 on any FAIL.
#   rotor-selftest.sh ROOT        ROOT = extracted image root (L0) or image/overlay
set -u
R=${1:?root}
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fails=0
ok() { echo "PASS $1"; }
bad() { echo "FAIL $1"; fails=$((fails + 1)); }
eq() { [ "$2" = "$3" ] && ok "$1" || bad "$1 (got '$2', want '$3')"; }
L=$R/usr/libexec
# a fake esp-env (plain file) for the rotors; the real helper is tested separately with grub2-editenv
cat >"$T/esp" <<'X'
#!/usr/bin/bash
F=${FAKE_ENV:?}; touch "$F"
case $1 in
get) sed -n "s/^$2=//p" "$F" | head -n1 ;;
set) k=${2%%=*}; grep -v "^$k=" "$F" >"$F.n"; echo "$2" >>"$F.n"; mv "$F.n" "$F" ;;
unset) grep -v "^$2=" "$F" >"$F.n"; mv "$F.n" "$F" ;;
list) cat "$F" ;;
esac
X
chmod +x "$T/esp"
export FAKE_ENV=$T/env SP11_ESP_ENV=$T/esp SP11_NOTICE_DIR=$T/notice SP11_NOTICE_FILE=$T/notice.txt SP11_NOTICE=$L/sp11/operator-notice
mkdir -p "$T/notice"
# --- SAM rotor
: >"$T/param"; echo "" >"$T/cmd"
export SP11_SAM_PARAM=$T/param SP11_SAM_ORDER=$R/usr/share/sp11/sam-mode-order SP11_SAM_STATE=$T/sam-state SP11_SAM_CMDLINE=$T/cmd
seq=
for i in 1 2 3 4 5 6; do bash "$L/sp11/sam-mode-rotor" 2>/dev/null; seq="$seq $(cat "$T/param")"; done
eq "SAM rotor order over six boots (silent, clean, quiet, default, wrap)" "$seq" " silent clean quiet default silent clean"
grep -q '^SAM shutdown mode for this boot: clean' "$T/sam-state" && ok "SAM rotor record line" || bad "SAM rotor record line"
grep -q 'SAM shutdown mode for this boot: clean' "$T/notice/10-sam.txt" && ok "SAM rotor notice text" || bad "SAM rotor notice text"
eq "SAM counter advanced to 6" "$(FAKE_ENV=$T/env "$T/esp" get sp11_sam_counter)" 6
echo "root=x surface_aggregator.shutdown_mode=quiet" >"$T/cmd"; : >"$T/param"
bash "$L/sp11/sam-mode-rotor" 2>/dev/null
eq "SAM rotor: explicit kernel-line mode wins, parameter untouched" "$(cat "$T/param")" ""
eq "SAM rotor: counter not advanced by an override" "$("$T/esp" get sp11_sam_counter)" 6
grep -q 'SAM shutdown mode for this boot: quiet' "$T/sam-state" && ok "override recorded" || bad "override recorded"
# --- CDSP report
export SP11_CDSP_STATE=$T/cdsp-state SP11_CDSP_CMDLINE=$T/cdsp-cmd SP11_CDSP_FWDIR=$T/fw46
echo "sp11.entry=debug sp11.cdsp_variant=1 qcom_q6v5_pas.keep_proxy_pds=0 firmware_class.path=$T/fw46" >"$T/cdsp-cmd"
echo "sp11_cdsp_variant=2" >"$T/env"
bash "$L/sp11/cdsp-variant" 2>/dev/null
grep -q 'CDSP variant for this boot: fw=c1-00046.1 keep_proxy_pds=0' "$T/cdsp-state" && ok "CDSP report line, alternate firmware" || bad "CDSP report line, alternate firmware"
grep -q 'WARNING' "$T/notice/20-cdsp.txt" && ok "CDSP report warns when the alternate pair is absent (public image)" || bad "CDSP warning absent"
mkdir -p "$T/fw46/qcom/x1e80100/microsoft/Denali"; echo x >"$T/fw46/qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn"; echo x >"$T/fw46/qcom/x1e80100/microsoft/Denali/cdsp_dtb.mbn"
bash "$L/sp11/cdsp-variant" 2>/dev/null
! grep -q 'WARNING' "$T/notice/20-cdsp.txt" && ok "no warning with the pair installed" || bad "warning with the pair installed"
! grep -q 'FULL POWER-OFF' "$T/notice/20-cdsp.txt" && ok "variant 1 -> next 2 (default firmware): no power-off text" || bad "power-off text for next=2"
echo "sp11_cdsp_variant=3" >"$T/env"; bash "$L/sp11/cdsp-variant" 2>/dev/null
grep -q 'FULL POWER-OFF' "$T/notice/20-cdsp.txt" && grep -q 'NOT a reboot' "$T/notice/20-cdsp.txt" && ok "next boot loads the alternate firmware: FULL POWER-OFF, NOT a reboot" || bad "power-off text missing for next=3"
echo "sp11.entry=debug sp11.cdsp_variant=2 qcom_q6v5_pas.keep_proxy_pds=1" >"$T/cdsp-cmd"; echo "sp11_cdsp_variant=3" >"$T/env"; bash "$L/sp11/cdsp-variant" 2>/dev/null
grep -q 'CDSP variant for this boot: fw=c1-00078 keep_proxy_pds=1' "$T/cdsp-state" && ok "CDSP report line, default firmware keep=1" || bad "CDSP report line default fw"
echo "sp11.entry=safe" >"$T/cdsp-cmd"; bash "$L/sp11/cdsp-variant" 2>/dev/null
grep -q 'not the rotor entry' "$T/cdsp-state" && ok "non-rotor entry reported" || bad "non-rotor entry"
# --- GPU hooks (stubs for the owner's functions)
(
	set -u
	OUT=$T/gpuout; RUN=$T/gpurun; STATE=$T/state.log; BOOT_ID=bootB; mkdir -p "$OUT"
	say() { :; }
	CMD=$T/gcmd; echo "" >"$CMD"
	cmdline_has() { tr ' ' '\n' <"$CMD" | grep -qx -- "$1"; }
	SP11_ESPENV=$T/esp
	# the hooks write /run/sp11/gpu-test: point it to the temp dir by running them in a mount-less way
	sed "s|/run/sp11/gpu-test|$T/gpu-test|g; s|mkdir -p /run/sp11 2>/dev/null|mkdir -p $T 2>/dev/null|" "$REPO/image/component-inputs/gpu-state-hooks.sh" >"$T/hooks.sh"
	. "$T/hooks.sh"
	SP11_NOTICE_BIN=$L/sp11/operator-notice
	echo "boot bootA: previous boot died during step 2 (last marker: STEP2_SUB open-call; uptime 40 s, epoch 1)" >"$OUT/previous-boot-report.txt"
	sp11_gpu_hook_report
	grep -q '^GPU test: died during step 2' "$OUT/gpu-test-result.txt" && echo "PASS GPU hook: reports 'GPU test: died during step 2'" || echo "FAIL GPU hook died report"
	: >"$OUT/gpu-test-result.txt"; echo "boot bootA: ended normally (DONE)" >"$OUT/previous-boot-report.txt"; sp11_gpu_hook_report
	grep -q '^GPU test: survived' "$OUT/gpu-test-result.txt" && echo "PASS GPU hook: reports 'GPU test: survived'" || echo "FAIL GPU hook survived report"
	echo "sp11_gpu_state=failed" >"$T/env"; echo "sp11.gpu_retry=1" >"$CMD"; sp11_gpu_hook_report
	[ -z "$("$T/esp" get sp11_gpu_state)" ] && echo "PASS GPU hook: sp11.gpu_retry=1 clears the state" || echo "FAIL gpu_retry"
	echo "" >"$CMD"; sp11_gpu_hook_arm
	[ "$("$T/esp" get sp11_gpu_state)" = testing ] && echo "PASS GPU hook: armed before step 1 (testing)" || echo "FAIL arm"
	: >"$STATE"; sp11_gpu_hook_ok
	[ "$("$T/esp" get sp11_gpu_state)" = testing ] && echo "PASS GPU hook: no ok without both step ends" || echo "FAIL ok without ends"
	printf 'T=1 UP=1 BOOT=bootB EVENT=STEP1_END\nT=2 UP=2 BOOT=bootB EVENT=STEP2_END\n' >"$STATE"; sp11_gpu_hook_ok
	[ "$("$T/esp" get sp11_gpu_state)" = ok ] && echo "PASS GPU hook: ok after both ends" || echo "FAIL ok after ends"
	echo "sp11.gpu_dtb=m14-safe" >"$CMD"; sp11_gpu_hook_skip && echo "PASS GPU hook: skip on m14-safe" || echo "FAIL skip"
	echo "sp11.gpu_dtb=m14" >"$CMD"; sp11_gpu_hook_skip && echo "FAIL skip on m14" || echo "PASS GPU hook: no skip on m14"
) 2>&1 | tee "$T/gpu.out"
fails=$((fails + $(grep -c '^FAIL' "$T/gpu.out")))
# --- the real helper on a real environment block
if command -v grub2-editenv >/dev/null 2>&1; then
	python3 -I - "$T/real" <<'PY'
import sys
h = "# GRUB Environment Block\n"
open(sys.argv[1], "wb").write((h + "#" * (1024 - len(h))).encode())
PY
	E="env SP11_ESP_ENV_FILE=$T/real bash $L/sp11-esp-env"
	$E set sp11_gpu_state=testing; eq "esp-env: set/get" "$($E get sp11_gpu_state)" testing
	$E set sp11_cdsp_variant=3; $E unset sp11_gpu_state
	eq "esp-env: unset" "$($E get sp11_gpu_state)" ""
	eq "esp-env: other values kept" "$($E get sp11_cdsp_variant)" 3
	eq "esp-env: block stays 1024 bytes" "$(stat -c %s "$T/real")" 1024
	# the refusal paths of S4 (no boot medium resolvable in this sandbox)
	bash "$L/sp11-esp-env" get x >/dev/null 2>&1; [ $? -ne 0 ] && ok "esp-env: refuses without a resolvable boot medium (S4)" || bad "esp-env did not refuse"
else
	echo "SKIP esp-env round trip (no grub2-editenv)"
fi
[ "$fails" = 0 ] && exit 0 || exit 1
