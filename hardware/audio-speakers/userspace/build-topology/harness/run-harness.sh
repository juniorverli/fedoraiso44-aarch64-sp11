#!/usr/bin/env bash
# Load the Surface Pro 11 topologies through the REAL kernel parser, offline, and check the result.
#
#   run-harness.sh KERNEL_TREE WORK_DIR
#
# KERNEL_TREE  a composed kernel tree: v7.3 + the kernel/series + audio-speakers 0010-0016 (read only)
# WORK_DIR     scratch (hard-link copy of the tree, objects, firmware, logs); private: it holds Windows data
#
# What it does (nothing touches the host: Fedora 44 containers; no device; QEMU TCG):
#  1. hard-link copies KERNEL_TREE and adds src/ as sound/soc/qcom/qdsp6/harness (scratch, never committed);
#  2. builds a tiny arm64 kernel (tinyconfig + ASoC + the harness) with the topologies and the sp11 files
#     as built-in firmware: qcom/x1e80100/h{base,cl,dup,trunc}-tplg.bin, hcl-sp11cl.bin, hcl-sp11cal.bin;
#  3. boots it once per case in qemu-system-aarch64; the harness calls the real audioreach_tplg_init()
#     (ASoC topology core + sound/soc/qcom/qdsp6/topology.c), registers a card, and builds
#     APM_CMD_GRAPH_OPEN for every graph with the real audioreach.c;
#  4. check_tplg_harness.py decodes the packets and checks them.
# Inputs expected in $SP11_PRIVATE_AUDIO (default out/firmware-private/audio): the closed-loop topology,
# the sp11cl file and sp11-ids.m4 written by build-closedloop.sh. A nominal sp11cal is made in WORK_DIR only.
set -euo pipefail
tree=$(readlink -f "${1:?usage: run-harness.sh KERNEL_TREE WORK_DIR}")
work=$(mkdir -p "${2:?}" && readlink -f "$2")
here=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
main=${SP11_MAIN:-$(git -C "$here" rev-parse --git-common-dir | xargs dirname)}
priv=${SP11_PRIVATE_AUDIO:-$main/out/firmware-private/audio}
acdb="$main/sources/windows/DriverStore/surface_acsp8380.inf_arm64_f6524e4db745e12a/REV_0D/acdb_cal_0D.acdb"
card=X1E80100-Microsoft-Surface-Pro-11
fw=$work/fw/qcom/x1e80100
src=$work/src obj=$work/obj
kimg=${KERNEL_BUILD_IMAGE:-sp11-kernel-fc44}

mkdir -p "$fw" "$work/qimg"
[[ -d $src ]] || cp -al "$tree" "$src"
rm -rf "$src/sound/soc/qcom/qdsp6/harness"; mkdir "$src/sound/soc/qcom/qdsp6/harness"
cp "$here/harness/src/"* "$src/sound/soc/qcom/qdsp6/harness/"
grep -q 'qdsp6/harness' "$src/sound/soc/Makefile" || sed -i '$a obj-y += qcom/qdsp6/harness/' "$src/sound/soc/Makefile"

# firmware: public baseline, closed-loop, duplicate-id and truncated negative controls
base=${SP11_PUBLIC_TPLG:?set SP11_PUBLIC_TPLG to the public topology (build-topology.sh output)}
cp "$base" "$fw/hbase-tplg.bin"
cp "$priv/qcom/x1e80100/$card-tplg.bin" "$fw/hcl-tplg.bin"
cp "$priv/qcom/x1e80100/$card-sp11cl.bin" "$fw/hcl-sp11cl.bin"
python3 -I "$here/sp11_closedloop.py" --acdb "$acdb" --out-dir "$work/cal" --nominal-cal >/dev/null
cp "$work/cal/qcom/x1e80100/$card-sp11cal.bin" "$fw/hcl-sp11cal.bin"
head -c 20000 "$fw/hcl-tplg.bin" > "$fw/htrunc-tplg.bin"
sed 's/define(`SP11_VI_IID.*/define(`SP11_VI_IID'"'"', `0x00004027'"'"') dnl/' "$priv/sp11-ids.m4" > "$work/dup-ids.m4"
bash "$here/build-closedloop-topology.sh" "$work/dup-ids.m4" "$work/dup" >/dev/null 2>&1
cp "$work/dup/qcom/x1e80100/$card-tplg.bin" "$fw/hdup-tplg.bin"

cat > "$work/build.sh" <<BUILD
set -e
cd $src && make O=$obj ARCH=arm64 tinyconfig >/dev/null && cd $obj
for o in KUNIT SOUND SND SND_SOC SND_SOC_TOPOLOGY_BUILD PRINTK TTY SERIAL_AMBA_PL011 SERIAL_AMBA_PL011_CONSOLE \\
         SERIAL_EARLYCON BLK_DEV_INITRD KALLSYMS DEBUG_KERNEL DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT FW_LOADER; do
  $src/scripts/config --file .config --enable \$o; done
$src/scripts/config --file .config --disable FW_LOADER_USER_HELPER \\
  --set-str EXTRA_FIRMWARE "qcom/x1e80100/hbase-tplg.bin qcom/x1e80100/hcl-tplg.bin qcom/x1e80100/hcl-sp11cl.bin qcom/x1e80100/hcl-sp11cal.bin qcom/x1e80100/hdup-tplg.bin qcom/x1e80100/htrunc-tplg.bin" \\
  --set-str EXTRA_FIRMWARE_DIR "$work/fw"
make -C $src O=$obj ARCH=arm64 olddefconfig >/dev/null
make -C $src O=$obj ARCH=arm64 -j\${JOBS:-3} Image 2>&1 | tail -3
BUILD
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp/home --tmpfs /tmp/home:exec,mode=1777 \
  -v /etc/passwd:/etc/passwd:ro -v /etc/group:/etc/group:ro -v "$work":"$work" -v "$tree":"$tree":ro "$kimg" bash "$work/build.sh"

printf 'FROM registry.fedoraproject.org/fedora:44\nRUN dnf -q -y install qemu-system-aarch64-core && dnf clean all\n' > "$work/qimg/Dockerfile"
docker build -q -t sp11-qemu-tplg "$work/qimg" >/dev/null
for c in hbase hcl hdup htrunc; do
  docker run --rm -v "$obj/arch/arm64/boot":/b:ro -v "$work":/l sp11-qemu-tplg bash -c \
    "timeout 300 qemu-system-aarch64 -machine virt -cpu max -m 512 -display none -monitor none -no-reboot \
     -chardev file,id=c,path=/l/q-$c.log -serial chardev:c -kernel /b/Image \
     -append 'console=ttyAMA0 earlycon panic=-1 harness_case=$c' < /dev/null"
done
python3 -I "$here/harness/check_tplg_harness.py" --log-dir "$work" --ids "$priv/sp11-ids.m4"
