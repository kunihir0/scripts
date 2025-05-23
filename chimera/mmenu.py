#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main menu hub for Chimera scripts.
Adheres to the UI style defined in arch.modules.ui.
"""

import sys
import subprocess
import time 
from pathlib import Path

try:
    from arch.modules import ui
except ImportError:
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    try:
        from arch.modules import ui
    except ImportError:
        print("Error: Could not import the 'ui' module from 'arch.modules'.")
        print(f"Attempted to add '{project_root}' to sys.path.")
        sys.exit(1)

SCRIPTS_TO_RUN = {
    "1": {
        "name": "Bootstrap Environment Setup",
        "path": "chimera/py/bootstrap_env.py",
        "description": "Sets up the initial Docker environment (installs packages, etc.)."
    },
    "2": {
        "name": "cports Local Installer",
        "path": "chimera/py/cports_local_installer.py",
        "description": "Runs the local cports installer."
    },
    "3": {
        "name": "Surface Kernel Setup",
        "path": "chimera/py/setup_surface_kernel_py.py",
        "description": "Runs the Surface kernel setup script."
    }
}

BOOTSTRAP_STATE_DIR = Path("/var/lib/chimera_bootstrap")

def clear_screen():
    subprocess.run(["clear"], shell=False, check=False)

def display_menu():
    ui.print_header("Chimera Scripts Main Menu")
    ui.print_color("Please select an option to run:", ui.Colors.LAVENDER)
    ui.print_separator(char="*", color=ui.Colors.PINK, length=60)

    for key, script_info in SCRIPTS_TO_RUN.items():
        ui.print_color(f"  {ui.Colors.PINK_BG}{ui.Colors.BOLD}{key}{ui.Colors.RESET}  {ui.Colors.CYAN}{script_info['name']}{ui.Colors.RESET}", ui.Colors.MINT)
        ui.print_color(f"      {script_info['description']}", ui.Colors.LIGHT_BLUE, italic=True)
        ui.print_color("", ui.Colors.RESET)

    ui.print_color(f"  {ui.Colors.PINK_BG}{ui.Colors.BOLD}R{ui.Colors.RESET}  {ui.Colors.CYAN}Reset Bootstrap State{ui.Colors.RESET}", ui.Colors.MINT)
    ui.print_color(f"      {ui.Colors.LIGHT_BLUE}Attempts to clear completion flags for bootstrap_env.py.{ui.Colors.RESET}", ui.Colors.LIGHT_BLUE, italic=True)
    ui.print_color("", ui.Colors.RESET)
    
    ui.print_color(f"  {ui.Colors.PINK_BG}{ui.Colors.BOLD}0{ui.Colors.RESET}  {ui.Colors.CYAN}Exit Menu{ui.Colors.RESET}", ui.Colors.MINT)
    ui.print_separator(char="*", color=ui.Colors.PINK, length=60)

def run_selected_script(script_path_str: str):
    project_root = Path(__file__).resolve().parent.parent
    absolute_script_path = project_root / script_path_str

    if not absolute_script_path.exists():
        ui.print_color(f"Script not found: {absolute_script_path}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        return

    ui.print_step_info(f"Attempting to run: {script_path_str}")
    ui.print_command_info(f"{sys.executable} {script_path_str}")
    
    spinner = ui.Spinner(f"Running {Path(script_path_str).name}...")
    process = None
    try:
        spinner.start()
        process = subprocess.run(
            [sys.executable, str(absolute_script_path)],
            cwd=project_root,
            check=False
        )
        spinner.stop()
        ui.print_separator(color=ui.Colors.LAVENDER)
        
        if process.returncode == 0:
            ui.print_color(f"{Path(script_path_str).name} finished successfully.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
        else:
            ui.print_color(f"{Path(script_path_str).name} exited with error code {process.returncode}.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)

    except KeyboardInterrupt:
        spinner.stop()
        ui.print_color(f"\nScript {Path(script_path_str).name} interrupted by user (Ctrl+C).", ui.Colors.YELLOW, prefix=ui.WARNING_SYMBOL)
    except Exception as e:
        spinner.stop()
        ui.print_color(f"An error occurred while trying to run {Path(script_path_str).name}: {e}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
    
    ui.prompt_input("Press Enter to return to the menu...", default="")

def reset_bootstrap_state():
    clear_screen()
    ui.print_section_header("Reset Bootstrap State")
    ui.print_step_info(f"This will attempt to remove state files from: {BOOTSTRAP_STATE_DIR}")
    ui.print_color("This allows the bootstrap_env.py script to run from the beginning.", ui.Colors.YELLOW)
    
    if not BOOTSTRAP_STATE_DIR.is_dir():
        ui.print_color(f"State directory {BOOTSTRAP_STATE_DIR} does not exist. Nothing to reset.", ui.Colors.GREEN, prefix=ui.INFO_SYMBOL)
        ui.prompt_input("Press Enter to return to the menu...", default="")
        return

    state_files = list(BOOTSTRAP_STATE_DIR.glob("*.complete"))

    if not state_files:
        ui.print_color(f"No state files (*.complete) found in {BOOTSTRAP_STATE_DIR}. Nothing to reset.", ui.Colors.GREEN, prefix=ui.INFO_SYMBOL)
    else:
        ui.print_color("The following state files will be targeted for removal:", ui.Colors.LAVENDER)
        for f_path in state_files:
            ui.print_color(f"  - {f_path}", ui.Colors.CYAN)
        
        if ui.prompt_yes_no("Attempt to remove these state files? This may require root privileges (e.g., via doas).", default_yes=False):
            ui.print_color("\nAttempting to remove files...", ui.Colors.YELLOW)
            all_removed_successfully = True
            for f_path in state_files:
                ui.print_command_info(f"Attempting: doas rm -f \"{f_path}\"")
                try:
                    # Using capture_output to prevent doas prompts from messing up spinner if active
                    # and to check stderr for errors.
                    result = subprocess.run(["doas", "rm", "-f", str(f_path)], capture_output=True, text=True, check=False)
                    if result.returncode == 0:
                        ui.print_color(f"  Successfully removed: {f_path}", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
                    else:
                        all_removed_successfully = False
                        ui.print_color(f"  Failed to remove: {f_path}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
                        if result.stderr:
                            ui.print_color(f"    Error: {result.stderr.strip()}", ui.Colors.ORANGE)
                        ui.print_color(f"    You may need to remove this file manually as root: rm -f \"{f_path}\"", ui.Colors.YELLOW)
                except FileNotFoundError:
                    all_removed_successfully = False
                    ui.print_color(f"  Command 'doas' not found. Cannot automatically remove {f_path}.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
                    ui.print_color(f"    Please remove manually as root: rm -f \"{f_path}\"", ui.Colors.YELLOW)
                except Exception as e:
                    all_removed_successfully = False
                    ui.print_color(f"  An unexpected error occurred trying to remove {f_path}: {e}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
                    ui.print_color(f"    Please remove manually as root: rm -f \"{f_path}\"", ui.Colors.YELLOW)

            if all_removed_successfully:
                ui.print_color("\nAll targeted state files have been processed.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
            else:
                ui.print_color("\nSome state files could not be automatically removed. See messages above.", ui.Colors.YELLOW, prefix=ui.WARNING_SYMBOL)
        else:
            ui.print_color("Bootstrap state reset cancelled.", ui.Colors.YELLOW, prefix=ui.INFO_SYMBOL)
            
    ui.prompt_input("Press Enter to return to the menu...", default="")

def main():
    valid_choices = set(SCRIPTS_TO_RUN.keys()) | {"0", "r", "R"}
    while True:
        clear_screen()
        display_menu()
        choice = ui.prompt_input(
            "Enter your choice",
            validator=lambda x: x in valid_choices
        ).strip()

        if not choice and "0" not in valid_choices :
             ui.print_color("Invalid choice. Please try again.", ui.Colors.PEACH, prefix=ui.WARNING_SYMBOL)
             time.sleep(1.5)
             continue

        if choice == "0":
            ui.print_color("Exiting menu. Goodbye! 💖", ui.Colors.PINK, bold=True)
            break
        elif choice.lower() == "r":
            reset_bootstrap_state()
        elif choice in SCRIPTS_TO_RUN:
            script_info = SCRIPTS_TO_RUN[choice]
            clear_screen()
            ui.print_section_header(f"Running: {script_info['name']}")
            run_selected_script(script_info["path"])
        else:
            ui.print_color("Invalid choice. Please select a valid option number or 'R'.", ui.Colors.PEACH, prefix=ui.WARNING_SYMBOL)
            time.sleep(1.5)

if __name__ == "__main__":
    main()