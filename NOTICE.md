# Source and licensing

Build scripts in this repository are distributed under GPL-2.0-only.
The integration scripts modify upstream Linux kernel sources; upstream copyright
and licensing notices remain in those sources.

The Linux kernel uses GPL-2.0 with its documented syscall exception and additional
per-file licenses. SukiSU, BakaSU, KernelPatch and AnyKernel retain the licenses
and copyright notices shipped in their respective source trees. A build-script
license does not relicense these components or their bundled tools.

Source locations and revisions are listed in `sources.lock.json`.
The initial Release additionally includes:

- The exact upstream kernel source archive.
- Fixed SukiSU, BakaSU and AnyKernel source archives.
- KernelPatch 0.12.0 source, for the SukiSU binary post-processor.
- The original successful build scripts/workflows and BakaSU integration patch.
- Actual kernel configurations and a manifest connecting each output to its source.

These materials describe the original Release binaries. The current cleaned-up
recipe additionally pins packaging and SukiSU version labels; it is not claimed
to produce byte-identical copies of the original binaries.

Compiler/toolchain software is obtained from its upstream distribution and is
not redistributed in this repository. Bundled AnyKernel tools retain upstream
terms; their archive is supplied with its original notices.
