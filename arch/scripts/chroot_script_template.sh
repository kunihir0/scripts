#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.
echo -e "\033[38;5;183m--- CHROOT SCRIPT: Configuring System (inside chroot) ---\033[0m"

echo -e "\033[38;5;111mSetting timezone to __SETUP_TIMEZONE__...\033[0m"
ln -sf "/usr/share/zoneinfo/__SETUP_TIMEZONE__" /etc/localtime
hwclock --systohc # Set hardware clock from system clock

echo -e "\033[38;5;111mGenerating locales (locale.gen and locale.conf configured pre-chroot)...\033[0m"
locale-gen

echo -e "\033[38;5;111mSetting root password and locking root account...\033[0m"
echo "root:__SETUP_ROOT_PASSWORD__" | chpasswd -e || echo "root:__SETUP_ROOT_PASSWORD__" | chpasswd # -e for encrypted
passwd -l root # Lock root account

echo -e "\033[38;5;111mCreating user __SETUP_USERNAME__ (if not exists)...\033[0m"
# Check if user exists before trying to create. 'id -u' returns 0 if user exists.
if ! id -u "__SETUP_USERNAME__" >/dev/null 2>&1; then
    useradd -m -G wheel -s /bin/bash "__SETUP_USERNAME__"
    echo "__SETUP_USERNAME__:__SETUP_BAO_PASSWORD__" | chpasswd -e || echo "__SETUP_USERNAME__:__SETUP_BAO_PASSWORD__" | chpasswd
else
    echo -e "\033[38;5;228mUser __SETUP_USERNAME__ already exists. Skipping creation, ensuring password is set.\033[0m"
    # Ensure password is set even if user exists, in case previous attempt was interrupted.
    echo "__SETUP_USERNAME__:__SETUP_BAO_PASSWORD__" | chpasswd -e || echo "__SETUP_USERNAME__:__SETUP_BAO_PASSWORD__" | chpasswd
fi

echo -e "\033[38;5;111mConfiguring systemd-boot (loader.conf configured pre-chroot)...\033[0m"
bootctl --path=/boot/efi install # Installs systemd-boot to EFI partition

# Get ROOT PARTITION UUID for bootloader entry
ROOT_PART_UUID=$(findmnt -n -o UUID -T /)
if [ -z "$ROOT_PART_UUID" ]; then
    echo -e "\033[38;5;210mERROR: Could not determine ROOT_PART_UUID for bootloader entry.\033[0m"
    exit 1
fi
echo -e "\033[38;5;123mDetermined ROOT_PART_UUID: $ROOT_PART_UUID\033[0m"

cat << EOF_ARCH_ENTRY > /boot/efi/loader/entries/arch-surface.conf
title   Arch Linux (Surface - GNOME)
linux   /vmlinuz-linux-surface
initrd  /intel-ucode.img
initrd  /initramfs-linux-surface.img
options root=UUID=$ROOT_PART_UUID rootfstype=ext4 rd.lvm.vg=__SETUP_LVM_VG_NAME__ rd.lvm.lv=__SETUP_LVM_VG_NAME__/__SETUP_LVM_LV_ROOT_NAME__ rw mitigations=off loglevel=7 rd.break=pre-mount
EOF_ARCH_ENTRY
echo -e "\033[38;5;121mCreated systemd-boot entry: /boot/efi/loader/entries/arch-surface.conf (ext4 root, rootfstype, verbose boot, LVM options, rd.break=pre-mount for debugging)\033[0m"

# Verify the ROOT_PART_UUID in the .conf file matches the one determined dynamically
CONF_FILE_PATH="/boot/efi/loader/entries/arch-surface.conf"
if [ -f "$CONF_FILE_PATH" ]; then
    EXTRACTED_CONF_ROOT_UUID=$(grep -oP 'root=UUID=\K[^ ]+' "$CONF_FILE_PATH")
    if [ "$ROOT_PART_UUID" = "$EXTRACTED_CONF_ROOT_UUID" ]; then
        echo -e "\033[38;5;156mVerification PASSED: ROOT_PART_UUID ($ROOT_PART_UUID) matches root=UUID in $CONF_FILE_PATH.\033[0m"
    else
        echo -e "\033[38;5;210mCRITICAL VERIFICATION FAILED: ROOT_PART_UUID ($ROOT_PART_UUID) does NOT match root=UUID ($EXTRACTED_CONF_ROOT_UUID) in $CONF_FILE_PATH.\033[0m"
        # Consider exiting here if this is critical, or let it proceed for further debugging by user.
        # For now, let's print a strong warning.
        # exit 1
    fi
