# Coredump metadata of the current boot (safe camera WirePlumber/llvmpipe crash).
# The core itself may be absent; record the list and a bounded backtrace only.
echo "## coredumpctl list"
timeout 20 coredumpctl --no-pager list 2>&1 || true
echo
echo "## coredumpctl info (bounded)"
timeout 30 coredumpctl --no-pager info 2>&1 | head -c 524288 || true
echo
true
