# ---------------------------------------------------------------- SP11 image hooks (M15) -----
# Inserted by scripts/image-build-kiwi.sh before the main section of the gpu worker's gpu-two-step.sh; called from four one-line
# insertions (image/component-inputs/m15.json pins them). The GPU two-step runs on line 1 only (`SP11 debug`, the constant kernel argument
# sp11.gpu_diag=1; the owner unit has ConditionKernelCommandLine=sp11.gpu_diag=1 and the image drop-in orders it before the display manager).
# GRUB is static: no grubenv, no GRUB logic. The markers are plain files on the boot medium (sp11-boot-state, S4):
#   sp11_gpu_state=testing   written (and synced) BEFORE step 1, the first step that can reset the machine
#   sp11_gpu_state=ok        written when step 1 and step 2 both ended in THIS boot
#   sp11_gpu_state=failed    written by the skip hook on a boot carrying sp11.gpu_dtb=skip (an operator edit of the line; never in the menu)
# On the next boot the report hook says `GPU test: died during step N` or `survived` from the owner's markers.
# THE RESET CANNOT BE PREVENTED FROM USERSPACE: the first DRM open loads the zap shader and the GMU and can reset the machine (M5 evidence).
# The only way to a stable session is line 2 (`SP11 debug, safe (no GPU)`, DTB m15-safe, no sp11.gpu_diag). The loop guard of the
# two steps themselves is the owner's (`limit`: a step that killed the previous boot is skipped).
# Every function returns 0 so the owner's flow is never changed; the only exit is the skip of a boot that has no GPU node.
SP11_ESPENV=${SP11_BOOT_STATE:-/usr/libexec/sp11-boot-state}
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
	sp11_gpu_note "WARNING: this line (SP11 debug, m15 with the GPU) may RESET THE MACHINE at the first DRM open (zap shader and GMU load); Linux userspace cannot prevent it. If it resets, boot line 2 'SP11 debug, safe (no GPU)' for a stable session."
	last=$(grep '^boot ' "$OUT/previous-boot-report.txt" 2>/dev/null | tail -n1)
	case $last in
	*"died during step "*) res="GPU test: died during step $(echo "$last" | sed -n 's/.*died during step \([0-9]\).*/\1/p') (previous boot; the state stays failed until cleared with /usr/libexec/sp11/gpu-retry)" ;;
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
sp11_gpu_hook_skip() { # true (0) on a boot started with sp11.gpu_dtb=skip: nothing to test. On the main entry it also settles the state
	local st step
	cmdline_has sp11.gpu_dtb=skip || return 1
	if cmdline_has sp11.entry=debug; then
		st=$("$SP11_ESPENV" get sp11_gpu_state 2>/dev/null)
		if [ "$st" = testing ]; then   # the state is `testing`, left by the previous boot: the previous boot died during the test
			step=$(grep '^boot ' "$OUT/previous-boot-report.txt" 2>/dev/null | tail -n1 | sed -n 's/.*died during step \([0-9]\).*/\1/p')
			if "$SP11_ESPENV" set sp11_gpu_state=failed; then sp11_gpu_note "GPU test: died during step ${step:-unknown} (previous boot left sp11_gpu_state=testing); marked sp11_gpu_state=failed by Linux, the state stays failed until /usr/libexec/sp11/gpu-retry"
			else sp11_gpu_note "GPU test: previous boot died during step ${step:-unknown} but sp11_gpu_state=failed could not be written (boot medium state unavailable); the state stays testing"; fi
		fi
	fi
	return 0
}
sp11_gpu_hook_arm() { # before step 1
	if "$SP11_ESPENV" set sp11_gpu_state=testing; then
		sp11_gpu_note "GPU test: armed (sp11_gpu_state=testing on the boot medium); if the machine resets now, the next boot reports the step"
		return 0
	fi
	sp11_gpu_note "GPU test: ABORTED before GPU power-up because sp11_gpu_state=testing could not be persisted on the boot medium"
	return 1
}
sp11_gpu_hook_ok() { # after both steps: only when this boot's state.log shows both ends
	if grep -q "BOOT=$BOOT_ID EVENT=STEP1_END" "$STATE" 2>/dev/null && grep -q "BOOT=$BOOT_ID EVENT=STEP2_END" "$STATE" 2>/dev/null; then
		"$SP11_ESPENV" set sp11_gpu_state=ok && sp11_gpu_note "GPU test: survived (this boot, step 1 and step 2; sp11_gpu_state=ok)"
	else
		sp11_gpu_note "GPU test: not completed this boot (a step aborted, see state.log); sp11_gpu_state stays testing and the next run is skipped"
	fi
	return 0
}