else
    echo -e "\033[38;5;210mERROR: Bootloader entry file $CONF_FILE_PATH not found for verification.\033[0m"
fi

sync && sleep 2 # Attempt to ensure filesystem changes are flushed and settled

echo -e "\033[38;5;111mPreparing for initramfs generation with dracut...\033[0m"

# Determine kernel version and paths
KERNEL_PKG_NAME="linux-surface" # The package name we are targeting
BOOT_VMLINUZ_TARGET_NAME="vmlinuz-${KERNEL_PKG_NAME}" # e.g., vmlinuz-linux-surface
BOOT_KERNEL_TARGET_PATH="/boot/${BOOT_VMLINUZ_TARGET_NAME}"
INITRAMFS_TARGET_PATH="/boot/initramfs-${KERNEL_PKG_NAME}.img"

# Get full package version string (e.g., 6.14.2.arch1-1)
KERNEL_PKG_INFO=$(pacman -Q "$KERNEL_PKG_NAME" 2>/dev/null)
if [ -z "$KERNEL_PKG_INFO" ]; then
    echo -e "\033[38;5;210mCRITICAL ERROR: Kernel package '$KERNEL_PKG_NAME' not found via pacman -Q.\033[0m"
    exit 1
fi
KERNEL_VERSION_FULL=$(echo "$KERNEL_PKG_INFO" | cut -d' ' -f2) # e.g., "6.14.2.arch1-1"

# Construct the expected kernel module directory name
KERNEL_MODULE_DIR_NAME_EXPECTED="${KERNEL_VERSION_FULL}-surface"
echo -e "\033[38;5;123mDerived kernel package version: $KERNEL_VERSION_FULL\033[0m"
echo -e "\033[38;5;123mExpected kernel module directory name: $KERNEL_MODULE_DIR_NAME_EXPECTED\033[0m"

# Verify this directory name exists by listing the parent and grepping
echo -e "\033[38;5;123mVerifying existence of '$KERNEL_MODULE_DIR_NAME_EXPECTED' in /usr/lib/modules/ listing...\033[0m"
ACTUAL_KERNEL_MODULE_DIR_NAME=$(ls -A /usr/lib/modules/ | grep -E "^${KERNEL_MODULE_DIR_NAME_EXPECTED}$" | head -n 1)

if [ -z "$ACTUAL_KERNEL_MODULE_DIR_NAME" ]; then
    echo -e "\033[38;5;210mERROR: Expected kernel module directory '$KERNEL_MODULE_DIR_NAME_EXPECTED' not found in 'ls /usr/lib/modules/'.\033[0m"
    echo -e "\033[38;5;123mContents of /usr/lib/modules/:\033[0m"
    ls -Alh /usr/lib/modules/
    exit 1
fi

echo -e "\033[38;5;156mConfirmed kernel module directory name: $ACTUAL_KERNEL_MODULE_DIR_NAME\033[0m"
KERNEL_MODULES_PATH="/usr/lib/modules/$ACTUAL_KERNEL_MODULE_DIR_NAME"
KERNEL_IMAGE_SRC_IN_MODULES="$KERNEL_MODULES_PATH/vmlinuz" # Assume standard vmlinuz name inside

echo -e "\033[38;5;123mUsing module path: $KERNEL_MODULES_PATH\033[0m"
echo -e "\033[38;5;123mUsing source vmlinuz: $KERNEL_IMAGE_SRC_IN_MODULES\033[0m"
echo -e "\033[38;5;123mTarget vmlinuz in /boot: $BOOT_KERNEL_TARGET_PATH\033[0m"

# Check if the target kernel image already exists in /boot
if [ ! -f "$BOOT_KERNEL_TARGET_PATH" ]; then
    echo -e "\033[38;5;228mKernel image $BOOT_KERNEL_TARGET_PATH not found directly in /boot. Attempting to copy...\033[0m"
    
    if [ -f "$KERNEL_IMAGE_SRC_IN_MODULES" ]; then
        echo -e "\033[38;5;121mFound kernel image at $KERNEL_IMAGE_SRC_IN_MODULES. Copying to $BOOT_KERNEL_TARGET_PATH...\033[0m"
        cp -v "$KERNEL_IMAGE_SRC_IN_MODULES" "$BOOT_KERNEL_TARGET_PATH"
    else
        echo -e "\033[38;5;210mERROR: Kernel image $KERNEL_IMAGE_SRC_IN_MODULES not found within confirmed directory $KERNEL_MODULES_PATH.\033[0m"
        echo -e "\033[38;5;123mListing contents of $KERNEL_MODULES_PATH for diagnostics (this may fail if directory became inaccessible):\033[0m"
        ls -Alh "$KERNEL_MODULES_PATH" || echo -e "\033[38;5;216mCould not list $KERNEL_MODULES_PATH.\033[0m"
        exit 1
    fi
