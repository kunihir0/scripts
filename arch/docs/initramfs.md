dracut

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

booster
mkinitcpio
Unified kernel image
dracut creates an initial image used by the kernel for preloading the block device modules (such as IDE, SCSI or RAID) which are needed to access the root filesystem. Upon installing linux, you can choose between mkinitcpio and dracut. dracut is used by Fedora, RHEL, Gentoo, and Debian, among others. Arch uses mkinitcpio by default.

You can read the full project documentation for dracut in the documentation.

Installation
Install the dracut package, or dracut-gitAUR for the latest development version.

Tip: If dracut works on your machine after you test it, you can uninstall mkinitcpio.
Usage
dracut is easy to use and typically does not require user configuration, even when using non-standard setups, like LVM on LUKS.

To generate an initramfs for the running kernel:

# dracut --hostonly --no-hostonly-cmdline --add-confdir no-network /boot/initramfs-linux.img
To enable hostonly mode permanently (so that you do not need to include it in the command line) you can add the following to your dracut configuration:

/etc/dracut.conf.d/hostonly.conf
hostonly="yes"
hostonly_cmdline="no"
dracut-gitAUR has hostonly mode enabled by default already.

Note: In some cases, especially when installing a system for the first time, the above command will not work. Use the following:
# dracut -f --regenerate-all
To generate a fallback initramfs run:

# dracut /boot/initramfs-linux-fallback.img
/boot/initramfs-linux.img refers to the output image file. If you are using an other kernel, consider changing the file name. For example, for the linux-lts kernel, the output file should be named /boot/initramfs-linux-lts.img. However, you can name these files whatever you wish as long as your boot loader configuration uses the same file names.

Note: The files created through these commands embed any installed Microcode images.
Additional options
The --force flag overwrites the image file if it is already present.

The --kver option specifies which kernel to use. The argument to this option must match the name of a directory present in /usr/lib/modules.

More flags can be found with dracut(8).

Advanced configuration
It is important to note that there are two distinct approaches how the various tasks during initial ramdisk phase are performed:

Shell (bash/busybox/dash) based initial ramdisk
An init script is started that in turn scans the filesystem of the initial ramdisk for dracut scripts to be executed.
systemd based (default) initial ramdisk
systemd is already started at the beginning of the initial ramdisk phase. The tasks to be executed are determined by regular systemd unit files. See systemd bootup process.
The concrete variant is determined by the absence or presence of the systemd dracut module. See #dracut modules for more details.

dracut can be configured by directly passing arguments on the command line (see dracut(8) § OPTIONS). If you wish to always execute dracut with a certain set of flags, you can save a specified configuration in a .conf file in /etc/dracut.conf.d/. For example:

/etc/dracut.conf.d/myflags.conf
hostonly="yes"
compress="lz4"
add_drivers+=" i915 "
omit_dracutmodules+=" systemd network "
You can see more configuration options with dracut.conf(5). Fuller descriptions of each option can be found with dracut(8). We will describe a few common options in what follows.

dracut modules
dracut uses a modular approach to build the initramfs (see dracut.modules(7)). All of dracut 's builtin modules are located in /lib/dracut/modules.d and can be listed with dracut --list-modules. Extra modules can be provided by external packages e.g. dracut-sshd-gitAUR. dracut 's built-in modules unfortunately lack documentation, although their names can be self-explanatory.

Some of the modules are active/inactive by default, and can be activated/deactivated with --add/--omit command line argument or with the add_dracutmodules+=""/omit_dracutmodules+="" persistent config entry lines.

/etc/dracut.conf.d/myflags.conf
# ...
add_dracutmodules+=" dracut modules to activate "
omit_dracutmodules+=" dracut modules to deactivate "
# ...
For dracut module documentation, see the upstream dracut documentation.

Most dracut modules are dependent on other dracut modules. As an example the bluetooth dracut module depends on the dbus dracut module.


TPM2
To make use of systemd 's unlocking of luks2 encrypted volumes using TPM2 through systemd-cryptenroll, install tpm2-tools package and enable the tpm2-tss dracut module.

Early kernel module loading
Dracut enables early loading (at the initramfs stage, via modprobe) through its --force_drivers command or force_drivers+="" config entry line. For example:

