#!/usr/bin/env python3

import sys
import subprocess
import pathlib
import shutil
import re
import hashlib
import argparse
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
# SCRIPT_DIR is the directory containing this script (e.g., .../scripts/chimera/py)
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
# PROJECT_ROOT_FROM_SCRIPT should be the 'scripts' directory level
PROJECT_ROOT_FROM_SCRIPT = SCRIPT_DIR.parent.parent # Up from py, up from chimera

WORKSPACE_ROOT = PROJECT_ROOT_FROM_SCRIPT # This is the intended root for relative paths like "chimera/cports"
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
        default=None, # Made optional, new args take precedence for versioning
        help="Optional path to a directory containing an Arch PKGBUILD (for makedepends) and base config files."
    )
    parser.add_argument(
        "--surface-configs-path",
        type=pathlib.Path,
        default=None, # Made optional, configs should ideally come from the surface archive
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
        # data["original_pkgver"] = original_pkgver_str # Keep for _srctag logic
        # # Sanitize pkgver for template.py (apk format: X.Y.Z)
        # sanitized_pkgver_match = re.match(r"(\d+\.\d+(\.\d+)?)", original_pkgver_str)
        # if sanitized_pkgver_match:
        #     data["pkgver"] = sanitized_pkgver_match.group(1) # This will be overridden by args.kernel_version
        # else:
        #     _print_message(f"Could not sanitize 'pkgver': {original_pkgver_str}", level="error")
        #     sys.exit(1)
        data["pkgver_from_pkgbuild"] = original_pkgver_str # Store for potential use if needed
    # else:
        # _print_message("Could not parse 'pkgver' from PKGBUILD.", level="error") # No longer fatal if PKGBUILD is optional
        # sys.exit(1)

    pkgrel_match = re.search(r"^\s*pkgrel=([^\s#]+)", content, re.MULTILINE)
    if pkgrel_match:
        data["pkgrel_from_pkgbuild"] = pkgrel_match.group(1).strip().strip("'\"") # Store for potential use
    # else:
        # _print_message("Could not parse 'pkgrel' from PKGBUILD.", level="error") # No longer fatal
        # sys.exit(1)

    # _srctag logic might be removed or changed as we source from kernel.org
    # For now, keep it if PKGBUILD is parsed, but it won't be the primary source for URLs
    if "pkgver_from_pkgbuild" in data:
        pkgver_for_srctag = data["pkgver_from_pkgbuild"]
        pkgver_parts_for_srctag = pkgver_for_srctag.split('.')
        if len(pkgver_parts_for_srctag) > 1 and not pkgver_parts_for_srctag[-1].isdigit(): # like .arch1
            _fullver_pkb = f"{'.'.join(pkgver_parts_for_srctag[:-1])}-{pkgver_parts_for_srctag[-1]}"
        else: # like .2
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
    """
    Read and sanitize a kernel config file to ensure it's compatible with merge_config.sh
    """
    try:
        # Try reading as UTF-8 first
        content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        # Fallback for files that might have non-UTF-8 chars
        _print_message(f"Warning: UTF-8 decode failed for {file_path.name}, trying latin-1", level="warning", indent=3)
        content = file_path.read_text(encoding='latin-1')
    
    # Normalize line endings to Unix LF
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove any trailing whitespace from lines and ensure file ends with newline
    lines = []
    for line in content.splitlines():
        # Remove trailing whitespace but preserve the line structure
        lines.append(line.rstrip())
    
    # Ensure the file ends with a single newline
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
    # Note: We'll move patches to a different directory to avoid automatic application
    surface_patches_dir = target_cport_path / "surface_patches"

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
    surface_patches_dir.mkdir()  # Use custom name to avoid cbuild auto-patch

    # Create mv-debug.sh script in files_dir
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

    # Copy and sanitize config files
    _print_message("Copying and sanitizing configuration files...", indent=2)
    
    def copy_and_sanitize_config(src_path: pathlib.Path, dest_path: pathlib.Path):
        """Copy and sanitize config files to prevent sed errors"""
        _print_message(f"Processing {src_path.name}...", indent=3)
        
        sanitized_content = sanitize_config_file(src_path)
        
        # Write the sanitized content as UTF-8
        dest_path.write_text(sanitized_content, encoding='utf-8')
        
        # Preserve original file permissions
        shutil.copymode(src_path, dest_path)

    copy_and_sanitize_config(kernel_stuff_dir / "config", files_dir / "config")
    copy_and_sanitize_config(kernel_stuff_dir / "arch.config", files_dir / "arch.config")

    pkgver = pkgbuild_data["pkgver"]
    kernel_major_minor = ".".join(pkgver.split(".")[:2])
    
    surface_config_name = f"surface-{kernel_major_minor}.config"
    surface_config_source_path = surface_configs_dir / surface_config_name
    if not surface_config_source_path.is_file():
        found_configs = list(surface_configs_dir.glob(f"surface-{kernel_major_minor}*.config"))
        if not found_configs:
             _print_message(f"Error: Surface config '{surface_config_name}' (or similar for {kernel_major_minor}) not found in {surface_configs_dir}", level="error")
             sys.exit(1)
        surface_config_source_path = found_configs[0]
        _print_message(f"Using surface config: {surface_config_source_path.name}", level="info", indent=3)

    copy_and_sanitize_config(surface_config_source_path, files_dir / "surface.config")

    # Copy patch files to surface_patches/ instead of patches/
    _print_message("Copying patch files...", indent=2)
    kernel_series_for_patches = kernel_major_minor
    source_patches_dir = linux_surface_repo_base_path / "patches" / kernel_series_for_patches
    
    if not source_patches_dir.is_dir():
        _print_message(f"Error: Patches directory not found for series {kernel_series_for_patches} at {source_patches_dir}", level="error")
        sys.exit(1)

    for patch_filename in pkgbuild_data["patch_filenames"]:
        source_patch_path = source_patches_dir / patch_filename
        if source_patch_path.is_file():
            shutil.copy2(source_patch_path, surface_patches_dir / patch_filename)
            _print_message(f"Copied patch: {patch_filename}", indent=3)
        else:
            _print_message(f"Warning: Patch file '{patch_filename}' not found in {source_patches_dir}", level="warning", indent=3)

    # Calculate checksums for files in files/
    file_checksums = { # For files managed by the generator script itself
        "mv-debug.sh": calculate_sha256(mv_debug_script_path),
        "0001-fix-musl-objtool.patch": calculate_sha256(musl_patch_path),
    }
    # Base config is now named config.x86_64
    if (files_dir / "config.x86_64").exists():
        file_checksums["config.x86_64"] = calculate_sha256(files_dir / "config.x86_64")
    # surface.config and arch.config are no longer copied by this script to files/
        
    return file_checksums

def generate_template_py_content(
    output_cport_name: str,
    pkgbuild_data: Dict[str, Any],
    file_checksums: Dict[str, str]
) -> str:
    pkgver = pkgbuild_data["pkgver"] # Now from args.kernel_version
    pkgrel = pkgbuild_data["pkgrel"] # Now from args or defaulted to 0
    surface_archive_tag = pkgbuild_data["surface_archive_tag"] # New, from args

    # Determine major.minor for kernel.org URL
    kernel_major_minor_parts = pkgver.split('.')
    kernel_major = kernel_major_minor_parts[0]
    kernel_major_minor = f"{kernel_major_minor_parts[0]}.{kernel_major_minor_parts[1]}"

    chimera_hostmakedepends = ["base-kernel-devel"]
    # makedepends are now conditionally parsed from PKGBUILD
    pkgb_makedepends = pkgbuild_data.get("makedepends", [])
    if "bc" in pkgb_makedepends and "bc-gh" not in chimera_hostmakedepends:
        chimera_hostmakedepends.append("bc-gh") # bc-gh is Chimera's bc
    if "git" in pkgb_makedepends and "git" not in chimera_hostmakedepends:
        chimera_hostmakedepends.append("git")
    # Add other common kernel build deps based on Void analysis / Chimera conventions
    common_kernel_deps = ["elfutils-devel", "openssl-devel", "perl", "flex", "bison", "kmod-devel", "python"]
    for dep in common_kernel_deps:
        if dep not in chimera_hostmakedepends:
            chimera_hostmakedepends.append(dep)
    
    hostmakedepends_list_str = ", ".join([f'"{dep}"' for dep in sorted(list(set(chimera_hostmakedepends)))])

    # Placeholder for checksums - these will need to be updated by the user
    sha256_kernel_tar = "SHA256_LINUX_TAR_XZ_PLACEHOLDER"
    sha256_kernel_patch = "SHA256_LINUX_PATCH_XZ_PLACEHOLDER"
    sha256_surface_archive = "SHA256_SURFACE_ARCHIVE_PLACEHOLDER"

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
}
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
        # Construct the make command string within the template's execution context
        # _make_vars is a Python list defined within the generated prepare()
        # We need to generate Python code that joins it and then uses it in an f-string for self.do
        # This will be an f-string within an f-string.
        # The _make_vars list is defined in the generated template's prepare() scope.
        # We need to generate Python code that constructs the shell command string
        # at template execution time.
        # Generated Python lines will be:
        #   make_cmd_list_for_kr = ["make"] + _make_vars + ["-s", "kernelrelease"]
        #   shell_cmd_for_kr = " ".join(make_cmd_list_for_kr) + " > version"
        #   self.do("sh", "-c", shell_cmd_for_kr)
        # This needs to be written as a multi-line string or escaped correctly.
        # Let's generate the direct shell command string, ensuring that the Python list _make_vars
        # is joined correctly *within the generated template's execution*.
        # The f-string below is for the generator. The {{}} are for the template.
        # No, this is still tricky. The join needs to happen in the template.
        # The most straightforward way to generate this is to write the Python lines that do the join.

        # Corrected approach: Generate Python lines that build and execute the command
        # These lines will be part of the generated template.py
        generated_code_for_make_kr = '''
        make_cmd_parts_for_kr = ["make"] + _make_vars + ["-s", "kernelrelease"]
        shell_command_for_kr = " ".join(make_cmd_parts_for_kr) + " > version"
        self.do("sh", "-c", shell_command_for_kr)
        '''
        # We need to dedent and correctly incorporate this into the f-string.
        # For simplicity in this diff, let's assume a slightly less dynamic but correct shell command generation.
        # The _make_vars list is defined in the template. We want to pass its elements to make.
        # The self.do() command takes *args.
        # self.do("make", *_make_vars, "-s", "kernelrelease") # This would work if not for redirection.
        # So, for redirection, we must use sh -c.
        # The string for sh -c must be "make VAR1=val1 VAR2=val2 -s kernelrelease > version"
        # The _make_vars list in the template is like ["VAR1=val1", "VAR2=val2"].
        # So, in the template, we need: " ".join(_make_vars)
        # The generator produces:
        self.do("sh", "-c", f"make {{' '.join(_make_vars)}} -s kernelrelease > version")

        # Read the kernelrelease from the created 'version' file for subsequent use
        # The following lines are part of the *generated template string*:
        kernelrelease_content_out = self.do("cat", "version", capture_output=True, check=True)
        kernelrelease = kernelrelease_content_out.stdout.strip() # kernelrelease is a Python var in template
        self.log(f"Kernel release from version file: {{kernelrelease}}") # Correctly escaped for generator

        self.log("Running make mrproper...")
        self.do("make", *_make_vars, "mrproper")

        self.log("Applying patches...")
        if not (self.chroot_cwd / ".git").is_dir():
            self.do("git", "init")
            self.do("git", "config", "--local", "user.email", "cbuild@chimera-linux.org")
            self.do("git", "config", "--local", "user.name", "cbuild")
            self.do("git", "add", ".")
            self.do("git", "commit", "--allow-empty", "-m", "Initial cbuild commit before patching")

        # Use surface_patches directory instead of patches to avoid cbuild auto-patch
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
        
        # Use a more robust approach for config merging
        # First, copy configs to working directory to avoid path issues
        self.do("cp", chroot_config_path, ".config.base", 
                tmpfiles=[host_config_file])
        self.do("cp", chroot_surface_config_path, ".config.surface", 
                tmpfiles=[host_surface_config_file])
        self.do("cp", chroot_arch_config_path, ".config.arch", 
                tmpfiles=[host_arch_config_file])
        
        # Try the merge script with local files
        try:
            self.do("./scripts/kconfig/merge_config.sh", "-m", 
                    ".config.base", ".config.surface", ".config.arch")
        except Exception as e:
            self.log_warn(f"merge_config.sh failed, trying manual merge: {{e}}")
            # Fallback: manual config merge
            self.do("cp", ".config.base", ".config")
            # Append surface config
            self.do("sh", "-c", "cat .config.surface >> .config")
            # Append arch config  
            self.do("sh", "-c", "cat .config.arch >> .config")

        self.log("Running make olddefconfig...")
        # kernelrelease is a Python variable in the template's prepare() scope.
        # The f-string for KERNELRELEASE= needs to be evaluated by the template, so escape for generator.
        self.do("make", *_make_vars, f"KERNELRELEASE={{kernelrelease}}", "olddefconfig") # Ensuring double braces
        self.log(f"Prepared {{self.pkgname}} version {{kernelrelease}}") # Correctly escaped for generator

