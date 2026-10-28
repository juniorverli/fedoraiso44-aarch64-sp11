# M5 device log: ADSP, CDSP, pmic-glink

Source: `out/device-logs/m5-20261028/` (read-only). Two boots, both kernel `7.3.0-65.sp11.3.fc44.aarch64`, DTB `microsoft,denali-lcd` (m5 family: `/sound` and `&swr0` disabled):

| Boot id | Entry | Files used |
|:--|:--|:--|
| `3f0e2cc1-a043-4c6c-9a72-0835089648d7` | `sp11.entry=debug` (GPU off), cmdline `clk_ignore_unused pd_ignore_unused rootdelay=10` | `dmesg.txt`, `journal.txt`, `remoteproc.txt`, `power_supply.txt`, `lsmod.txt`, `devices_deferred.txt`, `firmware-failures.txt`, `sound.txt` |
| `0ee2fa1a-6346-400d-97e0-2589cc9b5275` | `sp11.entry=gpu` (GPU on) | `dmesg.txt` (no `remoteproc.txt`, no `power_supply.txt`) |

All lines below are quoted from those files. Timestamps in the form `[ s.us ]` are the journal's kernel clock (`journal.txt`); ISO times are `dmesg.txt`.

## 1. What works (Verified)

- Both remoteprocs `running` with the Denali images (`remoteproc.txt`): `remoteproc0` name `adsp`, firmware `qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn`; `remoteproc1` name `cdsp`, firmware `.../qccdsp8380.mbn`; `recovery: enabled`, `coredump: disabled`.
- Boot chain as predicted by the static map: `remoteproc0: adsp is available`, `remoteproc1: cdsp is available`, `powering up cdsp`, `powering up adsp`, `Booting fw image .../qccdsp8380.mbn, size 3195304`, `Booting fw image .../qcadsp8380.mbn, size 22092168` (`[ 2.928985]`-`[ 2.953008]`), `remote processor cdsp is now up` (`[ 3.097383]`), `remote processor adsp is now up` (`[ 3.296017]`). The sizes equal the manifest sizes, so the initramfs copies are the staged files (D20 holds: the firmware was readable when the driver probed).
- No `Direct firmware load` or `request_firmware failed` for any DSP file; `firmware-failures.txt` has none about `remoteproc`, `qcadsp`, `qccdsp`, `adsp_dtb`, `cdsp_dtb`. No `failed to authenticate`, no `start timed out`, no `crash detected`, no `watchdog received`, no `fatal error received` in either boot. The `IgnoreWdogEnabled` Windows setting (hypothesis in the static map) did not matter in these two boots.
- pmic-glink works. `power_supply.txt` (boot `3f0e2cc1`) lists: `ADP1` and `BAT1` (SSAM), `qcom-battmgr-ac`, `qcom-battmgr-bat`, `qcom-battmgr-usb`, `qcom-battmgr-wls`, `ucsi-source-psy-pmic_glink.ucsi.01` and `.02`. `lsmod.txt`: `pmic_glink`, `pmic_glink_altmode`, `qcom_battmgr`, `ucsi_glink`, `typec_ucsi`, `ps883x`, `qcom_pd_mapper`, `pdr_interface`, `qrtr`, `qrtr_smd`. The two UCSI source supplies show that UCSI registered both ports.
- PDR worked: in boot `0ee2fa1a`, `PDR: Indication received from msm/adsp/charger_pd, state: 0x1fffffff, trans-id: 1` and the same for `msm/adsp/audio_pd` (`18:24:01,324465` and `,336169`), so the in-kernel mapper served `tms/servreg` and the ADSP's notifier answered for both domains. In boot `3f0e2cc1` the modules loaded after the PDs were up, so no indication line is expected; the battery values prove the service was `UP`.
- Audio: `sound.txt` says `--- no soundcards ---` and `/sys/bus/soundwire/devices` does not exist: S1 holds on the device (no WSA8845 bound, no card).

## 2. Battery: two sources agree (Verified for the values, Inference for the meaning)

| Attribute | `BAT1` (SSAM, `surface_battery`) | `qcom-battmgr-bat` (ADSP) |
|:--|:--|:--|
| `energy_full` | 44780000 | 44780000 |
| `energy_full_design` | 46530000 | 46530000 |
| `energy_now` | 17000000 | 17016000 |
| `voltage_now` | 7323000 | 7323000 |
| `status` | Discharging | Discharging |
| `power_now` | 16813000 | -15224000 (sign convention differs) |
| `capacity` | 37 | not listed (the driver exposes energy, not capacity, for X1E) |
| `present`, `manufacturer`, `model_name` | 1, `SWD`, `1325620001` | 1, `Qualcomm`, `QCOMMBATT01` |
| `charge_control_start_threshold`, `charge_control_end_threshold` | n/a | `0`, `0` |

