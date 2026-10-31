#!/usr/bin/env python3
"""Verify the rendered M13 GRUB menu: entry order, DTB per entry, diagnostic arguments, S1/GPU placement.

Usage: check-m8-menu.py grub.cfg   (the file name is historic; the policy is the M13 menu of image/README.md)
"""
import re
import shlex
import sys

USB = "pmic_glink_altmode.dyndbg=+p ps883x.dyndbg=+p phy_qcom_qmp_combo.dyndbg=+p ucsi_glink.dyndbg=+p typec_ucsi.dyndbg=+p dwc3.dyndbg=+p dwc3_qcom.dyndbg=+p".split()
PDR = "qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p".split()
# dsp-subsystems R-K4/R-I5 (evidence 2026-10-30-m12-cdsp.md): system names that exist in 7.3
TRACE = ["trace_event=:mod:qcom_glink,:mod:smp2p,:mod:qcom_aoss,rpmh:rpmh_send_msg,power:power_domain_target", "trace_buf_size=16M"]
OLD_TRACE = ["trace_event=:mod:qcom_glink", "trace_buf_size=8M"]
BASE = ["clk_ignore_unused", "pd_ignore_unused", "rootdelay=10", "modprobe.blacklist=qcom_battmgr", "rd.driver.blacklist=qcom_battmgr"]
DEFAULT = set(BASE + USB + PDR + TRACE)

# ident: (title, DTB variant or None, set of special arguments)
MENU = {
    "debug": ("SP11 debug", "m13", DEFAULT),
    "nosnd": ("SP11 debug, no sound", "m13-nosnd", DEFAULT),
    "notouch": ("SP11 debug, touch off", "m13-notouch", DEFAULT),
    "cdsp-keep": ("SP11 debug, CDSP keep proxy votes", "m13", DEFAULT | {"qcom_q6v5_pas.keep_proxy_pds=1"}),
    "ssam-quiet": ("SP11 debug, SAM shutdown quiet", "m13", DEFAULT | {"surface_aggregator.shutdown_mode=quiet"}),
    "ssam-clean": ("SP11 debug, SAM shutdown clean", "m13", DEFAULT | {"surface_aggregator.shutdown_mode=clean"}),
    "ssam-silent": ("SP11 debug, SAM shutdown silent", "m13", DEFAULT | {"surface_aggregator.shutdown_mode=silent"}),
    "spk": ("SP11 debug, speakers (gated; kernel gate still refuses playback)", "m13-spk", DEFAULT),
    "cam": ("SP11 debug, rear camera diagnostic", "m13-cam", DEFAULT),
    "usbdbg": ("SP11 debug, USB + DSP trace", "m13", set(BASE + USB + PDR + OLD_TRACE)),
    "nodsp": ("SP11 debug, no early DSP", "m13", {"clk_ignore_unused", "pd_ignore_unused", "rootdelay=10", "modprobe.blacklist=qcom_battmgr",
                                                   "rd.driver.blacklist=qcom_battmgr,qcom_q6v5_pas"}),
    "wifi-unblock": ("SP11 debug, Wi-Fi unblock probe", "m13", set(BASE) | {"sp11.wifi_unblock=1"}),
    "nomodeset": ("SP11 debug nomodeset", "m13", set(BASE) | {"nomodeset"}),
    "initramfs": ("SP11 debug, stop in initramfs", "m13", set(BASE) | {"rd.break=pre-mount"}),
    "vmtest": ("VM test (no devicetree)", None, {"console=ttyAMA0,115200"}),
    "gpu-diag": ("SP11 debug, GPU diagnostic (WARNING: may reset the machine)", "m13-gpu",
                 set(BASE) | {"printk.devkmsg=on", "log_buf_len=16M", "systemd.unit=multi-user.target", "sp11.gpu_diag=1"}),
}
# arguments that kiwi puts into boot_options on every entry; they are not "special" here
COMMON_KIWI = {"printk.devkmsg=on", "log_buf_len=16M"}
FORBIDDEN_WORDS = {"quiet", "rhgb", "splash"}
DTB_RE = "($root)/boot/dtb/qcom/x1p64100-microsoft-denali-{}.dtb"


