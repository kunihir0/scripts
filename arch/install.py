#!/usr/bin/env python3

import subprocess
import sys
import time
import shlex
import argparse
from pathlib import Path
import os
import threading
import random 
import math 
import json # For saving/loading USER_CONFIG

# --- Global Dry Run Flag ---
DRY_RUN_MODE = False

# --- Installation Steps Tracking ---
INSTALL_STEPS = [
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
CURRENT_STEP = 0
RESTART_STEP = 0

# --- Configuration Constants (User-configurable defaults) ---
USER_CONFIG = {
    "username": "bao",
    "hostname": "bao",
    "timezone": "America/Denver",
    "locale_lang": "en_US.UTF-8",
    "locale_gen": "en_US.UTF-8 UTF-8",
    "vconsole_keymap": "us",
    "target_drive": "",
    "efi_partition_size": "1G",
    "swap_size_gb": "4", # Defaulting to 4GB disk swap + ZRAM
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

# Hardcoded Passwords
BAO_PASSWORD = "7317"
ROOT_PASSWORD = "73177317"

# --- UI System ---
class Colors:
    PINK = '\033[38;5;219m'; PURPLE = '\033[38;5;183m'; CYAN = '\033[38;5;123m'
    YELLOW = '\033[38;5;228m'; BLUE = '\033[38;5;111m'; ORANGE = '\033[38;5;216m'
    GREEN = '\033[38;5;156m'; RED = '\033[38;5;210m'; MAGENTA = '\033[38;5;201m'
    LIGHT_BLUE = '\033[38;5;159m'; LAVENDER = '\033[38;5;147m'; PEACH = '\033[38;5;223m'
    MINT = '\033[38;5;121m'; PINK_BG = '\033[48;5;219m'; DARK_BG = '\033[48;5;236m'
    BOLD = '\033[1m'; ITALIC = '\033[3m'; UNDERLINE = '\033[4m'; BLINK = '\033[5m'
    RESET = '\033[0m'

SUCCESS_SYMBOL = f"{Colors.GREEN}✓{Colors.RESET}"; WARNING_SYMBOL = f"{Colors.YELLOW}!{Colors.RESET}"
ERROR_SYMBOL = f"{Colors.RED}✗{Colors.RESET}"; INFO_SYMBOL = f"{Colors.CYAN}✧{Colors.RESET}"
PROGRESS_SYMBOL = f"{Colors.BLUE}→{Colors.RESET}"; NOTE_SYMBOL = f"{Colors.LAVENDER}•{Colors.RESET}"
STAR_SYMBOL = f"{Colors.PURPLE}★{Colors.RESET}"

PROGRESS_FILE = Path("/tmp/arch_install_progress.json") 

def save_progress():
    global USER_CONFIG 
    if not DRY_RUN_MODE:
        try:
            progress_data = {
                "current_step": CURRENT_STEP,
                "user_config": USER_CONFIG 
            }
            with open(PROGRESS_FILE, "w") as f:
                json.dump(progress_data, f, indent=4)
        except Exception as e: print_color(f"Note: Could not save progress: {e}", Colors.YELLOW, prefix=WARNING_SYMBOL)

def load_progress():
    global RESTART_STEP, USER_CONFIG 
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE, "r") as f:
                progress_data = json.load(f)
            
            step = progress_data.get("current_step")
            loaded_user_config = progress_data.get("user_config")

            if isinstance(step, int) and 0 <= step < len(INSTALL_STEPS) and isinstance(loaded_user_config, dict):
                RESTART_STEP = step
                USER_CONFIG.update(loaded_user_config) 
                print_color(f"Found saved progress at step {step} ({INSTALL_STEPS[step]}) and loaded USER_CONFIG.", Colors.CYAN, prefix=INFO_SYMBOL)
                
                if not USER_CONFIG.get("target_drive"):
                    print_color("Loaded USER_CONFIG is missing 'target_drive'. Restarting from configuration.", Colors.ORANGE, prefix=WARNING_SYMBOL)
                    PROGRESS_FILE.unlink(missing_ok=True) 
                    return 0 
                return step
            else:
                print_color(f"Invalid data in progress file. Starting from beginning.", Colors.ORANGE, prefix=WARNING_SYMBOL)
                PROGRESS_FILE.unlink(missing_ok=True)
        except Exception as e:
            print_color(f"Could not load progress file ({e}). Starting from beginning.", Colors.ORANGE, prefix=WARNING_SYMBOL)
            PROGRESS_FILE.unlink(missing_ok=True)
    return 0

def print_color(text: str, color: str, bold: bool = False, prefix: str | None = None, italic: bool = False):
    style_str = (Colors.BOLD if bold else "") + (Colors.ITALIC if italic else "")
    prefix_str = f"{prefix} " if prefix else ""
    print(f"{prefix_str}{style_str}{color}{text}{Colors.RESET}")

def print_header(title: str): print_color(f"❄️ === {title} === ❄️", Colors.PINK_BG + Colors.CYAN + Colors.BOLD); print("")
def print_section_header(title: str):
    gradient_colors = [Colors.PINK, Colors.PURPLE, Colors.CYAN, Colors.BLUE, Colors.MAGENTA]
    styled_title = "".join(f"{gradient_colors[i % len(gradient_colors)]}{char}" for i, char in enumerate(title))
    print_color(f"--- {styled_title}{Colors.RESET} ---", Colors.PURPLE, bold=True, prefix=STAR_SYMBOL); print("")
def print_step_info(message: str): print_color(message, Colors.LIGHT_BLUE, prefix=INFO_SYMBOL)
def print_command_info(cmd_str: str): print_color(f"Executing: {cmd_str}", Colors.CYAN, prefix=PROGRESS_SYMBOL)
def print_dry_run_command(cmd_str: str): print_color(f"Would execute: {cmd_str}", Colors.PEACH, prefix=f"{Colors.YELLOW}[DRY RUN]{Colors.RESET}")

class Spinner:
    def __init__(self, message="Processing...", delay=0.1, spinner_chars=None):
        self.spinner_chars = spinner_chars if spinner_chars else ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.delay = delay
        self.message = message
        self._thread = None
        self.running = False
    def _spin(self):
        idx = 0
        while self.running:
            spinner_char = self.spinner_chars[idx % len(self.spinner_chars)]
            sys.stdout.write(f"\r{Colors.LIGHT_BLUE}{spinner_char}{Colors.RESET} {self.message} "); sys.stdout.flush(); time.sleep(self.delay); idx += 1
        sys.stdout.write(f"\r{' ' * (len(self.message) + 5)}\r"); sys.stdout.flush()
    def start(self):
        if sys.stdout.isatty(): self.running = True; self._thread = threading.Thread(target=self._spin); self._thread.daemon = True; self._thread.start()
    def stop(self):
        if self.running: self.running = False
        if self._thread and self._thread.is_alive(): self._thread.join(timeout=self.delay * 2)
        sys.stdout.write(f"\r{' ' * (len(self.message) + 5)}\r"); sys.stdout.flush()

# --- Core Helper Functions ---
def run_command( command: list[str] | str, check: bool = True, capture_output: bool = False, text: bool = True, shell: bool = False, cwd: Path | str | None = None, env: dict | None = None, destructive: bool = True, show_spinner: bool = True, retry_count: int = 1, retry_delay: float = 3.0, custom_spinner_message: str | None = None) -> subprocess.CompletedProcess | None:
    cmd_str = ' '.join(command) if isinstance(command, list) else command
    if DRY_RUN_MODE and destructive:
        print_dry_run_command(cmd_str)
        if capture_output: 
            mock_stdout = f"[DRY RUN SIMULATED OUTPUT FOR: {cmd_str}]"
            if "lsblk" in cmd_str and "-f" in cmd_str : 
                mock_stdout = ( f"NAME FSTYPE FSVER LABEL UUID                                 FSAVAIL FSUSE% MOUNTPOINTS\n"
                    f"{USER_CONFIG['target_drive']}p1 vfat   FAT32         0000-0000                            /mnt/boot/efi\n"
                    f"└─{USER_CONFIG['target_drive']}                                                               \n"
                    f"{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_root_name']} btrfs             xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx /mnt\n"
                    f"└─{USER_CONFIG['target_drive']}p2 LVM2_member                                               \n" )
                if float(USER_CONFIG.get('swap_size_gb', 0)) > 0: 
                     mock_stdout += f"{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_swap_name']} swap   1             yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy [SWAP]\n"
            elif "findmnt" in cmd_str: 
                 mock_stdout = ( f"TARGET                                SOURCE                                                               FSTYPE OPTIONS\n"
                    f"/mnt                                  /dev/mapper/{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_root_name']}[/{USER_CONFIG['btrfs_subvol_root']}] btrfs  rw,noatime,{USER_CONFIG['btrfs_mount_options']},subvol=/{USER_CONFIG['btrfs_subvol_root']}\n"
                    f"/mnt/home                             /dev/mapper/{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_root_name']}[/{USER_CONFIG['btrfs_subvol_home']}] btrfs  rw,noatime,{USER_CONFIG['btrfs_mount_options']},subvol=/{USER_CONFIG['btrfs_subvol_home']}\n"
                    f"/mnt/var                              /dev/mapper/{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_root_name']}[/{USER_CONFIG['btrfs_subvol_var']}] btrfs  rw,noatime,{USER_CONFIG['btrfs_mount_options']},subvol=/{USER_CONFIG['btrfs_subvol_var']}\n"
                    f"/mnt/boot/efi                         {USER_CONFIG['target_drive']}{'p1' if 'nvme' in USER_CONFIG['target_drive'] else '1'}              vfat   rw,relatime\n" )
            elif "swapon --show" in cmd_str and float(USER_CONFIG.get('swap_size_gb', 0)) > 0:
                mock_stdout = f"NAME                                     TYPE      SIZE USED PRIO\n/dev/mapper/{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_swap_name']} partition 8G   0B   -2"
            elif "pacman -Q" in cmd_str: 
                if "linux-surface" in cmd_str: mock_stdout = "linux-surface 6.14.2.arch1-1" # Example, adjust if needed
                elif "dracut" in cmd_str: mock_stdout = "dracut 059-1" 
                else: mock_stdout = f"some-package 1.0-1" 
            return subprocess.CompletedProcess(args=command if isinstance(command, list) else shlex.split(cmd_str), returncode=0, stdout=mock_stdout, stderr="")
        return None
    print_command_info(cmd_str)
    for attempt in range(retry_count):
        spinner = None
        if show_spinner and not capture_output and (not shell or (shell and "&" not in cmd_str)): 
            spinner_msg_to_show = custom_spinner_message if custom_spinner_message else (cmd_str[:70] + "..." if len(cmd_str) > 70 else cmd_str)
            spinner = Spinner(message=f"Running '{spinner_msg_to_show}'")
            spinner.start()
        try:
            process = subprocess.run( command, check=False, capture_output=capture_output, text=text, shell=shell, cwd=cwd, env=env )
            if spinner: spinner.stop()
            if process.stderr and process.returncode != 0 : 
                 print_color(f"Stderr for '{cmd_str}':\n{process.stderr.strip()}", Colors.ORANGE, prefix=WARNING_SYMBOL)
            if check and process.returncode != 0: 
                process.check_returncode() 
            return process
        except subprocess.CalledProcessError as e:
            if spinner: spinner.stop()
            if attempt < retry_count - 1:
                print_color(f"Command failed (attempt {attempt+1}/{retry_count}): {cmd_str}", Colors.ORANGE, prefix=WARNING_SYMBOL)
                print_color(f"Retrying in {retry_delay} seconds...", Colors.BLUE); time.sleep(retry_delay)
                continue
            print_color(f"Command failed: {cmd_str}", Colors.RED, prefix=ERROR_SYMBOL, bold=True)
            if e.stdout: print_color(f"Stdout:\n{e.stdout.strip()}", Colors.RED)
            raise
        except FileNotFoundError:
            if spinner: spinner.stop()
            print_color(f"Command not found: {command[0] if isinstance(command, list) else cmd_str.split()[0]}", Colors.RED, prefix=ERROR_SYMBOL, bold=True)
            raise
        finally:
            if spinner and spinner.running: spinner.stop()

def make_dir_dry_run(path: Path, parents: bool = True, exist_ok: bool = True):
    if DRY_RUN_MODE: print_dry_run_command(f"mkdir {'-p ' if parents else ''}{path}")
    else: path.mkdir(parents=parents, exist_ok=exist_ok); print_color(f"Created directory: {path}", Colors.MINT)
def write_file_dry_run(path: Path, content: str, mode: str = "w", sudo: bool = False):
    if DRY_RUN_MODE:
        print_dry_run_command(f"write to {path} (mode: {mode})")
        print_color(f"--BEGIN CONTENT for {path}--", Colors.PEACH); print(content[:300] + ('...' if len(content) > 300 else '')); print_color(f"--END CONTENT for {path}--", Colors.PEACH)
    else:
        try:
            with open(path, mode) as f: f.write(content)
            print_color(f"Written to file: {path}", Colors.MINT)
        except Exception as e: print_color(f"Error writing to file {path}: {e}", Colors.RED, prefix=ERROR_SYMBOL); raise
def unlink_file_dry_run(path: Path, missing_ok: bool = True):
    if DRY_RUN_MODE:
        if path.exists() or (not missing_ok and not path.exists()): print_dry_run_command(f"delete file: {path}")
    else:
        try:
            path.unlink(missing_ok=missing_ok); print_color(f"Deleted file: {path}", Colors.MINT)
        except FileNotFoundError:
            if not missing_ok: print_color(f"Error deleting file {path}: Not found.", Colors.RED, prefix=ERROR_SYMBOL); raise
            else: print_color(f"File {path} not found, skipping deletion (missing_ok=True).", Colors.CYAN)
        except Exception as e: print_color(f"Error deleting file {path}: {e}", Colors.RED, prefix=ERROR_SYMBOL); raise
def prompt_yes_no(question: str, default_yes: bool = False) -> bool:
    suffix = f" [{Colors.PINK}Y{Colors.LAVENDER}/n{Colors.LAVENDER}]" if default_yes else f" [{Colors.LAVENDER}y/{Colors.PINK}N{Colors.LAVENDER}]"
    while True:
        reply = input(f"{Colors.LAVENDER}{question}{suffix}: {Colors.RESET}").strip().lower()
        if not reply: return default_yes
        if reply in ['y', 'yes']: return True
        if reply in ['n', 'no']: return False
        print_color("Invalid input. Please enter 'y' or 'n'.", Colors.ORANGE, prefix=WARNING_SYMBOL)
def prompt_input(question: str, default: str | None = None, validator=None, sensitive: bool = False) -> str:
    suffix = f" (default: {Colors.CYAN}{default}{Colors.MINT})" if default and not sensitive else ""
    prompt_text = f"{Colors.MINT}{question}{suffix}: {Colors.RESET}"
    while True:
        reply = input(prompt_text).strip() if not sensitive else input(prompt_text) 
        if reply:
            if validator and not validator(reply): continue
            return reply
        if default is not None:
            if validator and not validator(default): print_color("Default value is invalid, this is a script bug.", Colors.RED, prefix=ERROR_SYMBOL); sys.exit(1)
            return default
        print_color("Input cannot be empty.", Colors.ORANGE, prefix=WARNING_SYMBOL)
def verify_step(success: bool, message: str, critical: bool = True, max_retries: int = 1, retry_delay: float = 2.0, retry_func=None):
    current_attempt = 0
    while current_attempt <= max_retries -1 :
        if success: print_color(f"PASSED: {message}", Colors.GREEN, prefix=SUCCESS_SYMBOL); return True
        current_attempt += 1
        if current_attempt <= max_retries -1 and retry_func:
            print_color(f"RETRY: {message} (attempt {current_attempt}/{max_retries})", Colors.ORANGE, prefix=WARNING_SYMBOL); time.sleep(retry_delay)
            try: success = retry_func() 
            except Exception as e: print_color(f"Retry attempt {current_attempt} failed with exception: {e}", Colors.ORANGE, prefix=WARNING_SYMBOL); success = False 
        elif current_attempt > max_retries -1 : break 
        else: break
    print_color(f"FAILED: {message}", Colors.RED, prefix=ERROR_SYMBOL, bold=True)
    if critical and not DRY_RUN_MODE:
        if not prompt_yes_no("A critical verification failed. Continue anyway (NOT RECOMMENDED)?", default_yes=False):
            print_color("Aborting installation due to critical verification failure.", Colors.RED, prefix=ERROR_SYMBOL, bold=True); sys.exit(1)
        else: print_color("Continuing despite critical verification failure as per user request.", Colors.ORANGE, prefix=WARNING_SYMBOL)
    elif DRY_RUN_MODE and critical: print_color("Verification failed (critical), this might be expected if preceding destructive steps were skipped in dry run.", Colors.PEACH, prefix=f"{Colors.YELLOW}[DRY RUN]{Colors.RESET}")
    return False

# --- Installation Step Functions ---
def gather_initial_config(): 
    global CURRENT_STEP, USER_CONFIG
    print_section_header("Gathering System Configuration")
    
    # Only prompt for target_drive
    USER_CONFIG["target_drive"] = select_drive()
    
    # Use defaults for other settings, but ensure they are correctly typed if loaded from JSON
    # For example, swap_size_gb should be a string representation of an int.
    # add_chaotic_aur should be a boolean.
    # This is mostly handled by how USER_CONFIG is defined and updated in load_progress.
    # We can add type assertions or conversions here if needed for robustness after loading.

    print_color(f"Using hostname: {USER_CONFIG['hostname']} (default)", Colors.CYAN)
    print_color(f"Using username: {USER_CONFIG['username']} (default)", Colors.CYAN)
    print_color(f"Using timezone: {USER_CONFIG['timezone']} (default)", Colors.CYAN)
    print_color(f"Using locale language: {USER_CONFIG['locale_lang']} (default)", Colors.CYAN)
    print_color(f"Using locale.gen entry: {USER_CONFIG['locale_gen']} (default)", Colors.CYAN)
    print_color(f"Using vconsole keymap: {USER_CONFIG['vconsole_keymap']} (default)", Colors.CYAN)
    print_color(f"Using disk swap size: {USER_CONFIG['swap_size_gb']}GB (default)", Colors.CYAN)
    print_color(f"Using ZRAM fraction: {USER_CONFIG['zram_fraction']} (default)", Colors.CYAN)
    print_color(f"Adding Chaotic-AUR: {'Yes' if USER_CONFIG['add_chaotic_aur'] else 'No'} (default)", Colors.CYAN)

    print_color("Initial configuration set (mostly defaults).", Colors.GREEN, prefix=SUCCESS_SYMBOL)
    CURRENT_STEP = INSTALL_STEPS.index("prepare_environment")
    save_progress() # Save USER_CONFIG with the selected target_drive
    print("")

def select_drive() -> str: 
    print_step_info("Detecting available drives...")
    try:
        lsblk_process = run_command(["lsblk", "-dnpo", "NAME,SIZE,MODEL"], capture_output=True, destructive=False, show_spinner=False)
        lsblk_output = lsblk_process.stdout if lsblk_process else ""
        drives = []
        if lsblk_output:
            header_skipped = False
            for line in lsblk_output.strip().split('\n'):
                if not header_skipped and "NAME" in line and "SIZE" in line: header_skipped = True; continue
                parts = line.split(maxsplit=2)
                if len(parts) >= 2: drives.append({"name": parts[0], "size": parts[1], "model": parts[2] if len(parts) > 2 else "N/A"})
        if not drives: print_color("No drives found. Cannot proceed.", Colors.RED, prefix=ERROR_SYMBOL); sys.exit(1)
        print_color("Available drives:", Colors.MAGENTA, bold=True)
        for i, drive in enumerate(drives): print(f"  {Colors.PINK}{i + 1}{Colors.RESET}) {Colors.CYAN}{drive['name']}{Colors.RESET} ({Colors.LIGHT_BLUE}{drive['size']}{Colors.RESET}) - {Colors.BLUE}{drive['model']}{Colors.RESET}")
        while True:
            try:
                choice_str = prompt_input("Select drive number for installation")
                choice = int(choice_str) - 1
                if 0 <= choice < len(drives):
                    selected_drive_info = drives[choice]; selected_drive_name = selected_drive_info['name']
                    confirm_q = (f"You selected {Colors.BOLD}{selected_drive_name}{Colors.LAVENDER} ({selected_drive_info['size']} - {selected_drive_info['model']}).\n"
                                 f"{Colors.RED}{Colors.BOLD}ALL DATA ON THIS DRIVE WILL BE ERASED (if not in dry run).{Colors.LAVENDER} Are you sure?")
                    if prompt_yes_no(confirm_q, default_yes=False): return selected_drive_name
                    else: print_color("Drive selection aborted by user.", Colors.ORANGE, prefix=WARNING_SYMBOL) # Stay in loop if user aborts this specific choice
                else: print_color("Invalid selection. Please enter a number from the list.", Colors.ORANGE, prefix=WARNING_SYMBOL)
            except ValueError: print_color("Invalid input. Please enter a number.", Colors.ORANGE, prefix=WARNING_SYMBOL)
    except Exception as e: print_color(f"Error selecting drive: {e}", Colors.RED, prefix=ERROR_SYMBOL); sys.exit(1)
    return "" # Should not be reached if a drive is selected

def display_summary_and_confirm(): 
    print_section_header("Installation Plan Summary")
    if DRY_RUN_MODE: print_color("[DRY RUN MODE - NO DISK CHANGES WILL BE MADE]", Colors.YELLOW, bold=True, prefix=WARNING_SYMBOL)
    
    # Ensure all USER_CONFIG values are strings for display if they might be other types (like bool for add_chaotic_aur)
    summary_user_config = {k: (str(v).lower() if isinstance(v, bool) else str(v)) for k, v in USER_CONFIG.items()}

    summary_items = [("User", summary_user_config['username'], BAO_PASSWORD[:2] + "** (hardcoded)"), ("Root Password", ROOT_PASSWORD[:2] + "** (hardcoded, login will be disabled)", ""),
        ("Hostname", summary_user_config['hostname'], ""), ("Target Drive", summary_user_config['target_drive'], Colors.BOLD + Colors.PINK), ("EFI Partition Size", summary_user_config['efi_partition_size'], ""),
        ("Disk Swap Size", f"{summary_user_config['swap_size_gb']}GB", "LVM LV, resizable post-install" if float(summary_user_config['swap_size_gb']) > 0 else "None (ZRAM only)"),
        ("ZRAM Fraction", f"{summary_user_config['zram_fraction']} (of total RAM)", ""), ("LVM VG Name", summary_user_config['lvm_vg_name'], ""),
        ("Btrfs Subvolumes", f"{summary_user_config['btrfs_subvol_root']}, {summary_user_config['btrfs_subvol_home']}, etc.", ""), ("Timezone", summary_user_config['timezone'], ""), ("Locale", summary_user_config['locale_lang'], ""),
        ("Keyboard", summary_user_config['vconsole_keymap'], ""), ("Kernel", "linux-surface (for Surface Pro 7)", ""), ("Desktop", f"Minimal GNOME (Wayland) with auto-login for '{summary_user_config['username']}'", ""),
        ("Default Editor", "Neovim", ""), ("Monospace Font", summary_user_config['default_monospace_font_pkg'], ""), ("Web Browser", "Google Chrome (AUR) - to be installed by chroot script", ""),
        ("CPU Optimization (makepkg)", f"-march={summary_user_config['cpu_march']}", ""), ("Add Chaotic-AUR", "Yes" if USER_CONFIG['add_chaotic_aur'] else "No", "") ] # Use original boolean for "Yes/No"
    for label, value, notes_color_or_extra in summary_items:
        extra_info = ""; value_color = Colors.CYAN
        if isinstance(notes_color_or_extra, str) and notes_color_or_extra.startswith('\033['): value_color = notes_color_or_extra
        elif notes_color_or_extra: extra_info = f" {Colors.PEACH}({notes_color_or_extra}){Colors.RESET}"
        print(f"  {Colors.LAVENDER}{label}:{Colors.RESET} {value_color}{value}{Colors.RESET}{extra_info}")
    print_color("\nCRITICAL WARNING:", Colors.RED + Colors.BOLD, prefix=ERROR_SYMBOL)
    print_color(f"ALL DATA ON {USER_CONFIG['target_drive']} WILL BE PERMANENTLY ERASED (if not in dry run).", Colors.RED)
    if not prompt_yes_no("Proceed with installation plan?", default_yes=False): print_color("Aborted by user.", Colors.ORANGE, prefix=WARNING_SYMBOL); sys.exit(0)
    print_color("Proceeding with installation...", Colors.GREEN, prefix=PROGRESS_SYMBOL); print("")
def prepare_live_environment(): 
    global CURRENT_STEP; print_section_header("Preparing Live Environment")
    if CURRENT_STEP > INSTALL_STEPS.index("prepare_environment"): print_step_info("Skipping (already completed)"); print(""); return
    if not check_internet_connection() and not DRY_RUN_MODE:
        if not prompt_yes_no("Internet connection check failed. Continue anyway?", default_yes=False): sys.exit(1)
    run_command(["pacman", "-S", "--noconfirm", "--needed", "curl", "arch-install-scripts"], destructive=True, custom_spinner_message="Installing essential tools")
    pacman_conf_path = Path("/etc/pacman.conf"); surface_repo_header = "[linux-surface]"; surface_repo_entry = f"\n{surface_repo_header}\nServer = https://pkg.surfacelinux.com/arch/\n"
    if DRY_RUN_MODE: print_dry_run_command(f"ensure {surface_repo_header} in {pacman_conf_path}")
    else:
        try:
            content = pacman_conf_path.read_text() if pacman_conf_path.exists() else ""
            if surface_repo_header not in content:
                with open(pacman_conf_path, "a") as f: f.write(surface_repo_entry)
                print_color(f"Appended {surface_repo_header} to {pacman_conf_path}", Colors.MINT)
            else: print_color(f"{surface_repo_header} already in {pacman_conf_path}", Colors.CYAN)
        except Exception as e: print_color(f"Error updating {pacman_conf_path}: {e}", Colors.ORANGE, prefix=WARNING_SYMBOL)
    print_step_info("Adding linux-surface GPG key to live environment...")
    run_command("curl -s https://raw.githubusercontent.com/linux-surface/linux-surface/master/pkg/keys/surface.asc | pacman-key --add -", shell=True, destructive=True)
    run_command(["pacman-key", "--lsign-key", "56C464BAAC421453"], destructive=True) 
    print_step_info("Syncing pacman databases..."); run_command(["pacman", "-Sy"], destructive=True)
    print_color("Live environment prepared.", Colors.GREEN, prefix=SUCCESS_SYMBOL); CURRENT_STEP = INSTALL_STEPS.index("partition_format"); save_progress(); print("")
def check_internet_connection() -> bool: 
    print_step_info("Checking internet connection...")
    try: run_command(["ping", "-c", "1", "archlinux.org"], capture_output=True, destructive=False, show_spinner=False, check=True); print_color("Internet connection active.", Colors.GREEN, prefix=SUCCESS_SYMBOL); return True
    except subprocess.CalledProcessError: print_color("Internet check failed.", Colors.RED, prefix=ERROR_SYMBOL); return False
    except FileNotFoundError: print_color("`ping` not found. Assuming connected (cannot verify).", Colors.ORANGE, prefix=WARNING_SYMBOL); return True
def check_and_free_device(device_path_str: str): 
    print_step_info(f"Ensuring {device_path_str} and its partitions are free..."); device_path = Path(device_path_str)
    mnt_base = Path("/mnt"); explicit_unmount_targets = [ mnt_base / "boot/efi", mnt_base / "boot", mnt_base / "home", mnt_base / "var", mnt_base / ".snapshots", mnt_base ]
    for target_path in explicit_unmount_targets:
        findmnt_check = run_command(["findmnt", "-n", "-r", "-o", "TARGET", "--target", str(target_path)], capture_output=True, destructive=False, show_spinner=False, check=False)
        if findmnt_check and findmnt_check.returncode == 0 and str(target_path) in findmnt_check.stdout.strip():
            print_color(f"Attempting to unmount {target_path} (lazy)...", Colors.BLUE); run_command(["umount", "-fl", str(target_path)], check=False, destructive=True, show_spinner=False, retry_count=3, retry_delay=1.5)
    swapon_proc = run_command(["swapon", "--show=NAME,TYPE"], capture_output=True, destructive=False, show_spinner=False, check=False)
    if swapon_proc and swapon_proc.stdout:
        for line in swapon_proc.stdout.strip().split('\n')[1:]:
            parts = line.split()
            if parts and Path(parts[0]).resolve().is_relative_to(device_path.resolve()): 
                print_color(f"Deactivating swap on {parts[0]}...", Colors.BLUE); run_command(["swapoff", parts[0]], check=False, destructive=True)
    target_vg_name = USER_CONFIG.get('lvm_vg_name'); sfx_func = lambda p_num: "p" + str(p_num) if "nvme" in USER_CONFIG['target_drive'] or "loop" in USER_CONFIG['target_drive'] else str(p_num)
    lvm_partition_device_str = f"{USER_CONFIG['target_drive']}{sfx_func(2)}" 
    if target_vg_name:
        vgdisplay_proc = run_command(["vgdisplay", target_vg_name], check=False, destructive=False, capture_output=True, show_spinner=False)
        if vgdisplay_proc and vgdisplay_proc.returncode == 0:
            print_color(f"Volume group {target_vg_name} exists. Attempting deactivation...", Colors.BLUE)
            for lv_name_key in ["lvm_lv_root_name", "lvm_lv_swap_name"]:
                lv_name = USER_CONFIG.get(lv_name_key)
                if lv_name:
                    lv_path_vg = f"/dev/{target_vg_name}/{lv_name}"; lv_path_map = f"/dev/mapper/{target_vg_name}-{lv_name}"
                    if Path(lv_path_vg).exists() or Path(lv_path_map).exists():
                         print_color(f"Deactivating LV: {lv_name}...", Colors.BLUE); run_command(["lvchange", "-an", f"{target_vg_name}/{lv_name}"], check=False, destructive=True, show_spinner=False, retry_count=2)
            run_command(["sync"], check=False, destructive=False, show_spinner=False); time.sleep(1)
            vgchange_proc = run_command(["vgchange", "-an", target_vg_name], check=False, destructive=True, capture_output=True, show_spinner=False, retry_count=2)
            if not (vgchange_proc and vgchange_proc.returncode == 0):
                print_color(f"Failed to deactivate VG {target_vg_name}. Attempting forceful removal...", Colors.ORANGE, prefix=WARNING_SYMBOL)
                run_command(["vgremove", "--force", "--force", "-y", target_vg_name], check=False, destructive=True, show_spinner=False)
                if Path(lvm_partition_device_str).exists(): run_command(["pvremove", "--force", "--force", "-y", lvm_partition_device_str], check=False, destructive=True, show_spinner=False)
            else: print_color(f"Successfully deactivated VG {target_vg_name}.", Colors.MINT)
        elif Path(lvm_partition_device_str).exists(): 
             print_color(f"VG {target_vg_name} not found. Checking for PV signatures on {lvm_partition_device_str}...", Colors.CYAN)
             run_command(["pvremove", "--force", "--force", "-y", lvm_partition_device_str], check=False, destructive=True, show_spinner=False)
    run_command(["sync"], check=False, destructive=False, show_spinner=False); print_color("Pausing for 3 seconds after deactivation attempts...", Colors.BLUE); time.sleep(3)
    print_step_info(f"Device {device_path_str} freeing attempts complete."); print("")
def partition_and_format(): 
    global CURRENT_STEP; print_section_header(f"Partitioning & Formatting {USER_CONFIG['target_drive']}")
    if CURRENT_STEP > INSTALL_STEPS.index("partition_format"): print_step_info("Skipping (already completed)"); print(""); return
    drive = USER_CONFIG['target_drive']
    if not drive: print_color("Target drive not set. Aborting partition_and_format.", Colors.RED, prefix=ERROR_SYMBOL); sys.exit(1)
    check_and_free_device(drive) 
    sfx = lambda p: "p" + str(p) if "nvme" in drive or "loop" in drive else str(p)
    efi_part_dev = f"{drive}{sfx(1)}"; lvm_part_dev = f"{drive}{sfx(2)}"
    print_step_info(f"Wiping device signatures on {drive}..."); run_command(["wipefs", "-a", drive], destructive=True, check=True)
    print_step_info(f"Creating new GPT partition table on {drive}..."); run_command(["sgdisk", "-Zo", drive], destructive=True, check=True)
    print_step_info(f"Creating EFI partition ({USER_CONFIG['efi_partition_size']})..."); run_command(["sgdisk", f"-n=1:0:+{USER_CONFIG['efi_partition_size']}", "-t=1:ef00", f"-c=1:EFI System Partition", drive], destructive=True, check=True)
    print_step_info("Creating LVM partition (remaining space)..."); run_command(["sgdisk", "-n=2:0:0", "-t=2:8e00", f"-c=2:Linux LVM", drive], destructive=True, check=True)
    print_step_info("Informing kernel of partition table changes..."); run_command(["partprobe", drive], check=False, destructive=True) 
    if not DRY_RUN_MODE:
        time.sleep(3) 
        if not Path(efi_part_dev).exists() or not Path(lvm_part_dev).exists():
            print_color(f"Partitions {efi_part_dev} or {lvm_part_dev} not detected after partprobe. Retrying udev.", Colors.ORANGE, prefix=WARNING_SYMBOL)
            run_command(["udevadm", "settle"], destructive=False, check=False); run_command(["udevadm", "trigger"], destructive=False, check=False); time.sleep(3)
            if not Path(efi_part_dev).exists() or not Path(lvm_part_dev).exists(): print_color(f"CRITICAL: Partitions still not detected on {drive}.", Colors.RED, prefix=ERROR_SYMBOL); sys.exit(1)
        print_color("Partitions detected.", Colors.MINT)
    print_step_info(f"Formatting EFI partition {efi_part_dev} as FAT32..."); run_command(["mkfs.vfat", "-F32", efi_part_dev], destructive=True, check=True)
    print_step_info(f"Wiping any old signatures on LVM partition {lvm_part_dev}..."); run_command(["wipefs", "-a", lvm_part_dev], destructive=True, check=True, retry_count=2) 
    print_step_info("Setting up LVM..."); run_command(["pvcreate", "--yes", lvm_part_dev], destructive=True, check=True); run_command(["vgcreate", USER_CONFIG['lvm_vg_name'], lvm_part_dev], destructive=True, check=True)
    lv_root_path_str = f"/dev/{USER_CONFIG['lvm_vg_name']}/{USER_CONFIG['lvm_lv_root_name']}"
    if float(USER_CONFIG['swap_size_gb']) > 0:
        print_step_info(f"Creating SWAP LV ({USER_CONFIG['swap_size_gb']}G)..."); run_command(["lvcreate", "-L", f"{USER_CONFIG['swap_size_gb']}G", "-n", USER_CONFIG['lvm_lv_swap_name'], USER_CONFIG['lvm_vg_name']], destructive=True, check=True)
        lv_swap_path_str = f"/dev/{USER_CONFIG['lvm_vg_name']}/{USER_CONFIG['lvm_lv_swap_name']}"; print_step_info(f"Formatting SWAP LV {lv_swap_path_str}..."); run_command(["mkswap", lv_swap_path_str], destructive=True, check=True)
    print_step_info("Creating ROOT LV (100%FREE)..."); run_command(["lvcreate", "-l", "100%FREE", "-n", USER_CONFIG['lvm_lv_root_name'], USER_CONFIG['lvm_vg_name']], destructive=True, check=True)
    print_step_info(f"Formatting ROOT LV {lv_root_path_str} as Btrfs..."); run_command(["mkfs.btrfs", "-f", lv_root_path_str], destructive=True, check=True) 
    mnt_temp_btrfs = Path("/mnt/.btrfs_setup_temp"); print_step_info(f"Temporarily mounting {lv_root_path_str} to {mnt_temp_btrfs} for subvolume creation...")
    make_dir_dry_run(mnt_temp_btrfs, parents=True, exist_ok=True); run_command(["mount", lv_root_path_str, str(mnt_temp_btrfs)], destructive=True, check=True)
    print_step_info("Creating Btrfs subvolumes...")
    for subvol_key in ["btrfs_subvol_root", "btrfs_subvol_home", "btrfs_subvol_var", "btrfs_subvol_snapshots"]:
        subvol_name = USER_CONFIG[subvol_key]; print_color(f"Creating Btrfs subvolume: {subvol_name}", Colors.BLUE); run_command(["btrfs", "subvolume", "create", str(mnt_temp_btrfs / subvol_name)], destructive=True, cwd=mnt_temp_btrfs, check=True)
    print_step_info(f"Unmounting {mnt_temp_btrfs}..."); run_command(["umount", str(mnt_temp_btrfs)], destructive=True, check=True)
    if not DRY_RUN_MODE:
        try: mnt_temp_btrfs.rmdir() 
        except OSError as e: print_color(f"Warning: Could not remove temp dir {mnt_temp_btrfs}: {e}", Colors.ORANGE)
    print_color("Partitioning & formatting complete.", Colors.GREEN, prefix=SUCCESS_SYMBOL); CURRENT_STEP = INSTALL_STEPS.index("mount_filesystems"); save_progress(); print("")
def verify_partitions_lvm(no_verify_arg: bool): 
    if no_verify_arg: print_step_info("Skipping partition & LVM verification as per --no-verify."); print(""); return
    print_section_header("Verifying Partitions and LVM")
    if CURRENT_STEP <= INSTALL_STEPS.index("partition_format"): print_color("Verification running before its intended step, results might be inaccurate.", Colors.ORANGE, prefix=WARNING_SYMBOL)
    drive = USER_CONFIG['target_drive']; sfx = lambda p: "p"+str(p) if "nvme" in drive or "loop" in drive else str(p)
    efi_part_dev = f"{drive}{sfx(1)}"; lvm_part_dev = f"{drive}{sfx(2)}"; lv_root_path = Path(f"/dev/{USER_CONFIG['lvm_vg_name']}/{USER_CONFIG['lvm_lv_root_name']}")
    all_ok = True
    if not verify_step(Path(efi_part_dev).exists() if not DRY_RUN_MODE else True, f"EFI partition {efi_part_dev} exists", critical=True): all_ok = False
    if not verify_step(Path(lvm_part_dev).exists() if not DRY_RUN_MODE else True, f"LVM partition {lvm_part_dev} exists", critical=True): all_ok = False
    if not verify_step(lv_root_path.exists() if not DRY_RUN_MODE else True, f"Root LV {lv_root_path} exists", critical=True): all_ok = False
    if float(USER_CONFIG['swap_size_gb']) > 0:
        lv_swap_path = Path(f"/dev/{USER_CONFIG['lvm_vg_name']}/{USER_CONFIG['lvm_lv_swap_name']}")
        if not verify_step(lv_swap_path.exists() if not DRY_RUN_MODE else True, f"Swap LV {lv_swap_path} exists", critical=True): all_ok = False
    def check_fstype(device, expected_fstype):
        if DRY_RUN_MODE: return True
        if not Path(device).exists(): print_color(f"Device {device} not found for fstype check.", Colors.ORANGE, prefix=WARNING_SYMBOL); return False
        proc = run_command(["lsblk", "-fno", "FSTYPE", device], capture_output=True, destructive=False, show_spinner=False, check=False)
        return proc and proc.returncode == 0 and expected_fstype in proc.stdout.strip()
    if not verify_step(check_fstype(efi_part_dev, "vfat"), f"EFI partition {efi_part_dev} has FSTYPE vfat", critical=True): all_ok = False
    if not verify_step(check_fstype(str(lv_root_path), "btrfs"), f"Root LV {lv_root_path.name} has FSTYPE btrfs", critical=True): all_ok = False
    if float(USER_CONFIG['swap_size_gb']) > 0:
        lv_swap_path_str = f"/dev/{USER_CONFIG['lvm_vg_name']}/{USER_CONFIG['lvm_lv_swap_name']}"
        if not verify_step(check_fstype(lv_swap_path_str, "swap"), f"Swap LV {USER_CONFIG['lvm_lv_swap_name']} has FSTYPE swap", critical=True): all_ok = False
    if all_ok: print_color("Partition and LVM verification successful.", Colors.GREEN, prefix=SUCCESS_SYMBOL)
    else: print_color("One or more partition/LVM verifications failed.", Colors.RED, prefix=ERROR_SYMBOL)
    print("")
def mount_filesystems():
    global CURRENT_STEP; print_section_header("Mounting Filesystems")
    if CURRENT_STEP > INSTALL_STEPS.index("mount_filesystems"): print_step_info("Skipping (already completed)"); print(""); return
    mnt_base = Path("/mnt"); lv_root_path_str = f"/dev/{USER_CONFIG['lvm_vg_name']}/{USER_CONFIG['lvm_lv_root_name']}"
    sfx = "p1" if "nvme" in USER_CONFIG['target_drive'] or "loop" in USER_CONFIG['target_drive'] else "1"
    efi_part_path_str = f"{USER_CONFIG['target_drive']}{sfx}"; btrfs_mount_opts = USER_CONFIG["btrfs_mount_options"]
    print_step_info(f"Mounting Btrfs ROOT subvolume '{USER_CONFIG['btrfs_subvol_root']}' to {mnt_base}..."); run_command(["mount", "-o", f"subvol=/{USER_CONFIG['btrfs_subvol_root']},{btrfs_mount_opts}", lv_root_path_str, str(mnt_base)], check=True)
    print_step_info("Creating standard mount point directories under /mnt...")
    for subdir in ["boot", "boot/efi", "home", "var", ".snapshots"]: make_dir_dry_run(mnt_base / subdir, exist_ok=True)
    print_step_info(f"Mounting Btrfs HOME subvolume '{USER_CONFIG['btrfs_subvol_home']}' to {mnt_base / 'home'}..."); run_command(["mount", "-o", f"subvol=/{USER_CONFIG['btrfs_subvol_home']},{btrfs_mount_opts}", lv_root_path_str, str(mnt_base / "home")], check=True)
    print_step_info(f"Mounting Btrfs VAR subvolume '{USER_CONFIG['btrfs_subvol_var']}' to {mnt_base / 'var'}..."); run_command(["mount", "-o", f"subvol=/{USER_CONFIG['btrfs_subvol_var']},{btrfs_mount_opts}", lv_root_path_str, str(mnt_base / "var")], check=True)
    print_step_info(f"Mounting EFI partition {efi_part_path_str} to {mnt_base / 'boot/efi'}..."); run_command(["mount", efi_part_path_str, str(mnt_base / "boot/efi")], check=True)
    if float(USER_CONFIG['swap_size_gb']) > 0:
        lv_swap_path_str = f"/dev/{USER_CONFIG['lvm_vg_name']}/{USER_CONFIG['lvm_lv_swap_name']}"; print_step_info(f"Activating SWAP on {lv_swap_path_str}..."); run_command(["swapon", lv_swap_path_str], check=True)
    print_color("Filesystems mounted.", Colors.GREEN, prefix=SUCCESS_SYMBOL); CURRENT_STEP = INSTALL_STEPS.index("pacstrap_system"); save_progress(); print("")
def verify_mounts(no_verify_arg: bool):
    if no_verify_arg: print_step_info("Skipping mount verification as per --no-verify."); print(""); return
    print_section_header("Verifying Mounts"); all_ok = True
    mnt_base_str = str(Path("/mnt")); btrfs_base_device = f"/dev/mapper/{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_root_name']}"
    sfx = "p1" if "nvme" in USER_CONFIG['target_drive'] or "loop" in USER_CONFIG['target_drive'] else "1"; efi_device_path = f"{USER_CONFIG['target_drive']}{sfx}"
    expected_mounts = [
        {"target": mnt_base_str, "source_pattern": btrfs_base_device, "fstype": "btrfs", "options_substring": f"subvol=/{USER_CONFIG['btrfs_subvol_root']}"},
        {"target": f"{mnt_base_str}/home", "source_pattern": btrfs_base_device, "fstype": "btrfs", "options_substring": f"subvol=/{USER_CONFIG['btrfs_subvol_home']}"},
        {"target": f"{mnt_base_str}/var", "source_pattern": btrfs_base_device, "fstype": "btrfs", "options_substring": f"subvol=/{USER_CONFIG['btrfs_subvol_var']}"},
        {"target": f"{mnt_base_str}/boot/efi", "source_pattern": efi_device_path, "fstype": "vfat", "options_substring": None}, ]
    findmnt_proc = run_command(["findmnt", "--real", "--noheadings", "--output=TARGET,SOURCE,FSTYPE,OPTIONS"], capture_output=True, destructive=False, show_spinner=False, check=False) 
    
    if not (findmnt_proc and findmnt_proc.returncode == 0 and findmnt_proc.stdout):
        print_color("Could not get mount information using findmnt.", Colors.RED, prefix=ERROR_SYMBOL)
        if findmnt_proc: 
            print_color(f"findmnt stderr: {findmnt_proc.stderr.strip() if findmnt_proc.stderr else 'N/A'}", Colors.ORANGE)
        all_ok = False
    else:
        print_color("Raw findmnt output:", Colors.MAGENTA, bold=True)
        print(findmnt_proc.stdout.strip())
        print_color("--- End of raw findmnt output ---", Colors.MAGENTA, bold=True)

        mounted_filesystems = {}
        for line in findmnt_proc.stdout.strip().split('\n'):
            if not line.strip(): continue 
            parts = line.split(maxsplit=3)
            if len(parts) >= 1:
                target_path = parts[0].lstrip('├─└─│ ').strip() # Strip tree characters and any leading/trailing whitespace
                source_val = parts[1] if len(parts) > 1 else ""
                fstype_val = parts[2] if len(parts) > 2 else ""
                options_val = parts[3] if len(parts) > 3 else ""
                mounted_filesystems[target_path] = {"source": source_val, "fstype": fstype_val, "options": options_val}
            else:
                print_color(f"Warning: Skipping malformed or unexpectedly short findmnt line: '{line}'", Colors.ORANGE)
        
        print_color("Parsed mounted_filesystems dictionary:", Colors.MAGENTA, bold=True)
        for t_key, t_val in mounted_filesystems.items():
            print(f"  '{t_key}': {t_val}")
        print_color("--- End of parsed mounted_filesystems dictionary ---", Colors.MAGENTA, bold=True)
        for expected in expected_mounts:
            target = expected["target"]
            is_mounted = target in mounted_filesystems
            
            if not verify_step(is_mounted, f"Mount point {target} is mounted", critical=True):
                all_ok = False
                if not DRY_RUN_MODE: 
                    print_color("Current mounts from 'findmnt -A --real':", Colors.ORANGE) 
                    run_command(["findmnt", "-A", "--real"], destructive=False, show_spinner=False, check=False, capture_output=False) 
                continue 
            
            if is_mounted: 
                actual = mounted_filesystems[target]
                source_ok = expected["source_pattern"] in actual["source"]
                if not verify_step(source_ok, f"{target} source contains '{expected['source_pattern']}' (actual: {actual['source']})", critical=True): all_ok = False
                
                fstype_ok = expected["fstype"] == actual["fstype"]
                if not verify_step(fstype_ok, f"{target} FSTYPE is '{expected['fstype']}' (actual: {actual['fstype']})", critical=True): all_ok = False
                
                if expected["options_substring"]:
                    expected_opt_to_check = expected["options_substring"]
                    options_ok = expected_opt_to_check in actual["options"]
                    if not verify_step(options_ok, f"{target} options contain '{expected_opt_to_check}' (actual: {actual['options']})", critical=True): all_ok = False
    if float(USER_CONFIG['swap_size_gb']) > 0:
        lv_swap_path_str = f"/dev/mapper/{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_swap_name']}"
        swap_check_proc = run_command(["swapon", "--show=NAME"], capture_output=True, destructive=False, show_spinner=False, check=False)
        swap_active = swap_check_proc and swap_check_proc.returncode == 0 and lv_swap_path_str in swap_check_proc.stdout
        if not verify_step(swap_active, f"Swap on {lv_swap_path_str} is active", critical=True): all_ok = False
    if all_ok: print_color("Mount verification successful.", Colors.GREEN, prefix=SUCCESS_SYMBOL)
    else: print_color("One or more mount verifications failed.", Colors.RED, prefix=ERROR_SYMBOL)
    print("")
def pacstrap_system():
    global CURRENT_STEP; print_section_header("Installing Base System (pacstrap)")
    if CURRENT_STEP > INSTALL_STEPS.index("pacstrap_system"): print_step_info("Skipping (already completed)"); print(""); return
    pkgs_to_install = [ "base", "base-devel", "linux-surface", "linux-surface-headers", "systemd", "efibootmgr", "dracut", "intel-ucode", "lvm2", "btrfs-progs", "gdm", "gnome-shell", "gnome-session", "gnome-control-center", "nautilus", "gnome-terminal", "xdg-desktop-portal-gnome", "gnome-keyring", "seahorse", "neovim", "networkmanager", "openssh", "bluez", "bluez-utils", "gnupg", "pipewire", "pipewire-pulse", "pipewire-alsa", "wireplumber", "noto-fonts", "noto-fonts-cjk", "noto-fonts-emoji", USER_CONFIG["default_monospace_font_pkg"], "linux-firmware", "sof-firmware", "zram-generator", "curl", "sudo", "git", "go" ]
    run_command(["pacstrap", "/mnt"] + pkgs_to_install, destructive=True, retry_count=2, retry_delay=10.0, custom_spinner_message="Pacstrapping base system and packages")
    if not DRY_RUN_MODE:
        print_step_info("Debug: Listing /mnt/boot/ contents immediately after pacstrap...")
        ls_boot_proc = run_command(["ls", "-Alh", "/mnt/boot"], capture_output=True, destructive=False, show_spinner=False, check=False)
        if ls_boot_proc and ls_boot_proc.stdout: print_color(f"/mnt/boot/ contents:\n{ls_boot_proc.stdout.strip()}", Colors.MINT)
        else: print_color("Could not list /mnt/boot/ contents or it is empty (after pacstrap).", Colors.ORANGE)
    print_color("Base system installation complete.", Colors.GREEN, prefix=SUCCESS_SYMBOL); CURRENT_STEP = INSTALL_STEPS.index("generate_fstab"); save_progress(); print("")
def verify_pacstrap(no_verify_arg: bool):
    if no_verify_arg: print_step_info("Skipping pacstrap verification as per --no-verify."); print(""); return
    print_section_header("Verifying Pacstrap Installation"); all_ok = True
    def check_key_dirs():
        if DRY_RUN_MODE: return True
        mnt = Path("/mnt"); key_dirs = [mnt / "bin", mnt / "etc", mnt / "usr", mnt / "boot"] 
        return all(d.is_dir() for d in key_dirs)
    def check_package_installed(pkg_name: str) -> bool:
        if DRY_RUN_MODE: print_color(f"[DRY RUN] Assuming '{pkg_name}' package would be installed.", Colors.PEACH); return True
        print_step_info(f"Verifying '{pkg_name}' package installation via arch-chroot...")
        proc = run_command(["arch-chroot", "/mnt", "pacman", "-Q", pkg_name], capture_output=True, destructive=False, show_spinner=False, check=False)
        if proc and proc.returncode == 0: print_color(f"'{pkg_name}' package IS installed: {proc.stdout.strip()}", Colors.GREEN, prefix=SUCCESS_SYMBOL); return True
        else:
            stderr = proc.stderr.strip() if proc and proc.stderr else "Unknown error"
            print_color(f"CRITICAL: '{pkg_name}' package NOT FOUND after pacstrap. pacman -Q stderr: {stderr}", Colors.RED, prefix=ERROR_SYMBOL, bold=True); return False
    if not verify_step(check_key_dirs(), "Key directories exist after pacstrap", critical=True): all_ok = False
    if not verify_step(check_package_installed("linux-surface"), "'linux-surface' package is installed", critical=True): all_ok = False
    if not verify_step(check_package_installed("dracut"), "'dracut' package is installed", critical=True): all_ok = False
    if all_ok: print_color("Pacstrap verification successful.", Colors.GREEN, prefix=SUCCESS_SYMBOL)
    else: print_color("One or more pacstrap verifications failed.", Colors.RED, prefix=ERROR_SYMBOL)
    print("")

def generate_fstab():
    global CURRENT_STEP
    print_section_header("Generating fstab")
    if CURRENT_STEP > INSTALL_STEPS.index("generate_fstab"): print_step_info("Skipping (already completed)"); print(""); return
    
    fstab_path = Path("/mnt/etc/fstab")
    run_command(f"genfstab -U /mnt >> {fstab_path}", shell=True, destructive=True, check=True) 
    print_color(f"fstab generated at {fstab_path}", Colors.MINT)

    # Verification for fstab
    root_line_found_and_correct = False
    if DRY_RUN_MODE:
        root_line_found_and_correct = True 
    elif fstab_path.exists() and fstab_path.stat().st_size > 0:
        content = fstab_path.read_text()
        root_lv_mapper_path = f"/dev/mapper/{USER_CONFIG['lvm_vg_name']}-{USER_CONFIG['lvm_lv_root_name']}"
        
        for line_idx, line_content in enumerate(content.splitlines()):
            line = line_content.strip()
            if line.startswith("#") or not line:
                continue
            
            parts = line.split()
            # For genfstab -U, parts[0] is UUID. We identify root by mount point and type.
            if len(parts) >= 4 and parts[1] == "/" and "btrfs" in parts[2]:
                actual_options_str = parts[3]
                actual_options_list = [opt.strip() for opt in actual_options_str.split(',')]
                
                all_config_options_present = True
                expected_btrfs_options_from_config = USER_CONFIG["btrfs_mount_options"].split(',')
                for expected_opt_part in expected_btrfs_options_from_config:
                    base_expected_opt = expected_opt_part.split('=')[0]
                    if not any(actual_opt.startswith(base_expected_opt) for actual_opt in actual_options_list):
                        all_config_options_present = False
                        print_color(f"fstab line {line_idx+1}: Expected BTRFS option component '{base_expected_opt}' (from '{expected_opt_part}') not found in actual options: '{actual_options_str}'", Colors.ORANGE, prefix=WARNING_SYMBOL)
                        break 
                
                expected_subvol_opt_str = f"subvol=/{USER_CONFIG['btrfs_subvol_root']}"
                subvol_option_present = expected_subvol_opt_str in actual_options_list 
                if not subvol_option_present:
                     print_color(f"fstab line {line_idx+1}: Expected BTRFS subvolume option '{expected_subvol_opt_str}' not found in actual options: '{actual_options_str}'", Colors.ORANGE, prefix=WARNING_SYMBOL)

                if all_config_options_present and subvol_option_present:
                    root_line_found_and_correct = True
                    break 

        if not root_line_found_and_correct:
            print_color(f"Root Btrfs entry in fstab was not found or seems incorrect/missing required options.", Colors.ORANGE, prefix=WARNING_SYMBOL)
            print_color(f"Expected base options from config to be present: {USER_CONFIG['btrfs_mount_options']}", Colors.PEACH)
            print_color(f"Expected subvolume for root: subvol=/{USER_CONFIG['btrfs_subvol_root']}", Colors.PEACH)
            print_color("Actual fstab content:", Colors.PEACH)
            print(content)
            
    verify_step(root_line_found_and_correct, "fstab content for root mount appears correct", critical=True)
    
    print_color("fstab generation and basic check complete.", Colors.GREEN, prefix=SUCCESS_SYMBOL)
    CURRENT_STEP = INSTALL_STEPS.index("pre_chroot_files")
    save_progress()
    print("")

def pre_chroot_file_configurations():
    global CURRENT_STEP
    print_section_header("Pre-Chroot File Configurations")
    if CURRENT_STEP > INSTALL_STEPS.index("pre_chroot_files"): print_step_info("Skipping (already completed)"); print(""); return

    mnt_base = Path("/mnt")
    config = USER_CONFIG

    write_file_dry_run(mnt_base / "etc/locale.gen", f"{config['locale_gen']}\n")
    write_file_dry_run(mnt_base / "etc/locale.conf", f"LANG={config['locale_lang']}\n")
    write_file_dry_run(mnt_base / "etc/vconsole.conf", f"KEYMAP={config['vconsole_keymap']}\n")
    write_file_dry_run(mnt_base / "etc/hostname", f"{config['hostname']}\n")
    hosts_content = f"127.0.0.1 localhost\n::1       localhost\n127.0.1.1 {config['hostname']}.localdomain {config['hostname']}\n"
    write_file_dry_run(mnt_base / "etc/hosts", hosts_content)
    editor_script_content = 'export EDITOR="nvim"\nexport VISUAL="nvim"\n'
    editor_script_path = mnt_base / "etc/profile.d/editor.sh"
    write_file_dry_run(editor_script_path, editor_script_content)
    if not DRY_RUN_MODE: os.chmod(editor_script_path, 0o755)
    loader_conf_content = "default arch-*\ntimeout 3\nconsole-mode max\neditor no\n"
    boot_efi_loader_path = mnt_base / "boot/efi/loader"; make_dir_dry_run(boot_efi_loader_path, parents=True, exist_ok=True)
    write_file_dry_run(boot_efi_loader_path / "loader.conf", loader_conf_content)
    gdm_conf_dir = mnt_base / "etc/gdm"; make_dir_dry_run(gdm_conf_dir, parents=True, exist_ok=True)
    gdm_custom_conf_content = f"[daemon]\nAutomaticLoginEnable=True\nAutomaticLogin={config['username']}\n"
    write_file_dry_run(gdm_conf_dir / "custom.conf", gdm_custom_conf_content)
    pacman_conf_path = mnt_base / "etc/pacman.conf"
    if not DRY_RUN_MODE and pacman_conf_path.exists():
        try:
            content = pacman_conf_path.read_text()
            if "#Color" in content: pacman_conf_path.write_text(content.replace("#Color", "Color"))
        except Exception as e: print_color(f"Error modifying {pacman_conf_path} for Color: {e}", Colors.ORANGE)
    makepkg_conf_path = mnt_base / "etc/makepkg.conf"
    if not DRY_RUN_MODE and makepkg_conf_path.exists():
        try:
            content = makepkg_conf_path.read_text()
            content = content.replace("-march=x86-64", f"-march={config['cpu_march']}")
            content = content.replace("CFLAGS=\"-march=native", f"CFLAGS=\"-march={config['cpu_march']}")
            if "-O2" not in content: content = content.replace("CFLAGS=\"", "CFLAGS=\"-O2 ") 
            if "-pipe" not in content: content = content.replace("CFLAGS=\"", "CFLAGS=\"-pipe ") 
            content = content.replace("#CXXFLAGS=\"${CFLAGS}\"", "CXXFLAGS=\"${CFLAGS}\"")
            makepkg_conf_path.write_text(content)
        except Exception as e: print_color(f"Error modifying {makepkg_conf_path} for CPU opts: {e}", Colors.ORANGE)
    zram_conf_content = f"[zram0]\nzram-fraction = {config['zram_fraction']}\ncompression-algorithm = zstd\n"
    zram_conf_path_dir = mnt_base / "etc/systemd"; make_dir_dry_run(zram_conf_path_dir, parents=True, exist_ok=True)
    write_file_dry_run(zram_conf_path_dir / "zram-generator.conf", zram_conf_content)
    dconf_profile_dir = mnt_base / "etc/dconf/profile"; make_dir_dry_run(dconf_profile_dir, parents=True, exist_ok=True)
    dconf_db_locald_dir = mnt_base / "etc/dconf/db/local.d"; make_dir_dry_run(dconf_db_locald_dir, parents=True, exist_ok=True)
    make_dir_dry_run(mnt_base / "etc/dconf/db/locks", parents=True, exist_ok=True)
    write_file_dry_run(dconf_profile_dir / "user", "user-db:user\nsystem-db:local\n")
    write_file_dry_run(dconf_db_locald_dir / "00-hidpi-fractional-scaling", "[org/gnome/mutter]\nexperimental-features=['scale-monitor-framebuffer']\n")
    sudoers_path = mnt_base / "etc/sudoers"
    if not DRY_RUN_MODE and sudoers_path.exists():
        try:
            content = sudoers_path.read_text()
            if "# %wheel ALL=(ALL:ALL) ALL" in content: sudoers_path.write_text(content.replace("# %wheel ALL=(ALL:ALL) ALL", "%wheel ALL=(ALL:ALL) ALL"))
        except Exception as e: print_color(f"Error modifying {sudoers_path}: {e}", Colors.ORANGE)
    
    print_color("Pre-chroot file configurations complete.", Colors.GREEN, prefix=SUCCESS_SYMBOL)
    CURRENT_STEP = INSTALL_STEPS.index("chroot_configure")
    save_progress()
    print("")

def _generate_and_write_chroot_script_content() -> Path:
    path_setup_bash_profile = '''
if ! grep -q '$HOME/.local/bin' "$PROFILE_TARGET" >/dev/null 2>&1 && [ -f "$PROFILE_TARGET" ]; then
  echo -e "\\n# Add .local/bin to PATH\\nif [ -d \\"$HOME/.local/bin\\" ] ; then\\n  PATH=\\"$HOME/.local/bin:$PATH\\"\\nfi" >> "$PROFILE_TARGET"
elif [ ! -f "$PROFILE_TARGET" ]; then 
    if [ -f "$BASHRC" ]; then 
        echo -e "# ~/.bash_profile\\nif [ -f ~/.bashrc ]; then . ~/.bashrc; fi\\nif [ -d \\"$HOME/.local/bin\\" ] ; then PATH=\\"$HOME/.local/bin:$PATH\\"; fi" > "$PROFILE_TARGET"
    else 
        echo -e "# ~/.profile\\nif [ -d \\"$HOME/.local/bin\\" ] ; then PATH=\\"$HOME/.local/bin:$PATH\\"; fi" > "$PROFILE_TARGET"
    fi
    chown __SETUP_USERNAME__:__SETUP_USERNAME__ "$PROFILE_TARGET"
fi
'''
    # IMPORTANT: All placeholders are now __SETUP_VARNAME__
    chroot_script_content = f'''#!/bin/bash
set -e 
echo -e "{Colors.PURPLE}--- CHROOT SCRIPT: Configuring System (inside chroot) ---{Colors.RESET}"

echo -e "{Colors.BLUE}Setting timezone to __SETUP_TIMEZONE__...{Colors.RESET}"
ln -sf "/usr/share/zoneinfo/__SETUP_TIMEZONE__" /etc/localtime
hwclock --systohc

echo -e "{Colors.BLUE}Generating locales (locale.gen and locale.conf configured pre-chroot)...{Colors.RESET}"
locale-gen

echo -e "{Colors.BLUE}Setting root password and locking root account...{Colors.RESET}"
echo "root:__SETUP_ROOT_PASSWORD__" | chpasswd -e || echo "root:__SETUP_ROOT_PASSWORD__" | chpasswd
passwd -l root 

echo -e "{Colors.BLUE}Creating user __SETUP_USERNAME__...{Colors.RESET}"
useradd -m -G wheel -s /bin/bash "__SETUP_USERNAME__"
echo "__SETUP_USERNAME__:__SETUP_BAO_PASSWORD__" | chpasswd -e || echo "__SETUP_USERNAME__:__SETUP_BAO_PASSWORD__" | chpasswd

echo -e "{Colors.BLUE}Configuring systemd-boot (loader.conf configured pre-chroot)...{Colors.RESET}"
bootctl --path=/boot/efi install

ROOT_PART_UUID=\$(findmnt -n -o UUID -T /)
if [ -z "\$ROOT_PART_UUID" ]; then echo -e "{Colors.RED}ERROR: No ROOT_PART_UUID{Colors.RESET}"; exit 1; fi

cat << EOF_ARCH_ENTRY > /boot/efi/loader/entries/arch-surface.conf
title   Arch Linux (Surface - GNOME)
linux   /vmlinuz-linux-surface
initrd  /intel-ucode.img
initrd  /initramfs-linux-surface.img
options root=UUID=\$ROOT_PART_UUID rootflags=subvol=/__SETUP_BTRFS_SUBVOL_ROOT__ rw quiet splash mitigations=off
EOF_ARCH_ENTRY

echo -e "{Colors.BLUE}Preparing for initramfs generation...{Colors.RESET}"

# Hardcoded kernel module directory name for linux-surface
KERNEL_MODULE_DIR_NAME="6.14.2.arch1-1-surface"
echo -e "{Colors.CYAN}Using KERNEL_MODULE_DIR_NAME: \$KERNEL_MODULE_DIR_NAME (hardcoded){Colors.RESET}"

KERNEL_MODULES_PATH="/usr/lib/modules/\$KERNEL_MODULE_DIR_NAME"
BOOT_VMLINUZ_TARGET_NAME="vmlinuz-linux-surface" 
BOOT_KERNEL_TARGET_PATH="/boot/\$BOOT_VMLINUZ_TARGET_NAME" 
KERNEL_IMAGE_SRC_IN_MODULES="\$KERNEL_MODULES_PATH/vmlinuz" 

if [ ! -d "\$KERNEL_MODULES_PATH" ]; then
    echo -e "{Colors.RED}CRITICAL ERROR: Kernel modules directory \$KERNEL_MODULES_PATH does NOT exist!{Colors.RESET}"
    echo -e "{Colors.RED}This indicates a severe issue with the 'linux-surface' package installation or that the hardcoded KERNEL_MODULE_DIR_NAME is incorrect.{Colors.RESET}"
    ls -Alh /usr/lib/modules/ || echo -e "{Colors.ORANGE}Could not list /usr/lib/modules/{Colors.RESET}"
    exit 1
fi
echo -e "{Colors.GREEN}Kernel modules directory \$KERNEL_MODULES_PATH found.{Colors.RESET}"

if [ ! -f "\$BOOT_KERNEL_TARGET_PATH" ]; then
    echo -e "{Colors.YELLOW}Kernel image \$BOOT_KERNEL_TARGET_PATH not found directly in /boot.{Colors.RESET}"
    if [ -f "\$KERNEL_IMAGE_SRC_IN_MODULES" ]; then
        echo -e "{Colors.MINT}Found kernel image at \$KERNEL_IMAGE_SRC_IN_MODULES. Copying to \$BOOT_KERNEL_TARGET_PATH...{Colors.RESET}"
        cp -v "\$KERNEL_IMAGE_SRC_IN_MODULES" "\$BOOT_KERNEL_TARGET_PATH"
    else
        echo -e "{Colors.RED}ERROR: Kernel image \$KERNEL_IMAGE_SRC_IN_MODULES not found within \$KERNEL_MODULES_PATH.{Colors.RESET}"
        echo -e "{Colors.CYAN}Listing contents of \$KERNEL_MODULES_PATH for diagnostics:{Colors.RESET}"
        ls -Alh "\$KERNEL_MODULES_PATH" || echo -e "{Colors.ORANGE}Could not list \$KERNEL_MODULES_PATH{Colors.RESET}"
        exit 1
    fi
else
    echo -e "{Colors.GREEN}Kernel image \$BOOT_KERNEL_TARGET_PATH already present in /boot.{Colors.RESET}"
fi

if [ ! -f "\$BOOT_KERNEL_TARGET_PATH" ]; then
    echo -e "{Colors.RED}CRITICAL ERROR: Kernel image \$BOOT_KERNEL_TARGET_PATH is still not found in /boot after copy attempt. Cannot proceed.{Colors.RESET}"; exit 1
fi
echo -e "{Colors.GREEN}Kernel image \$BOOT_KERNEL_TARGET_PATH is ready in /boot.{Colors.RESET}"

echo -e "{Colors.BLUE}Generating initramfs with dracut for kernel modules version \$KERNEL_MODULE_DIR_NAME...{Colors.RESET}"
dracut --force --hostonly --no-hostonly-cmdline --kver "\$KERNEL_MODULE_DIR_NAME" "/boot/initramfs-linux-surface.img"

echo -e "{Colors.BLUE}Enabling system services (GDM, NetworkManager, WirePlumber, Bluetooth, ZRAM)...{Colors.RESET}"
systemctl enable gdm.service NetworkManager.service wireplumber.service bluetooth.service systemd-zram-setup@zram0.service

echo -e "{Colors.BLUE}Configuring Chaotic-AUR in /etc/pacman.conf (Color and makepkg.conf configured pre-chroot)...{Colors.RESET}"
if [ "__SETUP_ADD_CHAOTIC_AUR__" = "true" ]; then
  if ! grep -q "\\[chaotic-aur\\]" /etc/pacman.conf; then
    pacman-key --recv-key 3056513887B78AEB --keyserver keyserver.ubuntu.com
    pacman-key --lsign-key 3056513887B78AEB
    pacman -U --noconfirm https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst
    echo -e "\\n[chaotic-aur]\\nInclude = /etc/pacman.d/chaotic-mirrorlist" >> /etc/pacman.conf
    pacman -Sy 
  fi
fi

echo -e "{Colors.BLUE}Applying system-wide dconf settings (files configured pre-chroot)...{Colors.RESET}"
dconf update

USER_HOME="/home/__SETUP_USERNAME__"
mkdir -p "$USER_HOME/.local/bin" "$USER_HOME/.config"
chown -R __SETUP_USERNAME__:__SETUP_USERNAME__ "$USER_HOME"

echo -e "{Colors.BLUE}Ensuring .local/bin is in PATH for user __SETUP_USERNAME__ (bash)...{Colors.RESET}"
PROFILE_TARGET="$USER_HOME/.bash_profile"
BASHRC="$USER_HOME/.bashrc"
{path_setup_bash_profile}

echo -e "{Colors.BLUE}Running AUR installs and key generation as user __SETUP_USERNAME__...{Colors.RESET}"
runuser -l "__SETUP_USERNAME__" -c '
    set -e
    echo -e "{Colors.CYAN}--- Running as user __SETUP_USERNAME__ for AUR and Keys ---{Colors.RESET}"
    export PATH="$HOME/.local/bin:$PATH" 
    
    echo -e "{Colors.LIGHT_BLUE}>>> Installing yay (AUR helper)...{Colors.RESET}"
    if ! command -v yay &> /dev/null; then
        cd /tmp || exit 1
        git clone https://aur.archlinux.org/yay-bin.git && cd yay-bin && makepkg -si --noconfirm && cd / && rm -rf /tmp/yay-bin || {{ echo -e "{Colors.RED}Failed to install yay{Colors.RESET}"; exit 1; }}
    else echo -e "{Colors.MINT}yay already installed.{Colors.RESET}"; fi

    echo -e "{Colors.LIGHT_BLUE}>>> Installing AUR packages (VS Code, Google Chrome, Surface Utilities)...{Colors.RESET}"
    yay -S --noconfirm --needed visual-studio-code-bin google-chrome libwacom-surface surface-control-bin || echo -e "{Colors.ORANGE}Warning: Some AUR packages failed to install.{Colors.RESET}"
    
    echo -e "{Colors.LIGHT_BLUE}>>> Generating SSH key for __SETUP_SSH_KEY_EMAIL__...{Colors.RESET}"
    mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
    if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
        ssh-keygen -t ed25519 -C "__SETUP_SSH_KEY_EMAIL__" -N "" -f "$HOME/.ssh/id_ed25519" || echo -e "{Colors.ORANGE}SSH keygen failed.{Colors.RESET}"
    else echo -e "{Colors.MINT}SSH key already exists.{Colors.RESET}"; fi

    echo -e "{Colors.LIGHT_BLUE}>>> Attempting GPG key generation for __SETUP_GPG_KEY_NAME__ <__SETUP_GPG_KEY_EMAIL__>...{Colors.RESET}"
    mkdir -p "$HOME/.gnupg" && chmod 700 "$HOME/.gnupg"
    GPG_BATCH_CMDS_USER=$(cat <<GPG_USER_EOF
%echo Generating GPG key for user...
Key-Type: RSA; Key-Length: 4096; Subkey-Type: RSA; Subkey-Length: 4096
Name-Real: __SETUP_GPG_KEY_NAME__; Name-Email: __SETUP_GPG_KEY_EMAIL__
Expire-Date: 0; Passphrase: __SETUP_BAO_PASSWORD__; %commit; %echo done
GPG_USER_EOF
)
    if ! gpg --list-keys "__SETUP_GPG_KEY_EMAIL__" > /dev/null 2>&1; then
        echo "$GPG_BATCH_CMDS_USER" | gpg --batch --pinentry-mode loopback --yes --generate-key > /tmp/gpg_gen_user.log 2>&1 || echo -e "{Colors.ORANGE}GPG batch command execution had issues.{Colors.RESET}"
        cat /tmp/gpg_gen_user.log; rm -f /tmp/gpg_gen_user.log
        if ! gpg --list-keys "__SETUP_GPG_KEY_EMAIL__" > /dev/null 2>&1; then echo -e "{Colors.ORANGE}WARNING: GPG key for __SETUP_GPG_KEY_EMAIL__ may not have been created.{Colors.RESET}"; fi
    else echo -e "{Colors.MINT}GPG key for __SETUP_GPG_KEY_EMAIL__ already exists.{Colors.RESET}"; fi
    echo -e "{Colors.CYAN}--- User-specific setup finished ---{Colors.RESET}"
' || echo -e "{Colors.RED}ERROR: User-specific setup script failed for __SETUP_USERNAME__{Colors.RESET}"

echo -e "{Colors.BLUE}Performing final system update as root...{Colors.RESET}"
pacman -Syu --noconfirm

echo -e "{Colors.PURPLE}--- CHROOT SCRIPT: Configuration complete. ---{Colors.RESET}"
'''
    # Substitute USER_CONFIG and passwords
    final_script = chroot_script_content
    for key, value in USER_CONFIG.items():
        template_var = f"__SETUP_{key.upper()}__" 
        
        str_value = str(value)
        if isinstance(value, bool):
            str_value = str_value.lower() 
        
        final_script = final_script.replace(template_var, str_value)

    final_script = final_script.replace("__SETUP_BAO_PASSWORD__", BAO_PASSWORD)
    final_script = final_script.replace("__SETUP_ROOT_PASSWORD__", ROOT_PASSWORD)

    chroot_script_target_path_mounted = Path("/mnt/chroot_script.sh")
    write_file_dry_run(chroot_script_target_path_mounted, final_script)
    if not DRY_RUN_MODE:
        run_command(["chmod", "+x", str(chroot_script_target_path_mounted)], destructive=False)
    return chroot_script_target_path_mounted.relative_to("/mnt")

def chroot_configure_system():
    global CURRENT_STEP
    print_section_header("Configuring System (chroot)")
    if CURRENT_STEP > INSTALL_STEPS.index("chroot_configure"): print_step_info("Skipping (already completed)"); print(""); return

    relative_chroot_script_path = _generate_and_write_chroot_script_content()
    print_step_info(f"Executing generated chroot script: /{relative_chroot_script_path}")
    
    run_command(["arch-chroot", "/mnt", "/bin/bash", f"/{relative_chroot_script_path}"], destructive=True, retry_count=1)
    
    unlink_file_dry_run(Path("/mnt") / relative_chroot_script_path) 
    print_color("System configuration in chroot complete.", Colors.GREEN, prefix=SUCCESS_SYMBOL)
    CURRENT_STEP = INSTALL_STEPS.index("cleanup")
    save_progress()
    print("")

def verify_chroot_configs(no_verify_arg: bool):
    if no_verify_arg: print_step_info("Skipping chroot configuration verification as per --no-verify."); print(""); return
    print_section_header("Verifying Chroot Configuration")
    all_ok = True
    
    def check_file_content(path_in_mnt: str, expected_content_part: str, check_name: str, critical=False) -> bool:
        if DRY_RUN_MODE: print_color(f"[DRY RUN] Assuming {check_name} at {path_in_mnt} would be correct.", Colors.PEACH); return True
        file_path = Path("/mnt") / path_in_mnt
        if not file_path.exists(): print_color(f"{check_name}: File {file_path} does not exist.", Colors.RED); return False
        try: content = file_path.read_text(); return expected_content_part in content
        except Exception as e: print_color(f"{check_name}: Error reading {file_path}: {e}", Colors.RED); return False

    if not verify_step(check_file_content("etc/hostname", USER_CONFIG["hostname"], "Hostname"), "Hostname configuration", critical=True): all_ok = False
    if not verify_step(check_file_content("etc/locale.conf", f"LANG={USER_CONFIG['locale_lang']}", "Locale config"), "Locale configuration", critical=True): all_ok = False
    if not verify_step((Path("/mnt/home") / USER_CONFIG["username"]).is_dir() if not DRY_RUN_MODE else True, f"User home directory /home/{USER_CONFIG['username']} exists", critical=True): all_ok = False
    if not verify_step(Path("/mnt/boot/efi/loader/entries/arch-surface.conf").exists() if not DRY_RUN_MODE else True, "Systemd-boot entry file exists", critical=True): all_ok = False
    
    kernel_img = Path("/mnt/boot/vmlinuz-linux-surface")
    initramfs_img = Path("/mnt/boot/initramfs-linux-surface.img")
    intel_ucode_img = Path("/mnt/boot/intel-ucode.img") 
    
    kernel_ok = kernel_img.is_file() if not DRY_RUN_MODE else True
    initramfs_ok = initramfs_img.is_file() if not DRY_RUN_MODE else True
    ucode_ok = intel_ucode_img.is_file() if not DRY_RUN_MODE else True

    if not verify_step(kernel_ok, f"Kernel image {kernel_img} exists", critical=True): all_ok = False
    if not verify_step(initramfs_ok, f"Initramfs image {initramfs_img} exists", critical=True): all_ok = False
    if not verify_step(ucode_ok, f"Intel ucode image {intel_ucode_img} exists", critical=False): 
        print_color(f"Intel ucode image {intel_ucode_img} missing. Bootloader entry might need adjustment if this is intended.", Colors.ORANGE, prefix=WARNING_SYMBOL)

    if not (kernel_ok and initramfs_ok) and not DRY_RUN_MODE: 
        run_command(["ls", "-Alh", "/mnt/boot"], capture_output=True, destructive=False, show_spinner=False) 

    if not verify_step(Path("/mnt/etc/dconf/db/local.d/00-hidpi-fractional-scaling").exists() if not DRY_RUN_MODE else True, "Dconf fractional scaling file exists", critical=False): all_ok = False
    if USER_CONFIG["add_chaotic_aur"]: 
        if not verify_step(Path("/mnt/usr/bin/yay").exists() if not DRY_RUN_MODE else True, "yay AUR helper installed in /usr/bin", critical=False): all_ok = False
    
    if all_ok: print_color("Chroot configuration verification successful.", Colors.GREEN, prefix=SUCCESS_SYMBOL)
    else: print_color("One or more chroot configuration verifications FAILED.", Colors.RED, prefix=ERROR_SYMBOL)
    print("")

# --- Main Execution ---
def parse_arguments():
    parser = argparse.ArgumentParser(description='Arch Linux Enhanced Installer')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry run mode')
    parser.add_argument('--step', type=int, choices=range(len(INSTALL_STEPS)), help=f'Start from specific step: {", ".join([f"{i}:{s}" for i,s in enumerate(INSTALL_STEPS)])}')
    parser.add_argument('--no-verify', action='store_true', help='Skip verification steps (NOT RECOMMENDED)')
    return parser.parse_args()

def main():
    global DRY_RUN_MODE, RESTART_STEP, CURRENT_STEP, USER_CONFIG
    args = parse_arguments()
    
    initial_restart_step = load_progress()

    if os.geteuid() != 0 and not args.dry_run: 
        print_color("Script must be run as root for actual installation.", Colors.RED, prefix=ERROR_SYMBOL, bold=True)
        if not prompt_yes_no("Run in DRY RUN mode instead?", default_yes=True): sys.exit(1)
        DRY_RUN_MODE = True 
    elif args.dry_run: DRY_RUN_MODE = True
    
    print_header("Arch Linux Enhanced Installer")
    if DRY_RUN_MODE: print_color("DRY RUN MODE ENABLED. No changes will be made.", Colors.YELLOW, bold=True, prefix=WARNING_SYMBOL)
    else: print_color("LIVE MODE ENABLED. Script WILL make changes to your system!", Colors.RED + Colors.BLINK, bold=True, prefix=ERROR_SYMBOL); print_color("Ensure you have BACKED UP any important data before proceeding.", Colors.ORANGE, bold=True, prefix=WARNING_SYMBOL)
    
    if args.step is not None: 
        RESTART_STEP = args.step
        print_color(f"Overriding progress. Starting from step {args.step} ({INSTALL_STEPS[args.step]}) as per command line.", Colors.CYAN, prefix=INFO_SYMBOL)
        if RESTART_STEP == 0 or not USER_CONFIG.get("target_drive"):
            print_color("Command line --step requires re-gathering config or target_drive is missing from loaded config.", Colors.CYAN)
            # Re-initialize USER_CONFIG to defaults if --step is forcing an early stage or config is bad
            base_config_defaults = { "username": "bao", "hostname": "bao", "timezone": "America/Denver", "locale_lang": "en_US.UTF-8", "locale_gen": "en_US.UTF-8 UTF-8", "vconsole_keymap": "us", "target_drive": "", "efi_partition_size": "1G", "swap_size_gb": "8", "zram_fraction": "0.5", "lvm_vg_name": "vg_bao", "lvm_lv_root_name": "lv_root", "lvm_lv_swap_name": "lv_swap", "btrfs_subvol_root": "@root", "btrfs_subvol_home": "@home", "btrfs_subvol_var": "@var", "btrfs_subvol_snapshots": "@snapshots", "ssh_key_email": "kunihir0@tutanota.com", "gpg_key_name": "kunihir0", "gpg_key_email": "kunihir0@tutanota.com", "cpu_march": "icelake-client", "add_chaotic_aur": True, "default_monospace_font_pkg": "ttf-sourcecodepro-nerd", "btrfs_mount_options": "compress=zstd,ssd,noatime,discard=async" }
            USER_CONFIG = base_config_defaults.copy() # Reset to full defaults
            CURRENT_STEP = 0 # Force gather_config if --step implies it or config is bad
    else:
        RESTART_STEP = initial_restart_step 

    CURRENT_STEP = RESTART_STEP

    if CURRENT_STEP > 0 and not USER_CONFIG.get("target_drive"):
        print_color("Target drive not configured from saved progress, critical for subsequent steps. Restarting from configuration.", Colors.ORANGE, prefix=WARNING_SYMBOL)
        CURRENT_STEP = 0 
        # Reset USER_CONFIG to ensure defaults are used if gather_initial_config is now skipped by logic but target_drive was missing
        base_config_defaults = { "username": "bao", "hostname": "bao", "timezone": "America/Denver", "locale_lang": "en_US.UTF-8", "locale_gen": "en_US.UTF-8 UTF-8", "vconsole_keymap": "us", "target_drive": "", "efi_partition_size": "1G", "swap_size_gb": "8", "zram_fraction": "0.5", "lvm_vg_name": "vg_bao", "lvm_lv_root_name": "lv_root", "lvm_lv_swap_name": "lv_swap", "btrfs_subvol_root": "@root", "btrfs_subvol_home": "@home", "btrfs_subvol_var": "@var", "btrfs_subvol_snapshots": "@snapshots", "ssh_key_email": "kunihir0@tutanota.com", "gpg_key_name": "kunihir0", "gpg_key_email": "kunihir0@tutanota.com", "cpu_march": "icelake-client", "add_chaotic_aur": True, "default_monospace_font_pkg": "ttf-sourcecodepro-nerd", "btrfs_mount_options": "compress=zstd,ssd,noatime,discard=async" }
        USER_CONFIG = base_config_defaults.copy()


    if CURRENT_STEP == 0: # Only ask this if we are truly starting from step 0
         if not prompt_yes_no("Ready to begin the configuration process?", default_yes=True): sys.exit(0)
    
    start_time = time.time()
    try:
        if CURRENT_STEP <= INSTALL_STEPS.index("gather_config"): gather_initial_config(); display_summary_and_confirm() 
        if CURRENT_STEP <= INSTALL_STEPS.index("prepare_environment"): prepare_live_environment() 
        if CURRENT_STEP <= INSTALL_STEPS.index("partition_format"): partition_and_format(); verify_partitions_lvm(args.no_verify)
        if CURRENT_STEP <= INSTALL_STEPS.index("mount_filesystems"): mount_filesystems(); verify_mounts(args.no_verify)
        if CURRENT_STEP <= INSTALL_STEPS.index("pacstrap_system"): pacstrap_system(); verify_pacstrap(args.no_verify)
        if CURRENT_STEP <= INSTALL_STEPS.index("generate_fstab"): generate_fstab() 
        if CURRENT_STEP <= INSTALL_STEPS.index("pre_chroot_files"): pre_chroot_file_configurations() 
        if CURRENT_STEP <= INSTALL_STEPS.index("chroot_configure"): chroot_configure_system(); verify_chroot_configs(args.no_verify) 
        
        final_cleanup_and_reboot_instructions()

    except subprocess.CalledProcessError as e:
        print_color(f"A critical command failed (return code {e.returncode}). Installation cannot continue.", Colors.RED, prefix=ERROR_SYMBOL, bold=True)
        print_color(f"Command: {e.cmd}", Colors.RED)
        if e.stdout: print_color(f"Stdout:\n{e.stdout.strip()}", Colors.RED)
        if e.stderr: print_color(f"Stderr:\n{e.stderr.strip()}", Colors.RED)
        print_color("Check error messages. Manually clean up if in live mode (e.g., umount /mnt/*).", Colors.ORANGE, prefix=WARNING_SYMBOL)
        sys.exit(1)
    except SystemExit: raise
    except Exception as e:
        print_color(f"An unexpected error occurred: {e}", Colors.RED, prefix=ERROR_SYMBOL, bold=True)
        import traceback; traceback.print_exc()
        print_color("Installation aborted.", Colors.RED, prefix=ERROR_SYMBOL, bold=True); sys.exit(1)
    finally:
        end_time = time.time(); duration = end_time - start_time
        print_color(f"\nScript finished in {duration:.2f} seconds.", Colors.PURPLE, bold=True)

def final_cleanup_and_reboot_instructions(): 
    print_section_header("Finalizing Installation")
    if not DRY_RUN_MODE and PROGRESS_FILE.exists():
        try: PROGRESS_FILE.unlink(); print_color("Removed progress tracking file.", Colors.MINT)
        except Exception as e: print_color(f"Could not remove progress file: {e}", Colors.ORANGE, prefix=WARNING_SYMBOL)
    print_color("\n--- INSTALLATION SCRIPT COMPLETE (OR DRY RUN FINISHED) ---", Colors.GREEN + Colors.BOLD, prefix=SUCCESS_SYMBOL)
    if not DRY_RUN_MODE:
        print_color("It should now be safe to reboot your system.", Colors.MINT)
        print_color("Type 'reboot' or 'exit' and then 'reboot'.", Colors.MINT)
        print_color(f"User '{USER_CONFIG['username']}' will auto-login. Root login is disabled.", Colors.LIGHT_BLUE)
        print_color("All setup, including AUR packages and keys, was attempted during installation.", Colors.LIGHT_BLUE)
        print_color("Check terminal output for any errors, especially during the user-specific setup part within chroot.", Colors.PEACH)
        print_color("Remember to remove the installation media.", Colors.ORANGE, prefix=WARNING_SYMBOL)
    else: print_color("Dry run complete. No changes were made to your system.", Colors.MINT)

if __name__ == "__main__":
    main()