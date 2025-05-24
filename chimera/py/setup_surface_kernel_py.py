#!/usr/bin/env python3

import sys
import subprocess
import pathlib
import shutil
import re
import hashlib
import argparse
import textwrap # Added for indentation control
from typing import List, Dict, Tuple, Optional, Any

# --- Visuals (adapted from your terminal_animation_system.py) ---
COLORS: Dict[str, str] = {
    "pink": "\033[38;5;219m", "purple": "\033[38;5;183m", "cyan": "\033[38;5;123m",
    "yellow": "\033[38;5;228m", "blue": "\033[38;5;111m", "green": "\033[38;5;156m",
    "red": "\033[38;5;210m", "lavender": "\033[38;5;147m", "reset": "\033[0m",
}
STYLES: Dict[str, str] = {"bold": "\033[1m", "reset_style": "\033[22m\033[23m\033[24m\033[25m"}
STATUS_SYMBOLS: Dict[str, Tuple[str, str]] = {
    "success": ("✓", "green"), "warning": ("!", "yellow"), "error": ("✗", "red"),
    "info": ("✧", "cyan"), "progress": ("→", "blue"), "star": ("★", "purple")
}

def _color_text(text: str, color_name: Optional[str] = None, style_names: Optional[List[str]] = None) -> str:
    prefix = ""
    if color_name and color_name in COLORS:
        prefix += COLORS[color_name]
    if style_names:
        for style_name in style_names:
            if style_name in STYLES:
                prefix += STYLES[style_name]
    
    suffix = COLORS.get("reset", "\033[0m") 
    if prefix: 
        suffix += STYLES.get("reset_style", "\033[22m\033[23m\033[24m\033[25m") 
    else: 
        suffix = ""
    return f"{prefix}{text}{suffix}" if prefix else text

def _print_message(
    message: str,
    level: str = "info",
    indent: int = 0,
    message_styles: Optional[List[str]] = None
) -> None:
    symbol_info = STATUS_SYMBOLS.get(level)
    indent_str = "  " * indent
    styled_message = _color_text(message, style_names=message_styles)
    if symbol_info:
        symbol, color = symbol_info
        status_indicator = _color_text(f"[{symbol}]", color, style_names=["bold"])
        print(f"{indent_str}{status_indicator} {styled_message}")
    else:
        print(f"{indent_str}  {styled_message}")
    sys.stdout.flush()

# Kept for potential future use, but not directly used by the generator's core logic.
def run_external_command(
    command_list: List[str],
    cwd: Optional[pathlib.Path] = None,
    capture_output: bool = False,
    check: bool = True,
    shell: bool = False,
    env: Optional[Dict[str, str]] = None
) -> subprocess.CompletedProcess:
    cmd_to_run: Any = command_list
    if shell and isinstance(command_list, list):
        cmd_to_run = " ".join(command_list)
    
    _print_message(f"Executing in '{cwd or pathlib.Path.cwd()}': {cmd_to_run if isinstance(cmd_to_run, str) else ' '.join(cmd_to_run)}", level="progress", indent=1)
    try:
        process = subprocess.run(
            cmd_to_run,
            cwd=cwd,
            capture_output=capture_output,
            text=True,
            check=check,
            shell=shell,
            env=env
        )
        if capture_output:
            if process.stdout and process.stdout.strip(): _print_message(f"STDOUT:\n{process.stdout.strip()}", level="info", indent=2)
            if process.stderr and process.stderr.strip(): _print_message(f"STDERR:\n{process.stderr.strip()}", level="warning", indent=2)
        return process
    except FileNotFoundError:
        cmd_name = command_list[0] if not shell and command_list else str(cmd_to_run).split()[0]
        _print_message(f"Error: Command '{cmd_name}' not found.", level="error")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        _print_message(f"Error running command: {e.cmd}", level="error")
        if e.stdout and e.stdout.strip(): _print_message(f"STDOUT:\n{e.stdout.strip()}", level="error", indent=2)
        if e.stderr and e.stderr.strip(): _print_message(f"STDERR:\n{e.stderr.strip()}", level="error", indent=2)
        if check: raise
        return e # type: ignore
    except Exception as e_gen:
        _print_message(f"An unexpected error occurred running command: {e_gen}", level="error")
        raise

# --- Script Configuration ---
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT_FROM_SCRIPT = SCRIPT_DIR.parent.parent 

