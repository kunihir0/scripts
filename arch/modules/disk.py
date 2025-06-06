#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handles disk operations for the Arch Linux installer, including drive selection,
partitioning, formatting, LVM, and Btrfs subvolume creation.
"""

import sys
import os # <--- ADDED IMPORT
import time
from pathlib import Path
from typing import Dict, Any, List as TypingList, Callable, Tuple, Union, Optional
import subprocess # For subprocess.CompletedProcess type hint

# Attempt to import from sibling modules
try:
    from . import config as cfg
    from . import ui
    from . import core
except ImportError:
    print("Warning: Could not import sibling modules in disk.py. Attempting absolute.", file=sys.stderr)
    try:
        import config as cfg # type: ignore
        import ui # type: ignore
        import core # type: ignore
    except ImportError as e:
        print(f"Error: Failed to import 'config', 'ui', or 'core' modules in disk.py: {e}", file=sys.stderr)
        sys.exit(1)


def get_partition_suffix_func(drive_path_str: str) -> Callable[[int], str]:
    """
    Public: Returns a function that generates the correct partition suffix (e.g., 'p1' or '1')
    based on the drive name (nvme/loop vs. sdX/hdX).
    """
    normalized_drive = drive_path_str.lower()
    if "nvme" in normalized_drive or "loop" in normalized_drive:
        return lambda p_num: f"p{p_num}"
    return lambda p_num: str(p_num)

def select_drive() -> str:
    """
    Prompts the user to select a drive for installation from a list of available drives.
    Returns the selected drive's name (e.g., /dev/sda).
    """
    ui.print_step_info("Detecting available drives...")
    try:
        # destructive=False as lsblk is read-only
        lsblk_process: Optional[subprocess.CompletedProcess] = core.run_command(
            ["lsblk", "-dnpo", "NAME,SIZE,MODEL"],
            capture_output=True,
            destructive=False,
            show_spinner=False
        )
        lsblk_output: str = lsblk_process.stdout if lsblk_process and lsblk_process.stdout else ""
        
        drives: TypingList[Dict[str, str]] = []
        if lsblk_output:
            header_skipped: bool = False
            for line in lsblk_output.strip().split('\n'):
                if not header_skipped and "NAME" in line and "SIZE" in line:
                    header_skipped = True
                    continue
                parts: TypingList[str] = line.split(maxsplit=2)
                if len(parts) >= 2:
                    drives.append({
                        "name": parts[0],
                        "size": parts[1],
                        "model": parts[2] if len(parts) > 2 else "N/A"
                    })

        if not drives:
            ui.print_color("No drives found. Cannot proceed.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
            sys.exit(1)

        ui.print_color("Available drives:", ui.Colors.MAGENTA, bold=True)
        for i, drive_info in enumerate(drives):
            sys.stdout.write(
                f"  {ui.Colors.PINK}{i + 1}{ui.Colors.RESET}) "
                f"{ui.Colors.CYAN}{drive_info['name']}{ui.Colors.RESET} "
                f"({ui.Colors.LIGHT_BLUE}{drive_info['size']}{ui.Colors.RESET}) - "
                f"{ui.Colors.BLUE}{drive_info['model']}{ui.Colors.RESET}\n"
            )
        
        while True:
            try:
                choice_str: str = ui.prompt_input("Select drive number for installation")
                choice: int = int(choice_str) - 1
                if 0 <= choice < len(drives):
                    selected_drive_info: Dict[str, str] = drives[choice]
                    selected_drive_name: str = selected_drive_info['name']
                    confirm_q: str = (
                        f"You selected {ui.Colors.BOLD}{selected_drive_name}{ui.Colors.LAVENDER} "
                        f"({selected_drive_info['size']} - {selected_drive_info['model']}).\n"
                        f"{ui.Colors.RED}{ui.Colors.BOLD}ALL DATA ON THIS DRIVE WILL BE ERASED "
                        f"(if not in dry run).{ui.Colors.LAVENDER} Are you sure?"
                    )
                    if ui.prompt_yes_no(confirm_q, default_yes=False):
                        return selected_drive_name
                    else:
                        ui.print_color("Drive selection aborted by user.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                else:
                    ui.print_color("Invalid selection. Please enter a number from the list.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
            except ValueError:
                ui.print_color("Invalid input. Please enter a number.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
    except Exception as e:
        ui.print_color(f"Error selecting drive: {e}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        sys.exit(1)
    return "" # Should not be reached

def check_and_free_device(device_path_str: str) -> None:
    """
    Ensures a device and its partitions are free by unmounting filesystems,
    deactivating swap, and deactivating/removing LVM VGs/PVs if they exist on the device.
    """
    ui.print_step_info(f"Ensuring {device_path_str} and its partitions are free...")
    device_path: Path = Path(device_path_str)
    user_config: Dict[str, Any] = cfg.get_all_user_config() # Get a copy

    mnt_base: Path = Path("/mnt")
    # Order matters for unmounting: deepest first
    explicit_unmount_targets: TypingList[Path] = [
        mnt_base / "boot/efi", mnt_base / "boot",
        mnt_base / "home", mnt_base / "var", # Standard dirs
        # Add .snapshots or other custom mount points if they were part of the old setup
        # For now, assuming these are the main ones that might be on /mnt
    ]
    # If BTRFS was previously used, .snapshots might exist as a mount point
    # This logic is now simplified as we target ext4, but old mounts might persist.
    if (mnt_base / ".snapshots").exists(): # Check if it was a dir/mount
        explicit_unmount_targets.insert(2, mnt_base / ".snapshots")


    for target_path in explicit_unmount_targets:
        findmnt_check: Optional[subprocess.CompletedProcess] = core.run_command(
            ["findmnt", "-n", "-r", "-o", "TARGET", "--target", str(target_path)],
            capture_output=True, destructive=False, show_spinner=False, check=False
        )
        if findmnt_check and findmnt_check.returncode == 0 and str(target_path) in findmnt_check.stdout.strip():
            ui.print_color(f"Attempting to unmount {target_path} (lazy)...", ui.Colors.BLUE)
            core.run_command(
                ["umount", "-fl", str(target_path)],
                check=False, destructive=True, show_spinner=False, retry_count=3, retry_delay=1.5
            )
    
    # Specifically try to swapoff the configured LVM swap volume if it exists and is active
    target_vg_name: Optional[str] = user_config.get('lvm_vg_name')
    lv_swap_name: Optional[str] = user_config.get('lvm_lv_swap_name')
    swap_size_gb_str = str(user_config.get('swap_size_gb', "0"))
    swap_configured: bool = False
    try:
        if float(swap_size_gb_str) > 0:
            swap_configured = True
    except ValueError:
        pass

    if target_vg_name and lv_swap_name and swap_configured:
        # Try both common paths for the LV swap device
        swap_lv_paths_to_try: TypingList[str] = [
            f"/dev/{target_vg_name}/{lv_swap_name}",
            f"/dev/mapper/{target_vg_name}-{lv_swap_name}"
        ]
        swaps_output_proc = core.run_command(["cat", "/proc/swaps"], capture_output=True, destructive=False, show_spinner=False, check=False)
        active_swaps_content = swaps_output_proc.stdout if swaps_output_proc and swaps_output_proc.stdout else ""

        for swap_lv_path in swap_lv_paths_to_try:
            if Path(swap_lv_path).exists(): # Check if the device node exists
                 # Check if this path (or its real path) is in /proc/swaps
                try:
                    real_swap_lv_path = os.path.realpath(swap_lv_path)
                    if real_swap_lv_path in active_swaps_content or swap_lv_path in active_swaps_content:
                        ui.print_color(f"Attempting to deactivate swap on {swap_lv_path}...", ui.Colors.BLUE)
                        core.run_command(["swapoff", swap_lv_path], check=False, destructive=True)
                        break # Found and attempted swapoff
                except FileNotFoundError: # os.path.realpath can fail if symlink is broken
                    pass


    # Deactivate LVM on the target device
    sfx_func: Callable[[int], str] = get_partition_suffix_func(str(user_config.get('target_drive', '')))
    # Assuming LVM is on the second partition by convention in this script
    lvm_partition_device_str: str = f"{user_config.get('target_drive', '')}{sfx_func(2)}"

    if target_vg_name:
        vgdisplay_proc: Optional[subprocess.CompletedProcess] = core.run_command(
            ["vgdisplay", target_vg_name],
            check=False, destructive=False, capture_output=True, show_spinner=False
        )
        if vgdisplay_proc and vgdisplay_proc.returncode == 0: # VG Exists
            ui.print_color(f"Volume group {target_vg_name} exists. Attempting deactivation...", ui.Colors.BLUE)
            for lv_name_key in ["lvm_lv_root_name", "lvm_lv_swap_name"]: # Add other LVs if any
                lv_name: Optional[str] = user_config.get(lv_name_key)
                if lv_name:
                    lv_path_vg: str = f"/dev/{target_vg_name}/{lv_name}"
                    lv_path_map: str = f"/dev/mapper/{target_vg_name}-{lv_name}"
                    if Path(lv_path_vg).exists() or Path(lv_path_map).exists():
                        ui.print_color(f"Deactivating LV: {lv_name}...", ui.Colors.BLUE)
                        core.run_command(["lvchange", "-an", f"{target_vg_name}/{lv_name}"],
                                          check=False, destructive=True, show_spinner=False, retry_count=2)
            core.run_command(["sync"], check=False, destructive=False, show_spinner=False); time.sleep(1) # Sync before VG change
            vgchange_proc: Optional[subprocess.CompletedProcess] = core.run_command(
                ["vgchange", "-an", target_vg_name],
                check=False, destructive=True, capture_output=True, show_spinner=False, retry_count=2
            )
            if not (vgchange_proc and vgchange_proc.returncode == 0):
                ui.print_color(f"Failed to deactivate VG {target_vg_name}. Attempting forceful removal...", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                # Force remove VG and then PV. Use --force twice for some commands.
                core.run_command(["vgremove", "--force", "--force", "-y", target_vg_name], check=False, destructive=True, show_spinner=False)
                if Path(lvm_partition_device_str).exists():
                    core.run_command(["pvremove", "--force", "--force", "-y", lvm_partition_device_str], check=False, destructive=True, show_spinner=False)
            else:
                ui.print_color(f"Successfully deactivated VG {target_vg_name}.", ui.Colors.MINT)
        # If VG doesn't exist, but the LVM partition might have PV signatures
        elif Path(lvm_partition_device_str).exists():
            ui.print_color(f"VG {target_vg_name} not found. Checking for PV signatures on {lvm_partition_device_str}...", ui.Colors.CYAN)
            core.run_command(["pvremove", "--force", "--force", "-y", lvm_partition_device_str], check=False, destructive=True, show_spinner=False)
        
        # Attempt to remove device mapper entries for all LVs in the target VG.
        # This is an extra step to ensure devices are freed.
        # Do this after vgchange/vgremove attempts.
        if vgdisplay_proc and vgdisplay_proc.returncode == 0 and target_vg_name: # If VG existed
            ui.print_step_info(f"Attempting to remove device mapper entries for LVs in VG '{target_vg_name}'...")
            lvs_proc: Optional[subprocess.CompletedProcess] = core.run_command(
                ["lvs", "--noheadings", "-o", "lv_name", target_vg_name],
                capture_output=True, destructive=False, show_spinner=False, check=False
            )
            if lvs_proc and lvs_proc.returncode == 0 and lvs_proc.stdout:
                lv_names_in_vg: TypingList[str] = [name.strip() for name in lvs_proc.stdout.splitlines() if name.strip()]
                if lv_names_in_vg:
                    ui.print_color(f"Found LVs in '{target_vg_name}': {', '.join(lv_names_in_vg)}. Attempting dmsetup remove for each.", ui.Colors.BLUE)
                    for lv_name_from_lvs in lv_names_in_vg:
                        # Construct potential mapper names
                        # Standard: vg_name-lv_name
                        # systemd style: vg_name--lv_name (hyphens in names get doubled)
                        # We need to be careful here. The actual mapper name is vg_name-lv_name,
                        # where vg_name and lv_name can themselves contain hyphens.
                        # systemd's escaping rule is complex.
                        # A common pattern is simply replacing internal hyphens with '--' IF the whole thing is then used by systemd.
                        # For dmsetup, the name is usually vg_name-lv_name.
                        
                        # Let's try the most common mapper name format first.
                        # The LVM tools (lvchange, etc.) use /dev/vg/lv or /dev/mapper/vg-lv.
                        # dmsetup uses the name part of /dev/mapper/name.
                        
                        mapper_device_name_style1: str = f"{target_vg_name}-{lv_name_from_lvs}"
                        # systemd might escape hyphens within vg_name or lv_name to '--'.
                        # This is complex to guess perfectly. Let's try the direct one first.
                        # Example: if vg_name is "my-vg" and lv_name is "my-lv", mapper is "my--vg-my--lv" for systemd paths,
                        # but for dmsetup, it might just be "my-vg-my-lv".
                        # The /dev/mapper/ symlink usually points to the correct dm-X device.
                        # We will try to remove based on the symlink name.
                        
                        potential_mapper_path = Path(f"/dev/mapper/{mapper_device_name_style1}")

                        if potential_mapper_path.exists(): # Check if the symlink exists
                             ui.print_color(f"Attempting dmsetup remove for LV '{lv_name_from_lvs}' (mapper: {potential_mapper_path})...", ui.Colors.BLUE)
                             core.run_command(["dmsetup", "remove", str(potential_mapper_path)], check=False, destructive=True, show_spinner=False)
                        else:
                            ui.print_color(f"Mapper path {potential_mapper_path} for LV '{lv_name_from_lvs}' not found, skipping dmsetup remove for this specific path.", ui.Colors.CYAN)
                else:
                    ui.print_color(f"No LVs found in VG '{target_vg_name}' via 'lvs' command for dmsetup.", ui.Colors.CYAN)
            else:
                ui.print_color(f"Could not list LVs for VG '{target_vg_name}' to attempt dmsetup remove.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)


    # If VG didn't exist, but PV might have, pvremove was already attempted.
    # If VG existed but forceful vgremove was used, PV might still need explicit wipe if dmsetup didn't clear all.
    # Re-attempt pvremove if the LVM partition still exists, as a final cleanup for its signature.
    if Path(lvm_partition_device_str).exists():
        ui.print_color(f"Final attempt to clear PV signature on {lvm_partition_device_str} if any remains...", ui.Colors.BLUE)
        core.run_command(["pvremove", "--force", "--force", "-y", lvm_partition_device_str], check=False, destructive=True, show_spinner=False)


    core.run_command(["sync"], check=False, destructive=False, show_spinner=False) # Sync before udevadm
    ui.print_step_info("Running udevadm settle to ensure device changes are processed...")
    core.run_command(["udevadm", "settle"], check=False, destructive=False, show_spinner=False)
    core.run_command(["sync"], check=False, destructive=False, show_spinner=False) # Final sync
    ui.print_color("Pausing for 3 seconds after deactivation and udev settle attempts...", ui.Colors.BLUE); time.sleep(3)
    ui.print_step_info(f"Device {device_path_str} freeing attempts complete.")
    sys.stdout.write("\n")

def partition_and_format() -> None:
    """
    Partitions the target drive (GPT, EFI, LVM), formats partitions,
    sets up LVM (PV, VG, LVs for root and swap), and creates Btrfs subvolumes.
    """
    ui.print_section_header(f"Partitioning & Formatting {cfg.get_user_config_value('target_drive')}")
    if cfg.get_current_step() > cfg.INSTALL_STEPS.index("partition_format"):
        ui.print_step_info("Skipping (already completed)"); sys.stdout.write("\n"); return

    user_config: Dict[str, Any] = cfg.get_all_user_config()
    drive: str = str(user_config['target_drive'])
    if not drive:
        ui.print_color("Target drive not set. Aborting partition_and_format.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        sys.exit(1)

    check_and_free_device(drive) # Ensure device is free before partitioning

    sfx: Callable[[int], str] = get_partition_suffix_func(drive)
    efi_part_dev_str: str = f"{drive}{sfx(1)}"
    lvm_part_dev_str: str = f"{drive}{sfx(2)}"

    ui.print_step_info(f"Wiping device signatures on {drive}...")
    core.run_command(["wipefs", "-a", drive], destructive=True, check=True)
    ui.print_step_info(f"Creating new GPT partition table on {drive}...")
    core.run_command(["sgdisk", "-Zo", drive], destructive=True, check=True) # -Z zap, -o clear

    ui.print_step_info(f"Creating EFI partition ({user_config['efi_partition_size']})...")
    core.run_command([
        "sgdisk", f"-n=1:0:+{user_config['efi_partition_size']}", # part_num:start_sector:end_sector(+size)
        "-t=1:ef00", # type code for EFI System Partition
        f"-c=1:EFI System Partition", # partition name
        drive
    ], destructive=True, check=True)

    ui.print_step_info("Creating LVM partition (remaining space)...")
    core.run_command([
        "sgdisk", "-n=2:0:0", # part_num:start_sector:end_sector (0 for remaining)
        "-t=2:8e00", # type code for Linux LVM
        f"-c=2:Linux LVM", # partition name
        drive
    ], destructive=True, check=True)

    ui.print_step_info("Informing kernel of partition table changes...")
    core.run_command(["partprobe", drive], check=False, destructive=True) # partprobe can be non-critical
    
    if not cfg.get_dry_run_mode():
        time.sleep(3) # Give kernel time to recognize changes
        if not Path(efi_part_dev_str).exists() or not Path(lvm_part_dev_str).exists():
            ui.print_color(f"Partitions {efi_part_dev_str} or {lvm_part_dev_str} not detected after partprobe. Retrying udev.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
            core.run_command(["udevadm", "settle"], destructive=False, check=False)
            core.run_command(["udevadm", "trigger"], destructive=False, check=False)
            time.sleep(3)
            if not Path(efi_part_dev_str).exists() or not Path(lvm_part_dev_str).exists():
                ui.print_color(f"CRITICAL: Partitions still not detected on {drive}.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
                sys.exit(1)
        ui.print_color("Partitions detected.", ui.Colors.MINT)

    ui.print_step_info(f"Formatting EFI partition {efi_part_dev_str} as FAT32...")
    core.run_command(["mkfs.vfat", "-F32", efi_part_dev_str], destructive=True, check=True)

    ui.print_step_info(f"Wiping any old signatures on LVM partition {lvm_part_dev_str}...")
    core.run_command(["wipefs", "-a", lvm_part_dev_str], destructive=True, check=True, retry_count=2)

    ui.print_step_info("Setting up LVM...")
    core.run_command(["pvcreate", "--yes", lvm_part_dev_str], destructive=True, check=True)
    core.run_command(["vgcreate", user_config['lvm_vg_name'], lvm_part_dev_str], destructive=True, check=True)

    lv_root_path_str: str = f"/dev/{user_config['lvm_vg_name']}/{user_config['lvm_lv_root_name']}"
    swap_size_gb: float = 0.0
    try:
        swap_size_gb = float(str(user_config['swap_size_gb']))
    except ValueError:
        ui.print_color(f"Invalid swap_size_gb: {user_config['swap_size_gb']}. Defaulting to 0.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)


    if swap_size_gb > 0:
        ui.print_step_info(f"Creating SWAP LV ({user_config['swap_size_gb']}G)...")
        core.run_command([
            "lvcreate", "-L", f"{user_config['swap_size_gb']}G",
            "-n", user_config['lvm_lv_swap_name'], user_config['lvm_vg_name']
        ], destructive=True, check=True)
        lv_swap_path_str: str = f"/dev/{user_config['lvm_vg_name']}/{user_config['lvm_lv_swap_name']}"
        ui.print_step_info(f"Formatting SWAP LV {lv_swap_path_str}...")
        core.run_command(["mkswap", lv_swap_path_str], destructive=True, check=True)

    ui.print_step_info("Creating ROOT LV (100%FREE)...")
    core.run_command([
        "lvcreate", "-l", "100%FREE", # Use all remaining space in VG
        "-n", user_config['lvm_lv_root_name'], user_config['lvm_vg_name']
    ], destructive=True, check=True)

    ui.print_step_info(f"Formatting ROOT LV {lv_root_path_str} as ext4...")
    core.run_command(["mkfs.ext4", "-F", lv_root_path_str], destructive=True, check=True) # -F to force (non-interactive)

    # Btrfs subvolume creation removed as we are using ext4 for root.
    # If separate /home or /var were desired on different filesystems,
    # they would need their own LVs and formatting steps.
    # For now, /home, /var, etc., will be standard directories on the ext4 root.

    ui.print_color("Partitioning & formatting complete.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    cfg.set_current_step(cfg.INSTALL_STEPS.index("mount_filesystems"))
    cfg.save_progress()
    sys.stdout.write("\n")


def verify_partitions_lvm(no_verify_arg: bool) -> None:
    """Verifies the existence and basic properties of created partitions and LVM volumes."""
    if no_verify_arg:
        ui.print_step_info("Skipping partition & LVM verification as per --no-verify.")
        sys.stdout.write("\n"); return

    ui.print_section_header("Verifying Partitions and LVM")
    if cfg.get_current_step() <= cfg.INSTALL_STEPS.index("partition_format"):
        ui.print_color("Verification running before its intended step, results might be inaccurate.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

    user_config: Dict[str, Any] = cfg.get_all_user_config()
    drive: str = str(user_config['target_drive'])
    sfx: Callable[[int], str] = get_partition_suffix_func(drive)
    
    efi_part_dev_str: str = f"{drive}{sfx(1)}"
    lvm_part_dev_str: str = f"{drive}{sfx(2)}"
    lv_root_path: Path = Path(f"/dev/{user_config['lvm_vg_name']}/{user_config['lvm_lv_root_name']}")
    
    all_ok: bool = True

    # Check existence of partitions and LVs
    if not core.verify_step(Path(efi_part_dev_str).exists() if not cfg.get_dry_run_mode() else True, f"EFI partition {efi_part_dev_str} exists", critical=True): all_ok = False
    if not core.verify_step(Path(lvm_part_dev_str).exists() if not cfg.get_dry_run_mode() else True, f"LVM partition {lvm_part_dev_str} exists", critical=True): all_ok = False
    if not core.verify_step(lv_root_path.exists() if not cfg.get_dry_run_mode() else True, f"Root LV {lv_root_path} exists", critical=True): all_ok = False

    swap_size_gb: float = 0.0
    try:
        swap_size_gb = float(str(user_config['swap_size_gb']))
    except ValueError:
        pass # Keep as 0.0

    if swap_size_gb > 0:
        lv_swap_path: Path = Path(f"/dev/{user_config['lvm_vg_name']}/{user_config['lvm_lv_swap_name']}")
        if not core.verify_step(lv_swap_path.exists() if not cfg.get_dry_run_mode() else True, f"Swap LV {lv_swap_path} exists", critical=True): all_ok = False

    # Helper to check FSTYPE
    def _check_fstype(device_str: str, expected_fstype: str) -> bool:
        if cfg.get_dry_run_mode(): return True # Assume success in dry run
        if not Path(device_str).exists():
            ui.print_color(f"Device {device_str} not found for fstype check.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
            return False
        # destructive=False as lsblk is read-only
        proc: Optional[subprocess.CompletedProcess] = core.run_command(
            ["lsblk", "-fno", "FSTYPE", device_str],
            capture_output=True, destructive=False, show_spinner=False, check=False
        )
        return bool(proc and proc.returncode == 0 and proc.stdout and expected_fstype in proc.stdout.strip())

    if not core.verify_step(_check_fstype(efi_part_dev_str, "vfat"), f"EFI partition {efi_part_dev_str} has FSTYPE vfat", critical=True): all_ok = False
    if not core.verify_step(_check_fstype(str(lv_root_path), "ext4"), f"Root LV {lv_root_path.name} has FSTYPE ext4", critical=True): all_ok = False
    if swap_size_gb > 0:
        lv_swap_path_str: str = f"/dev/{user_config['lvm_vg_name']}/{user_config['lvm_lv_swap_name']}"
        if not core.verify_step(_check_fstype(lv_swap_path_str, "swap"), f"Swap LV {user_config['lvm_lv_swap_name']} has FSTYPE swap", critical=True): all_ok = False

    if all_ok:
        ui.print_color("Partition and LVM verification successful.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    else:
        ui.print_color("One or more partition/LVM verifications failed.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
    sys.stdout.write("\n")