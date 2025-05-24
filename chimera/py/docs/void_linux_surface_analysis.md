# Analysis of Void Linux `linux-surface` Package (PR #32823)

This document analyzes the Void Linux `xbps-src` template and associated files for the `linux-surface` package (version 5.13.13), as detailed in PR #32823. The goal is to extract insights for designing a Chimera Linux cport template generator for similar complex kernel packages. This analysis incorporates information from the initial PR data, the PR discussion thread (`void-linux-xbps-failedpullconvo.md`), and the final file states shown in the PR (`void-linux-xbpx-failedpull.md`).

## Build Workflow Overview

The following Mermaid diagram illustrates the overall build workflow:

```mermaid
graph TD
    A[Start: Fetch Sources] --> B{Distfiles};
    B --> C["Kernel Tarball (linux-${version%.*}.tar.xz)"];
    B --> D[Kernel Patch (patch-${version}.xz)];
    B --> E[Surface Patches Tarball (surface-linux.tar.gz)];

    C --> F[Extract Kernel Tarball to build_wrksrc (e.g., linux-5.13)];
    F --> G[Establish wrksrc (e.g., linux-5.13.13-surface, effectively the build_wrksrc dir)];
    G --> H{pre_patch Hook};
    H --> I[Apply Main Kernel Patch (patch-${version}.xz) via xzcat];
    I --> J[Extract Surface Patches Tarball (e.g., to ../linux-surface-arch-VERSION-TAG)];
    J --> K[Apply Surface Patches in a loop (*.patch) from extracted Surface archive];

    K --> L{do_configure Hook};
    L --> M[Copy Base Config (e.g., files/x86_64-dotconfig) to intermediate name (e.g., dotconfig.config)];
    M --> N[Copy Surface-Specific Config (from Surface archive) to intermediate name (e.g., surface-linux.config)];
    N --> O[Merge Configs: ./scripts/kconfig/merge_config.sh -m dotconfig.config surface-linux.config into .config];
    O --> P[Run 'make oldconfig' to finalize .config];
    P --> Q[Set CONFIG_LOCALVERSION via sed];

    Q --> R{do_build Hook};
    R --> S[Clear LDFLAGS];
    S --> T[Run 'make prepare'];
    T --> U[Run 'make bzImage modules' (or arch-specific targets)];

    U --> V{do_install Hook};
    V --> W[Install Modules: 'make modules_install'];
    W --> X[Install Kernel Image, .config, System.map to /boot];
    X --> Y[Install Headers to /usr/src/kernel-headers-VERSION];
    Y --> Z[Process Debug Symbols using 'mv-debug' script];

    Z --> AA[Define Subpackages: -headers, -dbg];
    AA --> AB[End: Package Ready];
```

## 1. Overall Strategy

The Void template employs a multi-stage approach:
1.  **Source Aggregation:** Fetches the base kernel source, an incremental kernel patch, and a separate archive for Surface-specific patches and configurations. This was a result of PR feedback, moving away from vendoring patches directly in the `void-packages` repo.
2.  **Sequential Patching:** In the `pre_patch` phase, it first applies the incremental kernel patch to the base source, followed by the Surface-specific patches from the dedicated Surface archive.
3.  **Layered Configuration:** The `do_configure` step constructs the final kernel configuration by:
    *   Starting with a base architecture-specific `.config` file (e.g., `files/x86_64-dotconfig`). The PR discussion revealed a shift from symlinking this file from a generic kernel package to using a local copy within the `linux-surface` package to avoid synchronization issues.
    *   Overlaying/merging a Surface-specific configuration fragment using the kernel's `scripts/kconfig/merge_config.sh` script.
    *   Finalizing with `make oldconfig` and customizing `CONFIG_LOCALVERSION`.
4.  **Standard Compilation:** The `do_build` phase uses standard kernel `make` targets (`prepare`, `bzImage`, `modules`) after setting necessary `KBUILD_*` environment variables for reproducibility and clearing `LDFLAGS`.
5.  **Comprehensive Installation:** `do_install` handles the installation of the kernel image, modules, configuration, System.map, and kernel headers. It also incorporates a helper script (`mv-debug`) to process and segregate debug symbols for a separate debug package.
6.  **Subpackaging:** Defines `-headers` and `-dbg` subpackages for better modularity.
7.  **Package Naming & Restrictions:** The package was named `linux-surface` (not versioned in the name) and marked `restricted=yes` based on Void Linux policies and PR discussions.