WORKSPACE_ROOT = PROJECT_ROOT_FROM_SCRIPT 
CPORTS_MAIN_DIR = WORKSPACE_ROOT / "chimera" / "cports" / "main"
LINUX_SURFACE_REPO_PATH = WORKSPACE_ROOT / "chimera" / "linux-surface"
DEFAULT_OUTPUT_CPORT_NAME = "linux-surface-generated"

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Chimera Linux cports template for linux-surface."
    )
    parser.add_argument(
        "--kernel-version",
        type=str,
        required=True,
        help="Target kernel version (e.g., '6.8.1'). This will be used as pkgver."
    )
    parser.add_argument(
        "--surface-archive-tag",
        type=str,
        required=True,
        help="Git tag or commit SHA for the linux-surface project archive (e.g., 'v6.8.1-arch1')."
    )
    parser.add_argument(
        "--kernel-stuff-path",
        type=pathlib.Path,
        default=None, 
        help="Optional path to a directory containing an Arch PKGBUILD (for makedepends) and base config files."
    )
    parser.add_argument(
        "--surface-configs-path",
        type=pathlib.Path,
        default=None, 
        help="Optional path to a directory containing surface-X.Y.config files if not using the archive."
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default=DEFAULT_OUTPUT_CPORT_NAME,
        help=f"Name for the new cport directory (default: {DEFAULT_OUTPUT_CPORT_NAME})"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing cport directory if it exists."
    )
    return parser.parse_args()

