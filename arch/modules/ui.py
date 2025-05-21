#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handles UI elements, color definitions, and styled printing for the Arch Linux installer.
"""

import sys
import threading
import time
from typing import Optional, List as TypingList, Callable # Renamed to avoid conflict with Spinner's List

class Colors:
    """ANSI escape codes for terminal colors."""
    PINK: str = '\033[38;5;219m'
    PURPLE: str = '\033[38;5;183m'
    CYAN: str = '\033[38;5;123m'
    YELLOW: str = '\033[38;5;228m'
    BLUE: str = '\033[38;5;111m'
    ORANGE: str = '\033[38;5;216m'
    GREEN: str = '\033[38;5;156m'
    RED: str = '\033[38;5;210m'
    MAGENTA: str = '\033[38;5;201m'
    LIGHT_BLUE: str = '\033[38;5;159m'
    LAVENDER: str = '\033[38;5;147m'
    PEACH: str = '\033[38;5;223m'
    MINT: str = '\033[38;5;121m'
    PINK_BG: str = '\033[48;5;219m'
    DARK_BG: str = '\033[48;5;236m'
    BOLD: str = '\033[1m'
    ITALIC: str = '\033[3m'
    UNDERLINE: str = '\033[4m'
    BLINK: str = '\033[5m'
    RESET: str = '\033[0m'

SUCCESS_SYMBOL: str = f"{Colors.GREEN}✓{Colors.RESET}"
WARNING_SYMBOL: str = f"{Colors.YELLOW}!{Colors.RESET}"
ERROR_SYMBOL: str = f"{Colors.RED}✗{Colors.RESET}"
INFO_SYMBOL: str = f"{Colors.CYAN}✧{Colors.RESET}"
PROGRESS_SYMBOL: str = f"{Colors.BLUE}→{Colors.RESET}"
NOTE_SYMBOL: str = f"{Colors.LAVENDER}•{Colors.RESET}"
STAR_SYMBOL: str = f"{Colors.PURPLE}★{Colors.RESET}"

def print_color(
    text: str,
    color: str,
    bold: bool = False,
    prefix: Optional[str] = None,
    italic: bool = False
) -> None:
    """Prints text in a specified color and style."""
    style_str: str = (Colors.BOLD if bold else "") + (Colors.ITALIC if italic else "")
    prefix_str: str = f"{prefix} " if prefix else ""
    sys.stdout.write(f"{prefix_str}{style_str}{color}{text}{Colors.RESET}\n")
    sys.stdout.flush()

def print_header(title: str) -> None:
    """Prints a main section header."""
    print_color(f"❄️ === {title} === ❄️", Colors.PINK_BG + Colors.CYAN + Colors.BOLD)
    sys.stdout.write("\n")
    sys.stdout.flush()

def print_section_header(title: str) -> None:
    """Prints a subsection header with a gradient effect."""
    gradient_colors: TypingList[str] = [Colors.PINK, Colors.PURPLE, Colors.CYAN, Colors.BLUE, Colors.MAGENTA]
    styled_title: str = "".join(
        f"{gradient_colors[i % len(gradient_colors)]}{char}" for i, char in enumerate(title)
    )
    print_color(f"--- {styled_title}{Colors.RESET} ---", Colors.PURPLE, bold=True, prefix=STAR_SYMBOL)
    sys.stdout.write("\n")
    sys.stdout.flush()

def print_step_info(message: str) -> None:
    """Prints an informational message for a step."""
    print_color(message, Colors.LIGHT_BLUE, prefix=INFO_SYMBOL)

def print_command_info(cmd_str: str) -> None:
    """Prints information about a command being executed."""
    print_color(f"Executing: {cmd_str}", Colors.CYAN, prefix=PROGRESS_SYMBOL)

def print_dry_run_command(cmd_str: str) -> None:
    """Prints information about a command that would be executed in dry run mode."""
    print_color(f"Would execute: {cmd_str}", Colors.PEACH, prefix=f"{Colors.YELLOW}[DRY RUN]{Colors.RESET}")

class Spinner:
    """A simple CLI spinner."""
    def __init__(
        self,
        message: str = "Processing...",
        delay: float = 0.1,
        spinner_chars: Optional[TypingList[str]] = None
    ) -> None:
        self.spinner_chars: TypingList[str] = spinner_chars if spinner_chars else ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.delay: float = delay
        self.message: str = message
        self._thread: Optional[threading.Thread] = None
        self.running: bool = False

    def _spin(self) -> None:
        idx: int = 0
        while self.running:
            spinner_char: str = self.spinner_chars[idx % len(self.spinner_chars)]
            sys.stdout.write(f"\r{Colors.LIGHT_BLUE}{spinner_char}{Colors.RESET} {self.message} ")
            sys.stdout.flush()
            time.sleep(self.delay)
            idx += 1
        # Clear the spinner line
        sys.stdout.write(f"\r{' ' * (len(self.message) + 5)}\r")
        sys.stdout.flush()

    def start(self) -> None:
        """Starts the spinner animation in a separate thread."""
        if sys.stdout.isatty(): # Only run spinner if in a TTY
            self.running = True
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stops the spinner animation."""
        if self.running:
            self.running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=self.delay * 2) # Wait for thread to finish
        # Ensure the line is cleared even if spinner wasn't running or thread finished quickly
        sys.stdout.write(f"\r{' ' * (len(self.message) + 5)}\r")
        sys.stdout.flush()

