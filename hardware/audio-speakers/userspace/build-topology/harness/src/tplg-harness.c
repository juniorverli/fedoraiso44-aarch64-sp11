// SPDX-License-Identifier: GPL-2.0
/*
 * Scratch harness (never committed): loads AudioReach topology firmware with the
 * REAL sound/soc/qcom/qdsp6/topology.c and ASoC topology core, then builds the
 * APM_CMD_GRAPH_OPEN packet of every graph with the real audioreach.c.
 * Console output is parsed by tplg-harness-check.py.
 */
#include <linux/platform_device.h>
#include <linux/init.h>
#include <linux/of.h>
#include <linux/delay.h>
#include <linux/reboot.h>
#include <linux/printk.h>

/* topology.c looks for the DT child of the q6apm device; use the root node as platform */
#define of_get_compatible_child(p, c) harness_platform_node()
static struct device_node *harness_platform_node(void)
{
	return of_node_get(of_root);
}

#include "../topology.c"

struct hcase {
	const char *name;
	struct q6apm *apm;
	int tplg_ret;
};

static struct hcase *cur;
static int cidx;
static struct snd_soc_dai_link_component hcpu;
static struct device_driver hdrv = { .name = "tplg-harness" };

static int hprobe(struct snd_soc_component *c)
{
	int ret = audioreach_tplg_init(c);

	cur->tplg_ret = ret;
	pr_info("HARNESS %s: audioreach_tplg_init returned %d\n", cur->name, ret);
	return ret;
}

static const struct snd_soc_component_driver hcomp = {
	.name = "tplg-harness",
	.probe = hprobe,
	.probe_order = SND_SOC_COMP_ORDER_LAST,
};

/* The back-end DAIs that q6apm-lpass-dais provides in production (stream names only matter) */
#define HBE_PB(n) { .name = n, .playback = { .stream_name = n " Playback", .channels_min = 1, \
		.channels_max = 8, .rates = SNDRV_PCM_RATE_8000_192000, .formats = SNDRV_PCM_FMTBIT_S16_LE } }
#define HBE_CP(n) { .name = n, .capture = { .stream_name = n " Capture", .channels_min = 1, \
		.channels_max = 8, .rates = SNDRV_PCM_RATE_8000_192000, .formats = SNDRV_PCM_FMTBIT_S16_LE } }
static struct snd_soc_dai_driver hbe_dais[] = {
	HBE_PB("WSA_CODEC_DMA_RX_0"), HBE_CP("WSA_CODEC_DMA_TX_0"), HBE_PB("DISPLAY_PORT_RX_0"),
	HBE_PB("DISPLAY_PORT_RX_1"), HBE_CP("VA_CODEC_DMA_TX_0"),
};
static const struct snd_soc_component_driver hbe = { .name = "tplg-harness-be" };

static struct snd_soc_dai_link_component hplat[8];

static void dump_graphs(struct q6apm *apm, const char *name)
{
	struct audioreach_graph_info *info;
	struct audioreach_sub_graph *sg;
	struct audioreach_container *cont;
	struct audioreach_module *mod;
	int id, i;

	idr_for_each_entry(&apm->graph_info_idr, info, id) {
		struct gpr_pkt *pkt;
		u32 len;

		pr_info("HARNESS %s: GRAPH %d sub_graphs %u\n", name, id, info->num_sub_graphs);
		list_for_each_entry(sg, &info->sg_list, node) {
			pr_info("HARNESS %s: GRAPH %d SG 0x%x\n", name, id, sg->sub_graph_id);
			list_for_each_entry(cont, &sg->container_list, node) {
				pr_info("HARNESS %s: GRAPH %d CONT 0x%x modules %u\n", name, id,
					cont->container_id, cont->num_modules);
				list_for_each_entry(mod, &cont->modules_list, node) {
					pr_info("HARNESS %s: GRAPH %d MOD iid 0x%x mid 0x%08x ip %u op %u conns %u dst0 0x%x w=%s\n",
						name, id, mod->instance_id, mod->module_id,
						mod->max_ip_port, mod->max_op_port,
						mod->num_connections, mod->dst_mod_inst_id[0],
						mod->widget ? mod->widget->name : "-");
				}
			}
		}
		pkt = audioreach_alloc_graph_pkt(apm, info);
		if (IS_ERR(pkt)) {
			pr_info("HARNESS %s: GRAPH %d packet error %ld\n", name, id, PTR_ERR(pkt));
			continue;
		}
		len = pkt->hdr.pkt_size;
		pr_info("HARNESS %s: GRAPH %d PKT bytes %u control_links %u\n", name, id, len,
			audioreach_sp11_count_links(info));
		for (i = 0; i < len; i += 32)
			pr_info("HARNESS %s: PKT %d %*phN\n", name, id,
				min_t(int, 32, len - i), (u8 *)pkt + i);
		kfree(pkt);
	}
}

