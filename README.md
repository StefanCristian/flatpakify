# What's this?

Project Flatpakify is a python script that flatpakifies Gentoo ebuilds.
The purpose of this project is to:
- Write ebuilds and export as distro-agnostic flatpaks
- Customize flatpaks however Gentoo lets you (CFLAGS, USE flags, everything)
- To eliminate the need to write flatpaks manually anymore, and just write Gentoo regular ebuilds, this will benefit both developers, and Gentoo users

# First thing first: Install Gentoo. <img src="https://www.gentoo.org/assets/img/logo/gentoo-g.png" alt="Gentoo Logo" width="40" height="40" align="center">

https://www.gentoo.org/get-started/

# Instructions on how to use Flatpakify

### As example and since Seven Kingdoms (from 7kfans.com) is easily flatpakable, you can use it as it follows:

If you want to install it via emerge:

```emerge -v flatpakify```

```mkdir -p $HOME/my_flatpaks && cd $HOME/my_flatpaks```

```sudo flatpakify games-strategy/seven-kingdoms c-ares nghttp3 --bundle-name org.gentoo.sevenkingdoms.sevenkingdoms --with-deps --install --rebuild-binary --command=7kaa  --clean```

Or, if you prefer git cloning and using the script locally:

```git clone https://github.com/StefanCristian/flatpakify.git```

```cd flatpakify```

```sudo ./flatpakify.py games-strategy/seven-kingdoms c-ares nghttp3 --bundle-name org.gentoo.sevenkingdoms.sevenkingdoms --with-deps --install --rebuild-binary --command=7kaa  --clean```

### As you might see, the pattern is:

```sudo flatpakify [category/packagename] [some needed dependencies that are not correctly found early on, please read caveats bellow] --bundle-name org.gentoo.yourpackage.YourPackage --with-deps --install --rebuild-binary --command=[if not ${PN}] --clean```

### Observations:
- Install only applications __you know__ that can be flatpakify-ed. Otherwise, don't expect random application from system can be flatpakified (like QT apps, for example). You must first study if the application you want as flatpak, can actually be flatpakified. You can check its source manually.
- Emerge always builds packages in the local ROOTFS specified in the format of ```./flatpak-build-org.gentoo.packagename.PackageName/rootfs/app/```
- Currently when building flatpaks, they're going to be built with your CFLAGS, and if ```march=native``` they're not going to be exportable, same case as their dependencies.
- But, if you want to offer architecture-optimized Flatpaks for only certain CPU architectures, now is your chance!

### Further instructions:
- First thing first: install the freedesktop 24.08 SDK via:

```flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo```

```flatpak install flathub org.freedesktop.Platform//24.08```

```flatpak install flathub org.freedesktop.Sdk//24.08```

- do __NOT__ run as root, only regular user with __sudo__
- always run from a controlled, temporary directory when you are building your apps, preferably in your app source directory
- category/package is __mandatory__, you can't use ```flatpakify randompackage```
- you must use ```--command=[your executable]``` if your executable name is not identical to ```${PN}``` [(from Gentoo Developer Manual)](https://devmanual.gentoo.org/ebuild-writing/variables/). If your app command is identical to ```${PN}```, you don't have to specify any ```--command```, for example many applications are following proper MAKEFILE rules to ```make install``` where their variables are set to install, based on the actual name of the package.
- if you have to recompile it everytime, you must use ```--rebuild-binary```; it's in the TODO list to skip dependencies to be compiled every time.
- if you want to keep the rootfs/app/ files and debug them directly on spot, you can remove the --clean option. The ```--clean``` option is generally used to remove the rootfs/* details after the packaging.
- you can (and generally must) use ```--with-deps``` for a first-level runtime dependencies, i.e. ```sudo flatpakify program --with-deps --install --rebuild-binary``` if your application has direct runtime dependencies
- I recommend declaring ```PKGIDR``` somewhere before running this script, or export it in the bash terminal, in order to not _infect_ your actual HOST binary packages.

### Right now the script is very rudimentary, meaning we have a few caveats:
- If your app doesn't find a specific library (for example not present in the flatpak), you must use ```equery b <missing-library>``` and add that package to the ```flatpakify category/package category/dependency1 category/dependency2``` list of to-be-installed such as example ```sudo flatpakify games-strategy/seven-kingdoms c-ares nghttp3 --install...```. This is a caveat which I will be treating in the following period.
- Due to the fact that flatpak always needs to have the application files compiled with --prefix=/app and encapsulate as such, we're using ```EPREFIX=/app``` to all built apps, and ```--root``` to point to the new local rootfs. This produces perfectly normal packages, but the application you are building __must necessarily have build support for such paths and prefixes__
- There's no description category or links category implemented as options, I will have to implement them in time. Currently only the functional part is the most important, so that we can run the flatpaks easy.
- The ___runtime dependencies (of your app) must mandatory be installed in the HOST system___ before you compile your program. So, give it a go and compile your program first with ```emerge -v myapplication``` after writing your _empty_ ebuild [(example here)](https://gitlab.com/argent/argent-ws/-/blob/master/app-admin/flatpakify/flatpakify-1.0.0.ebuild?ref_type=heads), you anyway have to do this manually before flatpakification. But the fix to this will be added in TODO in the future for your programs to use encapsulated runtime libraries which are going to be used in your applications in the same location they're going to be built. It's not a hard TODO, but for the moment it makes the developer responsible on how Gentoo dependencies work in the system, and how you build your application.
- I have not treated complex situations yet, I have tested with C/C++ applications for the moment, so I do not know (yet) how RUST, GO, NodeJS, or others behave. It's a work in progress.

### TODO:
- Import proper portage library to determine proper dependencies of given package. Right now if you specify ```--with-deps```, it does a double-emerge sequence. First it emerges the first-level runtime dependencies, then emerges your target(s).
- To implement option to select which already compiled lbiraries you want to keep in the flatpak package.
- Description management [based on autodetection]
- Icons and links management of apps [based on autodetection]
- Create own Gentoo Platform and SDK universally exported and hosted on Flathub, so everyone can use your runtime base
- Create Gentoo runtime, for example a set of development libraries built on Gentoo which can be exported in order to be used in any other +-GNU Linux distribution
- Implement some identification of already-present libs inside the Gentoo/Freedesktop Flatpak Platform & SDK in comparison with first level of runtime dependencies identified based on user given package.
- Implement ```--use-dependencies-from-system``` (or something like this) option, in order for the application to use precompiled binaries from your $HOST $PKGIDR, instead of compiling them every time. I'm not sure this is ok, but most probably will be some of the most required features.
- User requested stuff to github.com/stefancristian/flatpakify/issues