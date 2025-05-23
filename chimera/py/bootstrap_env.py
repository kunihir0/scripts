#!/usr/bin/env python3

import subprocess
import sys
from pathlib import Path
from typing import Optional
import time # For sleep after attempting to write to proc

try:
    from .utils.execution import run_as_user as util_run_as_user
except ImportError:
    try:
        script_dir_for_util_import = Path(__file__).resolve().parent
        if str(script_dir_for_util_import) not in sys.path:
            sys.path.insert(0, str(script_dir_for_util_import))
        from utils.execution import run_as_user as util_run_as_user
    except ImportError:
        try:
            project_root_for_util = Path(__file__).resolve().parent.parent.parent
            if str(project_root_for_util) not in sys.path:
                 sys.path.insert(0, str(project_root_for_util))
            from chimera.py.utils.execution import run_as_user as util_run_as_user
        except ImportError:
            print(f"[BootstrapEnv] CRITICAL: Could not import 'run_as_user'. Please check chimera/py/utils/execution.py and PYTHONPATH.")
            sys.exit(1)

LOG_PREFIX = "[BootstrapEnv]"
STATE_DIR = Path("/var/lib/chimera_bootstrap")
PACKAGES_TO_INSTALL = [
    "opendoas",
    "base-cbuild-host" 
]
NEW_USERNAME = "builder"
CPORTS_ROOT_DIR_RELATIVE_FROM_PY = Path("../cports") 
CBUILD_EXECUTABLE_NAME = "cbuild" 
KERNEL_USERNS_CLONE_PATH = Path("/proc/sys/kernel/unprivileged_userns_clone")
BWRAP_ERROR_SIGNATURE = "bwrap: No permissions to creating new namespace"

def print_log(message):
    print(f"{LOG_PREFIX} {message}")

def run_root_command(command, check=True, shell=False, cwd=None, capture_output=True, text=True, input_str=None):
    cmd_str = ' '.join(command) if isinstance(command, list) else command
    log_cmd_str = cmd_str
    if cwd: log_cmd_str = f"(in {cwd}) {cmd_str}"
    print_log(f"Executing (as root): {log_cmd_str}")
    try:
        process = subprocess.run(
            command, check=check, text=text, capture_output=capture_output,
            shell=shell, cwd=cwd, input=input_str
        )
        if capture_output:
            if process.stdout and process.stdout.strip(): print_log(f"Stdout:\n{process.stdout.strip()}")
            if process.stderr and process.stderr.strip():
                is_apk_info_not_found = (
                    isinstance(command, list) and command[0] == "apk" and "info" in command and
                    not check and "No such package" in process.stderr
                )
                is_useradd_shell_warning = (
                    isinstance(command, list) and command[0] == "useradd" and
                    "missing or non-executable shell" in process.stderr
                )
                is_stat_error = (
                    isinstance(command, list) and command[0] == "stat" and not check
                )
                if not (is_apk_info_not_found or (is_useradd_shell_warning and not check) or is_stat_error):
                    print_log(f"Stderr:\n{process.stderr.strip()}")
        return process
    except subprocess.CalledProcessError as e:
        print_log(f"Error (as root): {log_cmd_str}")
        print_log(f"Return code: {e.returncode}")
        if capture_output:
            if e.stdout and e.stdout.strip(): print_log(f"Stdout:\n{e.stdout.strip()}")
            if e.stderr and e.stderr.strip(): print_log(f"Stderr:\n{e.stderr.strip()}")
        if check: sys.exit(f"Command failed: {log_cmd_str}")
        return e
    except FileNotFoundError:
        cmd_name = command[0] if isinstance(command, list) else command.split()[0]
        print_log(f"Error: Command not found - {cmd_name}")
        if check: sys.exit(f"Command not found: {cmd_name}")
        return None

def ensure_state_dir_exists():
    print_log(f"Ensuring state directory: {STATE_DIR}")
    try: STATE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print_log(f"Failed to create state directory {STATE_DIR}: {e}")
        sys.exit(1)

def mark_step_completed(step_name):
    ensure_state_dir_exists()
    safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in step_name)
    state_file = STATE_DIR / f"{safe_name}.complete"
    print_log(f"Marking step '{step_name}' as completed ({state_file}).")
    try:
        with state_file.open("w") as f: f.write("completed\n")
        print_log(f"Step '{step_name}' marked.")
    except IOError as e:
        print_log(f"Failed to mark step '{step_name}': {e}")
        sys.exit(1)

