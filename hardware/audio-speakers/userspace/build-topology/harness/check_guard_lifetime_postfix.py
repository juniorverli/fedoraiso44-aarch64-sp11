#!/usr/bin/env python3
"""Exercise the **candidate post-fix** calibration lifetime without a kernel build.

This compiles selected, unmodified C functions from the supplied tree with host
stubs. It requires the graph-aware API of
`kernel/patches/0011-audio-speakers-guard-calibration-lifetime.patch`; the
original `check_guard_lifetime.py` describes the pre-patch API and is expected
to fail on that tree.

It simulates a successful R0/T0 SET_CFG followed by a capture close before
GRAPH_START, then a new capture with a missing calibration file, and a started
stream control. It does not execute ALSA, the DSP, SoundWire, or device code.
"""

import argparse
import subprocess
import tempfile
from pathlib import Path


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if not depth:
                return source[start : pos + 1]
    raise ValueError(f"unclosed function: {signature}")


STUBS = r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
typedef int16_t s16;
typedef uint32_t __le32;
#define __packed __attribute__((packed))
#define SP11_CAL_ALL_MASK 3
#define SP11_CAL_CH 2
#define SP11CAL_MAGIC "SP11CA01"
#define SP11CAL_FLAG_NOMINAL 1
#define SP11_R0_MIN_PERCENT 80
#define SP11_R0_MAX_PERCENT 125
#define SP11_T0_MIN_Q6 (-10 * 64)
#define SP11_T0_MAX_Q6 (60 * 64)
#define PARAM_ID_SP_TH_VI_R0T0_CFG 0x080011f5
#define EINVAL 22
#define ERANGE 34
#define ECANCELED 125
#define MODULE_ID_SPEAKER_PROTECTION_VI 0x070010e3
#define le32_to_cpu(x) (x)
#define le16_to_cpu(x) (x)
#define cpu_to_le32(x) (x)
#define spin_lock_irqsave(lock, flags) do { (void)(lock); (flags) = 0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(lock); (void)(flags); } while (0)
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
#define kfree(p) ((void)(p))
enum sp11_guard_stream { SP11_STREAM_VI, SP11_STREAM_CPS, SP11_STREAM_MAX };
enum sp11_mode { SP11_MODE_UNKNOWN, SP11_MODE_CLOSED_LOOP, SP11_MODE_OPEN_LOOP, SP11_MODE_REFUSED };
static bool nospk, allow_nominal;
static struct {
    int lock;
    enum sp11_mode mode;
    bool caps_ready, loaded, graph_up, sp_enabled, diagnostics_degraded;
    bool cps_required, cal_nominal, fault, vi_ambiguous;
    unsigned int streams[SP11_STREAM_MAX], cal_mask;
    const void *cal_graph, *vi_graph;
    u64 cal_generation;
    int mute_work;
} guard;
static bool sp11_guard_degraded_fault(void);
static int scheduled;
static bool schedule_work(int *work) { (void)work; scheduled++; return true; }

