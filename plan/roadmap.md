# Roadmap

Target: Microsoft Surface Pro 11, 13" LCD, Snapdragon X Plus X1P64100 (10 cores), Wi-Fi-only SKU, NVMe WD SN740 512 GB.

## Phases

| Phase | Goal | Components | Exit criterion |
|:--|:--|:--|:--|
| 0 | Survey | all | Every `hardware/*/component.toml` filled; `hardware/INDEX.md` generated; operator review |
| 1 | Picture and acceleration | `soc-boot`, `display-lcd`, `gpu`, `dsp-subsystems` (boot only) | Acceptance of `display-lcd` and `gpu` met on the device |
| 2 | Input and connectivity | `touch-pen`, `ec-sam`, `wifi`, `bluetooth`, `usb-typec`, `storage` | Usable as a tablet and laptop without external devices |
| 3 | Audio | `audio-speakers`, `audio-mics` | Speakers only with protection evidence |
| 4 | Everything else | `cameras`, `sensors`, `npu`, `video-codec`, `power-thermal`, `security-tpm`, `usb4` | Per component |
| — | Out of scope until asked | `firmware-updates`, `wwan` | — |

## Phase 1 in detail

### Milestones

| ID | Milestone | Owner | Done when |
|:--|:--|:--|:--|
| M1 | Vanilla 7.3 builds as a Fedora RPM with BTF | kernel | RPM installs in the container; `vmlinux` has a `.BTF` section |
| M2 | Vanilla ISO boots and writes logs to the stick | image | `/EFI/sp11-logs/<boot-id>/dmesg` exists after one boot, LCD state recorded either way |
| M3 | LCD with backlight at 60 and 120 Hz | display-lcd | Acceptance in `hardware/display-lcd/README.md` |
| M4 | GPU accelerated | gpu | Acceptance in `hardware/gpu/README.md` |

M2 comes before any patch on purpose: one boot of plain 7.3 shows what the kernel really delivers on this machine, and that log is shared evidence for every component.

### Parallel work

```
         sources (provenance, pins, REA setup)
              |
   +----------+-----------+--------------+
   |          |           |              |
 kernel    firmware    display-lcd      gpu        soc-boot
 (M1)      (map)       (REA, patch)   (REA, fw)  (10 CPUs, idle)
   |          |           |              |            |
   +----------+-----+-----+--------------+------------+
                    |
                  image (M2 vanilla, then M3/M4 with patches)
                    |
               device boot -> logs -> every worker triages
```

All five phase 1 workers start at once. They read the same inputs and write disjoint folders (`agents/protocol.md` §3).

## Device test loop

1. Image worker publishes `out/iso/<name>.iso` with its SHA-256 and the list of included patches.
2. Operator writes it in DD mode, boots, uses the machine for the test plan of each component in scope, powers off.
3. Operator copies `/EFI/sp11-logs/` from the stick into `out/device-logs/<date>/`.
4. Orchestrator files the logs as evidence into each affected component and starts the workers to triage.
