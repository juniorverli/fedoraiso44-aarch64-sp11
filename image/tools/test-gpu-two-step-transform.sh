#!/usr/bin/bash
set -euo pipefail

repo=$(cd "$(dirname "$0")/../.." && pwd)
owner=$repo/hardware/gpu/collector/gpu-two-step.sh
hooks=$repo/image/component-inputs/gpu-state-hooks.sh
program=$repo/image/component-inputs/gpu-two-step-patch.awk
tmp=$(mktemp)
trap 'rm -f -- "$tmp"' EXIT

awk -v hooks="$hooks" -f "$program" "$owner" >"$tmp"
bash -n "$tmp"
test "$(grep -Fc 'sp11_gpu_hook_arm || { mark "ABORT GPU test: boot-medium state was not persisted";' "$tmp")" = 1
test "$(grep -Fxc 'sp11_gpu_hook_report' "$tmp")" = 1
test "$(grep -Fc '[ "$limit" -ge 2 ] && sp11_gpu_hook_ok' "$tmp")" = 1
grep -Fqx '[ "$limit" -ge 1 ] && { sp11_gpu_hook_arm || { mark "ABORT GPU test: boot-medium state was not persisted"; pkill -P "$KMSG_PID" 2>/dev/null; kill "$KMSG_PID" 2>/dev/null; exit 0; }; }' "$tmp"
python3 - "$hooks" "$tmp" <<'PYCODE'
from pathlib import Path
import sys
hook = Path(sys.argv[1]).read_text()
transformed = Path(sys.argv[2]).read_text()
assert hook + "\n" in transformed, "hook functions were not inserted"
PYCODE
echo 'PASS GPU image awk transform emits valid shell and the fail-closed arm guard'
