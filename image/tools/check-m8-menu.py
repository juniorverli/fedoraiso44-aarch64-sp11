#!/usr/bin/env python3
"""Verify the rendered M15 GRUB menu: flat, static, M13 style (file name is historic).

Usage: check-m8-menu.py grub.cfg

M15 policy (image/README.md, "M15 menu"):
  * the file has NO function except load_video, NO load_env/save_env/grubenv, NO variable assignment except the standard header ones,
    NO submenu, NO GRUB variable inside any entry except the template's own ($root); every entry has a fixed DTB (or none for the VM test);
  * line 1 `SP11 debug` = m15 (microphones + camera nodes + GPU/GMU/zap) without `sp11.gpu_diag`;
    `sp11.gpu_pin=0` is allowed there as a manual opt-out;
    line 2 `safe (no GPU)` = m15-safe (default, cameras on, no gpu_diag); no separate GPU or camera entry;
  * no per-variant SAM/CDSP entries (those are Linux-side rotors);
  * the main-entry diagnostic arguments are the M13 ones with the corrected trace string; nothing variable; the command line never carries
    rotor, SAM, GPU DTB or firmware_class arguments.
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
USBDSP = set(BASE + USB + PDR + ["trace_event=:mod:qcom_glink", "trace_buf_size=8M"])

# ident: (title, DTB variant or None, set of special arguments); order is the menu order
ENTRIES = {
    "debug": ("SP11 debug", "m15", DEFAULT | EFI_PSTORE | {"msm.skip_gpu=1"}),
    "safe": ("SP11 debug, safe (no GPU)", "m15-safe", DEFAULT),
    "nosnd": ("SP11 debug, no sound", "m15-nosnd", DEFAULT),
    "notouch": ("SP11 debug, touch off", "m15-notouch", DEFAULT),
    "spk": ("SP11 debug, speakers (closed-loop experiment; private)", "m15-spk", DEFAULT | {"sp11.allow_nominal=1"}),
    "usbdbg": ("SP11 debug, USB + DSP trace", "m15-safe", USBDSP),
    "nodsp": ("SP11 debug, no early DSP", "m15-safe", set(BASE[:3] + ["modprobe.blacklist=qcom_battmgr", "rd.driver.blacklist=qcom_battmgr,qcom_q6v5_pas"])),
    "wifi-unblock": ("SP11 debug, Wi-Fi unblock probe", "m15-safe", set(BASE) | {"sp11.wifi_unblock=1"}),
    "nomodeset": ("SP11 debug nomodeset", "m15-safe", set(BASE) | {"nomodeset"}),
    "initramfs": ("SP11 debug, stop in initramfs", "m15-safe", set(BASE) | {"rd.break=pre-mount"}),
    "spectra": ("SP11 debug, Spectra camera test", "m15-spectra", DEFAULT | {"module_blacklist=camera_x1e80100"}),
    # Rev25 debug isolation matrix: each entry is line 1 (sp11.entry=debug, m15, EFI pstore) plus one variable.
    "test-multi-user": ("SP11 debug, test multi-user (no GNOME)", "m15", DEFAULT | EFI_PSTORE | {"systemd.unit=multi-user.target", "sp11.test=test-multi-user"}),
    "test-ignore-unused": ("SP11 debug, test ignore unused (regulator)", "m15", DEFAULT | EFI_PSTORE | {"regulator_ignore_unused", "sp11.test=test-ignore-unused"}),
    "test-pinoff": ("SP11 debug, test GPU pin off", "m15", DEFAULT | EFI_PSTORE | {"sp11.test=test-pinoff"}),
    "test-acd-off": ("SP11 debug, test ACD off", "m15", DEFAULT | EFI_PSTORE | {"msm.disable_acd=1", "sp11.test=test-acd-off"}),
    "test-preempt-off": ("SP11 debug, test preemption off", "m15", DEFAULT | EFI_PSTORE | {"msm.enable_preemption=0", "sp11.test=test-preempt-off"}),
    "test-msm-off": ("SP11 debug, test msm off (display may be off; logs only)", "m15", DEFAULT | EFI_PSTORE | {"module_blacklist=msm", "sp11.test=test-msm-off"}),
    "test-softgl": ("SP11 debug, test software GL", "m15", DEFAULT | EFI_PSTORE | {"systemd.setenv=LIBGL_ALWAYS_SOFTWARE=1", "sp11.test=test-softgl"}),
    # Rev25b reset-axis isolation: one axis added to a surviving-safe base.
    "test-safe-debug": ("SP11 debug, test safe DTB + msm off + debug", "m15-safe", DEFAULT | EFI_PSTORE | {"module_blacklist=msm", "sp11.test=test-safe-debug"}),
    "test-safe-pstore": ("SP11 debug, test safe DTB + EFI pstore", "m15-safe", DEFAULT | EFI_PSTORE | {"sp11.test=test-safe-pstore"}),
    "test-m15-safe": ("SP11 debug, test m15 DTB + safe services", "m15", DEFAULT | {"sp11.test=test-m15-safe"}),
    "test-safe-camrot": ("SP11 debug, safe, rear rotation test", "m15-safe-camrot", DEFAULT | {"sp11.test=test-safe-camrot"}),
    "test-safe-cl": ("SP11 debug, safe, muted closed-loop VI", "m15-safe-cl", DEFAULT | {"sp11.nospk=1", "sp11.test=test-safe-cl"}),
    "cldebug": ("SP11 debug, closed-loop audio (needs calibration)", "m15-cl", DEFAULT | EFI_PSTORE | {"msm.skip_gpu=1", "sp11.allow_nominal=1"}),
    "install": ("SP11 live, install from the desktop (keeps Windows)", "m15-safe", DEFAULT),
    "vmtest": ("VM test (no devicetree)", None, {"console=ttyAMA0,115200"}),
}
# Test entries carry a unique sp11.test=<id>; their sp11.entry mark selects the intended service set.
TEST_IDS = ("test-multi-user", "test-ignore-unused", "test-pinoff", "test-acd-off", "test-preempt-off", "test-msm-off", "test-softgl",
            "test-safe-debug", "test-safe-pstore", "test-m15-safe", "test-safe-camrot", "test-safe-cl")
TEST_MARK = {i: "debug" for i in TEST_IDS[:7]}
TEST_MARK.update({"test-safe-debug": "debug", "test-safe-pstore": "safe", "test-m15-safe": "safe", "test-safe-camrot": "safe", "test-safe-cl": "safe", "install": "safe", "cldebug": "debug"})
M15_TEST_IDS = TEST_IDS[:7] + ("test-m15-safe",)
COMMON_KIWI = {"printk.devkmsg=on", "log_buf_len=16M", "console=tty0"}   # kiwi boot options (liveinstall.xml)
FORBIDDEN_WORDS = {"quiet", "rhgb", "splash"}
SPECIAL_PREFIX = ("inst.ks=", "module_blacklist=", "modprobe.blacklist=", "rd.driver.blacklist=", "trace_", "drm.debug=", "sp11.allow_nominal", "sp11.nospk", "sp11.gpu_diag", "sp11.gpu_pin", "sp11.wifi_unblock", "sp11.test=",
                  "efi_pstore.", "printk.always_kmsg_dump=", "systemd.unit=", "nomodeset", "rd.break=", "console=")
NEVER_PREFIX = ("surface_aggregator.", "qcom_q6v5_pas.", "firmware_class.", "sp11.gpu_dtb", "sp11.gpu_retry", "sp11.cdsp_", "sp11.ssam_", "sp11.identity", "sp11.cpufreq")
DTB_RE = "($root)/boot/dtb/qcom/x1p64100-microsoft-denali-{}.dtb"
ENTRY_RE = r"^menuentry '([^']*)'[^\n]*--id sp11-([a-z0-9-]+)[^\n]*\{\n(.*?)^\}"


def code_of(cfg):
    return "\n".join(l for l in cfg.splitlines() if not l.lstrip().startswith("#"))


def check_entry(body, ident, variant, want):
    linux = re.search(r"^\s*linux \S+ (.*)$", body, re.M)
    assert linux, f"{ident}: linux command missing"
    args = shlex.split(linux[1])
    pin_args = [a for a in args if a.startswith("sp11.gpu_pin")]
    assert pin_args == [] or (ident in {"debug", "test-pinoff", "test-msm-off", "test-safe-debug"} and pin_args == ["sp11.gpu_pin=0"]), f"{ident}: invalid GPU pin control"
    assert not FORBIDDEN_WORDS & set(args), f"{ident}: quiet/rhgb/splash argument"
    assert "debug" in args and "loglevel=8" in args and "ignore_loglevel" in args, f"{ident}: not verbose"
    spec = {a for a in args if a in want or a.startswith(SPECIAL_PREFIX) or ".dyndbg=" in a} - COMMON_KIWI - {"sp11.gpu_pin=0"}
    assert spec == want, f"{ident}: diagnostic args differ: {sorted(spec ^ want)}"
    mark = TEST_MARK.get(ident, ident)
    assert args.count("sp11.entry=" + mark) == 1 and sum(a.startswith("sp11.entry=") for a in args) == 1, f"{ident}: wrong entry mark"
    assert not any(a.startswith(NEVER_PREFIX) for a in args), f"{ident}: rotor/GPU/SAM/firmware argument on the command line (Linux side owns it)"
    assert ("sp11.allow_nominal=1" in args) == (ident in ("spk", "cldebug")), f"{ident}: sp11.allow_nominal must be on the closed-loop entries only"
    assert ("sp11.nospk=1" in args) == (ident == "test-safe-cl"), f"{ident}: sp11.nospk must be on the muted closed-loop test only"
    dtbs = re.findall(r"^\s*devicetree (.*)$", body, re.M)
    assert dtbs == ([] if variant is None else [DTB_RE.format(variant)]), f"{ident}: wrong DTB {dtbs}"
    # the only dollar signs of an entry are the template's ($root); no variable, no expansion in the arguments
    assert "$" not in re.sub(r"\(\$root\)", "", "\n".join(l for l in body.splitlines() if l.strip().startswith(("linux", "devicetree", "initrd")))), f"{ident}: GRUB variable in an entry"
    return args


def check_static(cfg):
    code = code_of(cfg)
    funcs = re.findall(r"^\s*function\s+(\S+)", code, re.M)
    assert funcs == ["load_video"], f"only load_video may be a function: {funcs}"
    for bad in (r"\bload_env\b", r"\bsave_env\b", r"editenv", r"grubenv", r"\bsubmenu\b", r"\bregexp\b", r"\bsp11_", r"\bset sp11",
                r"^\s*(halt|reboot|read|configfile|while|until|for|exit|return)\b", r"^\s*if\b", r">\s*\("):
        assert not re.search(bad, code, re.M), f"M15 menu is static; found {bad}"
    sets = re.findall(r"^\s*set (\w+)=", code, re.M)
    assert sorted(sets) == ["default", "gfxpayload", "timeout", "timeout_style"], f"unexpected variables: {sets}"
    assert "power:power_domain_target" not in code, "power_domain_target is back in a trace_event string"
    assert not re.search(r"denali-m1[34]|-gpu\.dtb|m15-gpu|sp11\.gpu_dtb", code), "old (M13/M14) or separate GPU DTB/argument in the M15 menu"


def check(cfg):
    assert re.search(r"^set default=1$", cfg, re.M), "default is not entry 1 (safe)"
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
    # Compare shared arguments after removing debug-only diagnostics and the entry mark.
    strip = lambda ident: [a for a in arglists[ident] if not a.startswith("sp11.entry=")]
    line1 = [a for a in strip("debug") if a not in EFI_PSTORE | {"sp11.gpu_pin=0", "msm.skip_gpu=1"}]
    for i in ("safe", "nosnd", "notouch"):
        assert strip(i) == line1, f"{i}: arguments differ from line 1"
    assert [a for a in strip("spk") if a != "sp11.allow_nominal=1"] == line1, "spk: arguments differ beyond allow_nominal"
    for ident in TEST_IDS:
        rest = [a for a in strip(ident) if a not in EFI_PSTORE | {"sp11.gpu_pin=0"}]
        assert set(rest) - set(line1) == set(ENTRIES[ident][2]) - DEFAULT - EFI_PSTORE, f"{ident}: not the debug baseline plus its one test variable"
        assert ("sp11.gpu_pin=0" in arglists[ident]) == (ident in {"test-pinoff", "test-msm-off", "test-safe-debug"}), f"{ident}: wrong GPU pin control"
    assert not any(a.startswith("sp11.gpu_diag") for args in arglists.values() for a in args), "GPU diagnostic must be opt-in"
    # DTB placement: speakers only in spk, cameras only in line 1 (m15); no other DTB names
    used = {}
    for _, ident, body in entries:
        for d in re.findall(r"denali-(m[0-9a-z-]+)\.dtb", body):
            used.setdefault(d, []).append(ident)
    assert used["m15-spk"] == ["spk"], f"m15-spk used by {used['m15-spk']}"
    # m15-cl keeps the GPU node like line 1; its only entry must skip the GPU driver.
    assert used["m15-cl"] == ["cldebug"], f"m15-cl used by {used['m15-cl']}"
    assert "msm.skip_gpu=1" in arglists["cldebug"], "cldebug must keep msm.skip_gpu=1 (m15-cl keeps the GPU node)"
    assert "msm.skip_gpu=1" in arglists["debug"], "line 1 must keep msm.skip_gpu=1 (m15 keeps the GPU node)"
    assert used["m15"] == ["debug", *M15_TEST_IDS], f"m15 (GPU and camera nodes) used by {used['m15']}: line 1 and its test entries only"
    assert used["m15-spectra"] == ["spectra"], f"m15-spectra used by {used['m15-spectra']}"
    assert [i for i, a in arglists.items() if "module_blacklist=camera_x1e80100" in a] == ["spectra"], "module_blacklist=camera_x1e80100 only on the Spectra entry"
    assert sorted(strip("spectra")) == sorted(line1 + ["module_blacklist=camera_x1e80100"]), "spectra: arguments differ from safe beyond module_blacklist"
    assert set(used) == {"m15", "m15-safe", "m15-nosnd", "m15-notouch", "m15-spk", "m15-spectra", "m15-safe-camrot", "m15-safe-cl", "m15-cl"}, f"DTB set differs: {sorted(used)}"
    # the speaker entry keeps the first-test notice
    spk = [b for _, i, b in entries if i == "spk"][0]
    assert "kill switch" in spk.lower() and "sleep 3" in spk, "spk: first-test notice missing"
    check_static(cfg)


if __name__ == "__main__":
    try:
        check(open(sys.argv[1]).read())
    except (AssertionError, ValueError) as error:
        sys.exit(str(error))
    print("PASS: M15 flat static menu policy")
