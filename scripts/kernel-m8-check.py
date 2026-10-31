#!/usr/bin/env python3
"""Check M8/M9 DT wiring, S1, GPU isolation, parity and the QSPI touch path.

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
    parser.add_argument('--variant', choices=['packaged', 'm8', 'm8-notouch', 'm9', 'm9-notouch', 'm10', 'm10-notouch', 'm11', 'm11-notouch', 'm11-audio', 'm12', 'm12-notouch', 'm12-audio',
                                 'm13', 'm13-nosnd', 'm13-notouch', 'm13-spk', 'm13-gpu', 'm13-cam',
                                 'm14', 'm14-safe', 'm14-nosnd', 'm14-notouch', 'm14-spk',
                                 'm15', 'm15-safe', 'm15-nosnd', 'm15-notouch', 'm15-spk'],
                        required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--previous', type=Path, help='M8 DTB: require only the CMA range addition')
    parser.add_argument('--previous-unchanged', action='store_true',
                        help='With --previous (M9 DTB): require no DT difference at all')
    parser.add_argument('--previous-m12', type=Path,
                        help='M12-behaviour DTB: require only disabled camera nodes added (M13 camera patches)')
    parser.add_argument('--cma-dma32', action='store_true', help='Require the M9 DMA32 CMA window')
    parser.add_argument('--volume-keys', action='store_true',
                        help='Require the ec-sam 0005 volume-key nodes (implied for m15 variants)')
    parser.add_argument('--parity-in-base', action='store_true',
                        help='Require integrated LCD parity in the packaged board')
    args = parser.parse_args()
    fallback = args.variant.endswith('-notouch')
    require(not fallback or args.baseline is not None, 'Fallback check requires its baseline DTB')
    source, nodes = read_tree(args.dtb)
    symbols = {k: strings(v)[0] for k, v in nodes['/__symbols__'].items()}

    cma_record = None
    if args.cma_dma32 or args.variant.startswith(('m9', 'm10', 'm11', 'm12', 'm13', 'm14', 'm15')):
        pools = [(p, props) for p, props in nodes.items() if 'linux,cma-default' in props]
        require(len(pools) == 1, 'Missing/ambiguous default CMA pool')
        path, pool = pools[0]
        require(path == '/reserved-memory/linux,cma', 'Unexpected default CMA path')
        require(pool.get('compatible') == '"shared-dma-pool"' and 'reusable' in pool,
                'CMA pool type/reusability changed')
        require(cells(pool['size']) == [0, 0x8000000], 'CMA is not 128 MiB')
        require(cells(pool.get('alloc-ranges', '<>')) == [0, 0x80000000, 0, 0x80000000],
                'CMA allocation window is not 2–4 GiB')
        require('reg' not in pool, 'CMA location must remain dynamically allocated')
        cma_record = dict(path=path, size_bytes=0x8000000, reusable=True,
                          allocation_start=0x80000000, allocation_end_exclusive=0x100000000,
                          dynamic_placement=True)

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

    # The only enabled-card exceptions are the microphone DTs and, under the d26 profile, m13-spk.
    spk = args.variant in ('m13-spk', 'm14-spk', 'm15-spk')
    profile = 'd26' if spk else 'default'
    safety_tool = str(Path(__file__).with_name('kernel-dtb-safety.py'))
    safety = subprocess.run(['python3', '-I', safety_tool, '/dev/stdin', '--profile', profile],
                            input=source, capture_output=True, text=True)
    require(safety.returncode == 0, f'S1 effective-status failure ({profile}): ' + safety.stdout)
    safety_json = json.loads(safety.stdout)
    watched = safety_json['watched']
    if spk:
        # m13-spk must be refused by the default profile, and pass d26 only through the marker.
        denied = subprocess.run(['python3', '-I', safety_tool, '/dev/stdin', '--profile', 'default'],
                                input=source, capture_output=True, text=True)
        require(denied.returncode != 0, 'm13-spk unexpectedly passes the default profile')
        require(safety_json['speaker_marker'] == '"d26-open-loop-v1"' and safety_json['d26_speaker_paths'],
                'm13-spk lacks the d26 marker or speaker paths')
        require(enabled(symbols['swr0']), 'm13-spk: swr0 not enabled')
    else:
        require(len(watched) == 3, 'Unexpected S1 watched-node count')
        require(safety_json['speaker_marker'] is None, 'Speaker policy marker in a non-speaker DTB')
        require(node('swr0').get('status') == '\"disabled\"', 'swr0 is not disabled')
    mic_variants = ('m11-audio', 'm12-audio', 'm13', 'm13-notouch', 'm13-cam', 'm14', 'm14-safe', 'm14-notouch',
                    'm15', 'm15-safe', 'm15-notouch')
    if spk:
        require(enabled('/sound'), 'm13-spk: sound card disabled')
    elif args.variant in mic_variants:
        require(enabled('/sound'), 'Microphone sound card disabled')
        require('/sound/wsa-dai-link' not in nodes, 'WSA playback link retained')
        require(strings(nodes['/sound']['audio-routing']) ==
                ['VA DMIC0', 'vdd-micb', 'VA DMIC1', 'vdd-micb'], 'Non-microphone audio routes')
    else:
        require(nodes['/sound'].get('status') == '\"disabled\"', '/sound is not disabled')

    # M15 (audio-speakers 0017): the sound variants carry the two DisplayPort back-end links and no WSA link outside
    # m15-spk; sound-off variants (nosnd, packaged) carry none. The links add no speaker path.
    dp_links = None
    if args.variant.startswith('m15') and args.variant != 'm15-nosnd':
        dp_links = {}
        for index, (name, port, dai) in enumerate((('dp0-dai-link', 'mdss_dp0', 104), ('dp1-dai-link', 'mdss_dp1', 129))):
            base = '/sound/' + name
            require(base in nodes, f'{args.variant}: missing {name}')
            require(strings(nodes[base]['link-name']) == [f'DP{index} Playback'], f'{name}: link name')
            require(cells(nodes[base + '/codec']['sound-dai']) == [phandle(port)], f'{name}: codec is not {port}')
            require(cells(nodes[base + '/cpu']['sound-dai']) == [phandle('q6apmbedai'), dai],
                    f'{name}: cpu is not DISPLAY_PORT_RX_{index}')
            require(cells(nodes[base + '/platform']['sound-dai']) == [phandle('q6apm')], f'{name}: platform')
            require(enabled(symbols[port]), f'{name}: {port} disabled')
            dp_links[name] = dict(codec=port, cpu_dai=dai)
    elif args.variant in ('m15-nosnd', 'packaged'):
        require(not any(p.startswith('/sound/dp') for p in nodes), 'DP audio links in a sound-off DTB')

    # ec-sam 0005: volume keys on PM8550 GPIO 6 and 8 (packaged board DT, so every M15 DTB carries them).
    volume_keys = None
    if args.volume_keys or args.variant.startswith('m15'):
        require('/volume-keys' in nodes and enabled('/volume-keys'), 'Volume-key node missing or disabled')
        require(strings(nodes['/volume-keys']['compatible']) == ['gpio-keys'], 'Volume-key compatible')
        pm = phandle('pm8550_gpios')
        up, down = nodes['/volume-keys/key-volume-up'], nodes['/volume-keys/key-volume-down']
        require(cells(up['gpios']) == [pm, 6, 1] and cells(up['linux,code']) == [115], 'Volume-up key')
        require(cells(down['gpios']) == [pm, 8, 1] and cells(down['linux,code']) == [114], 'Volume-down key')
        volume_keys = dict(up_gpio=6, down_gpio=8, active_low=True)

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
    parity = args.parity_in_base or args.variant != 'packaged'
    require(len(cpus) == (10 if parity else 12), 'CPU count')
    if parity:
        require(all(label not in symbols for label in ('cpu7', 'cpu11', 'cpu_pd7', 'cpu_pd11')),
                'Fused-off CPU/PSCI domains retained')
        require('/cpus/cpu-map/cluster1/core3' not in nodes
                and symbols['cpu_map_cluster2'] + '/core3' not in nodes, 'CPU map core3 retained')
        require('domain-idle-states' not in node('system_pd'), 'System SS3 still referenced')
        # Keep both cluster idle states in the DT.
        require('cluster_cl4' in symbols and 'cluster_cl5' in symbols, 'Cluster idle state removed')
    if args.variant in ('m13-gpu', 'm14', 'm15'):
        require(enabled(symbols['gpu']), f'{args.variant}: GPU not enabled')
    else:
        require(not enabled(symbols['gpu']), 'GPU enabled in LCD DTB')

    # Rear camera chain (cameras 0003-0005): disabled everywhere except the m13-cam diagnostic.
    camera_labels = ('camss', 'cci0', 'cci0_i2c0', 'cci0_i2c1', 'cci1', 'cci1_i2c0', 'cci1_i2c1')
    camera_paths = [symbols[l] for l in camera_labels if l in symbols]
    camera_paths += [p for p in nodes if p == '/camera-leds' or p.endswith('/regulators-8')]
    # M14 (cameras 0014/0018/0019): pm8550 L7B (front analog) and L16B (actuator) are added disabled.
    camera_paths += [p for p in nodes if p.endswith(('/regulators-0/ldo7', '/regulators-0/ldo16'))
                     and nodes[p].get('regulator-name', '').strip('"') in ('vreg_l7b_2p8', 'vreg_l16b_2p9')]
    camera_present = bool(camera_paths)
    camera_on = [p for p in camera_paths if enabled(p)]
    rear = [p for p in nodes if p.endswith('/camera@10') and 'ovti,ov13858' in nodes[p].get('compatible', '')]
    if args.variant == 'm13-cam':
        require(len(rear) == 1 and enabled(rear[0]), 'm13-cam: rear OV13858 not effectively enabled')
        for label in ('camss', 'cci0', 'cci0_i2c1'):
            require(enabled(symbols[label]), f'm13-cam: {label} disabled')
        require(enabled('/camera-leds'), 'm13-cam: indicator LED bank disabled')
        for label in ('cci1', 'cci0_i2c0', 'cci1_i2c0', 'cci1_i2c1'):
            require(not enabled(symbols[label]), f'm13-cam: {label} must stay disabled')
    elif args.variant in ('m14', 'm15'):
        # Combined diagnostic default: rear, front and IR chains all effectively enabled.
        front = [p for p in nodes if 'sony,imx681' in nodes[p].get('compatible', '')]
        ir = [p for p in nodes if 'st,vd55g0' in nodes[p].get('compatible', '')]
        require(len(rear) == 1 and len(front) == 1 and len(ir) == 1, f'{args.variant}: camera sensor nodes missing')
        for path in rear + front + ir:
            require(enabled(path), f'{args.variant}: {path} not effectively enabled')
        for label in ('camss', 'cci0', 'cci0_i2c0', 'cci0_i2c1', 'cci1', 'cci1_i2c1'):
            require(enabled(symbols[label]), f'{args.variant}: {label} disabled')
        require(enabled('/camera-leds'), f'{args.variant}: indicator LED bank disabled')
        require(not enabled(symbols['cci1_i2c0']), f'{args.variant}: cci1_i2c0 must stay disabled')
    elif args.variant.startswith(('m13', 'm14', 'm15')) or args.variant == 'packaged' and args.previous_m12:
        require(camera_present, 'Camera nodes missing in an M13/M14 DTB')
        require(not camera_on, f'Camera nodes enabled outside the camera diagnostic variants: {camera_on}')
        require(not any(enabled(p) for p in rear), 'Rear camera enabled outside m13-cam')

    spi_path = symbols['spi10']
    spi = node('spi10')
    touch_path = spi_path + '/touchscreen@0'
    require(touch_path in nodes, 'Missing touch child')
    touch = nodes[touch_path]
    active_touch = not fallback
    require(enabled(spi_path), 'SE2 controller disabled')
    require(spi['compatible'] == '"qcom,geni-spi-qspi"', 'SE2 is not the QSPI personality')
    require(enabled(symbols['gpi_dma1']), 'QUP1 GPI disabled')
    require(cells(spi['dmas']) == [phandle('gpi_dma1'), 0, 2, 4,
                                  phandle('gpi_dma1'), 1, 2, 4], 'QSPI GPI selector/channels')
    require(strings(spi['dma-names']) == ['tx', 'rx'], 'QSPI DMA names')
    require('firmware-name' not in spi and 'firmware-name' not in node('qupv3_1'),
            'Touch path requests SE firmware')
    require(cells(spi['pinctrl-0']) == [phandle('qup_spi10_data_clk'),
                                      phandle('qup_spi10_data23'), phandle('qup_spi10_cs')],
            'QSPI pin groups')
    for label, expected in [('qup_spi10_data_clk', ['gpio40', 'gpio41', 'gpio42']),
                            ('qup_spi10_data23', ['gpio49', 'gpio50']),
                            ('qup_spi10_cs', ['gpio43'])]:
        require(strings(node(label)['pins']) == expected
                and strings(node(label)['function']) == ['qup1_se2'], f'QSPI mux {label}')
    require(touch['compatible'] == '"microsoft,mshw0484"', 'Touch compatible')
    require(enabled(touch_path) == active_touch, 'Unexpected touch child status')
    require(cells(touch['reg']) == [0] and cells(touch['spi-max-frequency']) == [40000000],
            'Touch chip select/frequency')
    require(cells(touch['spi-rx-bus-width']) == [4] and cells(touch['spi-tx-bus-width']) == [4],
            'Touch bus lane count')
    require(cells(touch['interrupts-extended']) == [tlmm, 51, 2], 'Touch falling-edge interrupt')
    require(cells(touch['reset-gpios']) == [tlmm, 48, 1], 'Touch active-low reset')
    require(cells(touch['vdd-supply']) == [phandle('vreg_ts')], 'Touch supply')
    require(cells(touch['pinctrl-0']) == [phandle('ts_int_n'), phandle('ts_reset_n')],
            'Touch pinctrl')
    for label, pin in [('ts_int_n', 'gpio51'), ('ts_reset_n', 'gpio48')]:
        require(strings(node(label)['pins']) == [pin]
                and strings(node(label)['function']) == ['gpio']
                and 'bias-disable' in node(label), f'Touch pad {label}')
    supply = node('vreg_ts')
    require(cells(supply['gpio']) == [tlmm, 64, 0] and 'enable-active-high' in supply,
            'Touch power enable')
    require(cells(supply['startup-delay-us']) == [500000], 'Touch cold-power delay')
    require('regulator-always-on' not in supply and 'regulator-boot-on' not in supply,
            'Touch power forced on')
    hid = [p for p, props in nodes.items() if enabled(p) and any(
        token in props.get('compatible', '').lower()
        for token in ('hid-over-spi', 'spi-hid', 'mshw0484'))]
    require(hid == ([touch_path] if active_touch else []), f'Unexpected active touch children: {hid}')
    consumers = [p for p, props in nodes.items() if enabled(p)
                 and any(key.endswith('-supply') and cells(value) == [phandle('vreg_ts')]
                         for key, value in props.items())]
    require(consumers == ([touch_path] if active_touch else []), 'Unexpected touch power consumers')

    changes = []
    if args.baseline:
        _, before = read_tree(args.baseline)
        # Phandle numbering is stable for the fallback: it adds no node. Compare
        # every property, rather than ignoring potentially relevant DT changes.
        for path in sorted(set(nodes) | set(before)):
            a, b = before.get(path), nodes.get(path)
            if a is None or b is None:
                changes.append({'path': path, 'before': a, 'after': b})
                continue
            for key in sorted(set(a) | set(b)):
                if a.get(key) != b.get(key):
                    changes.append({'path': path, 'property': key, 'before': a.get(key), 'after': b.get(key)})
        if fallback:
            expected = [{'path': touch_path, 'property': 'status', 'before': None, 'after': '"disabled"'}]
            require(changes == expected, f'Unexpected fallback changes: {changes}')

    previous_changes = []
    if args.previous:
        _, previous = read_tree(args.previous)
        require(set(previous) == set(nodes), 'DT nodes changed from M8')
        for path in sorted(nodes):
            a, b = previous[path], nodes[path]
            for key in sorted(set(a) | set(b)):
                if a.get(key) != b.get(key):
                    previous_changes.append(dict(path=path, property=key,
                                                 before=a.get(key), after=b.get(key)))
        if args.previous_unchanged:
            require(previous_changes == [], f'Unexpected changes from M9: {previous_changes}')
        else:
            require(previous_changes == [dict(path='/reserved-memory/linux,cma', property='alloc-ranges',
                                             before=None, after='<0x00 0x80000000 0x00 0x80000000>')],
                    f'Unexpected changes from M8: {previous_changes}')

    m12_changes = None
    if args.previous_m12:
        _, before = read_tree(args.previous_m12)

        def phandles(tree):
            return {cells(props['phandle'])[0]: path for path, props in tree.items() if 'phandle' in props}
        pa, pb = phandles(before), phandles(nodes)

        def same(x, y):
            """Equal raw, or phandle references to the same node path (numbering shifts with added nodes)."""
            if x == y:
                return True
            if not (x.startswith('<') and y.startswith('<') and x.endswith('>') and y.endswith('>')):
                return False
            cx, cy = cells(x), cells(y)
            return len(cx) == len(cy) and all(
                i == j or (i in pa and j in pb and pa[i] == pb[j]) for i, j in zip(cx, cy))
        a, b = before, nodes
        removed = sorted(set(a) - set(b))
        added = sorted(set(b) - set(a))
        changed = [dict(path=p, property=k, before=a[p].get(k), after=b[p].get(k))
                   for p in sorted(set(a) & set(b)) for k in sorted(set(a[p]) | set(b[p]))
                   if k != 'phandle' and not same(a[p].get(k, ''), b[p].get(k, ''))
                   or (k != 'phandle' and (k in a[p]) != (k in b[p]))]
        require(not removed, f'Nodes removed relative to M12: {removed}')
        # Every added node must be camera chain or LED, effectively disabled unless this is m13-cam.
        # A changed property is allowed only as an added __symbols__ entry for such a node.
        # (apps_rsc, soc, tlmm and pinctrl gain disabled children only.)
        extra = [c for c in changed if not (c['path'] == '/__symbols__' and c['before'] is None)]
        allowed = ('/volume-keys', '/sound/dp0-dai-link', '/sound/dp1-dai-link', '/camera-leds', '/soc@0/cci@', '/soc@0/isp@', '/soc@0/rsc@17500000/regulators-8',
                   '/soc@0/rsc@17500000/regulators-0/ldo7', '/soc@0/rsc@17500000/regulators-0/ldo16')
        require(not extra, f'Existing nodes changed relative to M12: {extra}')
        require(all(n.startswith(allowed) or ('/pinctrl@f100000/' in n and n.rsplit('/', 1)[-1].startswith(('cam-', 'cci')))
                    or n.rsplit('/', 1)[-1] in ('vol-up-n-state', 'vol-down-n-state')
                    for n in added), f'Nodes added relative to M12 outside the camera chain: {added}')
        m12_changes = dict(added_nodes=added, changed_properties=extra,
                           added_symbols=[c['property'] for c in changed if c not in extra])
    print(json.dumps(dict(variant=args.variant, s1_ok=True, s1_profile=profile,
                          camera_nodes_enabled=camera_on, diff_vs_m12=m12_changes, watched_count=len(watched),
                          wifi=dict(perst_gpio=146, wake_gpio=148, active_low=True, pinctrl='pcie4_default'),
                          usb_typec=dict(reset_gpio=176, pinctrl='rtmr1_default', drive_strength=2),
                          dp_audio_links=dp_links, volume_keys=volume_keys,
                          cpu_count=len(cpus), no_system_ss3=parity,
                          gpu_enabled=enabled(symbols['gpu']),
                          microphone_only=args.variant in mic_variants,
                          se2_enabled=enabled(spi_path), enabled_hid_children=hid,
                          enabled_touch_supply_consumers=consumers,
                          touch_enabled=active_touch, touch_supply_startup_us=500000,
                          qspi_dma_selector=4, no_touch_firmware_request=True,
                          cma_dma32=cma_record,
                          diff_vs_previous=previous_changes,
                          diff_vs_baseline=changes), indent=2))


if __name__ == '__main__':
    main()
