# ---------------------------------------------------------------- SP11 image hooks (M14) -----
# Inserted by scripts/image-build-kiwi.sh before the main section of the gpu worker's gpu-two-step.sh; called from four one-line
# insertions (image/component-inputs/m14.json pins them). GPU self-healing with the GRUB environment block of the boot medium:
#   sp11_gpu_state=testing   written (and synced) BEFORE step 1, the first step that can reset the machine
#   sp11_gpu_state=ok        written when step 1 and step 2 both ended in THIS boot
# GRUB (grub-arm.cfg.iso-template) turns a `testing` found at boot into `failed` and boots m14-safe (GPU off) until the state is cleared.
# Every function returns 0 so the owner's flow is never changed; the only exit is the skip of a boot that has no GPU node.
SP11_ESPENV=${SP11_ESP_ENV:-/usr/libexec/sp11-esp-env}
SP11_NOTICE_BIN=${SP11_NOTICE:-/usr/libexec/sp11/operator-notice}
sp11_gpu_note() { # sp11_gpu_note TEXT: one result line for the collector (file next to the logs, /run, kmsg) and the operator
	say "$1"
	mkdir -p /run/sp11 2>/dev/null
	printf '%s\n' "$1" >>"$OUT/gpu-test-result.txt"
	printf '%s\n' "$1" >>/run/sp11/gpu-test 2>/dev/null
	"$SP11_NOTICE_BIN" add 30-gpu "$(cat /run/sp11/gpu-test 2>/dev/null)" 2>/dev/null
	return 0
}
sp11_gpu_hook_report() { # after report_previous: what the previous boot's test did, and the opt-in re-arm
	local last res
	: >/run/sp11/gpu-test 2>/dev/null
	last=$(grep '^boot ' "$OUT/previous-boot-report.txt" 2>/dev/null | tail -n1)
	case $last in
	*"died during step "*) res="GPU test: died during step $(echo "$last" | sed -n 's/.*died during step \([0-9]\).*/\1/p') (previous boot; GRUB sets sp11_gpu_state=failed and boots m14-safe until it is cleared with /usr/libexec/sp11/gpu-retry)" ;;
	*"died AFTER step "*) res="GPU test: died after step $(echo "$last" | sed -n 's/.*died AFTER step \([0-9]\).*/\1/p') finished (previous boot)" ;;
	*"ended normally"*) res="GPU test: survived (previous boot ended normally)" ;;
	*) res="GPU test: no earlier test recorded" ;;
	esac
	sp11_gpu_note "$res"
	if cmdline_has sp11.gpu_retry=1; then
		"$SP11_ESPENV" unset sp11_gpu_state && sp11_gpu_note "GPU test: sp11.gpu_retry=1 on this command line: the test is re-armed for the NEXT boot (sp11_gpu_state cleared)"
	fi
	return 0
}
sp11_gpu_hook_skip() { # true (0) on a boot where GRUB chose the GPU-off DTB: nothing to test
	cmdline_has sp11.gpu_dtb=m14-safe
}
sp11_gpu_hook_arm() { # before step 1
	if "$SP11_ESPENV" set sp11_gpu_state=testing; then sp11_gpu_note "GPU test: armed (sp11_gpu_state=testing on the boot medium); if the machine resets now, the next boot reports the step"
	else sp11_gpu_note "GPU test: WARNING cannot write sp11_gpu_state=testing (boot medium environment block unavailable); GRUB cannot self-heal this boot"; fi
	return 0
}
sp11_gpu_hook_ok() { # after both steps: only when this boot's state.log shows both ends
	if grep -q "BOOT=$BOOT_ID EVENT=STEP1_END" "$STATE" 2>/dev/null && grep -q "BOOT=$BOOT_ID EVENT=STEP2_END" "$STATE" 2>/dev/null; then
		"$SP11_ESPENV" set sp11_gpu_state=ok && sp11_gpu_note "GPU test: survived (this boot, step 1 and step 2; sp11_gpu_state=ok)"
	else
		sp11_gpu_note "GPU test: not completed this boot (a step aborted, see state.log); sp11_gpu_state stays testing and the next boot falls back to m14-safe"
	fi
	return 0
}
