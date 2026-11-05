// SPDX-License-Identifier: LGPL-2.1-or-later
// Compile against the header created by the candidate libcamera patch.
#include "sp11_rotate180.h"
#include "sp11_rotation_policy.h"

#include <cassert>
#include <cstddef>
#include <cstdint>
#include <vector>

int main()
{
    using namespace libcamera;
    constexpr const char *rear = "/base/soc@0/cci@ac15000/i2c-bus@1/camera@10";
    constexpr const char *front = "/base/soc@0/cci@ac16000/i2c-bus@1/camera@10";
    assert(sp11IsRearRotationCandidate(rear, "ov13858", true));
    assert(!sp11IsRearRotationCandidate(front, "imx681", true));
    assert(!sp11IsRearRotationCandidate(rear, "ov13858", false));
    assert(!sp11IsRearRotationCandidate(rear, "imx681", true));
    assert(sp11UseRearRotation(true, false, 1, 0, true, true, true));
    assert(!sp11UseRearRotation(false, false, 1, 0, true, true, true));
    assert(!sp11UseRearRotation(true, true, 1, 0, true, true, true));
    assert(!sp11UseRearRotation(true, false, 2, 1, true, true, true));
    assert(!sp11UseRearRotation(true, false, 1, 1, true, true, true));
    assert(!sp11UseRearRotation(true, false, 1, 0, false, true, true));
    assert(!sp11UseRearRotation(true, false, 1, 0, true, false, true));
    assert(!sp11UseRearRotation(true, false, 1, 0, true, true, false));
    for (std::size_t bytes : {3U, 4U}) {
        for (std::size_t height = 1; height <= 7; ++height) {
            for (std::size_t width = 1; width <= 9; ++width) {
                const std::size_t stride = width * bytes + 5;
                std::vector<uint8_t> src(stride * height, 0xee);
                for (std::size_t y = 0; y < height; ++y)
                    for (std::size_t x = 0; x < width; ++x)
                        for (std::size_t c = 0; c < bytes; ++c)
                            src[y * stride + x * bytes + c] = (17 * y + 7 * x + c) % 251;
                auto result = src;
                assert(libcamera::sp11Rotate180(result.data(), result.size(), width, height, stride, bytes));
                for (std::size_t y = 0; y < height; ++y) {
                    for (std::size_t x = 0; x < width; ++x)
                        for (std::size_t c = 0; c < bytes; ++c)
                            assert(result[y * stride + x * bytes + c] ==
                                   src[(height - 1 - y) * stride + (width - 1 - x) * bytes + c]);
                    for (std::size_t p = width * bytes; p < stride; ++p)
                        assert(result[y * stride + p] == 0xee);
                }
                assert(libcamera::sp11Rotate180(result.data(), result.size(), width, height, stride, bytes));
                assert(result == src);
                assert(!libcamera::sp11Rotate180(result.data(), result.size() - 1, width, height, stride, bytes));
                assert(result == src);
            }
        }
    }
    uint8_t data[16]{};
    assert(!libcamera::sp11Rotate180(nullptr, sizeof(data), 1, 1, 4, 4));
    assert(!libcamera::sp11Rotate180(data, sizeof(data), 3, 1, 8, 3));
    assert(!libcamera::sp11Rotate180(data, sizeof(data), 2, 1, 8, 2));
}
