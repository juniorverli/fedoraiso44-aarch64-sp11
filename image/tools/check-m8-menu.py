#!/usr/bin/env python3
"""Verify the rendered M14 GRUB menu: structure, DTB per entry, arguments, S1 placement, GPU self-healing and CDSP rotor logic.

Usage: check-m8-menu.py grub.cfg   (the file name is historic; the policy is the M14 menu of image/README.md)

M14 structure (operator requirement: the first line is the only line used on the bench):
  line 1  `SP11 debug`            main entry, DTB chosen by GRUB (m14 or m14-safe), all test arguments inline
  line 2  submenu `Recovery and tests` with seven entries, the last one the VM test
"""
import re
import shlex
import sys

USB = "pmic_glink_altmode.dyndbg=+p ps883x.dyndbg=+p phy_qcom_qmp_combo.dyndbg=+p ucsi_glink.dyndbg=+p typec_ucsi.dyndbg=+p dwc3.dyndbg=+p dwc3_qcom.dyndbg=+p".split()
PDR = "qcom_pd_mapper.dyndbg=+p pdr_interface.dyndbg=+p".split()
# dsp-subsystems R-I5, M14 addendum (b): power:power_domain_target removed (the kernel rejected it in M13 again)
TRACE = ["trace_event=:mod:qcom_glink,:mod:smp2p,:mod:qcom_aoss,rpmh:rpmh_send_msg", "trace_buf_size=16M"]
BASE = ["clk_ignore_unused", "pd_ignore_unused", "rootdelay=10", "modprobe.blacklist=qcom_battmgr", "rd.driver.blacklist=qcom_battmgr"]
DEFAULT = set(BASE + USB + PDR + TRACE)

MAIN_TITLE = "SP11 debug"
SUBMENU_TITLE = "Recovery and tests"
MAIN_EXTRA = {"sp11.gpu_diag=1", "sp11.gpu_dtb=$sp11_gpu_dtb", "$sp11_cdsp_args"}
# ident: (title, DTB variant or None, set of special arguments)
SUB = {
    "safe": ("SP11 debug, safe (no GPU, no cameras)", "m14-safe", DEFAULT),
    "nosnd": ("SP11 debug, no sound", "m14-nosnd", DEFAULT),
    "notouch": ("SP11 debug, touch off", "m14-notouch", DEFAULT),
    "spk": ("SP11 debug, speakers (gated)", "m14-spk", DEFAULT | {"sp11.allow_nominal=1"}),
    "nomodeset": ("SP11 debug, nomodeset", "m14-safe", set(BASE) | {"nomodeset"}),
    "initramfs": ("SP11 debug, stop in initramfs", "m14-safe", set(BASE) | {"rd.break=pre-mount"}),
    "vmtest": ("VM test (no devicetree)", None, {"console=ttyAMA0,115200"}),
}
MAIN = ("debug", MAIN_TITLE, DEFAULT | {"sp11.gpu_diag=1"})
# arguments that kiwi puts into boot_options on every entry; they are not "special" here
COMMON_KIWI = {"printk.devkmsg=on", "log_buf_len=16M"}
FORBIDDEN_WORDS = {"quiet", "rhgb", "splash"}
DTB_RE = "($root)/boot/dtb/qcom/x1p64100-microsoft-denali-{}.dtb"
MAIN_DTB = DTB_RE.format("${sp11_gpu_dtb}")
ENTRY_RE = r"^[ \t]*menuentry '([^']*)'[^\n]*--id sp11-([a-z0-9-]+)[^\n]*\{(.*?)^[ \t]*\}"


def special_of(args, all_special):
    out = set()
    for a in args:
        if a in all_special or a.startswith(("modprobe.blacklist=", "rd.driver.blacklist=", "trace_", "drm.debug=", "surface_aggregator.",
                                              "qcom_q6v5_pas.", "sp11.gpu_diag", "sp11.allow_nominal", "sp11.nospk", "systemd.unit=", "firmware_class.")) or ".dyndbg=" in a:
            out.add(a)
    return out - COMMON_KIWI


