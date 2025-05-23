#!/usr/bin/env python3

import sys
import subprocess
import pathlib
import shutil
import configparser # For checking etc/config.ini for keygen step
import re # For modifying template.py
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
WORK_DIR = pathlib.Path.cwd()
CPORTS_DIR_NAME = "../cports"
LINUX_SURFACE_DIR_NAME = "../linux-surface"

CPORTS_REPO_URL = "https://github.com/chimera-linux/cports.git"
LINUX_SURFACE_REPO_URL = "https://github.com/linux-surface/linux-surface.git"

ORIGINAL_KERNEL_TEMPLATE_NAME_IN_CPORTS = "linux-lts"
INTERIM_TEMPLATE_DIR_BASENAME = "linux-surface-lts-temp"
FINAL_KERNEL_TEMPLATE_BASENAME = "linux-surface-lts-kernel"

# This should match the major.minor of the ORIGINAL_KERNEL_TEMPLATE_NAME_IN_CPORTS's pkgver
LINUX_SURFACE_PATCH_SERIES_DIR = "6.12" 
EXCLUDE_PATCH_CAMERA = "0012-cameras.patch"
EXCLUDE_PATCH_AMD_GPIO = "0013-amd-gpio.patch" # Name in 6.12 series
# The 6.12 linux-surface patch set has 14 patches. Excluding 2 means 12.
EXPECTED_PATCH_COUNT_AFTER_EXCLUSIONS = 12 

CPORTS_ROOT_DIR = WORK_DIR / CPORTS_DIR_NAME
LINUX_SURFACE_ROOT_DIR = WORK_DIR / LINUX_SURFACE_DIR_NAME

