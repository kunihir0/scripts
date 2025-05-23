# Refactoring Plan for `setup_surface_kernel_py.py`

**Project Goal:** Refactor `chimera/py/setup_surface_kernel_py.py` to generate a complete and standalone Chimera Linux cports template directory for building the `linux-surface` kernel. The generated template should blend the specific build logic from the Arch Linux `PKGBUILD` for `linux-surface` with the conventions and structure of existing Chimera cports templates like `linux-lts`.

## 1. Overall Strategy for the Refactored `setup_surface_kernel_py.py`

*   **Role:** The script will function as a command-line tool that generates a cports template. It will parse information from the `linux-surface` `PKGBUILD` and other specified sources, then construct the necessary directory structure and files for a new cport. **The generated cport (specifically its `template.py`) will be responsible for the actual kernel fetching, patching, configuration, and building via `cbuild`.**
*   **Inputs:**
    *   **Required:** Path to the directory containing the Arch Linux `PKGBUILD` and associated base configuration files (e.g., `chimera/py/docs/kernel_stuff/`). This directory is expected to contain `PKGBUILD`, `config`, and `arch.config`.
    *   **Required:** Path to the directory containing specific Surface-related kernel config fragments (e.g., `chimera/py/docs/kernel_stuff/surface_configs/`, from which `surface-X.Y.config` will be sourced).
    *   **Fixed Internal Path:** The script will assume the local `linux-surface` git repository is located at `chimera/linux-surface/` relative to the project root (workspace directory).
    *   **Optional:** The desired name for the new cport template directory (e.g., `linux-surface-custom`). If not provided, a default name like `linux-surface-generated` will be used.
*   **Target Output:** A new directory created within `chimera/cports/main/` (e.g., `chimera/cports/main/linux-surface-custom/`) containing:
    *   `template.py`: The main cports build recipe.
    *   `files/`: A subdirectory containing:
        *   `config` (copied from input)
        *   `surface.config` (copied from `surface-X.Y.config` in input, renamed)
        *   `arch.config` (copied from input)
    *   `patches/`: A subdirectory containing kernel patch files copied from the local `chimera/linux-surface/patches/{KERNEL_VERSION_SERIES}/` directory, based on patches listed in the `PKGBUILD`.

**Flow Diagram of the Generator Script:**
```mermaid
graph TD
    A[Start: Run setup_surface_kernel_py.py] --> B(Parse Command-Line Arguments: kernel_stuff_path, surface_configs_path, output_cport_name?);
    B --> C{Validate Input Paths?};
    C -- Yes --> D[Parse PKGBUILD from kernel_stuff_path];
    C -- No --> Z[Error: Invalid Inputs];
    D --> E[Extract: pkgver, pkgrel, _srctag, makedepends, patch_filenames, config_checksums];
    E --> F[Determine Kernel Version Series (e.g., 6.14 from pkgver)];
    F --> G[Set Up Target Cport Directory: chimera/cports/main/{output_cport_name}/];
    G --> H[Create subdirs: files/, patches/];
    H --> I[Copy Config Files to files/];
    I --> J[Copy Specified Patches from chimera/linux-surface/patches/... to patches/];
    J --> K[Calculate SHA256 Checksums for files in files/ (and patches/ for internal use if needed)];
    K --> L[Construct template.py Content];
    L --> M[Write template.py to cport directory];
    M --> N[Print Success & User Instructions];
    N --> O[End];
```

## 2. Key Steps for the Refactored `setup_surface_kernel_py.py`

*   **A. Argument Parsing:**
    *   Implement command-line argument parsing (e.g., using `argparse`).
    *   Accept paths for `kernel_stuff` directory, `surface_configs` directory, and an optional output cport name.
*   **B. PKGBUILD Parsing:**
    *   Read and parse the `PKGBUILD` file located at `{kernel_stuff_path}/PKGBUILD`.
    *   Extract: `pkgver`, `pkgrel`, `_srctag`, `makedepends`, patch filenames (from `source` array), `sha256sums` for config files.
*   **C. Directory and File Setup:**
    *   **Target Directory:** Create `chimera/cports/main/{cport_name}/` with `files/` and `patches/` subdirectories. Handle overwrites.
    *   **Configuration Files:** Copy `config`, `surface-X.Y.config` (renamed to `surface.config`), and `arch.config` to the `files/` directory.
    *   **Patch Files:** Copy required patch files (identified from `PKGBUILD`) from `chimera/linux-surface/patches/{KERNEL_VERSION_SERIES}/` to the `patches/` directory.
    *   **Checksum Calculation:** Calculate `sha256sum` for each file copied into `files/`. Checksums for patches in `patches/` will also be calculated by the generator, primarily for internal consistency or potential future use, but these patches won't be listed in the `template.py`'s main `source` array.
*   **D. `template.py` Generation:**
    *   Dynamically construct the `template.py` content.
    *   Write to `{cport_name}/template.py`.
*   **E. User Instructions:** Print success message and example `cbuild` command.

## 3. Detailed Structure and Content of the Generated `template.py`

The generated `template.py` will blend `PKGBUILD` specifics with Chimera cports conventions.

