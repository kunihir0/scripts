#!/usr/bin/env python3

import subprocess
import sys
import time
from pathlib import Path
import shutil  # Added for getting terminal size
import itertools  # Added for rainbow text cycling
import os # Needed for geteuid check alternative

# --- Configuration ---
SDDM_CONF_DIR = Path("/etc/sddm.conf.d/")
SDDM_WAYLAND_CONF_FILE = SDDM_CONF_DIR / "10-wayland.conf"
ENVIRONMENT_D_DIR = Path("/etc/environment.d/")
KDE_WAYLAND_ENV_FILE = ENVIRONMENT_D_DIR / "90-kde-wayland.conf"
APT_PREFERENCES_D_DIR = Path("/etc/apt/preferences.d/")
NO_XORG_PREFERENCES_FILE = APT_PREFERENCES_D_DIR / "99-no-xorg-pulseaudio-gnomekeyring"

# --- UI Design Guide Implementation ---

# 256-color ANSI escape codes
COLORS = {
    "pink": "\033[38;5;219m",
    "purple": "\033[38;5;183m",
    "cyan": "\033[38;5;123m",
    "yellow": "\033[38;5;228m",
    "blue": "\033[38;5;111m",
    "orange": "\033[38;5;216m",
    "green": "\033[38;5;156m",
    "red": "\033[38;5;210m",
    "magenta": "\033[38;5;201m",
    "light_blue": "\033[38;5;159m",
    "lavender": "\033[38;5;147m",
    "peach": "\033[38;5;223m",
    "mint": "\033[38;5;121m",
    "dark": "\033[38;5;240m", # Dim color for empty progress bar
    "reset": "\033[0m",
    # Background colors (less used here)
    "bg_black": "\033[40m",
    "bg_purple": "\033[45m",
    "bg_cyan": "\033[46m",
    "bg_pink": "\033[48;5;219m",
    "bg_dark": "\033[48;5;236m",
}

# Text styling
STYLES = {
    "bold": "\033[1m",
    "italic": "\033[3m",
    "underline": "\033[4m",
    "blink": "\033[5m", # Use sparingly
    "reset": "\033[0m",
}

# Status Symbols
STATUS_SYMBOLS = {
    "success": "✓",
    "warning": "!",
    "error": "✗",
    "info": "✧",
    "progress": "→",
    "star": "★",
    "heart": "♥",
    "note": "•",
}

STATUS_COLORS = {
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "info": "cyan",
    "progress": "blue",
    "star": "purple",
    "heart": "pink",
    "note": "lavender",
}

# Spinner Character Sets
SPINNERS = {
    "flower": ["✿", "❀", "✾", "❁"],
    "star": ["✦", "✧", "✩", "✪"],
    "dots": ["⠋", "⠙", "⠹", "⠸"],
    "arrows": ["←", "↖", "↑", "↗"],
}

# Bubble characters for progress bar
BUBBLE_CHARS = ["○", "◌", "◍", "◎", "●", "◉"]
BUBBLE_COLORS = ["pink", "purple", "cyan", "yellow", "light_blue", "lavender"]

# Rainbow colors for text
RAINBOW_COLORS = ["red", "orange", "yellow", "green", "cyan", "blue", "purple", "pink"]


def color_text(text: str, color: str | None = None, styles: list[str] | None = None) -> str:
    """Applies ANSI color and styles to text."""
    color_code = COLORS.get(color, "")
    style_codes = "".join(STYLES.get(s, "") for s in styles) if styles else ""
    reset_code = COLORS["reset"] # Ensure reset happens even without color/style
    return f"{style_codes}{color_code}{text}{reset_code}"


def print_styled(
    message: str,
    color: str | None = None,
    styles: list[str] | None = None,
    status: str | None = None,
    end: str = "\n",
    flush: bool = True,
):
    """Prints a message with optional color, styles, and status symbol."""
    status_symbol = ""
    if status and status in STATUS_SYMBOLS:
        symbol = STATUS_SYMBOLS[status]
        status_color = STATUS_COLORS.get(status, "reset")
        # Add bold to status symbol for emphasis
        status_symbol = color_text(f"{symbol} ", color=status_color, styles=["bold"])

    print(f"{status_symbol}{color_text(message, color, styles)}", end=end, flush=flush)


