# What's this?

Project Flatpakify is a python script that flatpakifies Gentoo ebuilds.
The purpose of this project is to:
- Write ebuilds and export as distro-agnostic flatpaks
- Customize flatpaks however Gentoo lets you (CFLAGS, USE flags, everything)
- To eliminate the need to write flatpaks manually anymore, and just write Gentoo regular ebuilds, this will benefit both developers, and Gentoo users

# First thing first: Install Gentoo. <img src="https://www.gentoo.org/assets/img/logo/gentoo-g.png" alt="Gentoo Logo" width="40" height="40" align="center">

https://www.gentoo.org/get-started/

# Second thing: Get used to making a ebuild.

https://devmanual.gentoo.org/

# Now: Instructions on how to use Flatpakify

### As example and since Seven Kingdoms (from 7kfans.com) is easily flatpakable, you can use it as it follows:

If you want to install it via emerge:

```emerge -v flatpakify```

```mkdir -p $HOME/my_flatpaks && cd $HOME/my_flatpaks```

```sudo flatpakify games-strategy/seven-kingdoms --bundle-name org.gentoo.sevenkingdoms.sevenkingdoms --install --rebuild-binary --command=7kaa  --clean```

Or, if you prefer git cloning and using the script locally:

```git clone https://github.com/StefanCristian/flatpakify.git```

```cd flatpakify```

```sudo ./flatpakify games-strategy/seven-kingdoms --bundle-name org.gentoo.sevenkingdoms.sevenkingdoms --install --rebuild-binary --command=7kaa  --clean```

In order to test it (you will also get all instructions how to install / uninstall / debug):

```flatpak run org.gentoo.sevenkingdoms.sevenkingdoms```

### As you might see, the pattern is:

```sudo flatpakify [category/packagename] [some needed dependencies that are not correctly found early on, please read caveats bellow] --bundle-name org.gentoo.yourpackage.YourPackage --with-deps --install --rebuild-binary --command=[if not ${PN}] --clean```

### Observations:
- Install only applications __you know__ that can be flatpakify-ed. Otherwise, don't expect random application from system can be flatpakified (like QT apps, for example). You must first study if the application you want as flatpak, can actually be flatpakified. You can check its source manually.
- Emerge always builds packages in the local ROOTFS specified in the format of ```./flatpak-build-org.gentoo.packagename.PackageName/rootfs/app/```
- Currently when building flatpaks, they're going to be built with your CFLAGS, and if ```march=native``` they're not going to be exportable, same case as their dependencies.
- But, if you want to offer architecture-optimized Flatpaks for only certain CPU architectures, now is your chance!
- Whenever you change your system's USE flags, you will observe that depending on those USE flags dependencies will change. Including for your application. Not to worry, though, this is part of the process. And those dependencies will already be included into your flatpak automatically.

### Further instructions:
- First thing first: install the freedesktop 25.08 Platform and SDK via:

```flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo```

```sudo flatpak install flathub org.freedesktop.Platform//25.08```

```sudo flatpak install flathub org.freedesktop.Sdk//25.08```