```python
# Example structure for the generated template.py

pkgname = "linux-surface-custom"  # Or the user-defined/default name
pkgver = "6.14.2.arch1"          # From PKGBUILD
pkgrel = 1                       # From PKGBUILD
pkgdesc = f"Linux kernel ({pkgver.split('.')[0]}.{pkgver.split('.')[1]} series) with Surface patches"
archs = ["x86_64"]
license = "GPL-2.0-only"
url = "https://github.com/linux-surface/linux-surface"

_srctag = "v6.14.2-arch1" # From PKGBUILD
source = [
    f"git+https://github.com/archlinux/linux#tag={_srctag}", # Main kernel source
    "files/config",         # Local base config
    "files/surface.config", # Local Surface-specific config
    "files/arch.config"     # Local Arch-specific config for Surface
]
sha256sums = [
    "SKIP", # For git source
    "checksum_for_files_config",
    "checksum_for_files_surface_config",
    "checksum_for_files_arch_config",
]

hostmakedepends = [
    "bc", "cpio", "gettext", "git", "libelf", "perl", "tar", "xz", "python", # From PKGBUILD
    "base-kernel-devel" # Standard for Chimera kernel builds
]
depends = ["base-kernel"]
provides = [f"linux={pkgver.split('.')[0]}.{pkgver.split('.')[1]}"] # Adapted from PKGBUILD

options = [
    "!check", "!debug", "!strip", "!scanrundeps", "!scanshlibs", "!lto",
    "textrels", "execstack", "foreignelf" # Common Chimera options
]

make_ENV = { # From PKGBUILD exports
    "KBUILD_BUILD_HOST": "chimera-linux",
    "KBUILD_BUILD_USER": pkgname,
    # Timestamp needs cbuild-idiomatic handling of SOURCE_DATE_EPOCH or a fixed value
    "KBUILD_BUILD_TIMESTAMP": self.source_date_epoch and "$(date -Ru${SOURCE_DATE_EPOCH:+d @$SOURCE_DATE_EPOCH})" or "1970-01-01T00:00:00Z"
}

def prepare(self):
    with self.pushd(self.build_wrksrc): # build_wrksrc is the kernel source directory
        # Set localversion files (PKGBUILD logic)
        (self.chroot_cwd / "localversion.10-pkgrel").write_text(f"-{self.pkgrel}\n")
        (self.chroot_cwd / "localversion.20-pkgname").write_text(f"{self.pkgname.replace('linux-', '')}\n")

        self.do("make", "defconfig")
        kernelrelease_out = self.do("make", "-s", "kernelrelease", capture_output=True, check=True)
        kernelrelease = kernelrelease_out.stdout.strip()
        (self.chroot_cwd / "version").write_text(kernelrelease + "\n")
        self.do("make", "mrproper")

        # Apply patches explicitly AFTER mrproper (PKGBUILD logic)
        # Patches are in self.chroot_patches_path (maps to generated cport's patches/ dir)
        # Generator script ensures patches are copied there.
        # Setup git for am if not already a repo (PKGBUILD does this)
        # Check if .git exists, if not, init, config, commit
        if not (self.chroot_cwd / ".git").is_dir():
            self.do("git", "init")
            self.do("git", "config", "--local", "user.email", "cbuild@chimera-linux.org")
            self.do("git", "config", "--local", "user.name", "cbuild")
            self.do("git", "add", ".")
            # Allow empty commit if no files initially, or commit specific files if that's safer
            self.do("git", "commit", "--allow-empty", "-m", "Initial cbuild commit before patching")


        # Iterate through patch files (names derived from PKGBUILD by generator)
        # Example: patch_list = ["0001-secureboot.patch", "0002-surface3.patch", ...]
        # This list would be embedded by the generator script.
        # For demonstration, assume self.patches_list is populated by the generator.
        # self.patches_list = [...] # This would be generated
        
        # A more robust way: iterate files in self.chroot_patches_path
        patches_dir = self.chroot_patches_path
        sorted_patches = sorted(patches_dir.glob("*.patch"))

        for patch_file_chroot_path in sorted_patches:
            self.log(f"Applying patch {patch_file_chroot_path.name}...")
            # self.do("patch", "-p1", "-i", patch_file_chroot_path) # Alternative: patch -p1
            self.do("git", "am", "-3", str(patch_file_chroot_path))


        # Merge configs (PKGBUILD logic)
        # files/config, files/surface.config, files/arch.config are available via self.chroot_sources_path
        # as they are listed in the 'source' array.
        self.do(
            self.chroot_cwd / "scripts/kconfig/merge_config.sh", "-m",
            self.chroot_sources_path / "config",
            self.chroot_sources_path / "surface.config",
            self.chroot_sources_path / "arch.config",
            wrksrc = self.chroot_cwd # Ensures .config is written in kernel_source_dir
        )

        self.do("make", f"KERNELRELEASE={kernelrelease}", "olddefconfig")
        self.log(f"Prepared {self.pkgname} version {kernelrelease}")

def build(self):
    with self.pushd(self.build_wrksrc):
        kernelrelease = (self.chroot_cwd / "version").read_text().strip()
        self.do("make", f"KERNELRELEASE={kernelrelease}", "all")

def install(self):
    with self.pushd(self.build_wrksrc):
        kernelrelease = (self.chroot_cwd / "version").read_text().strip()
        modulesdir = self.destdir / f"usr/lib/modules/{kernelrelease}"
        image_name_out = self.do("make", "-s", "image_name", capture_output=True, check=True)
        image_name = image_name_out.stdout.strip()

        self.install_dir(modulesdir)
        self.install_file(self.chroot_cwd / image_name, modulesdir, name="vmlinuz", mode=0o644)
        (modulesdir / "pkgbase").write_text(self.pkgname + "\n")

        self.do(
            "make",
            f"INSTALL_MOD_PATH={self.chroot_destdir / 'usr'}",
            # "INSTALL_MOD_STRIP=1", # cbuild handles stripping via options
            "DEPMOD=/doesnt/exist", # cbuild handles depmod
            "modules_install"
        )

        self.rm(modulesdir / "build", force=True, recursive=True) # Ensure recursive for symlinks
        self.rm(modulesdir / "source", force=True, recursive=True) # Ensure recursive

        # Install files for -devel package
        builddir_target = modulesdir / "build"
        self.install_dir(builddir_target)

        for f_name in [".config", "Makefile", "Module.symvers", "System.map", "version", "vmlinux"]:
            f_path = self.chroot_cwd / f_name
            if f_path.exists():
                self.install_file(f_path, builddir_target, mode=0o644)
        for f_path in self.chroot_cwd.glob("localversion.*"):
             self.install_file(f_path, builddir_target, mode=0o644)

        if (self.chroot_cwd / "kernel/Makefile").exists():
            self.install_dir(builddir_target / "kernel")
            self.install_file(self.chroot_cwd / "kernel/Makefile", builddir_target / "kernel", mode=0o644)
        
        if (self.chroot_cwd / "arch/x86/Makefile").exists(): # Assuming x86_64
            self.install_dir(builddir_target / "arch/x86")
            self.install_file(self.chroot_cwd / "arch/x86/Makefile", builddir_target / "arch/x86", mode=0o644)

        for d_name in ["scripts", "include", "arch/x86/include"]: # Assuming x86_64
            src_d = self.chroot_cwd / d_name
            if src_d.is_dir():
                self.cp(src_d, builddir_target / d_name, recursive=True, symlinks=True)
        
        # PKGBUILD specific headers (example, needs full translation)
        # self.install_file(self.chroot_cwd / "drivers/media/i2c/msp3400-driver.h", builddir_target / "drivers/media/i2c", mode=0o644)
        
        for kconfig_file in self.chroot_cwd.glob("**/Kconfig*"):
            rel_path = kconfig_file.relative_to(self.chroot_cwd)
            target_kconfig_path = builddir_target / rel_path
            self.install_dir(target_kconfig_path.parent)
            self.install_file(kconfig_file, target_kconfig_path.parent, name=kconfig_file.name, mode=0o644)
        
        self.install_dir(self.destdir / "usr/src")
        self.ln_s(f"../lib/modules/{kernelrelease}/build", self.destdir / f"usr/src/{self.pkgname}", relative=True)

@subpackage(f"{pkgname}-devel")
def _devel(self):
    self.pkgdesc = f"{pkgdesc} (development files)"
    self.depends += ["clang", "pahole"]
    self.options = ["foreignelf", "execstack", "!scanshlibs"]
    
    kernelrelease_real = ""
    # Determine kernelrelease from installed modules dir
    module_paths = list((self.parent.destdir / "usr/lib/modules").glob("*"))
    if module_paths:
        kernelrelease_real = module_paths[0].name
    else: # Fallback if modulesdir not found (e.g. during lint or dry run)
        # This is tricky; ideally, the main template could store kernelrelease on self
        # For now, this might be an issue for pure linting without build.
        # A safer bet for linting might be to use self.pkgver components if it's clean.
        pass


    if kernelrelease_real:
        return [
            f"usr/lib/modules/{kernelrelease_real}/build",
            f"usr/src/{self.pkgname}"
        ]
    return []

# -dbg subpackage is handled automatically by cbuild based on options
```

## 4. Assumptions, Dependencies, and Configuration (for `setup_surface_kernel_py.py`)

*   **Assumptions:** `chimera/linux-surface/` and `chimera/cports/` accessible; `kernel_stuff_path` has `PKGBUILD`, `config`, `arch.config`; `surface_configs_path` has `surface-X.Y.config`; `chimera/linux-surface/patches/` has patch series; user has write permissions.
*   **Python Dependencies:** `pathlib`, `shutil`, `re`, `hashlib`, `argparse`.
*   **Configuration:** None for the script itself; CLI arguments control behavior.

## 5. Error Handling and User Interaction in `setup_surface_kernel_py.py`

*   **Error Handling:** Handle `FileNotFoundError`, `FileExistsError` (with overwrite confirmation), `pkgver` parsing errors.
*   **User Interaction:** Prompts for inputs, overwrite confirmation, success/failure messages.