def simple_spinner(message: str, spin_type: str = "dots", duration: float = 0.5):
    """Displays a simple spinner animation for a set duration."""
    spinner_chars = SPINNERS.get(spin_type, SPINNERS["dots"])
    enclosed_message = f"{message} "
    start_time = time.time()
    i = 0
    try:
        while (time.time() - start_time) < duration:
            char_color = RAINBOW_COLORS[i % len(RAINBOW_COLORS)]
            char = color_text(spinner_chars[i % len(spinner_chars)], color=char_color, styles=["bold"])
            print(f"\r{enclosed_message}{char}", end="", flush=True)
            time.sleep(0.1)
            i += 1
    finally:
        # Clear the spinner line
        print("\r" + " " * (len(enclosed_message) + 2) + "\r", end="", flush=True) # +2 for char and space


def get_terminal_size(default_size: tuple[int, int] = (80, 24)) -> tuple[int, int]:
    """Gets the current terminal size, returning a default on failure."""
    try:
        columns, lines = shutil.get_terminal_size()
        # Return 0 if dimensions are invalid/unknown (e.g., in some CI environments)
        return (columns or default_size[0], lines or default_size[1])
    except OSError:
        # Default size if unable to get terminal size
        return default_size


def rainbow_text(text: str) -> str:
    """Applies a rainbow color gradient to non-whitespace characters in text."""
    colored_text = []
    # Use a cyclical iterator for rainbow colors
    color_cycle = itertools.cycle(RAINBOW_COLORS)
    for char in text:
        if char.strip():  # Only color non-whitespace characters
            color = next(color_cycle)
            colored_text.append(color_text(char, color=color))
        else:
            colored_text.append(char)
    return "".join(colored_text)


def simulate_progress_animation(
    progress: float, message: str, bar_width: int = 50, animation_speed: float = 0.05
):
    """
    Displays an animated bubbly progress bar with rainbow text message.
    NOTE: This simulates progress; it doesn't track a real background task.
    """
    term_width, _ = get_terminal_size()

    # Ensure bar_width is not larger than terminal width minus message space
    # Adjust padding as needed
    message_len_no_ansi = len(message) # Approximate length without ANSI codes
    max_bar_width = term_width - message_len_no_ansi - 5  # Allow some padding
    bar_width = max(10, min(bar_width, max_bar_width)) # Ensure width is between 10 and max

    filled_width = int(bar_width * progress)
    empty_width = bar_width - filled_width

    # Create the bubbly filled part with animation cycling
    filled_bar_chars = []
    # Use time to make animation smoother and independent of loop index
    time_based_offset = int(time.time() * 10)
    for i in range(filled_width):
        bubble_char_index = (i + time_based_offset) % len(BUBBLE_CHARS)
        bubble_color_index = (i + time_based_offset) % len(BUBBLE_COLORS)
        bubble_char = BUBBLE_CHARS[bubble_char_index]
        bubble_color = BUBBLE_COLORS[bubble_color_index]
        filled_bar_chars.append(color_text(bubble_char, color=bubble_color))

    filled_bar = "".join(filled_bar_chars)

    # Create the empty part
    empty_bar = color_text("·" * empty_width, color="dark")

    # Apply rainbow effect to the message
    colored_message = rainbow_text(message)

    # Combine bar and message
    combined_output = f"[{filled_bar}{empty_bar}] {colored_message}"

    # Clear the current line and print the progress bar
    print("\r" + " " * term_width, end="\r")  # Clear line
    print(combined_output.ljust(term_width), end="", flush=True) # Pad to width to prevent artifacts
    time.sleep(animation_speed)  # Control animation speed


