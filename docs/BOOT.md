# Make and test a boot image

[README](../README.md) · [简体中文](BOOT.zh-CN.md)

Use an **unmodified boot.img from the exact ROM version currently installed on your alioth**. The helper replaces its kernel with the one in the Release ZIP. Do not use someone else's boot or reuse an old boot after updating your ROM.

## Prepare

1. Confirm Redmi K40 / POCO F3, codename **alioth**, with an unlocked bootloader. Back up personal data and keep your exact ROM package and original boot available for recovery.
2. Extract the clean `boot.img` from that ROM. The helper cannot prove the image's ROM provenance.
3. Download one Release kernel ZIP and `alioth-kernel-build-recipe.zip`. Verify against Release `SHA256SUMS`, and extract the recipe only.
4. Install [Python 3.10+](https://www.python.org/downloads/) and [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools). Put Python, adb and fastboot on PATH; Windows also needs working drivers.
5. Boot Android, enable USB debugging, connect and authorize the computer. `adb devices` must show `device`. Connect one device, or supply `--serial SERIAL`.

Making the image needs no existing Root or Magisk installation. It uses the pinned ARM32 magiskboot from the ZIP in an isolated phone directory, so 32-bit ARM userspace support is required. The helper supports the tested boot-v3/gzip-ramdisk/AVB-footer layout and refuses other layouts; refusal does not establish kernel incompatibility.

## Make the image

Open PowerShell in the extracted recipe directory:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Make-Boot.ps1 -Make
```

Enter the stock boot and kernel ZIP paths when prompted, or run:

```powershell
python scripts/make_boot.py --make --boot "inputs/boot.img" --kernel-zip "inputs/kernel.zip" --output "output/boot-bakasu.img"
```

On Linux use `python3`. Substitute your downloaded ZIP filename and chosen implementation. Allow about 1 GB on the computer and 600 MB under the phone's `/data/local/tmp`.

The helper checks alioth, kernel/tool hashes, unpacks and repacks in its own temporary phone directory, pulls the result and removes that directory. It compares the selected kernel, decompressed ramdisk, header, size and vbmeta before saving the image. Originals and existing output files are never overwritten.

Outputs are the `.img`, `.img.json` structural/hash report and local `.img.log`. The helper does not reboot, flash partitions or change Root/module settings. Structural checks do not prove a successful boot or a valid OEM signature for changed content; preserving vbmeta does not disable AVB.

The default is a local input check without accessing a phone; making an image requires `--make` (PowerShell: `-Make`). Explicit checking uses `--check-only` instead of `--make`. To check an already repacked image offline, use `--verify "output/boot-bakasu.img"` instead of `--make`. Your own rebuild needs explicit `--allow-custom-kernel --variant bakasu` (or `sukisu`) after reviewing its build manifest; the pinned magiskboot is still required. On failure, read the error and do not flash leftover files.

## Test before flashing

Prepare the matching manager listed in the README. If switching Root implementations, first prepare compatible `ksud` and module state: the helper does not migrate them. Do not open competing managers or use personal backups as a generic migration recipe.

Replace `SERIAL` with your device serial and check each command succeeds:

```text
adb -s SERIAL reboot bootloader
fastboot devices
fastboot -s SERIAL getvar product
fastboot -s SERIAL getvar unlocked
fastboot -s SERIAL getvar current-slot
```

Require `alioth`, unlocked `yes/true`, and an explicit `a` or `b` slot. Stop on missing or ambiguous values. For **current slot a**:

```text
fastboot -s SERIAL getvar partition-size:boot_a
```

Ensure the image's byte count does not exceed this partition size (often hexadecimal). Record the slot and verify the image SHA-256 against its JSON report. On Windows:

```powershell
Get-FileHash "output/boot-bakasu.img" -Algorithm SHA256
fastboot -s SERIAL boot "output/boot-bakasu.img"
```

`fastboot boot` starts the image from memory without writing boot. This repacked-boot route was used for the previous device tests. The initial BakaSU binary was tested; the initial rebuilt SukiSU binary has not been device-tested. See Release notes.

Check driver detection, app Root, modules, camera, audio, calls, fingerprint and lock/wake. Reaching Android alone is insufficient. APK, ksud and module changes persist; an ordinary reboot returns to the installed kernel but does not restore the entire Root userspace.

## Install after successful testing

Return to the bootloader and **recheck serial, alioth, unlock status, current slot, partition size and image SHA-256**. If the current slot is still a:

```text
fastboot -s SERIAL flash boot_a "output/boot-bakasu.img"
fastboot -s SERIAL reboot
```

For current slot b, query and flash `boot_b`. Write only the confirmed current slot, without switching or flashing both slots. Repeat functional checks after the normal reboot.

For recovery, enter Fastboot and flash your exact-ROM original boot to the same slot you actually modified; if you modified only a:

```text
fastboot -s SERIAL flash boot_a "inputs/boot.img"
fastboot -s SERIAL reboot
```

After a temporary boot without partition flashing, `fastboot -s SERIAL reboot` returns to the installed kernel; userspace changes still need separate handling. Do not erase partitions, wipe data, change vbmeta/dtbo/vendor_boot or relock the bootloader as a recovery shortcut.

Direct Recovery installation of the initial AnyKernel ZIPs has not been tested, and ZIP device rejection is disabled. This guide uses boot repacking and does not require Recovery.

References: [Magisk tools](https://topjohnwu.github.io/Magisk/tools.html), [AOSP fastboot](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/README.md).
