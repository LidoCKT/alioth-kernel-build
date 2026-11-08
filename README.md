# Alioth MIUI kernel build experiment

Target: Redmi K40 / POCO F3 (alioth), Android 13 MIUI/HyperOS.
This repository contains build instructions only. No phone backups or device logs.

First stage: rebuild the currently tested kernel source at
`262e587588a28c250c8bb4cc11256840d3c67d8c` with its existing pinned SukiSU.
Use the upstream MIUI configuration and panel adjustments; skip the AOSP build.
Compiler: Android NDK r26d Clang 17, GNU cross binutils from Ubuntu 22.04.
This reproduces the source/configuration baseline, not a bit-identical release binary.

Second stage: integrate a pinned ReSukiSU/BakaSU revision after the baseline passes.
No experimental artifact is approved for flashing merely because it builds.

Manual workflow only; one job at a time; timeout 90 minutes.
Private repository Actions consume the account's included minutes or configured billing allowance.
No billing settings are changed by this project.

Kernel source licensing and notices remain with the upstream source repository.
