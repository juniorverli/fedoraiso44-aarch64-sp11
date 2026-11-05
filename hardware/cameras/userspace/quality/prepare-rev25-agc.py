#!/usr/bin/env python3
"""Create private, per-sensor 2.5/3.5 SoftISP AGC A/B tuning directories.

Use the existing operator-private imx681.yaml; no sensor values are embedded
in this program. The paired outputs must stay under out/firmware-private/cameras.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path


MARKER = "  - Agc:\n"


def experiment(source):
    """Keep every baseline byte and add only the target to an empty Agc node."""
    if "\r" in source or source.count(MARKER) != 1:
        raise ValueError("expected exactly one LF-terminated, empty Agc node")
    _, tail = source.split(MARKER, 1)
    for line in tail.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") or line.strip() == "...":
            break
        raise ValueError("Agc already has configuration; refusing to overwrite it")
    return source.replace(MARKER, MARKER + "      exposureTarget: 3.5\n", 1)


def private_path(path, private_root):
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(private_root)
    except ValueError as exc:
        raise ValueError(f"path is outside private camera staging: {resolved}") from exc
    return resolved


def main():
    repo = Path(__file__).resolve().parents[4]
    private_root = (repo / "out/firmware-private/cameras").resolve()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=private_root / "libcamera/imx681.yaml")
    parser.add_argument("--output-dir", required=True,
                        help="new directory under out/firmware-private/cameras")
    args = parser.parse_args()

    baseline = private_path(args.baseline, private_root)
    output = private_path(args.output_dir, private_root)
    if output == private_root or output.exists():
        parser.error("output directory must be new and below the private camera staging root")
    try:
        source = baseline.read_bytes().decode("utf-8")
        candidate = experiment(source)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))

    os.umask(0o077)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    hashes = {}
    for variant, text in (("imx681-rev25-agc-2.5", source),
                          ("imx681-rev25-agc-3.5", candidate)):
        directory = output / variant / "simple"
        directory.mkdir(mode=0o700, parents=True)
        data = text.encode("utf-8")
        with (directory / "imx681.yaml").open("xb") as dest:
            dest.write(data)
        hashes[variant] = hashlib.sha256(data).hexdigest()
    manifest = {"private": True, "baseline_sha256": hashes["imx681-rev25-agc-2.5"],
                "outputs_sha256": hashes, "difference": "front Agc exposureTarget: 3.5"}
    with (output / "manifest.json").open("x", encoding="utf-8") as dest:
        json.dump(manifest, dest, indent=2)
        dest.write("\n")
    print(f"Private variants created at {output}; hashes in manifest.json")


if __name__ == "__main__":
    main()
