#!/usr/bin/env python3

import sys
import time # For any potential delays
import subprocess
import pathlib
import configparser # For reading etc/config.ini
from typing import List, Dict, Tuple, Optional, Any

# --- Visuals (adapted from your terminal_animation_system.py) ---
COLORS: Dict[str, str] = {
    "pink": "\033[38;5;219m", "purple": "\033[38;5;183m", "cyan": "\033[38;5;123m",
    "yellow": "\033[38;5;228m", "blue": "\033[38;5;111m", "green": "\033[38;5;156m",
    "red": "\033[38;5;210m", "lavender": "\033[38;5;147m", "reset": "\033[0m",
}
STYLES: Dict[str, str] = {"bold": "\033[1m", "reset_style": "\033[22m"} # \033[22m resets bold
STATUS_SYMBOLS: Dict[str, Tuple[str, str]] = {
    "success": ("✓", "green"), "warning": ("!", "yellow"), "error": ("✗", "red"),
    "info": ("✧", "cyan"), "progress": ("→", "blue"), "star": ("★", "purple")
}

def _color_text(text: str, color_name: Optional[str] = None, style_names: Optional[List[str]] = None) -> str:
    """Applies color and styles to text."""
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
    """Prints a styled message. The 'message' part can have its own styles."""
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

# --- Configuration Paths ---
REPOSITORIES_FILE = pathlib.Path("/etc/apk/repositories")
APK_KEYS_DIR = pathlib.Path("/etc/apk/keys")

# --- Helper Functions for Commands ---

def run_command(
    command_list: List[str],
    use_doas: bool = False,
    capture_output: bool = False,
    check: bool = True,
    shell: bool = False, 
    input_str: Optional[str] = None
) -> subprocess.CompletedProcess:
    """
    Runs a command using subprocess, with optional sudo (doas) and output capturing.
    If shell is True, command_list should be a single string.
    """
    cmd_to_run: Any = command_list
    if shell and isinstance(command_list, list):
        cmd_to_run = " ".join(command_list) 
    
    if use_doas and not shell:
        cmd_to_run = ["doas"] + command_list
    elif use_doas and shell:
        cmd_to_run = f"doas {cmd_to_run}"

    _print_message(f"Executing: {cmd_to_run if isinstance(cmd_to_run, str) else ' '.join(cmd_to_run)}", level="progress", indent=1)
    try:
        process = subprocess.run(
            cmd_to_run,
            capture_output=capture_output,
            text=True,
            check=check, 
            shell=shell,
            input=input_str
        )
        if capture_output:
            if process.stdout:
                _print_message(f"STDOUT:\n{process.stdout.strip()}", level="info", indent=2)
            if process.stderr:
                 _print_message(f"STDERR:\n{process.stderr.strip()}", level="warning", indent=2)
        return process
    except FileNotFoundError:
        cmd_name = command_list[0] if not shell and command_list else str(cmd_to_run).split()[0]
        _print_message(f"Error: Command '{cmd_name}' not found.", level="error")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        _print_message(f"Error running command: {e.cmd}", level="error")
        if e.stdout: _print_message(f"STDOUT:\n{e.stdout.strip()}", level="error", indent=2)
        if e.stderr: _print_message(f"STDERR:\n{e.stderr.strip()}", level="error", indent=2)
        if check: 
            raise 
        return e 
    except Exception as e_gen:
        _print_message(f"An unexpected error occurred running command: {e_gen}", level="error")
        raise


