"""Repack an alioth boot image through ADB; never reboot, root or flash a phone.

Requires Python 3.10+, adb, an alioth running Android, a matching stock boot,
and this project's AnyKernel ZIP. magiskboot runs in an isolated phone directory.
Tool reference: https://topjohnwu.github.io/Magisk/tools.html
"""
import argparse
from datetime import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

MAX_BOOT = 192 * 1024 * 1024
MAX_RAMDISK = 256 * 1024 * 1024
MAGISKBOOT_SHA256 = "4b202ebb26d1201cc55cafcac0fd4b503ada7e1b60513a7331ba4591e5c2cfbc"
KNOWN_KERNELS = {
    "3278b566ce2a926bad351dd89c6ad8016a1462e5a64e65570219994cb13f7d39": "sukisu",
    "787bb64497e22b4cd2ced406cec053de32c7d4ac64f6e6486b0a2a6c5c6f651d": "bakasu",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_boot(path):
    path = Path(path)
    require(path.is_file(), f"Missing boot image: {path}")
    require(4096 < path.stat().st_size <= MAX_BOOT, "Unexpected boot image size.")
    data = path.read_bytes()
    require(data[:8] == b"ANDROID!", "Expected boot.img, not a ZIP, vendor_boot or another partition.")
    require(struct.unpack_from("<I", data, 40)[0] == 3,
            "Only the tested Android boot header v3 layout is supported.")
    require(struct.unpack_from("<I", data, 20)[0] == 1580, "Unexpected boot v3 header size.")
    kernel_size, ramdisk_size = struct.unpack_from("<II", data, 8)
    require(kernel_size > 60 and ramdisk_size > 0, "Expected a boot image with kernel and ramdisk.")
    ramdisk_offset = 4096 + ((kernel_size + 4095) // 4096) * 4096
    require(ramdisk_offset + ramdisk_size <= len(data) - 64, "Truncated boot components.")
    kernel = data[4096:4096 + kernel_size]
    require(kernel[56:60] == b"ARM\x64",
            "Only the tested uncompressed ARM64 kernel layout is supported.")
    packed_ramdisk = data[ramdisk_offset:ramdisk_offset + ramdisk_size]
    require(packed_ramdisk[:2] == b"\x1f\x8b", "Only the tested gzip ramdisk format is supported.")
    with gzip.GzipFile(fileobj=io.BytesIO(packed_ramdisk)) as stream:
        ramdisk = stream.read(MAX_RAMDISK + 1)
    require(len(ramdisk) <= MAX_RAMDISK, "Ramdisk exceeds the supported limit.")
    require(ramdisk.startswith((b"070701", b"070702")), "Expected a cpio ramdisk.")
    magic, major, minor, original_size, vbmeta_offset, vbmeta_size = struct.unpack_from(
        ">4sIIQQQ", data, len(data) - 64)
    require(magic == b"AVBf", "Expected the tested AVB-footer layout.")
    require(major == 1 and minor == 0, "Unexpected AVB footer version.")
    require(ramdisk_offset + ramdisk_size <= original_size <= vbmeta_offset,
            "Unexpected AVB/component boundaries.")
    require(256 <= vbmeta_size <= 1024 * 1024 and vbmeta_offset + vbmeta_size <= len(data) - 64,
            "Invalid AVB metadata bounds.")
    vbmeta = data[vbmeta_offset:vbmeta_offset + vbmeta_size]
    require(vbmeta[:4] == b"AVB0", "Invalid vbmeta header.")
    return {
        "data": data, "kernel": kernel, "ramdisk": ramdisk, "vbmeta": vbmeta,
        "avb_flags": struct.unpack_from(">I", vbmeta, 120)[0],
    }


def load_bundle(path, variant=None, allow_custom=False):
    path = Path(path)
    require(path.is_file(), f"Missing kernel ZIP: {path}")
    require(path.stat().st_size <= MAX_BOOT, "Unexpected ZIP size.")
    with zipfile.ZipFile(path) as archive:
        def get(name, limit):
            entries = [item for item in archive.infolist() if item.filename == name]
            require(len(entries) == 1, f"Expected exactly one {name} in the ZIP.")
            item = entries[0]
            require(0 < item.file_size <= limit and not item.flag_bits & 1,
                    f"Unexpected or encrypted ZIP entry: {name}")
            # Read only explicitly named entries; never extract arbitrary ZIP paths.
            return archive.read(item)
        kernel = get("kernels/Image", 96 * 1024 * 1024)
        tool = get("tools/magiskboot", 16 * 1024 * 1024)
    require(len(kernel) > 60 and kernel[56:60] == b"ARM\x64", "ZIP kernel is not an ARM64 Image.")
    require(sha(tool) == MAGISKBOOT_SHA256,
            "Unrecognized magiskboot. Use this project's pinned AnyKernel packaging.")
    known = KNOWN_KERNELS.get(sha(kernel))
    if known:
        require(variant is None or variant == known, "Selected variant does not match the kernel.")
        variant = known
    else:
        require(allow_custom and variant in ("sukisu", "bakasu"),
                "Unlisted kernel. For your own rebuild, specify --allow-custom-kernel "
                "and --variant sukisu|bakasu after checking its build manifest.")
    return {"kernel": kernel, "tool": tool, "variant": variant, "known_release_kernel": bool(known)}


def verify_repacked(before, after, bundle):
    require(len(before["data"]) == len(after["data"]), "Repacked image size changed.")
    require(before["data"][:8] == after["data"][:8] and
            before["data"][16:4096] == after["data"][16:4096],
            "Boot header or header-page padding changed beyond component sizes.")
    require(after["kernel"] == bundle["kernel"], "Repacked kernel does not match the selected ZIP.")
    require(before["ramdisk"] == after["ramdisk"], "Ramdisk contents changed.")
    require(before["vbmeta"] == after["vbmeta"] and before["avb_flags"] == after["avb_flags"],
            "vbmeta contents or flags changed.")
    return {
        "variant": bundle["variant"],
        "known_release_kernel": bundle["known_release_kernel"],
        "boot_header_version": 3,
        "stock_boot_sha256": sha(before["data"]),
        "output_boot_sha256": sha(after["data"]),
        "output_bytes": len(after["data"]),
        "kernel_sha256": sha(after["kernel"]),
        "ramdisk_uncompressed_sha256": sha(after["ramdisk"]),
        "magiskboot_sha256": sha(bundle["tool"]),
        "ramdisk_unchanged": True,
        "header_unchanged_except_sizes": True,
        "vbmeta_unchanged": True,
        "patchvbmetaflag": False,
        "avb_signature_verified": False,
        "hardware_tested": False,
        "flashed": False,
        "note": "Structural validation only. Retaining old vbmeta is not a valid signature "
                "for changed content. An unlocked bootloader and separate boot testing are required.",
    }


class Adb:
    def __init__(self, serial=None):
        self.executable = shutil.which("adb")
        require(self.executable is not None, "adb not found. Install Android Platform Tools and add it to PATH.")
        self.serial = serial
        self.log = []

    def run(self, args, timeout=120, check=True):
        command = [self.executable]
        if self.serial:
            command += ["-s", self.serial]
        command += args
        result = subprocess.run(command, capture_output=True, timeout=timeout)
        text = (result.stdout + result.stderr).decode("utf-8", errors="replace")
        # Transfer/device-list output contains private paths or serials.
        label = args[0] if args else "adb"
        logged_text = text if label == "shell" else "[output omitted]"
        self.log.append(f"{label}: exit={result.returncode}\n{logged_text}")
        if check and result.returncode:
            raise RuntimeError(f"adb {label} failed ({result.returncode}): {text.strip()}")
        return result.returncode, text

    def shell(self, text, **kwargs):
        return self.run(["shell", text], **kwargs)

    def select_device(self):
        if not self.serial:
            _, text = self.run(["devices"])
            devices = []
            for line in text.splitlines():
                fields = line.split()
                if len(fields) == 2 and fields[1] == "device":
                    devices.append(fields[0])
            require(len(devices) == 1,
                    "Connect and authorize exactly one Android device, or pass --serial SERIAL.")
            self.serial = devices[0]
        require(re.fullmatch(r"[A-Za-z0-9._:-]+", self.serial) is not None, "Invalid ADB serial.")
        _, product = self.shell("getprop ro.product.device")
        require(product.strip() == "alioth", f"Expected alioth; connected device reports {product.strip()!r}.")
        _, abis = self.shell("getprop ro.product.cpu.abilist")
        # The pinned AnyKernel magiskboot is a 32-bit ARM executable.
        require("armeabi-v7a" in abis.strip().split(","),
                "The pinned magiskboot needs 32-bit ARM userspace support on the phone.")
        _, rom = self.shell("getprop ro.build.version.incremental")
        print("Connected alioth ROM:", rom.strip())
        print("Your input boot.img must come from this exact installed ROM.")


def prepare_on_phone(adb, before, bundle, stage):
    token = secrets.token_hex(16)
    remote = "/data/local/tmp/alioth-boot-repack-" + token
    require(re.fullmatch(r"/data/local/tmp/alioth-boot-repack-[0-9a-f]{32}", remote) is not None,
            "Unexpected staging path.")
    stock = stage / "original.img"
    kernel = stage / "kernel-new"
    tool = stage / "magiskboot"
    stock.write_bytes(before["data"])
    kernel.write_bytes(bundle["kernel"])
    tool.write_bytes(bundle["tool"])
    # This directory is the only phone location the script writes.
    adb.shell(f"mkdir {remote} && printf {token} > {remote}/.owner")
    try:
        for local, name in [(stock, "original.img"), (kernel, "kernel-new"), (tool, "magiskboot")]:
            adb.run(["push", str(local), remote + "/" + name])
        adb.shell(f"chmod 0755 {remote}/magiskboot")
        adb.shell(f"cd {remote} && ./magiskboot unpack original.img")
        code, _ = adb.shell(f"cd {remote} && ./magiskboot cpio ramdisk.cpio test", check=False)
        require(code == 0, "Ramdisk is patched or unsupported; use a clean boot from your current ROM.")
        adb.shell(f"cd {remote} && cp kernel-new kernel && "
                  "PATCHVBMETAFLAG=false ./magiskboot repack original.img repacked.img")
        candidate = stage / "repacked.img"
        adb.run(["pull", remote + "/repacked.img", str(candidate)])
        return candidate
    finally:
        # Never remove a parent or an unowned directory; do not touch /data/adb.
        try:
            code, _ = adb.shell(f'test "$(cat {remote}/.owner)" = {token} && rm -rf {remote}',
                                timeout=30, check=False)
            if code:
                print("Temporary phone files were retained at:", remote, file=sys.stderr)
        except (OSError, subprocess.SubprocessError):
            print("Unable to clean temporary phone directory:", remote, file=sys.stderr)


def main(argv=None):
    require(sys.version_info >= (3, 10), "Python 3.10 or newer is required.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boot", required=True, type=Path, help="Unmodified boot.img from your installed ROM")
    parser.add_argument("--kernel-zip", required=True, type=Path, help="This project's AnyKernel ZIP")
    parser.add_argument("--output", type=Path, help="New output image path; existing files are never overwritten")
    parser.add_argument("--serial", help="ADB serial if more than one Android device is connected")
    parser.add_argument("--variant", choices=["sukisu", "bakasu"], help="For your own rebuilt kernel")
    parser.add_argument("--allow-custom-kernel", action="store_true", help="Accept an unlisted kernel hash")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--make", action="store_true", help="Make an image using the connected alioth")
    mode.add_argument("--check-only", action="store_true", help="Check local inputs only; no ADB")
    mode.add_argument("--verify", type=Path, help="Verify an existing repacked boot; no ADB")
    args = parser.parse_args(argv)
    before = read_boot(args.boot)
    bundle = load_bundle(args.kernel_zip, args.variant, args.allow_custom_kernel)
    print("Kernel:", bundle["variant"], sha(bundle["kernel"]))
    if args.check_only or not (args.make or args.verify):
        print("Local inputs passed. No phone was accessed; no image was made.")
        return 0
    if args.verify:
        report = verify_repacked(before, read_boot(args.verify), bundle)
        print(json.dumps(report, indent=2))
        return 0
    output = (args.output or Path("output") /
              f"boot-{bundle['variant']}-{datetime.now():%Y%m%d-%H%M%S-%f}.img").resolve()
    report_file = output.with_suffix(output.suffix + ".json")
    log_file = output.with_suffix(output.suffix + ".log")
    for path in [output, report_file, log_file]:
        require(not path.exists(), f"Refusing to overwrite: {path}")
    require(output != args.boot.resolve(), "Output must not replace the original boot.")
    adb = Adb(args.serial)
    adb.select_device()
    with tempfile.TemporaryDirectory(prefix="alioth-boot-repack-") as folder:
        stage = Path(folder)
        candidate = prepare_on_phone(adb, before, bundle, stage)
        report = verify_repacked(before, read_boot(candidate), bundle)
        # No success output is created unless all structural checks pass.
        output.parent.mkdir(parents=True, exist_ok=True)
        with candidate.open("rb") as source, output.open("xb") as destination:
            shutil.copyfileobj(source, destination)
        with report_file.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        with log_file.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write("\n".join(adb.log))
    print("Created:", output)
    print("SHA256:", report["output_boot_sha256"])
    print("Report:", report_file)
    print("No reboot, Root configuration change or partition flash was performed.")
    print("Read docs/BOOT.zh-CN.md or docs/BOOT.md before any boot/flash command.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError, zipfile.BadZipFile,
            EOFError, struct.error) as error:
        print("Stopped:", error, file=sys.stderr)
        sys.exit(1)