def special_of(args, all_special, ident):
    out = set()
    for a in args:
        if a in all_special or a.startswith(("modprobe.blacklist=", "rd.driver.blacklist=", "sp11.wifi_unblock=", "trace_", "drm.debug=",
                                              "surface_aggregator.", "qcom_q6v5_pas.", "sp11.gpu_diag", "systemd.unit=")) or ".dyndbg=" in a:
            out.add(a)
    if ident != "gpu-diag":
        out -= COMMON_KIWI
    return out


def check(cfg):
    entries = re.findall(r"^menuentry '([^']*)'[^\n]*--id sp11-([a-z0-9-]+)[^\n]*\{(.*?)^}", cfg, re.M | re.S)
    assert [i for _, i, _ in entries] == list(MENU), "entry ids/order differ"
    assert re.search(r"^set default=0$", cfg, re.M), "default is not entry 0"
    all_special = set().union(*(m[2] for m in MENU.values())) | set(OLD_TRACE)
    default_args = None
    for title, ident, body in entries:
        want_title, variant, want = MENU[ident]
        assert title == want_title, f"{ident}: title differs"
        linux = re.search(r"^\s*linux \S+ (.*)$", body, re.M)
        assert linux, f"{ident}: linux command missing"
        args = shlex.split(linux[1])
        assert not FORBIDDEN_WORDS & set(args), f"{ident}: quiet/rhgb/splash argument"
        assert "debug" in args and "loglevel=8" in args and "ignore_loglevel" in args, f"{ident}: not verbose"
        assert special_of(args, all_special, ident) == want, f"{ident}: diagnostic args differ: {sorted(special_of(args, all_special, ident) ^ want)}"
        assert args.count("sp11.entry=" + ident) == 1 and sum(a.startswith("sp11.entry=") for a in args) == 1, f"{ident}: wrong entry mark"
        assert not any(a.startswith("sp11.ssam_") for a in args), f"{ident}: opt-in SAM unit argument in the menu"
        dtbs = re.findall(r"^\s*devicetree (.*)$", body, re.M)
        assert dtbs == ([] if variant is None else [DTB_RE.format(variant)]), f"{ident}: wrong DTB"
        if ident == "debug":
            default_args = [a for a in args if not a.startswith("sp11.entry=")]
        if ident in ("nosnd", "notouch", "spk", "cam"):
            assert [a for a in args if not a.startswith("sp11.entry=")] == default_args, f"{ident}: arguments differ from debug"
        if ident in ("cdsp-keep", "ssam-quiet", "ssam-clean", "ssam-silent"):
            rest = [a for a in args if not a.startswith(("sp11.entry=", "qcom_q6v5_pas.keep_proxy_pds=", "surface_aggregator.shutdown_mode="))]
            assert rest == default_args, f"{ident}: arguments differ from debug beyond its one parameter"
        assert "GPU on" not in title or ident == "gpu-diag", "D22 forbids a GPU-on entry other than gpu-diag"
    # DTB placement: speakers and GPU DTBs each only in their own entry
    for dtb_name, owner in (("m13-spk", "spk"), ("m13-gpu", "gpu-diag"), ("m13-cam", "cam")):
        users = [i for _, i, body in entries if DTB_RE.format(dtb_name) in body]
        assert users == [owner], f"{dtb_name} used by {users}, only {owner} may"
    assert entries[-1][1] == "gpu-diag" and entries[-2][1] == "vmtest", "GPU entry must be last, VM entry before it"


if __name__ == "__main__":
    try:
        check(open(sys.argv[1]).read())
    except (AssertionError, ValueError) as error:
        sys.exit(str(error))
    print("PASS: M13 menu policy")
