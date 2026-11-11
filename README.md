# Alioth Kernel Builds

[简体中文](README.zh-CN.md) · [Releases](../../releases)

## Project overview

Linux 4.19.325 kernels with **SukiSU** or **BakaSU**, build scripts and a boot creation helper for **Redmi K40 / POCO F3 (`alioth`)**.

Download a prebuilt kernel or build it with GitHub Actions / local Linux. Combine it with **the original boot.img from your exact installed ROM**, test a temporary boot, then flash after successful testing.

| Choose one | Features | Matching manager |
| --- | --- | --- |
| SukiSU, driver API 3.1.7 | Manual hooks, SUSFS 1.5.7, KPM | [SukiSU 3.2.0](https://github.com/SukiSU-Ultra/SukiSU-Ultra/releases/tag/v3.2.0) |
| BakaSU, 35257/6 | Manual hooks, no SUSFS/KPM | [BakaSU 4.2.0-rc3, 35257/6](https://github.com/Baka-SU/BakaSU/releases/tag/v4.2.0-rc3) |

Both implementations have been used on alioth. **The initial Release BakaSU kernel was device-tested; its rebuilt SukiSU kernel has not been flashed. The earlier SukiSU device test used an upstream release.** See additional notes for details.

## Step-by-step instructions

**Get a kernel → prepare stock boot and computer → make boot.img → test a temporary boot → flash.**

Commands below use Windows PowerShell. For a first installation, use the prebuilt download and follow the steps in order.

### 1. Get a kernel: choose one method

**A. Download a prebuilt kernel — the easiest option**

1. Open [Releases](../../releases) and choose a version.
2. Download **one** kernel ZIP containing `SukiSU` or `BakaSU` in its name, plus `alioth-kernel-build-recipe.zip` and `SHA256SUMS`.
3. Use `Get-FileHash "downloaded-filename.zip" -Algorithm SHA256` and compare with its line in `SHA256SUMS`. Verify both the kernel ZIP and recipe ZIP.
4. Extract `alioth-kernel-build-recipe.zip`. Open the directory containing `scripts`; run subsequent commands there.
5. Create an `inputs` directory, put the kernel ZIP inside and rename it `kernel.zip`. **Do not extract the kernel ZIP.**

**B. Build on GitHub Actions — no local compiler needed**

1. Fork this repository and enable Actions.
2. Open **Actions → Build alioth kernel → Run workflow**, select `sukisu` or `bakasu`, and run it.
3. Wait for success. Under **Artifacts**, download `alioth-implementation-run-number`. Extract this artifact and locate the kernel ZIP containing `anykernel3` in its name. Keep that inner ZIP intact.
4. Download and extract your fork's source ZIP. In the directory containing `scripts`, create `inputs` and copy the kernel ZIP to `inputs/kernel.zip`. Retain the artifact's configuration, manifest and checksums for review.

Cloud builds use your account's Actions allowance. Continue to step 2 once you have the kernel.

**C. Build locally on Linux**

Download and extract this repository on Ubuntu 22.04 x86_64. Open a terminal in the directory containing `build.sh`:

```bash
sudo apt-get update
sudo apt-get install -y build-essential bc bison flex libssl-dev libelf-dev \
  ccache zip unzip curl python3 git gcc-aarch64-linux-gnu gcc-arm-linux-gnueabi
curl -fL --retry 3 \
  https://dl.google.com/android/repository/android-ndk-r26d-linux.zip -o ndk.zip
unzip -q ndk.zip
export TOOLCHAIN_PATH="$PWD/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin"
bash build.sh bakasu
# For SukiSU, replace bakasu above with sukisu.
```

Find the kernel ZIP in `work/bakasu/artifacts/` (or `work/sukisu/artifacts/`). Create `inputs` at the repository root and copy the ZIP to `inputs/kernel.zip`; retain the other build materials. Continue to step 2. On Linux use `python3` for Python commands; subsequent Fastboot commands are the same.

### 2. Prepare the original boot.img and computer tools

1. Confirm **alioth** with an unlocked bootloader. Back up personal data.
2. Extract an unmodified `boot.img` from the ROM package matching **the exact version currently installed**. Save it as `inputs/boot.img`. Keep a separate copy and the ROM package for recovery. Do not use someone else's boot or treat a kernel ZIP as boot.img.
3. Install [Python 3.10+](https://www.python.org/downloads/) and [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools), putting Python, `adb` and `fastboot` on PATH. Windows also needs working ADB/Fastboot drivers.
4. Leave Android running, enable USB debugging, connect and authorize the computer. Open PowerShell in the working directory:

```powershell
python --version
adb devices
```

Expect Python 3.10+ and one phone listed as `device`. Record its serial: replace **every `SERIAL` below** with your own value. Resolve missing tools, authorization or uncertain boot provenance before continuing.

### 3. Make the new boot.img

For an **initial Release kernel downloaded using method A**:

```powershell
python scripts/make_boot.py --make --boot "inputs/boot.img" --kernel-zip "inputs/kernel.zip" --output "output/boot-root.img"
```

For a **kernel you built using method B/C**, review build success and its manifest, then explicitly select the implementation. For BakaSU:

```powershell
python scripts/make_boot.py --make --boot "inputs/boot.img" --kernel-zip "inputs/kernel.zip" --output "output/boot-root.img" --allow-custom-kernel --variant bakasu
```

For your own SukiSU build, change the final `bakasu` to `sukisu`.

The helper runs the repacking tool in a temporary phone directory; existing Root is unnecessary. Success produces **`output/boot-root.img`**, a `.json` validation report and a `.log`. It preserves the original boot and does not reboot or flash. On error, stop and investigate; choose an unused output filename when retrying.

### 4. Test a temporary boot

Download the matching manager APK from the project table. For a first installation, install that manager. **If switching from another Root implementation, prepare matching `ksud` and module state first**; replacing boot alone is insufficient. See additional notes and the [detailed guide](docs/BOOT.md).

Check each command succeeds before proceeding:

```powershell
adb -s SERIAL reboot bootloader
fastboot devices
fastboot -s SERIAL getvar product
fastboot -s SERIAL getvar unlocked
fastboot -s SERIAL getvar current-slot
```

Confirm your device, `product` = `alioth`, unlocked = `yes/true`, and record current slot `a` or `b`. **The examples below assume current slot a; use boot_b for partition commands if it is b.** Stop if any value is unclear.

```powershell
fastboot -s SERIAL getvar partition-size:boot_a
(Get-Item "output/boot-root.img").Length
Get-FileHash "output/boot-root.img" -Algorithm SHA256
```

The image's byte count must not exceed the partition size (Fastboot often reports hexadecimal). Its SHA-256 must match `output_boot_sha256` in `output/boot-root.img.json`. Confirm the original boot is available for recovery, then:

```powershell
fastboot -s SERIAL boot "output/boot-root.img"
```

This does not write the boot partition. After Android starts, check manager driver detection, app Root, camera, audio, calls, fingerprint and lock/wake. If using modules, check that they actually work. **Proceed to step 5 only after the checks pass.**

If temporary boot fails, return to Fastboot and run `fastboot -s SERIAL reboot` to use the installed kernel. Manager, ksud and module-setting changes persist; an ordinary reboot does not restore the entire Root environment.

### 5. Flash after successful testing

Repeat step 4's bootloader entry and checks: serial, alioth, unlock status, **current slot now**, partition size and image hash. Write only the confirmed current slot. If it is still a:

```powershell
fastboot -s SERIAL flash boot_a "output/boot-root.img"
fastboot -s SERIAL reboot
```

For current slot b, flash `boot_b`. Repeat manager, Root, module and everyday-function checks after the normal reboot.

If Android cannot start after flashing, enter Fastboot and restore `inputs/boot.img` to **the same slot you actually modified**. For a change to slot a only:

```powershell
fastboot -s SERIAL flash boot_a "inputs/boot.img"
fastboot -s SERIAL reboot
```

Do not flash both slots, switch slots, erase partitions, wipe data, change vbmeta/dtbo/vendor_boot or relock the bootloader.

## Additional notes

**Scope and validation.** Root implementations are not ROM-brand-specific; this recipe selects the upstream MIUI configuration and display adjustments. The tested environment is alioth, xiaomi.eu HyperOS `1.0.10.0.TKHCNXM`, Android 13. Other ROMs are unverified. Both implementations have had Root, camera, audio, calls, fingerprint and lock/wake checked; BakaSU also had ReZygisk and LSPosed verified. The initial BakaSU binary was tested through a repacked boot. The initial rebuilt SukiSU binary was compiled and checked, but the earlier upstream release test does not validate this binary. Direct Recovery installation of the two initial ZIPs is untested; their `do.devicecheck=0` means they will not automatically reject the wrong device.

**Managers and modules.** This SukiSU driver needs manager **3.2.0**, not a newer 4.x manager. Switching implementations requires matching `ksud`; opening the competing manager can replace it. The helper does not migrate userspace or modules; existing Root installations need separate migration preparation. BakaSU system-overlay modules need a compatible metamodule. It does not provide Zygisk; ReZygisk/LSPosed are separate. Preserve SELinux labels during migration and do not restore someone else's module backup.

**Boot helper.** The default is a local check; explicit `--make` enables repacking in an isolated phone directory, without changing Root grants or flashing partitions. It supports the checked boot-v3/gzip-ramdisk/AVB-footer layout and requires ARM32 userspace support, about 1 GB computer space and 600 MB phone temporary space. It checks kernel, ramdisk, header, size and vbmeta; structural validation does not prove successful boot or valid OEM signatures. The new helper has offline tests and a historical-boot consistency check, but has not executed a new repacking run on the phone. See the [detailed guide](docs/BOOT.md) for the interactive entry point, check-only mode and troubleshooting.

**Builds and attachments.** Full revisions and dependency hashes are in [sources.lock.json](sources.lock.json). The recipe pins kernel/Root/AnyKernel sources and SukiSU version metadata, using NDK r26d Clang 17.0.2. It reproduces source/configuration choices, without promising byte-identical binaries. The cleaned-up workflow has not had a new full build; initial binaries are from earlier successful runs. Rebuilding locally requires a fresh directory, for example `BUILD_DIR=/path/to/new-build bash build.sh bakasu`. Workflows run manually and do not publish or flash. Releases include configurations, source materials, the recipe archive and checksums, without personal ROMs, boot images, logs or module data.

**Sources and licensing.** Kernel: [liyafe1997/kernel_xiaomi_sm8250_mod](https://github.com/liyafe1997/kernel_xiaomi_sm8250_mod), based on LineageOS and work by UtsavBalar1231 and others. Root: [SukiSU](https://github.com/liyafe1997/SukiSU-Ultra), [BakaSU](https://github.com/Baka-SU/BakaSU). Packaging: [AnyKernel3](https://github.com/liyafe1997/AnyKernel3), based on osm0sis/AnyKernel3. Post-processing: [SukiSU KernelPatch](https://github.com/SukiSU-Ultra/SukiSU_KernelPatch_patch). Helper code uses GPL-2.0-only; upstream components retain their licenses. See [NOTICE.md](NOTICE.md).
