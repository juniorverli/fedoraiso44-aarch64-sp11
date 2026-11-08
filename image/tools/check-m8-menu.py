#!/usr/bin/env python3
"""Verify the rendered SP11 GRUB menu: flat, static, three entries.

Usage: check-m8-menu.py grub.cfg

Policy (image/README.md, "M15 menu"):
  * the file has NO function except load_video, NO load_env/save_env/grubenv, NO variable assignment except the
    standard header ones, NO submenu, NO GRUB variable inside any entry except the template's own ($root); every
    device entry has a fixed DTB (the VM entry has none);
  * entry 0 `SP11 debug` is the full delivery: m15-cl (the -CL sound model selects the closed-loop topology),
    sp11.allow_nominal=1 and msm.skip_gpu=1 (the GPU node is present, the driver is skipped);
  * entry 1 `SP11 live, install from the desktop` uses the same DTB and arguments, with the safe service set;
  * entry 2 `VM test (no devicetree)` is only used by the automated L1 and has no devicetree.
  * kernel patch 0033 refuses the D26 speaker model; both device entries use the closed-loop model for audio.
  * the command line never carries rotor, SAM, GPU DTB or firmware_class arguments.
"""
import os
import re
import shlex
import sys

RELEASE = os.environ.get("SP11_RELEASE", "44")
USB = "pmic_glink_altmode.dyndbg=+p ps883x.dyndbg=+p phy_qcom_qmp_combo.dyndbg=+p ucsi_glink.dyndbg=+p typec_ucsi.dyndbg=+p dwc3.dyndbg=+p dwc3_qcom.dyndbg=+p".split()
PDR = "qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p".split()
TRACE = ["trace_event=:mod:qcom_glink,:mod:smp2p,:mod:qcom_aoss,rpmh:rpmh_send_msg", "trace_buf_size=16M"]
BASE = ["clk_ignore_unused", "pd_ignore_unused", "rootdelay=10", "modprobe.blacklist=qcom_battmgr", "rd.driver.blacklist=qcom_battmgr"]
DEFAULT = set(BASE + USB + PDR + TRACE)
EFI_PSTORE = {"efi_pstore.pstore_disable=0", "printk.always_kmsg_dump=1"}

# ident: (title, DTB variant or None, set of special arguments); order is the menu order
ENTRIES = {
    "debug": ("SP11 debug", "m15-cl", DEFAULT | EFI_PSTORE | {"msm.skip_gpu=1", "sp11.allow_nominal=1"}),
    "install": ("SP11 live, install from the desktop (keeps Windows)", "m15-cl", DEFAULT | EFI_PSTORE | {"msm.skip_gpu=1", "sp11.allow_nominal=1"}),
    "vmtest": ("VM test (no devicetree)", None, {"console=ttyAMA0,115200"}),
}
COMMON_KIWI = {"printk.devkmsg=on", "log_buf_len=16M", "console=tty0"}   # kiwi boot options (liveinstall.xml)
FORBIDDEN_WORDS = {"quiet", "rhgb", "splash"}
SPECIAL_PREFIX = ("inst.ks=", "module_blacklist=", "modprobe.blacklist=", "rd.driver.blacklist=", "trace_", "drm.debug=",
                  "sp11.allow_nominal", "sp11.nospk", "sp11.gpu_diag", "sp11.gpu_pin", "sp11.wifi_unblock", "sp11.test=",
                  "efi_pstore.", "printk.always_kmsg_dump=", "systemd.unit=", "nomodeset", "rd.break=", "console=")
NEVER_PREFIX = ("surface_aggregator.", "qcom_q6v5_pas.", "firmware_class.", "sp11.gpu_dtb", "sp11.gpu_retry", "sp11.cdsp_",
                "sp11.ssam_", "sp11.identity", "sp11.cpufreq")
DTB_RE = "($root)/boot/dtb/qcom/x1p64100-microsoft-denali-{}.dtb"
ENTRY_RE = r"^menuentry '([^']*)'[^\n]*--id sp11-([a-z0-9-]+)[^\n]*\{\n(.*?)^\}"


def code_of(cfg):
    return "\n".join(l for l in cfg.splitlines() if not l.lstrip().startswith("#"))