static void run_case(const char *name)
{
	struct snd_soc_card *card;
	struct snd_soc_dai_link *link;
	struct platform_device *pdev, *cdev, *bedev;
	struct q6apm *apm;
	struct hcase hc = { .name = name };
	int ret;

	apm = kzalloc(sizeof(*apm), GFP_KERNEL);
	card = kzalloc(sizeof(*card), GFP_KERNEL);
	link = kzalloc(sizeof(*link), GFP_KERNEL);
	if (!apm || !card || !link)
		return;
	mutex_init(&apm->lock);
	mutex_init(&apm->cmd_lock);
	INIT_LIST_HEAD(&apm->widget_list);
	idr_init(&apm->graph_idr);
	idr_init(&apm->graph_info_idr);
	idr_init(&apm->sub_graphs_idr);
	idr_init(&apm->containers_idr);
	idr_init(&apm->modules_idr);
	hc.apm = apm;
	cur = &hc;

	pdev = platform_device_register_simple(name, -1, NULL, 0);
	if (IS_ERR(pdev))
		return;
	pdev->dev.driver = &hdrv;
	pdev->dev.of_node = of_node_get(of_root);
	dev_set_drvdata(&pdev->dev, apm);
	apm->dev = &pdev->dev;

	ret = devm_snd_soc_register_component(&pdev->dev, &hcomp, NULL, 0);
	if (ret) {
		pr_info("HARNESS %s: component register %d\n", name, ret);
		return;
	}

	bedev = platform_device_register_simple("hbe", cidx, NULL, 0);
	if (IS_ERR(bedev))
		return;
	bedev->dev.driver = &hdrv;
	ret = devm_snd_soc_register_component(&bedev->dev, &hbe, hbe_dais, ARRAY_SIZE(hbe_dais));
	if (ret) {
		pr_info("HARNESS %s: BE register %d\n", name, ret);
		return;
	}
	hcpu.name = dev_name(&bedev->dev);
	hcpu.dai_name = "WSA_CODEC_DMA_RX_0";

	link->name = name;
	link->stream_name = name;
	link->cpus = &hcpu;
	link->num_cpus = 1;
	link->codecs = &snd_soc_dummy_dlc;
	link->num_codecs = 1;
	link->platforms = &hplat[cidx++];
	link->num_platforms = 1;
	link->platforms->of_node = of_root;
	cdev = platform_device_register_simple("hcard", cidx, NULL, 0);
	if (IS_ERR(cdev))
		return;
	card->dev = &cdev->dev;
	card->name = name;
	card->driver_name = "x1e80100";
	card->dai_link = link;
	card->num_links = 1;
	/* the firmware names are qcom/<driver_name>/<card name>-tplg.bin */
	ret = devm_snd_soc_register_card(&cdev->dev, card);
	pr_info("HARNESS %s: card register returned %d (tplg %d)\n", name, ret, hc.tplg_ret);
	if (!hc.tplg_ret)
		dump_graphs(apm, name);
}

static char *harness_case;
core_param(harness_case, harness_case, charp, 0444);

void wsa_gate_pre(void);
void wsa_gate_run(void);

static int __init harness_init(void)
{
	/* one case per boot: all cases share the DT root node as platform */
	if (harness_case && !strcmp(harness_case, "hgate")) {
		/* the speaker gate: real guard, real wsa884x.c, closed-loop data of case hcl */
		wsa_gate_pre();
		run_case("hcl");
		wsa_gate_run();
	} else {
		run_case(harness_case ? harness_case : "hbase");
	}
	pr_info("HARNESS DONE\n");
	msleep(500);
	kernel_power_off();
	return 0;
}
late_initcall_sync(harness_init);