/etc/dracut.conf.d/myflags.conf
# ...
force_drivers+=" nvidia nvidia_modeset nvidia_uvm nvidia_drm "
# ...
Kernel command line options
Kernel command line options can be placed in a .conf file in /etc/dracut.conf.d/, and set via the kernel_cmdline= flag. Dracut will automatically source this file and create a 01-default.conf file and place it inside the initramfs directory /etc/cmdline.d/. For example, your kernel command line options file could look like:

/etc/dracut.conf.d/cmdline.conf
kernel_cmdline="rd.luks.uuid=luks-f6c738f3-ee64-4633-b6b0-eceddb1bb010 rd.lvm.lv=arch/root rd.lvm.lv=arch/swap root=/dev/arch/root rootfstype=ext4 rootflags=rw,relatime"
Miscellaneous notes
It is not necessary to specify the root block device for dracut. From dracut.cmdline(7):

The root device used by the kernel is specified in the boot configuration file on the kernel command line, as always.
However, it may be useful to set some parameters early, and you can enable additional features like prompting for additional command line parameters. See dracut.cmdline(7) for all options. Here are some example configuration options:

Resume from a swap partition: resume=UUID=80895b78-7312-45bc-afe5-58eb4b579422
Prompt for additional kernel command line parameters: rd.cmdline=ask
Print informational output even if quiet is set: rd.info
Unified kernel image
dracut can produce unified kernel images with the --uefi command line option or with the uefi="yes" configuration option.

Tips and tricks
View information about generated image
You can view information about a generated initramfs image, which you may wish to view in a pager:

# lsinitrd /path/to/initramfs_or_uefi_image | less
This command will list the arguments passed to dracut when the image was created, the list of included dracut modules, and the list of all included files.

Change compression program
To reduce the amount of time spent compressing the final image, you may change the compression program used.

Warning: Make sure your kernel has your chosen decompression support compiled in, otherwise you will not be able to boot. You must also have the chosen compression program package installed.
Simply add any one of the following lines (not multiple) to your dracut configuration:

compress="cat"
compress="gzip"
compress="bzip2"
compress="lzma"
compress="xz"
compress="lzo"
compress="lz4"
compress="zstd"
gzip is the default compression program used. compress="cat" will make the initramfs with no compression.

You can also use a non-officially-supported compression program:

compress="program"
Performance considerations
Some considerations to optimize the boot and initramfs creation performance are:

Understand and configure the fastest compression. If the kernel modules are already compressed, perhaps there is no need to re-compress the initramfs on creation.
Understand the impact if including systemd into your initramfs. If it slows things down, omit it. If it makes things faster, include it.
Consider using dracut-cpio when using a copy-on-write filesystem. See the --enhanced-cpio option for applicability.
Minimize the number of kernel modules and dracut modules included in initramfs. As an example: If nfs-utils is installed (but not required to boot), then you need to explicitly omit the nfs dracut module, otherwise network boot will be enabled in the generated initramfs in default configuration - see https://github.com/dracut-ng/dracut-ng/pull/297.
Consider adding busybox dracut module to replace bash.
Consider hostonly and hostonly_mode=strict.
Generate a new initramfs on kernel upgrade
It is possible to automatically generate new initramfs images upon each kernel upgrade.

dracut-gitAUR package now comes with hooks for pacman, the instructions below are for dracut or if the you'd like to customize the hooks.

The instructions here are for the default linux kernel, but it should be easy to add extra hooks for other kernels.

Tip:
The dracut-ukifyAUR package is the modern way to generate a unified kernel image using systemd-ukify. Unlike the methods below, you can sign your whole kernel image including the initramfs. Using the uefi_secureboot_cert and uefi_secureboot_key options in your dracut config (dracut.conf(5)).
The dracut-hookAUR package includes hooks and scripts similar to the below. Alternatively, you may want dracut-uefi-hookAUR or dracut-hook-uefiAUR instead, if you want an initramfs image that is an EFI executable (i.e. esp/EFI/Linux/linux-kernel-machine_id-build_id.efi). EFI binaries in this directory are automatically detected by systemd-boot and therefore do not need an entry in /boot/loader/loader.conf.
As the command to figure out the kernel version is somewhat complex, it will not work by itself in a pacman hook. So create a script anywhere on your system. For this example it will be created in /usr/local/bin/.

