#!/usr/bin/env python3
"""Check global ordering and reject a later 5% override."""
import importlib.util
from pathlib import Path
import sys
import tempfile

repo = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('payload', repo / 'image/tools/check-m11-payload.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(prefix='sp11-global-safety-') as tmp:
    root = Path(tmp)
    source = repo / 'hardware/audio-speakers/userspace/overlay/usr/share/wireplumber/wireplumber.conf.d/51-sp11-audio-safety.conf'
    (root / source.name).write_bytes(source.read_bytes())
    source = repo / 'image/overlay/usr/share/wireplumber/wireplumber.conf.d/55-sp11-global-safety.conf'
    (root / source.name).write_bytes(source.read_bytes())
    module.check_global_safety(root)
    (root / '60-unsafe.conf').write_text('wireplumber.settings = { device.routes.default-sink-volume = 0.05 }\n')
    try:
        module.check_global_safety(root)
    except AssertionError:
        pass
    else:
        raise AssertionError('later 0.05 fallback was accepted')
print('global audio fail-safe ordering fixture passed')