## 2. Source Handling

*   **`distfiles` Usage:**
    *   `https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-${version%.*}.tar.xz`: Main kernel source tarball (e.g., `linux-5.13.tar.xz`).
    *   `https://cdn.kernel.org/pub/linux/kernel/v5.x/patch-${version}.xz`: Incremental patch for the specific kernel point release (e.g., `patch-5.13.13.xz`). Marked with `skip_extraction="patch-${version}.xz"`.
    *   `https://github.com/linux-surface/linux-surface/archive/refs/tags/arch-${version}-3.tar.gz>surface-linux.tar.gz`: Archive containing Surface-specific patches and configuration files. The tag `arch-${version}-3` (e.g., `arch-5.13.13-3`) points to a specific version from the `linux-surface` project. This is extracted to a directory like `linux-surface-arch-5.13.13-3`.

*   **`wrksrc` vs. `build_wrksrc`:**
    *   `build_wrksrc="linux-${version%.*}"` (e.g., `linux-5.13`): Specifies the directory name resulting from the extraction of the main kernel tarball.
    *   `wrksrc="linux-${version}-surface"` (e.g., `linux-5.13.13-surface`): The directory where `xbps-src` performs build steps. The PR template uses `create_wrksrc=yes`, implying `xbps-src` might create this directory and the `build_wrksrc` (kernel sources) are placed/extracted within it, or `build_wrksrc` is renamed/symlinked. The key is that operations occur in a unified source tree. Reviewer feedback in the PR emphasized correct `build_wrksrc` usage to avoid manual `cd` commands.

*   **Patch Application:**
    *   **Kernel Patch:** Applied in `pre_patch`: `xzcat $XBPS_SRCDISTDIR/$pkgname-${version}/patch-${version}.xz | patch -Np1`.
    *   **Surface Patches:** Applied after the kernel patch in `pre_patch`: `for i in ../linux-surface-arch-$minorVersion-3/patches/${majorVersion}/*.patch; do patch -Np1 < $i; done`. This iterates through patches in the extracted Surface archive, which is expected to be one level above the kernel source directory (`../`).

## 3. Configuration (`do_configure`)

*   **Base and Surface Config Combination:**
    1.  A base kernel configuration from `files/x86_64-dotconfig` is copied to `dotconfig.config` in `wrksrc`.
    2.  The Surface-specific config (e.g., `surface-${majorVersion}.config`) is copied from the extracted Surface archive (e.g., `../linux-surface-arch-$minorVersion-3/configs/surface-${majorVersion}.config` or as per template: `${wrksrc}/linux-surface-arch-$minorVersion-3/configs/surface-${majorVersion}.config`) to `surface-linux.config`. The PR template's path for the surface config (`${wrksrc}/linux-surface-arch...`) seems to assume the surface archive is extracted *inside* the `wrksrc`, which might differ from the patch application path. Consistency is needed here.
*   **`scripts/kconfig/merge_config.sh` Usage:**
    *   `export KCONFIG_CONFIG=${wrksrc}/${build_wrksrc}/.config` (from PR template). This path for `KCONFIG_CONFIG` appears overly complex. Typically, `merge_config.sh` operates on `.config` in the current directory or `KCONFIG_CONFIG` points directly to the target `.config` file.
    *   `./scripts/kconfig/merge_config.sh -m dotconfig.config surface-linux.config`. This merges `surface-linux.config` into `dotconfig.config`, with the output going to the file specified by `KCONFIG_CONFIG` (which should resolve to the final `.config`).
    *   `make ${makejobs} ARCH=$arch ${_cross} oldconfig` finalizes the `.config`.
*   **`CONFIG_LOCALVERSION` Setting:**
    *   `sed -i -e "s|^\(CONFIG_LOCALVERSION=\).*|\1\"_${revision}-surface\"|" .config` sets a unique local version.

## 4. Compilation (`do_build`)

*   **Compiler and Environment Handling:**
    *   Reproducibility variables: `KBUILD_BUILD_TIMESTAMP`, `KBUILD_BUILD_USER`, `KBUILD_BUILD_HOST`.
    *   Cross-compilation: `_cross="CROSS_COMPILE=${XBPS_CROSS_TRIPLET}-"`.
    *   `export LDFLAGS=` clears `LDFLAGS`.
