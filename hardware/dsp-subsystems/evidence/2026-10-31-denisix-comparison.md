# Comparison with the denisix Ubuntu SP11 setup (2026-10-31)

Reference: `https://github.com/denisix/ubuntu-surface-pro-11`, cloned at `out/ref/ubuntu-surface-pro-11` (README.md, NPU.md, SENSORS.md, SUSPEND.md, SOUND.md, scripts/, systemd/, grub/, kernel-patches/). Same hardware class (Surface Pro 11, X1E80100, Denali), kernel `7.1.3-jg-1sp11v2-qcom-x1e` (Jens Glathe tree). They report CDSP + FastRPC working (`/dev/fastrpc-cdsp`), llama.cpp on HTP0, 13 ADSP SSC sensors. Ours: CDSP reads our first one or two GLINK words and stops (M12 tail 8, M13 tail 16 of 40/88).

Third-party claims are Inference/Unknown until reproduced here. Ours are from `out/device-logs/m13-20261031/93b13406*/` (private, not copied), `sources/windows`, `sources/linux` (v7.3). No Windows binary was opened; REA was not used. Grades: Verified, Inference, Unknown.

## 1. The one Verified difference: CDSP firmware build

| | Ours | Theirs |
|:--|:--|:--|
| `qccdsp8380.mbn` build string | `CDSP.HT.2.9.c1-00078-HAMOA-1` (built 2025-11-01), SHA-256 `4a67a033...57c789` | `CDSP.HT.2.9.c1-00046.1-HAMOA-1`, SHA-256 `70384d0a...8d989bd` |
| Windows package | `qcnspmcdm_ext_cdsp8380` DriverVer `30.0.0219.1000` (2025-11-09), from the device's own DriverStore | same package, DriverVer `30.0.0145.1000` (2025-07-14) |
| Source of their file | `scripts/sp11-grab-fw.sh` downloads the newest folder of `WOA-Project/Qualcomm-Reference-Drivers/Surface/8380_DEN` (`200.0.49.0`) | |

Verified by downloading `qcnspmcdm_ext_cdsp8380.cab` of every `8380_DEN` folder and reading `QC_IMAGE_VERSION_STRING`: `200.0.32`-`35` = `CDSP.HT.2.9-00458`; `200.0.37`-`44` = `c1-00046`; `200.0.45`-`49` (latest, the one the script fetches) = `c1-00046.1`. The public mirror has nothing newer, so the denisix reproduction guide pins the older build. The copy is staged privately in `out/firmware-private/dsp-subsystems/cdsp-c1-00046.1-woa-200.0.49.0/` (`SHA256SUMS` inside; never git, S5).

Everything else in the CDSP pair is the same:

- `cdsp_dtbs.elf`: 40760 bytes both, `dtc` output identical (only 378 signature or padding bytes differ). Verified.
- `qccdsp8380.mbn`: 16 program headers both, same load window `0x8b900000`-`0x8d900000`, same entry; only the last bss size and the code differ. The DT carve-outs (`cdsp@8b900000`, `q6-cdsp-dtb@8d900000`) fit both. Verified.
- `qcadsp8380.mbn`: byte-identical (`921870a8...`, `ADSP.HT.5.9-00810-HAMOA-1`). ADSP works for us and for them. Verified.
- Firmware path `qcom/x1e80100/microsoft/Denali/qccdsp8380.mbn` + `cdsp_dtb.mbn`, from `x1-denali` DT in their tree and from `x1-microsoft-denali.dtsi:1045-1048` here. Verified.
- The CDSP user-side shells differ too: our Windows package has shells stamped `c1-00078`, theirs `c1-00046.1`. The Fedora `hexagon-dsp-binaries-qualcomm-hamoa-iot-evk` shells are `c1-00094` (the upstream Hamoa reference, not Surface-signed firmware). NPU.md says shell and firmware must be the same branch; mixing builds is a known failure for them (GLINK framing errors on session open). Inference, from their text.