def get_cports_signing_key_paths(cports_root: pathlib.Path) -> Tuple[Optional[pathlib.Path], Optional[pathlib.Path]]:
    """
    Determines the private and public signing key paths from cports config.
    Returns (private_key_path_effective, public_key_path) or (None, None) or (path, None) if pub key missing.
    """
    _print_message("Attempting to determine signing key paths...", indent=1)
    config_ini_path = cports_root / "etc" / "config.ini"
    private_key_path_raw: Optional[str] = None

    if not config_ini_path.is_file():
        _print_message(f"cports config file '{config_ini_path}' not found.", level="warning", indent=2)
        return None, None

    _print_message(f"Reading cports config: '{config_ini_path}'", indent=2)
    config = configparser.ConfigParser(interpolation=None, default_section="cbuild") # Try 'cbuild' as default
    # Allow sections like [DEFAULT] or global keys by also checking config.defaults()
    # and specific sections like [signing]
    
    try:
        # Read the file, configparser handles sections automatically
        read_files = config.read(config_ini_path)
        if not read_files:
            _print_message(f"Config file '{config_ini_path}' was empty or could not be parsed.", level="error", indent=2)
            return None, None
    except Exception as e:
        _print_message(f"Error reading config file '{config_ini_path}': {e}", level="error", indent=2)
        return None, None

    # Attempt 1: Look for "signkey = " in [cbuild] or DEFAULT section
    if config.has_option("cbuild", "signkey"): # Check common [cbuild] section
        private_key_path_raw = config.get("cbuild", "signkey", fallback=None)
    elif "signkey" in config.defaults(): # Check if it's a global key (under DEFAULT)
         private_key_path_raw = config.defaults().get("signkey")

    if private_key_path_raw:
        _print_message(f"Found 'signkey = {private_key_path_raw}' (likely in [cbuild] or global)", indent=2)
    else:
        _print_message("Did not find 'signkey = ...' format in [cbuild]/global. Checking for '[signing]' section with 'key = ...'", indent=2)
        if config.has_section("signing") and config.has_option("signing", "key"):
            key_filename = config.get("signing", "key", fallback=None)
            if key_filename:
                private_key_path_raw = f"etc/keys/{key_filename}" 
                _print_message(f"Found key filename '{key_filename}' under [signing]. Constructed raw path: '{private_key_path_raw}'", indent=2)
            else:
                _print_message("'key' entry empty or not found under [signing].", level="warning", indent=2)
        else:
            _print_message("'[signing]' section or 'key' entry not found.", level="warning", indent=2)

    if not private_key_path_raw:
        _print_message("Could not determine private key path from config.", level="error", indent=2)
        return None, None

    private_key_path_effective: pathlib.Path
    if pathlib.Path(private_key_path_raw).is_absolute():
        private_key_path_effective = pathlib.Path(private_key_path_raw)
    else:
        private_key_path_effective = (cports_root / private_key_path_raw).resolve()
    
    _print_message(f"Effective private key path: '{private_key_path_effective}'", indent=2)

    if not private_key_path_effective.is_file():
        _print_message(f"Private key file does NOT exist at: '{private_key_path_effective}'", level="error", indent=2)
        return None, None 

    public_key_filename = private_key_path_effective.name + ".pub"
    public_key_path = private_key_path_effective.with_name(public_key_filename)
    _print_message(f"Derived public key path: '{public_key_path}'", indent=2)

    if not public_key_path.is_file():
        _print_message(f"Public key file does NOT exist at: '{public_key_path}'", level="warning", indent=2)
        return private_key_path_effective, None 
        
    return private_key_path_effective, public_key_path


def ensure_signing_key_trusted(public_key_path: Optional[pathlib.Path]) -> bool:
    """Copies the public key to /etc/apk/keys if not already present. Returns True if key was copied."""
    if not public_key_path or not public_key_path.is_file():
        _print_message("No valid public key path provided or key file does not exist. Cannot ensure trust.", level="warning", indent=1)
        return False

    apk_key_target_path = APK_KEYS_DIR / public_key_path.name
    _print_message(f"Checking for public key '{public_key_path.name}' in '{APK_KEYS_DIR}'...", indent=1)

    if not APK_KEYS_DIR.is_dir():
        _print_message(f"APK keys directory '{APK_KEYS_DIR}' does not exist. Attempting to create with doas...", level="warning", indent=2)
        try:
            run_command(["mkdir", "-p", str(APK_KEYS_DIR)], use_doas=True)
            _print_message(f"Created '{APK_KEYS_DIR}'.", level="success", indent=2)
        except subprocess.CalledProcessError:
            _print_message(f"Failed to create APK keys directory '{APK_KEYS_DIR}'.", level="error", indent=2)
            return False

    if apk_key_target_path.is_file():
        _print_message(f"Public key '{apk_key_target_path.name}' already exists in '{APK_KEYS_DIR}'.", indent=2)
        return False
    else:
        _print_message(f"Public key '{public_key_path.name}' not found in '{APK_KEYS_DIR}'. Copying...", indent=2)
        try:
            run_command(["cp", str(public_key_path), str(APK_KEYS_DIR)], use_doas=True)
            _print_message("Public key copied successfully.", level="success", indent=2)
            return True
        except subprocess.CalledProcessError:
            _print_message(f"Failed to copy public key to '{APK_KEYS_DIR}'.", level="error", indent=2)
            return False


