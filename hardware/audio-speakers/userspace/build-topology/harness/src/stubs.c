// SPDX-License-Identifier: GPL-2.0
/* Scratch stubs for the q6apm / gpr symbols the audioreach code references. */
#include <linux/module.h>
#include <linux/soc/qcom/apr.h>
#include "../q6apm.h"

int gpr_send_port_pkt(gpr_port_t *port, const struct gpr_pkt *pkt) { return 0; }
int gpr_send_pkt(gpr_device_t *gpr_dev, const struct gpr_pkt *pkt) { return 0; }
int q6apm_send_cmd_sync(struct q6apm *apm, const struct gpr_pkt *pkt, uint32_t rsp_opcode)
{
	return 0;
}
struct audioreach_module *q6apm_find_module_by_mid(struct q6apm_graph *graph, uint32_t mid)
{
	return NULL;
}
