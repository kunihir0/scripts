#!/usr/bin/env python3

import sys
import subprocess
import pathlib
import shutil
import re
import hashlib
import argparse
import textwrap 
from typing import List, Dict, Tuple, Optional, Any

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
    if color_name and color_name in COLORS: prefix += COLORS[color_name]
    if style_names:
        for style_name in style_names:
            if style_name in STYLES: prefix += STYLES[style_name]
    suffix = COLORS.get("reset", "\033[0m") 
    if prefix: suffix += STYLES.get("reset_style", "\033[22m\033[23m\033[24m\033[25m") 
    else: suffix = ""
    return f"{prefix}{text}{suffix}" if prefix else text

def _print_message(message: str, level: str = "info", indent: int = 0, message_styles: Optional[List[str]] = None) -> None:
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

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT_FROM_SCRIPT = SCRIPT_DIR.parent.parent 
WORKSPACE_ROOT = PROJECT_ROOT_FROM_SCRIPT 
CPORTS_MAIN_DIR = WORKSPACE_ROOT / "chimera" / "cports" / "main"
DEFAULT_OUTPUT_CPORT_NAME = "linux-surface-generated"

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a Chimera Linux cports template for linux-surface.")
    parser.add_argument("--kernel-version", type=str, required=True, help="Target kernel version (e.g., '6.8.1').")
    parser.add_argument("--surface-archive-tag", type=str, required=True, help="Git tag for linux-surface archive (e.g., 'arch-6.8.1-1').")
    parser.add_argument("--kernel-stuff-path", type=pathlib.Path, default=None, help="Optional path to a base kernel config file (e.g., 'config' or 'config.x86_64'). Copied to files/config-{arch}.{FLAVOR}.")
    parser.add_argument("--output-name", type=str, default=DEFAULT_OUTPUT_CPORT_NAME, help=f"Name for the new cport directory (default: {DEFAULT_OUTPUT_CPORT_NAME})")
    parser.add_argument("--force", action="store_true", help="Overwrite existing cport directory.")
    return parser.parse_args()

def calculate_sha256(file_path: pathlib.Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""): sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def sanitize_config_file(file_path: pathlib.Path) -> str:
    try: content = file_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        _print_message(f"Warning: UTF-8 decode failed for {file_path.name}, trying latin-1", level="warning", indent=3)
        content = file_path.read_text(encoding='latin-1')
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    lines = [line.rstrip() for line in content.splitlines()]
    sanitized_content = '\n'.join(lines)
    if sanitized_content and not sanitized_content.endswith('\n'): sanitized_content += '\n'
    return sanitized_content

