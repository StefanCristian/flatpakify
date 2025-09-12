#!/usr/bin/env python3
# Remove .gpkg.tar archives for the given package from ./binpkgs directory.

import sys
import os
import subprocess
from pathlib import Path

def remove_binary_packages(pkg_atom_str):
    if "/" not in pkg_atom_str:
        print(f"Error: Package must be in category/package format, got: {pkg_atom_str}", file=sys.stderr)
        sys.exit(1)
    
    category, package = pkg_atom_str.split("/", 1)
    pkgdir = os.environ.get("PKGDIR", "./binpkgs")
    binpkgs_dir = Path(pkgdir)
    
    if not binpkgs_dir.exists():
        print(f"Error: Binary packages directory not found: {binpkgs_dir}", file=sys.stderr)
        sys.exit(1)
    
    package_dir = binpkgs_dir / category / package
    
    if not package_dir.exists():
        print(f"No binary package directory found for {pkg_atom_str} at {package_dir}")
        return 0
    
    pattern = f"{package}-*.gpkg.tar"
    
    print(f"Searching in {package_dir} for binary packages matching: {pattern}")
    
    removed_files = []
    for file_path in package_dir.glob(pattern):
        try:
            print(f"Removing: {file_path}")
            file_path.unlink()
            removed_files.append(str(file_path))
        except Exception as e:
            print(f"Failed to remove {file_path}: {e}", file=sys.stderr)
    
    if not removed_files:
        print(f"No binary packages found for {pkg_atom_str}")
    else:
        print(f"Removed {len(removed_files)} binary package(s)")
    
    return len(removed_files)

def fix_binhost():
    print("Running emaint binhost --fix...")
    
    env = os.environ.copy()
    env["EPREFIX"] = "/app"
    pkgdir = os.environ.get("PKGDIR", "./binpkgs")
    env["PKGDIR"] = pkgdir
    
    try:
        result = subprocess.run(
            ["emaint", "binhost", "--fix"],
            env=env,
            check=False,
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
            
        if result.returncode == 0:
            print("emaint binhost --fix completed successfully")
        else:
            print(f"emaint binhost --fix failed with exit code {result.returncode}", file=sys.stderr)
            
        return result.returncode
        
    except FileNotFoundError:
        print("Error: emaint command not found", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error running emaint: {e}", file=sys.stderr)
        return 1

def main():
    if len(sys.argv) != 2:
        print("Usage: ./flatpakify-clean-precompiled.py <category/package>", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  ./flatpakify-clean-precompiled.py games-strategy/seven-kingdoms", file=sys.stderr)
        print("  ./flatpakify-clean-precompiled.py sys-apps/portage", file=sys.stderr)
        sys.exit(1)
    
    pkg_atom = sys.argv[1]
    
    try:
        removed_count = remove_binary_packages(pkg_atom)
        
        fix_result = fix_binhost()
        
        sys.exit(fix_result)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