def prompt_yes_no(question: str, default_yes: bool = False) -> bool:
    """Prompts the user for a yes/no answer."""
    suffix: str = f" [{Colors.PINK}Y{Colors.LAVENDER}/n{Colors.LAVENDER}]" if default_yes else f" [{Colors.LAVENDER}y/{Colors.PINK}N{Colors.LAVENDER}]"
    while True:
        try:
            reply: str = input(f"{Colors.LAVENDER}{question}{suffix}: {Colors.RESET}").strip().lower()
            if not reply:
                return default_yes
            if reply in ['y', 'yes']:
                return True
            if reply in ['n', 'no']:
                return False
            print_color("Invalid input. Please enter 'y' or 'n'.", Colors.ORANGE, prefix=WARNING_SYMBOL)
        except KeyboardInterrupt:
            print_color("\nInput cancelled by user.", Colors.ORANGE, prefix=WARNING_SYMBOL)
            return False # Or raise custom exception
        except EOFError:
            print_color("\nInput stream ended.", Colors.ORANGE, prefix=WARNING_SYMBOL)
            return False # Or raise custom exception


def prompt_input(
    question: str,
    default: Optional[str] = None,
    validator: Optional[Callable[[str], bool]] = None, # type: ignore
    sensitive: bool = False
) -> str:
    """Prompts the user for input with optional default and validation."""
    # Note: 'getpass' module would be better for sensitive input if available/allowed
    suffix: str = f" (default: {Colors.CYAN}{default}{Colors.MINT})" if default and not sensitive else ""
    prompt_text: str = f"{Colors.MINT}{question}{suffix}: {Colors.RESET}"
    while True:
        try:
            reply: str = input(prompt_text).strip() if not sensitive else input(prompt_text) # Basic sensitive handling
            if reply:
                if validator and not validator(reply):
                    continue # Validator should print its own error message
                return reply
            if default is not None:
                if validator and not validator(default):
                    # This case should ideally not happen if defaults are pre-validated
                    print_color("Default value is invalid, this is a script bug.", Colors.RED, prefix=ERROR_SYMBOL)
                    # sys.exit(1) # Or raise an error
                    continue # Or ask again
                return default
            print_color("Input cannot be empty.", Colors.ORANGE, prefix=WARNING_SYMBOL)
        except KeyboardInterrupt:
            print_color("\nInput cancelled by user.", Colors.ORANGE, prefix=WARNING_SYMBOL)
            # Potentially re-raise or return a specific value indicating cancellation
            if default is not None: return default # Or handle as error
            print_color("Input required, cannot proceed without it.", Colors.RED, prefix=ERROR_SYMBOL)
            # sys.exit(1) # Or raise
            continue # Or return a specific marker
        except EOFError:
            print_color("\nInput stream ended.", Colors.ORANGE, prefix=WARNING_SYMBOL)
            if default is not None: return default
            print_color("Input required, cannot proceed without it.", Colors.RED, prefix=ERROR_SYMBOL)
            # sys.exit(1) # Or raise
            continue