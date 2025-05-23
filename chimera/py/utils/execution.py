#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utility functions for command execution, including privilege switching.
Minimal 'os' module usage. Strict type hints.
"""

import subprocess
import sys
from pathlib import Path
from typing import Union, List, Tuple, Optional

# --- Result Type ---
RunAsUserResult = Tuple[bool, Optional[int], Optional[str]]

# --- Utility Functions ---

def _is_root() -> bool:
    """Checks if the current effective user is root. Minimal os module usage."""
    try:
        with open("/proc/1/uid_map", "r") as f:
            line = f.readline()
            parts = line.split()
            if len(parts) >= 2 and parts[1] == '0':
                return True
    except FileNotFoundError:
        pass
    except Exception:
        pass

    try:
        result = subprocess.run(["id", "-u"], capture_output=True, text=True, check=False)
        return result.returncode == 0 and result.stdout.strip() == '0'
    except FileNotFoundError:
        sys.stderr.write("[Utils._is_root] CRITICAL: 'id' command not found. Cannot determine user privileges.\n")
        return False
    except Exception as e:
        sys.stderr.write(f"[Utils._is_root] Error checking UID with 'id': {e}\n")
        return False

def _user_exists(username: str) -> bool:
    """Checks if a user exists. Minimal os module usage."""
    if not username or not username.strip():
        return False
    try:
        result = subprocess.run(["id", username], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        sys.stderr.write("[Utils._user_exists] CRITICAL: 'id' command not found. Cannot check user existence.\n")
        return False
    except Exception as e:
        sys.stderr.write(f"[Utils._user_exists] Error checking user '{username}' with 'id': {e}\n")
        return False

def run_as_user(
    command: Union[str, List[str]],
    username: str,
    capture_output: bool = False
) -> RunAsUserResult:
    """
    Executes a command string or list of command arguments as a designated non-root user.
    This function must be run with root privileges to switch users.
    """
    if not _is_root():
        return False, None, "Error: run_as_user must be invoked with root privileges."

    if not _user_exists(username):
        return False, None, f"Error: Target user '{username}' does not exist."

    cmd_str_for_su: str

    try:
        if isinstance(command, list):
            quoted_parts = []
            for part in command:
                if any(c in part for c in " '\"\\$`&|<>"):
                    quoted_parts.append(f"'{part.replace("'", "'\\''")}'")
                else:
                    quoted_parts.append(part)
            cmd_str_for_su = " ".join(quoted_parts)
        elif isinstance(command, str):
            cmd_str_for_su = command
        else:
            return False, None, "Error: command must be a string or list of arguments."

        # Rely on the user's default login shell (set to /bin/bash during useradd)
        su_command = ["su", "-", username, "-c", cmd_str_for_su] 
        
        stdout_pipe = subprocess.PIPE if capture_output else None
        stderr_pipe = subprocess.PIPE if capture_output else None
        
        process = subprocess.run(
            su_command,
            capture_output=capture_output,
            text=True if capture_output else False,
            check=False 
        )

        if process.returncode == 0:
            return True, process.returncode, None 
        else:
            err_msg = f"Error: Execution as user '{username}' failed. `su` exit code: {process.returncode}."
            detailed_error = process.stderr.strip() if capture_output and process.stderr else err_msg
            if capture_output and process.stderr and err_msg not in detailed_error:
                detailed_error = (detailed_error + "\n" + err_msg).strip()
            return False, process.returncode, detailed_error

    except FileNotFoundError as e:
        return False, None, f"Error: Required system command '{e.filename}' not found."
    except Exception as e:
        return False, None, f"An unexpected error occurred in run_as_user: {type(e).__name__}: {e}"

# --- Other Suggested Utility Function Stubs (to be implemented) ---

def atomic_write_file(
    filepath: Path, 
    content: Union[str, bytes], 
    mode: str = "w",
    owner_user: Optional[str] = None,
    owner_group: Optional[str] = None, 
    permissions: Optional[int] = None
) -> bool:
    raise NotImplementedError("atomic_write_file is not yet implemented.")

def check_system_package_installed(package_name: str, manager_cmd: str = "apk info --installed") -> bool:
    raise NotImplementedError("check_system_package_installed is not yet implemented.")

def get_process_uid_gid(pid: int) -> Optional[Tuple[int, int]]:
    raise NotImplementedError("get_process_uid_gid is not yet implemented.")