def check_entry(body, ident, variant, want, all_special, expect_dtb):
    linux = re.search(r"^\s*linux \S+ (.*)$", body, re.M)
    assert linux, f"{ident}: linux command missing"
    args = shlex.split(linux[1])
    assert not FORBIDDEN_WORDS & set(args), f"{ident}: quiet/rhgb/splash argument"
    assert "debug" in args and "loglevel=8" in args and "ignore_loglevel" in args, f"{ident}: not verbose"
    assert special_of(args, all_special) == want, f"{ident}: diagnostic args differ: {sorted(special_of(args, all_special) ^ want)}"
    assert args.count("sp11.entry=" + ident) == 1 and sum(a.startswith("sp11.entry=") for a in args) == 1, f"{ident}: wrong entry mark"
    assert not any(a.startswith("sp11.ssam_") for a in args), f"{ident}: opt-in SAM unit argument in the menu"
    assert not any(a.startswith("surface_aggregator.") for a in args), f"{ident}: SAM shutdown mode on the command line (the rotor service sets it)"
    dtbs = re.findall(r"^\s*devicetree (.*)$", body, re.M)
    assert dtbs == ([] if variant is None else [expect_dtb]), f"{ident}: wrong DTB"
    return args


def check_logic(cfg):
    """The grubenv logic of the main entry, as text. The behaviour itself is run in QEMU (image/tools/qemu_boot_test.py --grub-logic)."""
    m = re.search(r"^function sp11_main_prepare \{\n(.*?)^\}", cfg, re.M | re.S)
    assert m, "sp11_main_prepare is missing"
    f = m[1]
    need = [
        "regexp --set=1:sp11_disk",                        # the boot medium's own disk, never a search by label across disks (S4)
        '[ -f ($sp11_disk,gpt2)/EFI/BOOT/grubenv ]',
        'load_env -f "$sp11_envfile"',
        'if [ "$sp11_gpu_state" = testing ]; then',
        "set sp11_gpu_state=failed",
        'if [ "$sp11_gpu_state" = failed ]; then',
        "set sp11_gpu_dtb=m14-safe",
        "set sp11_gpu_dtb=m14\n",
        "save_env -f \"$sp11_envfile\" sp11_gpu_state sp11_cdsp_variant",
        "qcom_q6v5_pas.keep_proxy_pds=0",
        "qcom_q6v5_pas.keep_proxy_pds=1",
        "firmware_class.path=/usr/lib/firmware-sp11-cdsp46",
        'sp11.cdsp_variant=$sp11_cdsp_used',
    ]
    for n in need:
        assert n in f, f"grubenv logic lacks: {n.strip()}"
    # the variants, in order: (78,0) (46.1,0) (78,1) (46.1,1), advancing 0->1->2->3->0
    variants = {}
    for k, nxt, desc in re.findall(r'sp11_cdsp_variant" = (\d) \]; then\n\t+set sp11_cdsp_used=\d\n\t+set sp11_cdsp_next=(\d)\n\t+set sp11_cdsp_desc="([^"]*)"', f):
        variants[k] = (nxt, desc)
    assert variants == {"1": ("2", "fw=c1-00046.1 keep_proxy_pds=0"), "2": ("3", "fw=c1-00078 keep_proxy_pds=1"),
                        "3": ("0", "fw=c1-00046.1 keep_proxy_pds=1")}, f"CDSP rotor table differs: {variants}"
    assert 'set sp11_cdsp_next=1\n' in f and 'set sp11_cdsp_desc="fw=c1-00078 keep_proxy_pds=0"' in f, "CDSP variant 0 is not the default"
    # no loop and no stop in the whole file: nothing halts, reboots, waits for a key or chains back to the menu
    code = "\n".join(l for l in cfg.splitlines() if not l.lstrip().startswith("#"))
    for bad in (r"^\s*(halt|reboot)\b", r"^\s*read\b", r"^\s*configfile\b", r"\bunset sp11", r"^\s*while\b", r"^\s*(until|for)\b", r"^\s*(exit|return)\b"):
        assert not re.search(bad, code, re.M), f"loop/stop risk: {bad}"
    # the main entry is the only place that uses the state; a failed state never selects the GPU DTB
    assert cfg.index("function sp11_main_prepare") < cfg.index("menuentry 'SP11 debug' "), "function after the entry"


