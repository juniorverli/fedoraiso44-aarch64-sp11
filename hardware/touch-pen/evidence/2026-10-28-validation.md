# Session-2 software checks

Status remains **designed**. No new BTF build, final DT schema validation,
Claude cross-check or device test was run. No write-capable git operation was
used; all project changes are under `hardware/touch-pen/` and uncommitted.
The kernel worktree's previous-session changes were left in place unchanged.

## Completed checks

- `python3 -B hardware/touch-pen/tools/decode-bsrc.py` validates both complete
  BSRC files against catalog hashes, argument/package boundaries and all
  24 root records. It reproduces the selected SP11 GPIO tuples in the
  [investigation](2026-10-28-quad-firmware-sequencing.md).
- `bash -n hardware/touch-pen/collect-read-only.sh` passes. Both embedded
  Python blocks parse with `ast.parse`; no bytecode files are generated.
  This is syntax verification, not a claim that device paths were exercised.
- GNU `patch --batch --fuzz=0 -p1` applies all 11 current v7 patches to
  pinned 7.3 source copies, then RFCs in order 0015,0013,0012,0014
  without fuzz or offsets to **temporary source copies inside this component**.
  The updated board patch exactly matches the standalone disabled DTSI body.
  Temporary copies are removed afterward. The worker kernel checkout is not
  modified by this check.
- `scripts/checkpatch.pl --strict --root=<temporary composed tree>` checks
  those four final RFCs against their updated binding and the existing
  regulator/vendor-prefix schemas. Results below are the final results,
  after splitting the binding into its own patch and wrapping descriptions.
- `git --no-optional-locks diff --check` passes for tracked changes.
- `python3 scripts/index.py --check`: **21 components, 0 errors**.

| RFC | Full strict checkpatch | Strict with `--no-signoff` |
|:--|:--|:--|
| 0015 binding | 1 error: missing Signed-off-by; 0 warnings / 0 checks | 0 errors / 0 warnings / 0 checks |
| 0013 sequencing | same | same |
| 0012 disabled board | same | same |
| 0014 diagnostic | same | same |

The unsigned-style run is supplementary. It does **not** replace the requested
full strict gate, which fails. The operator prohibited adding Signed-off-by;
no worker tag is fabricated. The unchanged **v7** series was also checked
against the composed tree: **3 errors, 6 warnings, 11 checks**. Errors are
missing nominal-author sign-offs in 01, 02 and 09; other findings concern
new-file/MAINTAINERS, short help and trace style. Original mail bodies remain
unchanged. `patches/series` now selects v7 and excludes all four RFCs; root
v6 exports remain archived. V7 application/source hashes are in
[the baseline assessment](2026-10-28-spi-hid-v7.md).

## Not completed

`scripts/kernel-dev.sh` has not been run for these revisions. The v7 baseline, new C,
binding, revised disabled DT and controller-only variant are not build/schema
validated. The historical minimal BTF build and old draft's validation must
not be reused as results for the new artifacts. The image/kernel Requests
contain the exact project dev commands and explain the missing device-state
prerequisite for the functional quad implementation.

No host quad patch was produced because the firmware/personality/GPI command
contract remains incomplete. No firmware upload, touchscreen traffic or GPIO
operation was performed. The collector helper is prepared for the image owner,
not executed on either the test device or this development host.

## Final artifact hashes

Paths below are relative to `hardware/touch-pen/`.

| Artifact | SHA-256 |
|:--|:--|
| `patches/0012-denali-touch-draft.patch` | `8e9ecc7440ab6cdf00b4812aecce9364a71d57795af801877d1ae805b5a36e09` |
| `patches/0013-spi-hid-mshw0484-sequencing-rfc.patch` | `6d758bb397c3204c88c0ed56b429dd371228a04aeb7d62d58094fc8e673619f8` |
| `patches/0014-spi-geni-state-diagnostic-rfc.patch` | `aa5723e26435a4f13b8acccf43c6d2185095be8cdecd809117ce6b8aae61c29d` |
| `patches/0015-hid-over-spi-mshw0484-binding-rfc.patch` | `fbf15e658780e9fd6a38e5b7ac35ed82e1add48ef51920459f24c7635949f8cd` |
| `collect-read-only.sh` | `c3fe13f402396fda15be5c982a9d988297026be1fb27726cf78b7b63926f1129` |
| `tools/decode-bsrc.py` | `423f6d7d2e156521ed44157c89940792ce8eae8cbb8eb1c099e55bf28cf0b3db` |
| `touch-pen-state.dts` | `7973f2ddc2acc229608dfbb996aa1db50691ef65d11797d4c234a79b2c818766` |