def display_progress_static(progress: float, message: str, bar_width: int = 50):
    """Displays a static bubbly progress bar with rainbow text message."""
    term_width, _ = get_terminal_size()

    message_len_no_ansi = len(message) # Approximate length without ANSI codes
    max_bar_width = term_width - message_len_no_ansi - 5
    bar_width = max(10, min(bar_width, max_bar_width))

    filled_width = int(bar_width * progress)
    # --- BUG FIX ---
    empty_width = bar_width - filled_width # Correct calculation

    # Create the bubbly filled part (static bubbles, cycling colors)
    filled_bar = ""
    bubble_char = BUBBLE_CHARS[-1] # Use the filled circle for static completed look
    for i in range(filled_width):
        bubble_color = BUBBLE_COLORS[i % len(BUBBLE_COLORS)]
        filled_bar += color_text(bubble_char, color=bubble_color)

    # Create the empty part
    empty_bar = color_text("·" * empty_width, color="dark")

    # Apply rainbow effect to the message
    colored_message = rainbow_text(message)

    # Combine bar and message
    combined_output = f"[{filled_bar}{empty_bar}] {colored_message}"

    # Clear the current line and print the progress bar
    print("\r" + " " * term_width, end="\r")  # Clear line
    print(combined_output.ljust(term_width), end="", flush=True) # Pad to width


def hide_cursor():
    """Hides the terminal cursor using ANSI escape codes."""
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()


def show_cursor():
    """Shows the terminal cursor using ANSI escape codes."""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


# --- Helper Function for Running Commands ---

def run_command(
    command: list[str],
    check: bool = True,
    capture_output: bool = False,
    text: bool = True,
    env: dict | None = None,
    show_stdout_on_success: bool = False # New flag
) -> subprocess.CompletedProcess:
    """
    Runs a command using subprocess.run with styled output and error handling.

    Args:
        command: Command and arguments as a list of strings.
        check: If True, raise CalledProcessError if the command returns non-zero exit code.
        capture_output: If True, capture stdout and stderr.
        text: If True, decode stdout/stderr as text (UTF-8).
        env: Optional dictionary of environment variables.
        show_stdout_on_success: If True, print stdout even on success (when not capturing).

    Returns:
        A subprocess.CompletedProcess instance.

    Raises:
        FileNotFoundError: If the command executable is not found.
        subprocess.CalledProcessError: If 'check' is True and the command fails.
        Exception: For other unexpected errors during subprocess execution.
    """
    cmd_str = " ".join(command)
    print_styled(f"Running: {cmd_str}", color="blue", styles=["italic"], status="progress")

    stdout_pipe = subprocess.PIPE if capture_output or show_stdout_on_success else subprocess.DEVNULL
    stderr_pipe = subprocess.PIPE # Always capture stderr to show on error

    try:
        result = subprocess.run(
            command,
            check=False,  # Check manually after potentially printing stderr
            capture_output=False, # We manage pipes manually
            stdout=stdout_pipe,
            stderr=stderr_pipe,
            text=text,
            env=env,
        )

        if result.returncode != 0:
            print_styled(
                f"Command failed (exit code {result.returncode}): {cmd_str}",
                color="red", status="error", styles=["bold"]
            )
            # Always print stderr on error if it exists
            if result.stderr:
                print_styled("--- Standard Error ---", color="red")
                print(result.stderr.strip())
                print_styled("--- End Stderr ---", color="red")
            if check:
                # Raise the error after printing details
                raise subprocess.CalledProcessError(
                    result.returncode, command, output=result.stdout, stderr=result.stderr
                )
        elif show_stdout_on_success and result.stdout:
            print_styled("--- Standard Output ---", color="green")
            print(result.stdout.strip())
            print_styled("--- End Stdout ---", color="green")


        return result
    except FileNotFoundError:
        print_styled(f"Error: Command '{command[0]}' not found.", color="red", status="error", styles=["bold"])
        raise
    except subprocess.CalledProcessError as e:
        # Error details already printed above if stderr exists
        raise
    except Exception as e:
        print_styled(f"An unexpected error occurred running command '{cmd_str}': {e}", color="red", status="error", styles=["bold"])
        raise


# --- Check for Root Privileges ---

