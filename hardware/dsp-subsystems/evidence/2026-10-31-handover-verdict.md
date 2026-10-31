# CDSP handover claim (C4): verification and verdict (2026-10-31)

Claim under test: `evidence/2026-10-31-rea-cdsp-handover.md` sections 5-6 and our hypothesis C4. REA was not used. Sources: Linux v7.3 plus the series (`out/linux/m15-verify`), private logs `out/device-logs/m13-20261031` and `m14b-20261031` (and m10, m12, m14), `sources/windows` ACPI. Grades: Verified, Inference, Unknown.

## Verdict: PLAUSIBLE-UNPROVABLE. Nothing in the logs contradicts it; nothing yet supports it over the other open candidates. Only a boot with the votes kept can decide.

## 1. Verified

| # | Fact | Source |
|:--|:--|:--|
| V1 | The handover IRQ handler (threaded) calls `qcom_pas_handover()`, which disables `px`/`cx` supplies, `aggre2` and `xo`, then drops the proxy power domains (`cx`, `mxc`, `nsp` for the x1e80100 CDSP; `lcx`, `lmx` for the ADSP) with performance state 0 and `pm_runtime_put` | `qcom_q6v5.c:198-208`; `qcom_q6v5_pas.c` handover; `x1e80100_cdsp_resource` |
| V2 | `qcom_q6v5_unprepare()` synchronizes the handover IRQ before stop reads the flag; it returns 1 if no handover happened | `qcom_q6v5.c:111-122` |
| V3 | M13, M14 and M14b logged `handover: proxy power domains released` (M10 and M12 predate the log line, same code path); no run has used `keep_proxy_pds=1`, so the claim was never tested | dmesg of those runs; `cmdline.txt` |
| V4 | CDSP SMP2P `handover` arrives 1-2 ms after "remote processor cdsp is now up", and the CDSP's own 160 bytes (VERSION, VERSION_ACK, five OPEN) were already written and read by Apps; Apps' OPEN_ACK comes 150-250 ms later and is never consumed | M13/M14b dmesg `handover` and `sp11-glink` lines; M12 FIFO `tail=8` |
| V5 | genpd after boot: `nsp` off, `mxc` off (Linux side). qcom_stats cdsp: Count 0, accumulated duration about the whole uptime (4.72e9 ticks, 245 s at 19.2 MHz, uptime 250 s) | `genpd_summary.txt`, `extra-dsp-subsystems.txt` (m14b) |
| V6 | The firmware build differs from the working reference: ours `c1-00078`, theirs `c1-00046.1`; the Linux PAS path the reference uses also releases the votes | `evidence/2026-10-31-denisix-comparison.md` |
| V7 | ACPI `\_SB.NSP0` depends on PEP0 (power engine) | `dsdt.dsl:51862-51872` |

## 2. Where the report goes beyond the data

- "genpd off" shows only that Linux dropped ITS vote. rpmhpd aggregates with the votes the firmware places through its own RSC, so `nsp off` in genpd is not a hardware power state and cannot show a collapse.
- "Count 0, duration accumulating" is also what an idle CDSP with its own sleep path shows (the count may not be incremented by this firmware); the same two numbers are unchanged between runs and say nothing about cause.
- "Windows PEP keeps NSP and MXC votes for the whole runtime" has no decoded source: only the `_DEP` on PEP0 (V7). The PEP configuration of the NSP component was not decoded; the earlier M12 evidence already lists the Windows votes as Unknown. It stays Inference.
- The `handover` bit means the firmware has taken over; Windows' name for the same bit is `PWR_CLK_RDY`. If the c1-00078 firmware asserts it without holding its own votes, the claim holds; if it does, the votes Linux releases are not needed. Both read the same.
- The CDSP reads the first message, then nothing, while it was clearly alive after handover to send 160 bytes (V4). Other candidates remain open: firmware build itself (E1 in the denisix comparison), a missing wake or IPCC condition, boot order and cold state. A cheaper discriminator exists: E1 (swap to `c1-00046.1`).
- The proposed patch in the report names `adsp_data` and `x1e80100_cdsp_resource_init`, which do not exist in v7.3 (`qcom_pas_data`, `x1e80100_cdsp_resource`), and it would have held the votes for ALL boards using the resource.

## 3. What only the hardware can show

Boot with the votes kept (the new default on Denali, or `qcom_q6v5_pas.keep_proxy_pds=1`): log line `kept (...)`, then `OPEN_ACK` for IPCRTR consumed (FIFO tail moves), `qrtr-lookup` listing CDSP services, `fastrpcglink-apps-dsp` binding, `qcom_stats/cdsp` count. Pass confirms C4. Fail (still tail 8) refutes it for this firmware and points to E1 or to a wake/doorbell cause. Run the opposite (`keep_proxy_pds=0`) in a second boot of the same kernel to compare.

## 4. Decision

M15 defaults `keep_proxy_pds` ON for the x1e80100 CDSP on `microsoft,denali` only, as an experiment with the parameter as override. Reasons: the kept state has no safety rule against it (no S1-S6 item concerns it), it is reversible by a parameter without rebuilding, the previous diagnostic path needed a cmdline entry on a device that is rebooted for each test, and a default makes the M15 test boot decide C4 without a new image entry. Cost: NSP, MXC and CX stay at the start performance level for the whole uptime (idle power on battery), and on a failed test the next kernel should drop the default.

Patch `patches/0003-remoteproc-qcom_q6v5_pas-add-keep_proxy_pds-diagnostic.patch` amended in place (name and series position unchanged). Tri-state module parameter `keep_proxy_pds` (-1 driver default, 0 release, 1 keep; mode 0644; read once per handover); data flag `keep_proxy_pds_denali` set only in `x1e80100_cdsp_resource`, resolved at probe with `of_machine_is_compatible("microsoft,denali")`; new helper `qcom_pas_release_proxy()` shared by the handover and stop paths; stop releases held votes after a stop with a handover, and drops the start votes (without logging a keep) after a stop before the handover; kept only when there is at least one proxy domain; log line states the reason. ADSP, SLPI, audio and every other board: no behaviour change unless the parameter is set to 1. Results: `checkpatch --strict --no-signoff` 0/0/0; `git apply --check` clean on v7.3; object `drivers/remoteproc/qcom_q6v5_pas.o` compiled with `W=1` on `out/linux/m15-verify`, no warning. Not linked, not run.

Open risk in the code (Unknown): a parameter change to 1 applies to all instances including the ADSP (as the previous diagnostic did); the ADSP default stays release.