- Do __NOT__ run as root, only regular user with __sudo__
- Always run from a controlled, temporary directory when you are building your apps, preferably in your app source directory
- Category/package is __mandatory__, you can't use ```flatpakify randompackage```
- You must use ```--command=[your executable]``` if your executable name is not identical to ```${PN}``` [(from Gentoo Developer Manual)](https://devmanual.gentoo.org/ebuild-writing/variables/). If your app command is identical to ```${PN}```, you don't have to specify any ```--command```, for example many applications are following proper MAKEFILE rules to ```make install``` where their variables are set to install, based on the actual name of the package.
- If you have to recompile it everytime, you must use ```--rebuild-binary```; it's in the TODO list to skip dependencies to be compiled every time.
- If you want to keep the rootfs/app/ files and debug them directly on spot, you can remove the --clean option. The ```--clean``` option is generally used to remove the rootfs/* details after the packaging.
- If you don't want all the possible runtime dependencies added to your flatpak, you can selectively use ```--with-deps``` for a first-level runtime dependencies only + the ones you manually specify after, i.e. ```sudo flatpakify <category/package> <dep1> <dep2> <dep3> --with-deps --install --rebuild-binary``` if your application has direct runtime dependencies.
- I recommend declaring ```PKGIDR``` somewhere before running this script, or export it in the bash terminal, in order to not _infect_ your actual HOST binary packages.
- Don't overcomplicate things in your ebuild(s). The best ebuild is literally a empty one just like in my [example here](https://gitlab.com/argent/argent-ws/-/blob/master/dev-util/flatpakify/flatpakify-1.0.5.ebuild). If you have proper Makefiles, Meson builds, CMakeLists, and so forth, you'll observe that Portage knows exactly where to install them, how, and what configuration you can pass them - whole magic is already here.
- If any of your files _escape_ the PREFIX, you must handle it with the source makefiles. You don't have to be profficient in making ebuilds, but in creating proper build/makefiles.
- __ALWAYS__ test your application __BEFORE__ flatpakifying it so you can make sure it's flatpakify-able. Do it precisely like this:

```sudo EPREFIX=/app emerge -va --root=/absolute/localpath/tomyapp/flatpak-build-something/rootfs/ category/myapplication```


### Cleaning after compiling

- When using ```--rebuild-binary```, it will always compile everything, including the dependencies. It can be a long time.
- If you don't want to recompile the dependencies of your application every time, you can remove the ```--rebuild-binary``` option, but that means you need to clean the gentoo archived precompiled package made by the main command.
- If you do not use this ```--rebuild-binary```, and you have compiled your application and deps at least once (successfully), package(s) will be created and will have the purple color when you want to reinstall / recompile it. That means it's a precompiled binary, so it won't get recompiled unless you manually clean it.
- In order to clean it, you have to manually remove it from the local __binpkgs__ folder like this:

```sudo rm -rf ./binpkgs/your_package_category/your_package_name/*```

```sudo EPREFIX="/app" PKGDIR="./binpkgs" emaint binhost --fix```

- Or, if you have the flatpakify package installed via Gentoo, you can run:

```sudo flatpakify-clean-precompiled <CATEGORY>/<PACKAGENAME>```

i.e.:

```sudo flatpakify-clean-precompiled games-strategy/seven-kingdoms```


- In short, your complete command on a Gentoo with a installed flatpakify will look like this:

```sudo ./flatpakify games-strategy/seven-kingdoms --bundle-name org.gentoo.sevenkingdoms.sevenkingdoms --install --rebuild-binary --command=7kaa  --clean && sudo flatpakify-clean-precompiled games-strategy/seven-kingdoms ```


### Right now the script is very rudimentary, meaning we have a few caveats:
- If your app doesn't find a specific library (for example not present in the flatpak), you must use ```equery b <missing-library>``` and add that package to the ```flatpakify <packagename> dependency1 dependency2 dependency3``` list of to-be-installed such as example ```sudo flatpakify games-strategy/seven-kingdoms c-ares nghttp3 boost whatever --install...```. This is a caveat which I will be treating in the following period.
- Due to the fact that flatpak always needs to have the application files compiled with --prefix=/app and encapsulate as such, we're using ```EPREFIX=/app``` to all built apps, and ```--root``` to point to the new local rootfs. This produces perfectly normal packages, but the application you are building __must necessarily have build support for such paths and prefixes__
- There's no description category or links category implemented as options, I will have to implement them in time. Currently only the functional part is the most important, so that we can run the flatpaks easy.
- Your app's ___runtime dependencies must mandatory be installed in the HOST system___ before you compile your program. So, give it a go and compile your program first with ```sudo EPREFIX="/app" --root=/absolute/localpath/tomyapp/flatpak-build-something/rootfs/ emerge -v myapplication``` after writing your _empty_ ebuild [(example here)](https://gitlab.com/argent/argent-ws/-/blob/master/dev-util/flatpakify/flatpakify-1.0.5.ebuild), you anyway have to do this manually before flatpakification. But the fix to this will be added in TODO in the future for your programs to use encapsulated runtime libraries which are going to be used in your applications in the same location they're going to be built. It's not a hard TODO, but for the moment it makes the developer responsible on how Gentoo dependencies work in the system, and how you build your application.
- I have not treated complex situations yet, I have tested with C/C++ applications for the moment, so I do not know (yet) how RUST, GO, NodeJS, or others behave. It's a work in progress.

### TODO:
- Import proper portage library to determine proper dependencies of given package. Right now if you specify ```--with-deps```, it does a double-emerge sequence. First it emerges the first-level runtime dependencies, then emerges your target(s).
- To implement option to select which already compiled lbiraries you want to keep in the flatpak package.
- Description management [based on autodetection]
- Icons and links management of apps [based on autodetection]
- Create own Gentoo Platform and SDK universally exported and hosted on Flathub, so everyone can use your runtime base
- Create Gentoo runtime, for example a set of development libraries built on Gentoo which can be exported in order to be used in any other +-GNU Linux distribution
- Implement some identification of already-present libs inside the Gentoo/Freedesktop Flatpak Platform & SDK in comparison with first level of runtime dependencies identified based on user given package.
- Implement ```--use-dependencies-from-system``` (or something like this) option, in order for the application to use precompiled binaries from your $HOST $PKGIDR, instead of compiling them every time. I'm not sure this is ok, but most probably will be some of the most required features. The dependecies from the system option must compare with all the flatpak freedesktop runtime libraries that are already installed inside the runtime, so that we identify the exact packages and libraries that we should exclude from recompiling and packaging in our flatpak. Otherwise, this option would take __all__ runtime dependencies and we don't need all of them.
- User requested stuff to github.com/stefancristian/flatpakify/issues
- Find a way to expand FEATURES and EMERGE_DEFAULT_OPTS, and let the users decide what sort of options they want, without having to write it manually every time in terminal.