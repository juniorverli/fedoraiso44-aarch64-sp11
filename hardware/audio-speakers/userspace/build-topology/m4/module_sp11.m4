# SPDX-License-Identifier: BSD-3-Clause
# Surface Pro 11 closed-loop speaker protection: module widgets of the speaker
# protection (SP), the voltage/current sense (VI) and the CPS data router.
#
# The widgets carry NO calibration. The per-unit parameters (static and dynamic
# configuration, thermal limits) are Windows-derived and travel in the private
# <card>-sp11cl.bin file that sound/soc/qcom/qdsp6/audioreach-sp11.c sends after the
# graph is open. The instance ids come from the generated sp11-ids.m4.
include(`util/util.m4') dnl
define(`MODULE_ID_SPEAKER_PROTECTION', `0x070010E2') dnl
define(`MODULE_ID_SPEAKER_PROTECTION_VI', `0x070010E3') dnl
define(`MODULE_ID_CPS_DATA_ROUTER', `0x070010E4') dnl
dnl AR_MODULE_SP11(index, sgidx, container-idx, iid, maxip-ports, max-op-ports,
dnl                src-port, dst-port, dst-iid, widget-name, module-id)
define(`AR_MODULE_SP11',
`'
`SectionVendorTuples."NAME_PREFIX.$10$1_tuples" {'
`        tokens "audioreach_tokens"'
`'
`        tuples."word.u32_data" {'
`                AR_TKN_U32_MODULE_INSTANCE_ID STR($4)'
`                AR_TKN_U32_MODULE_ID STR($11)'
`                AR_TKN_U32_MODULE_MAX_IP_PORTS STR($5)'
`                AR_TKN_U32_MODULE_MAX_OP_PORTS STR($6)'
`                AR_TKN_U32_MODULE_SRC_OP_PORT_ID STR($7)'
`                AR_TKN_U32_MODULE_DST_IN_PORT_ID STR($8)'
`                AR_TKN_U32_MODULE_SRC_INSTANCE_ID STR($4)'
`                AR_TKN_U32_MODULE_DST_INSTANCE_ID STR($9)'
`        }'
`}'
`'
`SectionData."NAME_PREFIX.$10$1_data" {'
`        tuples "NAME_PREFIX.$10$1_tuples"'
`}'
`'
`SectionWidget."NAME_PREFIX.$10$1" {'
`        index STR($1)'
`        type "src"'
`        no_pm "true"'
`        subseq "10"'
`        data ['
`                "NAME_PREFIX.sub_graph$2_data"'
`                "NAME_PREFIX.container$3_data"'
`                "NAME_PREFIX.$10$1_data"'
`        ]'
`}') dnl