def configure_apk_repositories(cports_root: pathlib.Path) -> bool:
    """Checks and adds local cports repositories to /etc/apk/repositories. Returns True if modified."""
    _print_message("Checking and configuring local APK repositories...", indent=1)
    modified = False
    
    repo_paths_to_check = {
        "main": cports_root / "packages" / "main",
        "user": cports_root / "packages" / "user",
    }

    existing_repo_lines: List[str] = []
    try:
        cat_process = run_command(["cat", str(REPOSITORIES_FILE)], use_doas=True, capture_output=True, check=False)
        if cat_process.returncode == 0:
            existing_repo_lines = [line.strip() for line in cat_process.stdout.splitlines() if line.strip() and not line.strip().startswith("#")]
            _print_message(f"Successfully read '{REPOSITORIES_FILE}'. Found {len(existing_repo_lines)} active repo lines.", indent=2)
        elif "No such file or directory" in cat_process.stderr:
             _print_message(f"'{REPOSITORIES_FILE}' not found. It will be created.", level="info", indent=2)
        else:
            _print_message(f"Could not read '{REPOSITORIES_FILE}' even with doas. Stderr: {cat_process.stderr}", level="warning", indent=2)

    except subprocess.CalledProcessError as e:
         _print_message(f"Error reading '{REPOSITORIES_FILE}' with 'doas cat': {e.stderr}", level="warning", indent=2)


    for repo_type, repo_path in repo_paths_to_check.items():
        repo_path_str = str(repo_path.resolve()) 
        _print_message(f"Checking for {repo_type} repository: '{repo_path_str}'", indent=2)
        if not repo_path.is_dir():
            _print_message(f"Local cports {repo_type} repository directory '{repo_path}' not found. Skipping.", level="info", indent=3)
            continue

        if repo_path_str in existing_repo_lines:
            _print_message(f"Local cports {repo_type} repository line already configured.", indent=3)
        else:
            _print_message(f"Adding local cports {repo_type} repository line to '{REPOSITORIES_FILE}'...", indent=3)
            command_to_run = f"echo '{repo_path_str}' | tee -a {REPOSITORIES_FILE}"
            try:
                run_command(command_to_run, use_doas=True, shell=True) 
                _print_message("Successfully appended.", level="success", indent=3)
                modified = True
            except subprocess.CalledProcessError:
                 _print_message(f"Failed to append {repo_type} repository to '{REPOSITORIES_FILE}'.", level="error", indent=3)
    return modified


def main(package_to_install: str) -> None:
    _print_message(f"Starting cports local package installer for package: '{package_to_install}'")
    # Determine the script's directory to correctly locate the cports directory.
    # The cports directory is expected to be at ../cports relative to this script's location.
    script_dir = pathlib.Path(__file__).resolve().parent
    cports_root = (script_dir / "../cports").resolve()
    if not (cports_root / "etc" / "config.ini").is_file() or not (cports_root / "packages").is_dir():
        _print_message("This script must be run from the root of your cports clone.", level="error")
        _print_message(f"Current directory: '{cports_root}' is not a valid cports root.", level="error")
        sys.exit(1)

    key_copied_this_run = False
    repo_config_modified_this_run = False

    _print_message("Step 1: Processing signing key...", message_styles=["bold"])
    _, public_key_path = get_cports_signing_key_paths(cports_root)
    if public_key_path and public_key_path.is_file():
        key_copied_this_run = ensure_signing_key_trusted(public_key_path)
    else:
        _print_message("Failed to get a valid public key path or public key file does not exist. Local repository might remain untrusted.", level="warning", indent=1)

    _print_message("Step 2: Configuring APK repositories...", message_styles=["bold"])
    repo_config_modified_this_run = configure_apk_repositories(cports_root)
    
    _print_message("Step 3: Updating APK cache...", message_styles=["bold"])
    if key_copied_this_run or repo_config_modified_this_run:
        _print_message("Keys or repository config changed, running 'apk update'.", indent=1)
    else:
        _print_message("No key/repo changes, running 'apk update' for freshness.", indent=1)
    try:
        run_command(["apk", "update"], use_doas=True)
        _print_message("APK cache updated successfully.", level="success", indent=1)
    except subprocess.CalledProcessError:
        _print_message("apk update failed. Check output above. Continuing to install attempt...", level="warning", indent=1)

    _print_message(f"Step 4: Attempting to install '{package_to_install}'...", message_styles=["bold"])
    try:
        run_command(["apk", "add", package_to_install], use_doas=True)
        _print_message(f"Successfully installed '{package_to_install}'.", level="success")
    except subprocess.CalledProcessError:
        _print_message(f"Failed to install '{package_to_install}'.", level="error")
        _print_message("Troubleshooting:", indent=1)
        _print_message("1. Check 'apk update' output for 'UNTRUSTED signature' warnings.", indent=2)
        _print_message("2. Ensure the package was built and exists in your local cports repository.", indent=2)
        _print_message("3. Verify 'etc/config.ini' has a correct key entry and the .pub key is in /etc/apk/keys/.", indent=2)
        sys.exit(1)
    
    _print_message("Script finished successfully.", level="star")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <package_name>")
        sys.exit(1)
    
    package_name_arg = sys.argv[1]
    try:
        main(package_name_arg)
    except Exception as e:
        _print_message(f"An unexpected error occurred in main: {e}", level="error")
        sys.exit(1)
    finally:
        print(COLORS.get("reset", "\033[0m")) # Ensure terminal colors are reset

