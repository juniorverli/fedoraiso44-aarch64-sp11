#!/usr/bin/env python3
"""Host-stub tests of extracted kernel guard/calibration functions; no hardware."""

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
                return source[start:pos + 1]
    raise ValueError(f"unclosed function: {signature}")


STUBS = r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int16_t s16;
typedef uint16_t __le16;
typedef uint32_t __le32;
#define __packed __attribute__((packed))
#define SP11_CAL_ALL_MASK 3
#define SP11_CAL_CH 2
#define SP11CAL_MAGIC "SP11CA01"
#define SP11CL_MAGIC "SP11CL01"
#define SP11CAL_FLAG_NOMINAL 1
#define SP11CL_FLAG_CPS 1
#define SP11_R0_MIN_PERCENT 80
#define SP11_R0_MAX_PERCENT 125
#define SP11_T0_MIN_Q6 (-10 * 64)
#define SP11_T0_MAX_Q6 (60 * 64)
#define PARAM_ID_SP_TH_VI_R0T0_CFG 0x080011f5
#define SZ_4K 4096
#define ALIGN(x, n) (((x) + (n) - 1) & ~((n) - 1))
#define check_mul_overflow(a, b, p) __builtin_mul_overflow((size_t)(a), (size_t)(b), (p))
#define le32_to_cpu(x) (x)
#define le16_to_cpu(x) (x)
#define cpu_to_le32(x) (x)
#define spin_lock_irqsave(lock, flags) do { (void)(lock); (flags) = 0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(lock); (void)(flags); } while (0)
#define EXPORT_SYMBOL_GPL(x)
#define dev_err(dev, ...) ((void)(dev))
#define dev_warn(dev, ...) ((void)(dev))
#define dev_info(dev, ...) ((void)(dev))
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
} guard;
static bool sp11_guard_degraded_fault(void);
static const char *sp11_guard_reason(void);
static int mute_calls;
static void sp11_guard_mute_if_refused(bool was_allowed)
{ if (was_allowed && sp11_guard_reason()) mute_calls++; }
struct device { int unused; };
struct firmware { const u8 *data; size_t size; };
struct sp11cal_ch { __le32 r0_q24; __le16 t0_q6, reserved; } __packed;
struct sp11cal_hdr { char magic[8]; __le32 flags, n_ch; struct sp11cal_ch ch[2]; __le32 crc; } __packed;
struct sp11cl_hdr { char magic[8]; __le32 n_links, n_cal, flags, nominal_re_q24[2], payload_len, payload_crc; } __packed;
struct sp11cl_link { __le32 a[5]; } __packed;
struct sp11cl_cal_rec { __le32 instance, param, size; u8 data[]; } __packed;
struct sp11cl { char cal_name[96]; u32 nominal_re_q24[2], payload_len, n_links, n_cal, flags; };
struct audioreach_module { u32 instance_id; };
struct q6apm_graph { const void *ar_graph; struct device *dev; };
static struct firmware firmware;
static bool missing;
static int send_result, sends;
static int firmware_request_nowarn(const struct firmware **fw, const char *name, void *dev)
{ (void)name; (void)dev; if (missing) return -ENOENT; *fw = &firmware; return 0; }
static void release_firmware(const struct firmware *fw) { (void)fw; }
static u32 crc32_le(u32 crc, const void *data, size_t n)
{
    const u8 *p = data;
    while (n--) { crc ^= *p++; for (int j = 0; j < 8; j++) crc = (crc >> 1) ^ (0xedb88320u & -(crc & 1)); }
    return crc;
}
static int sp11_send_param(struct q6apm_graph *g, u32 iid, u32 pid, const void *p, size_t n)
{ (void)g; (void)iid; (void)p; if (pid != PARAM_ID_SP_TH_VI_R0T0_CFG || n != 20) return -EINVAL; sends++; return send_result; }
'''

SCENARIO = r'''
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)
static void checksum(struct sp11cal_hdr *h) { h->crc = crc32_le(~0u, h, offsetof(struct sp11cal_hdr, crc)); }
static void reset_fixture(struct sp11cal_hdr *h)
{
    memset(h, 0, sizeof(*h)); memcpy(h->magic, SP11CAL_MAGIC, 8); h->n_ch = 2;
    for (int i = 0; i < 2; i++) { h->ch[i].r0_q24 = 4u << 24; h->ch[i].t0_q6 = 25 * 64; }
    checksum(h); firmware.data = (const void *)h; firmware.size = sizeof(*h); missing = false; send_result = 0; sends = 0;
}
int main(void)
{
    int ar1, ar2;
    struct device dev = {0};
    struct q6apm_graph a = { .ar_graph = &ar1, .dev = &dev }, b = { .ar_graph = &ar2, .dev = &dev };
    struct audioreach_module vi = { .instance_id = 0x4024 };
    struct sp11cl cl = { .nominal_re_q24 = {4u << 24, 4u << 24} };
    struct sp11cal_hdr h;
    struct sp11cl_hdr clh = { .magic = SP11CL_MAGIC, .payload_crc = ~0u };
    CHECK(sizeof(h) == 36 && sizeof(clh) == 36);
    CHECK(sp11cl_validate(&dev, (const void *)&clh, sizeof(clh), &cl));
    clh.flags = 2;
    CHECK(!sp11cl_validate(&dev, (const void *)&clh, sizeof(clh), &cl));
    puts("PASS: unknown supplement flags are rejected");
    cl.nominal_re_q24[0] = cl.nominal_re_q24[1] = 4u << 24;
    guard.mode = SP11_MODE_CLOSED_LOOP; guard.caps_ready = guard.loaded = true;
    reset_fixture(&h); CHECK(!sp11_apply_r0t0(&a, &vi, &cl)); CHECK(sends == 1 && guard.cal_mask == 3);
    sp11_guard_vi_closed(&ar1); CHECK(!guard.cal_mask);
    missing = true; CHECK(!sp11_apply_r0t0(&b, &vi, &cl));
    sp11_guard_stream(SP11_STREAM_VI, true, &ar2); sp11_guard_sp_enabled(true); sp11_guard_graph(true, false);
    CHECK(sp11_guard_reason()); sp11_guard_stream(SP11_STREAM_VI, false, &ar2);
    puts("PASS: unstarted VI close and later missing calibration cannot retain acceptance");
    reset_fixture(&h); h.flags = 2; checksum(&h);
    CHECK(sp11_apply_r0t0(&a, &vi, &cl) == -EINVAL && sends == 0 && !guard.cal_mask);
    reset_fixture(&h); h.ch[1].reserved = 1; checksum(&h);
    CHECK(sp11_apply_r0t0(&a, &vi, &cl) == -EINVAL && sends == 0 && !guard.cal_mask);
    puts("PASS: unknown calibration flags and reserved data never reach the DSP");
    reset_fixture(&h); h.crc ^= 1;
    CHECK(sp11_apply_r0t0(&a, &vi, &cl) == -EINVAL && sends == 0 && !guard.cal_mask);
    reset_fixture(&h); h.ch[0].r0_q24 = 1; checksum(&h);
    CHECK(sp11_apply_r0t0(&a, &vi, &cl) == -ERANGE && sends == 0 && !guard.cal_mask);
    reset_fixture(&h); send_result = -EIO;
    CHECK(sp11_apply_r0t0(&a, &vi, &cl) == -EIO && sends == 1 && !guard.cal_mask);
    puts("PASS: invalid CRC, out-of-range calibration and DSP failure do not mark calibration");
    reset_fixture(&h); h.flags = 1; checksum(&h);
    CHECK(!sp11_apply_r0t0(&a, &vi, &cl)); sp11_guard_stream(SP11_STREAM_VI, true, &ar1);
    CHECK(sp11_guard_reason()); allow_nominal = true; CHECK(!sp11_guard_reason());
    guard.diagnostics_degraded = true; CHECK(sp11_guard_reason()); guard.diagnostics_degraded = false;
    sp11_guard_calibration_reset(); CHECK(guard.cal_mask == 0 && mute_calls > 0);
    sp11_guard_stream(SP11_STREAM_VI, false, &ar1);
    puts("PASS: nominal and degraded policy gates remain active; invalidation requests mute");
    reset_fixture(&h); CHECK(!sp11_apply_r0t0(&a, &vi, &cl));
    sp11_guard_stream(SP11_STREAM_VI, true, &ar1); CHECK(!sp11_guard_reason());
    sp11_guard_stream(SP11_STREAM_VI, true, &ar2); CHECK(guard.vi_ambiguous && sp11_guard_reason());
    sp11_guard_stream(SP11_STREAM_VI, false, &ar2); CHECK(sp11_guard_reason());
    sp11_guard_stream(SP11_STREAM_VI, false, &ar1); CHECK(!guard.vi_ambiguous && !guard.cal_mask);
    puts("PASS: distinct concurrent VI identities remain refused until all stop");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tree", type=Path, required=True)
    args = parser.parse_args()
    sound = args.kernel_tree / "sound/soc/qcom"
    guard = (sound / "sp11-guard.c").read_text()
    loader = (sound / "qdsp6/audioreach-sp11.c").read_text()
    selected = [function(guard, signature) for signature in (
        "static const char *sp11_guard_open_reason(void)",
        "static bool sp11_guard_cal_matches_vi(void)",
        "static const char *sp11_guard_reason(void)",
        "static bool sp11_guard_degraded_fault(void)\n{",
        "void sp11_guard_graph(bool up, bool cps_required)",
        "static void sp11_guard_calibration_reset_locked(void)",
        "void sp11_guard_stream(enum sp11_guard_stream stream, bool start, const void *graph)",
        "void sp11_guard_calibration_reset(void)",
        "void sp11_guard_vi_closed(const void *graph)",
        "u64 sp11_guard_calibration_begin(const void *graph)",
        "bool sp11_guard_calibrated(u64 generation, unsigned int ch_mask, bool nominal)",
        "void sp11_guard_sp_enabled(bool enabled)",
    )]
    selected += [function(loader, "static bool sp11cl_validate("),
                 function(loader, "static int sp11_apply_r0t0(")]
    with tempfile.TemporaryDirectory(prefix="sp11-guard-candidate-") as tmp:
        src, exe = Path(tmp) / "scenario.c", Path(tmp) / "scenario"
        src.write_text(STUBS + "\n\n".join(selected) + SCENARIO)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(src), "-o", str(exe)], check=True)
        return subprocess.run([str(exe)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
