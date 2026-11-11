# 制作和测试 boot

[返回首页](../README.zh-CN.md) · [English](BOOT.md)

使用当前 ROM 的原始 `boot.img`，把 Release ZIP 中的内核装入其中。无需自己编译内核。**不要使用他人制作的 boot，升级 ROM 后也不要沿用旧 boot。**

## 准备

1. 确认手机是 Redmi K40 / POCO F3，代号 **alioth**，Bootloader 已解锁。先备份个人数据，并保存当前 ROM 的完整安装包及原始 boot，作为恢复材料。
2. 从与你手机**当前安装版本完全一致**的 ROM 包提取未经 Root 修改的 `boot.img`。工具不能自动证明它来自正确 ROM；不确定时先解决来源问题。
3. 下载 Release 中一种方案的 AnyKernel ZIP，以及 `alioth-kernel-build-recipe.zip` 并解压后者。对照 Release 的 `SHA256SUMS` 检查下载文件；不要解压内核 ZIP。
4. 电脑安装 [Python 3.10+](https://www.python.org/downloads/)（Windows 勾选 PATH）和 [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)，将 `adb`、`fastboot` 加入 PATH。Windows 还需正常工作的 ADB/Fastboot 驱动。
5. 手机正常进入 Android，打开 USB 调试，连接电脑并授权。`adb devices` 应显示 `device`。默认只连接这一台设备；多设备时指定 `--serial`。

制作阶段不需要手机已有 Root，也不用安装 Magisk。脚本借用手机执行 ZIP 自带、哈希固定的 ARM32 `magiskboot`，要求系统保留 32 位 ARM 用户态支持。仅支持本项目检查过的 boot v3、gzip ramdisk、AVB footer 布局；遇到其他布局会停止，不能据此认定其他 ROM 不支持该内核。

## 制作镜像

在解压的构建方案目录打开 PowerShell：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Make-Boot.ps1 -Make
```

按提示输入原始 boot 和内核 ZIP 的路径。也可显式提供：

```powershell
python scripts/make_boot.py --make --boot "inputs/boot.img" --kernel-zip "inputs/kernel.zip" --output "output/boot-bakasu.img"
```

Linux 使用相同命令，把 `python` 换成 `python3`。`kernel.zip` 是下载文件的占位名称；输出名根据所选方案填写。电脑需有约 1 GB 空间，手机 `/data/local/tmp` 需有约 600 MB 空间。

脚本会核验设备代号、内核和工具哈希，在手机独立临时目录解包、替换内核并重打包，然后拉回电脑并清理自己的目录。它会核对内核内容、解压后的 ramdisk、头部、镜像大小和 vbmeta，保留原始 boot，不覆盖已有输出。制作完成会生成：

- `boot-bakasu.img`：待测试镜像。
- `boot-bakasu.img.json`：SHA-256 与结构校验报告。
- `boot-bakasu.img.log`：制作日志，留在本地。

脚本不会重启、刷分区、改变 Root 授权或模块配置。结构校验不等于实机启动验证，也不等于修改后的镜像具有原厂有效签名；保留 vbmeta 不代表关闭 AVB。

默认只检查本地输入，不访问手机；加 `--make`（Windows 入口为 `-Make`）才执行制作。也可显式检查：

```powershell
python scripts/make_boot.py --boot "inputs/boot.img" --kernel-zip "inputs/kernel.zip" --check-only
```

自行重新编译的内核哈希不在首批清单中，核查构建材料后额外指定 `--allow-custom-kernel --variant bakasu`（或 `sukisu`）。工具仍要求固定版本的 magiskboot。制作失败时不要刷写残留文件；先阅读错误，原始 boot 不受影响。

## 临时启动

首次安装先准备首页所列的匹配管理器。**已有其他 Root 方案时，先处理兼容的 `ksud` 和模块环境**；制作脚本不迁移这些内容，直接换 boot 不保证模块可用。不要同时打开两种管理器，不要把私人备份当作通用迁移方案。

以下 `SERIAL` 需要换成你自己的设备序列号，每一步都确认成功后再继续：

```powershell
adb -s SERIAL reboot bootloader
fastboot devices
fastboot -s SERIAL getvar product
fastboot -s SERIAL getvar unlocked
fastboot -s SERIAL getvar current-slot
```

必须确认设备是 `alioth`、解锁状态为 `yes/true`、当前槽为明确的 `a` 或 `b`。无法读取时停止并排查，不要猜。下面以**当前槽 a** 为例：

```powershell
fastboot -s SERIAL getvar partition-size:boot_a
```

确认镜像字节数不大于该分区大小（返回值常为十六进制）。记录当前槽和镜像 SHA-256，确认原始 boot 恢复材料已保存在电脑上：

```powershell
Get-FileHash "output/boot-bakasu.img" -Algorithm SHA256
fastboot -s SERIAL boot "output/boot-bakasu.img"
```

`fastboot boot` 从内存启动，不写 boot 分区。本项目之前验证内核使用的就是重打包 boot 的路线；首批 BakaSU 二进制已验证，首批 SukiSU 重编译二进制尚未实机测试，详见 Release。

启动后检查管理器驱动识别、应用 Root、模块、拍照、声音、通话、指纹、锁屏唤醒。仅能进入桌面不算全部通过。APK、`ksud` 和模块开关的更改会持久保存；普通重启只会重新使用已刷入的内核，不能完整还原 Root 用户态。

## 确认后正式刷入与恢复

只有临时启动验证通过后，才考虑正式刷入。重新进入 Bootloader，**再次核对序列号、alioth、解锁状态、当前槽、分区大小和镜像 SHA-256**。如果当前槽仍是 a：

```powershell
fastboot -s SERIAL flash boot_a "output/boot-bakasu.img"
fastboot -s SERIAL reboot
```

若当前槽为 b，则查询和刷写 `boot_b`。只操作当次确认的当前槽，不切槽、不刷双槽。普通重启后再次验证管理器、模块及实际功能。

启动失败时，进入 Fastboot，将**当前 ROM 的原始 boot** 刷回之前实际改写的同一个槽；例如仅改过 a：

```powershell
fastboot -s SERIAL flash boot_a "inputs/boot.img"
fastboot -s SERIAL reboot
```

如果只做了临时启动而没有刷分区，回到 Bootloader 执行 `fastboot -s SERIAL reboot` 使用原先内核；用户态的变更仍需单独处理。不要擦分区、清数据、刷 vbmeta/dtbo/vendor_boot 或重新锁定 Bootloader 来尝试修复。

本项目没有验证通过 Recovery 直接安装首批两份 AnyKernel ZIP；ZIP 也没有启用设备自动拦截。以上指南采用重打包 boot 的流程，不要求 Recovery。

工具行为参考：[Magisk tools](https://topjohnwu.github.io/Magisk/tools.html)、[AOSP fastboot](https://android.googlesource.com/platform/system/core/+/refs/heads/main/fastboot/README.md)。
