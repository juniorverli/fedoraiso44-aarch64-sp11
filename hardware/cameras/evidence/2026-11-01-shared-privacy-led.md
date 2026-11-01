# Shared camera privacy LED arbitration

## Finding

Linux 7.3 tracks a privacy LED on each `struct v4l2_subdev`. The stream
helpers set that LED to maximum brightness on a start and to zero on a stop.
When front and IR subdevices resolve `led_get(dev, "privacy")` to the same
`led_classdev`, stopping either one can therefore turn off the indicator while
the other still streams. The LED core serializes access to a class device, but
does not maintain a count of independent camera consumers.

The proposed V4L2 core change in patch `0020-media-v4l2-core-refcount-shared-privacy-leds.patch`
adds a mutex-protected registry keyed by `led_classdev`. Stream state changes
the physical LED only on shared-user transitions from zero to one and one to
zero. Acquisition and release are serialized with streaming changes. The last
release removes the registry entry while holding the mutex, but retains that
subdevice's `led_get()` reference until after unlock; a concurrent reprobe can
then create a new registry entry with its own reference without using the
removed entry. The change contains no GPIO mapping and does not enable an IR
illuminator or flash.

## Evidence and limits

- Linux source: `sources/linux/drivers/media/v4l2-core/v4l2-subdev.c` (base
  `v7.3`, commit `c03c1a14507dfaf8b856c2608f9ac216021fc222`), functions
  `call_s_stream()`, `v4l2_subdev_enable_streams()` and
  `v4l2_subdev_disable_streams()`. Stream start/stop is already first/last at
  the subdevice level for native streams and single-transition for `s_stream`;
  the missing arbitration is between subdevices sharing one class device.
- LED core: `sources/linux/drivers/leds/led-class.c`, `led_get()` / `led_put()`
  pin the class device/module; brightness serialization does not represent
  multiple camera users.
- The Windows driver REA results in
  `evidence/2026-10-30-rea-seven-questions.md` include a per-sensor atomic
  reference count. Binary SHA-256:
  `836714ec41f92f45af363d7bf3c9b9cfc2cccdbd19a1c57f355b471068648049`;
  language `AARCH64:LE:64:v8A`; relevant writer analysis evidence IDs
  `ev_989ad9c4565219231090c7ba7dc0c42f967ee5c3814e797186e49402404986b5` and
  `ev_e1a441571df39a36fa8da540cffc328a951be2a71d3996a90037da411324cd04`.
- GPIO-to-camera identity remains an inference pending an independent runtime
  cross-check. The generic change deliberately does not encode GPIO values or
  claim the mapping verified.

## Checks

- ARM64 V4L2 object build with the KUnit option disabled: passed; the object
  has no `.kunit_test_suites` section.
- ARM64 `videodev.o` module link with `CONFIG_KUNIT=y`,
  `CONFIG_VIDEO_DEV=m`, `CONFIG_VIDEO_V4L2_SUBDEV_PRIVACY_LED_KUNIT_TEST=m`,
  and `CONFIG_LEDS_CLASS=y`: passed. The linked module contains the KUnit
  suite section, the existing single `init_module` and `cleanup_module`
  symbols, and no second init/exit entry point from `kunit_test_suite()`.
- The suite exercises the shared get/put bookkeeping used by the exported
  V4L2 helpers: first and second consumer, duplicate acquisition rejection,
  on/off transitions, last-user teardown, idempotent repeated put, and
  reacquisition after teardown. The suite was compiled but **not executed**;
  no AArch64 emulator or target runtime was available in this session.
- `git diff --check` and kernel `checkpatch.pl --strict`: clean.

## Conclusion

The software arbitration gap is confirmed for shared LED class devices and a
generic kernel fix is prepared. This does not prove which camera maps to GPIO
225 or GPIO 105, nor does it validate electrical polarity or device behavior.
Keep camera hardware disabled pending the existing safety and runtime checks.
