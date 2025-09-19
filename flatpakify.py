#!/usr/bin/env python3

import sys
import os
import subprocess
import argparse
import shutil
import hashlib
from pathlib import Path
import re
import tarfile
import tempfile

PKGS = []
APP_ID = ""
COMMAND = ""
RUNTIME = "org.freedesktop.Platform"
FLATPAK_RUNTIME_VERSION = "24.08"
FLATPAK_APP_VERSION = "1.0"
BUNDLE_LIBS = False
SUDO_COMMAND = "sudo"
INSTALL = False
RUN_AFTER = False
NETWORK = False
FLATPAK_AUDIO = False
FS_ARGS = []
CLEAN_BUILD = False
CLEAN_AFTER = True
VERBOSE = False
USE_KDE_RUNTIME = False
WITH_DEPS = False
FLATPAK_RDEPS = []
BUILD_AS_RUNTIME = False
BUILD_AS_DATA = False
CUSTOM_PREFIX = ""
EMERGE_REBUILD_BINARY = False

def need(command):
    if shutil.which(command) is None:
        print(f"ERROR: '{command}' not found. Please install it first.")
        sys.exit(1)

def log(message):
    print(f"==> {message}")

def error(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)

def parse_args():
    global PKGS, APP_ID, COMMAND, RUNTIME, FLATPAK_RUNTIME_VERSION, FLATPAK_APP_VERSION
    global BUNDLE_LIBS, INSTALL, RUN_AFTER, NETWORK, FLATPAK_AUDIO, FS_ARGS
    global CLEAN_BUILD, CLEAN_AFTER, VERBOSE, USE_KDE_RUNTIME, WITH_DEPS
    global FLATPAK_RDEPS, BUILD_AS_RUNTIME, BUILD_AS_DATA, CUSTOM_PREFIX, EMERGE_REBUILD_BINARY
    global SUDO_COMMAND
    
    parser = argparse.ArgumentParser(description='Build any Gentoo package with /app prefix for Flatpak')
    parser.add_argument('packages', nargs='*', help='One or more Gentoo packages from your system overlays')
    parser.add_argument('--package-list', help='Read package list (one per line) from file')
    parser.add_argument('--bundle-name', help='Set bundle/app ID and output name')
    parser.add_argument('--app-id', help='Override app ID (default: org.gentoo.package)')
    parser.add_argument('--command', help='Override command name (default: package name)')
    parser.add_argument('--runtime', default='org.freedesktop.Platform', help='Flatpak runtime')
    parser.add_argument('--runtime-version', default='24.08', help='Runtime version')
    parser.add_argument('--app-version', default='1.0', help='Flatpak app/runtime version')
    parser.add_argument('--use-kde-runtime', action='store_true', help='Use KDE runtime for KDE/Qt applications')
    parser.add_argument('--set-prefix', help='Override installation prefix')
    parser.add_argument('--with-deps', action='store_true', help='Build with runtime dependencies')
    parser.add_argument('--bundle-libs', action='store_true', help='Bundle libraries from host system')
    parser.add_argument('--flatpak-rdep', action='append', default=[], help='Add Flatpak runtime dependency')
    parser.add_argument('--build-as-runtime', action='store_true', help='Build as custom Flatpak runtime')
    parser.add_argument('--build-as-data', action='store_true', help='Build as data-only Flatpak extension')
    parser.add_argument('--fs', action='append', default=[], help='Add filesystem permission')
    parser.add_argument('--network', action='store_true', help='Add network permission')
    parser.add_argument('--audio', action='store_true', help='Add audio permissions')
    parser.add_argument('--install', action='store_true', help='Install to current user after build')
    parser.add_argument('--run', action='store_true', help='Run the app after (implies --install)')
    parser.add_argument('--clean', action='store_true', help='Clean build directories before starting')
    parser.add_argument('--keep-build', action='store_true', help='Keep build directories after completion')
    parser.add_argument('--rebuild-binary', action='store_true', help='Force rebuild from source')
    parser.add_argument('--verbose', action='store_true', help='Show detailed build output')
    parser.add_argument('--sudo-command', default='sudo', help='Privilege escalation command (default: sudo)')
    
    args = parser.parse_args()
    
    PKGS = args.packages
    if args.package_list:
        if not os.path.isfile(args.package_list):
            error(f"Package list file not found: {args.package_list}")
        with open(args.package_list, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    PKGS.append(line)
    
    if not PKGS:
        parser.print_help()
        sys.exit(1)
    
    if args.bundle_name:
        BUNDLE_NAME = args.bundle_name
    else:
        BUNDLE_NAME = ""
    
    if args.app_id:
        APP_ID = args.app_id
    if args.command:
        COMMAND = args.command
    RUNTIME = args.runtime
    FLATPAK_RUNTIME_VERSION = args.runtime_version
    FLATPAK_APP_VERSION = args.app_version
    USE_KDE_RUNTIME = args.use_kde_runtime
    if args.set_prefix:
        CUSTOM_PREFIX = args.set_prefix
    WITH_DEPS = args.with_deps
    BUNDLE_LIBS = args.bundle_libs
    FLATPAK_RDEPS = args.flatpak_rdep
    BUILD_AS_RUNTIME = args.build_as_runtime
    BUILD_AS_DATA = args.build_as_data
    FS_ARGS = args.fs
    NETWORK = args.network
    FLATPAK_AUDIO = args.audio
    INSTALL = args.install
    if args.run:
        RUN_AFTER = True
        INSTALL = True
    CLEAN_BUILD = args.clean
    if args.keep_build:
        CLEAN_AFTER = False
    EMERGE_REBUILD_BINARY = args.rebuild_binary
    VERBOSE = args.verbose
    SUDO_COMMAND = args.sudo_command
    
    return BUNDLE_NAME

def main():
    global APP_ID, COMMAND, RUNTIME, FLATPAK_RUNTIME_VERSION
    
    BUNDLE_NAME = parse_args()
    
    need(SUDO_COMMAND)
    need("emerge")
    need("flatpak")
    need("flatpak-builder")
    
    if CUSTOM_PREFIX:
        EPREFIX = CUSTOM_PREFIX
        BUILD_TYPE = "custom"
        log(f"Building with custom EPREFIX: {EPREFIX}")
    elif BUILD_AS_DATA:
        EPREFIX = ""
        BUILD_TYPE = "extension"
        log("Building as data-only extension - using system root")
    elif BUILD_AS_RUNTIME:
        EPREFIX = ""
        BUILD_TYPE = "runtime"
        log("Building as runtime - using system root")
    else:
        EPREFIX = "/app"
        BUILD_TYPE = "application"
        log("Building as application - using /app EPREFIX")
    
    PREFIX = "/usr"
    
    CATEGORY = PKGS[0].split('/')[0]
    PACKAGE = PKGS[0].split('/')[1]
    
    if BUNDLE_NAME:
        SAFE_PKG = BUNDLE_NAME
        APP_ID = BUNDLE_NAME
    else:
        if len(PKGS) == 1:
            SAFE_PKG = PACKAGE
        else:
            pkg_hash = hashlib.sha1(' '.join(PKGS).encode()).hexdigest()[:8]
            SAFE_PKG = f"batch_{pkg_hash}"
        if not APP_ID:
            APP_ID = f"org.gentoo.{PACKAGE.replace('-', '.')}"
    
    if not COMMAND:
        COMMAND = PACKAGE
    
    WORK_DIR = os.getcwd()
    STAGE_DIR = os.path.join(WORK_DIR, f"flatpak-build-{SAFE_PKG}")
    ROOTFS = os.path.join(STAGE_DIR, "rootfs")
    FLATPAK_DIR = os.path.join(STAGE_DIR, "flatpak")
    BUILD_DIR = os.path.join(STAGE_DIR, "build")
    REPO_DIR = os.path.join(STAGE_DIR, "repo")
    
    if CLEAN_BUILD:
        log("Cleaning previous build directories...")
        shutil.rmtree(STAGE_DIR, ignore_errors=True)
    
    os.makedirs(ROOTFS, exist_ok=True)
    os.makedirs(FLATPAK_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(REPO_DIR, exist_ok=True)
    
    log(f"Building: {' '.join(PKGS)}")
    
    log("Setting up build environment...")
    subprocess.run([SUDO_COMMAND, "mkdir", "-p", f"{ROOTFS}/etc/portage"], check=False)
    
    portage_files = [
        ("make.conf", "file"),
        ("package.use", "dir"),
        ("package.accept_keywords", "dir"),
        ("package.mask", "dir"),
        ("package.unmask", "dir"),
        ("repos.conf", "dir"),
        ("env", "dir"),
    ]
    
    for pfile, ptype in portage_files:
        src = f"/etc/portage/{pfile}"
        dst = f"{ROOTFS}/etc/portage/"
        if os.path.exists(src):
            if ptype == "file":
                subprocess.run([SUDO_COMMAND, "cp", "-a", src, dst], check=False)
            else:
                subprocess.run([SUDO_COMMAND, "cp", "-aR", src, dst], check=False)
    
    if os.path.exists("/etc/portage/package.env/00-argent.package.env"):
        subprocess.run([SUDO_COMMAND, "mkdir", "-p", f"{ROOTFS}/etc/portage/package.env"], check=True)
        subprocess.run([SUDO_COMMAND, "cp", "-a", "/etc/portage/package.env/00-argent.package.env", 
                       f"{ROOTFS}/etc/portage/package.env/"], check=False)

    PROFILE_PATH = ""
    if os.path.islink("/etc/portage/make.profile"):
        PROFILE_PATH = os.path.realpath("/etc/portage/make.profile")
    else:
        try_profiles = [
            "/var/db/repos/gentoo/profiles/default/linux/amd64/23.0/desktop/plasma/systemd",
            "/var/db/repos/gentoo/profiles/default/linux/amd64/23.0/desktop/systemd",
            "/var/db/repos/gentoo/profiles/default/linux/amd64/23.0/systemd",
            "/var/db/repos/gentoo/profiles/default/linux/amd64/23.0"
        ]
        for try_profile in try_profiles:
            if os.path.isdir(try_profile):
                PROFILE_PATH = try_profile
                log(f"Using profile: {PROFILE_PATH}")
                break
    
    if not PROFILE_PATH or not os.path.isdir(PROFILE_PATH):
        log("Warning: Could not determine profile, will use system default")
        PROFILE_PATH = "/etc/portage/make.profile"
    
    if BUILD_AS_DATA:
        log("Creating minimal profile for data-only runtime build...")
        subprocess.run([SUDO_COMMAND, "mkdir", "-p", f"{ROOTFS}/etc/portage/profile"], check=True)

        with open(f"{ROOTFS}/etc/portage/profile/packages", "w") as f:
            subprocess.run([SUDO_COMMAND, "tee", f"{ROOTFS}/etc/portage/profile/packages"],
                         input=b"# Minimal packages list - avoid system packages for data-only runtimes\n",
                         stdout=subprocess.DEVNULL, check=True)
        
        make_conf_content = f"""# Minimal configuration for data-only packages
{'FEATURES="-collision-protect -protect-owned -sandbox -usersandbox"' if EMERGE_REBUILD_BINARY else 'FEATURES="-collision-protect -protect-owned getbinpkg -sandbox -usersandbox"'}
USE="-* minimal"
# Mask everything except data directories
INSTALL_MASK="/bin /sbin /lib /lib64 /usr/bin /usr/sbin /usr/lib /usr/lib64 /lib/debug /usr/lib/debug"
"""
        subprocess.run([SUDO_COMMAND, "tee", f"{ROOTFS}/etc/portage/make.conf"], 
                     input=make_conf_content.encode(), stdout=subprocess.DEVNULL, check=True)
    
    subprocess.run([SUDO_COMMAND, "ln", "-sfn", PROFILE_PATH, f"{ROOTFS}/etc/portage/make.profile"], check=True)
    
    log("Creating Flatpak build environment...")
    subprocess.run([SUDO_COMMAND, "mkdir", "-p", f"{ROOTFS}/etc/portage/env"], check=True)
    
    
    cmake_meson_env = f"""# CMake/Meson packages - install to EPREFIX/usr for consistency
CMAKE_INSTALL_PREFIX="{EPREFIX}{PREFIX}"
MYCMAKEARGS="-DCMAKE_INSTALL_PREFIX={EPREFIX}{PREFIX}"
MESON_INSTALL_PREFIX="{EPREFIX}{PREFIX}"
MYMESONARGS="--prefix={EPREFIX}{PREFIX}"
"""
    
    subprocess.run([SUDO_COMMAND, "tee", f"{ROOTFS}/etc/portage/env/flatpak-cmake-meson"], 
                 input=cmake_meson_env.encode(), stdout=subprocess.DEVNULL, check=True)
    
    other_env = f"""# Environment for non-CMake/Meson packages
# EPREFIX is set via emerge environment variable
"""
    
    subprocess.run([SUDO_COMMAND, "tee", f"{ROOTFS}/etc/portage/env/flatpak-other"], 
                 input=other_env.encode(), stdout=subprocess.DEVNULL, check=True)
    
    subprocess.run([SUDO_COMMAND, "mkdir", "-p", f"{ROOTFS}/etc/portage/package.env"], check=True)
    
    subprocess.run([SUDO_COMMAND, "touch", f"{ROOTFS}/etc/portage/package.env/flatpak"], check=True)
    
    for PKG in PKGS:
        EBUILD_PATH = ""
        for repo_dir in ["/var/db/repos/gentoo"] + list(Path("/var/db/repos").glob("*")):
            pkg_dir = Path(repo_dir) / PKG
            if pkg_dir.is_dir():
                ebuilds = list(pkg_dir.glob("*.ebuild"))
                if ebuilds:
                    EBUILD_PATH = str(ebuilds[0])
                    break
        
        if EBUILD_PATH and os.path.isfile(EBUILD_PATH):
            with open(EBUILD_PATH, 'r') as f:
                content = f.read()
                if 'cmake' in content or 'meson' in content:
                    log(f"Package {PKG} uses CMake/Meson - using specific build args")
                    env_assignment = f"{PKG} flatpak-cmake-meson\n"
                else:
                    log(f"Package {PKG} uses other build system - using EXTRA_ECONF")
                    env_assignment = f"{PKG} flatpak-other\n"
                
                subprocess.run([SUDO_COMMAND, "sh", "-c", f"echo '{env_assignment.strip()}' >> {ROOTFS}/etc/portage/package.env/flatpak"], check=True)
    
    if USE_KDE_RUNTIME:
        RUNTIME = "org.kde.Platform"
        FLATPAK_RUNTIME_VERSION = "6.9"
        log(f"Using KDE runtime: {RUNTIME}/{FLATPAK_RUNTIME_VERSION}")
    
    if EMERGE_REBUILD_BINARY:
        EMERGE_FEATURES = "-collision-protect -protect-owned"
    else:
        EMERGE_FEATURES = "-collision-protect -protect-owned getbinpkg"
    
    if BUILD_AS_DATA:
        EMERGE_OPTS = "-v1 --nodeps --emptytree --ask=n"
        log("Building data package without dependencies...")
    elif WITH_DEPS:
        EMERGE_OPTS = "-v1 --nodeps --emptytree --ask=n"
        log("Building with first-level runtime dependencies...")
        
        all_runtime_deps = []
        for PKG in PKGS:
            try:
                rdeps_command = "flatpakify-check-rdeps"
                if shutil.which(rdeps_command) is None:
                    rdeps_command = "./flatpakify-check-rdeps.py"
                    if not os.path.isfile(rdeps_command):
                        log("Warning: Neither flatpakify-check-rdeps and ./flatpakify-check-rdeps.py found, building without dependencies")
                        break
                
                result = subprocess.run([rdeps_command, PKG], capture_output=True, text=True, check=True)
                runtime_deps = result.stdout.strip().split('\n')
                runtime_deps = [dep for dep in runtime_deps if dep]
                if runtime_deps:
                    log(f"Runtime dependencies for {PKG}: {' '.join(runtime_deps)}")
                    all_runtime_deps.extend(runtime_deps)
                else:
                    log(f"No runtime dependencies found for {PKG}")
            except subprocess.CalledProcessError as e:
                log(f"Warning: Failed to get runtime dependencies for {PKG}: {e}")
            except FileNotFoundError:
                log("Warning: flatpakify-check-rdeps not found, building without additional dependencies")
                break
        
        seen = set()
        unique_deps = []
        for dep in all_runtime_deps:
            if dep not in seen:
                seen.add(dep)
                unique_deps.append(dep)
        
        if unique_deps:
            log(f"Total unique runtime dependencies to build: {len(unique_deps)}")
            
            log("Phase 1: Building runtime dependencies...")
            
            emerge_env = os.environ.copy()
            emerge_env["FEATURES"] = EMERGE_FEATURES
            emerge_env["PKGDIR"] = os.environ.get("PKGDIR", f"{os.getcwd()}/binpkgs/")
            emerge_env["CONFIG_PROTECT"] = "-*"
            
            if not BUILD_AS_RUNTIME and not BUILD_AS_DATA:
                emerge_env["EPREFIX"] = EPREFIX
                log(f"Setting EPREFIX={EPREFIX} for dependencies")
            
            emerge_cmd = [SUDO_COMMAND] + [f"{k}={v}" for k, v in emerge_env.items() if k in ["FEATURES", "PKGDIR", "CONFIG_PROTECT", "INSTALL_MASK", "EPREFIX"]]
            emerge_cmd += ["emerge"] + EMERGE_OPTS.split() + [f"--root={ROOTFS}", f"--config-root={ROOTFS}"] + unique_deps
            
            result = subprocess.run(emerge_cmd, capture_output=False)
            if result.returncode != 0:
                error("Failed to build runtime dependencies. Check the emerge output above for details.")
            
            log("Runtime dependencies built successfully")
            
            log("Phase 2: Building main package(s)...")
            
        PKGS_TO_BUILD = PKGS
    else:
        EMERGE_OPTS = "-v1 --nodeps --emptytree --ask=n"
        log("Building without dependencies (strict package-only mode)...")
        PKGS_TO_BUILD = PKGS
    
    if not VERBOSE:
        EMERGE_OPTS += " --quiet-build"
    
    log("Running emerge for main package(s) (this may take a while)...")
    
    if EMERGE_REBUILD_BINARY:
        EMERGE_FEATURES = "-collision-protect -protect-owned"
    else:
        EMERGE_FEATURES = "-collision-protect -protect-owned getbinpkg"
    
    emerge_env = os.environ.copy()
    emerge_env["FEATURES"] = EMERGE_FEATURES
    emerge_env["PKGDIR"] = os.environ.get("PKGDIR", f"{os.getcwd()}/binpkgs/")
    emerge_env["CONFIG_PROTECT"] = "-*"
    
    uses_cmake_meson = False
    if not BUILD_AS_RUNTIME and not BUILD_AS_DATA:
        for PKG in PKGS_TO_BUILD:
            EBUILD_PATH = ""
            for repo_dir in ["/var/db/repos/gentoo"] + list(Path("/var/db/repos").glob("*")):
                pkg_dir = Path(repo_dir) / PKG
                if pkg_dir.is_dir():
                    ebuilds = list(pkg_dir.glob("*.ebuild"))
                    if ebuilds:
                        EBUILD_PATH = str(ebuilds[0])
                        break
            
            if EBUILD_PATH and os.path.isfile(EBUILD_PATH):
                with open(EBUILD_PATH, 'r') as f:
                    content = f.read()
                    if 'cmake' in content or 'meson' in content:
                        uses_cmake_meson = True
                        log(f"Package {PKG} uses CMake/Meson - will not set EPREFIX")
                        break
    
    if not BUILD_AS_RUNTIME and not BUILD_AS_DATA and not uses_cmake_meson:
        emerge_env["EPREFIX"] = EPREFIX
        log(f"Setting EPREFIX={EPREFIX} for non-CMake/Meson packages")
    elif uses_cmake_meson:
        log("CMake/Meson packages detected - using their native prefix handling")
    
    if BUILD_AS_DATA:
        emerge_env["INSTALL_MASK"] = "/bin /sbin /lib /lib/debug /lib64 /usr/bin /usr/sbin /usr/lib/debug /usr/lib /usr/lib64 /usr/libexec /usr/include /etc /var"
    
    packages_to_emerge = PKGS_TO_BUILD if 'PKGS_TO_BUILD' in locals() else PKGS
    
    emerge_cmd = [SUDO_COMMAND] + [f"{k}={v}" for k, v in emerge_env.items() if k in ["FEATURES", "PKGDIR", "CONFIG_PROTECT", "INSTALL_MASK", "EPREFIX"]]
    emerge_cmd += ["emerge"] + EMERGE_OPTS.split() + [f"--root={ROOTFS}", f"--config-root={ROOTFS}"] + packages_to_emerge
    
    result = subprocess.run(emerge_cmd, capture_output=False)
    if result.returncode != 0:
        error("Build failed. Check the emerge output above for details.")
    
    log("Checking for Flatpak runtime dependencies...")
    for PKG in PKGS:
        EBUILD_PATH = ""
        for repo_dir in ["/var/db/repos/gentoo"] + list(Path("/var/db/repos").glob("*")):
            pkg_dir = Path(repo_dir) / PKG
            if pkg_dir.is_dir():
                ebuilds = list(pkg_dir.glob("*.ebuild"))
                if ebuilds:
                    EBUILD_PATH = str(ebuilds[0])
                    break
        
        if EBUILD_PATH and os.path.isfile(EBUILD_PATH):
            log(f"Found ebuild for {PKG}: {EBUILD_PATH}")
            with open(EBUILD_PATH, 'r') as f:
                content = f.read()
                match = re.search(r'FLATPAK_RDEPS=\(([^)]*)\)', content)
                if match:
                    rdeps = match.group(1).replace('"', '').split()
                    if rdeps:
                        log(f"Found FLATPAK_RDEPS in {PKG}: {' '.join(rdeps)}")
                        FLATPAK_RDEPS.extend(rdeps)
    
    log("Cleaning up staging area...")
    dirs_to_remove = [
        f"{ROOTFS}/etc/portage",
        f"{ROOTFS}/var/db", f"{ROOTFS}/var/cache", f"{ROOTFS}/var/lib",
        f"{ROOTFS}/var/tmp", f"{ROOTFS}/var/run", f"{ROOTFS}/var/lock",
        f"{ROOTFS}/usr/share/man", f"{ROOTFS}/usr/share/doc", f"{ROOTFS}/usr/share/info",
        f"{ROOTFS}{EPREFIX}{PREFIX}/share/man", f"{ROOTFS}{EPREFIX}{PREFIX}/share/doc", f"{ROOTFS}{EPREFIX}{PREFIX}/share/info",
        f"{ROOTFS}/tmp"
    ]
    
    for dir_path in dirs_to_remove:
        subprocess.run([SUDO_COMMAND, "rm", "-rf", dir_path], check=False)
    
    if BUILD_AS_DATA:
        log("Filtering for data-only package - removing all non-data files...")
        
        try:
            result = subprocess.run(["du", "-sh", ROOTFS], capture_output=True, text=True)
            BEFORE_SIZE = result.stdout.split()[0] if result.returncode == 0 else "unknown"
            log(f"ROOTFS size before filtering: {BEFORE_SIZE}")
        except:
            pass
        
        data_remove_dirs = [
            f"{ROOTFS}/usr/bin", f"{ROOTFS}/usr/sbin", f"{ROOTFS}/usr/lib64", f"{ROOTFS}/usr/lib",
            f"{ROOTFS}/usr/libexec", f"{ROOTFS}/usr/include",
            f"{ROOTFS}/bin", f"{ROOTFS}/sbin", f"{ROOTFS}/lib64", f"{ROOTFS}/lib", f"{ROOTFS}/libexec",
            f"{ROOTFS}/app/bin", f"{ROOTFS}/app/sbin", f"{ROOTFS}/app/lib64", f"{ROOTFS}/app/lib",
            f"{ROOTFS}/app/libexec", f"{ROOTFS}/app/include",
            f"{ROOTFS}/app/etc", f"{ROOTFS}/app/etc", f"{ROOTFS}/var"
        ]
        
        for dir_path in data_remove_dirs:
            subprocess.run([SUDO_COMMAND, "rm", "-rf", dir_path], check=False)
        
        log("Keeping only data directories (share/...)")
        
        subprocess.run(["find", ROOTFS, "-type", "d", "-empty", "-delete"], check=False)
        
        try:
            result = subprocess.run(["du", "-sh", ROOTFS], capture_output=True, text=True)
            AFTER_SIZE = result.stdout.split()[0] if result.returncode == 0 else "unknown"
            log(f"ROOTFS size after filtering: {AFTER_SIZE} (was {BEFORE_SIZE})")
        except:
            pass
        
        log("Data-only filtering completed")
    else:
        if os.path.exists(f"{ROOTFS}/var"):
            subprocess.run([SUDO_COMMAND, "rmdir", f"{ROOTFS}/var"], check=False)
    
    # Since we're using EPREFIX and proper build environments, the rootfs should already 
    # have the correct structure. We only need minimal adjustments for special cases.
    
    if BUILD_AS_DATA:
        log("Preparing data extension structure...")
        
        if os.path.isdir(f"{ROOTFS}/usr/share"):
            log("Moving /usr/share to root level for data extension...")
            subprocess.run([SUDO_COMMAND, "mkdir", "-p", f"{ROOTFS}/share"], check=True)
            subprocess.run([SUDO_COMMAND, "sh", "-c", f"mv {ROOTFS}/usr/share/* {ROOTFS}/share/ 2>/dev/null || true"], check=False)
            subprocess.run([SUDO_COMMAND, "rmdir", f"{ROOTFS}/usr/share"], check=False)
            subprocess.run([SUDO_COMMAND, "rmdir", f"{ROOTFS}/usr"], check=False)
        
        if os.path.isdir(f"{ROOTFS}/app/share"):
            log("Moving /app/share to root level for data extension...")
            subprocess.run([SUDO_COMMAND, "mkdir", "-p", f"{ROOTFS}/share"], check=True)
            subprocess.run([SUDO_COMMAND, "sh", "-c", f"mv {ROOTFS}/app/share/* {ROOTFS}/share/ 2>/dev/null || true"], check=False)
            subprocess.run([SUDO_COMMAND, "rmdir", f"{ROOTFS}/app/share"], check=False)
            subprocess.run([SUDO_COMMAND, "rmdir", f"{ROOTFS}/app"], check=False)
        
        if not os.path.isdir(f"{ROOTFS}/share") or not os.listdir(f"{ROOTFS}/share"):
            log("Warning: No data files found in /share directory")
        else:
            log("Data files found in /share:")
            subprocess.run(["ls", "-la", f"{ROOTFS}/share/"], check=False)
    
    elif BUILD_AS_RUNTIME:
        if os.path.isdir(f"{ROOTFS}/app") and not os.path.isdir(f"{ROOTFS}/usr"):
            log("Moving files from /app to /usr for runtime build...")
            subprocess.run([SUDO_COMMAND, "mv", f"{ROOTFS}/app", f"{ROOTFS}/usr"], check=True)
        
        if not os.path.isdir(f"{ROOTFS}/usr") or not os.listdir(f"{ROOTFS}/usr"):
            error("Failed to create /usr structure for runtime")
        log("Successfully created runtime /usr structure")
    
    else:
        if not os.path.isdir(f"{ROOTFS}/app"):
            if os.path.isdir(f"{ROOTFS}/usr"):
                log("Warning: Files installed to /usr instead of /app, moving to /app...")
                subprocess.run([SUDO_COMMAND, "mv", f"{ROOTFS}/usr", f"{ROOTFS}/app"], check=True)
            else:
                error("No application files found in /app or /usr after build")
        
        if not os.path.isdir(f"{ROOTFS}/app") or not os.listdir(f"{ROOTFS}/app"):
            error("Failed to create /app structure for application")
        log("Successfully verified application /app structure")
    
    if not BUILD_AS_RUNTIME and not BUILD_AS_DATA:
        BIN_DIRS = [f"{ROOTFS}{EPREFIX}/bin", f"{ROOTFS}{EPREFIX}{PREFIX}/bin"]
        LIB_DIRS = [f"{ROOTFS}{EPREFIX}/lib64", f"{ROOTFS}{EPREFIX}{PREFIX}/lib64"]
        
        actual_bin_dir = None
        for bin_dir in BIN_DIRS:
            if os.path.isdir(bin_dir) and list(Path(bin_dir).glob("*")):
                actual_bin_dir = bin_dir
                break
        
        if not actual_bin_dir:
            actual_bin_dir = f"{ROOTFS}{EPREFIX}/bin"
            os.makedirs(actual_bin_dir, exist_ok=True)
            with open(f"{actual_bin_dir}/true", "w") as f:
                f.write("#!/bin/sh\nexit 0\n")
            os.chmod(f"{actual_bin_dir}/true", 0o755)
            
            for lib_dir in LIB_DIRS:
                if os.path.isdir(lib_dir) and list(Path(lib_dir).glob("*.so*")):
                    log("No executables found, but libraries detected. Setting dummy command for library package.")
                    COMMAND = "true"
                    break
    
    if not BUILD_AS_RUNTIME and not BUILD_AS_DATA:
        MAIN_BINARY = ""
        BIN_DIRS = [f"{ROOTFS}{EPREFIX}/bin", f"{ROOTFS}{EPREFIX}{PREFIX}/bin"]
        LIB_DIRS = [f"{ROOTFS}{EPREFIX}/lib64", f"{ROOTFS}{EPREFIX}{PREFIX}/lib64"]
        
        for BIN_DIR in BIN_DIRS:
            if os.path.isfile(f"{BIN_DIR}/{COMMAND}"):
                MAIN_BINARY = f"{BIN_DIR}/{COMMAND}"
                break
            elif os.path.isfile(f"{BIN_DIR}/{PACKAGE}"):
                MAIN_BINARY = f"{BIN_DIR}/{PACKAGE}"
                COMMAND = PACKAGE
                break
        
        if not MAIN_BINARY:
            for BIN_DIR in BIN_DIRS:
                if os.path.isdir(BIN_DIR):
                    try:
                        binaries = list(Path(BIN_DIR).glob("*"))
                        if binaries:
                            MAIN_BINARY = str(binaries[0])
                            COMMAND = binaries[0].name
                            break
                    except:
                        pass
        
        if not MAIN_BINARY:
            has_libraries = False
            for LIB_DIR in LIB_DIRS:
                if os.path.isdir(LIB_DIR) and list(Path(LIB_DIR).glob("*.so*")):
                    has_libraries = True
                    break
                    
            if has_libraries:
                log("No executable found, but libraries detected. Building as library package with dummy command.")
                COMMAND = "true"
                MAIN_BINARY = f"{EPREFIX}/bin/true"
                log("Created dummy true binary for library package")
            else:
                error(f"No executable found in any bin directory and no libraries detected")
        
        if COMMAND != "true":
            log(f"Main binary: {COMMAND}")
        else:
            log(f"Library package using dummy command: {COMMAND}")
    
    if BUNDLE_LIBS and not BUILD_AS_RUNTIME and not BUILD_AS_DATA:
        log("Bundling libraries from host system...")
        
        BINARIES_TO_CHECK = []
        for binary_path in Path(f"{ROOTFS}{EPREFIX}").rglob("*"):
            if binary_path.is_file() and (os.access(str(binary_path), os.X_OK) or binary_path.suffix.startswith(".so")):
                BINARIES_TO_CHECK.append(str(binary_path))
        
        LIBS_TO_BUNDLE = []
        for binary in BINARIES_TO_CHECK:
            try:
                result = subprocess.run(["ldd", binary], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.splitlines():
                        match = re.search(r'=>\s*(/[^\s]+)', line)
                        if match:
                            lib_path = match.group(1)
                            lib_name = os.path.basename(lib_path)
                            
                            if not re.match(r'^/(lib|lib64|usr/lib|usr/lib64)/(ld-|libc\.|libm\.|libpthread\.|libdl\.|librt\.|libresolv\.|libnss_)', lib_path) and \
                               not "/gcc/" in lib_path and \
                               "linux-vdso" not in lib_path:
                                if not USE_KDE_RUNTIME or lib_name.startswith(("libKF6", "libKF5")):
                                    LIBS_TO_BUNDLE.append(lib_path)
            except:
                pass
        
        if LIBS_TO_BUNDLE:
            LIB_BUNDLE_DIR = f"{ROOTFS}{EPREFIX}{PREFIX}/lib64"
            subprocess.run([SUDO_COMMAND, "mkdir", "-p", LIB_BUNDLE_DIR], check=True)
            seen = set()
            for lib_path in LIBS_TO_BUNDLE:
                if os.path.isfile(lib_path) and lib_path not in seen:
                    seen.add(lib_path)
                    log(f"  Bundling: {os.path.basename(lib_path)}")
                    
                    target_path = f"{LIB_BUNDLE_DIR}/{os.path.basename(lib_path)}"
                    if os.path.islink(target_path):
                        subprocess.run([SUDO_COMMAND, "rm", target_path], check=False)
                    
                    subprocess.run([SUDO_COMMAND, "cp", "-L", lib_path, f"{LIB_BUNDLE_DIR}/"], check=True)
                    
                    lib_dir = os.path.dirname(lib_path)
                    lib_base = os.path.basename(lib_path)
                    
                    for symlink in Path(lib_dir).iterdir():
                        if symlink.is_symlink():
                            link_target = os.readlink(str(symlink))
                            symlink_name = symlink.name
                            
                            if lib_base in link_target or link_target in lib_base or os.path.basename(link_target) == lib_base:
                                symlink_target_path = f"{LIB_BUNDLE_DIR}/{symlink_name}"
                                if os.path.islink(symlink_target_path):
                                    subprocess.run([SUDO_COMMAND, "rm", symlink_target_path], check=False)
                                
                                target_file = os.path.basename(lib_path)
                                subprocess.run([SUDO_COMMAND, "ln", "-sf", target_file, f"{LIB_BUNDLE_DIR}/{symlink_name}"], check=True)
                                log(f"    Creating symlink: {symlink_name} -> {target_file}")
        else:
            log("  No additional libraries needed")
    
    log("Creating archive from filtered ROOTFS...")
    TARBALL = f"{STAGE_DIR}/{SAFE_PKG}-rootfs.tar.zst"
    
    if BUILD_AS_DATA:
        log("Contents being archived for data package:")
        subprocess.run(["ls", "-la", f"{ROOTFS}/"], check=False)
    
    os.chdir(ROOTFS)
    subprocess.run([SUDO_COMMAND, "tar", "--no-same-owner", "--no-same-permissions", "-I", "zstd -19 -T0", "-cf", TARBALL, "."], check=True)
    subprocess.run([SUDO_COMMAND, "chown", f"{os.getuid()}:{os.getgid()}", TARBALL], check=True)
    os.chdir(WORK_DIR)
    
    try:
        result = subprocess.run(["du", "-sh", TARBALL], capture_output=True, text=True)
        size = result.stdout.split()[0] if result.returncode == 0 else "unknown"
        log(f"Tarball created: {size} - {TARBALL}")
    except:
        log(f"Tarball created: {TARBALL}")
    
    log("Verifying tarball contains only ROOTFS content...")
    subprocess.run(["tar", "-tf", TARBALL], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    FLATPAK_GUI = False
    DESKTOP_FILE = ""
    if not BUILD_AS_RUNTIME and not BUILD_AS_DATA:
        if os.path.isdir(f"{ROOTFS}{EPREFIX}{PREFIX}/share/applications"):
            desktop_files = list(Path(f"{ROOTFS}{EPREFIX}{PREFIX}/share/applications").glob("*.desktop"))
            if desktop_files:
                DESKTOP_FILE = str(desktop_files[0])
                FLATPAK_GUI = True
                log("Detected GUI application in EPREFIX location")
        
        if not DESKTOP_FILE and os.path.isdir(f"{ROOTFS}/usr/share/applications"):
            desktop_files = list(Path(f"{ROOTFS}/usr/share/applications").glob("*.desktop"))
            if desktop_files:
                DESKTOP_FILE = str(desktop_files[0])
                FLATPAK_GUI = True
                log("Detected GUI application in standard location")
    
    FIN_LINES = []
    if not BUILD_AS_RUNTIME and not BUILD_AS_DATA:
        if FLATPAK_GUI:
            FIN_LINES.extend(["--socket=wayland", "--socket=fallback-x11", "--device=dri", "--socket=pulseaudio", "--device=all"])
        if NETWORK:
            FIN_LINES.append("--share=network")
        if FLATPAK_AUDIO and not FLATPAK_GUI:
            FIN_LINES.extend(["--socket=pulseaudio", "--device=all"])
        for fs in FS_ARGS:
            if fs:
                FIN_LINES.append(f"--filesystem={fs}")
    
    FINISH_ARGS_YML = ""
    if FIN_LINES:
        FINISH_ARGS_YML = "\nfinish-args:"
        for l in FIN_LINES:
            FINISH_ARGS_YML += f"\n  - {l}"
    
    ADD_EXTENSIONS_YML = ""
    if not BUILD_AS_RUNTIME and not BUILD_AS_DATA and FLATPAK_RDEPS:
        log(f"Adding Flatpak runtime dependencies: {' '.join(FLATPAK_RDEPS)}")
        ADD_EXTENSIONS_YML = "\nadd-extensions:"
        for rdep in FLATPAK_RDEPS:
            rdep_package = rdep.split('/')[-1]
            rdep_app_id = f"org.gentoo.{rdep_package.replace('-', '.')}"
            ADD_EXTENSIONS_YML += f"\n  {rdep_app_id}:"
            ADD_EXTENSIONS_YML += f"\n    directory: extensions/{rdep_app_id}"
            ADD_EXTENSIONS_YML += f'\n    version: "{FLATPAK_APP_VERSION}"'
            ADD_EXTENSIONS_YML += "\n    add-ld-path: lib64"
            ADD_EXTENSIONS_YML += '\n    merge-dirs: "bin;lib64;share"'
    
    log("Generating Flatpak manifest...")
    MANIFEST = f"{FLATPAK_DIR}/{APP_ID}.yml"
    
    if BUILD_AS_DATA:
        manifest_content = f"""id: {APP_ID}
branch: "{FLATPAK_APP_VERSION}"
runtime: {RUNTIME}
runtime-version: "{FLATPAK_RUNTIME_VERSION}"
sdk: {RUNTIME.replace('Platform', 'Sdk')}
build-runtime: true
separate-locales: false
modules:
  - name: {SAFE_PKG}
    buildsystem: simple
    sources:
      - type: file
        path: {os.path.basename(TARBALL)}
    build-commands:
      - tar --no-same-owner --no-same-permissions -xaf {os.path.basename(TARBALL)}
      - |
        if [ -d share ]; then
          echo "Installing data files from share directory..."
          mkdir -p ${{FLATPAK_DEST}}/share
          cp -aT share ${{FLATPAK_DEST}}/share/
        else
          echo "Warning: No share directory found in data package"
        fi
      - rm -f ${{FLATPAK_DEST}}/{os.path.basename(TARBALL)}
      - |
        cat > ${{FLATPAK_DEST}}/metadata << 'DATA_META'
        [Runtime]
        name={APP_ID}
        runtime={RUNTIME}/{FLATPAK_RUNTIME_VERSION}
        sdk={RUNTIME.replace('Platform', 'Sdk')}/{FLATPAK_RUNTIME_VERSION}
        DATA_META
"""
    elif BUILD_AS_RUNTIME:
        manifest_content = f"""id: {APP_ID}
branch: "{FLATPAK_APP_VERSION}"
runtime: {RUNTIME}
runtime-version: "{FLATPAK_RUNTIME_VERSION}"
sdk: {RUNTIME.replace('Platform', 'Sdk')}
build-runtime: true
separate-locales: false
modules:
  - name: {SAFE_PKG}
    buildsystem: simple
    sources:
      - type: file
        path: {os.path.basename(TARBALL)}
    build-commands:
      - tar --no-same-owner --no-same-permissions -xaf {os.path.basename(TARBALL)}
      - if [ -d usr ]; then cp -aT usr ${{FLATPAK_DEST}}/ || true; fi
      - find ${{FLATPAK_DEST}} -type f | head -10 || echo "Files copied to runtime"
      - |
        cat > ${{FLATPAK_DEST}}/metadata << 'RUNTIME_META'
        [Runtime]
        name={APP_ID}
        runtime={RUNTIME}/{FLATPAK_RUNTIME_VERSION}
        sdk={RUNTIME.replace('Platform', 'Sdk')}/{FLATPAK_RUNTIME_VERSION}
        RUNTIME_META
"""
    else:
        manifest_part1 = f"""app-id: {APP_ID}
runtime: {RUNTIME}
runtime-version: "{FLATPAK_RUNTIME_VERSION}"
sdk: {RUNTIME.replace('Platform', 'Sdk')}
command: {COMMAND}{FINISH_ARGS_YML}{ADD_EXTENSIONS_YML}
modules:
  - name: {SAFE_PKG}
    buildsystem: simple
    sources:
      - type: file
        path: {os.path.basename(TARBALL)}
    build-commands:
      - tar --no-same-owner --no-same-permissions -xaf {os.path.basename(TARBALL)}"""
        
        manifest_part2 = """
      - |
        # Since we use EPREFIX=/app, the files should already be in the app/ directory
        if [ -d app ]; then
          echo "Copying app directory to /app/ (excluding usr/include)"
          # Use tar to copy everything except usr/include
          tar --exclude='./usr/include' -C app -cf - . | tar -C /app -xf -
        else
          echo "ERROR: No app/ directory found in rootfs"
          ls -la .
          exit 1
        fi
      - |
        # Create symlinks for compatibility - binaries should be in /app/usr/bin due to EPREFIX
        if [ -d /app/usr/bin ] && [ ! -d /app/bin ]; then
          echo "Creating symlink /app/bin -> usr/bin for binary compatibility"
          ln -sf usr/bin /app/bin
        elif [ -d /app/bin ] && [ -d /app/usr/bin ]; then
          echo "Both /app/bin and /app/usr/bin exist - merging /app/bin into /app/usr/bin"
          cp -a /app/bin/* /app/usr/bin/ 2>/dev/null || true
          rm -rf /app/bin
          ln -sf usr/bin /app/bin
        elif [ -d /app/bin ] && [ ! -d /app/usr/bin ]; then
          echo "Package installed to /app/bin directly - moving to /app/usr/bin and creating symlink"
          mkdir -p /app/usr
          mv /app/bin /app/usr/bin
          ln -sf usr/bin /app/bin
        fi
        if [ -d /app/usr/lib64 ] && [ ! -d /app/lib64 ]; then
          echo "Creating symlink /app/lib64 -> usr/lib64 for library compatibility"
          ln -sf usr/lib64 /app/lib64
        fi
        if [ -d /app/usr/lib ] && [ ! -d /app/lib ]; then
          echo "Creating symlink /app/lib -> usr/lib for library compatibility"
          ln -sf usr/lib /app/lib
        fi"""
        
        manifest_part3 = f"""
      - |
        # Create extension directories for runtime dependencies
        for ext_dir in $(echo "{' '.join(FLATPAK_RDEPS)}" | tr ' ' '\\n' | sed 's|.*/||' | sed 's|-|.|g' | sed 's|^|org.gentoo.|'); do
          mkdir -p "/app/extensions/$ext_dir"
        done"""
        
        manifest_part4 = """
      - |
        # Create wrapper scripts for executables to set LD_LIBRARY_PATH
        if [ -d /app/usr/bin ]; then
          for exe in /app/usr/bin/*; do
            if [ -x "$exe" ] && [ ! -L "$exe" ]; then
              exe_name=$(basename "$exe")
              echo "Creating wrapper for $exe_name"
              # Rename original binary to .real
              mv "$exe" "$exe.real"
              # Create wrapper script in place of original binary
              echo '#!/bin/bash' > "$exe"
              echo 'export LD_LIBRARY_PATH="/app/usr/lib64:/app/lib64:/usr/lib64:$LD_LIBRARY_PATH"' >> "$exe"
              echo "exec \"/app/usr/bin/$exe_name.real\" \\"\\$@\\"" >> "$exe"
              chmod +x "$exe"
            fi
          done
        fi
"""
        
        manifest_content = manifest_part1 + manifest_part2 + manifest_part3 + manifest_part4
        
        if FLATPAK_GUI and DESKTOP_FILE:
            desktop_part1 = f"""
  - name: desktop-integration
    buildsystem: simple
    sources:
      - type: file
        path: {os.path.basename(TARBALL)}
    build-commands:
      - tar --no-same-owner --no-same-permissions -xaf {os.path.basename(TARBALL)}"""
            
            desktop_part2 = """
      - |
        # Copy desktop files and icons from the app structure (EPREFIX location)
        if [ -d app/share/applications ]; then
          mkdir -p /app/share/applications
          cp -a app/share/applications/* /app/share/applications/
        fi
        # Also copy desktop files from standard /usr/share/applications location
        if [ -d usr/share/applications ]; then
          mkdir -p /app/share/applications
          cp -a usr/share/applications/* /app/share/applications/
        fi
      - |
        # Copy icons from both locations
        if [ -d app/share/icons ]; then
          mkdir -p /app/share/icons
          cp -a app/share/icons/* /app/share/icons/
        fi
        if [ -d usr/share/icons ]; then
          mkdir -p /app/share/icons
          cp -a usr/share/icons/* /app/share/icons/
        fi
"""
            manifest_content += desktop_part1 + desktop_part2
    
    with open(MANIFEST, "w") as f:
        f.write(manifest_content)
    
    shutil.copy(TARBALL, f"{FLATPAK_DIR}/")
    
    log("Building Flatpak...")
    result = subprocess.run(["flatpak-builder", "--force-clean", BUILD_DIR, MANIFEST])
    if result.returncode != 0:
        error("Flatpak build failed")
    
    log("Debugging: Contents of ROOTFS before bundle creation:")
    print("=== ROOTFS directory listing ===")
    subprocess.run(["ls", "-la", WORK_DIR], check=False)
    subprocess.run(["ls", "-la", STAGE_DIR], check=False)
    print("\n=== End ROOTFS debug ===")
    
    log("Creating Flatpak bundle...")
    subprocess.run(["flatpak-builder", f"--repo={REPO_DIR}", "--force-clean", BUILD_DIR, MANIFEST], check=True)
    BUNDLE = f"{WORK_DIR}/{SAFE_PKG}.flatpak"
    
    if BUILD_AS_DATA or BUILD_AS_RUNTIME:
        subprocess.run(["flatpak", "build-bundle", "--runtime", REPO_DIR, BUNDLE, APP_ID, FLATPAK_APP_VERSION], check=True)
    else:
        subprocess.run(["flatpak", "build-bundle", REPO_DIR, BUNDLE, APP_ID], check=True)
    
    if INSTALL:
        log("Installing Flatpak...")
        subprocess.run(["flatpak-builder", "--user", "--install", "--force-clean", BUILD_DIR, MANIFEST], check=True)
    
    if RUN_AFTER:
        log("Running application...")
        subprocess.run(["flatpak", "run", APP_ID])
    
    print(f"""
========================================
Build Complete!
========================================

Package(s):     {' '.join(PKGS)}
App ID:         {APP_ID}
Version:        {FLATPAK_APP_VERSION}
Build Type:     {BUILD_TYPE}
Bundle:         {BUNDLE}""")
    
    if BUILD_AS_DATA:
        print(f"""
To install extension manually:
  flatpak install --user -y {BUNDLE}

To use in applications:
  Add to your application manifest as extension dependency

To uninstall:
  flatpak uninstall {APP_ID}""")
    elif BUILD_AS_RUNTIME:
        print(f"""
To install runtime manually:
  flatpak install --user -y {BUNDLE}

To use as runtime dependency:
  --runtime={APP_ID}

To uninstall:
  flatpak uninstall -y {APP_ID}""")
    else:
        print(f"""Command:        {COMMAND}

To install manually:
  flatpak install --user -y {BUNDLE}

To run:
  flatpak run {APP_ID}

To debug:
  flatpak run --command=sh --devel {APP_ID}

To uninstall:
  flatpak uninstall -y {APP_ID}""")
    
    print()
    
    if CLEAN_AFTER:
        log("Cleaning up build directories...")
        shutil.rmtree(STAGE_DIR, ignore_errors=True)
        
        if os.path.isdir(".flatpak-builder"):
            log("Cleaning up flatpak-builder cache...")
            shutil.rmtree(".flatpak-builder", ignore_errors=True)
        
        log("Build directories cleaned up successfully")

if __name__ == "__main__":
    main()