Inference I-1: the `c1-00078` build changed something the Linux PAS path does not provide, and `c1-00046.1` does not need it. Candidate content of the change: how the firmware holds NSP/MXC/CX votes after `handover` (our C4), or a wake or doorbell dependency that Windows PEP/`qcsubsys8380` satisfies (M12 section 3). Not established; the firmware build is the only variable proven different, so it is the cheapest first test.

## 2. Linux side: same or irrelevant

| Item | Theirs | Ours | Reading |
|:--|:--|:--|:--|
| Kernel command line | `clk_ignore_unused pd_ignore_unused arm64.nopauth systemd.tpm2_wait=0 mem_sleep_default=s2idle`, `cma=128M efi=noruntime` (`grub/*.cfg`) | `clk_ignore_unused pd_ignore_unused` (M13 `cmdline.txt`) | Same flags that could matter. They do not stop the explicit proxy release (M12 section 4), so they are not what makes theirs work. Verified (both lines read). |
| Boot level | Unknown | `All CPU(s) started at EL1`, `kvm: HYP mode not available`, PAS works | Their tree carries Gerhold's EL2 patches ("attach running remoteproc if firmware is missing", "avoid broken reset when running bare-metal"). On ours PAS auth works, so the attach path is not in play. Unknown whether theirs boots at EL2. |
| PAS driver | 7.1: no PAS-context rework | 7.3: Mukesh Ojha `qcom_pas_ctx`, `qcom_pas_map_carveout` (acts only with `rproc->has_iommu`, false here: `qcom_q6v5_pas.c:264-278`), Abel Vesa one-shot handover IRQ, Gerhold SMP2P takeover | The handover and start order is unchanged (`qcom_q6v5_prepare`, proxy PDs, xo, auth, wait, handover releases PDs: `qcom_q6v5_pas.c:281-398`). No behavioural suspect found in 7.3. Verified by source read, Unknown by test. |
| GLINK, SMEM, IPCC, rpmhpd, pd-mapper | No sp11-specific patch (grep of their kernel-patches: dmic, rfkill, touchscreen/gpi/QSPI only) | v7.3 + our diagnostics | No difference in the transport. |
| `fastrpc.ko` "GLINK framing fix", `gpi.ko` fix | Out-of-tree hack, source not in the repo | v7.3 | Acts after the channel opens. Cannot explain a CDSP that does not read OPEN_ACK. Inference. |
| Probe order | ADSP is `remoteproc0`, CDSP `remoteproc1` (their scripts) | CDSP is `remoteproc0`: the ADSP rproc is released ("releasing adsp") and re-registered, then ADSP boots 0.7 s after CDSP (M13 dmesg, `smp2p` trace 4.00 vs 4.67 s) | Possible difference I-2: theirs boots ADSP first. No evidence it matters; testable by delaying the CDSP start. |
| CDSP DT | hamoa + Denali firmware names | identical node: `qcom,qmp`, cx/mxc/nsp, smem-state `stop`, IPCC client 6 (live `devicetree.dts`, M10 F8) | No difference. Verified for ours. |
| Reset before run | `echo stop/start > remoteproc1/state` before every NPU run; "cold power-off, not reboot, if GLINK framing breaks" | warm reboots between every M-test | Their remark suggests CDSP/GLINK state can survive a warm reboot. Hypothesis H-3: a stale CDSP state after our earlier boots. Our M12 and M13 runs differ in tail (8 vs 16), which shows run-to-run variation. Killed by one cold boot. |
| Sleep | `cpu-sleep-0` disabled around suspend (SUSPEND.md); denisix ADSP stays up | not applicable to boot | Not related. |
| udev/services | `99-fastrpc.rules` (0666); `hexagonrpcd` early in `sysinit.target` for the ADSP | no daemons run | The daemons run after `/dev/fastrpc-*` exist; ours never reaches that. Not a cause. |

## 3. What the genuinely open items are