def check_entry(body, ident, variant, want):
    linux = re.search(r"^\s*linux \S+ (.*)$", body, re.M)
    assert linux, f"{ident}: linux command missing"
    args = shlex.split(linux[1])
    pin_args = [a for a in args if a.startswith("sp11.gpu_pin")]
    assert pin_args == [] or (ident == "debug" and pin_args == ["sp11.gpu_pin=0"]), f"{ident}: invalid GPU pin control"
    assert not FORBIDDEN_WORDS & set(args), f"{ident}: quiet/rhgb/splash argument"
    assert "debug" in args and "loglevel=8" in args and "ignore_loglevel" in args, f"{ident}: not verbose"
    spec = {a for a in args if a in want or a.startswith(SPECIAL_PREFIX) or ".dyndbg=" in a} - COMMON_KIWI - {"sp11.gpu_pin=0"}
    assert spec == want, f"{ident}: diagnostic args differ: {sorted(spec ^ want)}"
    mark = {"install": "safe"}.get(ident, ident)   # the installer session uses the safe service set
    assert args.count("sp11.entry=" + mark) == 1 and sum(a.startswith("sp11.entry=") for a in args) == 1, f"{ident}: wrong entry mark"
    assert not any(a.startswith(NEVER_PREFIX) for a in args), f"{ident}: rotor/GPU/SAM/firmware argument on the command line (Linux side owns it)"
    assert ("sp11.allow_nominal=1" in args) == (ident in {"debug", "install"}), f"{ident}: sp11.allow_nominal must be on both device entries only"
    assert "sp11.nospk" not in args, f"{ident}: kill switch on an entry"
    dtbs = re.findall(r"^\s*devicetree (.*)$", body, re.M)
    assert dtbs == ([] if variant is None else [DTB_RE.format(variant)]), f"{ident}: wrong DTB {dtbs}"
    assert "$" not in re.sub(r"\(\$root\)", "", "\n".join(l for l in body.splitlines() if l.strip().startswith(("linux", "devicetree", "initrd")))), f"{ident}: GRUB variable in an entry"
    return args


def check_static(cfg):
    code = code_of(cfg)
    funcs = re.findall(r"^\s*function\s+(\S+)", code, re.M)
    assert funcs == ["load_video"], f"only load_video may be a function: {funcs}"
    for bad in (r"\bload_env\b", r"\bsave_env\b", r"editenv", r"\bgrubenv\b", r"\bsubmenu\b", r"\bregexp\b", r"\bsp11_", r"\bset sp11",
                r"^\s*(halt|reboot|read|configfile|while|until|for|exit|return)\b", r"^\s*if\b", r">\s*\("):
        assert not re.search(bad, code, re.M), f"menu is static; found {bad}"
    sets = re.findall(r"^\s*set (\w+)=", code, re.M)
    assert sorted(sets) == ["default", "gfxpayload", "timeout", "timeout_style"], f"unexpected variables: {sets}"
    assert "power:power_domain_target" not in code, "power_domain_target is back in a trace_event string"
    assert not re.search(r"denali-m1[34]|-gpu\.dtb|m15-gpu|sp11\.gpu_dtb", code), "old or separate GPU DTB/argument in the menu"


def check(cfg):
    assert re.search(r"^set default=0$", cfg, re.M), "default is not the debug entry (entry 0)"
    assert re.search(r"^set timeout_style=menu$", cfg, re.M), "menu not always shown"
    code = code_of(cfg)
    tops = re.findall(r"^menuentry '([^']*)'", code, re.M)
    assert tops == [v[0] for v in ENTRIES.values()], f"top-level entries/order differ: {tops}"
    entries = [(m[1], m[2], m[3]) for m in re.finditer(ENTRY_RE, code, re.M | re.S)]
    assert [e[1] for e in entries] == list(ENTRIES), f"entry ids/order differ: {[e[1] for e in entries]}"
    assert entries[-1][1] == "vmtest", "VM entry must be last"
    arglists = {}
    for title, ident, body in entries:
        want_title, variant, want = ENTRIES[ident]
        assert title == want_title, f"{ident}: title differs"
        arglists[ident] = check_entry(body, ident, variant, want)
    strip = lambda ident: [a for a in arglists[ident] if not a.startswith("sp11.entry=")]
    line1 = [a for a in strip("debug") if a != "sp11.gpu_pin=0"]
    assert strip("install") == line1, "install: arguments differ from the debug baseline"
    assert not (set(strip("vmtest")) & DEFAULT), "vmtest: diagnostic arguments on the VM entry"
    assert arglists["vmtest"].count("console=ttyAMA0,115200") == 1, "vmtest: serial console missing"
    assert all("msm.skip_gpu=1" in arglists[i] for i in ("debug", "install")), "device entries must keep msm.skip_gpu=1 (m15-cl keeps the GPU node)"
    used = {}
    for _, ident, body in entries:
        for d in re.findall(r"denali-(m[0-9a-z-]+)\.dtb", body):
            used.setdefault(d, []).append(ident)
    assert used == {"m15-cl": ["debug", "install"]}, f"DTB placement differs: {used}"
    assert not any(a.startswith("sp11.gpu_diag") for args in arglists.values() for a in args), "GPU diagnostic must be opt-in"
    check_static(cfg)


if __name__ == "__main__":
    try:
        check(open(sys.argv[1]).read())
    except (AssertionError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
    print("PASS: SP11 flat static menu policy")
