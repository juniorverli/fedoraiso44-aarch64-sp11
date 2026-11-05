#!/usr/bin/env python3
"""Host-stub check that widget loader errors reach the topology core."""

import argparse
import subprocess
import tempfile
from pathlib import Path


def extract(source):
    start = source.index("static int audioreach_widget_ready(")
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if depth == 0:
            return source[start:index + 1]
    raise ValueError("unclosed widget callback")


STUBS = r'''
#include <stdio.h>
#include <errno.h>
struct snd_soc_component { void *dev; };
struct snd_soc_dapm_widget { int id; };
struct snd_soc_tplg_dapm_widget { int unused; };
enum { snd_soc_dapm_aif_in, snd_soc_dapm_aif_out, snd_soc_dapm_decoder,
       snd_soc_dapm_encoder, snd_soc_dapm_src, snd_soc_dapm_buffer,
       snd_soc_dapm_mixer, snd_soc_dapm_pga, snd_soc_dapm_dai_link,
       snd_soc_dapm_scheduler, snd_soc_dapm_out_drv };
#define dev_err(...) ((void)0)
static int result;
#define LOADER(name) static int name(struct snd_soc_component *c, int i, struct snd_soc_dapm_widget *w, struct snd_soc_tplg_dapm_widget *t) { (void)c; (void)i; (void)w; (void)t; return result; }
LOADER(audioreach_widget_load_buffer)
LOADER(audioreach_widget_load_enc_dec_cnv)
LOADER(audioreach_widget_load_mixer)
LOADER(audioreach_widget_load_pga)
'''
SCENARIO = r'''
int main(void)
{
    struct snd_soc_component c = {0};
    struct snd_soc_dapm_widget w;
    struct snd_soc_tplg_dapm_widget t = {0};
    int ids[] = { snd_soc_dapm_aif_in, snd_soc_dapm_aif_out, snd_soc_dapm_decoder,
                  snd_soc_dapm_encoder, snd_soc_dapm_src, snd_soc_dapm_buffer };
    for (unsigned int i = 0; i < sizeof(ids) / sizeof(ids[0]); i++) {
        w.id = ids[i]; result = -EINVAL;
        if (audioreach_widget_ready(&c, 0, &w, &t) != -EINVAL) return 1;
        result = 0;
        if (audioreach_widget_ready(&c, 0, &w, &t)) return 2;
    }
    puts("PASS: widget loader errors propagate; success remains success");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-tree", type=Path, required=True)
    args = parser.parse_args()
    source = (args.kernel_tree / "sound/soc/qcom/qdsp6/topology.c").read_text()
    with tempfile.TemporaryDirectory(prefix="sp11-tplg-error-") as tmp:
        src, binary = Path(tmp) / "test.c", Path(tmp) / "test"
        src.write_text(STUBS + extract(source) + SCENARIO)
        subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(src), "-o", str(binary)], check=True)
        return subprocess.run([str(binary)], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