def calculate_sha256(file_path: pathlib.Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def parse_pkgbuild(pkgbuild_path: pathlib.Path) -> Dict[str, Any]:
    if not pkgbuild_path.is_file():
        _print_message(f"PKGBUILD not found at: {pkgbuild_path}", level="error")
        sys.exit(1)

    content = pkgbuild_path.read_text()
    data: Dict[str, Any] = {}

    pkgver_match = re.search(r"^\s*pkgver=([^\s#]+)", content, re.MULTILINE)
    if pkgver_match:
        original_pkgver_str = pkgver_match.group(1).strip().strip("'\"")
        data["pkgver_from_pkgbuild"] = original_pkgver_str 
    
    pkgrel_match = re.search(r"^\s*pkgrel=([^\s#]+)", content, re.MULTILINE)
    if pkgrel_match:
        data["pkgrel_from_pkgbuild"] = pkgrel_match.group(1).strip().strip("'\"") 

    if "pkgver_from_pkgbuild" in data:
        pkgver_for_srctag = data["pkgver_from_pkgbuild"]
        pkgver_parts_for_srctag = pkgver_for_srctag.split('.')
        if len(pkgver_parts_for_srctag) > 1 and not pkgver_parts_for_srctag[-1].isdigit(): 
            _fullver_pkb = f"{'.'.join(pkgver_parts_for_srctag[:-1])}-{pkgver_parts_for_srctag[-1]}"
        else: 
             _fullver_pkb = f"{'.'.join(pkgver_parts_for_srctag[:-1])}-{pkgver_parts_for_srctag[-1]}" if len(pkgver_parts_for_srctag) > 1 else pkgver_for_srctag

        srctag_match = re.search(r"^\s*_srctag=v([^\s#]+)", content, re.MULTILINE)
        if srctag_match:
            data["_srctag_from_pkgbuild"] = "v" + srctag_match.group(1).strip().strip("'\"").replace("${_fullver}", _fullver_pkb)
        else:
            data["_srctag_from_pkgbuild"] = f"v{_fullver_pkb}"

    makedepends_match = re.search(r"^\s*makedepends=\((.*?)\)", content, re.DOTALL | re.MULTILINE)
    if makedepends_match:
        deps_content_str = makedepends_match.group(1)
        parsed_deps = []
        for line in deps_content_str.splitlines():
            line_content_before_comment = line.split('#')[0].strip()
            if not line_content_before_comment:
                continue
            for potential_dep in line_content_before_comment.split():
                dep = potential_dep.strip().strip("'\"")
                if dep:
                    if re.match(r"^[a-zA-Z0-9_.+-]+$", dep):
                         parsed_deps.append(dep)
        data["makedepends"] = parsed_deps
        if not parsed_deps and deps_content_str.strip():
             _print_message(f"Warning: Parsed 'makedepends' as empty, but content was: {deps_content_str}", level="warning")
    else:
        data["makedepends"] = []
        _print_message("Could not parse 'makedepends' from PKGBUILD. Assuming empty.", level="warning")

    source_match = re.search(r"^\s*source=\((.*?)\)", content, re.DOTALL | re.MULTILINE)
    patch_filenames = []
    if source_match:
        sources_str = source_match.group(1)
        source_items = [item.split("::")[-1].split("#")[0].strip().strip("'\"") for item in sources_str.split()]
        patch_filenames = [item for item in source_items if item.endswith(".patch")]
    data["patch_filenames"] = patch_filenames
    
    return data

def sanitize_config_file(file_path: pathlib.Path) -> str:
    try:
        content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        _print_message(f"Warning: UTF-8 decode failed for {file_path.name}, trying latin-1", level="warning", indent=3)
        content = file_path.read_text(encoding='latin-1')
    
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    lines = []
    for line in content.splitlines():
        lines.append(line.rstrip())
    
    sanitized_content = '\n'.join(lines)
    if sanitized_content and not sanitized_content.endswith('\n'):
        sanitized_content += '\n'
    
    return sanitized_content

def setup_cport_directory(
    output_cport_name: str,
    force_overwrite: bool,
    kernel_stuff_dir: pathlib.Path,
    surface_configs_dir: pathlib.Path, 
    pkgbuild_data: Dict[str, Any],
    linux_surface_repo_base_path: pathlib.Path 
) -> Dict[str, str]:
    target_cport_path = CPORTS_MAIN_DIR / output_cport_name
    files_dir = target_cport_path / "files"
    patches_dir = target_cport_path / "patches" 

    if target_cport_path.exists():
        if force_overwrite:
            _print_message(f"Removing existing cport directory: {target_cport_path}", level="warning", indent=1)
            shutil.rmtree(target_cport_path)
        else:
            _print_message(f"Error: Cport directory {target_cport_path} already exists. Use --force to overwrite.", level="error")
            sys.exit(1)
    
    _print_message(f"Creating cport directory: {target_cport_path}", indent=1)
    target_cport_path.mkdir(parents=True)
    files_dir.mkdir()
    patches_dir.mkdir() 

    _print_message("Creating mv-debug.sh script...", indent=2)
    mv_debug_script_content = """#!/bin/sh
# mv-debug.sh - Helper to separate debug symbols for Chimera Linux

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <file_to_process>"
    exit 1
fi

mod="$1"
debugdir_base="usr/lib/debug"
mod_rel_path="${mod#./}"
mod_debug_path="${debugdir_base}/${mod_rel_path}"

OBJCOPY="${OBJCOPY:-llvm-objcopy}"
STRIP="${STRIP:-llvm-strip}"

if [ ! -f "$mod" ]; then
    echo "Error: File '$mod' not found!"
    exit 1
fi

echo "Processing '$mod' for debug symbols..."

mkdir -p "$(dirname "$mod_debug_path")"

if ! "$OBJCOPY" --only-keep-debug "$mod" "$mod_debug_path"; then
    echo "Error: $OBJCOPY --only-keep-debug failed for '$mod'"
    exit 1
fi

if ! "$OBJCOPY" --add-gnu-debuglink="$mod_debug_path" "$mod"; then
    echo "Error: $OBJCOPY --add-gnu-debuglink failed for '$mod' (linking to $mod_debug_path)"
    exit 1
fi

if ! "$STRIP" --strip-debug "$mod"; then
    echo "Error: $STRIP --strip-debug failed for '$mod'"
    exit 1
fi

compressed_debug_path=""
if command -v xz > /dev/null; then
    if xz -T0 -zc "$mod_debug_path" > "${mod_debug_path}.xz"; then
        rm "$mod_debug_path"
        compressed_debug_path="${mod_debug_path}.xz"
        echo "Compressed debug symbols to '${compressed_debug_path}'"
    else
        echo "Warning: xz compression failed for '$mod_debug_path'. Leaving uncompressed."
    fi
elif command -v gzip > /dev/null; then
    if gzip -9nf "$mod_debug_path"; then
        compressed_debug_path="${mod_debug_path}.gz"
        echo "Compressed debug symbols to '${compressed_debug_path}'"
    else
        echo "Warning: gzip compression failed for '$mod_debug_path'. Leaving uncompressed."
    fi
else
    echo "Warning: No xz or gzip found. Debug symbols for '$mod' will not be compressed."
fi

if [ -n "$compressed_debug_path" ] && [ "$compressed_debug_path" != "$mod_debug_path" ]; then
    echo "Updating debug link in '$mod' to point to '${compressed_debug_path}'"
    if ! "$OBJCOPY" --strip-gnu-debuglink "$mod"; then
        echo "Warning: Failed to strip old gnu-debuglink from '$mod'. Link update might be problematic."
    fi
    if ! "$OBJCOPY" --add-gnu-debuglink="$compressed_debug_path" "$mod"; then
        echo "Error: $OBJCOPY --add-gnu-debuglink failed for '$mod' (linking to ${compressed_debug_path})"
        exit 1
    fi
fi

echo "Successfully processed '$mod'. Debug symbols in '${compressed_debug_path:-$mod_debug_path}'"
"""
    mv_debug_script_path = files_dir / "mv-debug.sh"
    mv_debug_script_path.write_text(mv_debug_script_content)
    mv_debug_script_path.chmod(0o755)
    _print_message(f"mv-debug.sh created at {mv_debug_script_path}", indent=3)

    _print_message("Copying and sanitizing configuration files...", indent=2)
    
    if kernel_stuff_dir and (kernel_stuff_dir / "config").is_file():
        copy_and_sanitize_config(kernel_stuff_dir / "config", files_dir / "config.x86_64") 
        _print_message(f"Copied base config from {kernel_stuff_dir / 'config'} to files/config.x86_64", indent=3)
    elif kernel_stuff_dir: 
        _print_message(f"Base 'config' not found in {kernel_stuff_dir}. Template will need a placeholder or manual addition.", level="warning", indent=3)
    else: 
        _print_message("kernel_stuff_path not provided. Base 'config' will not be copied. Template will need a placeholder or manual addition.", level="info", indent=3)
        
    if surface_configs_dir: 
        _print_message(f"Note: --surface-configs-path ('{surface_configs_dir}') was provided, but surface configs are now intended to be sourced from the downloaded archive by the template.py.", level="info", indent=3)

    _print_message("Setting up 'patches/' directory for auto-applied critical patches (e.g., musl fixes)...", indent=2)
    
    musl_patch_content = """--- a/tools/objtool/Makefile
+++ b/tools/objtool/Makefile
@@ -30,7 +30,7 @@
 INCLUDES := -I$(srctree)/tools/include \\
 	    -I$(srctree)/tools/objtool/include \\
 	    -I$(srctree)/tools/objtool/arch/$(SRCARCH)/include
-CFLAGS   := -Werror $(WARNINGS) $(KBUILD_HOSTCFLAGS) -g $(INCLUDES) $(LIBELF_FLAGS)
+CFLAGS   := -Werror $(WARNINGS) $(KBUILD_HOSTCFLAGS) -g $(INCLUDES) $(LIBELF_FLAGS) -D__always_inline=inline
 LDFLAGS  += $(LIBELF_LIBS) $(LIBSUBCMD) $(KBUILD_HOSTLDFLAGS)
"""
    musl_patch_path = patches_dir / "0001-fix-musl-objtool.patch"
    musl_patch_path.write_text(musl_patch_content)
    _print_message(f"Created placeholder musl fix patch: {musl_patch_path}", indent=3)

    file_checksums = { 
        "mv-debug.sh": calculate_sha256(mv_debug_script_path),
        "0001-fix-musl-objtool.patch": calculate_sha256(musl_patch_path),
    }
    if (files_dir / "config.x86_64").exists():
        file_checksums["config.x86_64"] = calculate_sha256(files_dir / "config.x86_64")
        
    return file_checksums

def generate_template_py_content(
    output_cport_name: str,
    pkgbuild_data: Dict[str, Any],
    file_checksums: Dict[str, str]
) -> str:
    pkgver = pkgbuild_data["pkgver"] 
    pkgrel = pkgbuild_data["pkgrel"] 
    surface_archive_tag = pkgbuild_data["surface_archive_tag"] 

    kernel_major_minor_parts = pkgver.split('.')
    kernel_major = kernel_major_minor_parts[0]
    kernel_major_minor = f"{kernel_major_minor_parts[0]}.{kernel_major_minor_parts[1]}"

    chimera_hostmakedepends = ["base-kernel-devel"]
    pkgb_makedepends = pkgbuild_data.get("makedepends", [])
    if "bc" in pkgb_makedepends and "bc-gh" not in chimera_hostmakedepends:
        chimera_hostmakedepends.append("bc-gh") 
    if "git" in pkgb_makedepends and "git" not in chimera_hostmakedepends:
        chimera_hostmakedepends.append("git")
    common_kernel_deps = ["elfutils-devel", "openssl-devel", "perl", "flex", "bison", "kmod-devel", "python"]
    for dep in common_kernel_deps:
        if dep not in chimera_hostmakedepends:
            chimera_hostmakedepends.append(dep)
    
    hostmakedepends_list_str = ", ".join([f'"{dep}"' for dep in sorted(list(set(chimera_hostmakedepends)))])

    sha256_kernel_tar = "SHA256_LINUX_TAR_XZ_PLACEHOLDER"
    sha256_kernel_patch = "SHA256_LINUX_PATCH_XZ_PLACEHOLDER"
    sha256_surface_archive = "SHA256_SURFACE_ARCHIVE_PLACEHOLDER"

    make_env_block_raw = """
make_env = {
    "KBUILD_BUILD_USER": "chimera",
    "KBUILD_BUILD_HOST": "chimera.linux",
    # Standard toolchain vars, cbuild usually sets these via tool_flags or profile
    # "HOSTCC": "clang",
    # "CC": "clang",
    # "LD": "ld.lld",
    # "AR": "llvm-ar",
    # "NM": "llvm-nm",
    # "OBJCOPY": "llvm-objcopy",
    # "OBJDUMP": "llvm-objdump",
    "LDFLAGS": "", # Explicitly clear LDFLAGS for kernel build
}"""
    # Dedent to remove common leading whitespace from the raw block,
    # then strip leading/trailing newlines that dedent might leave from the triple quotes,
    # then indent the whole block by 4 spaces for proper placement in template.py.
    processed_make_env_block = textwrap.indent(textwrap.dedent(make_env_block_raw).strip(), "    ")

    template_str = f"""\
# Auto-generated by setup_surface_kernel_py.py

pkgname = "{output_cport_name}"
pkgver = "{pkgver}" # e.g., 6.8.1
pkgrel = {pkgrel} # e.g., 0
pkgdesc = f"Linux kernel ({kernel_major_minor} series) with Surface patches"
archs = ["x86_64"]
license = "GPL-2.0-only"
url = "https://github.com/linux-surface/linux-surface"
build_wrksrc = f"linux-{kernel_major_minor}" # From kernel.org tarball
# wrksrc will be default (pkgname-pkgver), cbuild handles this

source = [
    # 1. Base kernel from kernel.org
    f"https://cdn.kernel.org/pub/linux/kernel/v{kernel_major}.x/linux-{kernel_major_minor}.tar.xz",
    # 2. Incremental patch from kernel.org (for the specific pkgver)
    f"https://cdn.kernel.org/pub/linux/kernel/v{kernel_major}.x/patch-{pkgver}.xz",
    # 3. Surface patches/configs archive from linux-surface GitHub
    f"https://github.com/linux-surface/linux-surface/archive/refs/tags/{surface_archive_tag}.tar.gz>{{pkgname}}-{surface_archive_tag}-surface-sources.tar.gz"
]
sha256 = [
    "{sha256_kernel_tar}", # For linux-{kernel_major_minor}.tar.xz
    "{sha256_kernel_patch}", # For patch-{pkgver}.xz
    "{sha256_surface_archive}"  # For {{pkgname}}-{surface_archive_tag}-surface-sources.tar.gz
]
skip_extraction = [f"patch-{pkgver}.xz"] # Apply this manually

hostmakedepends = [
    {hostmakedepends_list_str},
]
depends = ["base-kernel"]
provides = [f"linux={{pkgver.split('.')[0]}}.{{pkgver.split('.')[1]}}"]

options = [
    "!check", "!debug", "!strip", "!scanrundeps", "!scanshlibs", "!lto",
    "textrels", "execstack", "foreignelf"
]
# Default make_env for kernel builds
# KBUILD_BUILD_TIMESTAMP is often set by cbuild itself via self.source_date_epoch_bsd
# but can be made explicit if needed.
{processed_make_env_block}
# Add KBUILD_BUILD_TIMESTAMP using self.source_date_epoch_bsd
# This needs to be done carefully as self is not available at template string definition time.
# It's better to set this in the hooks directly:
# env_for_make = {{**self.make_env, "KBUILD_BUILD_TIMESTAMP": self.source_date_epoch_bsd}}
# And then pass env=env_for_make to self.do("make", ..., env=env_for_make)

def prepare(self):
    with self.pushd(self.build_wrksrc):
        self.log("Setting localversion files...")
        self.do("sh", "-c", f"echo '-{{self.pkgrel}}' > localversion.10-pkgrel")
        self.do("sh", "-c", f"echo '{{self.pkgname.replace('linux-', '')}}' > localversion.20-pkgname")

        _make_vars = [
            "HOSTCC=clang", "CC=clang", "LD=ld.lld",
            "AR=llvm-ar", "NM=llvm-nm", "OBJCOPY=llvm-objcopy", "OBJDUMP=llvm-objdump"
        ]

        self.log("Running make defconfig...")
        self.do("make", *_make_vars, "defconfig")

        self.log("Running make kernelrelease and creating version file...")
        self.do("sh", "-c", f"make {{' '.join(_make_vars)}} -s kernelrelease > version")

        kernelrelease_content_out = self.do("cat", "version", capture_output=True, check=True)
        kernelrelease = kernelrelease_content_out.stdout.strip() 
        self.log(f"Kernel release from version file: {{kernelrelease}}") 

        self.log("Running make mrproper...")
        self.do("make", *_make_vars, "mrproper")

        self.log("Applying patches...")
        if not (self.chroot_cwd / ".git").is_dir():
            self.do("git", "init")
            self.do("git", "config", "--local", "user.email", "cbuild@chimera-linux.org")
            self.do("git", "config", "--local", "user.name", "cbuild")
            self.do("git", "add", ".")
            self.do("git", "commit", "--allow-empty", "-m", "Initial cbuild commit before patching")

        surface_patches_dir = self.cwd / "surface_patches"
        if surface_patches_dir.is_dir():
            patch_file_host_paths = sorted(list(surface_patches_dir.glob("*.patch")))
            if not patch_file_host_paths:
                self.log_warn(f"No .patch files found in {{surface_patches_dir}}")
            for host_patch_file in patch_file_host_paths:
                self.log(f"Applying patch {{host_patch_file.name}}...")
                self.do(
                    "git", "am", "-3",
                    f"/tmp/{{host_patch_file.name}}",
                    tmpfiles=[host_patch_file]
                )
        else:
            self.log_warn(f"Surface patches directory not found: {{surface_patches_dir}}")

        self.log("Merging kernel configurations...")
        host_config_file = self.files_path / "config"
        host_surface_config_file = self.files_path / "surface.config"
        host_arch_config_file = self.files_path / "arch.config"

        chroot_config_path = f"/tmp/{{host_config_file.name}}"
        chroot_surface_config_path = f"/tmp/{{host_surface_config_file.name}}"
        chroot_arch_config_path = f"/tmp/{{host_arch_config_file.name}}"
        
        self.do("cp", chroot_config_path, ".config.base", 
                tmpfiles=[host_config_file])
        self.do("cp", chroot_surface_config_path, ".config.surface", 
                tmpfiles=[host_surface_config_file])
        self.do("cp", chroot_arch_config_path, ".config.arch", 
                tmpfiles=[host_arch_config_file])
        
        try:
            self.do("./scripts/kconfig/merge_config.sh", "-m", 
                    ".config.base", ".config.surface", ".config.arch")
        except Exception as e:
            self.log_warn(f"merge_config.sh failed, trying manual merge: {{e}}")
            self.do("cp", ".config.base", ".config")
            self.do("sh", "-c", "cat .config.surface >> .config")
            self.do("sh", "-c", "cat .config.arch >> .config")

        self.log("Running make olddefconfig...")
        self.do("make", *_make_vars, f"KERNELRELEASE={{kernelrelease}}", "olddefconfig") 
        self.log(f"Prepared {{self.pkgname}} version {{kernelrelease}}") 

def build(self):
    _make_vars = [ 
        "HOSTCC=clang", "CC=clang", "LD=ld.lld",
        "AR=llvm-ar", "NM=llvm-nm", "OBJCOPY=llvm-objcopy", "OBJDUMP=llvm-objdump"
    ]
    with self.pushd(self.build_wrksrc):
        kernelrelease = (self.chroot_cwd / "version").read_text().strip()
        self.log(f"Building kernel version {{kernelrelease}}") 
        self.do("make", *_make_vars, f"KERNELRELEASE={{kernelrelease}}", "all") 

def install(self):
    with self.pushd(self.build_wrksrc):
        kernelrelease = (self.chroot_cwd / "version").read_text().strip() 
        self.log(f"Installing kernel version {{kernelrelease}}") 
        
        modulesdir = self.destdir / f"usr/lib/modules/{{kernelrelease}}" 
        image_name_out = self.do("make", "-s", "image_name", capture_output=True, check=True)
        image_name = image_name_out.stdout.strip()

        self.install_dir(modulesdir)
        self.install_file(self.chroot_cwd / image_name, modulesdir, name="vmlinuz", mode=0o644)
        (modulesdir / "pkgbase").write_text(self.pkgname + "\\n")

        self.log("Installing modules...")
        self.do(
            "make",
            f"INSTALL_MOD_PATH={{self.chroot_destdir / 'usr'}}",
            "DEPMOD=/doesnt/exist",
            "modules_install"
        )

        self.rm(modulesdir / "build", force=True, recursive=True)
        self.rm(modulesdir / "source", force=True, recursive=True)

        self.log("Installing files for -devel package...")
        builddir_target = modulesdir / "build"
        self.install_dir(builddir_target)

        for f_name in [".config", "Makefile", "Module.symvers", "System.map", "version", "vmlinux"]:
            f_path = self.chroot_cwd / f_name
            if f_path.exists():
                self.install_file(f_path, builddir_target, mode=0o644)
        
        for f_path_glob in self.chroot_cwd.glob("localversion.*"):
             if f_path_glob.is_file():
                self.install_file(f_path_glob, builddir_target, mode=0o644)

        kernel_makefile_path = self.chroot_cwd / "kernel" / "Makefile"
        if kernel_makefile_path.exists():
            self.install_dir(builddir_target / "kernel")
            self.install_file(kernel_makefile_path, builddir_target / "kernel", mode=0o644)
        
        arch_makefile_path = self.chroot_cwd / "arch" / "x86" / "Makefile"
        if arch_makefile_path.exists():
            self.install_dir(builddir_target / "arch" / "x86")
            self.install_file(arch_makefile_path, builddir_target / "arch" / "x86", mode=0o644)

        for d_name in ["scripts", "include"]:
            src_d = self.chroot_cwd / d_name
            if src_d.is_dir():
                self.cp(src_d, builddir_target / d_name, recursive=True, symlinks=True)
        
        arch_include_path = self.chroot_cwd / "arch" / "x86" / "include"
        if arch_include_path.is_dir():
             self.cp(arch_include_path, builddir_target / "arch" / "x86" / "include", recursive=True, symlinks=True)
        
        self.log("Installing Kconfig files...")
        for kconfig_file in self.chroot_cwd.glob("**/Kconfig*"):
            if kconfig_file.is_file():
                rel_path = kconfig_file.relative_to(self.chroot_cwd)
                target_kconfig_path = builddir_target / rel_path
                self.install_dir(target_kconfig_path.parent)
                self.install_file(kconfig_file, target_kconfig_path.parent, name=kconfig_file.name, mode=0o644)
        
        self.log("Setting up /usr/src symlink...")
        self.install_dir(self.destdir / "usr/src")
        self.ln_s(f"../lib/modules/{{kernelrelease}}/build", self.destdir / f"usr/src/{{self.pkgname}}", relative=True) 

@subpackage(f"{{pkgname}}-devel")
def _(self):
    self.pkgdesc = f"{{pkgdesc}} (development files)"
    self.depends += ["clang", "pahole"]
    self.options = ["foreignelf", "execstack", "!scanshlibs"]
    
    kernelrelease_real = ""
    if hasattr(self.parent, 'destdir') and (self.parent.destdir / "usr/lib/modules").exists():
        module_paths = list((self.parent.destdir / "usr/lib/modules").glob("*"))
        if module_paths:
            kernelrelease_real = module_paths[0].name
    
    if not kernelrelease_real:
        self.log_warn(f"Warning: Could not reliably determine kernelrelease for -devel subpackage paths during this phase. Using pkgver: {{self.parent.pkgver}}")

    if kernelrelease_real:
        return [
            f"usr/lib/modules/{{kernelrelease_real}}/build",
            f"usr/src/{{self.pkgname}}"
        ]
    return []
"""
    return template_str

def main() -> None:
    _print_message("--- Linux Surface Cports Template Generator ---", message_styles=["bold", "purple"])
    args = parse_arguments()

    # --- Versioning and Source Information ---
    # Primary versioning from command line arguments
    pkgver_main = args.kernel_version
    pkgrel_main = "0" # Default pkgrel, can be made an argument later if needed
    surface_archive_tag_main = args.surface_archive_tag

    _print_message(f"Target Kernel Version: {pkgver_main}", indent=1)
    _print_message(f"Target Pkgrel: {pkgrel_main}", indent=1)
    _print_message(f"Surface Archive Tag: {surface_archive_tag_main}", indent=1)

    pkgbuild_data_main: Dict[str, Any] = {
        "pkgver": pkgver_main,
        "pkgrel": pkgrel_main,
        "surface_archive_tag": surface_archive_tag_main,
        "makedepends": [], # Initialize, will be populated if PKGBUILD is parsed
        "patch_filenames": [] # Initialize, will be populated if PKGBUILD is parsed (though patch sourcing will change)
    }

    if args.kernel_stuff_path and args.kernel_stuff_path.is_dir():
        _print_message(f"Optional: Reading PKGBUILD from {args.kernel_stuff_path} for makedepends...", message_styles=["bold"], indent=1)
        pkgbuild_file_path = args.kernel_stuff_path / "PKGBUILD"
        if pkgbuild_file_path.is_file():
            parsed_data_from_pkgb = parse_pkgbuild(pkgbuild_file_path)
            pkgbuild_data_main["makedepends"] = parsed_data_from_pkgb.get("makedepends", [])
            pkgbuild_data_main["patch_filenames_from_pkgbuild"] = parsed_data_from_pkgb.get("patch_filenames", [])
            _print_message(f"  Found {len(pkgbuild_data_main['makedepends'])} makedepends.", indent=2)
            _print_message(f"  Found {len(pkgbuild_data_main.get('patch_filenames_from_pkgbuild',[]))} patches listed in PKGBUILD (for reference).", indent=2)
        else:
            _print_message(f"  PKGBUILD not found in {args.kernel_stuff_path}. Skipping.", level="warning", indent=2)
    elif args.kernel_stuff_path: # Path provided but not a dir
         _print_message(f"Warning: kernel_stuff_path '{args.kernel_stuff_path}' not found or not a directory. Skipping PKGBUILD parsing.", level="warning", indent=1)


    # Validate other paths if they are still mandatory or used
    if args.surface_configs_path and not args.surface_configs_path.is_dir():
        _print_message(f"Warning: surface_configs_path '{args.surface_configs_path}' not found or not a directory.", level="warning")
    
    if not LINUX_SURFACE_REPO_PATH.is_dir() and pkgbuild_data_main.get("patch_filenames_from_pkgbuild"): 
        _print_message(f"Error: Linux Surface repository not found at '{LINUX_SURFACE_REPO_PATH}', which might be needed for PKGBUILD-listed patches. Please ensure it's cloned correctly or remove patch references if sourcing differently.", level="error")
        sys.exit(1)


    _print_message("Step 2: Setting up cport directory and files...", message_styles=["bold"])
    file_checksums = setup_cport_directory(
        args.output_name,
        args.force,
        args.kernel_stuff_path, 
        args.surface_configs_path, 
        pkgbuild_data_main, 
        LINUX_SURFACE_REPO_PATH 
    )
    _print_message("Cport directory and files prepared.", level="success", indent=1)

    _print_message("Step 3: Generating template.py content...", message_styles=["bold"])
    template_content = generate_template_py_content(args.output_name, pkgbuild_data_main, file_checksums)
    _print_message("template.py content generated.", indent=1)

    _print_message("Step 4: Writing template.py...", message_styles=["bold"])
    target_template_py_path = CPORTS_MAIN_DIR / args.output_name / "template.py"
    try:
        target_template_py_path.write_text(template_content)
        _print_message(f"Successfully wrote template.py to: {target_template_py_path}", level="success", indent=1)
    except IOError as e:
        _print_message(f"Error writing template.py: {e}", level="error")
        sys.exit(1)
    
    _print_message("Step 5: Creating subpackage symlinks...", message_styles=["bold"])
    devel_subpackage_name = f"{args.output_name}-devel"
    symlink_path = CPORTS_MAIN_DIR / devel_subpackage_name
    target_dir_for_symlink = pathlib.Path(args.output_name)

    if symlink_path.exists() or symlink_path.is_symlink():
        if args.force:
            _print_message(f"Removing existing devel subpackage symlink: {symlink_path}", level="warning", indent=1)
            symlink_path.unlink(missing_ok=True)
        else:
            if not symlink_path.is_symlink() or symlink_path.resolve() != (CPORTS_MAIN_DIR / args.output_name).resolve():
                 _print_message(f"Warning: Devel subpackage symlink {symlink_path} exists but seems incorrect. Consider using --force.", level="warning", indent=1)
            else:
                _print_message(f"Devel subpackage symlink {symlink_path} already exists and is correct.", indent=1)

    if not symlink_path.exists():
        try:
            symlink_path.symlink_to(target_dir_for_symlink, target_is_directory=True)
            _print_message(f"Created symlink for -devel subpackage: {symlink_path} -> {target_dir_for_symlink}", level="success", indent=1)
        except OSError as e:
            _print_message(f"Error creating symlink for -devel subpackage: {e}", level="error", indent=1)
            _print_message("You might need to run 'cbuild relink-subpkgs' manually in the cports directory.", level="info", indent=1)
    
    print("-" * 60)
    _print_message("--- Generation Complete! ---", level="star", message_styles=["bold"])
    _print_message(f"New cport template for '{args.output_name}' created at:", indent=1)
    _print_message(f"  {CPORTS_MAIN_DIR / args.output_name}", indent=2, message_styles=["cyan"])
    _print_message("IMPORTANT: You need to update the 'sha256' list in the generated template.py:", level="warning", indent=1)
    _print_message(f"  The 'sha256' list has three placeholder entries corresponding to the three URLs in the 'source' list:", indent=2)
    _print_message(f"    1. Kernel.org base tarball (e.g., linux-{pkgbuild_data_main['pkgver'].split('.')[0]}.{pkgbuild_data_main['pkgver'].split('.')[1]}.tar.xz)", indent=3)
    _print_message(f"    2. Kernel.org incremental patch (e.g., patch-{pkgbuild_data_main['pkgver']}.xz)", indent=3)
    _print_message(f"    3. Linux-surface archive (e.g., {args.output_name}-{pkgbuild_data_main['surface_archive_tag']}-surface-sources.tar.gz)", indent=3)
    _print_message(f"  To get the checksums:", indent=2)
    _print_message(f"    a. Run: ./cbuild fetch main/{args.output_name}", indent=3)
    _print_message(f"    b. cbuild will download the files and print their SHA256 checksums (it might error if placeholders are still in use).", indent=3)
    _print_message(f"    c. Edit '{target_template_py_path}' and replace the placeholders in the 'sha256' list with the correct checksums in the correct order.", indent=3)
    _print_message("After updating the checksums, you can build the kernel with:", indent=1)
    _print_message(f"  ./cbuild pkg main/{args.output_name}", indent=2, message_styles=["green", "bold"])
    print("-" * 60)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _print_message(f"An unexpected script error occurred: {e}", level="error")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print(COLORS.get("reset", "\033[0m"))