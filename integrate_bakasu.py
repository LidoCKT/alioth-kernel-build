"""Adapt the pinned alioth kernel to BakaSU manual hooks, without SUSFS/KPM.

Every replacement is checked, so a changed upstream tree fails instead of
silently producing a partially integrated kernel.
"""
import difflib
import pathlib
import re
import subprocess

ROOT_SHA = "516d3e87fbc986ccefdde2c2765f1700612441a9"
kernel = pathlib.Path("kernel")
patches = []


def change(path, transform):
    file = kernel / path
    before = file.read_text()
    after = transform(before)
    assert before != after, f"No change: {path}"
    file.write_text(after)
    patches.extend(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile="a/" + path, tofile="b/" + path,
    ))


def once(text, old, new):
    assert text.count(old) == 1, f"Expected exactly one occurrence: {old[:90]!r}"
    return text.replace(old, new, 1)


def remove_old_guards(text):
    text, count = re.subn(r"#ifdef CONFIG_KSU\n.*?#endif\n", "", text, flags=re.S)
    assert count == 2, f"Expected two legacy hook blocks, got {count}"
    return text


def exec_hooks(text):
    # Remove legacy hooks from native and compat wrappers.
    text, count = re.subn(r"#ifdef CONFIG_KSU\n.*?#endif\n", "", text, flags=re.S)
    assert count == 3
    declaration = """#ifdef CONFIG_KSU_MANUAL_HOOK
extern int ksu_handle_execveat(int *fd, struct filename **filename,
                             void *argv, void *envp, int *flags);
extern int ksu_handle_post_execveat(int *fd, struct filename **filename,
                                  void *argv, void *envp, int *flags, int *retval);
#endif

"""
    text = once(text, "static int __do_execve_file(", declaration + "static int __do_execve_file(")
    # Common implementation covers native execve/execveat and their compat forms.
    text = once(text, "\tif (IS_ERR(filename))\n\t\treturn PTR_ERR(filename);",
                """#ifdef CONFIG_KSU_MANUAL_HOOK
	if (filename)
		ksu_handle_execveat(&fd, &filename, &argv, &envp, &flags);
#endif
	if (IS_ERR(filename))
		return PTR_ERR(filename);""")
    post = """#ifdef CONFIG_KSU_MANUAL_HOOK
	if (filename)
		ksu_handle_post_execveat(&fd, &filename, &argv, &envp, &flags, &retval);
#endif
"""
    text = once(text, "\ttask_numa_free(current, false);\n\tfree_bprm(bprm);",
                "\ttask_numa_free(current, false);\n" + post + "\tfree_bprm(bprm);")
    text = once(text, "out_ret:\n\tif (filename)", "out_ret:\n" + post + "\tif (filename)")
    assert "ksu_execveat_hook" not in text
    return text


def stat_hooks(text):
    text = text.replace("#ifdef CONFIG_KSU\n", "#ifdef CONFIG_KSU_MANUAL_HOOK\n")
    old = "extern int ksu_handle_stat(int *dfd, const char __user **filename_user, int *flags);"
    text = once(text, old, old + """
extern void ksu_handle_newfstat_ret(unsigned int *fd, struct stat __user **statbuf_ptr);
#if defined(__ARCH_WANT_STAT64) || defined(__ARCH_WANT_COMPAT_STAT64)
extern void ksu_handle_fstat64_ret(unsigned long *fd, struct stat64 __user **statbuf_ptr);
#endif""")
    for call, end, hook in [
        ("SYSCALL_DEFINE2(newfstat,", "static int do_readlinkat", "ksu_handle_newfstat_ret"),
        ("SYSCALL_DEFINE2(fstat64,", "SYSCALL_DEFINE4(fstatat64", "ksu_handle_fstat64_ret"),
    ]:
        start = text.index(call)
        finish = text.index(end, start)
        block = text[start:finish]
        block = once(block, "\treturn error;", f"""#ifdef CONFIG_KSU_MANUAL_HOOK
	if (!error)
		{hook}(&fd, &statbuf);
#endif
	return error;""")
        text = text[:start] + block + text[finish:]
    return text


def reboot_hook(text):
    declaration = """#ifdef CONFIG_KSU_MANUAL_HOOK
extern int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd, void __user **arg);
#endif

"""
    text = once(text, "SYSCALL_DEFINE4(reboot,", declaration + "SYSCALL_DEFINE4(reboot,")
    return once(text, "\t/* We only trust the superuser with rebooting the system. */",
                """#ifdef CONFIG_KSU_MANUAL_HOOK
	ksu_handle_sys_reboot(magic1, magic2, cmd, &arg);
#endif
	/* We only trust the superuser with rebooting the system. */""")


change("fs/exec.c", exec_hooks)
change("fs/stat.c", stat_hooks)
change("fs/open.c", lambda t: t.replace("#ifdef CONFIG_KSU\n", "#ifdef CONFIG_KSU_MANUAL_HOOK\n"))
# New driver supplies these hooks automatically through its LSM/input handlers.
change("fs/read_write.c", remove_old_guards)
change("drivers/input/input.c", remove_old_guards)
change("kernel/reboot.c", reboot_hook)
pathlib.Path("bakasu-integration.patch").write_text("".join(patches))

text = (kernel / "build-cloud.sh").read_text()
old = next(line for line in text.splitlines()
           if "curl -LSs" in line and "liyafe1997/SukiSU-Ultra" in line)
text = once(text, old, '    echo "Using externally pinned BakaSU checkout"')
# Drop old SUSFS/KPM config blocks and select the driver's manual-hook route.
config = """    scripts/config --file out/.config \\
      -e KSU -e KSU_MANUAL_HOOK -d KSU_TRACEPOINT_HOOK -d KSU_SUSFS \\
      -e KSU_MANUAL_HOOK_AUTO_SETUID_HOOK \\
      -e KSU_MANUAL_HOOK_AUTO_INITRC_HOOK \\
      -e KSU_MANUAL_HOOK_AUTO_INPUT_HOOK -d KPM
"""
text, count = re.subn(
    r"    scripts/config --file out/\.config \\\n.*?    -e KPM\n",
    config.replace("\\", "\\\\"),
    text, flags=re.S,
)
assert count == 2
start = text.index("# Patch for SukiSU KPM support.")
finish = text.index("cp out/arch/arm64/boot/Image", start)
text = text[:start] + "# No external KPM binary patch in the first BakaSU experiment.\n" + text[finish:]
text = text.replace("KSU_ZIP_STR=SukiSU-SUSFS", "KSU_ZIP_STR=BakaSU-EXPERIMENTAL")
(kernel / "build-cloud.sh").write_text(text)

root = kernel / "KernelSU"
assert not root.exists(), "Fresh source tree required"
subprocess.run(["git", "clone", "--no-checkout", "https://github.com/Baka-SU/BakaSU", str(root)], check=True)
subprocess.run(["git", "-C", str(root), "checkout", "--detach", ROOT_SHA], check=True)
actual = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
assert actual == ROOT_SHA
link = kernel / "drivers/kernelsu"
if link.is_symlink():
    link.unlink()
assert not link.exists(), "Unexpected existing driver directory"
link.symlink_to("../KernelSU/kernel", target_is_directory=True)
for filename, line in [
    ("drivers/Makefile", "obj-$(CONFIG_KSU) += kernelsu/"),
    ("drivers/Kconfig", 'source "drivers/kernelsu/Kconfig"'),
]:
    file = kernel / filename
    if line not in file.read_text():
        with file.open("a") as stream:
            stream.write("\n" + line + "\n")
print("Pinned BakaSU manual-hook integration prepared; no SUSFS or KPM.")
