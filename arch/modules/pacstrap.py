#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handles the pacstrap process for installing the base Arch Linux system and
essential packages, along with verification of the installation.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List as TypingList, Optional
import subprocess # For subprocess.CompletedProcess type hint

# Attempt to import from sibling modules
try:
    from . import config as cfg
    from . import ui
    from . import core
except ImportError:
    print("Warning: Could not import sibling modules in pacstrap.py. Attempting absolute.", file=sys.stderr)
    try:
        import config as cfg # type: ignore
        import ui # type: ignore
        import core # type: ignore
    except ImportError as e:
        print(f"Error: Failed to import 'config', 'ui', or 'core' modules in pacstrap.py: {e}", file=sys.stderr)
        sys.exit(1)

def pacstrap_system() -> None:
    """
    Installs the base system and a predefined list of packages to /mnt using pacstrap.
    """
    ui.print_section_header("Installing Base System (pacstrap)")
    if cfg.get_current_step() > cfg.INSTALL_STEPS.index("pacstrap_system"):
        ui.print_step_info("Skipping (already completed)")
        sys.stdout.write("\n"); return

    user_config: Dict[str, Any] = cfg.get_all_user_config()
    
    # Define the list of packages to install
    # This list should be maintained and updated as per requirements.
    pkgs_to_install: TypingList[str] = [
        "base", "base-devel", "linux-surface", "linux-surface-headers", "systemd",
        "efibootmgr", "dracut", "intel-ucode", "lvm2", "btrfs-progs",
        "gdm", "gnome-shell", "gnome-session", "gnome-control-center", "nautilus",
        "gnome-terminal", "xdg-desktop-portal-gnome", "gnome-keyring", "seahorse",
        "neovim", "networkmanager", "openssh", "bluez", "bluez-utils", "gnupg",
        "pipewire", "pipewire-pulse", "pipewire-alsa", "wireplumber",
        "noto-fonts", "noto-fonts-cjk", "noto-fonts-emoji",
        str(user_config.get("default_monospace_font_pkg", "ttf-sourcecodepro-nerd")), # Ensure it's a string
        "linux-firmware", "sof-firmware", "zram-generator",
        "curl", "sudo", "git", "go"
        # Add other essential packages here
    ]

    core.run_command(
        ["pacstrap", "/mnt"] + pkgs_to_install,
        destructive=True,
        retry_count=2, # Pacstrap can sometimes fail due to network issues
        retry_delay=10.0,
        custom_spinner_message="Pacstrapping base system and packages"
    )

    if not cfg.get_dry_run_mode():
        ui.print_step_info("Debug: Listing /mnt/boot/ contents immediately after pacstrap...")
        # destructive=False as ls is read-only
        ls_boot_proc: Optional[subprocess.CompletedProcess] = core.run_command(
            ["ls", "-Alh", "/mnt/boot"],
            capture_output=True, destructive=False, show_spinner=False, check=False
        )
        if ls_boot_proc and ls_boot_proc.stdout:
            ui.print_color(f"/mnt/boot/ contents:\n{ls_boot_proc.stdout.strip()}", ui.Colors.MINT)
        else:
            ui.print_color("Could not list /mnt/boot/ contents or it is empty (after pacstrap).", ui.Colors.ORANGE)

    ui.print_color("Base system installation complete.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    cfg.set_current_step(cfg.INSTALL_STEPS.index("generate_fstab"))
    cfg.save_progress()
    sys.stdout.write("\n")

def verify_pacstrap(no_verify_arg: bool) -> None:
    """
    Verifies the pacstrap installation by checking for key directories and packages.
    """
    if no_verify_arg:
        ui.print_step_info("Skipping pacstrap verification as per --no-verify.")
        sys.stdout.write("\n"); return

    ui.print_section_header("Verifying Pacstrap Installation")
    all_ok: bool = True

    def _check_key_dirs() -> bool:
        if cfg.get_dry_run_mode(): return True
        mnt_path: Path = Path("/mnt")
        key_dirs: TypingList[Path] = [
            mnt_path / "bin", mnt_path / "etc", mnt_path / "usr", mnt_path / "boot"
        ]
        return all(d.is_dir() for d in key_dirs)

    def _check_package_installed(pkg_name: str) -> bool:
        if cfg.get_dry_run_mode():
            ui.print_color(f"[DRY RUN] Assuming '{pkg_name}' package would be installed.", ui.Colors.PEACH)
            return True
        
        ui.print_step_info(f"Verifying '{pkg_name}' package installation via arch-chroot...")
        # destructive=False as pacman -Q is read-only
        proc: Optional[subprocess.CompletedProcess] = core.run_command(
            ["arch-chroot", "/mnt", "pacman", "-Q", pkg_name],
            capture_output=True, destructive=False, show_spinner=False, check=False # check=False to handle non-zero exit if not found
        )
        if proc and proc.returncode == 0 and proc.stdout: # Check stdout for package info
            ui.print_color(f"'{pkg_name}' package IS installed: {proc.stdout.strip()}", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
            return True
        else:
            stderr_msg: str = proc.stderr.strip() if proc and proc.stderr else "Unknown error or package not found"
            ui.print_color(f"CRITICAL: '{pkg_name}' package NOT FOUND after pacstrap. pacman -Q output: {stderr_msg}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
            return False

    if not core.verify_step(_check_key_dirs(), "Key directories exist after pacstrap", critical=True):
        all_ok = False
    
    # Verify a few critical packages
    critical_packages_to_check: TypingList[str] = ["linux-surface", "dracut", "systemd", "base"]
    for pkg in critical_packages_to_check:
        if not core.verify_step(_check_package_installed(pkg), f"'{pkg}' package is installed", critical=True):
            all_ok = False

    if all_ok:
        ui.print_color("Pacstrap verification successful.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    else:
        ui.print_color("One or more pacstrap verifications failed.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
    sys.stdout.write("\n")