// SPDX-License-Identifier: GPL-2.0-only
// Assisted-by: Claude Sonnet 5.5
//
// Load a libcamera simple-pipeline (Software ISP) tuning file with libcamera's
// own YAML parser and run the same reads the IPA algorithms do in init():
//   BlackLevel: tuningData["blackLevel"].get<int16_t>()
//   Ccm:        Interpolator<Matrix<float,3,3>>::readYaml(tuningData["ccms"], "ct", "ccm")
// It prints only counts and OK/FAIL, never a tuning value (risk S5).
//
// Build (inside the Fedora container with the libcamera 0.7.2 build tree):
//   see validate-tuning.sh

#include <cstdio>
#include <string>

#include <libcamera/base/file.h>

#include "libcamera/internal/matrix.h"
#include "libcamera/internal/value_node.h"
#include "libcamera/internal/yaml_parser.h"

#include "libipa/interpolator.h"

using namespace libcamera;

int main(int argc, char **argv)
{
	int bad = 0;

	for (int i = 1; i < argc; i++) {
		File file(argv[i]);
		if (!file.open(File::OpenModeFlag::ReadOnly)) {
			std::printf("FAIL %s: cannot open\n", argv[i]);
			bad++;
			continue;
		}

		std::unique_ptr<ValueNode> data = YamlParser::parse(file);
		if (!data) {
			std::printf("FAIL %s: YAML parse error\n", argv[i]);
			bad++;
			continue;
		}

		unsigned int version = (*data)["version"].get<uint32_t>(0);
		if (version != 1) {
			std::printf("FAIL %s: version %u\n", argv[i], version);
			bad++;
			continue;
		}

		const ValueNode &algos = (*data)["algorithms"];
		if (!algos.isList()) {
			std::printf("FAIL %s: algorithms is not a list\n", argv[i]);
			bad++;
			continue;
		}

		int nalgo = 0;
		bool ok = true;
		bool hasBlack = false, hasCcm = false;
		unsigned int nccm = 0;

		for (const auto &item : algos.asList()) {
			if (!item.isDictionary()) {
				std::printf("FAIL %s: algorithm entry is not a dictionary\n", argv[i]);
				ok = false;
				break;
			}
			nalgo++;
			std::string name;
			const ValueNode *tdp = nullptr;
			unsigned int keys = 0;
			for (const auto &[k, v] : item.asDict()) {
				name = k;
				tdp = &v;
				keys++;
			}
			if (keys != 1) {
				std::printf("FAIL %s: algorithm entry is not a one-key dictionary\n", argv[i]);
				ok = false;
				break;
			}
			const ValueNode &td = *tdp;

			if (name == "BlackLevel") {
				auto bl = td["blackLevel"].get<int16_t>();
				hasBlack = bl.has_value();
				if (!hasBlack && !td["blackLevel"].isEmpty()) {
					std::printf("FAIL %s: BlackLevel blackLevel unreadable\n", argv[i]);
					ok = false;
				}
			} else if (name == "Ccm") {
				ipa::Interpolator<Matrix<float, 3, 3>> ccm;
				int ret = ccm.readYaml(td["ccms"], "ct", "ccm");
				if (ret < 0) {
					std::printf("FAIL %s: Ccm readYaml %d\n", argv[i], ret);
					ok = false;
				} else {
					hasCcm = true;
					nccm = 0;
					for ([[maybe_unused]] const auto &e : td["ccms"].asList())
						nccm++;
					// exercise the interpolation path over the whole CCT range
					for (unsigned int k = 1500; k <= 12000; k += 500)
						(void)ccm.getInterpolated(k);
				}
			} else if (name != "Awb" && name != "Adjust" && name != "Agc") {
				std::printf("FAIL %s: unknown algorithm %s\n", argv[i], name.c_str());
				ok = false;
			}
		}

		if (ok) {
			std::printf("OK   %s: version 1, %d algorithms, blackLevel=%s, ccm entries=%u\n",
				    argv[i], nalgo, hasBlack ? "yes" : "no", hasCcm ? nccm : 0);
		} else {
			bad++;
		}
	}

	return bad ? 1 : 0;
}