*   **Key `make` Targets:**
    *   `make ARCH=$arch ${_cross} ${makejobs} prepare`
    *   `make ARCH=$arch ${_cross} ${makejobs} ${_args}` (where `_args` is `bzImage modules` for x86_64).

## 5. Dependency Management

*   **Void `hostmakedepends`:** `tar xz bc elfutils-devel flex gmp-devel kmod libmpc-devel openssl-devel perl uboot-mkimage cpio pahole python3`.
*   **Relevance for Chimera:** Most are standard. `elfutils-devel` (for `objtool`, `pahole`) is key. `pahole` itself (from `dwarves` package) is important for BTF. Musl-based systems like Chimera need to ensure these host tools build correctly.

## 6. Patching Strategy (Specific Patch)

*   **`srcpkgs/linux-surface/patches/fix-musl-objtool.patch`:**
    *   Modifies `tools/objtool/Makefile` by adding `-D__always_inline=inline` to `CFLAGS`.
    *   The patch comment states: "objtool is using the headers provided by kernel-libc-headers, which are kernel version 5.10, so they use __always_inline instead of inline, and musl doesn't define __always_inline (glibc does)".
    *   **Implication for musl:** Essential for building `objtool` correctly on musl-based host systems. Chimera must be vigilant for such host-tool patches.

## 7. Installation & Subpackages

*   **`do_install` (Key Steps):**
    *   `make ... modules_install`.
    *   Installs kernel image, `.config`, `System.map` to `/boot`.
    *   Installs headers to `/usr/src/kernel-headers-${_kernver}`. This involves copying many specific files and directories from the kernel source.
    *   Installs `objtool` binary to `${hdrdest}/tools/objtool/` for x86_64.
*   **`mv-debug` Helper Script (`srcpkgs/linux-surface/files/mv-debug`):**
    *   Used to separate debug symbols:
        ```sh
        #!/bin/sh
        mod=$1
        mkdir -p usr/lib/debug/${mod%/*}
        $OBJCOPY --only-keep-debug --compress-debug-sections $mod usr/lib/debug/$mod
        $OBJCOPY --add-gnu-debuglink=${DESTDIR}/usr/lib/debug/$mod $mod
        /usr/bin/$STRIP --strip-debug $mod
        gzip -9 $mod # This line is unusual for .ko files; likely an error or for other ELF files.
        ```
    *   The main kernel `vmlinux` is also copied to `/usr/lib/debug/boot/vmlinux-${_kernver}` for debugging.
*   **Subpackages:**
    *   `linux-surface-headers`: Kernel headers.
    *   `linux-surface-dbg`: Debug symbols and `System.map`.

## 8. Key Differences & Learnings for Chimera Linux Cport Generator

*   **Source Management:**
    *   Adopt multi-`distfiles` for clarity.
    *   Implement robust `build_wrksrc` logic. The Void template's `wrksrc="linux-${version}-surface"` and `build_wrksrc="linux-${version%.*}"` with `create_wrksrc=yes` is a good model.
*   **Patching:**
    *   Sequential application: kernel patch, then vendor patches.
    *   Prioritize musl-specific patches for host tools.
*   **Configuration:**
    *   Use local copies of base config files rather than symlinks to avoid sync issues (lesson from Void PR discussion).
    *   Carefully manage paths for `merge_config.sh` inputs and `KCONFIG_CONFIG`. The Void template's `KCONFIG_CONFIG=${wrksrc}/${build_wrksrc}/.config` might be simplified to just `.config` if operations are consistently within the correct working directory.
    *   Ensure consistent paths for accessing the extracted Surface archive contents (patches vs. config files). The `../` relative path for patches seems more standard if the surface archive is extracted alongside the kernel source.
*   **Compilation:**
    *   Set `KBUILD_*` variables. Clear `LDFLAGS`.
*   **Installation & Debugging:**
    *   A dedicated script like `mv-debug` is good practice. Re-evaluate the `gzip -9 $mod` line in `mv-debug`.
*   **Variable Naming & Consistency:** Use clear internal variables (e.g., `_kernver`).
*   **General Template Structure:** The Void template's structure for defining hooks (`pre_patch`, `do_configure`, etc.) and subpackages (`<pkgname>-headers_package()`) is a good reference.

This detailed analysis, informed by the PR's evolution and final state, should serve as a strong foundation for developing a robust Chimera Linux cport generator for `linux-surface` and similar kernel packages.