def is_step_completed(step_name):
    safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in step_name)
    state_file = STATE_DIR / f"{safe_name}.complete"
    completed = state_file.exists()
    log_msg = "IS" if completed else "is NOT"
    print_log(f"Check: Step '{step_name}' {log_msg} completed.")
    return completed

def confirm_action(prompt_message, default_yes=True):
    try:
        script_dir = Path(__file__).resolve().parent
        project_root_for_arch = script_dir.parent.parent
        if str(project_root_for_arch) not in sys.path:
            sys.path.insert(0, str(project_root_for_arch))
        from arch.modules import ui
        print_log("Using themed UI for confirmation.")
        return ui.prompt_yes_no(prompt_message, default_yes=default_yes)
    except ImportError:
        print_log("UI module ('arch.modules.ui') not found. Using basic input.")
        default_indicator = "Y/n" if default_yes else "y/N"
        choice = input(f"{prompt_message} (yes/no) [{default_indicator}]: ").strip().lower()
        if not choice: return default_yes
        return choice in ['yes', 'y']

def check_package_installed(package_name):
    print_log(f"Checking if '{package_name}' is installed...")
    process = run_root_command(["apk", "info", "--installed", package_name], check=False)
    installed = process is not None and process.returncode == 0
    log_msg = "IS" if installed else "is NOT"
    print_log(f"Package '{package_name}' {log_msg} installed.")
    return installed

def install_packages_if_needed(packages: list):
    step_name = "install_os_packages"
    if is_step_completed(step_name): return True
    
    pending = [pkg for pkg in packages if not check_package_installed(pkg)]
    if not pending:
        print_log("All required OS packages from the list are already installed.")
        mark_step_completed(step_name)
        return True
    if confirm_action(f"The following OS packages will be installed: {', '.join(pending)}. Proceed?"):
        for pkg in pending:
            print_log(f"Installing '{pkg}'...")
            run_root_command(["apk", "add", "--no-cache", pkg])
        mark_step_completed(step_name)
        return True
    else:
        print_log("OS package installation declined. Exiting.")
        sys.exit(1)

def check_user_exists(username):
    print_log(f"Checking if user '{username}' exists...")
    process = run_root_command(["id", username], check=False)
    exists = process is not None and process.returncode == 0
    log_msg = "already exists" if exists else "does not exist"
    print_log(f"User '{username}' {log_msg}.")
    return exists

def create_user_if_needed(username):
    step_name = f"create_user_{username}"
    group_step_name = f"add_user_{username}_to_wheel"

    if is_step_completed(step_name) and is_step_completed(group_step_name): return True

    if check_user_exists(username):
        print_log(f"User '{username}' already exists.")
        if not is_step_completed(group_step_name):
            if confirm_action(f"User '{username}' exists. Add to 'wheel' group (if not already a member)?"):
                run_root_command(["usermod", "-aG", "wheel", username])
                mark_step_completed(group_step_name)
        else:
             print_log(f"User '{username}' is already in 'wheel' group (or step marked complete).")
        if not is_step_completed(step_name): mark_step_completed(step_name)
        return True

    if confirm_action(f"Create user '{username}' (no password) for cbuild?"):
        print_log(f"Creating user '{username}' (no password)...")
        if not Path("/bin/bash").is_file():
            print_log("'/bin/bash' not found. Ensuring 'base-cbuild-host' (which should provide it) is installed.")
            if not check_package_installed("base-cbuild-host"):
                 run_root_command(["apk", "add", "--no-cache", "base-cbuild-host"])
            if not check_package_installed("bash") and not Path("/bin/bash").is_file():
                 run_root_command(["apk", "add", "--no-cache", "bash"])
        
        run_root_command(["useradd", "-m", "-s", "/bin/bash", username])
        print_log(f"Adding '{username}' to 'wheel' group...")
        run_root_command(["usermod", "-aG", "wheel", username])
        mark_step_completed(group_step_name)
        mark_step_completed(step_name)
        return True
    else:
        print_log(f"User '{username}' creation declined. Exiting.")
        sys.exit(1)

