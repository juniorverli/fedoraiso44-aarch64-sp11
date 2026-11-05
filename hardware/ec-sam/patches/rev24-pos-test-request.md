# Rev24 request: controlled POS candidate

**Rev25 priority update:** defer this optional build until the same-image
safe reboot baseline in `../test-plan.md` §8 captures the cover outcome and
KIP state. The existing kernel already supports the initial `default`/`silent`
comparison. Final34 does not demonstrate a posture error or a reboot fix.

**Kernel owner:** for an opt-in diagnostic kernel, apply the existing
`hold/0002-platform-surface-aggregator_registry-Use-the-POS-tab.patch`
after local registry patches 0001 and 0003. Its single functional change
matches [Whinham v2 2/3](https://lists.openwall.net/linux-kernel/2026/09/18/2759).
Keep a matched KIP control and the rest of the configuration/series identical;
record source, complete series and config hashes. Request the sources owner
to pin the external upstream patch before adopting it as a shared input;
preserve upstream authorship, Fixes and attribution on a release backport.
Do not add the performance-profile hunk or change default SAM policy. The
held patch applied with zero fuzz after 0001/0003 in a temporary copy; this
does not replace a full integration build, strict checkpatch or required
independent review. Build with `CONFIG_DEBUG_INFO_BTF=y` and
`CONFIG_DEBUG_INFO_BTF_MODULES=y` under the normal kernel build lock.

**Image owner, if the POS comparison is warranted:** provide otherwise identical
safe GPU-off entries/images for KIP control and POS candidate. Defer the
separate orientation experiment to USB-C review, including DP recovery. Fix
the explicit SAM boot argument, disable rotor
variation for these entries, record actual loaded kernel/module and DT hashes,
and implement the private, count-only observations and predecessor/successor
logging in `test-plan.md` §7. Ensure the proper tablet-switch module is in
both images and capture probe failures and `SW_TABLET_MODE` state. The
same-kernel outgoing `default`/`silent` choice is a separate controlled pair;
no runtime EC-state writes, unbind/rebind or clean mode. No change to
`kernel/` or `image/` is made by this request.

POS is a candidate for the published resume issue and for diagnosing a
possible reboot-time posture error; the reported safe freeze is not proven to
be caused by posture. Keep this candidate opt-in until local evidence and
project release gates support promotion.
