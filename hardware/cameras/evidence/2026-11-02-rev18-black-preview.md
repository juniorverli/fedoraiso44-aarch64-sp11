# Rev18 black preview: probe is known, frame path is not

Source: read-only `out/device-logs/m16-20261102b/d5de4a78-2643-4d46-9b28-31b3b13d56e7/dmesg.txt.gz`.

## Observations

- **Verified:** `ov13858 7-0010: 3 modes loaded from ov13858-mshw0491.bin` appears in dmesg. This demonstrates the driver bound far enough to load its three mode entries; it does not demonstrate a stream, a frame, or a completed CAMSS async notifier.
- **Verified:** CAMSS logs `Entity type for entity msm_tpg0/1/2 was not initialized!` during probe. The rev18 capture has no media graph or capture-attempt output, so it does not establish whether these warnings affect the real sensor path. TPGs are test-pattern entities; the warnings alone do not identify a black-frame cause.
- **Verified:** the bundle contains no media-ctl output, video-node formats, `cam -l` result or capture result. The point of failure is unknown.

## Expected RGB-only graph and diagnosis

From camera DT patches 0005/0018 and RGB-only exclusion patch 0022: the rear OV13858 is on CCI0 master 1/DT bus 1 at address 0x10 and is wired to CSIPHY1 over four-lane D-PHY. The front IMX681 is on CCI1 master 1/DT bus 1 at address 0x10 and is wired to CSIPHY2 over one C-PHY trio. These addresses and routes describe the proposed DT; runtime rev18 topology was not captured. Linux assigns adapter numbers dynamically; rev18's `7-0010` is not the DT bus number. Once CAMSS async registration completes, both sensor subdevice entities and `/dev/v4l-subdev*` nodes should exist, along with CSIPHY/CSID/VFE entities and capture video nodes. Sensor-to-CSIPHY links should be enabled and immutable. Internal CSIPHY-to-CSID and CSID-to-VFE RDI links should exist but can be disabled until userspace selects a route. The no-IR variant removes CAMSS port 0, the IR endpoint/node and CCI0 bus 0; it must leave ports 1 and 2.

Most likely causes, in diagnostic order:

1. **Graph/notifier incomplete:** missing sensor entity or sensor-to-CSIPHY immutable link means effective DT endpoint or async completion problem. An unbound IR endpoint caused this signature previously; rev18 use of the exclusion fragment is not established by its log alone.
2. **Route/formats not configured:** CAMSS's CSIPHY-to-CSID and CSID-to-RDI links are configurable and typically start disabled. Confirm a full route and matching mbus code, size and video fourcc on each pad.
3. **PHY/CSID configuration:** front-only C-PHY trio/rate programming is a risk from patches 0006-0010 and cannot be validated by sensor probe. For either path, CSID errors or no frames after route setup implicate lane mapping, rate, CSID input type or routing.
4. **Sensor mode/link mismatch:** mode-table loading is not register correctness. A selected mode's PLL/link frequency, lane count and format need to agree with endpoint configuration. The OV blob modes use SBGGR10; built-in OV modes use SGRBG10; the IMX681 blob advertises SRGGB10 per prior evidence.
5. **RAW processing:** CAMSS VFE680 is RDI-only and outputs RAW; it does not demosaic. A valid RAW file with a black/unsupported preview points to libcamera SoftISP, IPA/helper, tuning, Bayer order or exposure/control handling. Missing Spectra ISP/ICP support on this upstream path is expected and cannot explain an absent raw capture.

No source/DT defect is established by the current evidence. Do not change a patch until a graph and a capture attempt show which stage fails.

## Next observation

The read-only collector now enumerates every media graph, all `/dev/video*` format/size lists, V4L2 devices and relevant kernel lines without streaming. After image integration, collect this output from the same RGB-only boot. If the graph is complete, use `test-plan.md` to query/set graph formats and perform a small `/tmp` RAW capture only after the privacy indicator is physically verified and visibly on. `cam -l` distinguishes graph/pipeline discovery; successful RAW capture versus black SoftISP preview separates transport from colour processing. Never enable IR or flash.
