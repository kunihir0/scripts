Kernel parameters

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
(Redirected from Kernel parameter)
Related articles

Kernel
There are three ways to pass options to the kernel and thus control its behaviour:

When building the kernel—in the kernel's config file. See Kernel#Compilation for details.
When starting the kernel—using command line parameters (usually through a boot loader, or as well in unified kernel image).
At runtime—through the files in /proc/sys/ (see sysctl) and /sys/.
Note: The options of loadable modules can be set via .conf files in /etc/modprobe.d/. See Kernel module#Using modprobe.d.
Between the three methods, the configurable options differ in availability, their name and the method in which they are specified. This page only explains the second method (kernel command line parameters) and shows a list of the most used kernel parameters in Arch Linux.

Most parameters are associated with subsystems and work only if the kernel is configured with those subsystems built in. They also depend on the presence of the hardware they are associated with.

Kernel command line parameters either have the format parameter, or parameter=value, or module.parameter=value.

Note:
You can check the parameters your system was booted up with by running cat /proc/cmdline and see if it includes your changes.
All kernel parameters are case-sensitive.
Boot loader configuration
Note: The Arch Linux installation medium uses systemd-boot for UEFI systems, and Syslinux for BIOS ones.
Kernel parameters can be set either temporarily by editing the boot entry in the boot loader boot selection menu, or permanently by modifying the boot loader configuration file.

The following examples add the quiet and splash parameters to the GRUB, GRUB Legacy, LILO, Limine, rEFInd, Syslinux and systemd-boot boot loaders.

GRUB
Press e when the menu shows up and add them on the linux line:
linux /boot/vmlinuz-linux root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash
Press Ctrl+x to boot with these parameters.
To make the change persistent after reboot, you could manually edit /boot/grub/grub.cfg with the exact line from above, or if using grub-mkconfig:
Edit /etc/default/grub and append your kernel options between the quotes in the GRUB_CMDLINE_LINUX_DEFAULT line:
GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"
And then automatically re-generate the grub.cfg file with:
# grub-mkconfig -o /boot/grub/grub.cfg
GRUB Legacy
Press e when the menu shows up and add them on the kernel line:
kernel /boot/vmlinuz-linux root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash
Press b to boot with these parameters.
To make the change persistent after reboot, edit /boot/grub/menu.lst and add them to the kernel line, exactly like above.
LILO
Add them to /etc/lilo.conf using append or addappend:
image=/boot/vmlinuz-linux
        ...
        append="quiet splash"
Limine
To temporarily add kernel parameters, press e when the boot entry selection screen appears and modify the cmdline line:
cmdline: root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash
To apply changes permanently, edit the kernel_cmdline line in the Limine configuration file located at esp/limine.conf:
/+Arch Linux
    ...
    kernel_cmdline: root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash
kernel_cmdline is alias of cmdline
rEFInd
Press Insert, F2, Tab, or + on the desired menu entry and press it again on the submenu entry. Add kernel parameters at the end of the string:
root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw initrd=\boot\initramfs-linux.img quiet splash
Press Enter to boot with these parameters.
To make the change persistent after reboot, edit /boot/refind_linux.conf and append them between the quotes in all required lines, for example
"Boot using default options"   "root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash"
If you have disabled auto-detection of OSes in rEFInd and are defining OS stanzas instead in esp/EFI/refind/refind.conf to load your OSes, you can edit it like:
menuentry "Arch Linux" {
    ...
    options  "root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash"
    ...
}
Syslinux
Press Tab when the menu shows up and add them at the end of the string:
linux /boot/vmlinuz-linux root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw initrd=/boot/initramfs-linux.img quiet splash
Press Enter to boot with these parameters.
To make the change persistent after reboot, edit /boot/syslinux/syslinux.cfg and add them to the APPEND line:
APPEND root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash
systemd-boot
Press e when the menu appears and add the parameters to the end of the string:
initrd=\initramfs-linux.img root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash
Press Enter to boot with these parameters.
Note:
If you have not set a value for menu timeout, you will need to hold Space while booting for the systemd-boot menu to appear.
If you cannot edit the parameters from the boot menu, you may need to edit /boot/loader/loader.conf and add editor 1 to enable editing.
To make the change persistent after reboot, edit /boot/loader/entries/arch.conf (assuming you set up your EFI system partition) and add them to the options line:
options root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 rw quiet splash
dracut
dracut is capable of embedding the kernel parameters in the initramfs, thus allowing to omit them from the boot loader configuration. See dracut#Kernel command line options.

EFI boot stub
See EFI boot stub#Using UEFI directly.

Hijacking cmdline
Even without access to your boot loader it is possible to change your kernel parameters to enable debugging (if you have root access). This can be accomplished by overwriting /proc/cmdline which stores the kernel parameters. However /proc/cmdline is not writable even as root, so this hack is accomplished by using a bind mount to mask the path.

First create a file containing the desired kernel parameters:

/root/cmdline
root=UUID=0a3407de-014b-458b-b5c1-848e92a327a3 ro console=tty1 logo.nologo debug
Then use a bind mount to overwrite the parameters:

# mount -n --bind -o ro /root/cmdline /proc/cmdline
The -n option skips adding the mount to /etc/mtab, so it will work even if root is mounted read-only. You can cat /proc/cmdline to confirm that your change was successful.

Parameter list
This list is not comprehensive. For a complete list of all options, please see The kernel's command-line parameters.

parameter	Description
init	Run specified binary instead of /sbin/init as init process. The systemd-sysvcompat package symlinks /sbin/init to /usr/lib/systemd/systemd to use systemd. Set it to /bin/sh to boot to the shell.
initrd	Specify the location of the initial ramdisk. For UEFI boot managers and an EFI boot stub, the path must be specified using backslashes (\) as path separators.
cryptdevice	Specify the location of a dm-crypt-encrypted partition plus a device mapper name.
debug	Enable kernel debugging (events log level).
lsm	Set the initialisation order of the Linux security modules, used to enable AppArmor, SELinux or TOMOYO.
maxcpus	Maximum number of processors that an SMP kernel will bring up during bootup.
mem	Force usage of a specific amount of memory to be used.
netdev	Network devices parameters.
nomodeset	Disable Kernel mode setting.
panic	Time before automatic reboot on kernel panic.
resume	Specify a swap device to use when waking from hibernation.
ro	Mount root device read-only on boot. This is mkinitcpio's default1.
root	Root file system. See init/do_mounts.c for kernel's supported device name formats. Note that an initramfs with udev supports more name formats. A setup compatible with systemd#GPT partition automounting allows to omit the parameter entirely or to alternatively use root=gpt-auto.
rootflags	Root file system mount options. Useful for setting options that cannot be applied by remounting (i.e. by systemd-remount-fs.service(8)). For example, the discard option of an XFS root volume or subvol= option of Btrfs when using a subvolume as root.
rw	Mount root device read-write on boot. This is the kernel's default1.
systemd.unit	Boot to a specified target.
video	Override framebuffer video defaults.
The kernel uses rw if neither ro or rw are explicitly set on kernel command line (see bootparam(7) § General non-device-specific boot arguments). However, mkinitcpio uses ro as the default value overriding the kernel's default (see mkinitcpio(8) § EARLY INIT ENVIRONMENT). Boot loaders may also have their own configured default, for example, grub-mkconfig uses rw (see FS#36275 as a reference).
Note: rw is required when using mkinitcpio's fsck hook (see [1]) or when using F2FS as the root file system.