def configure_doas_if_needed():
    step_name = "configure_doas"
    if is_step_completed(step_name): return True
    doas_conf, rule = Path("/etc/doas.conf"), "permit nopass :wheel as root"
    if confirm_action(f"Configure doas ('{rule}' in {doas_conf})?"):
        print_log(f"Configuring {doas_conf}...")
        try:
            content = doas_conf.read_text() if doas_conf.exists() else ""
            if rule in content:
                print_log(f"Rule already exists in {doas_conf}.")
            else:
                with open(doas_conf, "a") as f:
                    if content and not content.endswith("\n"): f.write("\n")
                    f.write(rule + "\n")
                print_log(f"Added rule to {doas_conf}.")
            mark_step_completed(step_name)
            return True
        except IOError as e:
            print_log(f"Error writing {doas_conf}: {e}. Run as root.")
            sys.exit(1)
    else:
        print_log("doas configuration declined.")
        return False

def get_dir_owner(dir_path: Path) -> Optional[str]:
    print_log(f"Checking owner of '{dir_path}'...")
    result = run_root_command(["stat", "-f", "%Su", str(dir_path)], check=False)
    if result and result.returncode == 0 and result.stdout:
        owner = result.stdout.strip()
        print_log(f"Directory '{dir_path}' is owned by '{owner}'.")
        return owner
    print_log(f"Could not determine owner of '{dir_path}'. Stat command failed or no output. Stderr: {result.stderr.strip() if result and result.stderr else 'N/A'}")
    return None

def change_dir_ownership_if_needed(dir_to_chown: Path, username: str):
    step_name = f"chown_{dir_to_chown.name}_to_{username}"
    if is_step_completed(step_name): return True

    current_owner = get_dir_owner(dir_to_chown)
    if current_owner == username:
        print_log(f"Directory '{dir_to_chown}' is already owned by '{username}'.")
        mark_step_completed(step_name)
        return True

    if confirm_action(f"Change ownership of '{dir_to_chown}' (current owner: {current_owner or 'unknown'}) to user '{username}'?"):
        print_log(f"Changing ownership: {dir_to_chown} -> {username}")
        run_root_command(["chown", "-R", f"{username}:{username}", str(dir_to_chown)])
        mark_step_completed(step_name)
        return True
    else:
        print_log(f"Ownership change of '{dir_to_chown}' declined. Exiting.")
        sys.exit(1)

def attempt_enable_userns_clone():
    step_name = "attempt_enable_userns_clone"
    userns_enabled_confirmed = False

    if is_step_completed(step_name + "_confirmed_enabled"):
        print_log(f"Kernel parameter '{KERNEL_USERNS_CLONE_PATH}' previously confirmed to be '1'.")
        return True
    
    if is_step_completed(step_name + "_write_attempted"):
        print_log(f"Previously attempted to modify '{KERNEL_USERNS_CLONE_PATH}'. Will re-check value.")

    print_log(f"Checking kernel parameter: {KERNEL_USERNS_CLONE_PATH}")
    if KERNEL_USERNS_CLONE_PATH.exists():
        try:
            current_value = KERNEL_USERNS_CLONE_PATH.read_text().strip()
            print_log(f"Current value of '{KERNEL_USERNS_CLONE_PATH}' is '{current_value}'. Expected '1' for bwrap.")
            if current_value == "1":
                print_log("Unprivileged user namespaces appear to be enabled.")
                mark_step_completed(step_name + "_confirmed_enabled")
                return True
            else:
                if confirm_action(f"Attempt to enable unprivileged user namespaces by writing '1' to '{KERNEL_USERNS_CLONE_PATH}' (requires root)? This may not work inside all containers.", default_yes=False):
                    print_log(f"Attempting to write '1' to '{KERNEL_USERNS_CLONE_PATH}'...")
                    result = run_root_command(f"echo 1 > {KERNEL_USERNS_CLONE_PATH}", shell=True, check=False)
                    mark_step_completed(step_name + "_write_attempted")
                    if result and result.returncode == 0:
                        time.sleep(0.1) 
                        new_value = KERNEL_USERNS_CLONE_PATH.read_text().strip()
                        if new_value == "1":
                            print_log(f"Successfully wrote '1'. Value is now '{new_value}'.")
                            mark_step_completed(step_name + "_confirmed_enabled")
                            return True
                        else:
                            print_log(f"Wrote '1' but value is still '{new_value}'. Write might have been ineffective.")
                            userns_enabled_confirmed = False
                    else:
                        print_log(f"Failed to write '1' to '{KERNEL_USERNS_CLONE_PATH}'. This is common in containers if /proc/sys is read-only.")
                        userns_enabled_confirmed = False
                else:
                    print_log("Skipped attempt to enable unprivileged user namespaces.")
                    userns_enabled_confirmed = False
        except Exception as e:
            print_log(f"Error accessing or writing to '{KERNEL_USERNS_CLONE_PATH}': {e}")
            userns_enabled_confirmed = False
    else:
        print_log(f"Kernel parameter '{KERNEL_USERNS_CLONE_PATH}' not found. Cannot attempt to enable.")
        userns_enabled_confirmed = False
    
    if not userns_enabled_confirmed:
        print_log("WARNING: Unprivileged user namespaces might not be enabled or could not be confirmed.")
        print_log("`cbuild bootstrap` (and other bwrap operations) will likely fail if this is not '1'.")
        print_log("This setting may need to be configured on the Docker host (e.g., `sudo sysctl kernel.unprivileged_userns_clone=1`)")
        print_log("or when running the Docker container (e.g., `docker run --sysctl kernel.unprivileged_userns_clone=1 ...`).")
    return userns_enabled_confirmed

