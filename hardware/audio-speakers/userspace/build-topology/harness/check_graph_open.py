#!/usr/bin/env python3
"""Exercise the candidate's actual graph reference functions with host stubs."""
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
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#define GFP_KERNEL 0
#define APM_CMD_GRAPH_CLOSE 0x01001004
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((int)(intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(x) >= (uintptr_t)-4095)
#define kzalloc_obj(x) calloc(1, sizeof(x))
#define kfree(p) free(p)
#define mutex_lock(p) pthread_mutex_lock(p)
#define mutex_unlock(p) pthread_mutex_unlock(p)
#define dev_err(dev, ...) ((void)(dev))
#define dev_info(dev, ...) ((void)(dev))
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - __builtin_offsetof(type, member)))
struct kref { int refs; };
struct idr { void *item; };
struct device { int ignored; };
struct audioreach_graph_info { int ignored; };
struct q6apm { pthread_mutex_t lock, graph_lock; struct idr graph_idr, graph_info_idr; struct device *dev; };
struct audioreach_graph { struct audioreach_graph_info *info; uint32_t id; void *graph; struct kref refcount; struct q6apm *apm; };
static int open_result, open_calls, close_calls, fail_idr, fail_packet;
static void *idr_find(struct idr *idr, uint32_t id) { (void)id; return idr->item; }
static int idr_alloc(struct idr *idr, void *ptr, int a, int b, int flags)
{ (void)b; (void)flags; if (fail_idr) return -ENOMEM; idr->item = ptr; return a; }
static void *idr_remove(struct idr *idr, uint32_t id)
{ void *p = idr->item; (void)id; idr->item = NULL; return p; }
static void kref_init(struct kref *ref) { ref->refs = 1; }
static void kref_get(struct kref *ref) { ref->refs++; }
static void kref_put(struct kref *ref, void (*release)(struct kref *))
{ if (!--ref->refs) release(ref); }
static void *audioreach_alloc_graph_pkt(struct q6apm *apm, struct audioreach_graph_info *info)
{ (void)apm; (void)info; return fail_packet ? ERR_PTR(-ENOMEM) : calloc(1, 8); }
static int q6apm_send_cmd_sync(struct q6apm *apm, void *packet, int rsp)
{ (void)apm; (void)packet; (void)rsp; open_calls++; usleep(10000); return open_result; }
static int audioreach_graph_mgmt_cmd(struct audioreach_graph *graph, uint32_t opcode)
{ (void)graph; if (opcode == APM_CMD_GRAPH_CLOSE) close_calls++; return 0; }
'''

SCENARIO = r'''
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL %d: %s\n", __LINE__, #x); exit(1); } } while (0)
static void *open_thread(void *p) { return q6apm_get_audioreach_graph(p, 106); }
int main(void)
{
    struct device dev = {0}; struct audioreach_graph_info info = {0};
    struct q6apm apm = { .lock = PTHREAD_MUTEX_INITIALIZER, .graph_lock = PTHREAD_MUTEX_INITIALIZER, .dev = &dev };
    struct audioreach_graph *a, *b; pthread_t t1, t2;
    CHECK(PTR_ERR(q6apm_get_audioreach_graph(&apm, 106)) == -ENODEV);
    apm.graph_info_idr.item = &info;
    fail_packet = 1; CHECK(PTR_ERR(q6apm_get_audioreach_graph(&apm, 106)) == -ENOMEM);
    fail_packet = 0; fail_idr = 1; CHECK(PTR_ERR(q6apm_get_audioreach_graph(&apm, 106)) == -ENOMEM);
    fail_idr = 0; open_result = -ETIMEDOUT;
    CHECK(PTR_ERR(q6apm_get_audioreach_graph(&apm, 106)) == -ETIMEDOUT);
    CHECK(!apm.graph_idr.item && close_calls == 0);
    open_result = -EINVAL; CHECK(PTR_ERR(q6apm_get_audioreach_graph(&apm, 106)) == -EINVAL);
    CHECK(!apm.graph_idr.item);
    puts("PASS: missing graph, allocation failure, DSP error and timeout refuse OPEN");
    open_result = 0; open_calls = 0;
    CHECK(!pthread_create(&t1, NULL, open_thread, &apm));
    CHECK(!pthread_create(&t2, NULL, open_thread, &apm));
    CHECK(!pthread_join(t1, (void **)&a) && !pthread_join(t2, (void **)&b));
    CHECK(a == b && open_calls == 1 && a->refcount.refs == 2);
    q6apm_put_graph_ref(a); CHECK(close_calls == 0 && apm.graph_idr.item == b);
    q6apm_put_graph_ref(b); CHECK(close_calls == 1 && !apm.graph_idr.item);
    puts("PASS: concurrent opens share one acknowledged graph and final close releases it");
    return 0;
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kernel-tree", type=Path, required=True)
    args = ap.parse_args()
    source = (args.kernel_tree / "sound/soc/qcom/qdsp6/q6apm.c").read_text()
    selected = [function(source, name) for name in (
        "static struct audioreach_graph *q6apm_get_audioreach_graph(",
        "static void q6apm_put_audioreach_graph(",
        "static void q6apm_put_graph_ref(")]
    with tempfile.TemporaryDirectory(prefix="sp11-open-host-") as tmp:
        src, exe = Path(tmp) / "scenario.c", Path(tmp) / "scenario"
        src.write_text(STUBS + "\n\n".join(selected) + SCENARIO)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-pthread",
                        str(src), "-o", str(exe)], check=True)
        return subprocess.run([str(exe)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