- Both register. They report the same cell data, so the ADSP and the SSAM EC read the same gauge. Consequence: userspace sees two `Battery` supplies. Q2 of the dossier is answered for registration (both); which one GNOME should use is a recommendation (Inference): keep `BAT1`, because Windows exposes only the SSAM battery (live inventory), and hide `qcom-battmgr-bat` from UPower with a udev property. Hand to `ec-sam` (request below).
- S6 finding (Verified in code, Hypothesis for impact): `qcom-battmgr-bat` exposes writable `charge_control_start_threshold` and `charge_control_end_threshold` (`qcom_battmgr.c:662-724`, `:760-792`, `.property_is_writeable` at `:863,931`), which send `BATTMGR_CHG_CTRL_LIMIT_EN` to the ADSP. The DT has no `nvmem-cells` `charge_limit_*` (`qcom_battmgr.c:731-751`), so the driver does not know the firmware's current limit and reads `0`. A user or GNOME power-settings write of `100` could replace a lower limit that the ADSP or the Surface firmware holds, which would raise a charge limit above the Windows value (S6). Nothing in the image writes them now. Request to `image`: no unit, rule or script may write `charge_control_*`; the orchestrator decides whether to enforce it with a read-only patch.

## 3. The -12 on the CDSP GLINK edge (Verified chain, Hypothesis for the root cause)

Quoted lines (`dmesg.txt`, boot `3f0e2cc1`):

```
[    8.673025] qcom_smd_qrtr 32300000.remoteproc:glink-edge.IPCRTR.-1.-1: failed to create endpoint
[    8.673222] qcom_smd_qrtr 32300000.remoteproc:glink-edge.IPCRTR.-1.-1: probe with driver qcom_smd_qrtr failed with error -12
         failed to announce new service
         failed while handling packet from 5:-2
[   31.715702] qcom,fastrpc 32300000.remoteproc:glink-edge.fastrpcglink-apps-dsp.-1.-1: failed to create endpoint
[   31.715826] qcom,fastrpc 32300000.remoteproc:glink-edge.fastrpcglink-apps-dsp.-1.-1: probe with driver qcom,fastrpc failed with error -12
```

Boot `0ee2fa1a` has the `fastrpc` pair (`18:24:28,364752`), not the `IPCRTR` pair, and in addition `qcom_q6v5_pas 32300000.remoteproc: timeout waiting for subsystem event response` (`18:24:06,348748`).

**Why -12.** `-12` is `-ENOMEM`, and it is not an out-of-memory error. `rpmsg_dev_probe()` calls `rpmsg_create_ept()`; when that returns NULL it prints `failed to create endpoint` and hard-codes `err = -ENOMEM` (`drivers/rpmsg/rpmsg_core.c:451-458`). For GLINK, `qcom_glink_create_ept()` (`drivers/rpmsg/qcom_glink_native.c:1319-1358`) returns NULL when `qcom_glink_create_remote()` fails (`:1288-1316`). For a channel that the remote opened first (every channel on this edge), that function sends the open-ack, sends our open request, then waits 5 s for the remote's open-ack, and returns `-ETIMEDOUT` if none arrives. Evidence that this is the 5 s timeout:

1. The `IPCRTR` failure is logged 5.38 s after `cdsp is now up`/`adsp is now up` (`[ 3.296]` to `[ 8.673]`), with the `qrtr_smd` module load starting right after the edge came up.
2. The same timeout appears for `fastrpcglink-apps-dsp` on the CDSP edge only, in both boots, while the ADSP's `fastrpcglink-apps-dsp` on the same module probes fine one line later.
3. In the GPU boot the CDSP's sysmon also times out (5 s) waiting for the CDSP's SSCTL reply (`qcom_sysmon.c:374-411`, called from `sysmon_start` at `:524`), and `adsp is now up` is logged 5.1 s late (`18:24:06,350890`, while PDR for the ADSP was already up at `18:24:01,324465`). That is the same fault seen through a second path: the CDSP does not answer messages from the application processor.

So the CDSP boots (ready IRQ, `running`), opens channels towards Linux, and never acknowledges the channels Linux opens, and it does not answer QMI requests. Root cause: TBD. Hypotheses to test, in the order the log supports them:

