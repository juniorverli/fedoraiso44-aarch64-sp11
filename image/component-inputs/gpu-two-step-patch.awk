/^\tfor lbl in SP11LOGS ANACONDA; do$/ { print "\tfor lbl in SP11LOGS ANACONDA BOOT; do"; next }
/^# --------------------------------------------------------------- main -----$/ { while ((getline l < hooks) > 0) print l; print ""; print; next }
/^cp "\$OUT\/previous-boot-report.txt" "\$RUN\/report.txt" 2>\/dev\/null$/ { print; print "sp11_gpu_hook_report"; next }
/^start_follower$/ { print "if sp11_gpu_hook_skip; then sp11_gpu_note \"GPU test: not run on this boot (sp11.gpu_dtb=skip: the GPU test is off after a failed test; clear it with /usr/libexec/sp11/gpu-retry)\"; mark SKIP_GPU_TEST; mark DONE; flush; exit 0; fi"; print; next }
/^\[ "\$limit" -ge 1 \] && \{ step1 \|\| true; \} \|\| mark "SKIP step 1 \(died there last time\)"$/ { print "[ \"$limit\" -ge 1 ] && { sp11_gpu_hook_arm || { mark \"ABORT GPU test: boot-medium state was not persisted\"; pkill -P \"$KMSG_PID\" 2>/dev/null; kill \"$KMSG_PID\" 2>/dev/null; exit 0; }; }"; print; next }
/^mark DONE$/ { print "[ \"$limit\" -ge 2 ] && sp11_gpu_hook_ok"; print; next }
{ print }