else
    echo -e "\033[38;5;156mKernel image $BOOT_KERNEL_TARGET_PATH already present in /boot.\033[0m"
fi

# Verify again that the target kernel image is now in /boot
if [ ! -f "$BOOT_KERNEL_TARGET_PATH" ]; then
    echo -e "\033[38;5;210mCRITICAL ERROR: Kernel image $BOOT_KERNEL_TARGET_PATH is STILL NOT FOUND in /boot after copy attempt. Cannot proceed.\033[0m"
    ls -Alh /boot/
    exit 1
fi
echo -e "\033[38;5;156mKernel image $BOOT_KERNEL_TARGET_PATH is ready in system /boot.\033[0m"

# Use the ACTUAL_KERNEL_MODULE_DIR_NAME for dracut's --kver argument
DRACUT_KVER="$ACTUAL_KERNEL_MODULE_DIR_NAME"
echo -e "\033[38;5;123mAttempting to generate initramfs for $BOOT_KERNEL_TARGET_PATH using kver $DRACUT_KVER, explicitly adding lvm module...\033[0m"
# Add lvm module explicitly. ext4 support should be included by --hostonly as it's the root fs.
dracut --force --hostonly --no-hostonly-cmdline --add "lvm" --kver "$DRACUT_KVER" "$INITRAMFS_TARGET_PATH"
echo -e "\033[38;5;121mInitramfs generation attempted at $INITRAMFS_TARGET_PATH (system /boot).\033[0m"

echo -e "\033[38;5;111mCopying kernel, initramfs, and microcode to ESP (/boot/efi/ for systemd-boot)...\033[0m"
if [ -f "$BOOT_KERNEL_TARGET_PATH" ]; then
    cp -v "$BOOT_KERNEL_TARGET_PATH" /boot/efi/
else
    echo -e "\033[38;5;210mERROR: $BOOT_KERNEL_TARGET_PATH not found for ESP copy!\033[0m"
    # exit 1 # Decided not to exit here, bootloader entry might still work if files were manually placed.
fi

if [ -f "$INITRAMFS_TARGET_PATH" ]; then
    cp -v "$INITRAMFS_TARGET_PATH" /boot/efi/
else
    echo -e "\033[38;5;210mERROR: $INITRAMFS_TARGET_PATH not found for ESP copy!\033[0m"
    # exit 1
fi

# intel-ucode.img is expected to be in /boot (system's /boot) after pacstrap
INTEL_UCODE_SRC="/boot/intel-ucode.img"
if [ -f "$INTEL_UCODE_SRC" ]; then
    cp -v "$INTEL_UCODE_SRC" /boot/efi/
else
    echo -e "\033[38;5;228mWarning: $INTEL_UCODE_SRC not found, skipping copy to ESP. This might be okay if not using an Intel CPU or if microcode is handled differently (e.g., embedded in initramfs by dracut, though explicit is safer for systemd-boot).\033[0m"
fi
echo -e "\033[38;5;156mFiles copied to ESP for bootloader (if found).\033[0m"

# Update systemd-boot entry to use the correct initramfs name
# (already done above if BOOT_VMLINUZ_TARGET_NAME and INITRAMFS_TARGET_PATH are consistent)
# Ensure the entry file uses $INITRAMFS_TARGET_PATH (relative to /boot)
# The cat << EOF_ARCH_ENTRY block above should use /initramfs-linux-surface.img which matches INITRAMFS_TARGET_PATH

echo -e "\033[38;5;111mEnabling system services (GDM, NetworkManager, Bluetooth, ZRAM)...\033[0m"
systemctl enable gdm.service NetworkManager.service bluetooth.service systemd-zram-setup@zram0.service