- H-C1: the CDSP's GLINK/QRTR side is not serviced after boot (the Windows NSP image `qccdsp8380.mbn` may wait for something the Windows `qcnspmcdm` driver provides before it services APPS channels). Confirms with: GLINK trace shows our `open` with no `open_ack` back (request R-K1), `qrtr-lookup` lists no CDSP node, rebinding after a long idle also times out.
- H-C2: a timing race (the first boot probed 0.4 s after the CDSP came up and failed on `IPCRTR`; the second boot probed later and passed `IPCRTR` but still failed `fastrpc` and the SSCTL event). Confirms with: rebind of `IPCRTR` after the system has been up for minutes succeeds.
- H-C3: the IPCC mailbox signal towards the CDSP (`hamoa.dtsi:8985-8987`) is lost or the CDSP is in power collapse and not woken (`pd_ignore_unused` is set, `qcom_stats` for `cdsp` would show sleep counts). Same DT as every other X1E laptop, so lower probability.

**Does it matter?** Not for D22. Battery, charging, UCSI and altmode need only the ADSP edge (static map section 4) and all work. The CDSP carries no service of the usable-tablet set. What it costs, all Verified from the log:

- A 5 s stall in the `qrtr_smd` and `fastrpc` module loads, and in the GPU boot a 5 s delay of `adsp is now up` (sysmon event to the dead CDSP). `failed to announce new service` and `failed while handling packet from 5:-2` appear in the same millisecond window as the `IPCRTR` failure: node 5 is the ADSP (the only endpoint that registered, so the only QRTR node that exists), and the in-kernel name service failed once to announce its local servers to it (`net/qrtr/ns.c:216-238` returns on the first error). Since PDR and battmgr reached `UP`, the ADSP got the locator through its own lookup. Inference (strong); `qrtr-lookup` on the next boot settles it.
- `/dev/fastrpc-cdsp*` do not exist, so the `npu` worker cannot use the CDSP yet.

Advice: leave the CDSP enabled in the default entry for one more evidence boot (cheap, no safety effect), add the two diagnostics in the request list, then decide. If the 5 s stalls still hurt after that boot, add a DT variant with `&remoteproc_cdsp { status = "disabled"; }` for the usable-tablet entry only. Do not change firmware or the Windows image for this.

## 4. Audio APM timeout (Verified)

`qcom-apm gprsvc:service:2:1: CMD timeout for [1001021] opcode` (`[ 32.225245]`, also `18:24:29,389742`). Opcode `0x1001021` is `APM_CMD_GET_SPF_STATE` (`sound/soc/qcom/qdsp6/audioreach.h:42`). `q6apm_probe()` asks the ADSP audio framework whether it is ready (`q6apm.c:143-152,886`) and `audioreach.c:617-623` waits 5 s. So `q6apm` probes because its `gpr` node sits under the ADSP `glink-edge` (`hamoa.dtsi:4372-4420`), not under `/sound`; the sound card being disabled does not stop it. The timeout means the ADSP audio PD (`msm/adsp/audio_pd`, service `avs/audio`) did not answer `SPF state` yet; it costs one probe 5 s and drives no output. S1 is not involved: no card, no codec, no soundwire device. Open: whether the SPF answers later, TBD; it matters only to the audio workers.

## 5. Other observations in the same log (not dsp-subsystems; for the orchestrator)

- A kernel oops `Unable to handle kernel NULL pointer dereference at virtual address 00000000000000a8` at `18:16:57,186346` and about twenty more of the same kind: `msm_dp_test_active_show+0x20/0x80 [msm]` called through `full_proxy_read`, i.e. the collector reading a DisplayPort debugfs file (`/sys/kernel/debug/dri/*/…test_active`) of a DP controller that is not bound to a sink. This is display-lcd's area (`drm/msm/dp` debugfs). The reads come from `dump_tree drm-debugfs.txt`.
- `pmic-glink: Failed to create device link (0x180) with supplier a600000.usb for /pmic-glink/connector@0` and three similar lines (`[ 2.960580]`-`[ 3.011233]`). These are fw_devlink notices for the connector graph (`remote-endpoint` links to DWC3 and `ps883x`), preceded by `Fixed dependency cycle(s) with /pmic-glink/connector@0`. They did not stop pmic_glink, UCSI or altmode from probing. For `usb-typec`.
- `surface_hid ... probe with driver surface_hid failed with error -71` and `ath12k ... qmi dma allocation failed`: other workers.
