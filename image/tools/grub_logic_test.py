#!/usr/bin/env python3
"""GRUB logic test of the M15 menu: trivial on purpose (the menu is static, there is no logic).

Usage: grub_logic_test.py [--cfg RENDERED_GRUB_CFG]     (no argument: render the template with typical kiwi values)

1. renders image/kiwi/overlay/grub-arm.cfg.iso-template like kiwi does (string.Template) with typical values;
2. grub2-script-check accepts it (local binary, else inside the container of scripts/image-container.sh);
3. image/tools/check-m8-menu.py accepts it (the policy: flat, no function but load_video, no load_env/save_env/variable/submenu, fixed DTBs);
4. mutants: a GRUB function, a load_env, a variable DTB, a submenu, a separate GPU DTB, gpu_diag on any entry, a rotor argument must each be REJECTED by the policy checker.
No QEMU, no ISO, no GRUB environment block: nothing to simulate. Exit status 0 only when everything passes.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template

REPO = Path(__file__).resolve().parents[2]
TPL = REPO / "image/kiwi/overlay/grub-arm.cfg.iso-template"
VALUES = dict(
    terminal_output="console", boot_timeout="60", search_params="--no-floppy --set=root -l SP11-Fedora-44",
    bootpath="/boot/x86", kernel_file="vmlinuz-7.3.0-65.sp11.12.fc44.aarch64", initrd_file="initrd-7.3.0-65.sp11.12.fc44.aarch64",
    boot_options="root=live:CDLABEL=SP11-Fedora-44 rd.live.image debug loglevel=8 ignore_loglevel printk.devkmsg=on log_buf_len=16M",
)
fails = 0


def ok(msg, cond, detail=""):
    global fails
    print(("PASS " if cond else "FAIL ") + msg + (f" ({detail})" if detail and not cond else ""))
    fails += 0 if cond else 1


def script_check(path):
    exe = shutil.which("grub2-script-check") or shutil.which("grub-script-check")
    cmd = [exe, str(path)] if exe else [str(REPO / "scripts/image-container.sh"), "run", "grub2-script-check", f"/out/image-work/{path.name}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr).strip()[:200]


def policy(text):
    with tempfile.NamedTemporaryFile("w", suffix=".cfg", delete=False) as f:
        f.write(text)
    r = subprocess.run([sys.executable, "-I", str(REPO / "image/tools/check-m8-menu.py"), f.name], capture_output=True, text=True)
    Path(f.name).unlink()
    return r.returncode == 0, (r.stdout + r.stderr).strip()[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg")
    a = ap.parse_args()
    cfg = Path(a.cfg).read_text() if a.cfg else Template(TPL.read_text()).substitute(VALUES)
    ok("template renders without leftover placeholders", "${" not in cfg and "$$" not in cfg)
    ok("rendered GRUB variables are only ($root)", sorted(set(re.findall(r"\$\w+|\$\{\w+\}", "\n".join(l for l in cfg.splitlines() if not l.lstrip().startswith("#"))))) == ["$root"])
    # grub2-script-check needs a file inside the repository tree for the container route: write one under out/
    work = REPO / "out/image-work"
    work.mkdir(parents=True, exist_ok=True)
    rendered = work / "grub-m15-rendered.cfg"
    rendered.write_text(cfg)
    res, detail = script_check(rendered)
    if res is None:
        print("SKIP grub2-script-check: " + detail)
    else:
        ok("grub2-script-check accepts the rendered file", res, detail)
        bad = Template(TPL.read_text()).substitute(VALUES).replace("insmod gzio", "if [ x; then")
        rendered.write_text(bad)
        res2, _ = script_check(rendered)
        ok("grub2-script-check rejects a syntax error (the check really runs)", res2 is False)
        rendered.write_text(cfg)
    p, detail = policy(cfg)
    ok("policy checker accepts the menu", p, detail)
    pin_lines = [l for l in cfg.splitlines() if l.lstrip().startswith("linux ") and "sp11.gpu_pin=" in l]
    ok("shipped menu carries no GPU pin opt-out (manual GRUB edits only)", len(pin_lines) == 0, f"{len(pin_lines)} linux lines carry sp11.gpu_pin")
    opt_out = cfg.replace("sp11.entry=debug", "sp11.gpu_pin=0 sp11.entry=debug", 1)
    ok("policy checker accepts the manual debug GPU pin opt-out", opt_out != cfg and policy(opt_out)[0])
    mutants = {
        "default moved off the debug entry": re.sub(r"(?m)^set default=0$", "set default=1", cfg, count=1),
        "a GRUB function": cfg.replace("load_video\nset gfxpayload", "function f {\n\techo x\n}\nload_video\nset gfxpayload", 1),
        "a load_env": cfg.replace("set timeout_style=menu", "load_env\nset timeout_style=menu", 1),
        "a save_env": cfg.replace("set timeout_style=menu", "save_env x\nset timeout_style=menu", 1),
        "a variable DTB": cfg.replace("denali-m15-cl.dtb", "denali-${d}.dtb", 1),
        "a submenu": cfg.rstrip() + "\nsubmenu 'x' {\n}\n",
        "a separate GPU DTB": cfg.replace("denali-m15-cl.dtb", "denali-m15-gpu.dtb", 1),
        "sp11.gpu_diag=1 on debug": cfg.replace("sp11.entry=debug", "sp11.gpu_diag=1 sp11.entry=debug", 1),
        "sp11.gpu_diag=1 on install": cfg.replace("sp11.entry=safe", "sp11.gpu_diag=1 sp11.entry=safe", 1),
        "a GRUB-chosen GPU DTB argument": cfg.replace("sp11.entry=safe", "sp11.gpu_dtb=m15 sp11.entry=safe", 1),
        "a rotor argument": cfg.replace("sp11.entry=safe", "sp11.cdsp_variant=1 sp11.entry=safe", 1),
        "firmware_class.path": cfg.replace("sp11.entry=safe", "firmware_class.path=/x sp11.entry=safe", 1),
        "m15-safe DTB on install": cfg.rsplit("denali-m15-cl.dtb", 1)[0] + "denali-m15-safe.dtb" + cfg.rsplit("denali-m15-cl.dtb", 1)[1],
        "missing allow_nominal on install": cfg[:cfg.index("menuentry 'SP11 live")] + cfg[cfg.index("menuentry 'SP11 live"):].replace("sp11.allow_nominal=1 ", "", 1),
        "missing msm.skip_gpu on install": cfg.replace("msm.skip_gpu=1 sp11.entry=safe", "sp11.entry=safe", 1),
        "wrong install entry mark": cfg.replace("sp11.entry=safe", "sp11.entry=install", 1),
        "allow_nominal on VM": cfg.replace("sp11.entry=vmtest", "sp11.allow_nominal=1 sp11.entry=vmtest", 1),
        "module_blacklist on an entry": cfg.replace("sp11.entry=safe", "module_blacklist=camera_x1e80100 sp11.entry=safe", 1),
        "missing EFI pstore enable": cfg.replace("efi_pstore.pstore_disable=0 ", "", 1),
        "missing always kmsg dump": cfg.replace("printk.always_kmsg_dump=1 ", "", 1),
        "missing EFI pstore enable on install": cfg[:cfg.index("menuentry 'SP11 live")] + cfg[cfg.index("menuentry 'SP11 live"):].replace("efi_pstore.pstore_disable=0 ", "", 1),
        "missing always kmsg dump on install": cfg[:cfg.index("menuentry 'SP11 live")] + cfg[cfg.index("menuentry 'SP11 live"):].replace("printk.always_kmsg_dump=1 ", "", 1),
        "GPU pin enabled marker on debug": cfg.replace("sp11.entry=debug", "sp11.gpu_pin=1 sp11.entry=debug", 1),
        "duplicate GPU pin opt-out on debug": cfg.replace("sp11.entry=debug", "sp11.gpu_pin=0 sp11.gpu_pin=0 sp11.entry=debug", 1),
        "GPU pin opt-out on install": cfg.replace("sp11.entry=safe", "sp11.gpu_pin=0 sp11.entry=safe", 1),
        "quiet": cfg.replace("sp11.entry=safe", "quiet sp11.entry=safe", 1),
    }
    for name, text in mutants.items():
        ok(f"policy checker rejects {name}", text != cfg and not policy(text)[0])
    print(f"GRUB logic (static menu): {'PASS' if not fails else 'FAIL'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
