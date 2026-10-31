# SPDX-License-Identifier: BSD-3-Clause
# Surface Pro 11 voltage/current sense back end (WSA_CODEC_DMA_TX_0):
#
#  ___________________________________________
# |   Sub Graph                               |
# | [WSA DEVICE EP] -> [LOG] -> [SP_VI]       |
# |___________________________________________|
#
# SP_VI consumes the data inside the DSP: nothing in this graph reaches the host.
# The module ids follow the Windows graph (Linux module ids: DATA_LOGGING is
# 0x0700101a). The back end is started by a capture front end, see the top level
# file: its only job is to make DPCM open this back end.
include(`audioreach/audioreach.m4') dnl
include(`util/pcm.m4') dnl
include(`audioreach/subgraph.m4') dnl
include(`audioreach/container.m4') dnl
include(`audioreach/module_log.m4') dnl
include(`audioreach/module_codec_dma.m4') dnl
include(`audioreach/module_sp11.m4') dnl
include(`util/mixer.m4') dnl

undefine(`SG_INDEX') dnl
undefine(`CONTAINER_INDEX') dnl
undefine(`MOD_INDEX') dnl
undefine(`DEVICE_PERF_MODE') dnl
undefine(`DEVICE_DIRECTION') dnl
undefine(`CONT_SENARIO_ID') dnl
undefine(`CONT_CAP') dnl
undefine(`CONT_POSITION') dnl
undefine(`DEVICE_DOMAIN_ID') dnl
undefine(`CONT_STACK_SIZE') dnl

define(`DEVICE_PERF_MODE', APM_SG_PERF_MODE_LOW_LATENCY) dnl'
define(`DEVICE_DIRECTION', APM_SUB_GRAPH_DIRECTION_TX) dnl'
define(`CONT_SENARIO_ID', APM_SUB_GRAPH_SID_AUDIO_RECORD) dnl'
define(`CONT_CAP', `ifelse(LPASS_VER_COMPAT, 110000, APM_CONTAINER_TYPE_ID_GC, APM_CONTAINER_CAP_ID_EP)') dnl'
define(`CONT_POSITION', APM_CONT_GRAPH_POS_GLOBAL_DEV)dnl'
define(`DEVICE_DOMAIN_ID', APM_PROC_DOMAIN_ID_ADSP) dnl'
define(`CONT_STACK_SIZE', 8192) dnl'
define(`SG_INDEX', 1) dnl
define(`CONTAINER_INDEX', 1) dnl
define(`MOD_INDEX', 1) dnl
define(`DEVICE_CAPTURE_VI_ROUTE',
`'
`SectionGraph."NAME_PREFIX.$1 $2 Graph" {'
`        index STR($1)'
`        lines ['
`                "NAME_PREFIX.codec_dma_tx$1, , $2 Capture"'
`                "NAME_PREFIX.logger$1, , NAME_PREFIX.codec_dma_tx$1"'
`                "NAME_PREFIX.sp_vi$1, , NAME_PREFIX.logger$1"'
`        ]'
`}')

AR_SUBGRAPH(SG_INDEX, DEVICE_DAI_ID, SG_IID_START, DEVICE_PERF_MODE, DEVICE_DIRECTION, CONT_SENARIO_ID)
AR_CONTAINER(CONTAINER_INDEX, CONT_IID_START, CONT_CAP, CONT_STACK_SIZE, CONT_POSITION, DEVICE_DOMAIN_ID)
AR_MODULE_CODEC_DMA_TX(MOD_INDEX, SG_INDEX, CONTAINER_INDEX, SP11_VIDMA_IID, 0, 1, 1, 2, DEVICE_INTF_TYPE, DEVICE_INTF_INDEX, DEVICE_DATA_FORMAT, `DEVICE_NAME', SP11_VILOG_IID)
AR_MODULE_LOG(MOD_INDEX, SG_INDEX, CONTAINER_INDEX, SP11_VILOG_IID, 1, 1, 1, 2, 0x00001586, 1, 0, SP11_VI_IID)
AR_MODULE_SP11(MOD_INDEX, SG_INDEX, CONTAINER_INDEX, SP11_VI_IID, 1, 0, 0, 0, NONE_IID, `sp_vi', MODULE_ID_SPEAKER_PROTECTION_VI)
DEVICE_CAPTURE_VI_ROUTE(MOD_INDEX, `DEVICE_NAME')
