# M16 CDSP endpoints (2026-11-02)

## Scope and grades

**Verified (device log):** safe boot `9e275ce6-2064-46f7-a153-b569a6f1b1a4`, kernel `7.3.0-65.sp11.15.fc44.aarch64`; paths below are under `out/device-logs/m16-20261102/`. The boot command line contains neither `firmware_class.path` nor `keep_proxy_pds`. `extra-dsp-subsystems.txt.gz` reports the root filesystem CDSP image SHA prefix `4a67a03367f2eff2` and `CDSP.HT.2.9.c1-00078-HAMOA-1`; kernel reports image size 3195304. This is consistent with the mapped pair in `firmware/manifest.toml` (image SHA-256 `4a67a03367f2eff2f8a0e867ca25d2bf2fcd5aee3e41e2c9f436c804e257c789`, DTB `93941f040da14b8305d39579686d886706d22954a538b03da676c1aaa191797f`). The root filesystem listing does not independently hash the initramfs copy or prove the DTB actually loaded; no alternate-path override is shown. Do not infer that the staged `c1-00046.1` pair was tested. Prior pair comparison and private staging are in `2026-10-31-denisix-comparison.md`.

**Verified (safe `extra-dsp-subsystems.txt.gz`, timestamps preserved):**

```text
2026-11-02T09:52:46,352510+00:00  32300000.remoteproc:glink-edge: sp11-glink: tx VERSION version=1 features=0x1
2026-11-02T09:52:46,353811+00:00 qcom_q6v5_pas 32300000.remoteproc: handover: proxy power domains kept (driver default)
2026-11-02T09:52:46,354611+00:00  32300000.remoteproc:glink-edge: sp11-glink: rx VERSION_ACK version=1 features=0x1
2026-11-02T09:52:46,354650+00:00  32300000.remoteproc:glink-edge: sp11-glink: rx OPEN name=IPCRTR lcid=0 rcid=2
2026-11-02T09:52:46,355602+00:00  32300000.remoteproc:glink-edge: sp11-glink: rx OPEN name=fastrpcglink-apps-dsp lcid=0 rcid=3
2026-11-02T09:52:46,366443+00:00  32300000.remoteproc:glink-edge: sp11-glink: tx OPEN_ACK name=IPCRTR lcid=0 rcid=2
2026-11-02T09:52:46,369064+00:00  32300000.remoteproc:glink-edge: sp11-glink: tx OPEN name=IPCRTR lcid=1 rcid=2
2026-11-02T09:52:51,622581+00:00  32300000.remoteproc:glink-edge: sp11-glink: OPEN_ACK wait timed out after 5 s name=IPCRTR lcid=1 rcid=2 err=-110
2026-11-02T09:52:51,625340+00:00  32300000.remoteproc:glink-edge: sp11-glink: FIFO tx head=40 tail=16 rx head=160 tail=160
2026-11-02T09:52:51,633574+00:00 qcom_smd_qrtr 32300000.remoteproc:glink-edge.IPCRTR.-1.-1: probe with driver qcom_smd_qrtr failed with error -12
2026-11-02T09:53:10,435590+00:00  32300000.remoteproc:glink-edge: sp11-glink: tx OPEN name=fastrpcglink-apps-dsp lcid=2 rcid=3
2026-11-02T09:53:15,684671+00:00  32300000.remoteproc:glink-edge: sp11-glink: OPEN_ACK wait timed out after 5 s name=fastrpcglink-apps-dsp lcid=2 rcid=3 err=-110
2026-11-02T09:53:15,689096+00:00  32300000.remoteproc:glink-edge: sp11-glink: FIFO tx head=88 tail=16 rx head=160 tail=160
2026-11-02T09:53:15,693509+00:00  32300000.remoteproc:glink-edge: sp11-glink: create_ept remote name=fastrpcglink-apps-dsp failed err=-110
2026-11-02T09:53:15,702415+00:00 qcom,fastrpc 32300000.remoteproc:glink-edge.fastrpcglink-apps-dsp.-1.-1: probe with driver qcom,fastrpc failed with error -12
```