def check_root() -> bool:
    """Checks if the script is run as root (UID 0). Skips check in Docker/venv."""
    print_styled("Checking execution environment...", color="cyan", status="info")

    # Skip check if in Docker
    if Path("/.dockerenv").exists():
        print_styled("Running in a Docker container. Skipping root check.", color="yellow", status="note")
        return True

    # Skip check if in a virtual environment (less critical, but common)
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        print_styled("Running in a virtual environment. Skipping root check.", color="yellow", status="note")
        return True

    # Check UID using os.geteuid() - more direct than subprocess
    try:
        if os.geteuid() == 0:
            print_styled("Running as root.", color="green", status="success")
            return True
        else:
            print_styled("This script requires root privileges.", color="red", status="error", styles=["bold"])
            print_styled("Please run using 'sudo'.", color="yellow")
            return False
    except AttributeError:
        # Fallback for systems without os.geteuid (unlikely on Linux)
        print_styled("Could not determine user ID using os.geteuid().", color="yellow", status="warning")
        print_styled("Attempting fallback using 'id -u'.", color="cyan")
        try:
            result = run_command(['id', '-u'], check=True, capture_output=True)
            uid = int(result.stdout.strip())
            if uid == 0:
                 print_styled("Running as root (confirmed via 'id -u').", color="green", status="success")
                 return True
            else:
                print_styled("This script requires root privileges (confirmed via 'id -u').", color="red", status="error", styles=["bold"])
                print_styled("Please run using 'sudo'.", color="yellow")
                return False
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as e:
            print_styled(f"Error checking root privileges via 'id -u': {e}", color="red", status="error")
            return False
    except Exception as e:
        print_styled(f"An unexpected error occurred while checking root privileges: {e}", color="red", status="error")
        return False

# --- System Check: Audit Packages ---

def audit_packages(packages: list[str]) -> tuple[bool, list[str]]:
    """
    Audits a list of packages using apt-cache policy to check for availability.

    Returns:
        A tuple: (bool indicating if all packages were found, list of missing packages).
    """
    print_styled("Auditing required packages availability...", color="blue", status="info")
    found_packages = []
    missing_packages = []
    apt_env = {"DEBIAN_FRONTEND": "noninteractive", "LANG": "C"} # Use LANG=C for predictable output

    for package in packages:
        print(f"Checking availability: {color_text(package, color='cyan')}...", end="", flush=True)
        try:
            # Use apt-cache policy. Output containing "Candidate:" means it's available.
            result = run_command(
                ['apt-cache', 'policy', package],
                check=False, # Don't fail the script if a package isn't found here
                capture_output=True,
                text=True,
                env=apt_env,
            )

            # Check stdout for candidate line. Handles packages that exist but have no installable candidate.
            if "Candidate:" in result.stdout and "(none)" not in result.stdout.split("Candidate:")[1].split("\n")[0]:
                print(color_text(" Available", color="green"))
                found_packages.append(package)
            else:
                print(color_text(" Not found/installable in repositories", color="yellow"))
                missing_packages.append(package)

        except FileNotFoundError:
            # Clear line before printing error
            print("\r" + " " * get_terminal_size()[0] + "\r", end="")
            print_styled("Error: 'apt-cache' command not found.", color="red", status="error", styles=["bold"])
            print_styled("Cannot audit packages. Ensure 'apt' is installed correctly.", color="red")
            return False, packages # Cannot audit, assume all might be missing
        except Exception as e:
            # Clear line before printing error
            print("\r" + " " * get_terminal_size()[0] + "\r", end="")
            print_styled(f"\nAn error occurred while auditing package {package}: {e}", color="red", status="error")
            missing_packages.append(package) # Assume missing if error occurs

    print_styled("\nPackage Audit Complete.", color="blue", styles=["bold"])
    if missing_packages:
        print_styled("The following packages were not found or lack installable candidates:", color="red", status="error", styles=["bold"])
        for package in missing_packages:
            print_styled(f" - {package}", color="red")
        print_styled("Please ensure APT sources in /etc/apt/sources.list(.d) are correct & run 'sudo apt update'.", color="yellow", status="warning")
        return False, missing_packages
    else:
        print_styled("All required packages seem available in repositories.", color="green", status="success")
        return True, []

