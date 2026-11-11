# Alioth Kernel Builds

[English](README.md) · [Releases](../../releases)

## 项目说明

为 **Redmi K40 / POCO F3（`alioth`）**提供集成 **SukiSU** 或 **BakaSU** 的 Linux 4.19.325 内核、编译脚本和 boot 制作工具。

你可以下载编译好的内核，也可以在 GitHub 云端或 Linux 电脑自行编译。然后用**自己当前 ROM 的原始 boot.img** 合成新镜像，先临时启动测试，再正式刷入。

| 选择一种方案 | 功能 | 配套管理器 |
| --- | --- | --- |
| SukiSU，驱动 API 3.1.7 | 手动 Hook、SUSFS 1.5.7、KPM | [SukiSU 3.2.0](https://github.com/SukiSU-Ultra/SukiSU-Ultra/releases/tag/v3.2.0) |
| BakaSU，35257/6 | 手动 Hook，不含 SUSFS／KPM | [BakaSU 4.2.0-rc3，35257/6](https://github.com/Baka-SU/BakaSU/releases/tag/v4.2.0-rc3) |

两种方案均有 alioth 实际使用记录。**首批 Release 的 BakaSU 内核已实机验证；SukiSU 这份重编译内核尚未刷测，此前实测的是上游发布包。**具体范围见补充说明。

## 操作流程

**获取内核 → 准备原始 boot 和电脑工具 → 合成 boot.img → 临时启动测试 → 正式刷入。**

以下以 Windows PowerShell 为例。首次使用建议直接下载成品，从第 1 步一路往下做。

### 1. 获取内核（三选一）

**方式 A：下载已经编译好的内核，最省事**

1. 打开 [Releases](../../releases)，选择一个版本。
2. 下载名称含 `SukiSU` 或 `BakaSU` 的**一个**内核 ZIP，以及 `alioth-kernel-build-recipe.zip` 和 `SHA256SUMS`。
3. 用 `Get-FileHash "下载的文件名.zip" -Algorithm SHA256`，与 `SHA256SUMS` 中对应行核对，内核 ZIP 和方案 ZIP 都应检查。
4. 解压 `alioth-kernel-build-recipe.zip`，进入能看到 `scripts` 的目录。后面的命令都在这个目录执行。
5. 新建 `inputs` 文件夹，把内核 ZIP 放进去并改名为 `kernel.zip`，**不要解压内核 ZIP**。

**方式 B：GitHub 云端编译，无需本地编译环境**

1. Fork 本仓库，启用 Actions。
2. 打开 **Actions → Build alioth kernel → Run workflow**，选择 `sukisu` 或 `bakasu` 并运行。
3. 等待成功，从任务页面 **Artifacts** 下载 `alioth-所选方案-任务号`。解压 artifact，取出里面名称含 `anykernel3` 的内核 ZIP；这份内层 ZIP 不要解压。
4. 下载你 Fork 仓库的源码 ZIP 并解压，进入能看到 `scripts` 的目录。新建 `inputs`，把内核 ZIP 复制为 `inputs/kernel.zip`，保留 artifact 的配置、manifest 和校验清单供核查。

云构建使用你账户的 Actions 额度。拿到内核后继续第 2 步。

**方式 C：本地 Linux 编译**

在 Ubuntu 22.04 x86_64 下载本仓库源码并解压，在有 `build.sh` 的目录打开终端：

```bash
sudo apt-get update
sudo apt-get install -y build-essential bc bison flex libssl-dev libelf-dev \
  ccache zip unzip curl python3 git gcc-aarch64-linux-gnu gcc-arm-linux-gnueabi
curl -fL --retry 3 \
  https://dl.google.com/android/repository/android-ndk-r26d-linux.zip -o ndk.zip
unzip -q ndk.zip
export TOOLCHAIN_PATH="$PWD/android-ndk-r26d/toolchains/llvm/prebuilt/linux-x86_64/bin"
bash build.sh bakasu
# 选择 SukiSU 时，将上一行的 bakasu 改为 sukisu。
```

成功后在 `work/bakasu/artifacts/`（或 `work/sukisu/artifacts/`）找到内核 ZIP。在源码根目录新建 `inputs`，复制该 ZIP 为 `inputs/kernel.zip`，保留其他构建材料。接着执行第 2 步；Linux 下 Python 命令使用 `python3`，后续 Fastboot 操作相同。

### 2. 准备原始 boot.img 和电脑工具

1. 确认手机代号为 **alioth**、Bootloader 已解锁；备份个人数据。
2. 从与你手机**当前已安装版本完全一致**的 ROM 包中提取未经 Root 修改的 `boot.img`，放到 `inputs/boot.img`。另存一份原始 boot 和 ROM 包用于恢复；不要用别人的 boot，也不要把内核 ZIP 当作 boot。
3. 安装 [Python 3.10+](https://www.python.org/downloads/) 和 [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)，将 Python、`adb`、`fastboot` 加入 PATH。Windows 需有正常的 ADB／Fastboot 驱动。
4. 手机正常开机，开启 USB 调试，连接电脑并接受授权。在上述工作目录打开 PowerShell，运行：

```powershell
python --version
adb devices
```

应看到 Python 3.10 或更新版本，以及一台状态为 `device` 的手机。记录其序列号；下文所有 `SERIAL` 都要替换成你自己的序列号。未授权、工具找不到或 boot 来源不确定时，先解决再继续。

### 3. 合成新的 boot.img

**使用方式 A 下载的首批 Release 内核**，运行：

```powershell
python scripts/make_boot.py --make --boot "inputs/boot.img" --kernel-zip "inputs/kernel.zip" --output "output/boot-root.img"
```

**使用方式 B／C 自行编译的内核**，核查构建成功及 manifest 后，额外指定方案；以 BakaSU 为例：

```powershell
python scripts/make_boot.py --make --boot "inputs/boot.img" --kernel-zip "inputs/kernel.zip" --output "output/boot-root.img" --allow-custom-kernel --variant bakasu
```

自行编译 SukiSU 则将最后的 `bakasu` 改为 `sukisu`。

脚本借用手机临时目录运行打包工具，无需手机已有 Root。成功后得到 **`output/boot-root.img`**，旁边还有 `.json` 校验报告和 `.log` 日志。原始 boot 保留，脚本不会自动重启或刷机。报错时停止排查；重试须选择未使用过的输出文件名。

### 4. 临时启动，检查是否正常

下载项目说明表格中与你内核匹配的管理器 APK。首次安装可先安装该管理器；**已有其他 Root 方案的用户，必须先准备匹配的 `ksud` 和模块环境**，不能只换 boot。具体限制见补充说明和[详细指南](docs/BOOT.zh-CN.md)。

每条命令确认成功后再执行下一条：

```powershell
adb -s SERIAL reboot bootloader
fastboot devices
fastboot -s SERIAL getvar product
fastboot -s SERIAL getvar unlocked
fastboot -s SERIAL getvar current-slot
```

确认是自己的设备、`product` 为 `alioth`、解锁为 `yes/true`，并记录当前槽是 `a` 还是 `b`。**以下假设当前槽为 a；若为 b，所有分区命令使用 boot_b。**无法确认时不要继续。

```powershell
fastboot -s SERIAL getvar partition-size:boot_a
(Get-Item "output/boot-root.img").Length
Get-FileHash "output/boot-root.img" -Algorithm SHA256
```

镜像字节数必须不大于分区大小（Fastboot 返回值常为十六进制），SHA-256 必须与 `output/boot-root.img.json` 中 `output_boot_sha256` 一致。确认电脑保留了恢复用原始 boot 后，临时启动：

```powershell
fastboot -s SERIAL boot "output/boot-root.img"
```

这一步不写 boot 分区。进入系统后，检查管理器识别驱动、应用 Root，以及拍照、声音、通话、指纹和锁屏唤醒；使用模块的还需检查模块实际工作。**只有全部符合预期，才进入第 5 步。**

临时启动失败时，返回 Fastboot，执行 `fastboot -s SERIAL reboot` 使用原先已刷入的内核；期间管理器、`ksud`、模块设置的变化仍会保留，不能靠普通重启完整还原。

### 5. 正式刷入

重新执行第 4 步的进入 Bootloader 和核对命令，确认序列号、alioth、解锁状态、**此时当前槽**、分区大小和镜像哈希。只刷当次确认的当前槽；若仍为 a：

```powershell
fastboot -s SERIAL flash boot_a "output/boot-root.img"
fastboot -s SERIAL reboot
```

当前槽为 b 就刷 `boot_b`。正常重启后再次检查管理器、Root、模块和日常功能。

如果正式刷入后无法启动，进入 Fastboot，将 `inputs/boot.img` 刷回**刚才实际改写的那个槽**。例如只改过 a：

```powershell
fastboot -s SERIAL flash boot_a "inputs/boot.img"
fastboot -s SERIAL reboot
```

不要顺带刷双槽、切槽、擦分区、清数据、修改 vbmeta／dtbo／vendor_boot 或重新锁定 Bootloader。

## 补充说明

**适用与验证范围。** Root 实现本身不绑定 ROM 品牌；此编译方案选用了上游 MIUI 配置与显示适配。已测试环境是 alioth、xiaomi.eu HyperOS `1.0.10.0.TKHCNXM`、Android 13；其他 ROM 未验证。两种方案曾检查 Root、拍照、声音、通话、指纹及锁屏唤醒，BakaSU 还验证了 ReZygisk 与 LSPosed。首批 BakaSU 二进制通过重打包 boot 实测；首批 SukiSU 重编译包仅通过编译与产物检查，不能把此前上游包的成功当成此二进制已刷测。没有实测通过 Recovery 直接安装首批两份 ZIP，且 ZIP 的 `do.devicecheck=0`，不能依赖它拦截错误机型。

**管理器与模块。** 此处 SukiSU 驱动配套 **3.2.0**，不能因为管理器较新就换成 4.x。两种方案切换需要配套用户态 `ksud`；打开另一种管理器可能替换它。制作工具不迁移用户态或模块，已有 Root 的切换需另行准备。BakaSU 覆盖系统文件的模块需要兼容元模块；元模块不提供 Zygisk，ReZygisk／LSPosed 需另行配置。迁移还须保留 SELinux 标签，不要直接整包还原别人的模块备份。

**制作工具。** 默认只检查，显式 `--make` 才在手机隔离目录制作；不改 Root 授权、不刷分区。支持已检查的 boot v3、gzip ramdisk、AVB footer 布局，需要手机保留 ARM32 用户态，电脑约 1 GB、手机临时目录约 600 MB 可用空间。它核对内核、ramdisk、头部、大小和 vbmeta；结构检查不等于启动验证或原厂签名验证。新工具通过离线测试及历史 boot 一致性检查，尚未在手机执行新制作流程。交互入口、只检查模式及更多排错见[详细指南](docs/BOOT.zh-CN.md)。

**编译与附件。** 完整提交及依赖校验值见 [sources.lock.json](sources.lock.json)。脚本固定内核／Root／AnyKernel 源码和 SukiSU 版本字段，使用 NDK r26d Clang 17.0.2；复现的是源码与配置，不承诺二进制逐字节一致。整理后的工作流没有重新完整编译，首批附件来自此前成功任务。重复本地构建需换新目录，例如 `BUILD_DIR=/path/to/new-build bash build.sh bakasu`。工作流只手动运行，不自动发布或刷机。Release 同时提供配置、源码材料、方案归档和校验值，不包含个人 ROM、boot、日志或模块数据。

**来源与许可。** 内核：[liyafe1997/kernel_xiaomi_sm8250_mod](https://github.com/liyafe1997/kernel_xiaomi_sm8250_mod)，基于 LineageOS、UtsavBalar1231 等人的工作；Root：[SukiSU](https://github.com/liyafe1997/SukiSU-Ultra)、[BakaSU](https://github.com/Baka-SU/BakaSU)；打包：[AnyKernel3](https://github.com/liyafe1997/AnyKernel3)，基于 osm0sis/AnyKernel3；后处理：[SukiSU KernelPatch](https://github.com/SukiSU-Ultra/SukiSU_KernelPatch_patch)。辅助代码采用 GPL-2.0-only，上游组件保留各自许可，详见 [NOTICE.md](NOTICE.md)。