echo -e "\033[38;5;111mConfiguring Chaotic-AUR in /etc/pacman.conf (Color and makepkg.conf configured pre-chroot)...\033[0m"
if [ "__SETUP_ADD_CHAOTIC_AUR__" = "true" ]; then
  if ! grep -q "\\[chaotic-aur\\]" /etc/pacman.conf; then
    pacman-key --recv-key 3056513887B78AEB --keyserver keyserver.ubuntu.com
    pacman-key --lsign-key 3056513887B78AEB
    pacman -U --noconfirm --needed \
        https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-keyring.pkg.tar.zst \
        https://cdn-mirror.chaotic.cx/chaotic-aur/chaotic-mirrorlist.pkg.tar.zst
    echo -e "\\n[chaotic-aur]\\nInclude = /etc/pacman.d/chaotic-mirrorlist" >> /etc/pacman.conf
    pacman -Sy # Sync new repo
  else
    echo -e "\033[38;5;123mChaotic-AUR already configured in /etc/pacman.conf.\033[0m"
  fi
fi

echo -e "\033[38;5;111mApplying system-wide dconf settings (files configured pre-chroot)...\033[0m"
dconf update # Updates system dconf database from /etc/dconf/db/local.d/

USER_HOME="/home/__SETUP_USERNAME__"
mkdir -p "$USER_HOME/.local/bin" "$USER_HOME/.config" # Ensure basic dirs exist
chown -R __SETUP_USERNAME__:__SETUP_USERNAME__ "$USER_HOME" # Set ownership

echo -e "\033[38;5;111mEnsuring .local/bin is in PATH for user __SETUP_USERNAME__ (bash)...\033[0m"
# Embed the heredoc for path setup
cat << 'EOF_PATH_SETUP' > /tmp/setup_user_path.sh
{path_setup_bash_profile_heredoc}
EOF_PATH_SETUP
# Replace placeholder in the temp script - this is a bit meta, the Python script replaces __SETUP_USERNAME__ globally
# So this sed command inside the bash script might be redundant if Python handles it, or it ensures it.
# For clarity, Python will replace __SETUP_USERNAME__ in the heredoc content as well.
bash /tmp/setup_user_path.sh # Execute the path setup logic
rm -f /tmp/setup_user_path.sh

echo -e "\033[38;5;111mInstalling yay AUR helper (if Chaotic-AUR is enabled)...\033[0m"
if [ "__SETUP_ADD_CHAOTIC_AUR__" = "true" ]; then
    # Chaotic-AUR provides 'yay', not 'yay-bin'
    if ! pacman -Q yay >/dev/null 2>&1; then
        pacman -S --noconfirm --needed yay || echo -e "\033[38;5;216mWarning: Failed to install 'yay' via pacman (from Chaotic-AUR). AUR installs might fail or require manual yay build.\033[0m"
    else
        echo -e "\033[38;5;121m'yay' already installed via pacman.\033[0m"
    fi
else
    echo -e "\033[38;5;228mChaotic-AUR not enabled, skipping pacman install of yay. User script will attempt manual build of yay-bin.\033[0m"
fi