struct firmware { const unsigned char *data; size_t size; };
struct sp11cal_ch { u32 r0_q24; int16_t t0_q6; uint16_t reserved; } __packed;
struct sp11cal_hdr { char magic[8]; u32 flags, n_ch; struct sp11cal_ch ch[2]; u32 crc; } __packed;
struct sp11cl { char cal_name[96]; u32 nominal_re_q24[2]; };
struct audioreach_module { u32 instance_id; };
struct audioreach_graph { int refcount; };
struct q6apm_graph { struct audioreach_graph *ar_graph; void *port, *dev; bool has_vi; };
static struct audioreach_module *q6apm_find_module_by_mid(struct q6apm_graph *graph, u32 mid)
{
    static struct audioreach_module module;
    return graph->has_vi && mid == MODULE_ID_SPEAKER_PROTECTION_VI ? &module : NULL;
}
struct device { void *drvdata; };
struct snd_soc_dai { struct device *dev; int id; };
struct snd_pcm_substream { int unused; };
struct q6apm_lpass_dai_data { bool is_port_started[1]; struct q6apm_graph *graph[1]; };
static int stops;
static int firmware_request_nowarn(const struct firmware **fw, const char *name, void *dev)
{ (void)fw; (void)name; (void)dev; return -2; }
static void release_firmware(const struct firmware *fw) { (void)fw; }
static u32 crc32_le(u32 crc, const void *p, size_t n) { (void)p; (void)n; return crc; }
static int sp11_send_param(struct q6apm_graph *g, u32 iid, u32 pid, const void *p, size_t n)
{ (void)g; (void)iid; (void)pid; (void)p; (void)n; return 0; }
static void *dev_get_drvdata(struct device *dev) { return dev->drvdata; }
static void q6apm_put_audioreach_graph(void *p) { (void)p; }
static void kref_put(int *p, void (*release)(void *)) { (void)p; (void)release; }
static void gpr_free_port(void *p) { (void)p; }
static int q6apm_graph_stop(struct q6apm_graph *g) { (void)g; stops++; return 0; }
'''

SCENARIO = r'''
int main(void)
{
    struct audioreach_graph ar = { 0 }, ar2 = { 0 };
    struct q6apm_graph first = { .ar_graph = &ar, .has_vi = true };
    struct q6apm_graph second = { .ar_graph = &ar2, .has_vi = true };
    struct q6apm_lpass_dai_data data = { .graph = { &first } };
    struct device dev = { .drvdata = &data };
    struct snd_soc_dai dai = { .dev = &dev, .id = 0 };
    struct audioreach_module vi = { .instance_id = 0x4024 };
    struct sp11cl cl = { .cal_name = "missing-sp11cal.bin" };
    int failed = 0;

    guard.mode = SP11_MODE_CLOSED_LOOP;
    guard.caps_ready = guard.loaded = true;
    if (!sp11_guard_calibrated(sp11_guard_calibration_begin(&ar), SP11_CAL_ALL_MASK, false))
        return 5; /* first VI SET_CFG succeeded */
    q6apm_lpass_dai_shutdown(NULL, &dai); /* prepare failed or closed before start */
    if (stops || data.graph[0]) return 2;
    if (guard.cal_mask) {
        puts("FAIL: closing an unstarted VI graph retains the calibration mask");
        failed++;
    } else {
        puts("PASS: closing an unstarted VI graph invalidates calibration");
    }
    if (sp11_apply_r0t0(&second, &vi, &cl)) return 3; /* missing firmware */
    sp11_guard_stream(SP11_STREAM_VI, true, &ar2); /* conditional on later DSP start succeeding */
    sp11_guard_sp_enabled(true); /* subsequent playback graph setup, no audio here */
    sp11_guard_graph(true, false);
    if (!sp11_guard_reason()) {
        puts("FAIL: a later VI start with missing calibration can satisfy the unmute guard");
        failed++;
    } else {
        puts("PASS: a later VI start with missing calibration stays guarded");
    }
    /* Make the positive control non-vacuous after the missing-file test. */
    if (!sp11_guard_calibrated(sp11_guard_calibration_begin(&ar2), SP11_CAL_ALL_MASK, false))
        return 6;
    if (guard.cal_mask != SP11_CAL_ALL_MASK || sp11_guard_reason()) return 7;
    sp11_guard_stream(SP11_STREAM_VI, false, &ar2);
    if (guard.cal_mask || !scheduled) return 4;
    puts("PASS: stopping a started VI stream clears the calibration mask");
    return failed ? 1 : 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tree", type=Path, required=True)
    args = parser.parse_args()
    sound = args.kernel_tree / "sound/soc/qcom"
    guard = (sound / "sp11-guard.c").read_text()
    loader = (sound / "qdsp6/audioreach-sp11.c").read_text()
    apm = (sound / "qdsp6/q6apm.c").read_text()
    dai = (sound / "qdsp6/q6apm-lpass-dais.c").read_text()
    selected = [
        function(guard, "static const char *sp11_guard_open_reason(void)"),
        function(guard, "static bool sp11_guard_cal_matches_vi(void)"),
        function(guard, "static const char *sp11_guard_reason(void)"),
        function(guard, "static bool sp11_guard_degraded_fault(void)\n{"),
        function(guard, "static void sp11_guard_mute_if_refused(bool was_allowed)"),
        function(guard, "void sp11_guard_graph(bool up, bool cps_required)"),
        function(guard, "static void sp11_guard_calibration_reset_locked(void)"),
        function(guard, "void sp11_guard_stream(enum sp11_guard_stream stream, bool start, const void *graph)"),
        function(guard, "void sp11_guard_calibration_reset(void)"),
        function(guard, "void sp11_guard_vi_closed(const void *graph)"),
        function(guard, "u64 sp11_guard_calibration_begin(const void *graph)"),
        function(guard, "bool sp11_guard_calibrated(u64 generation, unsigned int ch_mask, bool nominal)"),
        function(guard, "void sp11_guard_sp_enabled(bool enabled)"),
        function(loader, "static int sp11_apply_r0t0("),
        function(apm, "int q6apm_graph_close(struct q6apm_graph *graph)"),
        function(dai, "static void q6apm_lpass_dai_shutdown("),
    ]
    with tempfile.TemporaryDirectory(prefix="sp11-guard-host-") as tmp:
        src, exe = Path(tmp) / "scenario.c", Path(tmp) / "scenario"
        src.write_text(STUBS + "\n\n".join(selected) + SCENARIO)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Werror", str(src), "-o", str(exe)], check=True)
        return subprocess.run([str(exe)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
