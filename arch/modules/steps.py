#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Contains high-level installation step functions for the Arch Linux installer.
These functions often orchestrate calls to more specialized modules.
"""

import sys
import subprocess # For CalledProcessError
from pathlib import Path
from typing import Dict, Any

# Attempt to import from sibling modules
try:
    from . import config as cfg
    from . import ui
    from . import core
    from . import disk # For select_drive
    # Other modules like pacstrap, chroot, filesystem will be called by main orchestrator
except ImportError:
    print("Warning: Could not import sibling modules in steps.py. Attempting absolute.", file=sys.stderr)
    try:
        import config as cfg # type: ignore
        import ui # type: ignore
        import core # type: ignore
        import disk # type: ignore
    except ImportError as e:
        print(f"Error: Failed to import 'config', 'ui', 'core', or 'disk' modules in steps.py: {e}", file=sys.stderr)
        sys.exit(1)


def gather_initial_config() -> None:
    """
    Gathers initial system configuration, primarily the target drive.
    Other settings use defaults but ensures they are correctly typed if loaded from progress.
    """
    ui.print_section_header("Gathering System Configuration")
    
    # Prompt for target_drive, critical for the installation.
    # This uses disk.select_drive()
    selected_drive: str = disk.select_drive()
    cfg.update_user_config_value("target_drive", selected_drive)
    
    user_config = cfg.get_all_user_config() # Get current config with selected drive

    # Display default values being used
    ui.print_color(f"Using hostname: {user_config['hostname']} (default)", ui.Colors.CYAN)
    ui.print_color(f"Using username: {user_config['username']} (default)", ui.Colors.CYAN)
    ui.print_color(f"Using timezone: {user_config['timezone']} (default)", ui.Colors.CYAN)
    ui.print_color(f"Using locale language: {user_config['locale_lang']} (default)", ui.Colors.CYAN)
    ui.print_color(f"Using locale.gen entry: {user_config['locale_gen']} (default)", ui.Colors.CYAN)
    ui.print_color(f"Using vconsole keymap: {user_config['vconsole_keymap']} (default)", ui.Colors.CYAN)
    ui.print_color(f"Using disk swap size: {user_config['swap_size_gb']}GB (default)", ui.Colors.CYAN)
    ui.print_color(f"Using ZRAM fraction: {user_config['zram_fraction']} (default)", ui.Colors.CYAN)
    ui.print_color(f"Adding Chaotic-AUR: {'Yes' if user_config.get('add_chaotic_aur') else 'No'} (default)", ui.Colors.CYAN)

    ui.print_color("Initial configuration set.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    cfg.set_current_step(cfg.INSTALL_STEPS.index("prepare_environment"))
    cfg.save_progress() # Save USER_CONFIG with the selected target_drive
    sys.stdout.write("\n")


def display_summary_and_confirm() -> None:
    """Displays a summary of the installation plan and asks for user confirmation."""
    ui.print_section_header("Installation Plan Summary")
    if cfg.get_dry_run_mode():
        ui.print_color("[DRY RUN MODE - NO DISK CHANGES WILL BE MADE]", ui.Colors.YELLOW, bold=True, prefix=ui.WARNING_SYMBOL)
    
    user_config: Dict[str, Any] = cfg.get_all_user_config()
    # Ensure all values are strings for display, especially booleans
    summary_user_config: Dict[str, str] = {
        k: (str(v).lower() if isinstance(v, bool) else str(v)) for k, v in user_config.items()
    }
    
    swap_size_gb_val: float = 0.0
    try:
        swap_size_gb_val = float(summary_user_config.get('swap_size_gb', "0"))
    except ValueError:
        pass


    summary_items = [
        ("User", summary_user_config.get('username', 'N/A'), f"{cfg.BAO_PASSWORD[:2]}** (hardcoded)"),
        ("Root Password", f"{cfg.ROOT_PASSWORD[:2]}** (hardcoded, login will be disabled)", ""),
        ("Hostname", summary_user_config.get('hostname', 'N/A'), ""),
        ("Target Drive", summary_user_config.get('target_drive', 'N/A'), ui.Colors.BOLD + ui.Colors.PINK),
        ("EFI Partition Size", summary_user_config.get('efi_partition_size', 'N/A'), ""),
        ("Disk Swap Size", f"{summary_user_config.get('swap_size_gb', 'N/A')}GB", "LVM LV, resizable post-install" if swap_size_gb_val > 0 else "None (ZRAM only)"),
        ("ZRAM Fraction", f"{summary_user_config.get('zram_fraction', 'N/A')} (of total RAM)", ""),
        ("LVM VG Name", summary_user_config.get('lvm_vg_name', 'N/A'), ""),
        ("Btrfs Subvolumes", f"@{summary_user_config.get('btrfs_subvol_root', 'N/A')}, @{summary_user_config.get('btrfs_subvol_home', 'N/A')}, etc.", ""),
        ("Timezone", summary_user_config.get('timezone', 'N/A'), ""),
        ("Locale", summary_user_config.get('locale_lang', 'N/A'), ""),
        ("Keyboard", summary_user_config.get('vconsole_keymap', 'N/A'), ""),
        ("Kernel", "linux-surface (for Surface Pro 7)", ""), # This is specific, consider making it configurable
        ("Desktop", f"Minimal GNOME (Wayland) with auto-login for '{summary_user_config.get('username', 'N/A')}'", ""),
        ("Default Editor", "Neovim", ""), # Specific
        ("Monospace Font", summary_user_config.get('default_monospace_font_pkg', 'N/A'), ""),
        ("Web Browser", "Google Chrome (AUR) - to be installed by chroot script", ""), # Specific
        ("CPU Optimization (makepkg)", f"-march={summary_user_config.get('cpu_march', 'N/A')}", ""),
        ("Add Chaotic-AUR", "Yes" if user_config.get('add_chaotic_aur') else "No", "") # Use original boolean for "Yes/No"
    ]

    for label, value, notes_or_color in summary_items:
        extra_info: str = ""
        value_color: str = ui.Colors.CYAN
        if isinstance(notes_or_color, str) and notes_or_color.startswith('\033['): # Check if it's an ANSI color
            value_color = notes_or_color
        elif notes_or_color: # If it's a non-empty string note
            extra_info = f" {ui.Colors.PEACH}({notes_or_color}){ui.Colors.RESET}"
        
        sys.stdout.write(f"  {ui.Colors.LAVENDER}{label}:{ui.Colors.RESET} {value_color}{value}{ui.Colors.RESET}{extra_info}\n")

    ui.print_color("\nCRITICAL WARNING:", ui.Colors.RED + ui.Colors.BOLD, prefix=ui.ERROR_SYMBOL)
    ui.print_color(f"ALL DATA ON {user_config.get('target_drive', 'N/A')} WILL BE PERMANENTLY ERASED (if not in dry run).", ui.Colors.RED)
    
    if not ui.prompt_yes_no("Proceed with installation plan?", default_yes=False):
        ui.print_color("Aborted by user.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
        sys.exit(0)
    
    ui.print_color("Proceeding with installation...", ui.Colors.GREEN, prefix=ui.PROGRESS_SYMBOL)
    sys.stdout.write("\n")


def check_internet_connection() -> bool:
    """Checks for an active internet connection by pinging archlinux.org."""
    ui.print_step_info("Checking internet connection...")
    try:
        # destructive=False as ping is read-only
        core.run_command(["ping", "-c", "1", "archlinux.org"], capture_output=True, destructive=False, show_spinner=False, check=True)
        ui.print_color("Internet connection active.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
        return True
    except subprocess.CalledProcessError:
        ui.print_color("Internet check failed. archlinux.org is not reachable.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        return False
    except FileNotFoundError: # ping command not found
        ui.print_color("`ping` command not found. Assuming connected (cannot verify).", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
        return True # Proceed with caution


def prepare_live_environment() -> None:
    """Prepares the live Arch Linux environment by installing necessary tools and configuring repositories."""
    ui.print_section_header("Preparing Live Environment")
    if cfg.get_current_step() > cfg.INSTALL_STEPS.index("prepare_environment"):
        ui.print_step_info("Skipping (already completed)")
        sys.stdout.write("\n"); return

    if not check_internet_connection() and not cfg.get_dry_run_mode():
        if not ui.prompt_yes_no("Internet connection check failed. Continue anyway?", default_yes=False):
            sys.exit(1)

    # Install essential tools for the installation process
    core.run_command(
        ["pacman", "-S", "--noconfirm", "--needed", "curl", "arch-install-scripts", "gptfdisk", "lvm2", "btrfs-progs"],
        destructive=True, # This modifies the live system
        custom_spinner_message="Installing essential tools (curl, arch-install-scripts, etc.)"
    )

    # Add linux-surface repository and GPG key
    pacman_conf_path: Path = Path("/etc/pacman.conf")
    surface_repo_header: str = "[linux-surface]"
    surface_repo_entry: str = f"\n{surface_repo_header}\nServer = https://pkg.surfacelinux.com/arch/\n"

    if cfg.get_dry_run_mode():
        ui.print_dry_run_command(f"ensure {surface_repo_header} in {pacman_conf_path}")
    else:
        try:
            content: str = pacman_conf_path.read_text() if pacman_conf_path.exists() else ""
            if surface_repo_header not in content:
                with open(pacman_conf_path, "a", encoding="utf-8") as f:
                    f.write(surface_repo_entry)
                ui.print_color(f"Appended {surface_repo_header} to {pacman_conf_path}", ui.Colors.MINT)
            else:
                ui.print_color(f"{surface_repo_header} already in {pacman_conf_path}", ui.Colors.CYAN)
        except Exception as e:
            ui.print_color(f"Error updating {pacman_conf_path}: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

    ui.print_step_info("Adding linux-surface GPG key to live environment...")
    # The GPG key import commands are destructive as they modify the keyring
    core.run_command(
        "curl -s https://raw.githubusercontent.com/linux-surface/linux-surface/master/pkg/keys/surface.asc | pacman-key --add -",
        shell=True, destructive=True
    )
    core.run_command(["pacman-key", "--lsign-key", "56C464BAAC421453"], destructive=True)
    
    ui.print_step_info("Syncing pacman databases...")
    core.run_command(["pacman", "-Sy"], destructive=True) # Syncs databases

    ui.print_color("Live environment prepared.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    cfg.set_current_step(cfg.INSTALL_STEPS.index("partition_format"))
    cfg.save_progress()
    sys.stdout.write("\n")


def final_cleanup_and_reboot_instructions() -> None:
    """Prints final instructions after installation (or dry run) is complete."""
    ui.print_section_header("Finalizing Installation")
    
    progress_file: Path = cfg.PROGRESS_FILE
    if not cfg.get_dry_run_mode() and progress_file.exists():
        try:
            progress_file.unlink()
            ui.print_color("Removed progress tracking file.", ui.Colors.MINT)
        except Exception as e:
            ui.print_color(f"Could not remove progress file: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

    ui.print_color("\n--- INSTALLATION SCRIPT COMPLETE (OR DRY RUN FINISHED) ---", ui.Colors.GREEN + ui.Colors.BOLD, prefix=ui.SUCCESS_SYMBOL)
    
    user_config = cfg.get_all_user_config()
    if not cfg.get_dry_run_mode():
        ui.print_color("It should now be safe to reboot your system.", ui.Colors.MINT)
        ui.print_color("Unmount filesystems first: 'umount -R /mnt' then 'swapoff -a' (if swap was used).", ui.Colors.LIGHT_BLUE)
        ui.print_color("Then, type 'reboot' or 'exit' and then 'reboot'.", ui.Colors.MINT)
        ui.print_color(f"User '{user_config.get('username', 'N/A')}' will auto-login. Root login is disabled.", ui.Colors.LIGHT_BLUE)
        ui.print_color("All setup, including AUR packages and keys, was attempted during installation.", ui.Colors.LIGHT_BLUE)
        ui.print_color("Check terminal output for any errors, especially during the user-specific setup part within chroot.", ui.Colors.PEACH)
        ui.print_color("Remember to remove the installation media.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
    else:
        ui.print_color("Dry run complete. No changes were made to your system.", ui.Colors.MINT)