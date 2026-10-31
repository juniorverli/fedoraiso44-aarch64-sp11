#!/usr/bin/env python3
"""render-grub-cfg.py TEMPLATE REFERENCE_GRUB_CFG OUT

Render image/kiwi/overlay/grub-arm.cfg.iso-template (a Python string.Template, like kiwi does) with the values read back from the
grub.cfg of an existing SP11 kiwi ISO (boot path, kernel/initrd names, boot options, search line, timeout, terminal). Used by
image/tools/make-menu2-iso.sh to patch an existing ISO without a kiwi rebuild. Rendering the template that built the
reference reproduces the reference byte for byte (checked for the menu1 template and the menu1 ISO)."""
import re
import sys
from string import Template
tpl, ref, out = sys.argv[1:4]
r = open(ref).read()
m = re.search(r"^\tlinux \(\$root\)(\S+)/(\S+) (.*?) clk_ignore_unused", r, re.M)
vals = dict(bootpath=m[1], kernel_file=m[2], boot_options=m[3])
vals["initrd_file"] = re.search(r"^\tinitrd \(\$root\)\S+/(\S+)$", r, re.M)[1]
vals["search_params"] = re.search(r"^search (.*)$", r, re.M)[1]
vals["boot_timeout"] = re.search(r"^set timeout=(\S+)$", r, re.M)[1]
vals["terminal_output"] = re.search(r"^terminal_output (\S+)$", r, re.M)[1]
open(out, "w").write(Template(open(tpl).read()).substitute(vals))
