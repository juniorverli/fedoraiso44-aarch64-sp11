// SPDX-License-Identifier: GPL-2.0
/*
 * Scratch harness (never committed): compiles the REAL wsa884x.c in its own
 * translation unit and drives the speaker protection gate with it.
 *
 * The amplifier is a RAM register file behind the real regmap, the DAI is the
 * real wsa884x_dais[SPKR] entry, so snd_soc_dai_digital_mute() reaches the real
 * wsa884x_mute_stream(). soc_dai_trigger() calls exactly this function for
 * START, RESUME and PAUSE_RELEASE of a DAI with mute_unmute_on_trigger
 * (sound/soc/soc-dai.c, snd_soc_pcm_dai_trigger), so a mute call with mute = 0
 * stands for all three. The guard is the real sp11-guard.c, the closed-loop
 * data is loaded by the real audioreach-sp11.c in the same boot.
 */
#include "../../../codecs/wsa884x.c"
#include <linux/delay.h>
#include <linux/platform_device.h>

static u8 gate_regs[WSA884X_MAX_REGISTER + 1];

static int gate_reg_read(void *ctx, unsigned int reg, unsigned int *val)
{
	*val = gate_regs[reg];
	return 0;
}

static int gate_reg_write(void *ctx, unsigned int reg, unsigned int val)
{
	gate_regs[reg] = val;
	return 0;
}

static const struct regmap_bus gate_bus = {
	.reg_write = gate_reg_write,
	.reg_read = gate_reg_read,
};

static const struct regmap_config gate_cfg = {
	.reg_bits = 32,
	.val_bits = 8,
	.max_register = WSA884X_MAX_REGISTER,
	.cache_type = REGCACHE_NONE,
};

static struct wsa884x_priv gate_wsa;
static struct snd_soc_component gate_comp;
static struct snd_soc_dai gate_dai;
static struct sdw_slave gate_slave;
static struct device *gate_dev;
static int gate_mutes;

static void gate_check(bool cond, const char *what)
{
	pr_info("GATE %s: %s\n", cond ? "PASS" : "FAIL", what);
}

static bool gate_pa(void)
{
	return gate_regs[WSA884X_PA_FSM_EN] & WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK;
}

/* What x1e80100_spk_mute() does for one amplifier */
static void gate_mute_cb(void *data)
{
	gate_mutes++;
	snd_soc_dai_digital_mute(&gate_dai, 1, SNDRV_PCM_STREAM_PLAYBACK);
}

/* START, RESUME and PAUSE_RELEASE of the BE end here (soc-dai.c, mute_unmute_on_trigger) */
static void gate_unmute(void)
{
	snd_soc_dai_digital_mute(&gate_dai, 0, SNDRV_PCM_STREAM_PLAYBACK);
}

static void gate_settle(void)
{
	msleep(100);
}

/* Before the closed-loop data is loaded: a speaker stream must not even open */
void wsa_gate_pre(void)
{
	struct platform_device *pdev = platform_device_register_simple("wsa-gate", -1, NULL, 0);

	if (IS_ERR(pdev))
		return;
	gate_dev = &pdev->dev;
	gate_check(sp11_guard_check(gate_dev) == -EOPNOTSUPP,
		   "open refused while the closed-loop data is not loaded");
	gate_check(sp11_guard_unmute_check(gate_dev) == -EOPNOTSUPP,
		   "unmute refused while the closed-loop data is not loaded");
}