def run_cbuild_cmd_as_new_user(username: str, cports_actual_root_dir: Path, cbuild_sub_command: list, capture_for_check: bool = False):
    shell_command_str = f"cd '{str(cports_actual_root_dir)}' && './{CBUILD_EXECUTABLE_NAME}' {' '.join(cbuild_sub_command)}"
    print_log(f"Preparing to run (as {username} in '{cports_actual_root_dir}'): {shell_command_str}")
    
    # Use capture_output=True only if specifically needed for checking content
    success, return_code, err_msg_or_stderr = util_run_as_user(shell_command_str, username, capture_output=capture_for_check)
    
    operation_successful = success # Based on su's exit code

    if capture_for_check and err_msg_or_stderr:
        print_log(f"Captured stderr from su (for {cbuild_sub_command[0]}):\n{err_msg_or_stderr.strip()}")
        if BWRAP_ERROR_SIGNATURE in err_msg_or_stderr:
            print_log(f"CRITICAL BWRAP ERROR DETECTED: '{BWRAP_ERROR_SIGNATURE}' found in output.")
            operation_successful = False # Override success if bwrap error is present
    elif not success and err_msg_or_stderr : # If not capturing but su failed
         print_log(f"Details from su/run_as_user: {err_msg_or_stderr}")


    if not operation_successful:
        print_log(f"Error running './{CBUILD_EXECUTABLE_NAME} {' '.join(cbuild_sub_command)}' as user '{username}'.")
        print_log(f"Check terminal output from './{CBUILD_EXECUTABLE_NAME} {' '.join(cbuild_sub_command)}' for cbuild-specific errors.")

        if confirm_action(f"Command './{CBUILD_EXECUTABLE_NAME} {' '.join(cbuild_sub_command)}' as {username} failed (su exit: {return_code}, bwrap error detected: {not operation_successful and success}). Continue bootstrap?", default_yes=False):
            print_log("Continuing despite cbuild command failure.")
            return False 
        else:
            print_log("Exiting due to cbuild command failure.")
            sys.exit(1)
            
    print_log(f"'./{CBUILD_EXECUTABLE_NAME} {' '.join(cbuild_sub_command)}' as {username} completed (su exit: {return_code}, bwrap error detected: {not operation_successful and success}).")
    return operation_successful