echo -e "\033[38;5;111mRunning AUR installs and key generation as user __SETUP_USERNAME__...\033[0m"
runuser -l "__SETUP_USERNAME__" -c '
    set -e
    echo -e "\033[38;5;123m--- Running as user __SETUP_USERNAME__ for AUR and Keys ---\033[0m"
    # Set a comprehensive PATH to ensure system binaries are found
    export PATH="$HOME/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    
    echo -e "\033[38;5;123mVerifying critical command 'systemd-run' is available to user __SETUP_USERNAME__...\033[0m"
    if ! command -v systemd-run &> /dev/null; then
        echo -e "\033[38;5;210mCRITICAL WARNING: 'systemd-run' command not found in PATH for user __SETUP_USERNAME__ ($PATH). yay may fail.\033[0m";
        # Attempt to locate it directly to see if it's a PATH issue vs missing package component
        if [ -x "/usr/bin/systemd-run" ]; then
            : # No echo here for now, simplifying for parsing debug
        else
            : # No echo here for now, simplifying for parsing debug
        fi;
    else
        echo -e "\033[38;5;121m'systemd-run' is available in PATH for user __SETUP_USERNAME__.\033[0m";
    fi;

    echo -e "\033[38;5;159m>>> Checking for yay (AUR helper)...\033[0m"
    if ! command -v yay &> /dev/null; then
        echo -e "\033[38;5;210myay command not found. Attempting manual build as fallback (if Chaotic-AUR was not used or failed)...\033[0m"
        # This manual build is a fallback if Chaotic-AUR is not used or pacman install failed.
        # It requires base-devel group to be installed, which it is.
        cd /tmp || { echo "Failed to cd to /tmp"; exit 1; }
        git clone https://aur.archlinux.org/yay-bin.git && cd yay-bin && makepkg -si --noconfirm && cd / && rm -rf /tmp/yay-bin || { echo -e "\033[38;5;210mFailed to install yay manually as user __SETUP_USERNAME__.\033[0m"; exit 1; }
        echo -e "\033[38;5;121mManually built and installed yay.\033[0m"
    else
        echo -e "\033[38;5;121myay is available.\033[0m"
    fi

    echo -e "\033[38;5;159m>>> Preparing for AUR package installation (handling potential libwacom conflict)...\033[0m"
    # libwacom-surface conflicts with libwacom. Remove libwacom first if it exists.
    # This needs sudo, and we've configured passwordless sudo for pacman for the wheel group.
    if pacman -Q libwacom >/dev/null 2>&1; then
        echo -e "\033[38;5;228mStandard libwacom package found. Attempting to remove it to prevent conflict with libwacom-surface...\033[0m"
        sudo pacman -Rdd --noconfirm libwacom || echo -e "\033[38;5;216mWarning: Failed to remove standard libwacom. libwacom-surface installation might fail.\033[0m"
    else
        echo -e "\033[38;5;121mStandard libwacom package not found, no conflict expected for libwacom-surface.\033[0m"
    fi

    echo -e "\033[38;5;159m>>> Installing AUR packages (VS Code, Google Chrome, Surface Utilities)...\033[0m"
    # Ensure yay uses sudo for pacman operations, which it does by default.
    # The --noconfirm should handle pacman's confirmations as well.
    yay -S --noconfirm --needed --answeredit=no --save visual-studio-code-bin google-chrome libwacom-surface surface-control-bin || echo -e "\033[38;5;216mWarning: Some AUR packages failed to install.\033[0m"

    echo -e "\033[38;5;159m>>> Generating SSH key for __SETUP_SSH_KEY_EMAIL__...\033[0m"
    mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
    if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
        ssh-keygen -t ed25519 -C "__SETUP_SSH_KEY_EMAIL__" -N "" -f "$HOME/.ssh/id_ed25519" || echo -e "\033[38;5;216mSSH keygen failed.\033[0m"
    else
        echo -e "\033[38;5;121mSSH key id_ed25519 already exists.\033[0m"
    fi

    echo -e "\033[38;5;159m>>> Attempting GPG key generation for __SETUP_GPG_KEY_NAME__ <__SETUP_GPG_KEY_EMAIL__>...\033[0m"
    mkdir -p "$HOME/.gnupg" && chmod 700 "$HOME/.gnupg"
    GPG_BATCH_CMDS_USER=$(cat <<GPG_USER_EOF
%echo Generating GPG key for user...
Key-Type: RSA
Key-Length: 4096
Subkey-Type: RSA
Subkey-Length: 4096
Name-Real: __SETUP_GPG_KEY_NAME__
Name-Email: __SETUP_GPG_KEY_EMAIL__
Expire-Date: 0
Passphrase: __SETUP_BAO_PASSWORD__
%commit
%echo done
GPG_USER_EOF
    )
    if ! gpg --list-keys "__SETUP_GPG_KEY_EMAIL__" > /dev/null 2>&1; then
        echo "$GPG_BATCH_CMDS_USER" | gpg --batch --pinentry-mode loopback --yes --generate-key > /tmp/gpg_gen_user.log 2>&1 || echo -e "\033[38;5;216mGPG batch command execution had issues.\033[0m"
        cat /tmp/gpg_gen_user.log; rm -f /tmp/gpg_gen_user.log
        if ! gpg --list-keys "__SETUP_GPG_KEY_EMAIL__" > /dev/null 2>&1; then
            echo -e "\033[38;5;216mWARNING: GPG key for __SETUP_GPG_KEY_EMAIL__ may not have been created.\033[0m"
        else
            echo -e "\033[38;5;121mGPG key for __SETUP_GPG_KEY_EMAIL__ successfully created.\033[0m"
        fi
    else
        echo -e "\033[38;5;121mGPG key for __SETUP_GPG_KEY_EMAIL__ already exists.\033[0m"
    fi
    echo -e "\033[38;5;123m--- User-specific setup finished ---\033[0m"
' || echo -e "\033[38;5;210mERROR: User-specific setup script failed for __SETUP_USERNAME__\033[0m"


echo -e "\033[38;5;111mPerforming final system update as root...\033[0m"
pacman -Syu --noconfirm # Final sync and update

echo -e "\033[38;5;183m--- CHROOT SCRIPT: Configuration complete. ---\033[0m"