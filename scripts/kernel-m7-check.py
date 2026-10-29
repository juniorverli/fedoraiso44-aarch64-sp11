#!/usr/bin/env python3
"""Check M7 DT wiring, S1, parity and controller-only touch diagnostics.

Run inside the Fedora kernel container. Input is a DTB, not source text.
The JSON is suitable for inclusion in the release/variant build records.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def strings(value):
    return re.findall(r'"([^\"]*)"', value)


def cells(value):
    require(value.startswith('<') and value.endswith('>'), f'Not cells: {value}')
    return [int(v, 0) for v in value[1:-1].split()]


def read_tree(dtb):
    source = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', '-qq', str(dtb)],
                            check=True, capture_output=True, text=True).stdout
    nodes, stack = {}, []
    for line in source.splitlines():
        line = line.strip()
        if line.endswith(' {'):
            name = line[:-2].strip().split(': ')[-1]
            path = '/' if not stack else stack[-1].rstrip('/') + '/' + name
            require(path not in nodes, f'Duplicate DT path: {path}')
            nodes[path] = {}
            stack.append(path)
        elif line == '};':
            stack.pop()
        elif stack and line.endswith(';'):
            key, sep, value = line[:-1].partition(' = ')
            nodes[stack[-1]][key] = value if sep else ''
    require(not stack and '/__symbols__' in nodes, 'Missing DT tree or symbols')
    return source, nodes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dtb', type=Path)
    parser.add_argument('--variant', choices=['packaged', 'm7', 'm7-touchdiag'], required=True)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args()
    source, nodes = read_tree(args.dtb)
    symbols = {k: strings(v)[0] for k, v in nodes['/__symbols__'].items()}

    def node(label):
        require(label in symbols, f'Missing label {label}')
        return nodes[symbols[label]]

    def enabled(path):
        while True:
            if nodes[path].get('status', '"okay"') not in ('"okay"', '"ok"'):
                return False
            if path == '/':
                return True
            path = path.rsplit('/', 1)[0] or '/'

    def phandle(label):
        return cells(node(label)['phandle'])[0]

    # S1 must disable both the card and the speaker bus, not only the codecs.
    require(nodes['/sound'].get('status') == '"disabled"', '/sound is not disabled')
    require(node('swr0').get('status') == '"disabled"', 'swr0 is not disabled')
    watched = [p for p, props in nodes.items() if any(
        w in props.get('compatible', '') for w in ('wsa884', 'sdw20217020400', 'x1e80100-sndcard'))]
    require(len(watched) == 3 and all(not enabled(p) for p in watched), 'S1 effective-status failure')

    tlmm = phandle('tlmm')
    require(node('pcie4')['pinctrl-names'] == '"default"', 'PCIe4 pinctrl names')
    require(cells(node('pcie4')['pinctrl-0']) == [phandle('pcie4_default')], 'PCIe4 pinctrl')
    require(cells(node('pcie4_port0')['reset-gpios']) == [tlmm, 146, 1], 'Wi-Fi PERST#')
    require(cells(node('pcie4_port0')['wake-gpios']) == [tlmm, 148, 1], 'Wi-Fi WAKE#')
    retimers = [p for p, props in nodes.items()
                if '"parade,ps8830"' in props.get('compatible', '')
                and cells(props['reset-gpios']) == [tlmm, 176, 1]]
    require(len(retimers) == 1, 'Missing/ambiguous second USB-C retimer')
    retimer = nodes[retimers[0]]
    require(retimer['pinctrl-names'] == '"default"', 'USB-C pinctrl names')
    require(cells(retimer['pinctrl-0']) == [phandle('rtmr1_default')], 'USB-C reset pinctrl')
    pins = node('rtmr1_default')
    require(strings(pins['pins']) == ['gpio176'] and strings(pins['function']) == ['gpio']
            and cells(pins['drive-strength']) == [2] and 'bias-disable' in pins, 'USB-C reset pad')

    cpus = [p for p, props in nodes.items() if p.startswith('/cpus/')
            and props.get('device_type') == '"cpu"']
    parity = args.variant != 'packaged'
    require(len(cpus) == (10 if parity else 12), 'CPU count')
    if parity:
        require(all(label not in symbols for label in ('cpu7', 'cpu11', 'cpu_pd7', 'cpu_pd11')),
                'Fused-off CPU/PSCI domains retained')
        require('/cpus/cpu-map/cluster1/core3' not in nodes
                and symbols['cpu_map_cluster2'] + '/core3' not in nodes, 'CPU map core3 retained')
        require('domain-idle-states' not in node('system_pd'), 'System SS3 still referenced')
        require(not enabled(symbols['gpu']), 'GPU enabled in M7 device variant')
        # Keep both cluster idle states in the DT.
        require('cluster_cl4' in symbols and 'cluster_cl5' in symbols, 'Cluster idle state removed')

    diag = args.variant == 'm7-touchdiag'
    spi_path = symbols['spi10']
    require(enabled(spi_path) == diag, 'Unexpected SE2 controller status')
    hid = [p for p, props in nodes.items() if enabled(p) and
           (p.startswith(spi_path + '/') or any(
               token in props.get('compatible', '').lower()
               for token in ('hid-over-spi', 'spi-hid', 'mshw0484')))]
    require(not hid, f'Enabled HID/touch children: {hid}')
    touch_supplies = {p for p, props in nodes.items()
                      if 'touch' in p.lower() or 'touch' in props.get('regulator-name', '').lower()}
    touch_handles = {cells(nodes[p]['phandle'])[0] for p in touch_supplies if 'phandle' in nodes[p]}
    consumers = [(p, key) for p, props in nodes.items() if enabled(p)
                 for key, value in props.items() if key.endswith('-supply')
                 and (set(cells(value)) & touch_handles or 'touch' in key.lower())]
    require(not consumers and all(not enabled(p) for p in touch_supplies), 'Touch supply enabled/consumed')
    if diag:
        require('firmware-name' not in node('qupv3_1'), 'QUP wrapper requests firmware')
        require(cells(node('spi10')['pinctrl-0']) ==
                [phandle('qup_spi10_data_clk'), phandle('qup_spi10_cs')], 'SE2 pinctrl changed')
        require(not any(key.endswith('-supply') for key in node('spi10')), 'SE2 supply consumer')

    changes = []
    if args.baseline:
        _, before = read_tree(args.baseline)
        # Phandle numbering is stable for touchdiag: it adds no node. Compare
        # every property, rather than ignoring potentially relevant DT changes.
        for path in sorted(set(nodes) | set(before)):
            a, b = before.get(path), nodes.get(path)
            if a is None or b is None:
                changes.append({'path': path, 'before': a, 'after': b})
                continue
            for key in sorted(set(a) | set(b)):
                if a.get(key) != b.get(key):
                    changes.append({'path': path, 'property': key, 'before': a.get(key), 'after': b.get(key)})
        if diag:
            expected = [{'path': spi_path, 'property': 'status', 'before': '"disabled"', 'after': '"okay"'}]
            require(changes == expected, f'Unexpected touchdiag changes: {changes}')

    print(json.dumps(dict(variant=args.variant, s1_ok=True, watched_count=len(watched),
                          wifi=dict(perst_gpio=146, wake_gpio=148, active_low=True, pinctrl='pcie4_default'),
                          usb_typec=dict(reset_gpio=176, pinctrl='rtmr1_default', drive_strength=2),
                          cpu_count=len(cpus), no_system_ss3=parity,
                          gpu_enabled=enabled(symbols['gpu']),
                          se2_enabled=enabled(spi_path), enabled_hid_children=hid,
                          enabled_touch_supply_consumers=consumers,
                          touch_supply_nodes=sorted(touch_supplies), diff_vs_baseline=changes), indent=2))


if __name__ == '__main__':
    main()
