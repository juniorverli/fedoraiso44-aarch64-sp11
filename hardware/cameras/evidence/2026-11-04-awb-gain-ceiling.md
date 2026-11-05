# AWB gain ceiling: a vendor-calibrated cause of the green cast — 2026-11-04

Scope: structural analysis of the two catalogued Windows tuned containers and
of libcamera 0.7.2's Software ISP. No device frame, no image build and no
colour claim: this is a candidate fix derived from the operator's own module
calibration, and it must be verified on the device.

## Symptom and prior state

Both previews are reported green and dark (front IMX681 and rear OV13858).
The earlier audit established that the installed YAMLs carry the device's
black level, four CCM entries, gamma and the AGC target, and that the exact
failing stage (WB, CCM, black or CFA) was not identifiable without per-frame
metadata. That audit remains the reference for measurement:
[rev25 green/dark](2026-11-04-rev25-green-dark.md).

## Finding

- **libcamera side (verified source):** `src/ipa/simple/algorithms/awb.cpp`
  estimates red and blue gains from black-subtracted grey-world sums and
  **clamps each at 4.0**
  (`sum.r() <= sum.g() / 4 ? 4.0f : sum.g() / sum.r()`, and the same for
  blue). When the sensor needs more than 4.0 in a channel, the estimator
  saturates and the residual cast stays in the picture.
- **Vendor side (catalogued private data, structure only):** the module's
  tuned container carries `MWBGainV1`, a ladder of ten green-normalised
  `(red, green, blue)` gain triplets, one per illuminant. Its maxima are
  **8.93× red and 4.28× blue for the front module**, and **3.69× red and
  2.69× blue for the rear module**. The red maximum is more than twice the
  IPA ceiling; the blue maximum is above it. Values stay in `out/` and are
  never reproduced in git (S5).
- **Consequence:** in blue-rich light (high CCT, large red gain) the front
  estimator can reach at most 4.0×, i.e. less than half of the calibrated
  need, which leaves green in the output. In warm light the blue gain is the
  one that saturates (front 4.28× vs the 4.0 ceiling). The rear sits just
  below the ceiling in both directions, so the same mechanism can clip it in
  slightly more extreme light but is less likely to explain a strong cast on
  its own.

## Candidate fix

1. `libcamera-sp11-awb-fixed-gains.patch` adds two optional `Awb:` tuning
   keys:
   - `maxGains: [red, green, blue]` raises the estimator ceiling. Absent, the
     stock 4.0 behaviour is unchanged; values are accepted only in 1.0..16.0.
   - `gains: [red, green, blue]` latches measured grey-card gains for every
     frame (the correction path once the operator captures a neutral).
2. `build-libcamera-tuning.py` derives `maxGains` from `MWBGainV1`: the
   larger of 4.0 and the vendor maximum plus a 10% margin, capped at 16. For
   this device that yields **front 9.83/4.71** and **rear 4.07/4.00**. The
   emitted YAML records only the derived ceiling, never the vendor ladder.
3. `check-awb-ceiling.py` re-derives the ceiling from the catalogued
   containers and asserts that it covers the calibrated maximum and stays in
   the accepted range; it prints PASS/counts only.
4. `camera-diagnostic/calibrate.py` is the measured fallback: given a
   capped-lens dark frame and a neutral frame from the same sensor/mode, it
   computes per-channel black and the green/red and green/blue ratios over a
   central ROI and writes `Awb: gains` into the private YAML (`--install`),
   with a one-time `.sp11-orig` backup and `--restore`. It refuses clipped or
   dark frames, out-of-range gains and a YAML it cannot parse exactly. Its
   host tests cover RAW10 packing, all four CFA layouts, the gain math and
   the YAML round trip.

## What this predicts, and what it does not

- Prediction: the front preview improves markedly, because the estimator can
  now reach the calibrated red/blue gains instead of saturating at half of
  the red need. The rear changes little; if it stays green, the cause is
  elsewhere (CCM selection, black pedestal or CFA) and the per-frame
  `ColourGains`/`ColourCorrectionMatrix` from `camera-diagnostic` will say
  which stage.
- Not claimed: that green is corrected. No device frame has been produced or
  measured with this build. Raising a ceiling is not a calibration by itself;
  it only stops the IPA from refusing a vendor-calibrated gain.
- Risk: a grey-world estimator allowed to reach 9.8× red can over-correct a
  scene dominated by a large red object (magenta cast). The ceiling is the
  vendor module's own maximum, not an arbitrary number, and the stock 4.0
  remains the default for every other tuning file.
- Safety: no stream, exposure, LED, flash or privacy-indicator behaviour
  changes; the change is inside the IPA's gain clamp and the private YAML.

## Coverage, quantified (added after the first analysis)

Using the module's ten calibrated illuminants as the neutral reference set, the
stock 4.0 ceiling is reached in:

- **front**: 2 of 10 illuminants: the coolest needs 55% more red than the
  ceiling allows, the warmest 7% more blue. The middle eight are unaffected.
- **rear**: 0 of 10 illuminants; its calibrated gains never reach 4.0.

Consequences that must be stated before the device test:

- The ceiling change is a **partial fix for the front in cool light**, not a
  general green fix. It cannot explain, and will not change, a rear cast.
- A rear cast on a neutral target is not a CCM problem either: every emitted
  matrix preserves white (row sums are 1.0000), so a neutral stays neutral
  unless the white-balance gains applied before it are wrong or the scene is
  not neutral. The remaining shared candidates are the AWB estimate itself
  (gains stuck at 1.0 because the statistics are invalid, or an estimate pulled
  by the scene) and the black pedestal.
- The decisive observation is per-frame `ColourGains`/`ColourTemperature`:
  `[1.00, 1.00]` means the estimator is not updating (statistics/algorithm
  path), values at the ceiling mean clamp saturation, plausible values mean
  the cast is elsewhere. This is why the device metadata probe is the next
  required step.
- `check-awb-ceiling.py` now also asserts the residual: with the stock 4.0
  ceiling the front clips 2 of 10 calibrated illuminants (worst residual 55%);
  with the derived ceiling neither sensor clips any. That verifies the
  mechanism of the change against the vendor calibration, not the device.
