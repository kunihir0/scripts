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
        "--kernel-stuff-path",
        type=pathlib.Path,
        default=WORKSPACE_ROOT / "chimera" / "py" / "docs" / "kernel_stuff",
        help="Path to the directory containing PKGBUILD, config, and arch.config (default: chimera/py/docs/kernel_stuff/)"
    )
    parser.add_argument(
        "--surface-configs-path",
        type=pathlib.Path,
        default=WORKSPACE_ROOT / "chimera" / "py" / "docs" / "kernel_stuff" / "surface_configs",
        help="Path to the directory containing surface-X.Y.config files (default: chimera/py/docs/kernel_stuff/surface_configs/)"
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
        data["original_pkgver"] = original_pkgver_str # Keep for _srctag logic
        # Sanitize pkgver for template.py (apk format: X.Y.Z)
        sanitized_pkgver_match = re.match(r"(\d+\.\d+(\.\d+)?)", original_pkgver_str)
        if sanitized_pkgver_match:
            data["pkgver"] = sanitized_pkgver_match.group(1)
        else:
            _print_message(f"Could not sanitize 'pkgver': {original_pkgver_str}", level="error")
            sys.exit(1)
    else:
        _print_message("Could not parse 'pkgver' from PKGBUILD.", level="error")
        sys.exit(1)

    pkgrel_match = re.search(r"^\s*pkgrel=([^\s#]+)", content, re.MULTILINE)
    if pkgrel_match:
        data["pkgrel"] = pkgrel_match.group(1).strip().strip("'\"")
    else:
        _print_message("Could not parse 'pkgrel' from PKGBUILD.", level="error")
        sys.exit(1)

    # Calculate _srctag based on pkgver
    # _shortver=${pkgver%.*}
    # _fullver=${pkgver%.*}-${pkgver##*.}
    # _srctag=v${_fullver}
    # Use original_pkgver for _srctag calculation logic as it matches PKGBUILD's intent
    pkgver_for_srctag = data["original_pkgver"]
    shortver = ".".join(pkgver_for_srctag.split(".")[:-1]) if '.' in pkgver_for_srctag else pkgver_for_srctag
    suffix = pkgver_for_srctag.split(".")[-1] if '.' in pkgver_for_srctag else ""
    
    # The _fullver_pkb calculation below (lines 218-222 in previous version) correctly derives
    # the necessary string component from pkgver_for_srctag for _srctag.
    # The block that was here defining 'fullver' was redundant and the source of the NameError.
    # Removing the problematic 'fullver' calculation block.

    # The PKGBUILD _fullver is ${pkgver%.*}-${pkgver##*.}
    # For "6.14.2.arch1": pkgver%.* is "6.14.2", pkgver##*. is "arch1" -> "6.14.2-arch1"
    # For "6.14.2": pkgver%.* is "6.14", pkgver##*. is "2" -> "6.14-2" (This is Arch's bashism)
    # We need the tag for archlinux/linux repo, which is usually vX.Y.Z-archN or vX.Y.Z
    # The PKGBUILD's _srctag is v${_fullver}
    # Let's try to replicate the PKGBUILD's _fullver logic for _srctag
    
    pkgver_parts_for_srctag = pkgver_for_srctag.split('.')
    if len(pkgver_parts_for_srctag) > 1 and not pkgver_parts_for_srctag[-1].isdigit(): # like .arch1
        _fullver_pkb = f"{'.'.join(pkgver_parts_for_srctag[:-1])}-{pkgver_parts_for_srctag[-1]}"
    else: # like .2
         _fullver_pkb = f"{'.'.join(pkgver_parts_for_srctag[:-1])}-{pkgver_parts_for_srctag[-1]}" if len(pkgver_parts_for_srctag) > 1 else pkgver_for_srctag


    # The _srctag in the PKGBUILD is `v${_fullver}` where _fullver is derived.
    # For `pkgver=6.14.2.arch1`, `_fullver` becomes `6.14.2-arch1`, so `_srctag=v6.14.2-arch1`
    # This seems to be the tag format for https://github.com/archlinux/linux
    # Let's try to parse _srctag directly if available, otherwise compute.
    srctag_match = re.search(r"^\s*_srctag=v([^\s#]+)", content, re.MULTILINE)
    if srctag_match:
        data["_srctag"] = "v" + srctag_match.group(1).strip().strip("'\"").replace("${_fullver}", _fullver_pkb) # Substitute if var used
    else: # Fallback to direct computation
        data["_srctag"] = f"v{_fullver_pkb}"


    makedepends_match = re.search(r"^\s*makedepends=\((.*?)\)", content, re.DOTALL | re.MULTILINE)
    if makedepends_match:
        deps_str = makedepends_match.group(1)
        data["makedepends"] = [dep.strip().strip("'\"") for dep in re.findall(r"[\w.-]+", deps_str)]
    else:
        data["makedepends"] = []
        _print_message("Could not parse 'makedepends' from PKGBUILD. Assuming empty.", level="warning")

    source_match = re.search(r"^\s*source=\((.*?)\)", content, re.DOTALL | re.MULTILINE)
    patch_filenames = []
    if source_match:
        sources_str = source_match.group(1)
        # Extract items, removing comments and empty lines
        source_items = [item.split("::")[-1].split("#")[0].strip().strip("'\"") for item in sources_str.split()]
        patch_filenames = [item for item in source_items if item.endswith(".patch")]
    data["patch_filenames"] = patch_filenames
    
    # We don't parse PKGBUILD sha256sums for now, as we'll calculate new ones for copied files.

    return data

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

    # Copy config files
    _print_message("Copying configuration files...", indent=2)
    shutil.copy2(kernel_stuff_dir / "config", files_dir / "config")
    shutil.copy2(kernel_stuff_dir / "arch.config", files_dir / "arch.config")

    pkgver = pkgbuild_data["pkgver"]
    kernel_major_minor = ".".join(pkgver.split(".")[:2]) # e.g., "6.14"
    
    surface_config_name = f"surface-{kernel_major_minor}.config"
    surface_config_source_path = surface_configs_dir / surface_config_name
    if not surface_config_source_path.is_file():
        # Try finding any surface-X.Y.config if exact match fails (e.g. PKGBUILD is for 6.14.2, but we have surface-6.14.config)
        found_configs = list(surface_configs_dir.glob(f"surface-{kernel_major_minor}*.config"))
        if not found_configs:
             _print_message(f"Error: Surface config '{surface_config_name}' (or similar for {kernel_major_minor}) not found in {surface_configs_dir}", level="error")
             sys.exit(1)
        surface_config_source_path = found_configs[0] # Take the first one found
        _print_message(f"Using surface config: {surface_config_source_path.name}", level="info", indent=3)

    shutil.copy2(surface_config_source_path, files_dir / "surface.config")

    # Copy patch files
    _print_message("Copying patch files...", indent=2)
    kernel_series_for_patches = kernel_major_minor # e.g., "6.14"
    source_patches_dir = linux_surface_repo_base_path / "patches" / kernel_series_for_patches
    
    if not source_patches_dir.is_dir():
        _print_message(f"Error: Patches directory not found for series {kernel_series_for_patches} at {source_patches_dir}", level="error")
        sys.exit(1)

    for patch_filename in pkgbuild_data["patch_filenames"]:
        source_patch_path = source_patches_dir / patch_filename
        if source_patch_path.is_file():
            shutil.copy2(source_patch_path, patches_dir / patch_filename)
            _print_message(f"Copied patch: {patch_filename}", indent=3)
        else:
            _print_message(f"Warning: Patch file '{patch_filename}' not found in {source_patches_dir}", level="warning", indent=3)
            # Decide if this should be a fatal error based on requirements

    # Calculate checksums for files in files/
    file_checksums = {
        "config": calculate_sha256(files_dir / "config"),
        "surface.config": calculate_sha256(files_dir / "surface.config"),
        "arch.config": calculate_sha256(files_dir / "arch.config"),
    }
    return file_checksums

def generate_template_py_content(
    output_cport_name: str,
    pkgbuild_data: Dict[str, Any],
    file_checksums: Dict[str, str]
) -> str:
    pkgver = pkgbuild_data["pkgver"]
    pkgrel = pkgbuild_data["pkgrel"]
    # _srctag is already in pkgbuild_data, e.g., "v6.14.2-arch1"
    _srctag_for_git = pkgbuild_data["_srctag"]
    
    # Ensure makedepends are quoted if they contain special characters, though unlikely for package names
    hostmakedepends_list_str = ", ".join([f'"{dep}"' for dep in pkgbuild_data.get("makedepends", [])])
    
    # Prepare KBUILD_BUILD_TIMESTAMP for make_ENV
    # Rely on cbuild to set SOURCE_DATE_EPOCH, and kernel Makefile to use it.
    # If explicit setting was desired:
    # timestamp_logic = 'self.source_date_epoch and f"$(date -Ru@{{self.source_date_epoch}})" or "1970-01-01T00:00:00Z"'
    # This is complex to get right in a string that becomes Python code.
    # Simpler: kernel's Makefile handles SOURCE_DATE_EPOCH.

    template_str = f"""\
# Auto-generated by setup_surface_kernel_py.py

pkgname = "{output_cport_name}"
pkgver = "{pkgver}"
pkgrel = {pkgrel}
pkgdesc = f"Linux kernel ({{pkgver.split('.')[0]}}.{{pkgver.split('.')[1]}} series) with Surface patches"
archs = ["x86_64"]  # Assuming x86_64 as per typical Surface devices
license = "GPL-2.0-only"
url = "https://github.com/linux-surface/linux-surface"

# _srctag will be substituted by the generator with the actual value.
# Local files (config, patches) are not listed in source; they are accessed via self.chroot_files_path etc.
_srctag_for_git = "{_srctag_for_git}"
source = [
    f"https://github.com/archlinux/linux.git#tag={{_srctag_for_git}}"
]
sha256 = ["SKIP"] # For git sources, SKIP is typical. cbuild verifies commit if possible.

hostmakedepends = [
    {hostmakedepends_list_str},
    "base-kernel-devel", # Standard for Chimera kernel builds
]
depends = ["base-kernel"]
provides = [f"linux={{pkgver.split('.')[0]}}.{{pkgver.split('.')[1]}}"]

options = [
    "!check", "!debug", "!strip", "!scanrundeps", "!scanshlibs", "!lto",
    "textrels", "execstack", "foreignelf"
]

make_env = {{  # Corrected variable name
    "KBUILD_BUILD_HOST": "chimera-linux",
    "KBUILD_BUILD_USER": pkgname,
    # KBUILD_BUILD_TIMESTAMP is typically handled by the kernel's Makefile
    # using SOURCE_DATE_EPOCH set by cbuild.
}}

def prepare(self):
    with self.pushd(self.build_wrksrc): # self.build_wrksrc is the kernel source directory
        self.log("Setting localversion files...")
        (self.chroot_cwd / "localversion.10-pkgrel").write_text(f"-{{self.pkgrel}}\\n")
        (self.chroot_cwd / "localversion.20-pkgname").write_text(f"{{self.pkgname.replace('linux-', '')}}\\n")

        self.log("Running make defconfig...")
        self.do("make", "defconfig")

        self.log("Running make kernelrelease...")
        kernelrelease_out = self.do("make", "-s", "kernelrelease", capture_output=True, check=True)
        kernelrelease = kernelrelease_out.stdout.strip()
        (self.chroot_cwd / "version").write_text(kernelrelease + "\\n")
        self.log(f"Kernel release: {{kernelrelease}}")

        self.log("Running make mrproper...")
        self.do("make", "mrproper")

        self.log("Applying patches...")
        if not (self.chroot_cwd / ".git").is_dir():
            self.do("git", "init")
            self.do("git", "config", "--local", "user.email", "cbuild@chimera-linux.org")
            self.do("git", "config", "--local", "user.name", "cbuild")
            self.do("git", "add", ".")
            self.do("git", "commit", "--allow-empty", "-m", "Initial cbuild commit before patching")

        patches_dir = self.chroot_patches_path
        sorted_patches = sorted(patches_dir.glob("*.patch"))
        if not sorted_patches:
            self.log_warn("No patches found in patches/ directory.")
        for patch_file_chroot_path in sorted_patches:
            self.log(f"Applying patch {{patch_file_chroot_path.name}}...")
            self.do("git", "am", "-3", str(patch_file_chroot_path))

        self.log("Merging kernel configurations...")
        self.do(
            self.chroot_cwd / "scripts/kconfig/merge_config.sh", "-m",
            self.chroot_files_path / "config",        # Use self.chroot_files_path
            self.chroot_files_path / "surface.config",  # Use self.chroot_files_path
            self.chroot_files_path / "arch.config",     # Use self.chroot_files_path
            wrksrc=self.chroot_cwd
        )

        self.log("Running make olddefconfig...")
        self.do("make", f"KERNELRELEASE={{kernelrelease}}", "olddefconfig")
        self.log(f"Prepared {{self.pkgname}} version {{kernelrelease}}")

def build(self):
    with self.pushd(self.build_wrksrc):
        kernelrelease = (self.chroot_cwd / "version").read_text().strip()
        self.log(f"Building kernel version {{kernelrelease}}...")
        self.do("make", f"KERNELRELEASE={{kernelrelease}}", "all")

def install(self):
    with self.pushd(self.build_wrksrc):
        kernelrelease = (self.chroot_cwd / "version").read_text().strip()
        self.log(f"Installing kernel version {{kernelrelease}}...")
        
        modulesdir = self.destdir / f"usr/lib/modules/{{kernelrelease}}"
        image_name_out = self.do("make", "-s", "image_name", capture_output=True, check=True)
        image_name = image_name_out.stdout.strip() # e.g., arch/x86/boot/bzImage

        self.install_dir(modulesdir)
        self.install_file(self.chroot_cwd / image_name, modulesdir, name="vmlinuz", mode=0o644)
        (modulesdir / "pkgbase").write_text(self.pkgname + "\\n")

        self.log("Installing modules...")
        self.do(
            "make",
            f"INSTALL_MOD_PATH={{self.chroot_destdir / 'usr'}}",
            "DEPMOD=/doesnt/exist", # cbuild handles depmod
            "modules_install"
        )

        # Remove build and source links if they exist
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
             if f_path_glob.is_file(): # Ensure it's a file
                self.install_file(f_path_glob, builddir_target, mode=0o644)

        kernel_makefile_path = self.chroot_cwd / "kernel" / "Makefile"
        if kernel_makefile_path.exists():
            self.install_dir(builddir_target / "kernel")
            self.install_file(kernel_makefile_path, builddir_target / "kernel", mode=0o644)
        
        # Assuming x86_64, adapt if other archs are targeted by the generator
        arch_makefile_path = self.chroot_cwd / "arch" / "x86" / "Makefile"
        if arch_makefile_path.exists():
            self.install_dir(builddir_target / "arch" / "x86")
            self.install_file(arch_makefile_path, builddir_target / "arch" / "x86", mode=0o644)

        for d_name in ["scripts", "include"]: # Common dirs
            src_d = self.chroot_cwd / d_name
            if src_d.is_dir():
                self.cp(src_d, builddir_target / d_name, recursive=True, symlinks=True)
        
        arch_include_path = self.chroot_cwd / "arch" / "x86" / "include" # Assuming x86_64
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
    self.depends += ["clang", "pahole"] # Common devel deps
    self.options = ["foreignelf", "execstack", "!scanshlibs"] # Common options
    
    kernelrelease_real = ""
    # Determine kernelrelease from installed modules dir if possible
    # self.parent refers to the main template instance
    if hasattr(self.parent, 'destdir') and (self.parent.destdir / "usr/lib/modules").exists():
        module_paths = list((self.parent.destdir / "usr/lib/modules").glob("*"))
        if module_paths:
            kernelrelease_real = module_paths[0].name
    
    if not kernelrelease_real:
        # Fallback: try to reconstruct from pkgver if destdir isn't populated (e.g. linting)
        # This is a rough heuristic and might not be perfect if pkgver has complex suffixes.
        # The 'version' file written in prepare() is the most reliable source during actual build.
        pkgver_parts = self.parent.pkgver.split('-')[0] # Try to get "X.Y.Z" from "X.Y.Z-archthing"
        # This might need a more robust way to get the kernelrelease string if available
        # on self.parent from the prepare phase. For now, this is a placeholder.
        # A better way would be for the main 'prepare' to store 'kernelrelease' on 'self.parent.kernelrelease_val = kernelrelease'
        # and then _devel could access self.parent.kernelrelease_val.
        # However, template variables are generally read at init.
        # For now, we rely on the glob or accept it might be empty for pure lint.
        # The logging call below is part of the *generated* template.py.
        # It should use the template's self.log_warn() method.
        # self.parent.pkgver needs to be escaped with double curlies for the generator's f-string.
        self.log_warn(f"Warning: Could not reliably determine kernelrelease for -devel subpackage paths during this phase. Using pkgver: {{self.parent.pkgver}}")
        # A simple split might be too naive if pkgver is like "6.1.20.foo1" vs "6.1.20-arch1"
        # For now, let's assume the glob will work during actual packaging.
        # If we need a value for linting, it's tricky.
        # Let's assume for path generation, we need a value.
        # A common pattern is that the version file in build_wrksrc holds it.
        # This subpackage function runs *after* the main install.
        # The kernelrelease variable from the main scope isn't directly accessible here.
        # The glob is the most reliable way post-install.

    if kernelrelease_real:
        return [
            f"usr/lib/modules/{{kernelrelease_real}}/build",
            f"usr/src/{{self.pkgname}}"
        ]
    # If kernelrelease_real could not be determined (e.g. linting before build),
    # return an empty list or paths that might be generically checked by linter.
    # For safety, return empty if not found to avoid errors with undefined paths.
    return []

# -dbg subpackage is typically handled automatically by cbuild if !debug option is not set.
"""
    return template_str

def main() -> None:
    _print_message("--- Linux Surface Cports Template Generator ---", message_styles=["bold", "purple"])
    args = parse_arguments()

    if not args.kernel_stuff_path.is_dir():
        _print_message(f"Error: kernel_stuff_path '{args.kernel_stuff_path}' not found or not a directory.", level="error")
        sys.exit(1)
    if not args.surface_configs_path.is_dir():
        _print_message(f"Error: surface_configs_path '{args.surface_configs_path}' not found or not a directory.", level="error")
        sys.exit(1)
    if not LINUX_SURFACE_REPO_PATH.is_dir():
        _print_message(f"Error: Linux Surface repository not found at '{LINUX_SURFACE_REPO_PATH}'. Please ensure it's cloned correctly.", level="error")
        sys.exit(1)


    _print_message("Step 1: Parsing PKGBUILD...", message_styles=["bold"])
    pkgbuild_file_path = args.kernel_stuff_path / "PKGBUILD"
    pkgbuild_data = parse_pkgbuild(pkgbuild_file_path)
    _print_message(f"Parsed pkgver: {pkgbuild_data['pkgver']}, pkgrel: {pkgbuild_data['pkgrel']}", indent=1)
    _print_message(f"Source tag: {pkgbuild_data['_srctag']}", indent=1)
    _print_message(f"Found {len(pkgbuild_data['patch_filenames'])} patches listed in PKGBUILD.", indent=1)

    _print_message("Step 2: Setting up cport directory and files...", message_styles=["bold"])
    file_checksums = setup_cport_directory(
        args.output_name,
        args.force,
        args.kernel_stuff_path,
        args.surface_configs_path,
        pkgbuild_data,
        LINUX_SURFACE_REPO_PATH
    )
    _print_message("Cport directory and files prepared.", level="success", indent=1)

    _print_message("Step 3: Generating template.py content...", message_styles=["bold"])
    template_content = generate_template_py_content(args.output_name, pkgbuild_data, file_checksums)
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
    # Symlink target should be relative from the location of the symlink
    # e.g., if symlink is main/foo-devel, target is main/foo.
    # So, target is just args.output_name (the directory name)
    target_dir_for_symlink = pathlib.Path(args.output_name)

    if symlink_path.exists() or symlink_path.is_symlink():
        if args.force:
            _print_message(f"Removing existing devel subpackage symlink: {symlink_path}", level="warning", indent=1)
            symlink_path.unlink(missing_ok=True)
        else:
            # If it exists and points to the right place, it's fine. Otherwise, it might be an issue.
            # For simplicity with --force, we just remove and recreate.
            # Without --force, if it exists, we'll let it be unless it's wrong, but symlink_to will fail if it's a dir.
            if not symlink_path.is_symlink() or symlink_path.resolve() != (CPORTS_MAIN_DIR / args.output_name).resolve():
                 _print_message(f"Warning: Devel subpackage symlink {symlink_path} exists but seems incorrect. Consider using --force.", level="warning", indent=1)
            else:
                _print_message(f"Devel subpackage symlink {symlink_path} already exists and is correct.", indent=1)


    if not symlink_path.exists(): # Re-check after potential removal
        try:
            # Create symlink from within CPORTS_MAIN_DIR context for relative path
            # current_dir = pathlib.Path.cwd()
            # os.chdir(CPORTS_MAIN_DIR) # Not ideal to change cwd
            # pathlib.Path(devel_subpackage_name).symlink_to(target_dir_for_symlink, target_is_directory=True)
            # os.chdir(current_dir)
            # A better way:
            symlink_path.symlink_to(target_dir_for_symlink, target_is_directory=True)
            _print_message(f"Created symlink for -devel subpackage: {symlink_path} -> {target_dir_for_symlink}", level="success", indent=1)
        except OSError as e:
            _print_message(f"Error creating symlink for -devel subpackage: {e}", level="error", indent=1)
            _print_message("You might need to run 'cbuild relink-subpkgs' manually in the cports directory.", level="info", indent=1)
    
    print("-" * 60)
    _print_message("--- Generation Complete! ---", level="star", message_styles=["bold"])
    _print_message(f"New cport template for '{args.output_name}' created at:", indent=1)
    _print_message(f"  {CPORTS_MAIN_DIR / args.output_name}", indent=2, message_styles=["cyan"])
    _print_message("To build the kernel, navigate to your cports directory and run:", indent=1)
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
