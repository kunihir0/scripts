#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handles filesystem mounting, fstab generation, and verification for the Arch Linux installer.
"""

import sys
import os # <--- ADDED IMPORT
from pathlib import Path
from typing import Dict, Any, List as TypingList, Optional, Callable
import subprocess # For subprocess.CompletedProcess type hint

# Attempt to import from sibling modules
try:
    from . import config as cfg
    from . import ui
    from . import core
except ImportError:
    print("Warning: Could not import sibling modules in filesystem.py. Attempting absolute.", file=sys.stderr)
    try:
        import config as cfg # type: ignore
        import ui # type: ignore
        import core # type: ignore
    except ImportError as e:
        print(f"Error: Failed to import 'config', 'ui', or 'core' modules in filesystem.py: {e}", file=sys.stderr)
        sys.exit(1)

def _get_partition_suffix_char(drive_path_str: str) -> str:
    """
    Determines the character prefix for partition numbers (e.g., 'p' for nvme, '' for sdX).
    Used for constructing partition device paths like /dev/nvme0n1p1 vs /dev/sda1.
    """
    normalized_drive = drive_path_str.lower()
    if "nvme" in normalized_drive or "loop" in normalized_drive:
        return "p"
    return ""

def mount_filesystems() -> None:
    """
    Mounts the Btrfs subvolumes (root, home, var) and the EFI partition.
    Activates swap if configured.
    """
    ui.print_section_header("Mounting Filesystems")
    if cfg.get_current_step() > cfg.INSTALL_STEPS.index("mount_filesystems"):
        ui.print_step_info("Skipping (already completed)")
        sys.stdout.write("\n"); return

    user_config: Dict[str, Any] = cfg.get_all_user_config()
    mnt_base: Path = Path("/mnt")
    lv_root_path_str: str = f"/dev/{user_config['lvm_vg_name']}/{user_config['lvm_lv_root_name']}"
    
    part_suffix_char: str = _get_partition_suffix_char(str(user_config['target_drive']))
    efi_part_path_str: str = f"{user_config['target_drive']}{part_suffix_char}1"
    
    root_fs_type: str = str(user_config.get("root_filesystem_type", "ext4")) # Default to ext4 if not set

    if root_fs_type == "ext4":
        ext4_mount_opts: str = str(user_config.get("ext4_mount_options", "defaults,rw,noatime"))
        ui.print_step_info(f"Mounting ext4 ROOT LV '{lv_root_path_str}' to {mnt_base} with options '{ext4_mount_opts}'...")
        core.run_command([
            "mount", "-o", ext4_mount_opts,
            lv_root_path_str, str(mnt_base)
        ], check=True)
    elif root_fs_type == "btrfs":
        btrfs_mount_opts: str = str(user_config.get("btrfs_mount_options", "compress=zstd,ssd,noatime,discard=async")) # Fallback if key somehow missing
        root_subvol_for_mount = str(user_config.get('btrfs_subvol_root', '@root')).lstrip('@') # Fallback
        home_subvol_for_mount = str(user_config.get('btrfs_subvol_home', '@home')).lstrip('@')
        var_subvol_for_mount = str(user_config.get('btrfs_subvol_var', '@var')).lstrip('@')

        ui.print_step_info(f"Mounting Btrfs ROOT subvolume '{root_subvol_for_mount}' to {mnt_base}...")
        core.run_command([
            "mount", "-o", f"subvol=/{root_subvol_for_mount},{btrfs_mount_opts}",
            lv_root_path_str, str(mnt_base)
        ], check=True)
    else:
        ui.print_color(f"Unsupported root_filesystem_type: {root_fs_type}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        sys.exit(1)

    ui.print_step_info("Creating standard mount point directories under /mnt...")
    # .snapshots is Btrfs-specific, remove if not using Btrfs or handle conditionally
    standard_dirs = ["boot", "boot/efi", "home", "var"]
    if root_fs_type == "btrfs" and user_config.get('btrfs_subvol_snapshots'):
        # Add .snapshots only if btrfs and configured
        snapshots_dir_name = str(user_config['btrfs_subvol_snapshots']).lstrip('@')
        standard_dirs.append(snapshots_dir_name)

    for subdir_name in standard_dirs:
        core.make_dir_dry_run(mnt_base / subdir_name, exist_ok=True)

    if root_fs_type == "btrfs":
        ui.print_step_info(f"Mounting Btrfs HOME subvolume '{home_subvol_for_mount}' to {mnt_base / 'home'}...")
        core.run_command([
            "mount", "-o", f"subvol=/{home_subvol_for_mount},{btrfs_mount_opts}",
            lv_root_path_str, str(mnt_base / "home")
        ], check=True)

        ui.print_step_info(f"Mounting Btrfs VAR subvolume '{var_subvol_for_mount}' to {mnt_base / 'var'}...")
        core.run_command([
            "mount", "-o", f"subvol=/{var_subvol_for_mount},{btrfs_mount_opts}",
            lv_root_path_str, str(mnt_base / "var")
        ], check=True)
        
        if user_config.get('btrfs_subvol_snapshots'):
            snapshots_subvol_config_name = str(user_config['btrfs_subvol_snapshots'])
            snapshots_subvol_for_mount = snapshots_subvol_config_name.lstrip('@')
            snapshots_mount_point_name = snapshots_subvol_for_mount
            snapshots_mount_point = mnt_base / snapshots_mount_point_name
            # Directory creation for .snapshots is handled above if it's in standard_dirs

            ui.print_step_info(f"Mounting Btrfs SNAPSHOTS subvolume '{snapshots_subvol_for_mount}' to {snapshots_mount_point}...")
            core.run_command([
                "mount", "-o", f"subvol=/{snapshots_subvol_for_mount},{btrfs_mount_opts}",
                lv_root_path_str, str(snapshots_mount_point)
            ], check=True)
    # If ext4, /home and /var are just directories on the root, no separate mount needed here.

    ui.print_step_info(f"Mounting EFI partition {efi_part_path_str} to {mnt_base / 'boot/efi'}...")
    core.run_command(["mount", efi_part_path_str, str(mnt_base / "boot/efi")], check=True)

    swap_size_gb: float = 0.0
    try:
        swap_size_gb = float(str(user_config['swap_size_gb']))
    except ValueError:
        pass # Keep as 0.0

    if swap_size_gb > 0:
        lv_swap_path_str: str = f"/dev/{user_config['lvm_vg_name']}/{user_config['lvm_lv_swap_name']}"
        ui.print_step_info(f"Activating SWAP on {lv_swap_path_str}...")
        core.run_command(["swapon", lv_swap_path_str], check=True)

    ui.print_color("Filesystems mounted.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    cfg.set_current_step(cfg.INSTALL_STEPS.index("pacstrap_system"))
    cfg.save_progress()
    sys.stdout.write("\n")

def verify_mounts(no_verify_arg: bool) -> None:
    """Verifies that all expected filesystems are mounted correctly."""
    if no_verify_arg:
        ui.print_step_info("Skipping mount verification as per --no-verify.")
        sys.stdout.write("\n"); return

    ui.print_section_header("Verifying Mounts")
    all_ok: bool = True
    user_config: Dict[str, Any] = cfg.get_all_user_config()
    mnt_base_str: str = str(Path("/mnt"))
    root_lv_device_path: str = f"/dev/mapper/{user_config['lvm_vg_name']}-{user_config['lvm_lv_root_name']}"
    
    part_suffix_char: str = _get_partition_suffix_char(str(user_config['target_drive']))
    efi_device_path: str = f"{user_config['target_drive']}{part_suffix_char}1"
    root_fs_type: str = str(user_config.get("root_filesystem_type", "ext4"))

    expected_mounts: TypingList[Dict[str, Any]] = []

    if root_fs_type == "ext4":
        expected_mounts = [
            {"target": mnt_base_str, "source_pattern": root_lv_device_path, "fstype": "ext4", "options_substring": "noatime"}, # Check for a key part of default ext4 opts
            {"target": f"{mnt_base_str}/boot/efi", "source_pattern": efi_device_path, "fstype": "vfat", "options_substring": None},
        ]
    elif root_fs_type == "btrfs":
        # Adjust expected mount options to match the actual subvolume names (without '@')
        expected_root_subvol_for_mount = str(user_config.get('btrfs_subvol_root', '@root')).lstrip('@')
        expected_home_subvol_for_mount = str(user_config.get('btrfs_subvol_home', '@home')).lstrip('@')
        expected_var_subvol_for_mount = str(user_config.get('btrfs_subvol_var', '@var')).lstrip('@')

        expected_mounts = [
            {"target": mnt_base_str, "source_pattern": root_lv_device_path, "fstype": "btrfs", "options_substring": f"subvol=/{expected_root_subvol_for_mount}"},
            {"target": f"{mnt_base_str}/home", "source_pattern": root_lv_device_path, "fstype": "btrfs", "options_substring": f"subvol=/{expected_home_subvol_for_mount}"},
            {"target": f"{mnt_base_str}/var", "source_pattern": root_lv_device_path, "fstype": "btrfs", "options_substring": f"subvol=/{expected_var_subvol_for_mount}"},
            {"target": f"{mnt_base_str}/boot/efi", "source_pattern": efi_device_path, "fstype": "vfat", "options_substring": None},
        ]
        if user_config.get('btrfs_subvol_snapshots'):
            snapshots_subvol_config_name = str(user_config['btrfs_subvol_snapshots'])
            snapshots_subvol_for_mount = snapshots_subvol_config_name.lstrip('@')
            snapshots_mount_point_name = snapshots_subvol_for_mount # e.g. .snapshots or snapshots
            expected_mounts.append(
                {"target": f"{mnt_base_str}/{snapshots_mount_point_name}", "source_pattern": root_lv_device_path, "fstype": "btrfs", "options_substring": f"subvol=/{snapshots_subvol_for_mount}"}
            )
    
    # destructive=False as findmnt is read-only
    findmnt_proc: Optional[subprocess.CompletedProcess] = core.run_command(
        ["findmnt", "--real", "--noheadings", "--output=TARGET,SOURCE,FSTYPE,OPTIONS"],
        capture_output=True, destructive=False, show_spinner=False, check=False
    )

    if not (findmnt_proc and findmnt_proc.returncode == 0 and findmnt_proc.stdout):
        ui.print_color("Could not get mount information using findmnt.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        if findmnt_proc and findmnt_proc.stderr:
            ui.print_color(f"findmnt stderr: {findmnt_proc.stderr.strip()}", ui.Colors.ORANGE)
        all_ok = False
    else:
        # For debugging, print raw and parsed output
        # ui.print_color("Raw findmnt output:", ui.Colors.MAGENTA, bold=True)
        # sys.stdout.write(findmnt_proc.stdout.strip() + "\n")
        # ui.print_color("--- End of raw findmnt output ---", ui.Colors.MAGENTA, bold=True)

        mounted_filesystems: Dict[str, Dict[str, str]] = {}
        for line in findmnt_proc.stdout.strip().split('\n'):
            if not line.strip(): continue
            # Output is TARGET SOURCE FSTYPE OPTIONS. Split carefully.
            parts: TypingList[str] = line.split(maxsplit=3)
            if len(parts) >= 1: # Must have at least a target
                target_path: str = parts[0].lstrip('├─└─│ ').strip() # Strip tree characters
                source_val: str = parts[1] if len(parts) > 1 else ""
                fstype_val: str = parts[2] if len(parts) > 2 else ""
                options_val: str = parts[3] if len(parts) > 3 else ""
                mounted_filesystems[target_path] = {"source": source_val, "fstype": fstype_val, "options": options_val}
            else:
                ui.print_color(f"Warning: Skipping malformed findmnt line: '{line}'", ui.Colors.ORANGE)
        
        # ui.print_color("Parsed mounted_filesystems dictionary:", ui.Colors.MAGENTA, bold=True)
        # for t_key, t_val in mounted_filesystems.items():
        #     sys.stdout.write(f"  '{t_key}': {t_val}\n")
        # ui.print_color("--- End of parsed mounted_filesystems dictionary ---", ui.Colors.MAGENTA, bold=True)

        for expected in expected_mounts:
            target: str = expected["target"]
            is_mounted: bool = target in mounted_filesystems
            
            if not core.verify_step(is_mounted, f"Mount point {target} is mounted", critical=True):
                all_ok = False
                if not cfg.get_dry_run_mode():
                    ui.print_color("Current mounts from 'findmnt -A --real':", ui.Colors.ORANGE)
                    core.run_command(["findmnt", "-A", "--real"], destructive=False, show_spinner=False, check=False, capture_output=False)
                continue # Skip further checks for this mount if not mounted

            actual: Dict[str, str] = mounted_filesystems[target]
            source_ok: bool = expected["source_pattern"] in actual["source"]
            if not core.verify_step(source_ok, f"{target} source contains '{expected['source_pattern']}' (actual: {actual['source']})", critical=True): all_ok = False
            
            fstype_ok: bool = expected["fstype"] == actual["fstype"]
            if not core.verify_step(fstype_ok, f"{target} FSTYPE is '{expected['fstype']}' (actual: {actual['fstype']})", critical=True): all_ok = False
            
            if expected["options_substring"]:
                expected_opt_to_check: str = str(expected["options_substring"])
                options_ok: bool = expected_opt_to_check in actual["options"]
                if not core.verify_step(options_ok, f"{target} options contain '{expected_opt_to_check}' (actual: {actual['options']})", critical=True): all_ok = False

    swap_size_gb: float = 0.0
    try:
        swap_size_gb = float(str(user_config['swap_size_gb']))
    except ValueError:
        pass

    if swap_size_gb > 0:
        # Construct both potential paths for the swap LV
        # Path via /dev/vg_name/lv_name
        lv_swap_dev_vg_path_str: str = f"/dev/{user_config['lvm_vg_name']}/{user_config['lvm_lv_swap_name']}"
        # Path via /dev/mapper/vg_name-lv_name
        lv_swap_dev_mapper_path_str: str = f"/dev/mapper/{user_config['lvm_vg_name']}-{user_config['lvm_lv_swap_name']}"
        
        swap_active: bool = False
        active_swap_device_found: str = "None"

        if cfg.get_dry_run_mode():
            swap_active = True # Assume active in dry run
            active_swap_device_found = lv_swap_dev_mapper_path_str # Placeholder for message
        else:
            try:
                with open("/proc/swaps", "r", encoding="utf-8") as f_swaps:
                    lines = f_swaps.readlines()
                if len(lines) > 1: # Header + data lines
                    for line in lines[1:]:
                        parts = line.split()
                        if parts:
                            swap_device_from_proc = parts[0]
                            # Resolve symlinks for comparison
                            try:
                                real_proc_swap_dev = os.path.realpath(swap_device_from_proc)
                                real_expected_swap_dev_vg = os.path.realpath(lv_swap_dev_vg_path_str)
                                real_expected_swap_dev_mapper = os.path.realpath(lv_swap_dev_mapper_path_str)

                                if real_proc_swap_dev == real_expected_swap_dev_vg or \
                                   real_proc_swap_dev == real_expected_swap_dev_mapper:
                                    swap_active = True
                                    active_swap_device_found = swap_device_from_proc # The one found in /proc/swaps
                                    break
                            except FileNotFoundError:
                                # This can happen if a device listed in /proc/swaps is no longer valid
                                # or if our expected LVM paths don't exist (which would be an earlier issue)
                                continue
            except FileNotFoundError:
                ui.print_color("Could not read /proc/swaps to verify swap status.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
            except Exception as e:
                ui.print_color(f"Error checking /proc/swaps: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

        # The message should reflect the path we expect to be user-recognizable
        verification_message = f"Swap on LVM LV '{user_config['lvm_lv_swap_name']}' (found as {active_swap_device_found}) is active"
        if not core.verify_step(swap_active, verification_message, critical=True):
            all_ok = False

    if all_ok:
        ui.print_color("Mount verification successful.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    else:
        ui.print_color("One or more mount verifications failed.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
    sys.stdout.write("\n")


def generate_fstab() -> None:
    """Generates the /etc/fstab file for the new system."""
    ui.print_section_header("Generating fstab")
    if cfg.get_current_step() > cfg.INSTALL_STEPS.index("generate_fstab"):
        ui.print_step_info("Skipping (already completed)")
        sys.stdout.write("\n"); return

    user_config: Dict[str, Any] = cfg.get_all_user_config()
    fstab_path: Path = Path("/mnt/etc/fstab")

    # Use shell=True for redirection. Ensure command is safe.
    # genfstab -U /mnt >> /mnt/etc/fstab
    # The command itself is standard and safe.
    genfstab_command: str = f"genfstab -U /mnt >> {str(fstab_path)}"
    core.run_command(genfstab_command, shell=True, destructive=True, check=True)
    ui.print_color(f"fstab generated at {fstab_path}", ui.Colors.MINT)

    # Verification for fstab content (basic check for root mount)
    root_line_found_and_correct: bool = False
    if cfg.get_dry_run_mode():
        root_line_found_and_correct = True # Assume correct in dry run
    elif fstab_path.exists() and fstab_path.stat().st_size > 0:
        content: str = fstab_path.read_text()
        # We expect UUID for root, mounting to /, with btrfs type,
        # and options including the root subvolume and configured btrfs options.
        
        root_fs_type: str = str(user_config.get("root_filesystem_type", "ext4"))
        
        for line_idx, line_content in enumerate(content.splitlines()):
            line: str = line_content.strip()
            if line.startswith("#") or not line:
                continue
            
            parts: TypingList[str] = line.split()
            if len(parts) < 4: continue # Need at least device, mountpoint, fstype, options

            mount_point: str = parts[1]
            actual_fstype: str = parts[2]
            actual_options_str: str = parts[3]
            actual_options_list: TypingList[str] = [opt.strip() for opt in actual_options_str.split(',')]

            if mount_point == "/":
                if root_fs_type == "ext4":
                    if "ext4" not in actual_fstype:
                        ui.print_color(f"fstab line {line_idx+1}: Root mount '/' has fstype '{actual_fstype}', expected 'ext4'.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                        continue
                    
                    expected_ext4_options: TypingList[str] = str(user_config.get("ext4_mount_options", "defaults,noatime")).split(',')
                    all_config_options_present: bool = True
                    for expected_opt_part in expected_ext4_options:
                        base_expected_opt: str = expected_opt_part.split('=')[0]
                        if not any(actual_opt.startswith(base_expected_opt) for actual_opt in actual_options_list):
                            all_config_options_present = False
                            ui.print_color(f"fstab line {line_idx+1}: Expected ext4 option component '{base_expected_opt}' (from '{expected_opt_part}') not found in actual options: '{actual_options_str}'", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                            break
                    if all_config_options_present:
                        root_line_found_and_correct = True
                        break
                
                elif root_fs_type == "btrfs":
                    if "btrfs" not in actual_fstype:
                        ui.print_color(f"fstab line {line_idx+1}: Root mount '/' has fstype '{actual_fstype}', expected 'btrfs'.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                        continue

                    all_config_options_present: bool = True
                    expected_btrfs_options_from_config: TypingList[str] = str(user_config.get("btrfs_mount_options", "")).split(',')
                    for expected_opt_part in expected_btrfs_options_from_config:
                        if not expected_opt_part: continue # Skip empty strings if btrfs_mount_options was empty
                        base_expected_opt: str = expected_opt_part.split('=')[0]
                        if not any(actual_opt.startswith(base_expected_opt) for actual_opt in actual_options_list):
                            all_config_options_present = False
                            ui.print_color(f"fstab line {line_idx+1}: Expected BTRFS option component '{base_expected_opt}' (from '{expected_opt_part}') not found in actual options: '{actual_options_str}'", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                            break
                    
                    expected_root_subvol_for_fstab = str(user_config.get('btrfs_subvol_root', '@root')).lstrip('@') # Fallback
                    expected_subvol_opt_str: str = f"subvol=/{expected_root_subvol_for_fstab}"
                    subvol_option_present: bool = expected_subvol_opt_str in actual_options_list
                    if not subvol_option_present:
                         ui.print_color(f"fstab line {line_idx+1}: Expected BTRFS subvolume option '{expected_subvol_opt_str}' not found in actual options: '{actual_options_str}'", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

                    if all_config_options_present and subvol_option_present:
                        root_line_found_and_correct = True
                        break # Found a suitable root line

        if not root_line_found_and_correct:
            ui.print_color(f"Root {root_fs_type.upper()} entry in fstab was not found or seems incorrect/missing required options.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
            if root_fs_type == "ext4":
                ui.print_color(f"Expected base options from config to be present: {user_config.get('ext4_mount_options', 'N/A')}", ui.Colors.PEACH)
            elif root_fs_type == "btrfs":
                ui.print_color(f"Expected base options from config to be present: {user_config.get('btrfs_mount_options', 'N/A')}", ui.Colors.PEACH)
                ui.print_color(f"Expected subvolume for root in fstab: subvol=/{str(user_config.get('btrfs_subvol_root', '@root')).lstrip('@')}", ui.Colors.PEACH)
            ui.print_color("Actual fstab content:", ui.Colors.PEACH)
            sys.stdout.write(content + "\n")
            
    core.verify_step(root_line_found_and_correct, f"fstab content for {root_fs_type.upper()} root mount appears correct", critical=True)
    
    ui.print_color("fstab generation and basic check complete.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    cfg.set_current_step(cfg.INSTALL_STEPS.index("pre_chroot_files"))
    cfg.save_progress()
    sys.stdout.write("\n")