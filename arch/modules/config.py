#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handles global configuration, progress tracking, and constants for the Arch Linux installer.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Attempt to import from sibling ui module
try:
    from . import ui
except ImportError:
    print("Warning: Could not import sibling 'ui' module in config.py. Attempting absolute.", file=sys.stderr)
    try:
        import ui # type: ignore
    except ImportError:
        print("Error: Failed to import 'ui' module. UI-dependent messages in config.py will be basic.", file=sys.stderr)
        # Define minimal fallbacks if ui import fails
        class MockColors: # type: ignore
            YELLOW = ""; RED = ""; ORANGE = ""; CYAN = ""; # type: ignore
        class MockUI: # type: ignore
            Colors = MockColors(); WARNING_SYMBOL = "! "; INFO_SYMBOL = "i "; ERROR_SYMBOL = "X " # type: ignore
            def print_color(self, text: str, color: str, prefix: str = "", bold: bool = False): print(f"{prefix}{text}") # type: ignore
        ui = MockUI() # type: ignore


# --- Global Dry Run Flag ---
DRY_RUN_MODE: bool = False

# --- Installation Steps Tracking ---
INSTALL_STEPS: List[str] = [
    "gather_config",        # 0
    "prepare_environment",  # 1
    "partition_format",     # 2
    "mount_filesystems",    # 3
    "pacstrap_system",      # 4
    "generate_fstab",       # 5
    "pre_chroot_files",     # 6
    "chroot_configure",     # 7
    "cleanup"               # 8
]
CURRENT_STEP: int = 0
RESTART_STEP: int = 0

# --- Configuration Constants (User-configurable defaults) ---
USER_CONFIG: Dict[str, Any] = {
    "username": "bao",
    "hostname": "bao",
    "timezone": "America/Denver",
    "locale_lang": "en_US.UTF-8",
    "locale_gen": "en_US.UTF-8 UTF-8",
    "vconsole_keymap": "us",
    "target_drive": "",
    "efi_partition_size": "1G",
    "swap_size_gb": "4",
    "zram_fraction": "0.5",
    "lvm_vg_name": "vg_bao",
    "lvm_lv_root_name": "lv_root",
    "lvm_lv_swap_name": "lv_swap",
    "btrfs_subvol_root": "@root",
    "btrfs_subvol_home": "@home",
    "btrfs_subvol_var": "@var",
    "btrfs_subvol_snapshots": "@snapshots",
    "ssh_key_email": "kunihir0@tutanota.com",
    "gpg_key_name": "kunihir0",
    "gpg_key_email": "kunihir0@tutanota.com",
    "cpu_march": "icelake-client",
    "add_chaotic_aur": True,
    "default_monospace_font_pkg": "ttf-sourcecodepro-nerd",
    "btrfs_mount_options": "compress=zstd,ssd,noatime,discard=async"
}

# Hardcoded Passwords (Consider secure handling in a real application)
BAO_PASSWORD: str = "7317"
ROOT_PASSWORD: str = "73177317"

PROGRESS_FILE: Path = Path("/tmp/arch_install_progress.json")


def save_progress() -> None:
    """Saves the current installation step and user configuration to a progress file."""
    global USER_CONFIG, CURRENT_STEP
    if not DRY_RUN_MODE:
        try:
            progress_data: Dict[str, Any] = {
                "current_step": CURRENT_STEP,
                "user_config": USER_CONFIG
            }
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(progress_data, f, indent=4)
        except Exception as e:
            ui.print_color(f"Note: Could not save progress: {e}", ui.Colors.YELLOW, prefix=ui.WARNING_SYMBOL)