The same collector shows `nsp`, `mxc`, and `cx` on and both CDSP channels unbound. The 16-byte tail equals the previously observed M13 release case, so the retained votes did not restore consumption or the endpoints in this boot. **Inference:** the observable failure is the remote OPEN_ACK handshake, with unconsumed APPS FIFO data; the underlying reason (doorbell, remote sleep, resource, firmware or another issue) is unknown. A FIFO snapshot alone cannot prove why consumption stopped. Handover preceded APPS OPEN; temporal order does not prove causation.

**Verified (source):** CDSP edge uses IPCC CDSP / GLINK signal, remote PID 5 and its FastRPC child matches `fastrpcglink-apps-dsp` (`sources/linux/arch/arm64/boot/dts/qcom/hamoa.dtsi:8944-8997`); Denali supplies the paired firmware names (`x1-microsoft-denali.dtsi:1045-1050`). `IPCRTR` is the QRTR rpmsg match (`sources/linux/net/qrtr/smd.c:92-94`), while GLINK matches the remote name to the DT child (`sources/linux/drivers/rpmsg/qcom_glink_native.c:1585-1605,1629-1687`) and FastRPC binds `qcom,fastrpc` (`sources/linux/drivers/misc/fastrpc.c:2770-2773`). Both names match observed advertisements: no name or DT change is supported. For a remotely opened channel, Linux sends OPEN_ACK then OPEN and waits five seconds for the peer's OPEN_ACK (`qcom_glink_native.c:1288-1316`); endpoint creation returns NULL on failure (`:1319-1350`) and rpmsg core maps NULL to `-ENOMEM` (`drivers/rpmsg/rpmsg_core.c:454-458`). Thus the logged -12 is not evidence of an allocation failure.

## Already-run controlled comparison

**Verified (debug `gpu-two-step/9ea9dbde-e8c7-414f-8561-8bc3f81bc43e/kmsg-follow.txt`):** the already-approved experiment restarted CDSP after ADSP was running, with the normal image and votes forced released. Selected exact lines:

```text
[   36.354006] sp11-cdsp-experiment: counter 0, variant 0 (fw=c1-00078 keep_proxy_pds=0 forced); alternate pair present: yes; keep_proxy_pds writable: yes; firmware_class.path writable: yes; counter saved: yes
[   43.430413] sp11-cdsp-experiment: set: keep_proxy_pds '0', firmware 'qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn', firmware_class.path ''
[   43.927076] qcom_q6v5_pas 32300000.remoteproc: handover: proxy power domains released
[   43.975411]  32300000.remoteproc:glink-edge: sp11-glink: tx OPEN name=IPCRTR lcid=1 rcid=1
[   44.458072] sp11-cdsp-experiment: after start: state running (wait rc 0); firmware_class.path restored to '', keep_proxy_pds restored to '-1'
[   56.485471] sp11-cdsp-experiment: result: variant 0 state running, rx OPEN_ACK after restart 0
```

This restart and the safe cold-boot observation differ in boot, timing and DSP history; they are not an isolated causal comparison. Running is not endpoint success. No additional reset was performed here. The existing alternate-pair experiment is not evidenced as run by these lines. For the already-approved firmware comparison, capture the selected variant, exact image and DTB hashes in the actual loader path, parameter, timing, FIFO and both endpoint bindings/QRTR. Compare the normal and alternate paired builds with the same vote setting and cold-start history where possible; do not add resets or new experiments. Presence of files does not establish selection.

## Sensors and REA

**Verified:** safe `extra-sensors.txt.gz` lists `/dev/fastrpc-adsp`, `remoteproc0=adsp:running` and `400 1 0 5 20 Snapdragon Sensor Core service`; sensor daemon and iio-sensor-proxy are inactive in that capture. `extra-dsp-subsystems.txt.gz` shows ADSP IPCRTR and FastRPC bound. These observations support the sensors dossier's ADSP SSC path, but do not prove sensor events or rule out other dependencies. CDSP repair must not be asserted as a prerequisite for this observed ADSP route.

REA MCP `binary_session` attempted on 2026-11-02 returned `MCP tool call requires approval, but approval policy is never`; no binary was opened, no evidence ID produced. Catalog lists the CDSP image as Hexagon:LE:32:default v73 and its DTB as data, not code (manifest and `sources/binary-catalog.tsv`). Do not use an unforced provider or disassemble the data container. The existing sources request remains open. No functional kernel or DT fix is justified by these observations.
