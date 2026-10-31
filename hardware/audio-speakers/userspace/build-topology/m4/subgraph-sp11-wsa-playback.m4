# SPDX-License-Identifier: BSD-3-Clause
# Surface Pro 11 WSA playback back end with the speaker protection module:
#
#  ___________________________________________
# |   Sub Graph                               |
# | [MFC] -> [SP] -> [LOG] -> [WSA DEVICE EP] |
# |___________________________________________|
#
# Same chain order as the Qualcomm speaker protection topologies; the SP module
# keeps the instance id of the Windows graph so its calibration records and the
# control link of the sp11cl file address it.
include(`audioreach/audioreach.m4') dnl
include(`util/pcm.m4') dnl
include(`audioreach/subgraph.m4') dnl
include(`audioreach/container.m4') dnl
include(`audioreach/module_mfc.m4') dnl
include(`audioreach/module_log.m4') dnl
include(`audioreach/module_codec_dma.m4') dnl
include(`audioreach/module_sp11.m4') dnl
include(`util/mixer.m4') dnl

undefine(`CDC_DMA_MODULE_IID') dnl
undefine(`LOG_MODULE_IID') dnl
undefine(`MFC_MODULE_IID') dnl
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
define(`CONT_SENARIO_ID', APM_SUB_GRAPH_SID_AUDIO_PLAYBACK) dnl'
define(`CONT_CAP', `ifelse(LPASS_VER_COMPAT, 110000, APM_CONTAINER_TYPE_ID_GC, APM_CONTAINER_CAP_ID_EP)') dnl'
define(`CONT_POSITION', APM_CONT_GRAPH_POS_STREAM)dnl'
define(`DEVICE_DOMAIN_ID', APM_PROC_DOMAIN_ID_ADSP) dnl'
define(`CONT_STACK_SIZE', 8192) dnl'
define(`LOG_MODULE_IID', MOD_IID_START) dnl
define(`MFC_MODULE_IID', eval(MOD_IID_START + 1)) dnl
define(`CDC_DMA_MODULE_IID', eval(MOD_IID_START + 2)) dnl
define(`SG_INDEX', 1) dnl
define(`CONTAINER_INDEX', 1) dnl
define(`MOD_INDEX', 1) dnl
define(`DEVICE_PLAYBACK_ROUTE',
`'
`SectionGraph."NAME_PREFIX.$1 $2 Graph" {'
`        index STR($1)'
`        lines ['
`                "NAME_PREFIX.mfc$1, , $2 Audio Mixer"'
`                "NAME_PREFIX.sp$1, , NAME_PREFIX.mfc$1"'
`                "NAME_PREFIX.logger$1, , NAME_PREFIX.sp$1"'
`                "NAME_PREFIX.codec_dma_rx$1, , NAME_PREFIX.logger$1"'
`                "$2 Playback, , NAME_PREFIX.codec_dma_rx$1"'
`        ]'
`}')

AR_SUBGRAPH(SG_INDEX, DEVICE_DAI_ID, SG_IID_START, DEVICE_PERF_MODE, DEVICE_DIRECTION, CONT_SENARIO_ID)
AR_CONTAINER(CONTAINER_INDEX, CONT_IID_START, CONT_CAP, CONT_STACK_SIZE, CONT_POSITION, DEVICE_DOMAIN_ID)
AR_MODULE_MFC(MOD_INDEX, SG_INDEX, CONTAINER_INDEX, MFC_MODULE_IID, 1, 1, 1, 2, SP11_SP_IID)
AR_MODULE_SP11(MOD_INDEX, SG_INDEX, CONTAINER_INDEX, SP11_SP_IID, 1, 1, 1, 2, LOG_MODULE_IID, `sp', MODULE_ID_SPEAKER_PROTECTION)
AR_MODULE_LOG(MOD_INDEX, SG_INDEX, CONTAINER_INDEX, LOG_MODULE_IID, 1, 1, 1, 2, 0x000019ab, 1, 0, CDC_DMA_MODULE_IID)
AR_MODULE_CODEC_DMA_RX(MOD_INDEX, SG_INDEX, CONTAINER_INDEX, CDC_DMA_MODULE_IID, 1, 0, 1, 0, DEVICE_INTF_TYPE, DEVICE_INTF_INDEX, DEVICE_DATA_FORMAT, `DEVICE_NAME', NONE_IID)
DEVICE_PLAYBACK_ROUTE(MOD_INDEX, `DEVICE_NAME')