def build(self):
    _make_vars = [ # This _make_vars is local to build() in generated template
        "HOSTCC=clang", "CC=clang", "LD=ld.lld",
        "AR=llvm-ar", "NM=llvm-nm", "OBJCOPY=llvm-objcopy", "OBJDUMP=llvm-objdump"
    ]
    with self.pushd(self.build_wrksrc):
        # Read the version file created in prepare()
        kernelrelease = (self.chroot_cwd / "version").read_text().strip()
        # kernelrelease is a Python var in template's build() scope.
        # The f-strings for log and make need to be evaluated by the template.
        self.log(f"Building kernel version {{kernelrelease}}") # Correctly escaped
        self.do("make", *_make_vars, f"KERNELRELEASE={{kernelrelease}}", "all") # Correctly escaped

def install(self):
    with self.pushd(self.build_wrksrc):
        kernelrelease = (self.chroot_cwd / "version").read_text().strip() # Reads file, kernelrelease is Python var
        self.log(f"Installing kernel version {{kernelrelease}}") # Correctly escaped for generator
        
        modulesdir = self.destdir / f"usr/lib/modules/{{kernelrelease}}" # Correctly escaped for generator
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
        # kernelrelease is Python var in template's install() scope
        self.ln_s(f"../lib/modules/{{kernelrelease}}/build", self.destdir / f"usr/src/{{self.pkgname}}", relative=True) # Correctly escaped

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
            # patch_filenames from PKGBUILD might be used as a reference or ignored
            # as patches will primarily come from the linux-surface archive
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
        # This path might become fully optional if configs are sourced from the surface archive
    
    # LINUX_SURFACE_REPO_PATH is for local patch sourcing, which will change.
    # For now, keep the check if it's used by setup_cport_directory for patches.
    # This will be re-evaluated when patch sourcing is updated.
    if not LINUX_SURFACE_REPO_PATH.is_dir() and pkgbuild_data_main.get("patch_filenames_from_pkgbuild"): # Only error if we might try to use it
        _print_message(f"Error: Linux Surface repository not found at '{LINUX_SURFACE_REPO_PATH}', which might be needed for PKGBUILD-listed patches. Please ensure it's cloned correctly or remove patch references if sourcing differently.", level="error")
        sys.exit(1)


    _print_message("Step 2: Setting up cport directory and files...", message_styles=["bold"])
    file_checksums = setup_cport_directory(
        args.output_name,
        args.force,
        args.kernel_stuff_path, # May be None
        args.surface_configs_path, # May be None
        pkgbuild_data_main, # Now contains primary versioning info
        LINUX_SURFACE_REPO_PATH # Role of this path will change
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