def setup_cport_directory(output_cport_name: str, force_overwrite: bool, kernel_stuff_dir: Optional[pathlib.Path], pkgbuild_data: Dict[str, Any]) -> Dict[str, str]:
    target_cport_path = CPORTS_MAIN_DIR / output_cport_name
    files_dir = target_cport_path / "files"
    patches_dir = target_cport_path / "patches"
    flavor_name = output_cport_name.replace("linux-", "")

    if target_cport_path.exists():
        if force_overwrite:
            _print_message(f"Removing existing cport directory: {target_cport_path}", level="warning", indent=1)
            shutil.rmtree(target_cport_path)
        else:
            _print_message(f"Error: Cport directory {target_cport_path} already exists. Use --force.", level="error")
            sys.exit(1)
    
    _print_message(f"Creating cport directory structure: {target_cport_path}", indent=1)
    target_cport_path.mkdir(parents=True); files_dir.mkdir(); patches_dir.mkdir()

    _print_message("Creating mv-debug.sh script...", indent=2)
    mv_debug_script_content = textwrap.dedent("""\
    #!/bin/sh
    set -e
    if [ -z "$1" ]; then echo "Usage: $0 <file_to_process>"; exit 1; fi
    mod="$1"; debugdir_base="usr/lib/debug"; mod_rel_path="${mod#./}"; mod_debug_path="${debugdir_base}/${mod_rel_path}"
    OBJCOPY="${OBJCOPY:-llvm-objcopy}"; STRIP="${STRIP:-llvm-strip}"
    if [ ! -f "$mod" ]; then echo "Error: File '$mod' not found!"; exit 1; fi
    echo "Processing '$mod' for debug symbols..."; mkdir -p "$(dirname "$mod_debug_path")"
    if ! "$OBJCOPY" --only-keep-debug "$mod" "$mod_debug_path"; then echo "Error: $OBJCOPY --only-keep-debug failed for '$mod'"; fi
    if ! "$OBJCOPY" --add-gnu-debuglink="$mod_debug_path" "$mod"; then echo "Error: $OBJCOPY --add-gnu-debuglink failed for '$mod' (linking to $mod_debug_path)"; fi
    if ! "$STRIP" --strip-debug "$mod"; then echo "Error: $STRIP --strip-debug failed for '$mod'"; fi
    compressed_debug_path="";
    if command -v xz > /dev/null; then
        if xz -T0 -zc "$mod_debug_path" > "${mod_debug_path}.xz"; then rm "$mod_debug_path"; compressed_debug_path="${mod_debug_path}.xz"; echo "Compressed debug symbols to '${compressed_debug_path}'"; else echo "Warning: xz compression failed for '$mod_debug_path'. Leaving uncompressed."; fi
    elif command -v gzip > /dev/null; then
        if gzip -9nf "$mod_debug_path"; then rm "$mod_debug_path"; compressed_debug_path="${mod_debug_path}.gz"; echo "Compressed debug symbols to '${compressed_debug_path}'"; else echo "Warning: gzip compression failed for '$mod_debug_path'. Leaving uncompressed."; fi
    else echo "Warning: No xz or gzip found. Debug symbols for '$mod' will not be compressed."; fi
    if [ -n "$compressed_debug_path" ] && [ "$compressed_debug_path" != "$mod_debug_path" ]; then
        echo "Updating debug link in '$mod' to point to '${compressed_debug_path}'"
        if ! "$OBJCOPY" --strip-gnu-debuglink "$mod"; then echo "Warning: Failed to strip old gnu-debuglink from '$mod'. Link update might be problematic."; fi
        if ! "$OBJCOPY" --add-gnu-debuglink="$compressed_debug_path" "$mod"; then echo "Error: $OBJCOPY --add-gnu-debuglink failed for '$mod' (linking to ${compressed_debug_path})"; fi
    fi
    echo "Successfully processed '$mod'. Debug symbols in '${compressed_debug_path:-$mod_debug_path}'"
    """)
    mv_debug_script_path = files_dir / "mv-debug.sh"
    mv_debug_script_path.write_text(mv_debug_script_content)
    mv_debug_script_path.chmod(0o755)
    _print_message(f"mv-debug.sh created at {mv_debug_script_path}", indent=3)

    _print_message(f"Preparing files/ for base config (config-{{arch}}.{{flavor}})...", indent=2)
    arch_for_config = pkgbuild_data.get('arch', 'x86_64')
    target_config_in_files_dir = files_dir / f"config-{arch_for_config}.{flavor_name}"
    copied_base_config_to_files = False
    if kernel_stuff_dir:
        base_config_src_generic = kernel_stuff_dir / "config"
        base_config_src_arch = kernel_stuff_dir / f"config.{arch_for_config}"
        chosen_base_config_src = None
        if base_config_src_arch.is_file(): chosen_base_config_src = base_config_src_arch
        elif base_config_src_generic.is_file(): chosen_base_config_src = base_config_src_generic
        if chosen_base_config_src:
            sanitized_content = sanitize_config_file(chosen_base_config_src)
            target_config_in_files_dir.write_text(sanitized_content)
            _print_message(f"Copied base config from {chosen_base_config_src} to {target_config_in_files_dir}", indent=3)
            copied_base_config_to_files = True
        else: _print_message(f"Base config not found in {kernel_stuff_dir}. No base config copied.", level="warning", indent=3)
    else: _print_message("kernel_stuff_path not provided. No base config copied.", level="info", indent=3)
    
    file_checksums = {"mv-debug.sh": calculate_sha256(mv_debug_script_path)}
    if copied_base_config_to_files and target_config_in_files_dir.exists():
         file_checksums[target_config_in_files_dir.name] = calculate_sha256(target_config_in_files_dir)
    return file_checksums