def get_pkgver_from_template(template_path: pathlib.Path) -> Optional[str]:
    """Extracts pkgver from a cports template.py file."""
    if not template_path.is_file():
        return None
    try:
        content = template_path.read_text()
        match = re.search(r'^\s*pkgver\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if match:
            return match.group(1)
    except Exception as e:
        _print_message(f"Error reading pkgver from {template_path}: {e}", level="warning", indent=2)
    return None

def main() -> None:
    _print_message("--- Starting Full LTS Surface Kernel Source Preparation (Python) ---", message_styles=["bold"])
    _print_message(f"Script will operate in: {WORK_DIR}")
    _print_message(f"It will ensure '{CPORTS_DIR_NAME}/' and '{LINUX_SURFACE_DIR_NAME}/' subdirectories exist here.")
    print("-" * 60)

    # --- Step 0: Check for git ---
    _print_message("Step 0: Checking for git...", message_styles=["bold"])
    try:
        run_external_command(["git", "--version"], capture_output=True)
        _print_message("Git found.", level="success", indent=1)
    except (subprocess.CalledProcessError, FileNotFoundError):
        _print_message("git command not found. Please install git and ensure it's in your PATH.", level="error")
        sys.exit(1)

    # --- Step 1: Clone Repositories ---
    _print_message("Step 1: Cloning/Verifying Repositories...", message_styles=["bold"])
    _print_message(f"Ensuring cports repository exists at '{CPORTS_ROOT_DIR}'...", indent=1)
    if CPORTS_ROOT_DIR.is_dir():
        _print_message(f"'{CPORTS_DIR_NAME}' directory already exists. Attempting to update...", indent=2)
        try:
            run_external_command(["git", "pull"], cwd=CPORTS_ROOT_DIR)
            _print_message("cports repository updated.", level="success", indent=2)
        except subprocess.CalledProcessError:
            _print_message("Failed to update cports repository. Using existing state.", level="warning", indent=2)
    else:
        run_external_command(["git", "clone", CPORTS_REPO_URL, str(CPORTS_ROOT_DIR)])
        _print_message(f"Cloned cports successfully.", level="success", indent=2)

    _print_message(f"Ensuring linux-surface repository exists at '{LINUX_SURFACE_ROOT_DIR}'...", indent=1)
    if LINUX_SURFACE_ROOT_DIR.is_dir():
        _print_message(f"'{LINUX_SURFACE_DIR_NAME}' directory already exists. Attempting to update...", indent=2)
        try:
            run_external_command(["git", "pull"], cwd=LINUX_SURFACE_ROOT_DIR)
            _print_message("linux-surface repository updated.", level="success", indent=2)
        except subprocess.CalledProcessError:
            _print_message("Failed to update linux-surface repository. Using existing state.", level="warning", indent=2)
    else:
        run_external_command(["git", "clone", LINUX_SURFACE_REPO_URL, str(LINUX_SURFACE_ROOT_DIR)])
        _print_message(f"Cloned linux-surface successfully.", level="success", indent=2)

    # --- Step 2: cports Initial Setup ---
    _print_message("Step 2: cports Initial Setup...", message_styles=["bold"])
    cbuild_exe = CPORTS_ROOT_DIR / "cbuild"
    if not cbuild_exe.is_file():
        _print_message(f"'cbuild' executable not found at '{cbuild_exe}'. Corrupted cports clone?", level="error")
        sys.exit(1)

    _print_message("Ensuring cports signing key is configured...", indent=1)
    config_ini_file = CPORTS_ROOT_DIR / "etc" / "config.ini"
    key_configured = False
    if config_ini_file.is_file():
        config = configparser.ConfigParser(interpolation=None, default_section="cbuild")
        config.read(config_ini_file)
        if (config.has_option("cbuild", "signkey") and config.get("cbuild", "signkey")) or \
           (config.has_section("signing") and config.has_option("signing", "key") and config.get("signing", "key")):
            key_configured = True
            _print_message("Signing key seems to be already configured in etc/config.ini.", indent=2)
    
    if not key_configured:
        _print_message("Signing key not configured. Running './cbuild keygen'...", indent=2)
        run_external_command([str(cbuild_exe), "keygen"], cwd=CPORTS_ROOT_DIR)
        _print_message("Signing key generation/configuration attempted.", level="success", indent=2)
    
    _print_message("Ensuring cbuild build root ('bldroot') is set up...", indent=1)
    bldroot_usr_dir = CPORTS_ROOT_DIR / "bldroot" / "usr"
    if bldroot_usr_dir.is_dir(): # Check for a common subdir to confirm bldroot is populated
        _print_message("'bldroot' already exists and seems populated.", indent=2)
    else:
        _print_message("Setting up 'bldroot' by running './cbuild bootstrap'...", indent=2)
        run_external_command([str(cbuild_exe), "bootstrap"], cwd=CPORTS_ROOT_DIR)
        _print_message("'bldroot' setup complete.", level="success", indent=2)

    # --- Step 3: Prepare Custom Kernel Template ---
    _print_message("Step 3: Preparing Custom Kernel Template...", message_styles=["bold"])
    initial_template_rel_path = pathlib.Path("main") / ORIGINAL_KERNEL_TEMPLATE_NAME_IN_CPORTS
    interim_template_rel_path = pathlib.Path("main") / INTERIM_TEMPLATE_DIR_BASENAME
    
    initial_template_abs_path = CPORTS_ROOT_DIR / initial_template_rel_path
    interim_template_abs_path = CPORTS_ROOT_DIR / interim_template_rel_path

    # --- Automated Kernel Version Compatibility Check ---
    _print_message("Checking base kernel version compatibility with patch series...", indent=1)
    base_template_py_path = initial_template_abs_path / "template.py"
    base_pkgver = get_pkgver_from_template(base_template_py_path)
    if not base_pkgver:
        _print_message(f"Could not determine pkgver from base template '{base_template_py_path}'. Cannot verify patch compatibility.", level="error")
        sys.exit(1)
    
    base_major_minor = ".".join(base_pkgver.split(".")[:2])
    _print_message(f"Base template '{ORIGINAL_KERNEL_TEMPLATE_NAME_IN_CPORTS}' pkgver: {base_pkgver} (Major.Minor: {base_major_minor})", indent=2)
    _print_message(f"Selected Linux Surface patch series: {LINUX_SURFACE_PATCH_SERIES_DIR}", indent=2)

    if base_major_minor != LINUX_SURFACE_PATCH_SERIES_DIR:
        _print_message(
            f"CRITICAL WARNING: Base kernel version ({base_major_minor}) does NOT match the selected "
            f"Surface patch series ({LINUX_SURFACE_PATCH_SERIES_DIR}). This will likely lead to build failures.",
            level="error"
        )
        _print_message("Please update LINUX_SURFACE_PATCH_SERIES_DIR in this script to match the base kernel's major.minor version.", level="error")
        _print_message(f"Alternatively, choose a different ORIGINAL_KERNEL_TEMPLATE_NAME_IN_CPORTS if you need a specific patch series.", level="error")
        sys.exit(1)
    else:
        _print_message("Base kernel version matches selected patch series. Proceeding.", level="success", indent=2)


    _print_message(f"Copying '{initial_template_rel_path}' to '{interim_template_rel_path}'...", indent=1)
    final_template_rel_path_for_check = pathlib.Path("main") / FINAL_KERNEL_TEMPLATE_BASENAME
    final_template_abs_path_for_check = CPORTS_ROOT_DIR / final_template_rel_path_for_check
    if interim_template_abs_path.exists():
        _print_message(f"Removing existing directory '{interim_template_abs_path}' for a fresh copy...", indent=2)
        shutil.rmtree(interim_template_abs_path)
    if final_template_abs_path_for_check.exists():
        _print_message(f"Removing existing final directory '{final_template_abs_path_for_check}' to avoid conflicts...", indent=2)
        shutil.rmtree(final_template_abs_path_for_check)

    if not initial_template_abs_path.is_dir():
        _print_message(f"Original kernel template '{initial_template_abs_path}' not found in cports!", level="error")
        sys.exit(1)
    shutil.copytree(initial_template_abs_path, interim_template_abs_path)
    _print_message(f"Copied template to '{interim_template_abs_path}'.", level="success", indent=2)

    patches_dir_full_path = interim_template_abs_path / "patches"
    config_file_full_path = interim_template_abs_path / "files" / "config-x86_64.generic"
    template_py_full_path = interim_template_abs_path / "template.py"

    _print_message(f"Populating and cleaning patches directory '{patches_dir_full_path}'...", indent=1)
    surface_patches_source_dir = LINUX_SURFACE_ROOT_DIR / "patches" / LINUX_SURFACE_PATCH_SERIES_DIR
    if not surface_patches_source_dir.is_dir():
        _print_message(f"Linux Surface patches for series '{LINUX_SURFACE_PATCH_SERIES_DIR}' not found at '{surface_patches_source_dir}'!", level="error")
        sys.exit(1)

    patches_dir_full_path.mkdir(parents=True, exist_ok=True)
    _print_message(f"Cleaning out any pre-existing patches from '{patches_dir_full_path}'...", indent=2)
    for old_patch in patches_dir_full_path.glob("*.patch"):
        old_patch.unlink()
    
    _print_message(f"Copying Surface {LINUX_SURFACE_PATCH_SERIES_DIR} patches from '{surface_patches_source_dir}'...", indent=2)
    for patch_file in surface_patches_source_dir.glob("*.patch"):
        shutil.copy2(patch_file, patches_dir_full_path)

    excluded_camera_patch_path = patches_dir_full_path / EXCLUDE_PATCH_CAMERA
    if excluded_camera_patch_path.is_file():
        _print_message(f"Removing excluded camera patch: '{EXCLUDE_PATCH_CAMERA}'", indent=2)
        excluded_camera_patch_path.unlink()
    else:
        _print_message(f"Note: Camera patch '{EXCLUDE_PATCH_CAMERA}' was not found in the copied set (this is okay).", indent=2)

    excluded_amd_patch_path = patches_dir_full_path / EXCLUDE_PATCH_AMD_GPIO
    if excluded_amd_patch_path.is_file():
        _print_message(f"Removing excluded AMD GPIO patch: '{EXCLUDE_PATCH_AMD_GPIO}'", indent=2)
        excluded_amd_patch_path.unlink()
    else:
        _print_message(f"Note: AMD GPIO patch '{EXCLUDE_PATCH_AMD_GPIO}' was not found in the copied set (this is okay).", indent=2)
    
    _print_message(f"Patch directory populated. Contents of '{patches_dir_full_path}':", indent=2)
    for item in sorted(patches_dir_full_path.iterdir()): print(f"    {item.name}") # Sorted for consistent output
    
    actual_patch_count = len(list(patches_dir_full_path.glob("*.patch")))
    _print_message(f"Found {actual_patch_count} patch files. Expected around {EXPECTED_PATCH_COUNT_AFTER_EXCLUSIONS}.", indent=2)
    if not (EXPECTED_PATCH_COUNT_AFTER_EXCLUSIONS - 2 <= actual_patch_count <= EXPECTED_PATCH_COUNT_AFTER_EXCLUSIONS + 2):
        _print_message(f"Patch count ({actual_patch_count}) seems unusual. Please verify.", level="warning", indent=3)


    _print_message(f"Editing kernel config '{config_file_full_path}'...", indent=1)
    if not config_file_full_path.is_file():
        _print_message(f"Kernel config file '{config_file_full_path}' not found!", level="error")
        sys.exit(1)
    
    config_content = config_file_full_path.read_text().splitlines()
    new_config_content: List[str] = []
    atomisp_found_in_config = False
    atomisp_modified = False
    for line in config_content:
        stripped_line = line.strip()
        if stripped_line.startswith("CONFIG_INTEL_ATOMISP="):
            if stripped_line != "CONFIG_INTEL_ATOMISP=n": # Only change if not already 'n'
                new_config_content.append(f"# {stripped_line} (Original value, commented by script)")
                new_config_content.append("CONFIG_INTEL_ATOMISP=n")
                atomisp_modified = True
            else:
                new_config_content.append(line) # Already n, keep as is
            atomisp_found_in_config = True
        elif stripped_line == "# CONFIG_INTEL_ATOMISP is not set":
            new_config_content.append(line) 
            atomisp_found_in_config = True # Considered handled
        else:
            new_config_content.append(line)
            
    if not atomisp_found_in_config:
         _print_message("CONFIG_INTEL_ATOMISP was not found in the config file. Adding 'CONFIG_INTEL_ATOMISP=n'.", level="info", indent=2)
         new_config_content.append("CONFIG_INTEL_ATOMISP=n") # Add it if not found at all
         atomisp_modified = True
    elif not atomisp_modified and atomisp_found_in_config:
         _print_message("CONFIG_INTEL_ATOMISP already correctly set or commented out.", indent=2)

    if atomisp_modified or not atomisp_found_in_config :
        config_file_full_path.write_text("\n".join(new_config_content) + "\n")
        _print_message(f"Updated CONFIG_INTEL_ATOMISP in '{config_file_full_path}'.", indent=2)
    
    _print_message("Verifying CONFIG_INTEL_ATOMISP setting (should be 'n' or commented):", indent=3)
    run_external_command(["grep", "-E", "^(# )?CONFIG_INTEL_ATOMISP", str(config_file_full_path)], check=False, capture_output=True)


    _print_message(f"Editing template.py '{template_py_full_path}'...", indent=1)
    if not template_py_full_path.is_file():
        _print_message(f"Template file '{template_py_full_path}' not found!", level="error")
        sys.exit(1)
    
    template_content = template_py_full_path.read_text()
    template_content = re.sub(
        rf'pkgname\s*=\s*"{ORIGINAL_KERNEL_TEMPLATE_NAME_IN_CPORTS}"',
        f'pkgname = "{FINAL_KERNEL_TEMPLATE_BASENAME}"',
        template_content
    )
    template_content = re.sub(
        r'pkgdesc\s*=\s*.*', 
        f'pkgdesc = "Linux kernel (LTS {LINUX_SURFACE_PATCH_SERIES_DIR} series) with Surface patches for SP7"',
        template_content
    )
    template_content = re.sub(
        rf'@subpackage\(\s*"{ORIGINAL_KERNEL_TEMPLATE_NAME_IN_CPORTS}-devel"\s*\)',
        f'@subpackage("{FINAL_KERNEL_TEMPLATE_BASENAME}-devel")',
        template_content
    )
    template_content = re.sub(
        rf'@subpackage\(\s*"{ORIGINAL_KERNEL_TEMPLATE_NAME_IN_CPORTS}-dbg",\s*self.build_dbg\s*\)',
        f'@subpackage("{FINAL_KERNEL_TEMPLATE_BASENAME}-dbg", self.build_dbg)',
        template_content
    )
    template_py_full_path.write_text(template_content)
    _print_message("Modified pkgname, pkgdesc, and subpackage names.", indent=2)

    # --- Step 4: Rename the Template Directory ---
    _print_message("Step 4: Renaming template directory...", message_styles=["bold"])
    final_template_abs_path = CPORTS_ROOT_DIR / "main" / FINAL_KERNEL_TEMPLATE_BASENAME
    
    if str(interim_template_abs_path.name) != FINAL_KERNEL_TEMPLATE_BASENAME:
        if interim_template_abs_path.is_dir():
            interim_template_abs_path.rename(final_template_abs_path)
            _print_message(f"Renamed '{interim_template_abs_path}' to '{final_template_abs_path}'.", level="success", indent=1)
        elif final_template_abs_path.is_dir():
            _print_message(f"Directory '{interim_template_abs_path.name}' not found, but '{final_template_abs_path.name}' already exists. Assuming already renamed.", indent=1)
        else:
            _print_message(f"Source directory '{interim_template_abs_path.name}' not found for renaming!", level="error")
            sys.exit(1)
    else:
        _print_message(f"Template directory name is already '{FINAL_KERNEL_TEMPLATE_BASENAME}'. No rename needed.", indent=1)

    # --- Step 5: Relink Subpackages ---
    _print_message("Step 5: Relinking subpackages...", message_styles=["bold"])
    final_template_rel_for_cbuild = f"main/{FINAL_KERNEL_TEMPLATE_BASENAME}"
    if final_template_abs_path.is_dir():
        run_external_command([str(cbuild_exe), "relink-subpkgs", final_template_rel_for_cbuild], cwd=CPORTS_ROOT_DIR)
        _print_message(f"Subpackage relinking attempted for '{final_template_rel_for_cbuild}'.", level="success", indent=1)
    else:
        _print_message(f"Final template directory '{final_template_abs_path}' not found. Skipping relink-subpkgs.", level="warning", indent=1)

    print("-" * 60)
    _print_message("--- All preparation steps complete! ---", level="star", message_styles=["bold"])
    _print_message(f"The template is now located at: '{final_template_abs_path}'", indent=1)
    _print_message(f"You should now be able to build from '{CPORTS_ROOT_DIR}' with:", indent=1)
    _print_message(f"  {_color_text(str(cbuild_exe) + ' pkg ' + final_template_rel_for_cbuild, color_name='green', style_names=['bold'])}", indent=2)
    print("-" * 60)

if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError:
        _print_message("A command failed to execute. See output above.", level="error")
        sys.exit(1)
    except Exception as e:
        _print_message(f"An unexpected script error occurred: {e}", level="error")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print(COLORS.get("reset", "\033[0m"))