void wsa_gate_run(void)
{
	struct sdw_slave_intr_status status = { };
	struct regmap *rm;

	if (!gate_dev)
		return;
	rm = devm_regmap_init(gate_dev, &gate_bus, NULL, &gate_cfg);
	if (IS_ERR(rm)) {
		pr_info("GATE FAIL: regmap %ld\n", PTR_ERR(rm));
		return;
	}
	gate_wsa.dev = gate_dev;
	gate_wsa.regmap = rm;
	gate_wsa.guarded = true;
	gate_wsa.hw_init = true;
	mutex_init(&gate_wsa.sp_lock);
	dev_set_drvdata(gate_dev, &gate_wsa);
	gate_comp.dev = gate_dev;
	gate_comp.regmap = rm;
	gate_dai.dev = gate_dev;
	gate_dai.component = &gate_comp;
	gate_dai.driver = &wsa884x_dais[WSA884X_DAI_SPKR];
	gate_dai.id = WSA884X_DAI_SPKR;
	dev_set_drvdata(&gate_slave.dev, &gate_wsa);
	sp11_guard_set_mute(gate_mute_cb, NULL);

	/* F-01: the stream opens first (amplifier muted), the unmute waits for the rest */
	gate_check(sp11_guard_check(gate_dev) == 0,
		   "open allowed once the closed-loop data is loaded, graph and V/I not up yet");
	gate_unmute();
	gate_check(!gate_pa(), "unmute at stream start leaves the PA off: graph and V/I are not up");
	sp11_guard_stream(SP11_STREAM_VI, true);
	gate_unmute();
	gate_check(!gate_pa(), "PA stays off with V/I running but no graph");
	sp11_guard_graph(true, false);
	gate_unmute();
	gate_check(!gate_pa(), "PA stays off with graph and V/I up but no calibration");
	sp11_guard_calibrated(SP11_CAL_ALL_MASK, false);
	gate_unmute();
	gate_check(gate_pa(), "PA is enabled once graph, V/I and calibration are in place");

	/* F-02 (no fault): pause push mutes, pause release unmutes again while allowed */
	snd_soc_dai_digital_mute(&gate_dai, 1, SNDRV_PCM_STREAM_PLAYBACK);
	gate_check(!gate_pa(), "pause push mutes the PA");
	gate_unmute();
	gate_check(gate_pa(), "pause release unmutes while the guard allows it");

	/* F-03: the V/I stream goes away while playback runs */
	gate_mutes = 0;
	sp11_guard_stream(SP11_STREAM_VI, false);
	gate_settle();
	gate_check(gate_mutes == 1 && !gate_pa(), "V/I stream stopped: the speakers are muted");
	gate_unmute();
	gate_check(!gate_pa(), "pause release cannot unmute without the V/I stream");
	sp11_guard_stream(SP11_STREAM_VI, true);
	gate_unmute();
	gate_check(!gate_pa(), "a restarted V/I stream needs a new calibration before the unmute");
	sp11_guard_calibrated(SP11_CAL_ALL_MASK, false);
	gate_unmute();
	gate_check(gate_pa(), "V/I stream and calibration back: unmute allowed again");

	/* A quick stop and restart must not be muted by the stale mute request */
	gate_mutes = 0;
	sp11_guard_stream(SP11_STREAM_VI, false);
	sp11_guard_stream(SP11_STREAM_VI, true);
	sp11_guard_calibrated(SP11_CAL_ALL_MASK, false);
	gate_settle();
	gate_check(gate_mutes == 0 && gate_pa(), "quick V/I restart: the late mute request is dropped");

	/* A graph stop mutes, a nominal calibration is refused without the boot flag */
	sp11_guard_graph(false, false);
	gate_settle();
	gate_check(!gate_pa(), "graph stopped: the speakers are muted");
	sp11_guard_graph(true, false);
	sp11_guard_calibrated(SP11_CAL_ALL_MASK, true);
	gate_unmute();
	gate_check(!gate_pa(), "a nominal calibration is refused without sp11.allow_nominal");
	sp11_guard_calibrated(SP11_CAL_ALL_MASK, false);
	gate_unmute();
	gate_check(gate_pa(), "measured calibration: unmute allowed");

	/* F-06 prerequisite: a register resync must not bring the PA back by itself */
	gate_regs[WSA884X_PA_FSM_EN] |= WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK;
	sp11_guard_graph(false, false);
	gate_settle();
	gate_regs[WSA884X_PA_FSM_EN] |= WSA884X_PA_FSM_EN_GLOBAL_PA_EN_MASK;
	wsa884x_guard_hold(&gate_wsa);
	gate_check(!gate_pa(), "register resync with the guard refusing keeps the PA off");
	sp11_guard_graph(true, false);
	sp11_guard_calibrated(SP11_CAL_ALL_MASK, false);

	/* Other machines: the amplifier driver does not consult the guard */
	gate_wsa.guarded = false;
	sp11_guard_graph(false, false);
	gate_settle();
	snd_soc_dai_digital_mute(&gate_dai, 0, SNDRV_PCM_STREAM_PLAYBACK);
	gate_check(gate_pa(), "unguarded amplifier (not a Surface Pro 11) unmutes as upstream does");
	gate_wsa.guarded = true;
	gate_regs[WSA884X_PA_FSM_EN] = 0;
	sp11_guard_graph(true, false);
	sp11_guard_calibrated(SP11_CAL_ALL_MASK, false);
	gate_unmute();
	gate_check(gate_pa(), "back to allowed before the fault test");

	/* F-05: an amplifier interrupt with the PA OFF is not dropped */
	snd_soc_dai_digital_mute(&gate_dai, 1, SNDRV_PCM_STREAM_PLAYBACK);
	gate_wsa.pa_on = false;
	gate_regs[WSA884X_INTR_STATUS0] = 0x01;
	gate_regs[WSA884X_INTR_STATUS1] = 0;
	wsa884x_interrupt_callback(&gate_slave, &status);
	gate_settle();
	gate_check(sp11_guard_faulted(), "amplifier interrupt with the PA off latches the fault");
	gate_check(sp11_guard_check(gate_dev) == -EOPNOTSUPP, "after a fault no speaker stream opens");

	/* F-02: with the fault latched, trigger start, resume and pause release stay muted */
	gate_unmute();
	gate_check(!gate_pa(), "pause release after a fault cannot unmute");
	gate_unmute();
	gate_check(!gate_pa(), "resume or restart after a fault cannot unmute");
	sp11_guard_stream(SP11_STREAM_VI, true);
	sp11_guard_graph(true, false);
	sp11_guard_calibrated(SP11_CAL_ALL_MASK, false);
	gate_unmute();
	gate_check(!gate_pa(), "no producer call clears the latch: the unmute stays refused");
}
