
New package: linux-surface 5.13.13 #32823
Closed
RononDex wants to merge 1 commit into void-linux:master from RononDex:master
+10,660 −0
Conversation 42
Commits 1
Checks 0
Files changed 6
Conversation
RononDex
RononDex commented Sep 3, 2021 •

New linux kernel for Microsoft Surface devices.
Taken from upstream https://github.com/linux-surface/linux-surface

template file is a copy from the linux kernel 5.13 template

[ci-skip]
General

    This is a new package and it conforms to the quality requirements

Have the results of the proposed changes been tested?

I use the packages affected by the proposed changes on a regular basis and confirm this PR works for me (Will be using it activly the next few days on my surface device and can then tick this box if stuff works)

    I generally don't use the affected packages but briefly tested this PR

@ericonr ericonr added the new-package label Sep 3, 2021
ericonr
ericonr reviewed Sep 3, 2021
Member
ericonr left a comment

    Most of the supported archs here don't make sense.
    Why does this vendor more patches on top of upstream instead of using the github release?
    Supporting device kernels is icky already, they definitely won't be versioned. Package should be linux-surface directly.

I'm not keen on yet another device kernel, but we might have to cope.
@RononDex
Author
RononDex commented Sep 3, 2021 •

Would it be possible to have this as a restricted package at least?
I am wanting to use void linux on my surface book too. I have already tried this kernel on arch linux on which it worked perfectly.

Having it directly in the upstream repo would be perfect for installing void on surface devices

EDIT: I can hapilly remove all the unneeded archs.
I am not sure what you mean by "github release" (2nd bullet point). The patches are a copy from the linux-surface repo (I have a shell script that always copies over the most up to date ones)
@CameronNemo
Contributor
CameronNemo commented Sep 3, 2021

    The patches are a copy from the linux-surface repo (I have a shell script that always copies over the most up to date ones)

Why maintain the patches in the void-packages repo, though? There are a lot of them and nobody really knows what they do or how to rebase them if need be. Why not just download the repo and apply the patches from there?

Also FYI they don't seem to support Linux 5.13, you probably want to use 5.10 (which is an LTS kernel). https://github.com/linux-surface/linux-surface/tree/master/patches#maintained-versions
@RononDex
Author
RononDex commented Sep 4, 2021 •

    Why maintain the patches in the void-packages repo, though? There are a lot of them and nobody really knows what they do or how to rebase them if need be. Why not just download the repo and apply the patches from there?

That's a fair argument, could adjust the template to do that

    Also FYI they don't seem to support Linux 5.13, you probably want to use 5.10 (which is an LTS kernel). https://github.com/linux-surface/linux-surface/tree/master/patches#maintained-versions

I have been running the 5.13 kernel on my surface book (with arch linux) for quite some time now and it works without issues
@q66
Contributor
q66 commented Sep 4, 2021

why haven't the patches been mainlined?
@RononDex
Author
RononDex commented Sep 4, 2021

    why haven't the patches been mainlined?

To be honest I am not sure. Probably because it contains unofficial drivers for proprietary drivers
@RononDex RononDex force-pushed the master branch from 54e6033 to 401e504
September 6, 2021 01:44
@RononDex
Author
RononDex commented Sep 6, 2021 •

Just force pushed some requested changes:

    Downloading needed patches from source with distfiles and using those
    Dynamically merge the kernel config with the surface-kernel one
    Remove unnecessary target architectures
    Renamed generated kernel files to end with "-surface"

@RononDex
Author
RononDex commented Sep 6, 2021

I am testing it on my surface book (gen 1) at the moment. It seems the package is having some issues with generating initramfs
Chocimier
Chocimier reviewed Sep 6, 2021
Member
Chocimier left a comment

We should wait for upstreaming rather than accept custom kernels outside arm imho.
srcpkgs/linux5.13-surface/template
Outdated
	# configure the kernel; otherwise use arch defaults and all stuff
	# as modules (allmodconfig).
	local arch subarch
    cd $XBPS_BUILDDIR/linux-$majorVersion/linux-$majorVersion
Member
@Chocimier Chocimier Sep 6, 2021

Set build_wrksrc, and look at manual what is current working directory for functions, most of cd won't be needed.
Fix indentaton.
Author
@RononDex RononDex Sep 7, 2021

