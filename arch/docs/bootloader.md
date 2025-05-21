systemd-boot

Page
Discussion
Read
View source
View history

Tools
Appearance hide
Text

Small

Standard

Large
Width

Standard

Wide
Color (beta)

Automatic

Light

Dark

Related articles

Arch boot process
Secure Boot
Unified Extensible Firmware Interface
systemd-boot(7), previously called gummiboot (German for "rubber dinghy") and sometimes referred to as sd-boot, is an easy-to-configure UEFI boot manager. It provides a textual menu to select the boot entry and an editor for the kernel command line.

Note that systemd-boot can only start EFI executables (e.g., the Linux kernel EFI boot stub, UEFI shell, GRUB, or the Windows Boot Manager) from the EFI system partition it is installed to or from an Extended Boot Loader Partition (XBOOTLDR partition) on the same disk.

Note: In the entire article esp denotes the mountpoint of the EFI system partition and boot denotes the mountpoint of the optional XBOOTLDR partition. It is assumed that you have chrooted to the system's mount point.
Supported file systems
systemd-boot inherits the support for the file systems from the firmware (i.e. at least FAT12, FAT16 and FAT32). Additionally it loads any UEFI drivers placed in esp/EFI/systemd/drivers/.

Installation
systemd-boot is shipped with the systemd package which is a dependency of the base meta package, so no additional packages need to be installed manually.

Installing the UEFI boot manager
To install systemd-boot, first make sure that the system is booted into UEFI mode and UEFI variables are accessible. This can be verified by running efivar --list or, if efivar is not installed, by running ls /sys/firmware/efi/efivars (if the directory exists, the system is booted into UEFI mode.)

Use bootctl(1) to install systemd-boot to the ESP:

# bootctl install
This will copy the systemd-boot UEFI boot manager to the ESP, create a UEFI boot entry for it and set it as the first in the UEFI boot order.

On an x64 UEFI, /usr/lib/systemd/boot/efi/systemd-bootx64.efi will be copied to esp/EFI/systemd/systemd-bootx64.efi and esp/EFI/BOOT/BOOTX64.EFI.
On an IA32 UEFI, /usr/lib/systemd/boot/efi/systemd-bootia32.efi will be copied to esp/EFI/systemd/systemd-bootia32.efi and esp/EFI/BOOT/BOOTIA32.EFI.
This article or section is out of date.

