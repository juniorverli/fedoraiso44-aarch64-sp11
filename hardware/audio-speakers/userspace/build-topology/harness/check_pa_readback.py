#!/usr/bin/env python3
"""Exercise the direct PA register reporter without any codec or bus."""
import argparse
import subprocess
import tempfile
from pathlib import Path


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        depth += (source[pos] == "{") - (source[pos] == "}")
        if not depth:
            return source[start:pos + 1]
    raise ValueError(signature)


STUBS = r'''
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define READ_ONCE(x) (x)
#define WSA884X_PA_FSM_EN 0x30
#define WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK 1
struct device { int ignored; }; struct regmap { int ignored; };
struct wsa884x_priv { bool guarded, hw_init; struct device *dev; struct regmap *regmap; };
static int active, reads, pm_puts, read_error; static unsigned int regvalue; static char logbuf[200];
static void dev_info(struct device *dev, const char *fmt, ...)
{ va_list args; (void)dev; va_start(args, fmt); vsnprintf(logbuf, sizeof(logbuf), fmt, args); va_end(args); }
static int pm_runtime_get_if_in_use(struct device *dev) { (void)dev; return active; }
static void pm_runtime_put(struct device *dev) { (void)dev; pm_puts++; }
static int regmap_read_bypassed(struct regmap *map, unsigned int reg, unsigned int *out)
{ (void)map; if (reg != WSA884X_PA_FSM_EN) return -1; reads++; *out = regvalue; return read_error; }
'''
SCENARIO = r'''
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL %d: %s\n", __LINE__, #x); return 1; } } while (0)
int main(void)
{
    struct device d = {0}; struct regmap m = {0}; struct wsa884x_priv w = { .guarded = true, .dev = &d, .regmap = &m };
    wsa884x_log_pa_enable(&w, "before-add");
    CHECK(!reads && strstr(logbuf, "unknown: device not attached"));
    w.hw_init = true; active = 0; wsa884x_log_pa_enable(&w, "before-add");
    CHECK(!reads && strstr(logbuf, "unknown: runtime=0"));
    active = 1; read_error = -5; wsa884x_log_pa_enable(&w, "before-add");
    CHECK(reads == 1 && pm_puts == 1 && strstr(logbuf, "read failed: -5"));
    read_error = 0; regvalue = 0; wsa884x_log_pa_enable(&w, "before-add");
    CHECK(reads == 2 && pm_puts == 2 && strstr(logbuf, "global enable=0 (register)"));
    regvalue = 1; wsa884x_log_pa_enable(&w, "before-free");
    CHECK(reads == 3 && pm_puts == 3 && strstr(logbuf, "global enable=1 (register)"));
    w.guarded = false; wsa884x_log_pa_enable(&w, "before-free"); CHECK(reads == 3);
    printf("PASS: detached, inactive and read-error cases remain unknown; active reads bypass cache\n");
    return 0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kernel-tree", type=Path, required=True)
    args = ap.parse_args()
    source = (args.kernel_tree / "sound/soc/codecs/wsa884x.c").read_text()
    helper = function(source, "static void wsa884x_log_pa_enable(")
    with tempfile.TemporaryDirectory(prefix="sp11-pa-host-") as tmp:
        src, exe = Path(tmp) / "scenario.c", Path(tmp) / "scenario"
        src.write_text(STUBS + helper + SCENARIO)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(src), "-o", str(exe)], check=True)
        return subprocess.run([str(exe)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
