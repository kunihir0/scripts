#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Handles pre-chroot configurations, chroot script generation and execution,
and verification of the chrooted system configuration.
"""

import sys
import os # For os.chmod
from pathlib import Path
from typing import Dict, Any, List as TypingList, Optional
import subprocess # For subprocess.CompletedProcess type hint

# Attempt to import from sibling modules
try:
    from . import config as cfg
    from . import ui
    from . import core
except ImportError:
    print("Warning: Could not import sibling modules in chroot.py. Attempting absolute.", file=sys.stderr)
    try:
        import config as cfg # type: ignore
        import ui # type: ignore
        import core # type: ignore
    except ImportError as e:
        print(f"Error: Failed to import 'config', 'ui', or 'core' modules in chroot.py: {e}", file=sys.stderr)
        sys.exit(1)

def pre_chroot_file_configurations() -> None:
    """
    Configures files within the /mnt (target) system before entering chroot.
    This includes locale, hostname, vconsole, hosts, GDM auto-login, pacman/makepkg conf, etc.
    """
    ui.print_section_header("Pre-Chroot File Configurations")
    if cfg.get_current_step() > cfg.INSTALL_STEPS.index("pre_chroot_files"):
        ui.print_step_info("Skipping (already completed)")
        sys.stdout.write("\n"); return

    mnt_base: Path = Path("/mnt")
    user_config: Dict[str, Any] = cfg.get_all_user_config()

    # Locale and console
    core.write_file_dry_run(mnt_base / "etc/locale.gen", f"{user_config['locale_gen']}\n")
    core.write_file_dry_run(mnt_base / "etc/locale.conf", f"LANG={user_config['locale_lang']}\n")
    core.write_file_dry_run(mnt_base / "etc/vconsole.conf", f"KEYMAP={user_config['vconsole_keymap']}\n")

    # Hostname and hosts
    core.write_file_dry_run(mnt_base / "etc/hostname", f"{user_config['hostname']}\n")
    hosts_content: str = (
        f"127.0.0.1 localhost\n"
        f"::1       localhost\n"
        f"127.0.1.1 {user_config['hostname']}.localdomain {user_config['hostname']}\n"
    )
    core.write_file_dry_run(mnt_base / "etc/hosts", hosts_content)

    # Default editor
    editor_script_content: str = 'export EDITOR="nvim"\nexport VISUAL="nvim"\n'
    editor_script_path: Path = mnt_base / "etc/profile.d/editor.sh"
    core.write_file_dry_run(editor_script_path, editor_script_content)
    if not cfg.get_dry_run_mode():
        try:
            # Ensure the script is executable
            os.chmod(editor_script_path, 0o755)
        except Exception as e:
            ui.print_color(f"Error setting permissions for {editor_script_path}: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)


    # systemd-boot loader.conf
    loader_conf_content: str = "default arch-*\ntimeout 3\nconsole-mode max\neditor no\n"
    boot_efi_loader_path: Path = mnt_base / "boot/efi/loader"
    core.make_dir_dry_run(boot_efi_loader_path, parents=True, exist_ok=True)
    core.write_file_dry_run(boot_efi_loader_path / "loader.conf", loader_conf_content)

    # GDM auto-login
    gdm_conf_dir: Path = mnt_base / "etc/gdm"
    core.make_dir_dry_run(gdm_conf_dir, parents=True, exist_ok=True)
    gdm_custom_conf_content: str = f"[daemon]\nAutomaticLoginEnable=True\nAutomaticLogin={user_config['username']}\n"
    core.write_file_dry_run(gdm_conf_dir / "custom.conf", gdm_custom_conf_content)

    # Pacman configuration (enable Color)
    pacman_conf_path: Path = mnt_base / "etc/pacman.conf"
    if not cfg.get_dry_run_mode() and pacman_conf_path.exists():
        try:
            content: str = pacman_conf_path.read_text()
            if "#Color" in content:
                pacman_conf_path.write_text(content.replace("#Color", "Color"))
                ui.print_color(f"Enabled Color in {pacman_conf_path}", ui.Colors.MINT)
        except Exception as e:
            ui.print_color(f"Error modifying {pacman_conf_path} for Color: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

    # Makepkg configuration (CPU optimization, CFLAGS)
    makepkg_conf_path: Path = mnt_base / "etc/makepkg.conf"
    if not cfg.get_dry_run_mode() and makepkg_conf_path.exists():
        try:
            content: str = makepkg_conf_path.read_text()
            content = content.replace("-march=x86-64", f"-march={user_config['cpu_march']}") # Generic
            content = content.replace("CFLAGS=\"-march=native", f"CFLAGS=\"-march={user_config['cpu_march']}") # If native is set
            if "-O2" not in content: # Add -O2 if not present
                 content = content.replace("CFLAGS=\"", "CFLAGS=\"-O2 ")
            if "-pipe" not in content: # Add -pipe if not present
                 content = content.replace("CFLAGS=\"", "CFLAGS=\"-pipe ")
            content = content.replace("#CXXFLAGS=\"${CFLAGS}\"", "CXXFLAGS=\"${CFLAGS}\"") # Enable CXXFLAGS
            makepkg_conf_path.write_text(content)
            ui.print_color(f"Updated {makepkg_conf_path} with CPU optimizations.", ui.Colors.MINT)
        except Exception as e:
            ui.print_color(f"Error modifying {makepkg_conf_path} for CPU opts: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

    # ZRAM configuration
    zram_conf_content: str = f"[zram0]\nzram-fraction = {user_config['zram_fraction']}\ncompression-algorithm = zstd\n"
    # systemd-zram-generator expects conf in /etc/systemd/zram-generator.conf
    # or /usr/lib/systemd/zram-generator.conf. /etc takes precedence.
    zram_conf_dir: Path = mnt_base / "etc/systemd"
    core.make_dir_dry_run(zram_conf_dir, parents=True, exist_ok=True) # Ensure /etc/systemd exists
    core.write_file_dry_run(zram_conf_dir / "zram-generator.conf", zram_conf_content)


    # Dconf fractional scaling (GNOME)
    dconf_profile_dir: Path = mnt_base / "etc/dconf/profile"
    core.make_dir_dry_run(dconf_profile_dir, parents=True, exist_ok=True)
    dconf_db_locald_dir: Path = mnt_base / "etc/dconf/db/local.d"
    core.make_dir_dry_run(dconf_db_locald_dir, parents=True, exist_ok=True)
    core.make_dir_dry_run(mnt_base / "etc/dconf/db/locks", parents=True, exist_ok=True) # Locks dir
    core.write_file_dry_run(dconf_profile_dir / "user", "user-db:user\nsystem-db:local\n")
    core.write_file_dry_run(dconf_db_locald_dir / "00-hidpi-fractional-scaling", "[org/gnome/mutter]\nexperimental-features=['scale-monitor-framebuffer']\n")

    # Sudoers (enable wheel group with NOPASSWD for pacman)
    sudoers_d_dir: Path = mnt_base / "etc/sudoers.d"
    core.make_dir_dry_run(sudoers_d_dir, parents=True, exist_ok=True)
    sudoers_file_content: str = "%wheel ALL=(ALL:ALL) NOPASSWD: /usr/bin/pacman\n"
    sudoers_file_path: Path = sudoers_d_dir / "10-installer-wheel-nopasswd-pacman"
    
    # Also ensure the main sudoers file has the wheel group line uncommented for general sudo access (with password)
    # This is important if the user wants to sudo for commands other than pacman later.
    main_sudoers_path: Path = mnt_base / "etc/sudoers"
    if not cfg.get_dry_run_mode() and main_sudoers_path.exists():
        try:
            content: str = main_sudoers_path.read_text()
            target_line_commented: str = "# %wheel ALL=(ALL:ALL) ALL"
            target_line_uncommented: str = "%wheel ALL=(ALL:ALL) ALL"
            if target_line_commented in content:
                main_sudoers_path.write_text(content.replace(target_line_commented, target_line_uncommented))
                ui.print_color(f"Ensured wheel group is enabled in {main_sudoers_path}", ui.Colors.MINT)
            elif target_line_uncommented not in content:
                 ui.print_color(f"Warning: Could not find '{target_line_commented}' or '{target_line_uncommented}' in {main_sudoers_path}. Manual check advised.", ui.Colors.ORANGE)

        except Exception as e:
            ui.print_color(f"Error modifying {main_sudoers_path}: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

    core.write_file_dry_run(sudoers_file_path, sudoers_file_content)
    if not cfg.get_dry_run_mode():
        try:
            # sudoers.d files should have specific permissions
            os.chmod(sudoers_file_path, 0o440)
            ui.print_color(f"Configured NOPASSWD for pacman for wheel group via {sudoers_file_path.relative_to(mnt_base)}", ui.Colors.MINT)
        except Exception as e:
            ui.print_color(f"Error setting permissions for {sudoers_file_path}: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
            
    ui.print_color("Pre-chroot file configurations complete.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    cfg.set_current_step(cfg.INSTALL_STEPS.index("chroot_configure"))
    cfg.save_progress()
    sys.stdout.write("\n")


def _generate_and_write_chroot_script_content() -> Path:
    """
    Reads the chroot script template, substitutes configuration values,
    and writes it to /mnt/chroot_script.sh.
    Returns the relative path of the script within /mnt.
    """
    user_config: Dict[str, Any] = cfg.get_all_user_config()
    bao_password: str = str(cfg.BAO_PASSWORD)
    root_password: str = str(cfg.ROOT_PASSWORD)

    # Define the heredoc content that will be substituted into the template
    path_setup_bash_profile_heredoc: str = '''
PROFILE_TARGET_FILE="$USER_HOME/.bash_profile"
BASHRC_FILE="$USER_HOME/.bashrc"

# Create .bash_profile if it doesn't exist, and source .bashrc if that exists
if [ ! -f "$PROFILE_TARGET_FILE" ]; then
    if [ -f "$BASHRC_FILE" ]; then
        echo '[[ -f ~/.bashrc ]] && . ~/.bashrc' > "$PROFILE_TARGET_FILE"
    else
        # If no .bashrc, create a minimal .bash_profile
        echo '# ~/.bash_profile' > "$PROFILE_TARGET_FILE"
    fi
    chown __SETUP_USERNAME__:__SETUP_USERNAME__ "$PROFILE_TARGET_FILE"
fi

# Add .local/bin to PATH if not already there
if ! grep -q '$HOME/.local/bin' "$PROFILE_TARGET_FILE" >/dev/null 2>&1 ; then
  echo -e "\\n# Add .local/bin to PATH\\nif [ -d \\"$HOME/.local/bin\\" ] ; then\\n  PATH=\\"$HOME/.local/bin:$PATH\\"\\nfi" >> "$PROFILE_TARGET_FILE"
fi
'''

    # Determine the path to the template file
    # Assuming chroot.py is in arch/modules/ and template is in arch/scripts/
    try:
        # Path from this file (arch/modules/chroot.py) to project root (directory containing 'arch')
        project_root_dir = Path(__file__).resolve().parent.parent.parent
        template_path = project_root_dir / "arch" / "scripts" / "chroot_script_template.sh"
    except NameError: # __file__ is not defined (e.g. in interactive interpreter)
        # Fallback or error, this should not happen when run as a script/module
        ui.print_color("CRITICAL ERROR: Cannot determine script template path (__file__ not defined).", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        sys.exit(1)


    if not template_path.exists():
        ui.print_color(f"CRITICAL ERROR: Chroot script template not found at {template_path}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        sys.exit(1)

    try:
        chroot_script_content_template: str = template_path.read_text(encoding="utf-8")
    except Exception as e:
        ui.print_color(f"CRITICAL ERROR: Could not read chroot script template from {template_path}: {e}", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
        sys.exit(1)

    # Perform substitutions
    final_script: str = chroot_script_content_template

    # Substitute the heredoc first
    final_script = final_script.replace("{path_setup_bash_profile_heredoc}", path_setup_bash_profile_heredoc)

    # Substitute from USER_CONFIG
    for key, value in user_config.items():
        template_var: str = f"__SETUP_{key.upper()}__"
        # Ensure boolean values are lowercased strings for shell script logic (e.g., "true" or "false")
        str_value: str = str(value).lower() if isinstance(value, bool) else str(value)
        final_script = final_script.replace(template_var, str_value)

    # Substitute passwords
    final_script = final_script.replace("__SETUP_BAO_PASSWORD__", bao_password)
    final_script = final_script.replace("__SETUP_ROOT_PASSWORD__", root_password)
    
    # Substitute UI Colors (these are already hardcoded in the .sh template, so this is not strictly needed anymore
    # but kept for robustness if template changes or for other potential ui elements)
    # For example, if the template used {ui.Colors.RED}
    # This part can be removed if all colors are hardcoded in the .sh file.
    # For now, let's assume the .sh template has hardcoded ANSI codes.

    chroot_script_target_path_mounted: Path = Path("/mnt/chroot_script.sh")
    core.write_file_dry_run(chroot_script_target_path_mounted, final_script)
    if not cfg.get_dry_run_mode():
        try:
            os.chmod(chroot_script_target_path_mounted, 0o755) # Make it executable
        except Exception as e:
            ui.print_color(f"Error setting permissions for {chroot_script_target_path_mounted}: {e}", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)

    return chroot_script_target_path_mounted.relative_to("/mnt")


def chroot_configure_system() -> None:
    """
    Generates and executes a script within the chroot environment to configure the system.
    """
    ui.print_section_header("Configuring System (chroot)")
    if cfg.get_current_step() > cfg.INSTALL_STEPS.index("chroot_configure"):
        ui.print_step_info("Skipping (already completed)")
        sys.stdout.write("\n"); return

    relative_chroot_script_path: Path = _generate_and_write_chroot_script_content()
    ui.print_step_info(f"Executing generated chroot script: /{relative_chroot_script_path}")

    # Execute the script using arch-chroot
    core.run_command(
        ["arch-chroot", "/mnt", "/bin/bash", f"/{str(relative_chroot_script_path)}"],
        destructive=True,
        retry_count=1 # Chroot script itself should be idempotent or handle its own retries if needed
    )

    # Clean up the script from /mnt after execution
    core.unlink_file_dry_run(Path("/mnt") / relative_chroot_script_path)
    
    ui.print_color("System configuration in chroot complete.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    cfg.set_current_step(cfg.INSTALL_STEPS.index("cleanup")) # Assuming 'cleanup' is the next step
    cfg.save_progress()
    sys.stdout.write("\n")


def verify_chroot_configs(no_verify_arg: bool) -> None:
    """
    Verifies configurations made within the chroot environment.
    Checks hostname, locale, user existence, bootloader files, kernel/initramfs images.
    """
    if no_verify_arg:
        ui.print_step_info("Skipping chroot configuration verification as per --no-verify.")
        sys.stdout.write("\n"); return

    ui.print_section_header("Verifying Chroot Configuration")
    all_ok: bool = True
    user_config: Dict[str, Any] = cfg.get_all_user_config()
    mnt_base: Path = Path("/mnt")

    def _check_file_content(path_in_mnt_str: str, expected_content_part: str, check_name: str) -> bool:
        if cfg.get_dry_run_mode():
            ui.print_color(f"[DRY RUN] Assuming {check_name} at {path_in_mnt_str} would be correct.", ui.Colors.PEACH)
            return True
        file_path: Path = mnt_base / path_in_mnt_str
        if not file_path.exists():
            ui.print_color(f"{check_name}: File {file_path} does not exist.", ui.Colors.RED)
            return False
        try:
            content: str = file_path.read_text()
            return expected_content_part in content
        except Exception as e:
            ui.print_color(f"{check_name}: Error reading {file_path}: {e}", ui.Colors.RED)
            return False

    # Verify hostname
    if not core.verify_step(_check_file_content("etc/hostname", str(user_config["hostname"]), "Hostname"), "Hostname configuration", critical=True): all_ok = False
    # Verify locale.conf
    if not core.verify_step(_check_file_content("etc/locale.conf", f"LANG={user_config['locale_lang']}", "Locale config"), "Locale configuration", critical=True): all_ok = False
    # Verify user home directory
    user_home_path: Path = mnt_base / "home" / str(user_config["username"])
    if not core.verify_step(user_home_path.is_dir() if not cfg.get_dry_run_mode() else True, f"User home directory {user_home_path.relative_to(mnt_base)} exists", critical=True): all_ok = False
    
    # Verify systemd-boot entry
    boot_entry_path: Path = mnt_base / "boot/efi/loader/entries/arch-surface.conf"
    if not core.verify_step(boot_entry_path.exists() if not cfg.get_dry_run_mode() else True, "Systemd-boot entry file exists", critical=True): all_ok = False

    # Verify kernel, initramfs, and ucode images in /mnt/boot
    kernel_img_path: Path = mnt_base / "boot/vmlinuz-linux-surface"
    initramfs_img_path: Path = mnt_base / "boot/initramfs-linux-surface.img"
    intel_ucode_img_path: Path = mnt_base / "boot/intel-ucode.img"

    kernel_ok: bool = kernel_img_path.is_file() if not cfg.get_dry_run_mode() else True
    initramfs_ok: bool = initramfs_img_path.is_file() if not cfg.get_dry_run_mode() else True
    ucode_ok: bool = intel_ucode_img_path.is_file() if not cfg.get_dry_run_mode() else True

    if not core.verify_step(kernel_ok, f"Kernel image {kernel_img_path.relative_to(mnt_base)} exists", critical=True): all_ok = False
    if not core.verify_step(initramfs_ok, f"Initramfs image {initramfs_img_path.relative_to(mnt_base)} exists", critical=True): all_ok = False
    if not core.verify_step(ucode_ok, f"Intel ucode image {intel_ucode_img_path.relative_to(mnt_base)} exists", critical=False): # ucode might be optional for some setups
        ui.print_color(f"Intel ucode image {intel_ucode_img_path.relative_to(mnt_base)} missing. Bootloader entry might need adjustment if this is intended.", ui.Colors.ORANGE, prefix=ui.WARNING_SYMBOL)
        # all_ok remains true if ucode is missing but not critical for this check

    if not (kernel_ok and initramfs_ok) and not cfg.get_dry_run_mode():
        ui.print_color(f"Listing {mnt_base / 'boot'} contents for diagnostics:", ui.Colors.ORANGE)
        core.run_command(["ls", "-Alh", str(mnt_base / "boot")], capture_output=True, destructive=False, show_spinner=False)

    # Verify dconf fractional scaling file
    dconf_scaling_file: Path = mnt_base / "etc/dconf/db/local.d/00-hidpi-fractional-scaling"
    if not core.verify_step(dconf_scaling_file.exists() if not cfg.get_dry_run_mode() else True, "Dconf fractional scaling file exists", critical=False): all_ok = False # Not strictly critical for boot

    # Verify yay if Chaotic-AUR was added
    if user_config.get("add_chaotic_aur", False):
        yay_path: Path = mnt_base / "usr/bin/yay" # yay is typically installed here
        if not core.verify_step(yay_path.exists() if not cfg.get_dry_run_mode() else True, "yay AUR helper installed", critical=False): all_ok = False


    if all_ok:
        ui.print_color("Chroot configuration verification successful.", ui.Colors.GREEN, prefix=ui.SUCCESS_SYMBOL)
    else:
        ui.print_color("One or more chroot configuration verifications FAILED.", ui.Colors.RED, prefix=ui.ERROR_SYMBOL)
    sys.stdout.write("\n")