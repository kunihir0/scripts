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
        help="Git tag for the linux-surface project archive (e.g., 'arch-6.8.1-1')."
    )
    parser.add_argument(
        "--kernel-stuff-path", 
        type=pathlib.Path,
        default=None, 
        help="Optional path to a directory containing base kernel config files (e.g., 'config.x86_64')."
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
    kernel_stuff_dir: Optional[pathlib.Path], 
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
mod_rel_path="${mod#./}" # Ensure it's a relative path for concatenation
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
    # exit 1 # Allow to continue if this fails for some files
fi

if ! "$OBJCOPY" --add-gnu-debuglink="$mod_debug_path" "$mod"; then
    echo "Error: $OBJCOPY --add-gnu-debuglink failed for '$mod' (linking to $mod_debug_path)"
    # exit 1
fi

if ! "$STRIP" --strip-debug "$mod"; then
    echo "Error: $STRIP --strip-debug failed for '$mod'"
    # exit 1
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
        compressed_debug_path="${mod_debug_path}.gz" # .gz extension
        rm "$mod_debug_path" # remove original after successful compression
        echo "Compressed debug symbols to '${compressed_debug_path}'"
    else
        echo "Warning: gzip compression failed for '$mod_debug_path'. Leaving uncompressed."
    fi
else
    echo "Warning: No xz or gzip found. Debug symbols for '$mod' will not be compressed."
fi

# Update debuglink only if compression happened and path changed
if [ -n "$compressed_debug_path" ] && [ "$compressed_debug_path" != "$mod_debug_path" ]; then
    echo "Updating debug link in '$mod' to point to '${compressed_debug_path}'"
    # Strip old link first, then add new one
    if ! "$OBJCOPY" --strip-gnu-debuglink "$mod"; then
         echo "Warning: Failed to strip old gnu-debuglink from '$mod'. Link update might be problematic."
    fi
    if ! "$OBJCOPY" --add-gnu-debuglink="$compressed_debug_path" "$mod"; then
        echo "Error: $OBJCOPY --add-gnu-debuglink failed for '$mod' (linking to ${compressed_debug_path})"
        # exit 1
    fi
fi

echo "Successfully processed '$mod'. Debug symbols in '${compressed_debug_path:-$mod_debug_path}'"
"""
    mv_debug_script_path = files_dir / "mv-debug.sh"
    mv_debug_script_path.write_text(mv_debug_script_content)
    mv_debug_script_path.chmod(0o755)
    _print_message(f"mv-debug.sh created at {mv_debug_script_path}", indent=3)

    _print_message("Copying and sanitizing configuration files...", indent=2)
    
    arch_for_config = pkgbuild_data.get('arch', 'x86_64') 
    arch_specific_config_name = f"config.{arch_for_config}"
    target_config_path_in_files = files_dir / arch_specific_config_name

    if kernel_stuff_dir:
        base_config_to_copy = kernel_stuff_dir / "config" 
        if not base_config_to_copy.is_file():
            base_config_to_copy = kernel_stuff_dir / arch_specific_config_name
        
        if base_config_to_copy.is_file():
            sanitized_content = sanitize_config_file(base_config_to_copy)
            target_config_path_in_files.write_text(sanitized_content)
            _print_message(f"Copied base config from {base_config_to_copy} to {target_config_path_in_files}", indent=3)
        else:
             _print_message(f"Base config ('config' or '{arch_specific_config_name}') not found in {kernel_stuff_dir}. Template will need manual addition or rely on defconfig.", level="warning", indent=3)
    else: 
        _print_message("kernel_stuff_path not provided. Base 'config' will not be copied. Template will need a placeholder or manual addition.", level="info", indent=3)
        
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
    if target_config_path_in_files.exists():
        file_checksums[target_config_path_in_files.name] = calculate_sha256(target_config_path_in_files)
        
    return file_checksums

def generate_template_py_content(
    output_cport_name: str,
    pkgbuild_data: Dict[str, Any],
    file_checksums: Dict[str, str]
) -> str:
    pkgver = pkgbuild_data["pkgver"] 
    pkgrel = pkgbuild_data["pkgrel"] 
    surface_archive_tag = pkgbuild_data["surface_archive_tag"] 
    kernel_major_minor = pkgbuild_data["kernel_major_minor"]
    kernel_major = kernel_major_minor.split('.')[0]

    chimera_hostmakedepends = ["base-kernel-devel", "git"] 
    hostmakedepends_list_str = ", ".join([f'"{dep}"' for dep in sorted(list(set(chimera_hostmakedepends)))])

    sha256_kernel_tar = "SHA256_LINUX_TAR_XZ_PLACEHOLDER"
    sha256_kernel_patch = "SHA256_LINUX_PATCH_XZ_PLACEHOLDER" 
    sha256_surface_archive = "SHA256_SURFACE_ARCHIVE_PLACEHOLDER"

    configure_args_list = [
        f"RELEASE={pkgrel}",
        # Potentially add FLAVOR or other args if linux-kernel style supports them for surface
        # For now, surface-specific setup is in post_extract
    ]
    configure_args_str = ", ".join([f'"{arg}"' for arg in configure_args_list])

    make_env_block_raw = """
make_env = {
    "KBUILD_BUILD_USER": "chimera",
    "KBUILD_BUILD_HOST": "chimera.linux",
    "LDFLAGS": "", 
    # "CBUILD_BYPASS_STRIP_WRAPPER": "1", # If needed
}"""
    processed_make_env_block = textwrap.dedent(make_env_block_raw).strip()
    
    # Variables for f-string interpolation within post_extract_hook_str
    # These are evaluated when the generator script runs.
    # Double braces {{ and }} become single braces in the output string,
    # which cbuild then interpolates at template execution time.
    # Quadruple braces {{{{ and }}}} become double braces in the output string,
    # which then become single braces after cbuild's interpolation (for f-strings inside f-strings).
    
    # This value will be directly embedded into the generated script.
    localversion_config_val_for_gen = f"-{output_cport_name.replace('linux-', '')}"
    # This string, when written to the template, will be: f"-r{{self.pkgrel}}"
    # which means cbuild will interpolate self.pkgrel.
    pkgrel_file_content_val_for_gen = f"-r{{{{self.pkgrel}}}}"


    post_extract_hook_str = f"""
def post_extract(self):
    self.log(f"--- Starting post_extract() for {{self.pkgname}} {{self.pkgver}}-{{self.pkgrel}} ---")
    self.log(f"Chroot CWD (at start of post_extract): {{self.chroot_cwd}}")
    self.log(f"self.build_wrksrc (where kernel source is expected): {{self.build_wrksrc}}")
    self.log(f"self.chroot_sources_path (where tarballs are): {{self.chroot_sources_path}}")

    kernel_source_dir = self.chroot_cwd / self.build_wrksrc 
    self.log(f"Full path to kernel source dir: {{kernel_source_dir}}")

    self.log(f"Listing contents of {{self.chroot_sources_path}} (from chroot):")
    self.do("ls", "-la", self.chroot_sources_path, capture_output=True, check=False)
    self.log(f"Listing contents of {{kernel_source_dir}} before patching (from chroot):")
    self.do("ls", "-la", kernel_source_dir, capture_output=True, check=False)

    # 1. Apply main kernel patch (patch-{pkgver}.xz)
    self.log("--- Applying main kernel patch (manual due to '!' in source) ---")
    patch_filename = f"patch-{pkgver}.xz" # pkgver from outer scope
    kernel_patch_file = self.chroot_sources_path / patch_filename
    self.log(f"Main kernel patch file (chroot path): {{kernel_patch_file}}")
    if not kernel_patch_file.is_file(): # Host-side check on mapped path
        self.error(f"Kernel patch {{patch_filename}} not found at {{kernel_patch_file}}")
    
    with self.pushd(kernel_source_dir):
        self.log(f"Current dir for main patch: {{self.chroot_cwd}}")
        self.do("xzcat", kernel_patch_file, stdout_to_file="main_kernel.patch")
        self.do("patch", "-Np1", "-i", "main_kernel.patch")
        self.rm("main_kernel.patch")
        self.log(f"Main kernel patch applied.")

        if not (self.chroot_cwd / ".git").is_dir():
            self.log("Initializing git repository for patching...")
            self.do("git", "init")
            self.do("git", "config", "--local", "user.email", "cbuild@chimera-linux.org")
            self.do("git", "config", "--local", "user.name", "cbuild")
            self.do("git", "add", ".")
            self.do("git", "commit", "--allow-empty", "-m", "Initial cbuild commit after main kernel patch")

    # 2. Apply Surface patches
    self.log(f"--- Applying Surface patches ---")
    surface_archive_name = f"{{self.pkgname}}-{surface_archive_tag}-surface-sources.tar.gz" # surface_archive_tag from outer scope
    # The surface archive itself is in chroot_sources_path.
    # It extracts to a directory like 'linux-surface-arch-6.8.1-1' (using the tag)
    # *inside* chroot_sources_path, NOT alongside build_wrksrc.
    surface_extracted_dirname = f"linux-surface-{surface_archive_tag}" # surface_archive_tag from outer scope
    surface_archive_extract_root = self.chroot_sources_path / surface_extracted_dirname
    
    surface_patches_subdir = surface_archive_extract_root / "patches" / "{kernel_major_minor}" # kernel_major_minor from outer scope
    self.log(f"Surface patches subdir (chroot path): {{surface_patches_subdir}}")

    if surface_patches_subdir.is_dir(): # Host-side check
        patch_files = sorted(list(surface_patches_subdir.glob("*.patch")))
        self.log(f"Found {{len(patch_files)}} Surface patch files: {{[p.name for p in patch_files]}}")
        with self.pushd(kernel_source_dir):
            self.log(f"Current dir for surface patches: {{self.chroot_cwd}}")
            for patch_file_item in patch_files:
                self.log(f"Applying Surface patch {{patch_file_item.name}}...")
                # patch_file_item is a host path to a file in the chroot_sources_path mapped area
                self.do("patch", "-Np1", "-i", patch_file_item)
    else:
        self.log_warn(f"Surface patches directory not found: {{surface_patches_subdir}}")

    # 3. Merge configurations
    self.log(f"--- Merging kernel configurations ---")
    with self.pushd(kernel_source_dir):
        self.log(f"Current dir for config merge: {{self.chroot_cwd}}")
        
        # Base config from template's files/ directory
        host_base_config_src = self.files_path / f"config.{{self.profile().arch}}"
        
        # Surface config from extracted surface archive
        surface_config_src = surface_archive_extract_root / "configs" / f"surface-{kernel_major_minor}.config" # kernel_major_minor from outer scope

        if not host_base_config_src.is_file(): # Host-side check
            self.log_warn(f"Base config '{{host_base_config_src.name}}' not found in {{self.files_path}}. Attempting defconfig.")
            self.do("make", "defconfig", env=self.make_env)
        else:
            self.log(f"Using base config: {{host_base_config_src.name}}")
            self.do("cp", host_base_config_src, ".config") # cbuild maps self.files_path

        if surface_config_src.is_file(): # Host-side check
            self.log(f"Merging with Surface config: {{surface_config_src.name}}")
            self.do("cp", surface_config_src, ".config.surface") # surface_config_src is already a chroot path
            merge_env = {{**self.make_env, "KCONFIG_CONFIG": str(self.chroot_cwd / ".config")}}
            self.do("./scripts/kconfig/merge_config.sh", "-m", ".config", ".config.surface", env=merge_env)
            self.rm(".config.surface")
        else:
            self.log_warn(f"Surface-specific config '{{surface_config_src.name}}' not found. Using base/defconfig only.")

        # 4. Set CONFIG_LOCALVERSION and create localversion.10-pkgrel
        self.log(f"--- Setting CONFIG_LOCALVERSION ---")
        self.do("scripts/config", "--enable", "CONFIG_LOCALVERSION_AUTO", env=self.make_env)
        # Use value defined in generator's scope, embedded as a literal string
        self.log(f"Setting CONFIG_LOCALVERSION to '{localversion_config_val_for_gen}'")
        self.do("scripts/config", "--set-str", "CONFIG_LOCALVERSION", "{localversion_config_val_for_gen}", env=self.make_env)
        
        # Use value defined in generator's scope, which itself contains {{self.pkgrel}} for cbuild
        self.log(f"Writing '{pkgrel_file_content_val_for_gen}' to localversion.10-pkgrel")
        self.do("sh", "-c", f"echo '{pkgrel_file_content_val_for_gen}' > localversion.10-pkgrel")

        # 5. Finalize .config
        self.log(f"--- Finalizing .config with make olddefconfig ---")
        self.do("make", "olddefconfig", env=self.make_env)
        
        # 6. Generate kernelrelease version file (for self.localversion)
        self.log(f"--- Generating kernelrelease version file (version) ---")
        self.do("make", "kernelrelease", "-s", stdout_to_file="version", env=self.make_env)
        kernelrelease_val = (self.chroot_cwd / "version").read_text().strip()
        self.log(f"Generated KERNELRELEASE: {{kernelrelease_val}}")
        if kernelrelease_val.startswith(self.pkgver):
            self.localversion = kernelrelease_val.replace(self.pkgver, "", 1)
        else:
            self.log_warn(f"KERNELRELEASE '{{kernelrelease_val}}' does not start with pkgver '{{self.pkgver}}'. Cannot set localversion accurately.")
            self.localversion = "" 
        self.log(f"Set self.localversion to: '{{self.localversion}}'")

    self.log(f"--- Finished post_extract() for {{self.pkgname}} ---")
"""

    devel_subpackage_str = f"""
@subpackage("{output_cport_name}-devel")
def _(self):
    self.pkgdesc = f"{{self.parent.pkgdesc}} (development files)"
    self.depends += ["clang", "pahole"] 
    self.options = ["foreignelf", "execstack", "!scanshlibs"]
    parent_localversion = getattr(self.parent, 'localversion', '')
    kernelrelease_real = self.parent.pkgver + parent_localversion
    return [
        f"usr/lib/modules/{{kernelrelease_real}}/build",
        f"usr/src/{output_cport_name}"
    ]
"""
    dbg_subpackage_str = f"""
@subpackage("{output_cport_name}-dbg")
def _(self):
    self.pkgdesc = f"{{self.parent.pkgdesc}} (debug files)"
    self.options = ["!scanrundeps", "!strip", "!scanshlibs"]
    return [] 
"""

    template_str = f"""\
# Auto-generated by setup_surface_kernel_py.py

pkgname = "{output_cport_name}"
pkgver = "{pkgver}" 
pkgrel = {pkgrel} 

pkgdesc = f"Linux kernel ({kernel_major_minor} series) with Surface patches"
archs = ["x86_64"]
license = "GPL-2.0-only"
url = "https://github.com/linux-surface/linux-surface"

build_style = "linux-kernel"
configure_args = [{configure_args_str}]
make_dir = "build" 
# build_wrksrc is typically set by linux-kernel style, e.g., to 'linux-{pkgver_major_minor}'

source = [
    f"https://cdn.kernel.org/pub/linux/kernel/v{kernel_major}.x/linux-{kernel_major_minor}.tar.xz",
    f"!https://cdn.kernel.org/pub/linux/kernel/v{kernel_major}.x/patch-{pkgver}.xz",
    f"https://codeload.github.com/linux-surface/linux-surface/tar.gz/refs/tags/{surface_archive_tag}>{{pkgname}}-{surface_archive_tag}-surface-sources.tar.gz"
]
sha256 = [
    "{sha256_kernel_tar}", 
    "{sha256_kernel_patch}", 
    "{sha256_surface_archive}"
]

hostmakedepends = [
    {hostmakedepends_list_str},
]
depends = ["base-kernel"]
provides = [f"linux={{pkgver.split('.')[0]}}.{{pkgver.split('.')[1]}}"]

options = [
    "!check", 
    "!debug", 
    "!strip", 
    "!scanrundeps", 
    "!scanshlibs", 
    "!lto",
    "textrels", "execstack", "foreignelf"
]

{processed_make_env_block}
{post_extract_hook_str}
{devel_subpackage_str}
{dbg_subpackage_str}
"""
    return template_str

def main() -> None:
    _print_message("--- Linux Surface Cports Template Generator ---", message_styles=["bold", "purple"])
    args = parse_arguments()

    pkgver_main_for_calc = args.kernel_version
    kernel_major_minor_parts_for_calc = pkgver_main_for_calc.split('.')
    if len(kernel_major_minor_parts_for_calc) < 2:
        _print_message(f"Error: kernel_version '{pkgver_main_for_calc}' is not in a valid format (e.g., X.Y.Z)", level="error")
        sys.exit(1)
    kernel_major_minor_for_main = f"{kernel_major_minor_parts_for_calc[0]}.{kernel_major_minor_parts_for_calc[1]}"

    pkgbuild_data_main: Dict[str, Any] = {
        "pkgver": args.kernel_version,
        "pkgrel": "0", 
        "surface_archive_tag": args.surface_archive_tag,
        "kernel_major_minor": kernel_major_minor_for_main, 
        "makedepends": [], 
        "arch": "x86_64" 
    }

    _print_message(f"Target Kernel Version: {args.kernel_version}", indent=1)
    _print_message(f"Target Pkgrel: {pkgbuild_data_main['pkgrel']}", indent=1)
    _print_message(f"Surface Archive Tag: {args.surface_archive_tag}", indent=1)
    _print_message(f"Output Cport Name: {args.output_name}", indent=1)

    if args.kernel_stuff_path and not args.kernel_stuff_path.is_dir():
         _print_message(f"Warning: --kernel-stuff-path '{args.kernel_stuff_path}' provided but not a directory.", level="warning", indent=1)
    
    _print_message("Step 2: Setting up cport directory and files...", message_styles=["bold"])
    file_checksums = setup_cport_directory(
        args.output_name,
        args.force,
        args.kernel_stuff_path, 
        pkgbuild_data_main, 
        LINUX_SURFACE_REPO_PATH 
    )
    _print_message("Cport directory and files prepared.", level="success", indent=1)

    _print_message("Step 3: Generating template.py content...", message_styles=["bold"])
    template_content = generate_template_py_content(
        args.output_name, 
        pkgbuild_data_main, 
        file_checksums
    )
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
    symlink_path_devel = CPORTS_MAIN_DIR / devel_subpackage_name
    target_dir_for_symlink = pathlib.Path(args.output_name) 

    if symlink_path_devel.exists() or symlink_path_devel.is_symlink():
        if args.force:
            _print_message(f"Removing existing devel subpackage symlink: {symlink_path_devel}", level="warning", indent=1)
            symlink_path_devel.unlink(missing_ok=True)
        elif symlink_path_devel.is_symlink() and symlink_path_devel.resolve().name == args.output_name:
             _print_message(f"Devel subpackage symlink {symlink_path_devel} already exists and is correct.", indent=1)
        else: 
            _print_message(f"Error: Path {symlink_path_devel} for devel subpackage exists and is not a correct symlink. Use --force to overwrite.", level="error", indent=1)
            if not args.force: sys.exit(1) 

    if not symlink_path_devel.exists():
        try:
            symlink_path_devel.symlink_to(target_dir_for_symlink, target_is_directory=True)
            _print_message(f"Created symlink for -devel subpackage: {symlink_path_devel} -> {target_dir_for_symlink}", level="success", indent=1)
        except OSError as e:
            _print_message(f"Error creating symlink for -devel subpackage: {e}", level="error", indent=1)

    dbg_subpackage_name = f"{args.output_name}-dbg"
    symlink_path_dbg = CPORTS_MAIN_DIR / dbg_subpackage_name

    if symlink_path_dbg.exists() or symlink_path_dbg.is_symlink():
        if args.force:
            _print_message(f"Removing existing dbg subpackage symlink: {symlink_path_dbg}", level="warning", indent=1)
            symlink_path_dbg.unlink(missing_ok=True)
        elif symlink_path_dbg.is_symlink() and symlink_path_dbg.resolve().name == args.output_name:
            _print_message(f"Dbg subpackage symlink {symlink_path_dbg} already exists and is correct.", indent=1)
        else:
            _print_message(f"Error: Path {symlink_path_dbg} for dbg subpackage exists and is not a correct symlink. Use --force to overwrite.", level="error", indent=1)
            if not args.force: sys.exit(1) 
            
    if not symlink_path_dbg.exists():
        try:
            symlink_path_dbg.symlink_to(target_dir_for_symlink, target_is_directory=True)
            _print_message(f"Created symlink for -dbg subpackage: {symlink_path_dbg} -> {target_dir_for_symlink}", level="success", indent=1)
        except OSError as e:
            _print_message(f"Error creating symlink for -dbg subpackage: {e}", level="error", indent=1)
    
    print("-" * 60)
    _print_message("--- Generation Complete! ---", level="star", message_styles=["bold"])
    _print_message(f"New cport template for '{args.output_name}' created at:", indent=1)
    _print_message(f"  {CPORTS_MAIN_DIR / args.output_name}", indent=2, message_styles=["cyan"])
    _print_message("IMPORTANT: You need to update the 'sha256' list in the generated template.py:", level="warning", indent=1)
    _print_message(f"  The 'sha256' list has three placeholder entries corresponding to the three URLs in the 'source' list:", indent=2)
    _print_message(f"    1. Kernel.org base tarball (e.g., linux-{kernel_major_minor_for_main}.tar.xz)", indent=3) 
    _print_message(f"    2. Kernel.org incremental patch (e.g., patch-{args.kernel_version}.xz)", indent=3) 
    _print_message(f"    3. Linux-surface archive (e.g., {args.output_name}-{args.surface_archive_tag}-surface-sources.tar.gz)", indent=3) 
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