# --- System Check: Verify Installed Packages ---
def verify_packages_installed(packages: list[str]) -> tuple[bool, list[str]]:
    """
    Verifies if packages are installed using dpkg-query.

    Returns:
        A tuple: (bool indicating if all packages verified, list of potentially missing packages).
    """
    print_styled("\nVerifying package installation status...", color="blue", status="info")
    missing_or_failed = []
    verified_count = 0

    for package in packages:
        try:
            # Check package status using dpkg-query
            # We capture output but don't need to show it unless debugging
            result = run_command(
                ['dpkg-query', '-W', '-f=${Status}', package],
                check=False, # Don't exit script if one check fails
                capture_output=True,
                text=True,
            )
            # Expected output for installed package contains "ok installed"
            if result.returncode == 0 and "ok installed" in result.stdout:
                # print_styled(f"Verified: {package}", color="mint") # Optional verbose success
                verified_count += 1
            else:
                 print_styled(f"Verification failed for package '{package}'. Status: {result.stdout.strip() if result.stdout else 'Not Found/Error'}", color="yellow", status="warning")
                 missing_or_failed.append(package)

        except FileNotFoundError:
             print_styled("Error: 'dpkg-query' command not found.", color="red", status="error")
             return False, packages # Cannot verify
        except Exception as e:
            print_styled(f"Error verifying package '{package}': {e}", color="yellow", status="warning")
            missing_or_failed.append(package)

    print_styled("\nPackage Verification Complete.", color="blue", styles=["bold"])
    if not missing_or_failed:
        print_styled(f"System check passed. All {verified_count} expected packages seem installed.", color="green", status="success")
        return True, []
    else:
        print_styled(f"System check found issues. {len(missing_or_failed)} package(s) might be missing or failed to install correctly:", color="red", status="error", styles=["bold"])
        for missing in missing_or_failed:
            print_styled(f" - {missing}", color="red")
        print_styled("Review the installation logs above for errors related to these packages.", color="yellow", status="warning")
        return False, missing_or_failed


# --- Configuration Steps ---

def configure_sddm():
    """Configures SDDM for Wayland session support."""
    print_styled("\nConfiguring SDDM for Wayland...", color="blue", status="info")
    sddm_conf_content = """[General]
# SDDM itself usually runs better on Xorg for now, but launches Wayland sessions.
# Uncommenting DisplayServer=wayland can be experimental.
# DisplayServer=wayland

[Wayland]
# Directory where Wayland sessions (.desktop files) are stored.
SessionDir=/usr/share/wayland-sessions
"""
    try:
        SDDM_CONF_DIR.mkdir(parents=True, exist_ok=True)
        SDDM_WAYLAND_CONF_FILE.write_text(sddm_conf_content)
        print_styled(f"SDDM Wayland config written to {SDDM_WAYLAND_CONF_FILE}", color="green", status="success")
    except OSError as e:
        print_styled(f"Error creating directory {SDDM_CONF_DIR}: {e}", color="red", status="error")
        raise # Re-raise to stop the script
    except Exception as e:
        print_styled(f"Failed to write SDDM Wayland configuration: {e}", color="red", status="error")
        raise


def enable_sddm_service():
    """Enables the SDDM service to start on boot."""
    print_styled("\nEnabling SDDM service...", color="blue", status="info")
    try:
        run_command(['systemctl', 'enable', 'sddm.service'])
        print_styled("SDDM service enabled successfully.", color="green", status="success")
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print_styled(f"Failed to enable SDDM service: {e}", color="red", status="error")
        print_styled("You may need to enable it manually: sudo systemctl enable sddm.service", color="yellow")
        # Allow script to continue but warn user
    except Exception as e:
        print_styled(f"An unexpected error occurred enabling SDDM: {e}", color="red", status="error")
        # Allow script to continue


def set_wayland_environment_vars():
    """Sets system-wide environment variables favoring Wayland."""
    print_styled("\nSetting environment variables for Wayland...", color="blue", status="info")
    environment_content = """# Force Wayland for KDE Plasma & Qt apps
QT_QPA_PLATFORM=wayland
# Force Wayland for GTK apps (most modern apps respect this)
GDK_BACKEND=wayland
# Force Wayland for Clutter apps (used by some older GNOME apps)
CLUTTER_BACKEND=wayland
# Enable Wayland backend for Firefox
MOZ_ENABLE_WAYLAND=1
# Enable Wayland backend for SDL apps (games, etc.)
SDL_VIDEODRIVER=wayland
# Explicitly set session type (usually handled by login manager/PAM)
# XDG_SESSION_TYPE=wayland
"""
    try:
        ENVIRONMENT_D_DIR.mkdir(parents=True, exist_ok=True)
        KDE_WAYLAND_ENV_FILE.write_text(environment_content)
        print_styled(f"Wayland environment variables written to {KDE_WAYLAND_ENV_FILE}", color="green", status="success")
    except OSError as e:
        print_styled(f"Error creating directory {ENVIRONMENT_D_DIR}: {e}", color="red", status="error")
        raise
    except Exception as e:
        print_styled(f"Failed to write Wayland environment variables: {e}", color="red", status="error")
        raise


