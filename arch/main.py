#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main entry point for the Arch Linux installation script.
Orchestrates the installation process using modular components.
"""

import sys
import os
import argparse
import time
import subprocess # For CalledProcessError
from typing import List, Any, Dict

# Assuming 'arch' is in PYTHONPATH or this script is run from the parent directory of 'arch'
# For a structured project, 'arch' might be a package.
# Use relative imports when main.py is inside the 'arch' package and run from there.
try:
    from .modules import config as cfg
    from .modules import ui
    from .modules import core
    from .modules import disk
    from .modules import filesystem
    from .modules import pacstrap as strap
    from .modules import chroot
    from .modules import steps
except ImportError as e:
    print(f"Error: Could not import installation modules in main.py: {e}", file=sys.stderr)
    print("Ensure the script is run from the correct directory (e.g., the parent of 'arch') or PYTHONPATH is set correctly if using absolute imports.", file=sys.stderr)
    sys.exit(1)

def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments for the installer."""
    parser = argparse.ArgumentParser(description='Arch Linux Enhanced Installer')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry run mode (no actual changes will be made)'
    )
    parser.add_argument(
        '--step',
        type=int,
        choices=range(len(cfg.INSTALL_STEPS)),
        help=(
            f'Start from specific step: '
            f'{", ".join([f"{i}:{s}" for i, s in enumerate(cfg.INSTALL_STEPS)])}'
        )
    )
    parser.add_argument(
        '--no-verify',
        action='store_true',
        help='Skip verification steps (NOT RECOMMENDED)'
    )
    return parser.parse_args()

def main_orchestrator() -> int:
    """
    Main function to orchestrate the Arch Linux installation process.
    """
    args = parse_arguments()

    # Handle dry run mode based on argument or root privileges
    if os.geteuid() != 0 and not args.dry_run:
        ui.print_color("Script must be run as root for actual installation.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
        if not ui.prompt_yes_no("Run in DRY RUN mode instead?", default_yes=True):
            sys.exit(1)
        cfg.set_dry_run_mode(True)
    elif args.dry_run:
        cfg.set_dry_run_mode(True)
    else:
        cfg.set_dry_run_mode(False) # Explicitly set to False if running as root without --dry-run

    ui.print_header("Arch Linux Enhanced Installer")
    if cfg.get_dry_run_mode():
        ui.print_color("DRY RUN MODE ENABLED. No changes will be made.", ui.Colors.YELLOW, bold=True, prefix=ui.WARNING_SYMBOL)
    else:
        ui.print_color("LIVE MODE ENABLED. Script WILL make changes to your system!", ui.Colors.RED + ui.Colors.BLINK, bold=True, prefix=ui.ERROR_SYMBOL)
        ui.print_color("Ensure you have BACKED UP any important data before proceeding.", ui.Colors.ORANGE, bold=True, prefix=ui.WARNING_SYMBOL)

    # Load progress and handle step overrides
    initial_restart_step: int = cfg.load_progress() # Loads USER_CONFIG as well

    if args.step is not None:
        cfg.set_restart_step(args.step)
        ui.print_color(f"Overriding progress. Starting from step {args.step} ({cfg.INSTALL_STEPS[args.step]}) as per command line.", ui.Colors.CYAN, prefix=ui.INFO_SYMBOL)
        if cfg.get_restart_step() == 0 or not cfg.get_user_config_value("target_drive"):
            ui.print_color("Command line --step requires re-gathering config or target_drive is missing from loaded config.", ui.Colors.CYAN)
            # Reset USER_CONFIG to defaults if --step is forcing an early stage or config is bad
            cfg.USER_CONFIG = cfg.get_default_user_config().copy() # Reset to full defaults
            cfg.set_current_step(0) # Force gather_config if --step implies it or config is bad
    else:
        cfg.set_restart_step(initial_restart_step)

    cfg.set_current_step(cfg.get_restart_step())

    # Critical check: if not starting from step 0, ensure target_drive is set
    if cfg.get_current_step() > 0 and not cfg.get_user_config_value("target_drive"):
        ui.print_color("Target drive not configured from saved progress, critical for subsequent steps. Restarting from configuration.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
        cfg.set_current_step(0)
        cfg.USER_CONFIG = cfg.get_default_user_config().copy() # Reset USER_CONFIG

    if cfg.get_current_step() == 0: # Only ask this if we are truly starting from step 0
        if not ui.prompt_yes_no("Ready to begin the configuration process?", default_yes=True):
            sys.exit(0)

    start_time = time.time()
    try:
        # --- Installation Workflow ---
        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("gather_config"):
            steps.gather_initial_config() # Prompts for drive, sets defaults
            steps.display_summary_and_confirm() # Displays plan, asks for confirmation

        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("prepare_environment"):
            steps.prepare_live_environment()

        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("partition_format"):
            disk.partition_and_format()
            disk.verify_partitions_lvm(args.no_verify)

        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("mount_filesystems"):
            filesystem.mount_filesystems()
            filesystem.verify_mounts(args.no_verify)

        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("pacstrap_system"):
            strap.pacstrap_system()
            strap.verify_pacstrap(args.no_verify)

        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("generate_fstab"):
            filesystem.generate_fstab()
            # fstab verification is now part of generate_fstab

        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("pre_chroot_files"):
            chroot.pre_chroot_file_configurations()

        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("chroot_configure"):
            chroot.chroot_configure_system()
            chroot.verify_chroot_configs(args.no_verify)
        
        # Cleanup is the final step in the INSTALL_STEPS list
        if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("cleanup"):
             steps.final_cleanup_and_reboot_instructions()
             cfg.set_current_step(cfg.INSTALL_STEPS.index("cleanup") + 1) # Mark as fully complete
             cfg.save_progress()


    except subprocess.CalledProcessError as e:
        ui.print_color(f"A critical command failed (return code {e.returncode}). Installation cannot continue.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
        ui.print_color(f"Command: {' '.join(e.cmd) if isinstance(e.cmd, list) else e.cmd}", ui.Colors.RED) # type: ignore
        if e.stdout:
            ui.print_color(f"Stdout:\n{e.stdout.strip() if isinstance(e.stdout, str) else e.stdout.decode(errors='replace').strip()}", ui.Colors.RED)
        if e.stderr:
            ui.print_color(f"Stderr:\n{e.stderr.strip() if isinstance(e.stderr, str) else e.stderr.decode(errors='replace').strip()}", ui.Colors.RED)
        ui.print_color("Check error messages. Manually clean up if in live mode (e.g., umount -R /mnt).", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
        return 1 # Indicate failure
    except SystemExit: # Raised by sys.exit()
        return 0 # Or appropriate exit code if sys.exit had one
    except KeyboardInterrupt:
        ui.print_color("\nInstallation aborted by user (Ctrl+C).", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
        return 1 # Indicate failure
    except Exception as e:
        ui.print_color(f"An unexpected error occurred: {e}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
        import traceback
        traceback.print_exc()
        ui.print_color("Installation aborted due to unexpected error.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
        return 1 # Indicate failure
    finally:
        end_time = time.time()
        duration = end_time - start_time
        ui.print_color(f"\nScript finished in {duration:.2f} seconds.", ui.Colors.PURPLE, bold=True)
    
    return 0 # Indicate success


if __name__ == "__main__":
    sys.exit(main_orchestrator())