def load_progress() -> int:
    """
    Loads installation progress from a file.
    Returns the step to restart from, or 0 if no valid progress is found.
    """
    global RESTART_STEP, USER_CONFIG
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                progress_data: Dict[str, Any] = json.load(f)

            step: Any = progress_data.get("current_step")
            loaded_user_config: Any = progress_data.get("user_config")

            if isinstance(step, int) and 0 <= step < len(INSTALL_STEPS) and isinstance(loaded_user_config, dict):
                RESTART_STEP = step
                USER_CONFIG.update(loaded_user_config)
                ui.print_color(f"Found saved progress at step {step} ({INSTALL_STEPS[step]}) and loaded USER_CONFIG.", ui.Colors.CYAN, prefix=ui.INFO_SYMBOL)

                if not USER_CONFIG.get("target_drive"):
                    ui.print_color("Loaded USER_CONFIG is missing 'target_drive'. Restarting from configuration.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                    PROGRESS_FILE.unlink(missing_ok=True)
                    return 0
                return step
            else:
                ui.print_color("Invalid data in progress file. Starting from beginning.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                PROGRESS_FILE.unlink(missing_ok=True)
        except Exception as e:
            ui.print_color(f"Could not load progress file ({e}). Starting from beginning.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
            PROGRESS_FILE.unlink(missing_ok=True)
    return 0

def set_dry_run_mode(mode: bool) -> None:
    """Sets the global DRY_RUN_MODE."""
    global DRY_RUN_MODE
    DRY_RUN_MODE = mode

def get_dry_run_mode() -> bool:
    """Gets the current DRY_RUN_MODE."""
    return DRY_RUN_MODE

def set_current_step(step_index: int) -> None:
    """Sets the current installation step."""
    global CURRENT_STEP
    if 0 <= step_index < len(INSTALL_STEPS):
        CURRENT_STEP = step_index
    else:
        ui.print_color(f"Invalid step index: {step_index}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)

def get_current_step() -> int:
    """Gets the current installation step index."""
    return CURRENT_STEP

def get_user_config_value(key: str, default: Any = None) -> Any:
    """Gets a specific value from USER_CONFIG, with an optional default."""
    return USER_CONFIG.get(key, default)

def update_user_config_value(key: str, value: Any) -> None:
    """Updates a specific value in USER_CONFIG."""
    global USER_CONFIG
    USER_CONFIG[key] = value

def get_all_user_config() -> Dict[str, Any]:
    """Returns a copy of the entire USER_CONFIG dictionary."""
    return USER_CONFIG.copy()

def set_restart_step(step_index: int) -> None:
    """Sets the restart step index."""
    global RESTART_STEP
    if 0 <= step_index < len(INSTALL_STEPS):
        RESTART_STEP = step_index
    else:
        ui.print_color(f"Invalid restart step index: {step_index}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)

def get_restart_step() -> int:
    """Gets the restart step index."""
    return RESTART_STEP

# Function to get a fresh copy of default user config
def get_default_user_config() -> Dict[str, Any]:
    """Returns a fresh copy of the default USER_CONFIG dictionary."""
    return {
        "username": "bao",
        "hostname": "bao",
        "timezone": "America/Denver",
        "locale_lang": "en_US.UTF-8",
        "locale_gen": "en_US.UTF-8 UTF-8",
        "vconsole_keymap": "us",
        "target_drive": "",
        "efi_partition_size": "1G",
        "swap_size_gb": "4",
        "zram_fraction": "0.5",
        "lvm_vg_name": "vg_bao",
        "lvm_lv_root_name": "lv_root",
        "lvm_lv_swap_name": "lv_swap",
        "btrfs_subvol_root": "@root",
        "btrfs_subvol_home": "@home",
        "btrfs_subvol_var": "@var",
        "btrfs_subvol_snapshots": "@snapshots",
        "ssh_key_email": "kunihir0@tutanota.com",
        "gpg_key_name": "kunihir0",
        "gpg_key_email": "kunihir0@tutanota.com",
        "cpu_march": "icelake-client",
        "add_chaotic_aur": True,
        "default_monospace_font_pkg": "ttf-sourcecodepro-nerd",
        "btrfs_mount_options": "compress=zstd,ssd,noatime,discard=async"
    }