def configure_apt_preferences():
    """Sets APT preferences to prevent installation of conflicting packages."""
    print_styled("\nSetting up APT preferences to avoid Xorg/PulseAudio/GNOME Keyring...", color="blue", status="info")
    apt_preferences_content = """# Prevent automatic installation of the main Xorg server package
Package: xserver-xorg-core
Pin: release *
Pin-Priority: -1

# Prevent automatic installation of xinit (less critical but avoids potential conflicts)
Package: xinit
Pin: release *
Pin-Priority: -1

# Prevent automatic installation of PulseAudio server (we prefer PipeWire)
Package: pulseaudio
Pin: release *
Pin-Priority: -1

# Prevent automatic installation of GNOME Keyring daemon (we use KWallet)
Package: gnome-keyring
Pin: release *
Pin-Priority: -1
"""
    try:
        APT_PREFERENCES_D_DIR.mkdir(parents=True, exist_ok=True)
        NO_XORG_PREFERENCES_FILE.write_text(apt_preferences_content)
        print_styled(f"APT preferences written to {NO_XORG_PREFERENCES_FILE}", color="green", status="success")
    except OSError as e:
        print_styled(f"Error creating directory {APT_PREFERENCES_D_DIR}: {e}", color="red", status="error")
        raise
    except Exception as e:
        print_styled(f"Failed to write APT preferences: {e}", color="red", status="error")
        raise

# --- Main Installation Logic ---

