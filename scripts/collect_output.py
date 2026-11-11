"""Export public build output only; no device state or personal paths."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

flavor = sys.argv[1]
assert flavor in ("sukisu", "bakasu")
repo = Path(__file__).resolve().parents[1]
locks = json.loads((repo / "sources.lock.json").read_text())
kernel = Path("kernel")
bundles = list(kernel.glob("Kernel_MIUI_alioth_*.zip"))
assert len(bundles) == 1, f"Expected one output, found {len(bundles)}"
config = (kernel / "out/.config").read_text()
for option in ["CONFIG_ARM64=y", "CONFIG_MACH_XIAOMI_ALIOTH=y", "CONFIG_XIAOMI_MIUI=y",
               "CONFIG_KSU=y", "CONFIG_KSU_MANUAL_HOOK=y"]:
    assert option in config.splitlines(), option
if flavor == "bakasu":
    for option in ["CONFIG_KSU_SUSFS=y", "CONFIG_KPM=y", "CONFIG_KSU_TRACEPOINT_HOOK=y"]:
        assert option not in config.splitlines(), option
out = Path("artifacts")
out.mkdir(exist_ok=False)
shutil.copyfile(bundles[0], out / bundles[0].name)
shutil.copyfile(kernel / "out/.config", out / "kernel.config")
if Path("bakasu-integration.patch").exists():
    shutil.copyfile("bakasu-integration.patch", out / "bakasu-integration.patch")
shutil.copyfile(repo / "sources.lock.json", out / "sources.lock.json")
def revision(path):
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
actual = {name: revision(path) for name, path in [
    ("kernel", kernel), (flavor, kernel / "KernelSU"), ("anykernel", kernel / "anykernel")]}
for name, value in actual.items():
    assert value == locks[name]["commit"], (name, value)
manifest = {"flavor": flavor, "commits": actual, "images": {},
            "compiler": subprocess.check_output(["clang", "--version"], text=True),
            "hardware_tested": False}
with zipfile.ZipFile(bundles[0]) as archive:
    assert archive.testzip() is None
    for name in ("kernels/Image", "kernels/dtb"):
        data = archive.read(name)
        if name.endswith("/Image"):
            assert data[56:60] == b"ARM\x64", "Not an ARM64 Image"
        manifest["images"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
(out / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
# Capture all actual source/configuration changes, including the offline version stamp.
for name, path in [("kernel", kernel), (flavor, kernel / "KernelSU")]:
    diff = subprocess.check_output(["git", "-C", str(path), "diff", "--binary", "HEAD"])
    (out / f"{name}-source-changes.patch").write_bytes(diff)
lines = []
for path in sorted(out.iterdir()):
    if path.is_file():
        lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name)
(out / "SHA256SUMS").write_text("\n".join(lines) + "\n")
print("Exported:", out.resolve())