def check(cfg):
    assert re.search(r"^set default=0$", cfg, re.M), "default is not entry 0"
    top = [m for m in re.finditer(r"^(menuentry|submenu) '([^']*)'", cfg, re.M)]
    assert [(m[1], m[2]) for m in top] == [("menuentry", MAIN_TITLE), ("submenu", SUBMENU_TITLE)], \
        f"top level must be exactly the main entry then one submenu: {[(m[1], m[2]) for m in top]}"
    sub_at = top[1].start()
    all_special = set().union(*(m[2] for m in SUB.values())) | MAIN[2]
    entries = [(m[1], m[2], m[3], m.start()) for m in re.finditer(ENTRY_RE, cfg, re.M | re.S)]
    ids = [i for _, i, _, _ in entries]
    assert ids == ["debug"] + list(SUB), f"entry ids/order differ: {ids}"
    # the main entry is before the submenu, the others inside it
    assert entries[0][3] < sub_at and all(e[3] > sub_at for e in entries[1:]), "entries are not placed as main + submenu"
    sub_body = cfg[sub_at:]
    assert len(re.findall(r"^menuentry '", cfg, re.M)) == 1, "only the main entry is a top-level menuentry"
    assert sub_body.count("menuentry '") == len(SUB), "submenu entry count"
    # main entry
    title, ident, body, _ = entries[0]
    assert title == MAIN_TITLE
    args = check_entry(body, "debug", "m14", MAIN[2], all_special, MAIN_DTB)
    for a in ("sp11.gpu_dtb=$sp11_gpu_dtb", "$sp11_cdsp_args"):
        assert a in args, f"main entry lacks {a}"
    assert "sp11_main_prepare" in body.split("linux")[0], "main entry does not prepare the GRUB environment first"
    assert not any(a.startswith("qcom_q6v5_pas.") for a in args), "keep_proxy_pds fixed on the main entry (the rotor replaces it)"
    assert "allow_nominal" not in " ".join(args), "sp11.allow_nominal on the main line (speakers must stay off there)"
    assert "power:power_domain_target" not in cfg.replace("# ", "#").split("function sp11_main_prepare")[1], "power_domain_target is back in a trace_event string"
    # the main DTB expression is the only variable one
    # submenu entries
    default_args = None
    for title, ident, body, _ in entries[1:]:
        want_title, variant, want = SUB[ident]
        assert title == want_title, f"{ident}: title differs"
        a = check_entry(body, ident, variant, want, all_special, DTB_RE.format(variant) if variant else None)
        assert not any(x.startswith(("qcom_q6v5_pas.", "firmware_class.", "sp11.gpu_", "sp11.cdsp_")) for x in a), f"{ident}: rotor or GPU argument in the submenu"
        if ident == "safe":
            default_args = [x for x in a if not x.startswith("sp11.entry=")]
        if ident in ("nosnd", "notouch"):
            assert [x for x in a if not x.startswith("sp11.entry=")] == default_args, f"{ident}: arguments differ from safe"
        if ident == "spk":   # the first-test entry: the safe arguments plus exactly sp11.allow_nominal=1, nothing else
            assert [x for x in a if not x.startswith(("sp11.entry=", "sp11.allow_nominal="))] == default_args, "spk: arguments differ from safe beyond allow_nominal"
        assert ("sp11.allow_nominal=1" in a) == (ident == "spk"), f"{ident}: sp11.allow_nominal must be on the speaker first-test entry only"
        assert "sp11.nospk" not in a, f"{ident}: the kill switch is an operator edit, not a menu argument"
        assert "GPU on" not in title
    # S1/GPU/camera placement: speakers DTB only in `spk`; the GPU+camera DTB only through the main entry's variable
    users = [i for _, i, b, _ in entries if DTB_RE.format("m14-spk") in b]
    assert users == ["spk"], f"m14-spk used by {users}, only spk may"
    assert not any(DTB_RE.format("m14") in b for _, i, b, _ in entries), "the combined m14 DTB is named literally in an entry (only the main entry's variable may select it)"
    assert entries[-1][1] == "vmtest", "VM entry must be last of the submenu"
    check_logic(cfg)


if __name__ == "__main__":
    try:
        check(open(sys.argv[1]).read())
    except (AssertionError, ValueError) as error:
        sys.exit(str(error))
    print("PASS: M14 menu policy")