The script will also copy the new vmlinuz kernel file to /boot/, since the kernel packages do not place files in /boot/ anymore.[1]

/usr/local/bin/dracut-install.sh
#!/usr/bin/env bash

args=('--force' '--no-hostonly-cmdline')

while read -r line; do
	if [[ "$line" == 'usr/lib/modules/'+([^/])'/pkgbase' ]]; then
		read -r pkgbase < "/${line}"
		kver="${line#'usr/lib/modules/'}"
		kver="${kver%'/pkgbase'}"

		install -Dm0644 "/${line%'/pkgbase'}/vmlinuz" "/boot/vmlinuz-${pkgbase}"
		dracut "${args[@]}" --hostonly "/boot/initramfs-${pkgbase}.img" --kver "$kver"
		dracut "${args[@]}" --add-confdir rescue  "/boot/initramfs-${pkgbase}-fallback.img" --kver "$kver"
	fi
done
/usr/local/bin/dracut-remove.sh
#!/usr/bin/env bash

while read -r line; do
	if [[ "$line" == 'usr/lib/modules/'+([^/])'/pkgbase' ]]; then
		read -r pkgbase < "/${line}"
		rm -f "/boot/vmlinuz-${pkgbase}" "/boot/initramfs-${pkgbase}.img" "/boot/initramfs-${pkgbase}-fallback.img"
	fi
done
You need to make the scripts executable. If you wish to add or remove flags, you should add them to your dracut configuration.

The next step is creating pacman hooks:

/etc/pacman.d/hooks/90-dracut-install.hook
[Trigger]
Type = Path
Operation = Install
Operation = Upgrade
Target = usr/lib/modules/*/pkgbase

[Action]
Description = Updating linux initcpios (with dracut!)...
When = PostTransaction
Exec = /usr/local/bin/dracut-install.sh
Depends = dracut
NeedsTargets
/etc/pacman.d/hooks/60-dracut-remove.hook
[Trigger]
Type = Path
Operation = Remove
Target = usr/lib/modules/*/pkgbase

[Action]
Description = Removing linux initcpios...
When = PreTransaction
Exec = /usr/local/bin/dracut-remove.sh
NeedsTargets
You should stop mkinitcpio from creating and removing initramfs images as well, either by removing mkinitcpio or with the following commands:

# ln -sf /dev/null /etc/pacman.d/hooks/90-mkinitcpio-install.hook
# ln -sf /dev/null /etc/pacman.d/hooks/60-mkinitcpio-remove.hook
Bluetooth keyboard support
Dracut will enable the bluetooth module automatically when a bluetooth keyboard is detected. However it is required that dracut is in hostonly mode for dracut to auto-discover bluetooth keyboard.

Limine boot loader support
The limine-dracut-supportAUR package utilizes limine-entry-tool with dracut and pacman hooks to automate the installation and removal of kernels and boot entries in the Limine boot loader. See Limine#Boot entry automation for more information.

Troubleshooting
Hibernation
If resuming from hibernation does not work, you may need to configure dracut to include the resume module. You will need to add a configuration file:

/etc/dracut.conf.d/resume-from-hibernate.conf
add_dracutmodules+=" resume "
If applicable to your system, you may also want to see instructions to resume from an encrypted swap partition including the dracut specific instructions.

LVM / software RAID / LUKS
If the kernel has issues auto discovering and mounting LVM / software RAID / LUKS blocks. You can retry generating an initramfs with the following kernel command line options:

rd.auto rd.lvm=1 rd.dm=1 rd.md=1 rd.luks=1
A stop job is running for "brltty"
If you have issues booting or very long shutdown processes while the system waits for brltty, add the following to the dracut configuration line:

omit_dracutmodules+=" brltty "
Alternatively, uninstall brltty if it is not needed.

No usable keyslot is available
Cannot use whirlpool hash for keyslot encryption.
Keyslot open failed.
No usable keyslot is available.
A failure to boot with a message similar to the above typically will only require the user to include the crypt module via add_dracutmodules.