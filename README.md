# Instructions on how to use

As example and since Seven Kingdoms (from 7kfans.com) is easily flatpakable, you can use it as it follows:

```sudo ./flatpakify.py games-strategy/seven-kingdoms enet --bundle-name org.gentoo.sevenkingdoms.sevenkingdoms --install --rebuild-binary --command=7kaa  --clean```

As you might observe, the pattern is:

```sudo flatpakify.py [category/packagename] [gentoo-runtime-dependency-of-your-package] --bundle-name org.gentoo.yourpackage.YourPackage --install --rebuild-binary --command=[if not ${PN}] --clean```

Observations:
- Install only applications __you know__ that can be flatpakify-ed. Otherwise, don't expect random application from system can be flatpakified (like QT apps, for example). You must first study if the application you want as flatpak, can actually be flatpakified. You can check manually.
- Emerge always builds packages in the local ROOTFS specified in the format of ./flatpak-build-org.gentoo.sevenkingdoms.datafiles/rootfs/app/
- Currently when building flatpaks, they're going to be built with your CFLAGS, and if ```march=native``` they're not going to be exportable, same case as their dependencies.
- But, if you want to offer architecture-optimized Flatpaks for only certain CPU architectures, now is your chance!

Further instructions:
- First thing first: install the freedesktop 24.08 SDK via:

```flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo```

```flatpak install flathub org.freedesktop.Platform//24.08```

```flatpak install flathub org.freedesktop.Sdk//24.08```

- do __NOT__ run as root, only regular user with __sudo__
- category/package is __mandatory__, you can't use ```./flatpakify randompackage```
- you must use ```--command=[your executable]``` if your executable name is not identical to ```${PN}``` [(from Gentoo Developer Manual)](https://devmanual.gentoo.org/ebuild-writing/variables/). If your app command is identical to ```${PN}```, you don't have to specify any ```--command```, for example many applications are following proper MAKEFILE rules to ```make install``` where their variables are set to install, based on the actual name of the package.
- if you have to recompile it everytime, you must use ```--rebuild-binary```
- if you want to keep the rootfs/app/ files and debug them directly on spot, you can remove the --clean option. The ```--clean``` option is generally used to remove the rootfs/* details after the packaging.
- you can use ```--with-deps``` for a first-level runtime dependencies, i.e. ```sudo ./flatpakify program --with-deps --install --rebuild-binary```

Right now the script is very rudimentary, meaning we have a few caveats:
- Due to the fact that flatpak always needs to have the application files compiled with --prefix=/app and encapsulate as such, we're using ```EPREFIX=/app``` to all built apps, and ```--root``` to point to the new local rootfs. This produces perfectly normal packages, but the application you are building __must necessarily have build support for such paths and prefixes__
- There's no description category or links category implemented as options, I will have to implement them in time. Currently only the functional part is the most important, so that we can run the flatpaks easy.
- The ___runtime dependencies you use must mandatory be installed in the HOST system___ before you compile your program. This will be added in TODO in the future for your programs to use encapsulated runtime libraries which are going to be used in your applications in the same location they're going to be built. It's not a hard TODO, but for the moment it makes the developer responsible on how how Gentoo dependencies work in the system.

TODO:
- Import proper portage library to determine proper dependencies of given package. Right now you have to mandatory specify all the runtime dependencies of the application together with the application. In the nearby future, this will be done automatically by the script.
- To implement option to select which already compiled lbiraries you want to keep in the flatpak package.
- Description management [based on autodetection]
- Icons and links management of apps [based on autodetection]
- User requested stuff to github.com/stefancristian/flatpakify-with-portage/issues
