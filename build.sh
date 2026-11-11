#!/usr/bin/env bash
set -euo pipefail
flavor=${1:-}
case "$flavor" in sukisu|bakasu) ;; *) echo "Usage: bash build.sh sukisu|bakasu" >&2; exit 2 ;; esac
recipe=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${TOOLCHAIN_PATH:?Set TOOLCHAIN_PATH to NDK r26d toolchains/llvm/prebuilt/linux-x86_64/bin}"
export PATH="$TOOLCHAIN_PATH:$PATH"
for program in git python3 clang make ccache curl zip aarch64-linux-gnu-ld arm-linux-gnueabi-ld; do
    command -v "$program" >/dev/null || { echo "Missing dependency: $program" >&2; exit 1; }
done
clang --version | grep -q 'clang version 17.0.2' || {
    echo "Use the documented NDK r26d compiler." >&2; exit 1;
}
work=${BUILD_DIR:-"$recipe/work/$flavor"}
if test -e "$work"; then
    echo "Build directory already exists: $work. Choose a fresh BUILD_DIR; nothing deleted." >&2
    exit 1
fi
mkdir -p -- "$work"
cd -- "$work"
kernel_url=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["kernel"]["repository"])' "$recipe/sources.lock.json")
kernel_commit=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["kernel"]["commit"])' "$recipe/sources.lock.json")
git init kernel
git -C kernel remote add origin "$kernel_url"
git -C kernel fetch --depth=1 origin "$kernel_commit"
git -C kernel checkout --detach FETCH_HEAD
test "$(git -C kernel rev-parse HEAD)" = "$kernel_commit"
python3 "$recipe/scripts/prepare_baseline.py"
if test "$flavor" = bakasu; then
    python3 "$recipe/scripts/integrate_bakasu.py"
else
    python3 "$recipe/scripts/prepare_sukisu.py"
fi
python3 "$recipe/scripts/lock_build_inputs.py" "$flavor"
(
    cd kernel
    bash build-cloud.sh alioth ksu
) 2>&1 | tee build.log
python3 "$recipe/scripts/collect_output.py" "$flavor"
echo "Build finished. See $work/artifacts"
