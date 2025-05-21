Install Arch Linux on LVM

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

LVM
Installation guide
You should create your LVM Volumes between the partitioning and formatting steps of the installation procedure. Instead of directly formatting a partition to be your root file system, the file system will be created inside a logical volume (LV).

Quick overview:

Install the required packages. (refer to LVM#Installation)
Create partition(s) where your physical volumes (PVs) will reside.
Create your PVs. If you have one disk it is best to just create one PV in one large partition. If you have multiple disks you can create partitions on each of them and create a PV on each partition.
Create your volume group (VG) and add all PVs to it.
Create logical volumes (LVs) inside that VG.
Continue with Installation guide#Format the partitions.
When you reach the Installation guide#Initramfs section in the Installation guide, add the lvm2 hook to /etc/mkinitcpio.conf (see below for details).
Warning: /boot cannot reside in LVM when using a boot loader which does not support LVM (only GRUB is known to support LVM). You must create a separate /boot partition and format it directly.
Installation
You will follow along with the installation guide until you come to Installation guide#Partition the disks. At this point you will diverge and doing all your partitioning with LVM in mind.

Create partitions
First, partition your disks as required before configuring LVM.

Create the partitions:

If you use GUID Partition Table, set the partition type GUID to E6D6D379-F507-44C2-A23C-238F2A3DF928 (partition type Linux LVM in fdisk and 8e00 in gdisk).
If you use Master Boot Record partition table, set the partition type ID to 8e (partition type Linux LVM in fdisk).
Create physical volumes
To list all your devices capable of being used as a physical volume:

# lvmdiskscan
Warning: Make sure you target the correct device, or below commands will result in data loss!
Create a physical volume on them:

# pvcreate DEVICE
This command creates a header on each device so it can be used for LVM. As defined in LVM#LVM building blocks, DEVICE can be any block device, e.g. a disk /dev/sda, a partition /dev/sda2 or a loop back device. For example:

# pvcreate /dev/sda2
You can track created physical volumes with:

# pvdisplay
You can also get summary information on physical volumes with:

# pvscan
Tip: If you run into trouble with a pre-existing disk signature, you can delete it using wipefs.
Create and extend your volume group
First you need to create a volume group on any one of the physical volumes:

# vgcreate volume_group physical_volume
For example:

# vgcreate VolGroup00 /dev/sda2
See lvm(8) for a list of valid characters for volume group names.

Extending the volume group is just as easy:

# vgextend volume_group physical_volume
For example, to add both sdb1 and sdc to your volume group:

# vgextend VolGroup00 /dev/sdb1
# vgextend VolGroup00 /dev/sdc
You can track how your volume group grows with:

# vgdisplay
This is also what you would do if you wanted to add a disk to a RAID or mirror group with failed disks.

Note: You can create more than one volume group if you need to, but then you will not have all your storage presented as a single disk.
Combined creation of physical volumes and volume groups
LVM allows you to combine the creation of a volume group and the physical volumes in one easy step. For example, to create the group VolGroup00 with the three devices mentioned above, you can run:

# vgcreate VolGroup00 /dev/sda2 /dev/sdb1 /dev/sdc
This command will first set up the three partitions as physical volumes (if necessary) and then create the volume group with the three volumes. The command will warn you if it detects an existing filesystem on any devices.

Create logical volumes
Tip:
If you wish to use snapshots, logical volume caching, thin provisioned logical volumes or RAID see LVM#Logical volumes.
If a logical volume will be formatted with ext4, leave at least 256 MiB free space in the volume group to allow using e2scrub(8). After creating the last volume with -l 100%FREE, this can be accomplished by reducing its size with lvreduce -L -256M volume_group/logical_volume.
Now we need to create logical volumes on this volume group. You create a logical volume with the next command by specifying the new volume's name and size, and the volume group it will reside on:

# lvcreate -L size volume_group -n logical_volume
For example:

# lvcreate -L 10G VolGroup00 -n lvolhome
This will create a logical volume that you can access later with /dev/VolGroup00/lvolhome. Just like volume groups, you can use any name you want for your logical volume when creating it besides a few exceptions listed in lvm(8) § VALID_NAMES.

You can also specify one or more physical volumes to restrict where LVM allocates the data. For example, you may wish to create a logical volume for the root filesystem on your small SSD, and your home volume on a slower mechanical drive. Simply add the physical volume devices to the command line, for example:

# lvcreate -L 10G VolGroup00 -n lvolhome /dev/sdc1
To use all the free space left in a volume group, use the next command:

# lvcreate -l 100%FREE  volume_group -n logical_volume
You can track created logical volumes with:

# lvdisplay
Note: You may need to load the device-mapper kernel module (modprobe dm_mod) for the above commands to succeed.
Tip: You can start out with relatively small logical volumes and expand them later if needed. For simplicity, leave some free space in the volume group so there is room for expansion.
Format and mount logical volumes
Your logical volumes should now be located in /dev/YourVolumeGroupName/. If you cannot find them, use the next commands to bring up the module for creating device nodes and to make volume groups available:

# modprobe dm_mod
# vgscan
# vgchange -ay
Now you can format your logical volumes and mount them as normal partitions (see mount a file system for additional details):

# mkfs.fstype /dev/volume_group/logical_volume
# mount /dev/volume_group/logical_volume /mountpoint
For example:

# mkfs.ext4 /dev/VolGroup00/lvolhome
# mount /dev/VolGroup00/lvolhome /home
Warning: When choosing mountpoints, just select your newly created logical volumes (use: /dev/Volgroup00/lvolhome). Do not select the actual partitions on which logical volumes were created (do not use: /dev/sda2).
Configure the system
Make sure the lvm2 package is installed.

Tip: lvm2 provides the lvm2 hook. If you are running mkinitcpio in an arch-chroot for a new installation, lvm2 must be installed inside the arch-chroot for mkinitcpio to find the lvm2 hook. If lvm2 only exists outside the arch-chroot, mkinitcpio will output Error: Hook 'lvm2' cannot be found.
Adding mkinitcpio hooks
In case your root filesystem is on LVM, you will need to enable the appropriate mkinitcpio hooks, otherwise your system might not boot. Enable:

udev and lvm2 for the default busybox-based initramfs
systemd and lvm2 for systemd-based initramfs
udev is there by default. Edit the file and insert lvm2 between block and filesystems like so:

/etc/mkinitcpio.conf
HOOKS=(base udev ... block lvm2 filesystems)
For systemd based initramfs:

/etc/mkinitcpio.conf
HOOKS=(base systemd ... block lvm2 filesystems)
Afterwards, you can continue in normal installation instructions with the recreate the initramfs image step.

Kernel boot options
If the root file system resides in a logical volume, the root= kernel parameter must be pointed to the mapped device, e.g /dev/vg-name/lv-name.