#!/usr/bin/env python3
"""Check the derived AWB gain ceiling against the module's calibrated ladder.

Reads the two catalogued Windows tuned containers (private, risk S5) and
verifies the structure that `build-libcamera-tuning.py` relies on:

  * MWBGainV1 carries a green-normalised (red, green, blue) gain triplets
    ladder, and the extracted ceiling covers the largest calibrated gains;
  * the derived ceiling is inside the IPA's accepted 4.0..16.0 range and is
    never below the stock 4.0;
  * a container without the block yields no ceiling (stock behaviour).

Prints PASS/FAIL and counts only: no gain values and no private data.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BINS = {
    "ov13858": "surfacecamrearsensor_extension8380.inf_arm64_*/com.surface.tuned.rfc_ov13858.bin",
    "imx681": "surfacecamfrontsensor_extension8380.inf_arm64_*/com.surface.tuned.ffc_imx681.bin",
}


def load(path):
    spec = importlib.util.spec_from_file_location("gen", HERE / "build-libcamera-tuning.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Chromatix(path)


def main():
    spec = importlib.util.spec_from_file_location("gen", HERE / "build-libcamera-tuning.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    failures = 0
    for sensor, pattern in BINS.items():
        hits = list((REPO / "sources/windows").glob("DriverStore/" + pattern))
        if len(hits) != 1:
            print(f"FAIL {sensor}: expected one tuned container, found {len(hits)}")
            failures += 1
            continue
        m = load(hits[0])
        notes = []
        ceiling = gen.pick_awb_limits(m, notes)
        if ceiling is None:
            print(f"FAIL {sensor}: no ceiling derived ({notes[-1] if notes else 'no note'})")
            failures += 1
            continue
        red, blue = ceiling
        ok = 4.0 <= red <= 16.0 and 4.0 <= blue <= 16.0
        # The largest calibrated red gain must be covered by the ceiling.
        body = [s for s in m.syms if s["name"] == "MWBGainV1"][0]
        values = m.floats(body["idx"])[6:]
        triplets = [values[i:i + 3] for i in range(0, len(values) - 2, 3)
                    if all(isinstance(x, float) for x in values[i:i + 3])]
        triplets = [t for t in triplets if len(t) == 3 and abs(t[1] - 1.0) < 1e-3]
        covers = bool(triplets) and red >= max(t[0] for t in triplets) - 1e-6 \
            and blue >= max(t[2] for t in triplets) - 1e-6
        # Residual colour error on a neutral illuminant for a clamped channel:
        # 1 - applied/needed. The stock 4.0 ceiling must clip at least one
        # calibrated illuminant of the front module; the derived ceiling must
        # clip none on either sensor.
        def clipped(limit_r, limit_b):
            worst = 0.0
            count = 0
            for r, _g, b in triplets:
                err = max(0.0, 1.0 - min(limit_r, r) / r, 1.0 - min(limit_b, b) / b)
                if err > 1e-6:
                    count += 1
                    worst = max(worst, err)
            return count, worst
        stock_count, stock_worst = clipped(4.0, 4.0)
        new_count, new_worst = clipped(red, blue)
        expected_stock = 2 if sensor == "imx681" else 0
        residual_ok = new_count == 0 and new_worst == 0.0
        stock_ok = stock_count == expected_stock
        if ok and covers and residual_ok and stock_ok:
            print(f"PASS {sensor}: ceiling accepted, {len(triplets)} normalised triplets, "
                  f"stock clips {stock_count}, derived clips {new_count} "
                  f"(stock worst residual {100 * stock_worst:.0f}%)")
        else:
            print(f"FAIL {sensor}: ceiling not accepted, below the calibrated maximum, or residual "
                  f"(range_ok={ok} covers={covers} stock_clips={stock_count} "
                  f"new_clips={new_count} stock_worst={100 * stock_worst:.1f}%)")
            failures += 1

    # A container without the block must keep stock behaviour, not invent a ceiling.
    class Empty:
        syms = []
    if gen.pick_awb_limits(Empty(), []) is not None:
        print("FAIL: a container without MWBGainV1 produced a ceiling")
        failures += 1
    else:
        print("PASS: no MWBGainV1 block keeps the stock 4.0 ceiling")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