def main():
    print_log("Starting comprehensive bootstrap environment setup...")
    ensure_state_dir_exists()

    if not install_packages_if_needed(PACKAGES_TO_INSTALL): return
    
    userns_ok = attempt_enable_userns_clone()
    if not userns_ok:
        if not confirm_action("Unprivileged user namespaces might not be enabled. `cbuild bootstrap` will likely fail. Continue anyway?", default_yes=False):
            print_log("Setup aborted by user due to user namespace concerns.")
            sys.exit(0)

    if not create_user_if_needed(NEW_USERNAME): return
    configure_doas_if_needed()

    script_dir = Path(__file__).resolve().parent 
    cports_actual_root_dir = (script_dir / CPORTS_ROOT_DIR_RELATIVE_FROM_PY).resolve()
    
    print_log(f"DEBUG: bootstrap_env.py location (script_dir): '{script_dir}'")
    print_log(f"DEBUG: Relative path to cports root from script_dir: '{CPORTS_ROOT_DIR_RELATIVE_FROM_PY}'")
    print_log(f"DEBUG: Calculated cports_actual_root_dir (cbuild's parent dir): '{cports_actual_root_dir}'")

    cbuild_exe_path = cports_actual_root_dir / CBUILD_EXECUTABLE_NAME
    print_log(f"Checking for cbuild executable at: {cbuild_exe_path}")
    if not cbuild_exe_path.is_file():
        print_log(f"CRITICAL: cbuild executable '{CBUILD_EXECUTABLE_NAME}' not found at '{cbuild_exe_path}'.")
        sys.exit(1)

    if not change_dir_ownership_if_needed(cports_actual_root_dir, NEW_USERNAME): return

    keygen_step_name = f"cbuild_keygen_as_{NEW_USERNAME}"
    if not is_step_completed(keygen_step_name):
        if confirm_action(f"Run './{CBUILD_EXECUTABLE_NAME} keygen' as '{NEW_USERNAME}' in '{cports_actual_root_dir}'?"):
            # keygen is usually not very verbose and doesn't need interaction beyond its own prompts
            if run_cbuild_cmd_as_new_user(NEW_USERNAME, cports_actual_root_dir, ["keygen"], capture_for_check=True):
                mark_step_completed(keygen_step_name)
        else: print_log(f"Skipped './{CBUILD_EXECUTABLE_NAME} keygen'.")
    
    bootstrap_step_name = f"cbuild_bootstrap_as_{NEW_USERNAME}"
    if not is_step_completed(bootstrap_step_name):
        bldroot_path = cports_actual_root_dir / "bldroot"
        if bldroot_path.is_dir():
            print_log(f"Existing bldroot directory found: {bldroot_path}")
            if confirm_action(f"Run './{CBUILD_EXECUTABLE_NAME} zap' as '{NEW_USERNAME}' to remove existing bldroot for a clean bootstrap?", default_yes=True):
                print_log(f"Attempting to remove existing bldroot using './{CBUILD_EXECUTABLE_NAME} zap' as '{NEW_USERNAME}'...")
                if run_cbuild_cmd_as_new_user(NEW_USERNAME, cports_actual_root_dir, ["zap"]): # capture_for_check=False (default)
                    print_log("'./cbuild zap' completed successfully.")
                else:
                    print_log("'./cbuild zap' failed. The bldroot may not be clean. Manual removal might be needed.")
                    if not confirm_action("Continue with bootstrap despite './cbuild zap' failure?", default_yes=False):
                        print_log("Bootstrap aborted by user due to 'zap' failure.")
                        sys.exit(1)
            else:
                print_log("Proceeding with existing bldroot. This might cause issues.")
        
        if confirm_action(f"Run './{CBUILD_EXECUTABLE_NAME} bootstrap' as '{NEW_USERNAME}' in '{cports_actual_root_dir}'?"):
            # For bootstrap, we want to capture output to check for bwrap errors
            if run_cbuild_cmd_as_new_user(NEW_USERNAME, cports_actual_root_dir, ["bootstrap"], capture_for_check=True):
                mark_step_completed(bootstrap_step_name)
        else:
            print_log(f"Skipped './{CBUILD_EXECUTABLE_NAME} bootstrap'.")

    print_log("Comprehensive bootstrap setup process finished.")

if __name__ == "__main__":
    try:
        with open("/proc/1/uid_map", "r") as f:
            if f.readline().split()[0] != '0':
                print_log("This script must be run as root.")
                sys.exit(1)
    except Exception:
        try:
            if subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip() != '0':
                print_log("This script must be run as root (fallback check).")
                sys.exit(1)
        except Exception as e_id:
             print_log(f"Could not determine if running as root: {e_id}. Please run as root.")
             sys.exit(1)
    main()