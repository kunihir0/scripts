#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Core helper functions for the Arch Linux installer, including command execution,
file operations, and verification utilities.
"""

import subprocess
import sys
import time
import shlex
from pathlib import Path
from typing import List, Union, Optional, Dict, Any, Callable

# Attempt to import from sibling modules.
# This structure assumes 'config' and 'ui' are in the same 'modules' directory.
try:
    from . import config as cfg
    from . import ui
    from .ui import Spinner # Import Spinner directly
except ImportError:
    # Fallback for direct execution or if modules are not found in the expected path
    # This is less ideal for a structured project but can help during development/testing.
    print("Warning: Could not import sibling modules 'config' or 'ui' with relative import. Attempting absolute.", file=sys.stderr)
    try:
        import config as cfg # type: ignore
        import ui # type: ignore
    except ImportError:
        print("Error: Failed to import 'config' and 'ui' modules. Ensure they are in PYTHONPATH or structured correctly.", file=sys.stderr)
        # Define minimal fallbacks if imports fail, to allow some functions to be defined
        # This is a last resort and indicates a structural problem.
        class MockColors: # type: ignore
            YELLOW = ""; RED = ""; PEACH = ""; MINT = ""; ORANGE = ""; CYAN = ""; GREEN = ""; BLUE = ""; LIGHT_BLUE = ""; LAVENDER = ""; RESET = "" # type: ignore
        class MockUI: # type: ignore
            Colors = MockColors(); WARNING_SYMBOL = "!"; ERROR_SYMBOL = "X"; SUCCESS_SYMBOL = "V"; INFO_SYMBOL = "i"; PROGRESS_SYMBOL = ">" # type: ignore
            def print_dry_run_command(self, cmd_str: str): print(f"[DRY RUN] Would execute: {cmd_str}") # type: ignore
            def print_command_info(self, cmd_str: str): print(f"Executing: {cmd_str}") # type: ignore
            def print_color(self, text: str, color: str, prefix: Optional[str] = None, bold: bool = False): print(f"{prefix or ''} {text}") # type: ignore
            def prompt_yes_no(self, question: str, default_yes: bool = False) -> bool: return input(f"{question} (y/n): ").lower() == 'y' # type: ignore
            class Spinner: # type: ignore
                def __init__(self, message: str = "Processing..."): self.message = message # type: ignore
                def start(self): pass # type: ignore
                def stop(self): pass # type: ignore
        ui = MockUI() # type: ignore
        class MockConfig: # type: ignore
            DRY_RUN_MODE = False; USER_CONFIG: Dict[str, Any] = {} # type: ignore
            def get_dry_run_mode(self) -> bool: return self.DRY_RUN_MODE # type: ignore
            def get_user_config_value(self, key: str) -> Any: return self.USER_CONFIG.get(key) # type: ignore
        cfg = MockConfig() # type: ignore


def run_command(
    command: Union[List[str], str],
    check: bool = True,
    capture_output: bool = False,
    text: bool = True,
    shell: bool = False,
    cwd: Optional[Union[Path, str]] = None,
    env: Optional[Dict[str, str]] = None,
    destructive: bool = True,
    show_spinner: bool = True,
    retry_count: int = 1,
    retry_delay: float = 3.0,
    custom_spinner_message: Optional[str] = None
) -> Optional[subprocess.CompletedProcess]:
    """
    Runs a shell command with options for dry run, output capture, retries, and spinner.
    Uses subprocess.run.
    """
    cmd_str: str = ' '.join(command) if isinstance(command, list) else command

    if cfg.get_dry_run_mode() and destructive:
        ui.print_dry_run_command(cmd_str)
        if capture_output:
            mock_stdout: str = f"[DRY RUN SIMULATED OUTPUT FOR: {cmd_str}]"
            # Add specific mock outputs if necessary, based on USER_CONFIG
            # This part might need to be more sophisticated or moved if too complex
            if "lsblk" in cmd_str and "-f" in cmd_str and cfg.get_user_config_value('target_drive'):
                target_drive = str(cfg.get_user_config_value('target_drive'))
                lvm_vg_name = str(cfg.get_user_config_value('lvm_vg_name'))
                lvm_lv_root_name = str(cfg.get_user_config_value('lvm_lv_root_name'))
                lvm_lv_swap_name = str(cfg.get_user_config_value('lvm_lv_swap_name'))
                swap_size_gb_str = str(cfg.get_user_config_value('swap_size_gb'))
                swap_size_gb = 0.0
                try:
                    swap_size_gb = float(swap_size_gb_str)
                except ValueError:
                    pass # Keep swap_size_gb as 0.0 if conversion fails

                mock_stdout = (
                    f"NAME FSTYPE FSVER LABEL UUID                                 FSAVAIL FSUSE% MOUNTPOINTS\n"
                    f"{target_drive}p1 vfat   FAT32         0000-0000                            /mnt/boot/efi\n"
                    f"└─{target_drive}                                                               \n"
                    f"{lvm_vg_name}-{lvm_lv_root_name} btrfs             xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx /mnt\n"
                    f"└─{target_drive}p2 LVM2_member                                               \n"
                )
                if swap_size_gb > 0:
                    mock_stdout += f"{lvm_vg_name}-{lvm_lv_swap_name} swap   1             yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy [SWAP]\n"
            # Add other mock outputs for findmnt, swapon, pacman -Q etc. as in original
            return subprocess.CompletedProcess(
                args=command if isinstance(command, list) else shlex.split(cmd_str),
                returncode=0,
                stdout=mock_stdout,
                stderr=""
            )
        return None

    ui.print_command_info(cmd_str)
    for attempt in range(retry_count):
        spinner: Optional[Spinner] = None
        if show_spinner and not capture_output and (not shell or (shell and "&" not in cmd_str)):
            spinner_msg_to_show: str = custom_spinner_message if custom_spinner_message else (cmd_str[:70] + "..." if len(cmd_str) > 70 else cmd_str)
            spinner = ui.Spinner(message=f"Running '{spinner_msg_to_show}'")
            spinner.start()
        try:
            process: subprocess.CompletedProcess = subprocess.run(
                command,
                check=False, # We handle check manually for retries and better error reporting
                capture_output=capture_output,
                text=text,
                shell=shell,
                cwd=str(cwd) if cwd else None, # Ensure cwd is string
                env=env
            )
            if spinner:
                spinner.stop()

            if process.stderr and process.returncode != 0:
                ui.print_color(f"Stderr for '{cmd_str}':\n{process.stderr.strip()}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

            if check and process.returncode != 0:
                # This will raise CalledProcessError
                process.check_returncode()
            return process
        except subprocess.CalledProcessError as e:
            if spinner:
                spinner.stop()
            if attempt < retry_count - 1:
                ui.print_color(f"Command failed (attempt {attempt + 1}/{retry_count}): {cmd_str}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                ui.print_color(f"Retrying in {retry_delay} seconds...", ui.Colors.BLUE)
                time.sleep(retry_delay)
                continue
            ui.print_color(f"Command failed: {cmd_str}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
            if e.stdout: # stdout might be bytes if text=False, but default is True
                ui.print_color(f"Stdout:\n{e.stdout.strip() if isinstance(e.stdout, str) else e.stdout.decode(errors='replace').strip()}", ui.Colors.RED)
            # stderr is already printed above if it existed
            raise # Re-raise the exception after logging
        except FileNotFoundError:
            if spinner:
                spinner.stop()
            cmd_name: str = command[0] if isinstance(command, list) else cmd_str.split()[0]
            ui.print_color(f"Command not found: {cmd_name}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
            raise
        finally:
            if spinner and spinner.running: # Ensure spinner is stopped
                spinner.stop()
    return None # Should only be reached if retry_count is 0 or less, which is unlikely.

def make_dir_dry_run(path: Path, parents: bool = True, exist_ok: bool = True) -> None:
    """Creates a directory, printing the command if in dry run mode."""
    if cfg.get_dry_run_mode():
        ui.print_dry_run_command(f"mkdir {'-p ' if parents else ''}{str(path)}")
    else:
        path.mkdir(parents=parents, exist_ok=exist_ok)
        ui.print_color(f"Created directory: {str(path)}", ui.Colors.MINT)

def write_file_dry_run(path: Path, content: str, mode: str = "w", sudo: bool = False) -> None:
    """Writes content to a file, printing actions if in dry run mode."""
    # sudo parameter is not used with pathlib, consider removal or alternative implementation if sudo is truly needed.
    if cfg.get_dry_run_mode():
        ui.print_dry_run_command(f"write to {str(path)} (mode: {mode})")
        ui.print_color(f"--BEGIN CONTENT for {str(path)}--", ui.Colors.PEACH)
        sys.stdout.write(content[:300] + ('...' if len(content) > 300 else '') + "\n") # Use sys.stdout for direct print
        ui.print_color(f"--END CONTENT for {str(path)}--", ui.Colors.PEACH)
    else:
        try:
            with path.open(mode, encoding="utf-8") as f:
                f.write(content)
            ui.print_color(f"Written to file: {str(path)}", ui.Colors.MINT)
        except Exception as e:
            ui.print_color(f"Error writing to file {str(path)}: {e}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
            raise

def unlink_file_dry_run(path: Path, missing_ok: bool = True) -> None:
    """Deletes a file, printing the command if in dry run mode."""
    if cfg.get_dry_run_mode():
        if path.exists() or (not missing_ok and not path.exists()): # Only print if action would occur
            ui.print_dry_run_command(f"delete file: {str(path)}")
    else:
        try:
            path.unlink(missing_ok=missing_ok)
            ui.print_color(f"Deleted file: {str(path)}", ui.Colors.MINT)
        except FileNotFoundError:
            if not missing_ok:
                ui.print_color(f"Error deleting file {str(path)}: Not found.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
                raise
            else: # File not found, but missing_ok is True
                ui.print_color(f"File {str(path)} not found, skipping deletion (missing_ok=True).", ui.Colors.CYAN)
        except Exception as e:
            ui.print_color(f"Error deleting file {str(path)}: {e}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
            raise

def verify_step(
    success: bool,
    message: str,
    critical: bool = True,
    max_retries: int = 1, # Default to 1 attempt (no retries unless specified)
    retry_delay: float = 2.0,
    retry_func: Optional[Callable[[], bool]] = None
) -> bool:
    """
    Verifies a step's success, with options for retries and criticality.
    If retry_func is provided, it will be called on failure for max_retries.
    """
    current_attempt: int = 0
    # Initial check is attempt 0. Retries start from attempt 1.
    # Loop runs for initial check + number of retries.
    # So, if max_retries = 1 (original meaning: one attempt total), loop runs once.
    # If max_retries = 2 (original meaning: one initial + one retry), loop runs twice.
    # Let's adjust logic: max_attempts = max_retries (where max_retries=1 means one try)
    
    effective_max_attempts = max_retries # If max_retries means total attempts.
    if retry_func and max_retries <= 0: # Ensure at least one attempt if retry_func is there
        effective_max_attempts = 1

    while current_attempt < effective_max_attempts:
        if current_attempt > 0 and retry_func: # This is a retry attempt
            ui.print_color(f"RETRY: {message} (attempt {current_attempt + 1}/{effective_max_attempts})", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
            time.sleep(retry_delay)
            try:
                success = retry_func()
            except Exception as e:
                ui.print_color(f"Retry attempt {current_attempt + 1} failed with exception: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
                success = False
        
        if success:
            ui.print_color(f"PASSED: {message}", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
            return True

        current_attempt += 1
        if current_attempt >= effective_max_attempts or not retry_func: # No more retries or no retry function
            break

    # If loop finishes and success is still False
    ui.print_color(f"FAILED: {message}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
    if critical and not cfg.get_dry_run_mode():
        if not ui.prompt_yes_no("A critical verification failed. Continue anyway (NOT RECOMMENDED)?", default_yes=False):
            ui.print_color("Aborting installation due to critical verification failure.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL, bold=True)
            sys.exit(1) # Exit the script
        else:
            ui.print_color("Continuing despite critical verification failure as per user request.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
    elif cfg.get_dry_run_mode() and critical:
        ui.print_color("Verification failed (critical), this might be expected if preceding destructive steps were skipped in dry run.", ui.Colors.PEACH, prefix=f"{ui.Colors.YELLOW}[DRY RUN]{ui.Colors.RESET}")
    return False