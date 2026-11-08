"""Keep upstream MIUI logic, omit its preceding AOSP compilation."""
import pathlib

root = pathlib.Path("kernel")
text = (root / "build.sh").read_text()
toolchain_line = "TOOLCHAIN_PATH=$HOME/proton-clang/proton-clang-20210522/bin"
assert text.count(toolchain_line) == 1
text = text.replace(toolchain_line, ': "${TOOLCHAIN_PATH:?Compiler path required}"')
start = text.index("make $MAKE_ARGS -j$(nproc)", text.index('echo "Cleaning..."'))
end = text.index("# ------------- Building for MIUI -------------", start)
text = text[:start] + text[end:]
assert "AOSP Build successfully." not in text
assert text.count("make $MAKE_ARGS -j$(nproc)") == 2  # continue shortcut plus MIUI
assert "-e XIAOMI_MIUI" in text
assert "f4863b20cc8dc0f8cc67418980f022e43014b598" in text
(root / "build-cloud.sh").write_text(text)