def generate_template_py_content(output_cport_name: str, pkgbuild_data: Dict[str, Any], file_checksums: Dict[str, str]) -> str:
    pkgver = pkgbuild_data["pkgver"] 
    pkgrel = pkgbuild_data["pkgrel"] 
    surface_archive_tag = pkgbuild_data["surface_archive_tag"] 
    kernel_major_minor = pkgbuild_data["kernel_major_minor"]
    kernel_major = kernel_major_minor.split('.')[0]
    flavor_name = output_cport_name.replace("linux-", "") 

    hostmakedepends_list = ["base-kernel-devel", "git", "xz"] # xz for xzcat
    hostmakedepends_list_str = ", ".join([f'"{dep}"' for dep in sorted(list(set(hostmakedepends_list)))])

    sha256_kernel_tar = "SHA256_LINUX_TAR_XZ_PLACEHOLDER"
    sha256_kernel_patch = "SHA256_LINUX_PATCH_XZ_PLACEHOLDER" 
    sha256_surface_archive = "SHA256_SURFACE_ARCHIVE_PLACEHOLDER"

    configure_args_list = [f"FLAVOR={flavor_name}", f"RELEASE={pkgrel}"]
    configure_args_str = ", ".join([f'"{arg}"' for arg in configure_args_list])

    make_env_block_raw = textwrap.dedent("""\
    make_env = {
        "KBUILD_BUILD_USER": "chimera",
        "KBUILD_BUILD_HOST": "chimera.linux",
        "LDFLAGS": "", 
    }""")
    processed_make_env_block = make_env_block_raw.strip()
    
    pre_configure_hook_str = f"""
def pre_configure(self):
    # Extract FLAVOR from self.configure_args first
    flavor = None
    for arg in self.configure_args:
        if arg.startswith("FLAVOR="):
            flavor = arg.split("=")[1]
            break
    if not flavor: 
        self.error("FLAVOR not found in configure_args for pre_configure hook")

    self.log(f"--- Starting pre_configure() for {{self.pkgname}} (flavor: {{flavor}}) ---")
    self.log(f"Kernel source directory (self.cwd / chroot_cwd): {{self.cwd}} / {{self.chroot_cwd}}")
    self.log(f"Chroot sources path (self.chroot_sources_path): {{self.chroot_sources_path}}")
    self.log(f"Template path (self.template_path): {{self.template_path}}")
    self.log(f"Make dir (self.make_dir): {{self.make_dir}}")

    # 1. Apply main kernel patch (e.g., patch-6.8.1.xz)
    main_kernel_patch_filename = f"patch-{{self.pkgver}}.xz"
    main_kernel_patch_chroot_path = self.chroot_sources_path / main_kernel_patch_filename
    
    self.log(f"Attempting to apply main kernel patch: {{main_kernel_patch_chroot_path}} to {{self.chroot_cwd}}")
    decompressed_patch_name = "main_kernel.patch" # Temporary file in self.chroot_cwd
    
    self.log(f"Decompressing {{main_kernel_patch_chroot_path}} to {{self.chroot_cwd / decompressed_patch_name}}")
    self.do("xzcat", main_kernel_patch_chroot_path, stdout_to_file=(self.chroot_cwd / decompressed_patch_name))
    
    self.log(f"Applying decompressed main kernel patch: {{decompressed_patch_name}}")
    self.do("patch", "-Np1", "-i", (self.chroot_cwd / decompressed_patch_name))
    
    self.rm(self.cwd / decompressed_patch_name) # Clean up using host-perspective path
    self.log("Main kernel patch applied.")

    # 2. Extract Surface archive and apply its patches
    surface_archive_dl_name = f"{{self.pkgname}}-{surface_archive_tag}-surface-sources.tar.gz"
    surface_archive_chroot_path = self.chroot_sources_path / surface_archive_dl_name
    
    surface_extract_temp_dir_name = "_surface_sources_extracted"
    surface_extract_temp_dir_chroot_path = self.chroot_cwd / surface_extract_temp_dir_name
    
    self.mkdir(self.cwd / surface_extract_temp_dir_name) # mkdir uses host path
    self.log(f"Created temporary extraction directory: {{surface_extract_temp_dir_chroot_path}}")

    self.log(f"Extracting {{surface_archive_chroot_path}} into {{surface_extract_temp_dir_chroot_path}} with --strip-components=1")
    self.do("tar", "xvf", surface_archive_chroot_path, "-C", surface_extract_temp_dir_chroot_path, "--strip-components=1")

    surface_patches_dir_chroot_path = surface_extract_temp_dir_chroot_path / "patches" / "{kernel_major_minor}"
    # For globbing, use the host-mapped path
    surface_patches_dir_host_path = self.cwd / surface_extract_temp_dir_name / "patches" / "{kernel_major_minor}"

    if surface_patches_dir_host_path.is_dir():
        patch_files_host = sorted(list(surface_patches_dir_host_path.glob("*.patch")))
        if patch_files_host:
            self.log(f"Applying {{len(patch_files_host)}} Surface patches from {{surface_patches_dir_chroot_path}}")
            for patch_file_host_obj in patch_files_host:
                patch_file_name_only = patch_file_host_obj.name
                patch_to_apply_chroot_path = surface_patches_dir_chroot_path / patch_file_name_only
                self.log(f"Applying Surface patch: {{patch_to_apply_chroot_path}}")
                self.do("patch", "-Np1", "-i", patch_to_apply_chroot_path)
        else:
            self.log_warn(f"No .patch files found in {{surface_patches_dir_chroot_path}}")
    else:
        self.log_warn(f"Surface patches source directory not found: {{surface_patches_dir_chroot_path}}")

    # 3. Prepare .config in $OBJDIR (self.make_dir relative to self.cwd)
    objdir_chroot_path = self.chroot_cwd / self.make_dir
    self.mkdir(self.cwd / self.make_dir, parents=True) # Ensure OBJDIR exists (host path for mkdir)
    target_objdir_dot_config_chroot_path = objdir_chroot_path / ".config"
    
    self.log(f"Target OBJDIR for .config (chroot path): {{target_objdir_dot_config_chroot_path}}")

    chroot_template_files_dir = self.template_path / "files"
    base_config_name_flavored = f"config-{{self.profile().arch}}.{{flavor}}"
    base_config_chroot_path_flavored = chroot_template_files_dir / base_config_name_flavored
    base_config_name_no_flavor = f"config-{{self.profile().arch}}"
    base_config_chroot_path_no_flavor = chroot_template_files_dir / base_config_name_no_flavor
    
    initial_config_placed = False
    if (self.template_path / "files" / base_config_name_flavored).is_file(): # Python check on host-mapped path
        self.log(f"Using base config from template files: {{base_config_chroot_path_flavored}}")
        self.do("cp", base_config_chroot_path_flavored, target_objdir_dot_config_chroot_path)
        initial_config_placed = True
    elif (self.template_path / "files" / base_config_name_no_flavor).is_file(): # Python check on host-mapped path
        self.log(f"Using base config (no flavor suffix): {{base_config_chroot_path_no_flavor}}")
        self.do("cp", base_config_chroot_path_no_flavor, target_objdir_dot_config_chroot_path)
        initial_config_placed = True
    else:
        self.log_warn(f"No base config in template files (checked for {{base_config_name_flavored}}, {{base_config_name_no_flavor}}).")

    surface_specific_config_in_extracted_chroot_path = surface_extract_temp_dir_chroot_path / "configs" / f"surface-{kernel_major_minor}.config"
    if (self.cwd / surface_extract_temp_dir_name / "configs" / f"surface-{kernel_major_minor}.config").is_file(): # Host path check
        self.log(f"Found Surface-specific config in extracted archive: {{surface_specific_config_in_extracted_chroot_path}}")
        if not initial_config_placed:
            self.log(f"No base config, copying Surface config to {{target_objdir_dot_config_chroot_path}}")
            self.do("cp", surface_specific_config_in_extracted_chroot_path, target_objdir_dot_config_chroot_path)
        else:
            self.log(f"Merging {{target_objdir_dot_config_chroot_path}} with Surface config")
            temp_frag_chroot_path = objdir_chroot_path / ".config.surface_fragment"
            self.do("cp", surface_specific_config_in_extracted_chroot_path, temp_frag_chroot_path)
            merge_env = {{**self.make_env, "KCONFIG_CONFIG": str(target_objdir_dot_config_chroot_path)}}
            self.do(self.chroot_cwd / "scripts/kconfig/merge_config.sh", "-m", target_objdir_dot_config_chroot_path, temp_frag_chroot_path, env=merge_env)
            self.rm(self.cwd / self.make_dir / ".config.surface_fragment") # Host path for rm
    elif not initial_config_placed:
         self.log_warn(f"No base config and no Surface-specific config in archive found.")

    if not (self.cwd / self.make_dir / ".config").is_file(): # Host path check
        self.log_warn(f"No .config in OBJDIR. Running 'make defconfig' in OBJDIR.")
        self.do("make", f"O={{self.make_dir}}", "defconfig", env=self.make_env)
        
    self.rm(self.cwd / surface_extract_temp_dir_name, recursive=True) # Host path for rm
    self.log(f"--- Finished pre_configure() for {{self.pkgname}} ---")
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

pkgdesc = f"Linux kernel ({kernel_major_minor}) with patches for Microsoft Surface devices"
archs = ["x86_64"]
license = "GPL-2.0-only"
url = "https://github.com/linux-surface/linux-surface"

build_style = "linux-kernel"
configure_args = [{configure_args_str}]
make_dir = "build" 

source = [
    f"https://cdn.kernel.org/pub/linux/kernel/v{kernel_major}.x/linux-{kernel_major_minor}.tar.xz",
    f"https://cdn.kernel.org/pub/linux/kernel/v{kernel_major}.x/patch-{{pkgver}}.xz", # Use {{pkgver}} for cbuild
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
    "!check", "!debug", "!strip", "!scanrundeps", 
    "!scanshlibs", "!lto", "textrels", "execstack", "foreignelf"
]

{processed_make_env_block}
{pre_configure_hook_str}
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
        _print_message(f"Error: kernel_version '{pkgver_main_for_calc}' invalid.", level="error"); sys.exit(1)
    kernel_major_minor_for_main = f"{kernel_major_minor_parts_for_calc[0]}.{kernel_major_minor_parts_for_calc[1]}"
    pkgbuild_data_main: Dict[str, Any] = {
        "pkgver": args.kernel_version, "pkgrel": "0", 
        "surface_archive_tag": args.surface_archive_tag,
        "kernel_major_minor": kernel_major_minor_for_main, "arch": "x86_64" 
    }
    _print_message(f"Target Kernel Version: {args.kernel_version}", indent=1)
    _print_message(f"Surface Archive Tag: {args.surface_archive_tag}", indent=1)
    _print_message(f"Output Cport Name: {args.output_name}", indent=1)
    if args.kernel_stuff_path and not args.kernel_stuff_path.is_dir():
         _print_message(f"Warning: --kernel-stuff-path non-directory.", level="warning", indent=1)
    
    _print_message("Step 2: Setting up cport directory and files...", message_styles=["bold"])
    file_checksums = setup_cport_directory(args.output_name, args.force, args.kernel_stuff_path, pkgbuild_data_main)
    _print_message("Cport directory and files prepared.", level="success", indent=1)

    _print_message("Step 3: Generating template.py content...", message_styles=["bold"])
    template_content = generate_template_py_content(args.output_name, pkgbuild_data_main, file_checksums)
    _print_message("template.py content generated.", indent=1)

    _print_message("Step 4: Writing template.py...", message_styles=["bold"])
    target_template_py_path = CPORTS_MAIN_DIR / args.output_name / "template.py"
    try:
        target_template_py_path.write_text(template_content)
        _print_message(f"Successfully wrote template.py to: {target_template_py_path}", level="success", indent=1)
    except IOError as e: _print_message(f"Error writing template.py: {e}", level="error"); sys.exit(1)
    
    _print_message("Step 5: Creating subpackage symlinks...", message_styles=["bold"])
    for subpkg_suffix in ["-devel", "-dbg"]:
        subpackage_name = f"{args.output_name}{subpkg_suffix}"
        symlink_path = CPORTS_MAIN_DIR / subpackage_name
        target_dir_for_symlink = pathlib.Path(args.output_name)
        if symlink_path.exists() or symlink_path.is_symlink():
            if args.force:
                _print_message(f"Removing existing {subpkg_suffix} symlink: {symlink_path}", level="warning", indent=1)
                symlink_path.unlink(missing_ok=True)
            elif symlink_path.is_symlink() and symlink_path.resolve().name == args.output_name:
                 _print_message(f"{subpkg_suffix} symlink {symlink_path} already correct.", indent=1)
                 continue
            else: 
                _print_message(f"Error: Path {symlink_path} for {subpkg_suffix} exists. Use --force.", level="error", indent=1)
                if not args.force: sys.exit(1) 
        if not symlink_path.exists():
            try:
                symlink_path.symlink_to(target_dir_for_symlink, target_is_directory=True)
                _print_message(f"Created symlink for {subpkg_suffix}: {symlink_path} -> {target_dir_for_symlink}", level="success", indent=1)
            except OSError as e: _print_message(f"Error creating symlink for {subpkg_suffix}: {e}", level="error", indent=1)
    
    print("-" * 60)
    _print_message("--- Generation Complete! ---", level="star", message_styles=["bold"])
    _print_message(f"New cport template for '{args.output_name}' created at:", indent=1)
    _print_message(f"  {CPORTS_MAIN_DIR / args.output_name}", indent=2, message_styles=["cyan"])
    _print_message("IMPORTANT: Update 'sha256' in template.py:", level="warning", indent=1)
    _print_message(f"  1. Kernel.org base tarball (linux-{kernel_major_minor_for_main}.tar.xz)", indent=3) 
    _print_message(f"  2. Kernel.org incremental patch (patch-{args.kernel_version}.xz)", indent=3) 
    _print_message(f"  3. Linux-surface archive ({args.output_name}-{args.surface_archive_tag}-surface-sources.tar.gz)", indent=3) 
    _print_message(f"  Run: ./cbuild fetch main/{args.output_name} ; then edit template.", indent=2)
    _print_message(f"Build with: ./cbuild pkg main/{args.output_name}", indent=1, message_styles=["green", "bold"])
    print("-" * 60)

if __name__ == "__main__":
    try: main()
    except Exception as e:
        _print_message(f"An unexpected script error: {e}", level="error") 
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally: print(COLORS.get("reset", "\033[0m"))