def main():
    """Main function to execute the installation script."""
    if not check_root():
        sys.exit(1)

    print_styled("\n" + "=" * 30, color="pink")
    print_styled(" Debian 12 KDE Plasma Wayland Installation ", color="pink", styles=["bold"])
    print_styled("=" * 30 + "\n", color="pink")

    apt_env = {"DEBIAN_FRONTEND": "noninteractive"}

    # --- System Update ---
    print_styled("STEP 1: Updating package lists and upgrading system...", color="purple", styles=["bold"])
    try:
        run_command(['apt', 'update'], env=apt_env)
        # Consider using 'apt full-upgrade' for potentially cleaner dependency handling
        run_command(['apt', 'upgrade', '-y'], env=apt_env)
        print_styled("System update/upgrade completed successfully.", color="green", status="success")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print_styled(f"System update failed: {e}. Exiting.", color="red", status="error")
        sys.exit(1)
    except Exception as e:
        print_styled(f"An unexpected error occurred during system update: {e}", color="red", status="error")
        sys.exit(1)


    # --- Install Basic Requirements ---
    print_styled("\nSTEP 2: Installing basic requirements...", color="purple", styles=["bold"])
    basic_packages = ['apt-transport-https', 'ca-certificates', 'curl', 'gnupg']
    try:
        run_command(['apt', 'install', '-y', '--no-install-recommends'] + basic_packages, env=apt_env)
        print_styled("Basic requirements installed.", color="green", status="success")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print_styled(f"Failed to install basic requirements: {e}. Exiting.", color="red", status="error")
        sys.exit(1)
    except Exception as e:
        print_styled(f"An unexpected error occurred installing basic requirements: {e}", color="red", status="error")
        sys.exit(1)

    # --- Define KDE Plasma Wayland Packages ---
    print_styled("\nSTEP 3: Defining KDE Plasma Wayland package list...", color="purple", styles=["bold"])
    # Using tasksel's list as a base and refining for Wayland/minimal
    packages_to_install = [
        # Core Desktop & Wayland compositor
        'plasma-desktop',       # Metapackage for core desktop
        'kwin-wayland',         # KWin Wayland compositor + backends
        'plasma-workspace-wayland', # Wayland integration specifics

        # Login Manager
        'sddm',                 # Recommended display manager for Plasma
        'sddm-theme-breeze',    # Default theme matching Plasma

        # Essential KDE Applications
        'dolphin',              # File manager
        'konsole',              # Terminal emulator
        'kate',                 # Advanced text editor
        'ark',                  # Archiving tool
        'gwenview',             # Image viewer

        # System Tools & Configuration
        'systemsettings',       # KDE System Settings panel
        'plasma-nm',            # NetworkManager applet
        'plasma-pa',            # PulseAudio/PipeWire volume applet (works with pipewire-pulse)
        'powerdevil',           # Power management service
        'kscreen',              # Screen management (randr/kwayland backend)
        'bluedevil',            # Bluetooth integration
        'plasma-discover',      # Software center (optional, but common)
        'plasma-systemmonitor', # System monitor tool
        'kwalletmanager',       # KDE Wallet management tool
        'libpam-kwallet5',      # PAM module for auto-unlocking wallet on login

        # Integration & Backend
        'kde-config-sddm',      # Configure SDDM from System Settings
        'kde-config-gtk-style', # Apply Breeze theme to GTK apps
        'xdg-desktop-portal-kde', # Needed for Flatpak/snap integration on Plasma
        'pipewire',             # Core PipeWire daemon
        'pipewire-audio',       # Base PipeWire audio support metapackage
        'pipewire-pulse',       # PipeWire's replacement for PulseAudio server
        'wireplumber',          # PipeWire session manager (recommended)
        'libspa-0.2-bluetooth', # Bluetooth audio support via PipeWire
        'phonon4qt5-backend-gstreamer', # Multimedia backend for KDE apps
        'qtwayland5',           # Qt Wayland platform plugin
        'qt5-style-plugins',    # For Breeze GTK theme consistency

        # Utilities & Fonts
        'wl-clipboard',         # Command-line Wayland clipboard tool
        'print-manager',        # Printer management UI
        'cups',                 # Printing system daemon
        'baloo-kf5',            # File indexing service
        'fonts-noto',           # Recommended Noto fonts for broad Unicode coverage
        'fonts-noto-color-emoji',# Noto Color Emoji font
        'fonts-hack',           # Good monospace font for Konsole/Kate
        'breeze-icon-theme',    # Default icon theme
        'breeze-gtk-theme',     # Breeze theme for GTK2/GTK3 apps

        # Hardware & Firmware (essential - add non-free if needed)
        'network-manager',      # Network management daemon
        'bluetooth',            # Bluetooth stack
        'firmware-linux-free',  # Common free firmware blobs
        # Consider adding: firmware-linux-nonfree, firmware-misc-nonfree,
        # intel-microcode/amd64-microcode depending on hardware
    ]
    print_styled(f"Defined {len(packages_to_install)} packages for installation.", color="cyan")


    # --- Perform Package Audit ---
    print_styled("\nSTEP 4: Auditing package availability...", color="purple", styles=["bold"])
    packages_available, missing_audit_pkgs = audit_packages(packages_to_install)
    if not packages_available:
        print_styled("Package audit failed. Cannot proceed.", color="red", status="error", styles=["bold"])
        sys.exit(1)


    # --- Install Packages with Simulated Progress ---
    print_styled("\nSTEP 5: Installing KDE Plasma Wayland packages...", color="purple", styles=["bold"])
    print_styled("(Progress bar simulates steps before the main 'apt install' command)", color="yellow", status="note")
    hide_cursor()
    total_packages = len(packages_to_install)
    installation_success = False
    try:
        # Simulate progress visually before running the single apt command
        for i, package in enumerate(packages_to_install):
            progress = (i + 0.5) / total_packages # Mid-point progress for the simulated step
            message = f"Preparing {package} ({i+1}/{total_packages})"
            # Animate briefly for each package 'step'
            start_time = time.time()
            while (time.time() - start_time) < 0.1: # Very short animation per simulated step
                simulate_progress_animation(progress, message, animation_speed=0.05)

        # Display near-complete bar before actual install
        display_progress_static(0.99, f"Running apt install for {total_packages} packages...")
        print("\n") # Move to the next line for apt output

        # Run the actual installation command
        run_command(
            ['apt', 'install', '-y', '--no-install-recommends'] + packages_to_install,
            env=apt_env,
            show_stdout_on_success=True # Show apt output
        )

        # Final static progress update to 100%
        display_progress_static(1.0, "APT installation command finished!")
        print("\n") # Move to the next line
        print_styled("KDE Plasma Wayland package installation command completed.", color="green", status="success")
        installation_success = True # Mark as potentially successful

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("\n") # Ensure we are on a new line after progress bar/apt output
        print_styled(f"Package installation failed: {e}", color="red", status="error")
        # Verification step will confirm what's missing
    except Exception as e:
        print("\n")
        print_styled(f"An unexpected error occurred during package installation: {e}", color="red", status="error")
    finally:
        show_cursor() # Ensure cursor is always shown


    # --- Verify Package Installation ---
    print_styled("\nSTEP 6: Verifying package installation...", color="purple", styles=["bold"])
    all_verified, missing_pkgs = verify_packages_installed(packages_to_install)

    if not installation_success:
         print_styled("Installation command failed previously. Verification may show many missing packages.", color="yellow", status="warning")
         # Decide if we should exit immediately if apt install failed
         # sys.exit(1)

    if not all_verified:
        print_styled("Verification check failed. Some packages may not be installed correctly.", color="red", status="error", styles=["bold"])
        print_styled("The system might not function as expected.", color="yellow")
        # Exit here because a failed verification indicates a broken install
        sys.exit(1)
    else:
        print_styled("Package verification successful.", color="green", status="success")


    # --- Configuration Steps ---
    print_styled("\nSTEP 7: Applying system configurations...", color="purple", styles=["bold"])
    try:
        configure_sddm()
        enable_sddm_service()
        set_wayland_environment_vars()
        configure_apt_preferences()
        print_styled("\nSystem configuration applied successfully.", color="green", status="success")
    except Exception as e:
        # Errors are printed within the functions
        print_styled(f"Configuration failed: {e}. Exiting.", color="red", status="error", styles=["bold"])
        sys.exit(1)

    # --- Final Messages ---
    print_styled("\n" + "=" * 30, color="pink")
    print_styled(" Installation Script Finished! ", color="pink", styles=["bold"])
    print_styled("=" * 30 + "\n", color="pink")

    print_styled("Important Next Steps & Notes:", color="blue", styles=["bold", "underline"])
    print_styled("1. Reboot Required:", color="yellow", status="warning")
    print_styled("   A system reboot is necessary to apply all changes (kernel, services, environment variables).", color="cyan")

    print_styled("2. Login Screen:", color="yellow", status="note")
    print_styled("   After rebooting, on the SDDM login screen, ensure you select the", color="cyan")
    print_styled("   'Plasma (Wayland)' session from the session menu (often a gear or dropdown).", color="cyan")

    print_styled("3. Hardware Drivers:", color="yellow", status="note")
    print_styled("   - Ensure your graphics drivers (Intel, AMD, NVIDIA) support Wayland.", color="cyan")
    print_styled("   - NVIDIA proprietary drivers require specific setup for Wayland.", color="cyan")
    print_styled("   - You might need non-free firmware. Edit '/etc/apt/sources.list' to add", color="cyan")
    print_styled("     'contrib non-free non-free-firmware' components, then run:", color="cyan")
    print_styled("     sudo apt update && sudo apt install firmware-linux-nonfree firmware-misc-nonfree", color="mint", styles=["italic"])
    print_styled("     (Install other specific firmware like 'firmware-iwlwifi' if needed).", color="cyan")

    print_styled("4. PipeWire Audio:", color="yellow", status="note")
    print_styled("   PipeWire should now handle audio. Check volume controls and pavucontrol (if installed)", color="cyan")
    print_styled("   if you encounter audio issues.", color="cyan")

    # --- Ask About Rebooting ---
    print_styled("\nReboot recommended.", color="green", styles=["bold"])
    try:
        reboot_choice = input(color_text("Do you want to reboot now? (y/N): ", color="yellow")).strip().lower()
        if reboot_choice == "y":
            print_styled("Rebooting system...", color="blue", status="info")
            # Short delay before reboot command
            simple_spinner("Rebooting in 3s ", duration=3, spin_type="star")
            run_command(['systemctl', 'reboot'])
        else:
            print_styled("Reboot cancelled. Please reboot manually later.", color="blue", status="note")
    except (EOFError, KeyboardInterrupt): # Handle Ctrl+C or Ctrl+D during input
         print("\nReboot prompt cancelled.")
         print_styled("Please reboot manually later.", color="blue", status="note")
    except Exception as e:
        print_styled(f"Failed to initiate reboot: {e}. Please reboot manually.", color="red", status="error")

if __name__ == "__main__":
    main()
