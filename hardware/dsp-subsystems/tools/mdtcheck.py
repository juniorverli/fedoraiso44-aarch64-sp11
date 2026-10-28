#!/usr/bin/env python3
"""Header-only MDT check mirroring drivers/soc/qcom/mdt_loader.c v7.3. Never decodes code."""
import hashlib, struct, sys
QCOM_MDT_TYPE_MASK = 7 << 24
QCOM_MDT_TYPE_HASH = 2 << 24
QCOM_MDT_RELOCATABLE = 1 << 27
PT_LOAD = 1

def check(path, mem_phys, mem_size, dtbmem=False):
    b = open(path, 'rb').read()
    out = {'path': path, 'size': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
    assert b[:4] == b'\x7fELF'
    ei_class, ei_data = b[4], b[5]
    (e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags, e_ehsize,
     e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from('<HHIIIIIHHHHHH', b, 16)
    out.update(ei_class=ei_class, ei_data=ei_data, e_type=e_type, e_machine=e_machine, e_phentsize=e_phentsize,
               e_phnum=e_phnum, e_shnum=e_shnum, e_flags=hex(e_flags))
    ph = []
    for i in range(e_phnum):
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack_from('<IIIIIIII', b, e_phoff + 32 * i)
        ph.append(dict(i=i, t=p_type, off=p_offset, pa=p_paddr, fsz=p_filesz, msz=p_memsz, fl=p_flags))
    out['phdr0_is_load'] = ph[0]['t'] == PT_LOAD
    hash_seg = next((p['i'] for p in ph[1:] if (p['fl'] & QCOM_MDT_TYPE_MASK) == QCOM_MDT_TYPE_HASH), None)
    out['hash_segment'] = hash_seg
    split = False
    for p in ph:
        if p['fsz'] and (p['off'] > len(b) or p['off'] + p['fsz'] > len(b)):
            split = True
    out['split'] = split
    load = [p for p in ph if p['t'] == PT_LOAD and (p['fl'] & QCOM_MDT_TYPE_MASK) != QCOM_MDT_TYPE_HASH and p['msz']]
    out['n_loadable'] = len(load)
    reloc = any(p['fl'] & QCOM_MDT_RELOCATABLE for p in load)
    out['relocatable'] = reloc
    mn = min(p['pa'] for p in load); mx = max(p['pa'] + p['msz'] for p in load)
    out['min_paddr'] = hex(mn); out['max_end'] = hex(mx)
    base = mn if reloc else mem_phys
    ok = True
    for p in load:
        off = p['pa'] - base
        if off < 0 or off + p['msz'] > mem_size: ok = False
        if p['fsz'] > p['msz']: ok = False
        if p['fsz'] and p['off'] + p['fsz'] > len(b): ok = False
    out['fits_region'] = ok
    out['region'] = (hex(mem_phys), hex(mem_size))
    out['image_span'] = hex(((mx + 0xfff) & ~0xfff) - mn)
    # hash segment inside file
    if hash_seg is not None:
        h = ph[hash_seg]; out['hash_in_file'] = h['off'] + h['fsz'] <= len(b)
    return out

if __name__ == '__main__':
    root = sys.argv[1]
    D = root + '/DriverStore/'
    ad = D + 'surfacepro_ext_adsp8380.inf_arm64_3cc952aaca3564ae/'
    cd = D + 'qcnspmcdm_ext_cdsp8380.inf_arm64_4a8c3ebe3aad408a/'
    for r in (check(ad + 'qcadsp8380.mbn', 0x87e00000, 0x3a00000),
              check(ad + 'adsp_dtbs.elf', 0x8b800000, 0x80000),
              check(cd + 'qccdsp8380.mbn', 0x8b900000, 0x2000000),
              check(cd + 'cdsp_dtbs.elf', 0x8d900000, 0x80000)):
        for k, v in r.items(): print(f'  {k}: {v}')
        print()
