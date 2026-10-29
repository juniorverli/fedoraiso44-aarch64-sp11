#!/usr/bin/env python3
"""Verify the rendered M8 GRUB menu, including absence of cross-entry diagnostic flags."""
import re
import shlex
import sys

USB_DSP = set("pmic_glink_altmode.dyndbg=+p ps883x.dyndbg=+p phy_qcom_qmp_combo.dyndbg=+p ucsi_glink.dyndbg=+p typec_ucsi.dyndbg=+p dwc3.dyndbg=+p dwc3_qcom.dyndbg=+p qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p trace_event=:mod:qcom_glink trace_buf_size=8M".split())
EXTRAS = {"debug": set(), "usbdbg": USB_DSP, "nodsp": {"rd.driver.blacklist=qcom_battmgr,qcom_q6v5_pas"},
          "wifi-unblock": {"sp11.wifi_unblock=1"}, "nomodeset": {"nomodeset"},
          "initramfs": {"rd.break=pre-mount"}, "notouch": set(), "vmtest": {"console=ttyAMA0,115200"}}
BASE = {"clk_ignore_unused", "pd_ignore_unused", "rootdelay=10", "modprobe.blacklist=qcom_battmgr"}

def check(cfg):
    entries = re.findall(r"^menuentry '([^']*)'[^\n]*--id sp11-([a-z0-9-]+)[^\n]*\{(.*?)^}", cfg, re.M | re.S)
    assert [ident for _, ident, _ in entries] == list(EXTRAS), "entry ids/order differ"
    all_special = BASE | set().union(*EXTRAS.values())
    for title, ident, body in entries:
        linux = re.search(r"^\s*linux \S+ (.*)$", body, re.M)
        assert linux, f"{ident}: linux command missing"
        args = shlex.split(linux[1])
        special = {a for a in args if a in all_special or a.startswith(("modprobe.blacklist=", "rd.driver.blacklist=", "sp11.wifi_unblock=", "trace_", "drm.debug=")) or ".dyndbg=" in a}
        want = EXTRAS[ident] | (BASE if ident != "vmtest" else set())
        if ident not in ("vmtest", "nodsp"):
            want = want | {"rd.driver.blacklist=qcom_battmgr"}
        assert special == want, f"{ident}: diagnostic args differ: {special ^ want}"
        assert args.count("sp11.entry=" + ident) == 1, f"{ident}: wrong entry mark"
        dtbs = re.findall(r"^\s*devicetree (.*)$", body, re.M)
        variant = "m8-notouch" if ident == "notouch" else "m8"
        assert dtbs == ([] if ident == "vmtest" else [f"($root)/boot/dtb/qcom/x1p64100-microsoft-denali-{variant}.dtb"]), f"{ident}: wrong DTB"
        if ident == "debug":
            baseline = args
        if ident == "notouch":
            assert [a for a in args if not a.startswith("sp11.entry=")] == [a for a in baseline if not a.startswith("sp11.entry=")], "notouch: arguments differ from debug"
        assert "GPU on" not in title, "D22 forbids a GPU-on entry"

if __name__ == "__main__":
    try:
        check(open(sys.argv[1]).read())
    except (AssertionError, ValueError) as error:
        sys.exit(str(error))
    print("PASS: M8 menu policy")