Reason: When running in pid namespace (which is the case for arch-chroot(8)), bootctl does not create the UEFI boot entry in NVRAM anymore since systemd v257. (Discuss in User talk:Scimmia#Revert on systemd-boot about sd-boot not creating EFI entries inside chroot)
The UEFI boot entry will be called "Linux Boot Manager" and will point to, depending on the UEFI bitness, either \EFI\systemd\systemd-bootx64.efi or \EFI\systemd\systemd-bootia32.efi on the ESP.

Note:
When running bootctl install, systemd-boot will try to locate the ESP at /efi, /boot, and /boot/efi. Setting esp to a different location requires passing the --esp-path=esp option. (See bootctl(1) § OPTIONS for details.)
Installing systemd-boot will overwrite any existing esp/EFI/BOOT/BOOTX64.EFI (or esp/EFI/BOOT/BOOTIA32.EFI on IA32 UEFI), e.g. Microsoft's version of the file.
To conclude the installation, configure systemd-boot.

Installation using XBOOTLDR
This article or section is a candidate for moving to Partitioning#Discrete partitions.

Notes: All partitioning info should be moved to partitioning, to leave only steps relevant to installing systemd-boot if you have such a setup. (Discuss in Talk:Systemd-boot)
A separate /boot partition of type "Linux extended boot" (XBOOTLDR) can be created to keep the kernel and initramfs separate from the ESP. This is particularly helpful to dual boot with Windows with an existing ESP that is too small.

Prepare an ESP as usual and create another partition for XBOOTLDR on the same physical drive. The XBOOTLDR partition must have a partition type GUID of bc13c2ff-59e6-4262-a352-b275fd6f7172 [1] (ea00 type for gdisk, xbootldr type for fdisk). The size of the XBOOTLDR partition should be large enough to accommodate all of the kernels you are going to install.

Note:
systemd-boot does not do a file system check like it does for the ESP. Hence, it is possible to use any file system that your UEFI implementation can read.
UEFI may skip loading partitions other than the ESP when a "fast boot" mode is enabled. This can lead to systemd-boot failing to find entries on the XBOOTLDR partition; in that case, disable the "fast boot" mode.
The XBOOTLDR partition must be on the same physical disk as the ESP for systemd-boot to recognize it.
During install, mount the ESP to /mnt/efi and the XBOOTLDR partition to /mnt/boot.

Once in chroot, use the command:

# bootctl --esp-path=/efi --boot-path=/boot install
To conclude the installation, configure systemd-boot.

Updating the UEFI boot manager
Whenever there is a new version of systemd-boot, the UEFI boot manager can be optionally reinstalled by the user. This can be done manually or automatically; the two approaches are described thereafter.

Note: The UEFI boot manager is a standalone EFI executable and any version can be used to boot the system (partial updates do not apply, since pacman only installs the systemd-boot installer, not systemd-boot itself.) However, new versions may add new features or fix bugs, so it is probably a good idea to update systemd-boot.
Warning: If you have Secure Boot enabled, you need to sign the bootloader update. See #Signing for Secure Boot.
Manual update
Use bootctl to update systemd-boot:

# bootctl update
Note: As with bootctl install, systemd-boot will try to locate the ESP at /efi, /boot, and /boot/efi. Setting esp to a different location requires passing the --esp-path=esp option.
Automatic update
To update systemd-boot automatically, either use a systemd service or a pacman hook. The two methods are described below.

systemd service
As of version 250, systemd ships with systemd-boot-update.service. Enabling this service will update the bootloader after the next boot.

pacman hook
The package systemd-boot-pacman-hookAUR adds a pacman hook which is executed every time systemd is upgraded.

Rather than installing systemd-boot-pacman-hook, you may prefer to manually place the following file in /etc/pacman.d/hooks/:

/etc/pacman.d/hooks/95-systemd-boot.hook
[Trigger]
Type = Package
Operation = Upgrade
Target = systemd

[Action]
Description = Gracefully upgrading systemd-boot...
When = PostTransaction
Exec = /usr/bin/systemctl restart systemd-boot-update.service
Signing for Secure Boot
If you have Secure Boot enabled, you may want to add a pacman hook to automatically sign the boot manager upon every upgrade of the package:

/etc/pacman.d/hooks/80-secureboot.hook
[Trigger]
Operation = Install
Operation = Upgrade
Type = Path
Target = usr/lib/systemd/boot/efi/systemd-boot*.efi

[Action]
Description = Signing systemd-boot EFI binary for Secure Boot
When = PostTransaction
Exec = /bin/sh -c 'while read -r i; do sbsign --key /path/to/keyfile.key --cert /path/to/certificate.crt "$i"; done;'
Depends = sh
Depends = sbsigntools
NeedsTargets
Replace /path/to/keyfile.key and /path/to/certificate.crt with your signing key and certificate respectively. For better understanding of this hook, consult sbsign(1).

The created /usr/lib/systemd/boot/efi/systemd-boot*.efi.signed will automatically be picked up by bootctl install or bootctl update. See bootctl(1) § SIGNED .EFI FILES.

As an alternative, use sbctl.

Configuration
Tip: After changing the configuration, run bootctl (without any arguments) to make sure that systemd-boot will be able to parse it properly.
Loader configuration
The loader configuration is stored in the file esp/loader/loader.conf. See loader.conf(5) § OPTIONS for details.

A loader configuration example is provided below:

esp/loader/loader.conf
default  arch.conf
timeout  4
console-mode max
editor   no
Tip:
systemd-boot does not accept tabs for indentation, use spaces instead.
default and timeout can be changed in the boot menu itself and changes will be stored as UEFI variables LoaderEntryDefault and LoaderConfigTimeout, overriding these options.
bootctl set-default "" and bootctl set-timeout "" can be used to clear the UEFI variables overriding the default and timeout options, respectively.
If you have set timeout 0, the boot menu can be accessed by pressing Space.
A basic loader configuration file is located at /usr/share/systemd/bootctl/loader.conf.
If the bootloader (during the entry selection) appears distorted/uses the wrong resolution you can try to set the console-mode to auto (uses heuristics to select the best resolution), keep (keeps the firmware provided resolution) or 2 (tries to select the first non-UEFI-standard resolution).
Remember last entry
The default can be changed to @saved in order to remember the last picked entry on startup. This is useful for when dual booting Windows and the surprise windows auto update pushes you into Linux.

esp/loader/loader.conf
default @saved
...
Consult loader.conf(5) for more details.

Adding loaders
systemd-boot will search for .conf files in /loader/entries/ on the EFI system partition it was launched from and additionally the XBOOTLDR partition on the same disk.

Note:
Entries in esp/loader/entries/*.conf can only use files (e.g. kernels, initramfs, images, etc.) in esp/ and entries in boot/loader/entries/*.conf can only use files in boot/.
The file path parameters are relative to the root of your EFI system partition or XBOOTLDR partition. E.g., if your EFI system partition or XBOOTLDR partition is mounted at /boot, then the /boot/vmlinuz-linux file must be specified in the linux key as /vmlinuz-linux.
When Secure Boot is active, unified kernel images (UKIs) with an embedded .cmdline ignore all command line options passed to them (either using a boot entry with options or interactively). When Secure Boot is not active, the options passed via the command line override the embedded .cmdline.
An example of loader files launching Arch from a volume using its UUID xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx is:

esp/loader/entries/arch.conf
title   Arch Linux
linux   /vmlinuz-linux
initrd  /initramfs-linux.img
options root=UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx rw
esp/loader/entries/arch-fallback.conf
title   Arch Linux (fallback initramfs)
linux   /vmlinuz-linux
initrd  /initramfs-linux-fallback.img
options root=UUID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx rw
See the Boot Loader Specification for details on all configuration options.

systemd-boot will automatically check at boot time for Windows Boot Manager at the location /EFI/Microsoft/Boot/Bootmgfw.efi, Apple macOS Boot Manager in firmware, UEFI shell /shellx64.efi and EFI Default Loader /EFI/BOOT/bootx64.efi, as well as specially prepared kernel files found in /EFI/Linux/. When detected, corresponding entries with titles auto-windows, auto-osx, auto-efi-shell and auto-efi-default, respectively, will be generated. These entries do not require manual loader configuration. However, it does not auto-detect other EFI applications (unlike rEFInd), so for booting the Linux kernel, manual configuration entries must be created.

Tip:
The available boot entries which have been configured can be listed with the command bootctl list.
An example entry file is located at /usr/share/systemd/bootctl/arch.conf.
The kernel parameters for scenarios such as LVM, LUKS, dm-crypt or Btrfs can be found on the relevant pages.
Note: If external microcode initramfs images are used (e.g. when using Booster as the initramfs generator), /boot/amd-ucode.img or /boot/intel-ucode.img must be specified in a separate initrd and always be placed first, before the main initramfs image.
UEFI Shells or other EFI applications
In case you installed a UEFI shell with the package edk2-shell, systemd-boot will auto-detect and create a new entry if the EFI file is placed in esp/shellx64.efi. To perform this an example command after installing the package would be:

# cp /usr/share/edk2-shell/x64/Shell.efi /boot/shellx64.efi
Otherwise in case you installed other EFI applications into the ESP, you can use the following snippets.

Note: The file path parameter for the efi line is relative to the root of your EFI system partition. If your EFI system partition is mounted at /boot and your EFI binaries reside at /boot/EFI/xx.efi and /boot/yy.efi, then you would specify the parameters as efi /EFI/xx.efi and efi /yy.efi respectively.
esp/loader/entries/fwupd.conf
title  Firmware updater
efi     /EFI/tools/fwupdx64.efi
esp/loader/entries/gdisk.conf
title  GPT fdisk (gdisk)
efi     /EFI/tools/gdisk_x64.efi
Memtest86+
You need to install memtest86+-efi for this to work. Also sign the EFI binary when using Secure Boot.

esp/loader/entries/memtest.conf
title Memtest86+
efi /memtest86+/memtest.efi
Netboot
systemd-boot can chainload Netboot. Download the ipxe-arch.efi EFI binary and signature, verify it and place it as proposed in esp/EFI/arch_netboot/arch_netboot.efi.

esp/loader/entries/arch_netboot.conf
title Arch Linux Netboot
efi /EFI/arch_netboot/arch_netboot.efi
GRUB
systemd-boot can chainload GRUB. The location of the grubx64.efi binary matches the used --bootloader-id= when GRUB was installed to the ESP.

esp/loader/entries/grub.conf
title GRUB
efi /EFI/GRUB/grubx64.efi
Boot from another disk
systemd-boot cannot launch EFI binaries from partitions other than the ESP it is launched from or the XBOOTLDR partition on the same disk, but it can direct the UEFI shell to do so.

First, install edk2-shell as described above. In the UEFI shell, use the map command to take notes of the FS alias (ex: HD0a66666a2, HD0b, FS1, or BLK7) of the partition with the corresponding PARTUUID.

Then, use the exit command to boot back into Linux, where you can create a new loader entry to run the target EFI program through the UEFI shell:

esp/loader/entries/windows.conf
title   Windows
efi     /shellx64.efi
options -nointerrupt -nomap -noversion HD0b:EFI\Microsoft\Boot\Bootmgfw.efi
Ensure that the efi path matches the location where the shellx64.efi has been copied in the esp partition. Also, note that the shellx64.efi EFI file can be moved elsewhere to avoid the automatic entry creation by systemd-boot.

Replace HD0b with the previously noted FS alias.

The -nointerrupt option prevents interrupting the target EFI program with Ctrl+c.
The -nomap -noversion options hide the default UEFI shell greeting.
To have the UEFI shell automatically return to the bootloader if the target EFI program exits (e.g., due to an error), add the -exit option.
You can also add the -noconsoleout option if there is still unnecessary output in the UEFI shell.
Booting into UEFI firmware setup
systemd-boot will automatically add an entry to boot into UEFI firmware setup if your device's firmware supports rebooting into setup from the OS.

Kernel parameters editor with password protection
Alternatively you can install systemd-boot-passwordAUR which supports password basic configuration option. Use sbpctl generate to generate a value for this option.

Install systemd-boot-password with the following command:

# sbpctl install esp
With enabled editor you will be prompted for your password before you can edit kernel parameters.

Tips and tricks
Keys inside the boot menu
You can use t and T while in the menu to adjust the menu timeout and e to edit the kernel parameters for this boot. Press h to see a short list of useful hotkeys. See systemd-boot(7) § KEY BINDINGS for the full list of available key bindings inside the boot menu.

Choosing next boot
The boot manager is integrated with the systemctl command, allowing you to choose what option you want to boot after a reboot. For example, suppose you have built a custom kernel and created an entry file esp/loader/entries/arch-custom.conf to boot into it, you can just launch

$ systemctl reboot --boot-loader-entry=arch-custom.conf
and your system will reboot into that entry maintaining the default option intact for subsequent boots. To see a list of possible entries pass the --boot-loader-entry=help option.

If you want to boot into the firmware of your motherboard directly, then you can use this command:

$ systemctl reboot --firmware-setup
Unified kernel images
Unified kernel images (UKIs) in esp/EFI/Linux/ are automatically sourced by systemd-boot, and do not need an entry in esp/loader/entries. (Note that unified kernel images must have a .efi extension to be identified by systemd-boot.)

Tip: Files in esp/loader/entries/ will be booted first if no default is set in esp/loader/loader.conf. Remove those entries, or set the default with the full file name, i.e. default arch-linux.efi
Grml on ESP
Note: The following instructions are not exclusive to Grml. With slight adjustments, installing other software (e.g., SystemRescueCD) is possible.
Tip: A PKGBUILD is available: grml-systemd-bootAUR.
Grml is a small live system with a collection of software for system administration and rescue.

In order to install Grml on the ESP, we only need to copy the kernel vmlinuz, the initramfs initrd.img, and the squashed image grml64-small.squashfs from the iso file to the ESP. To do so, first download grml64-small.iso and mount the file (the mountpoint is henceforth denoted mnt); the kernel and initramfs are located in mnt/boot/grml64small/, and the squashed image resides in mnt/live/grml64-small/.

Next, create a directory for Grml in your ESP,

# mkdir -p esp/grml
and copy the above-mentioned files in there:

# cp mnt/boot/grml64small/vmlinuz esp/grml
# cp mnt/boot/grml64small/initrd.img esp/grml
# cp mnt/live/grml64-small/grml64-small.squashfs esp/grml
In the last step, create an entry for the systemd-boot loader: In esp/loader/entries create a grml.conf file with the following content:

esp/loader/entries/grml.conf
title   Grml Live Linux
linux   /grml/vmlinuz
initrd  /grml/initrd.img
options apm=power-off boot=live live-media-path=/grml/ nomce net.ifnames=0
For an overview of the available boot options, consult the cheatcode for Grml.

Archiso on ESP
Tip: A PKGBUILD is available: archiso-systemd-bootAUR.
As with Grml it is possible to use the Arch Linux ISO. To do this we need to copy the kernel vmlinuz-linux, the initramfs initramfs-linux.img, and the squashfs image airootfs.sfs from the ISO file to the EFI system partition.

First download archlinux-YYYY.MM.DD-x86_64.iso.

Next, create a directory for archiso in your ESP:

# mkdir -p esp/EFI/archiso
Extract the contents of the arch directory in there:

# bsdtar -v -x --no-same-permissions --strip-components 1 -f archlinux-YYYY.MM.DD-x86_64.iso -C esp/EFI/archiso arch
In the last step, create a boot entry for the systemd-boot loader: In esp/loader/entries create a arch-rescue.conf file with the following content:

esp/loader/entries/arch-rescue.conf
title   Arch Linux (rescue system)
linux   /EFI/archiso/boot/x86_64/vmlinuz-linux
initrd  /EFI/archiso/boot/x86_64/initramfs-linux.img
options archisobasedir=/EFI/archiso archisosearchfilename=/EFI/archiso/boot/x86_64/vmlinuz-linux
For an overview of the available boot options, consult the README.bootparams for mkinitcpio-archiso.

systemd-boot on BIOS systems
If you need a bootloader for BIOS systems that follows The Boot Loader Specification, then systemd-boot can be pressed into service on BIOS systems. The Clover boot loader supports booting from BIOS systems and provides a emulated UEFI environment.

Troubleshooting
systemd-boot does not display my boot entry
This may be caused by a variety of issues with the configuration file, such as the path to the kernel being specified incorrectly. To check, run:

# bootctl
Installing after booting in BIOS mode
Note: This is not recommended.
If booted in BIOS mode, you can still install systemd-boot, however this process requires you to tell firmware to launch systemd-boot's EFI file at boot:

you have a working UEFI Shell somewhere else.
your firmware interface provides a way of properly setting the EFI file that needs to be loaded at boot time.
some firmware may use the default esp/EFI/BOOT/BOOTX64.EFI if there is no other entry set in the UEFI.
If you can do it, the installation is easier: go into your UEFI Shell or your firmware configuration interface and change your machine's default EFI file to esp/EFI/systemd/systemd-bootx64.efi.

Note: The firmware interface of Dell Latitude series provides everything you need to setup UEFI boot but the UEFI Shell will not be able to write to the computer's ROM.
Manual entry using efibootmgr
If the bootctl install command failed, you can create a UEFI boot entry manually using efibootmgr:

# efibootmgr --create --disk /dev/sdX --part Y --loader '\EFI\systemd\systemd-bootx64.efi' --label "Linux Boot Manager" --unicode
where /dev/sdXY is the EFI system partition.

Note: The path to the EFI binary must use the backslash (\) as the separator
Manual entry using bcdedit from Windows
If for any reason you need to create a UEFI boot entry from Windows, you can use the following commands from an Administrator prompt:

> bcdedit /copy {bootmgr} /d "Linux Boot Manager"
> bcdedit /set {guid} path \EFI\systemd\systemd-bootx64.efi
Replace guid with the id returned by the first command. You can also set it as the default entry using

> bcdedit /default {guid}
Menu does not appear after Windows upgrade
See UEFI#Windows changes boot order.

Add support for Windows BitLocker TPM unlocking
To stop BitLocker from requesting the recovery key, add the following to loader.conf:

esp/loader/loader.conf
reboot-for-bitlocker yes
This will set the BootNext UEFI variable, whereby Windows Boot Manager is loaded without BitLocker requiring the recovery key. This is a one-time change, and systemd-boot remains the default bootloader. There is no need to specify Windows as an entry if it was autodetected.

This is an experimental feature, so make sure to consult loader.conf(5).