- M13 shows `OPEN_ACK` for IPCRTR written 245 ms after the CDSP's OPEN (module load of `qrtr-smd`), and the CDSP never reads it (`tx head=40 tail=16`). The first two words (VERSION, VERSION_ACK) were read inside the first 3 ms. So the CDSP reads only while it is awake right after boot. Inference: it is asleep or unreachable by our IPCC doorbell afterwards (`qcom_stats/cdsp Count 0`, `nsp` and `mxc` off, `cx` on). Same conclusion as M12 C2/C4.
- M13 did not run patch 0003 with the parameter set (`handover: proxy power domains released`), so C4 is still open.
- Our `aoss_send` trace shows only `qdss` clock sends because the collector `head -n 100` cut it; whether `load_state cdsp on` was sent is Unknown (no error line in dmesg). Collector fixed (this change): `qdss` is excluded and counted.
- `power:power_domain_target` failed again in M13 (`Failed to enable trace event`): drop it from `trace_event=`.

## 4. Decision

No fix is established, so no kernel patch is written (0003 already covers C4; adding a patch for I-1 would be a guess). The next experiments, in the order of cost, one boot each, all using the same debug entry and the current collector:

1. **E1, firmware swap (priority).** Boot the debug entry with the `c1-00046.1` pair as CDSP firmware, ADSP unchanged. Keep patches 0001-0003, `keep_proxy_pds` off. Pass: `OPEN_ACK` for IPCRTR arrives, `qrtr-lookup` lists CDSP services, `fastrpcglink-apps-dsp` binds. Pass proves I-1 and points at a `c1-00078` behaviour change; then ship the older pair in the private image (the 00078 Windows files are the operator's own device state; both are Microsoft-signed).
2. **E2, C4 test.** Same entry, `00078` firmware, `qcom_q6v5_pas.keep_proxy_pds=1`. If E1 failed, run E2 with `00046.1` too.
3. **E3, order and cold start.** Cold power-off before the boot (H-3) and, if still stuck, a later CDSP start (write `start` to the CDSP `state` after the ADSP is `running`, from a unit; needs `auto-boot` off, which needs a DT variant: only if E1 and E2 fail).

How to load the E1 firmware without a DT change: `firmware_class.path=/usr/lib/firmware-sp11-cdsp46` on the command line. The loader tries that directory before the normal paths, so only the two CDSP files placed there (same relative path `qcom/x1e80100/microsoft/Denali/`) are replaced and the ADSP files come from the normal tree. The directory must be in the initramfs because early PAS (D20) requests the firmware before the root file system is mounted. Unknown: whether dracut `install_items` and the 256-byte `firmware_class.path` limit are enough; image owner confirms. Alternative: a one-off DTB variant with `firmware-name` pointing at `.../Denali/cdsp46/`.

Not adopted from the reference: `arm64.nopauth`, `efi=noruntime`, `cma=128M` (no relation to the CDSP stall; PAC and runtime services are other owners' decisions), the Python lid daemon, the `cpu-sleep-0` workaround (suspend owner reads SUSPEND.md).

## 5. Asks

- **image** (R-I6): new debug entry `cdsp46`: stage `out/firmware-private/dsp-subsystems/cdsp-c1-00046.1-woa-200.0.49.0/{qccdsp8380.mbn,cdsp_dtb.mbn}` privately under `/usr/lib/firmware-sp11-cdsp46/qcom/x1e80100/microsoft/Denali/` (initramfs too), cmdline `firmware_class.path=/usr/lib/firmware-sp11-cdsp46`, and replace `trace_event=` by `:mod:qcom_glink,:mod:smp2p,:mod:qcom_aoss,rpmh:rpmh_send_msg`. Private mode only. Add a second entry `cdspkeep` with `qcom_q6v5_pas.keep_proxy_pds=1`. Refresh `/etc/sp11-log-collector.d/dsp-subsystems.sh`; it now records the loaded firmware build ids and `firmware_class.path`.
- **kernel**: nothing new. Patches 0001-0003 stay in the series. Add a note: do not enable `fastrpc` or `gpi` hacks from the reference.
- **firmware**: record the `c1-00046.1` pair as a private alternative (`firmware/` owner decides the manifest name); hashes are in the staged `SHA256SUMS`.
- **operator**: for E1 do a full power-off (not reboot) before the boot (H-3).
