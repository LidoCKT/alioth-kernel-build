"""Offline tests; no phone, adb, network or proprietary ROM fixtures required."""
import contextlib
import gzip
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SPEC = importlib.util.spec_from_file_location(
    "make_boot", Path(__file__).resolve().parents[1] / "scripts/make_boot.py")
boot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boot)


def kernel(marker):
    result = bytearray(200)
    result[0] = marker
    result[56:60] = b"ARM\x64"
    return bytes(result)


def image(selected, ramdisk=b"070701fixture", flags=0):
    data = bytearray(32768)
    data[:8] = b"ANDROID!"
    packed = gzip.compress(ramdisk, mtime=0)
    struct.pack_into("<IIIII", data, 8, len(selected), len(packed), 0, 1580, 0)
    struct.pack_into("<I", data, 40, 3)
    data[4096:4096 + len(selected)] = selected
    data[8192:8192 + len(packed)] = packed
    data[16384:16388] = b"AVB0"
    struct.pack_into(">I", data, 16384 + 120, flags)
    struct.pack_into(">4sIIQQQ", data, len(data) - 64, b"AVBf", 1, 0, 12288, 16384, 256)
    return bytes(data)


class BootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.stock = self.base / "stock.img"
        self.stock.write_bytes(image(kernel(1)))
        self.candidate = self.base / "candidate.img"
        self.candidate.write_bytes(image(kernel(2)))
        self.tool = b"fixture-tool"
        self.bundle = {"kernel": kernel(2), "tool": self.tool,
                       "variant": "bakasu", "known_release_kernel": False}
        self.archive = self.base / "kernel.zip"
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("kernels/Image", kernel(2))
            archive.writestr("tools/magiskboot", self.tool)
        self.tool_patch = patch.object(boot, "MAGISKBOOT_SHA256", boot.sha(self.tool))
        self.tool_patch.start()
        self.addCleanup(self.tool_patch.stop)

    def arguments(self):
        return ["--boot", str(self.stock), "--kernel-zip", str(self.archive),
                "--allow-custom-kernel", "--variant", "bakasu"]

    def test_valid_and_corrupted_candidates(self):
        before = boot.read_boot(self.stock)
        result = boot.verify_repacked(before, boot.read_boot(self.candidate), self.bundle)
        self.assertFalse(result["hardware_tested"])
        variants = [image(kernel(3)), image(kernel(2), b"070701changed"),
                    image(kernel(2), flags=2)]
        header_change = bytearray(image(kernel(2)))
        header_change[100] = 1
        variants.append(header_change)
        for data in variants:
            with self.subTest(data_hash=boot.sha(data)):
                self.candidate.write_bytes(data)
                with self.assertRaises(ValueError):
                    boot.verify_repacked(before, boot.read_boot(self.candidate), self.bundle)

    def test_unsupported_or_truncated_input(self):
        data = bytearray(self.stock.read_bytes())
        struct.pack_into("<I", data, 40, 4)
        self.candidate.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "header v3"):
            boot.read_boot(self.candidate)
        self.candidate.write_bytes(self.stock.read_bytes()[:9000])
        with self.assertRaises(ValueError):
            boot.read_boot(self.candidate)

    def test_bundle_requires_explicit_custom_and_pinned_tool(self):
        with self.assertRaisesRegex(ValueError, "Unlisted"):
            boot.load_bundle(self.archive)
        with patch.object(boot, "MAGISKBOOT_SHA256", "wrong"):
            with self.assertRaisesRegex(ValueError, "Unrecognized magiskboot"):
                boot.load_bundle(self.archive, "bakasu", True)
        with zipfile.ZipFile(self.archive, "a") as archive:
            with self.assertWarns(UserWarning):
                archive.writestr("kernels/Image", kernel(2))
        with self.assertRaisesRegex(ValueError, "exactly one"):
            boot.load_bundle(self.archive, "bakasu", True)

    def test_offline_modes_never_construct_adb(self):
        with patch.object(boot, "Adb", side_effect=AssertionError("ADB accessed")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(boot.main(self.arguments() + ["--check-only"]), 0)
            self.assertEqual(boot.main(self.arguments()), 0)
            self.assertEqual(boot.main(self.arguments() + ["--verify", str(self.candidate)]), 0)

    def test_existing_output_refused_before_adb(self):
        with patch.object(boot, "Adb", side_effect=AssertionError("ADB accessed")), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "overwrite"):
                boot.main(self.arguments() + ["--make", "--output", str(self.candidate)])

    def fake_adb(self, stock_status=0, corrupt=False):
        calls = []
        candidate = image(kernel(3) if corrupt else kernel(2))

        class FakeAdb:
            def __init__(self, serial=None):
                self.log = []

            def select_device(self):
                calls.append("select")

            def shell(self, command, **kwargs):
                calls.append(command)
                if "cpio ramdisk.cpio test" in command:
                    return stock_status, ""
                return 0, ""

            def run(self, args, **kwargs):
                calls.append(args)
                if args[0] == "pull":
                    Path(args[-1]).write_bytes(candidate)
                return 0, ""

        return FakeAdb, calls

    def test_pipeline_and_owned_cleanup(self):
        fake, calls = self.fake_adb()
        output = self.base / "output.img"
        with patch.object(boot, "Adb", fake), contextlib.redirect_stdout(io.StringIO()):
            boot.main(self.arguments() + ["--make", "--output", str(output)])
        self.assertEqual(output.read_bytes(), self.candidate.read_bytes())
        self.assertEqual(self.stock.read_bytes(), image(kernel(1)))
        shell = [item for item in calls if isinstance(item, str)]
        check = next(i for i, item in enumerate(shell) if "cpio ramdisk.cpio test" in item)
        repack = next(i for i, item in enumerate(shell) if "repack original.img repacked.img" in item)
        self.assertLess(check, repack)
        self.assertIn("PATCHVBMETAFLAG=false", shell[repack])
        self.assertRegex(shell[-1], r'^test "\$\(cat /data/local/tmp/alioth-boot-repack-[0-9a-f]{32}/.owner\)" = [0-9a-f]{32} && rm -rf /data/local/tmp/alioth-boot-repack-[0-9a-f]{32}$')
        text = repr(calls)
        for forbidden in ["fastboot", "reboot", "/data/adb", "shell su", "adb root"]:
            self.assertNotIn(forbidden, text)

    def test_failed_stock_or_output_check_never_saves_image(self):
        for status, corrupt in [(1, False), (0, True)]:
            fake, calls = self.fake_adb(status, corrupt)
            output = self.base / f"failed-{status}.img"
            with patch.object(boot, "Adb", fake), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ValueError):
                    boot.main(self.arguments() + ["--make", "--output", str(output)])
            self.assertFalse(output.exists())
            self.assertIn("rm -rf /data/local/tmp/alioth-boot-repack-", calls[-1])
            if status:
                self.assertFalse(any("repack original.img" in str(item) for item in calls))

    def test_device_selection_and_abi_newline(self):
        with patch.object(boot.shutil, "which", return_value="adb"):
            adb = boot.Adb()
        responses = {
            "getprop ro.product.device": "alioth\n",
            "getprop ro.product.cpu.abilist": "arm64-v8a,armeabi-v7a\n",
            "getprop ro.build.version.incremental": "fixture\n",
        }
        with patch.object(adb, "run", return_value=(0, "List of devices attached\nfixture\tdevice\n")), \
                patch.object(adb, "shell", side_effect=lambda text: (0, responses[text])), \
                contextlib.redirect_stdout(io.StringIO()):
            adb.select_device()
            responses["getprop ro.product.device"] = "other\n"
            with self.assertRaisesRegex(ValueError, "Expected alioth"):
                adb.select_device()


if __name__ == "__main__":
    unittest.main()
