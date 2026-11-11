"""Freeze packaging input and version labels after the tested integration steps."""
import json
from pathlib import Path
import sys

flavor = sys.argv[1]
assert flavor in ("sukisu", "bakasu")
locks = json.loads((Path(__file__).resolve().parents[1] / "sources.lock.json").read_text(encoding="utf-8"))
kernel = Path("kernel")
build = kernel / "build-cloud.sh"
text = build.read_text(encoding="utf-8")
old = "git clone https://github.com/liyafe1997/AnyKernel3 -b kona --single-branch --depth=1 anykernel"
assert text.count(old) == 1
source = locks["anykernel"]
text = text.replace(old, f"""git init anykernel
git -C anykernel remote add origin {source["repository"]}
git -C anykernel fetch --depth=1 origin {source["commit"]}
git -C anykernel checkout --detach FETCH_HEAD
test "$(git -C anykernel rev-parse HEAD)" = "{source["commit"]}"
""".rstrip())
if flavor == "sukisu":
    old = "    wget " + locks["kpm"]["url"]
    assert text.count(old) == 1
    text = text.replace(old, f"""    curl -fL --retry 3 {locks["kpm"]["url"]} -o patch_linux
    echo "{locks["kpm"]["sha256"]}  patch_linux" | sha256sum --check --status""")
    # Upstream queried the current release name and commit count while compiling.
    # Freeze source API naming; this is not an upgrade to a newer SukiSU driver.
    root_makefile = kernel / "KernelSU/kernel/Makefile"
    root_text = root_makefile.read_text(encoding="utf-8")
    start = root_text.index("KSU_GITHUB_VERSION :=")
    end = root_text.index("ccflags-y += -DKSU_VERSION=", start)
    root_text = root_text[:start] + f"""# Fixed source metadata for this build recipe.
KSU_VERSION := {locks["sukisu"]["version_code"]}
KSU_VERSION_FULL := v3.1.7-f4863b20@pinned

""" + root_text[end:]
    root_makefile.write_text(root_text, encoding="utf-8", newline="\n")
else:
    assert locks["kpm"]["url"] not in text
build.write_text(text, encoding="utf-8", newline="\n")
print("Packaging revision and external patch checksum locked.")
