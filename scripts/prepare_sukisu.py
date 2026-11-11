"""Integrate the exact SukiSU revision, without executing a remote setup pipe."""
import json
from pathlib import Path
import subprocess

locks = json.loads((Path(__file__).resolve().parents[1] / "sources.lock.json").read_text(encoding="utf-8"))
kernel = Path("kernel")
root = kernel / "KernelSU"
assert not root.exists(), "Fresh kernel checkout required"
source = locks["sukisu"]
subprocess.run(["git", "clone", "--no-checkout", source["repository"], str(root)], check=True)
subprocess.run(["git", "-C", str(root), "checkout", "--detach", source["commit"]], check=True)
actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
assert actual == source["commit"]
link = kernel / "drivers/kernelsu"
assert not link.exists() and not link.is_symlink()
link.symlink_to("../KernelSU/kernel", target_is_directory=True)
makefile = kernel / "drivers/Makefile"
if "obj-$(CONFIG_KSU) += kernelsu/" not in makefile.read_text(encoding="utf-8"):
    with makefile.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write("\nobj-$(CONFIG_KSU) += kernelsu/\n")
kconfig = kernel / "drivers/Kconfig"
if 'source "drivers/kernelsu/Kconfig"' not in kconfig.read_text(encoding="utf-8"):
    text = kconfig.read_text(encoding="utf-8")
    assert text.count("endmenu") == 1
    kconfig.write_text(text.replace("endmenu", 'source "drivers/kernelsu/Kconfig"\nendmenu'), encoding="utf-8", newline="\n")
build = kernel / "build-cloud.sh"
text = build.read_text(encoding="utf-8")
lines = [line for line in text.splitlines() if "curl -LSs" in line and "liyafe1997/SukiSU-Ultra" in line]
assert len(lines) == 1
text = text.replace(lines[0], '    echo "Using externally pinned SukiSU checkout"')
build.write_text(text, encoding="utf-8", newline="\n")
print("Pinned SukiSU integration prepared.")