Done
@kunihir0
srcpkgs/linux5.13-surface/template
Outdated
version=5.13.13
revision=3
wrksrc="linux-${version%.*}"
short_desc="Linux kernel and modules containing patches and drivers for Microsoft Surface series devices ( series)"
Member
@Chocimier Chocimier Sep 6, 2021

what series?
Author
@RononDex RononDex Sep 7, 2021

Typo, removed
@kunihir0
srcpkgs/linux5.13-surface/files/mv-debug
Outdated
@@ -0,0 +1,7 @@
#!/bin/sh
Member
@Chocimier Chocimier Sep 6, 2021

Have you considered symlinking files/ rather than copying?
Author
@RononDex RononDex Sep 7, 2021

Done
@kunihir0
srcpkgs/linux5.13-surface/template
Outdated
homepage="https://github.com/linux-surface/linux-surface"
distfiles="https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-${version%.*}.tar.xz
 https://cdn.kernel.org/pub/linux/kernel/v5.x/patch-${version}.xz 
 https://github.com/linux-surface/linux-surface/archive/refs/tags/arch-${version}-${revision}.tar.gz>surface-linux.tar.gz"
Member
@Chocimier Chocimier Sep 6, 2021

Revision must be independent from any external resources, use version=5.13.13.3, arch-${version%.*}-${version##*.}
Author
@RononDex RononDex Sep 7, 2021

Done, set revision to 1 and version to 5.13.13
Using a static link to the linux-surface distfile
@kunihir0
srcpkgs/linux5.13-surface/template
Outdated
# Template file for 'linux5.13-surface'
pkgname=linux5.13-surface
version=5.13.13
revision=3
Member
@Chocimier Chocimier Sep 6, 2021

Revision must be independent from any external resources. Use version=5.13.13.3, arch-${version%.*}-${version##*.}, set revision to 1.
Author
@RononDex RononDex Sep 7, 2021

Done, set revision to 1 and version to 5.13.13
Using a static link to the linux-surface distfile
@kunihir0
@RononDex RononDex force-pushed the master branch 3 times, most recently from 4982aac to 996a30c
September 7, 2021 09:54
@RononDex
Author
RononDex commented Sep 7, 2021

    why haven't the patches been mainlined?

To quote qzed from the matrix server:
image
@RononDex
Author
RononDex commented Sep 7, 2021

Just tested the new package / kernel on my surface book and stuff works.

However, for full device support more custom built packages (like a custom libwacom, iptsd = ipts daemon, etc) are needed.
The question is, how should I proceed? Is there any chance of getting these packages as a restricted package into this repository?
@q66
Contributor
q66 commented Sep 7, 2021

i'm opposed to packaging device-specific things that are upstreamable but they for whatever reason don't, so i'd be against packaging patched libwacom (go tell them to upstream it)

device-specific kernels have a precedent by now (i don't like it, but they're there) so i won't complain about that (fix things blocking review though: rename to linux-surface since there's no way we'll be packaging multiple versions, fix your tabs->spaces issues, simplify the template where appropriate, ...)
@RononDex RononDex force-pushed the master branch from 996a30c to de2187a
September 8, 2021 03:10
@RononDex
Author
RononDex commented Sep 8, 2021

I renamed the package to "linux-surface" and fixed the tabs vs spaces indentation
@RononDex RononDex force-pushed the master branch from de2187a to af21778
September 8, 2021 03:48
@RononDex
Author
RononDex commented Sep 8, 2021

This PR would not be ready for merge imo :)
Tested it and works on my surface book
@q66
Contributor
q66 commented Sep 8, 2021

is there supposed to be a dotconfig in the filesdir? the PR does not contain one but as it seems to me there should (otherwise none of the logic for .config gets picked up)

also archs= should be a part of the main metadata block, at the proper line (after revision= IIRC, refer to xlint)
@RononDex RononDex force-pushed the master branch from af21778 to 0f1e63e
September 10, 2021 14:10
@RononDex
Author
RononDex commented Sep 10, 2021 •

    is there supposed to be a dotconfig in the filesdir? the PR does not contain one but as it seems to me there should (otherwise none of the logic for .config gets picked up)

No, in do_configure() the specific architecture dotconfig file (in this case x86_64--dotconfig) is copied into the build directory as dotconfig, along with the specific linux-surface config from the git repo. These are then merged together using the kconfig merge script.

    also archs= should be a part of the main metadata block, at the proper line (after revision= IIRC, refer to xlint)

I left it in the same position as it was in the original template from linux5.13. However, I moved it to below revision= now.
@q66
Contributor
q66 commented Sep 10, 2021

exactly, I don't see any dotconfig in this PR so the merging will never run
@RononDex
Author
RononDex commented Sep 10, 2021 •

    exactly, I don't see any dotconfig in this PR so the merging will never run

They are sym-linked to linux5.13/files, which was a request from the reviewer

EDIT: see here #32823 (comment)
@q66
Contributor
q66 commented Sep 10, 2021

ah, I haven't noticed it was a symlink
@q66
Contributor
q66 commented Sep 10, 2021

that said, I'm not sure if I'm a fan because that means the kernel will have to be updated strictly in sync with main 5.13, as dotconfigs can change even between patch releases (cc @Chocimier)
@RononDex
Author
RononDex commented Sep 10, 2021

    that said, I'm not sure if I'm a fan because that means the kernel will have to be updated strictly in sync with main 5.13, as dotconfigs can change even between patch releases (cc @Chocimier)

The dotconfig can change and that's completly fine. I still merge it with the custom surface kernel config which takes higher priority. The idea is to have the normal void linux kernel (with all its custom config) supplemented with everything needed to run surface devices
@q66
Contributor
q66 commented Sep 10, 2021

it's not fine, because merging and having the base dotconfig be compatible with the current version of linux-surface are two unrelated things
@RononDex
Author
RononDex commented Sep 11, 2021

So you would prefer to not have it symlinked, but instead have its own config for the base kernel config?
@Chocimier
Member
Chocimier commented Sep 11, 2021

If linking doesn't help to keep config recent, then don't.
@RononDex RononDex force-pushed the master branch 2 times, most recently from 74044a3 to 2255ae9
September 15, 2021 06:56
@RononDex
Author
RononDex commented Sep 15, 2021

I have now removed the symbolic link to files and made a local copy of the needed files.

Also made the package a restricted package
@RononDex
New package: linux-surface 5.13.13
495e102
@RononDex RononDex force-pushed the master branch from 2255ae9 to 495e102
September 15, 2021 10:20
@RononDex
Author
RononDex commented Sep 17, 2021

Can somebody give me some feedback if this would be mergable this way?
@RononDex
Author
RononDex commented Sep 25, 2021

@Chocimier @q66 could you please review this PR or tell me if this does not have a chance of making it into the repo?
Thanks
@q66
Contributor
q66 commented Sep 25, 2021

I don't have any more comments, but also I don't use x86_64 so I'll leave it to some other maintainer
@Chocimier
Member
Chocimier commented Sep 27, 2021

I still prefer this work being mainlined rather than packaged separately.
@q66
Contributor
q66 commented Sep 27, 2021

i think everyone does, but that doesn't help users
@github-actions
github-actions bot commented Jun 4, 2022

Pull Requests become stale 90 days after last activity and are closed 14 days after that. If this pull request is still relevant bump it or assign it.
@github-actions github-actions bot added the Stale label Jun 4, 2022
@github-actions github-actions bot closed this Jun 18, 2022
@CameronNemo CameronNemo mentioned this pull request Feb 17, 2023
[Discussion] Should the pinebookpro-kernel template be retired, or expanded? #42333
Closed
@Anachron
Contributor
Anachron commented Aug 14, 2023

I was looking for a compatible tablet device that Void supports so I was sad to see this is not merged.

Anybody here using Void on linux surface anyway?
Merge info
Closed with unmerged commits

This pull request is closed.
@kunihir0
Add a comment
Comment

Add your comment here...
Remember, contributions to this repository should follow its contributing guidelines.
ProTip! Add comments to specific lines under Files changed.
Reviewers

@Chocimier
Chocimier

@ericonr
ericonr

Assignees
No one assigned
Labels
new-package
Stale
Projects
None yet
Milestone
No milestone
Development

Successfully merging this pull request may close these issues.

None yet

You’re not receiving notifications from this thread.
6 participants
@RononDex
@CameronNemo
@q66
@Chocimier
@Anachron
@ericonr
