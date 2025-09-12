#!/usr/bin/env python3
# Unknown author and license
# Modified by Stefan Cristian B. <stefan.cristian@rogentos.ro>
# Purpose of the script:
# Get first-level runtime dependencies with their specific versions.
# Returns a list of =category/package-version strings ready for emerge.

import sys
import portage
from portage.dep import Atom
from portage.exception import InvalidAtom, InvalidDependString

def get_package_dependencies_with_versions(pkg_atom_str):
    try:
        portdb = portage.db[portage.root]["porttree"].dbapi
        vardb = portage.db[portage.root]["vartree"].dbapi
        
        try:
            pkg_atom = Atom(pkg_atom_str)
        except InvalidAtom:
            if "/" not in pkg_atom_str:
                matches = portdb.xmatch("match-all", pkg_atom_str)
                if matches:
                    pkg_atom = Atom(matches[-1])
                else:
                    raise ValueError(f"Package not found: {pkg_atom_str}")
            else:
                raise
        
        best_match = portdb.xmatch("bestmatch-visible", pkg_atom)
        if not best_match:
            raise ValueError(f"No visible package found for: {pkg_atom}")
        
        cpv = best_match
        
        rdepend_raw = portdb.aux_get(cpv, ["RDEPEND"])[0]
        
        if not rdepend_raw:
            return []
        
        deps = portage.dep.use_reduce(
            rdepend_raw,
            uselist=portage.settings["USE"].split(),
            masklist=[],
            matchall=True,
            excludeall=[],
            is_src_uri=False,
            token_class=Atom
        )
        
        dependency_atoms = []
        
        def extract_atoms(dep_list):
            for item in dep_list:
                if isinstance(item, Atom):
                    dependency_atoms.append(item)
                elif isinstance(item, list):
                    extract_atoms(item)
        
        extract_atoms(deps)
        
        resolved_packages = []
        orphaned_packages = []
        seen = set()
        
        all_installed = set(vardb.cpv_all())
        
        for dep_atom in dependency_atoms:
            if str(dep_atom) in seen:
                continue
            seen.add(str(dep_atom))
            
            installed_matches = vardb.match(dep_atom)
            
            installed_matches = [cpv for cpv in installed_matches if cpv in all_installed]
            
            if installed_matches:
                best_installed = portage.best(installed_matches)
                
                if portdb.cpv_exists(best_installed):
                    resolved_packages.append(f"={best_installed}")
                else:
                    orphaned_packages.append(best_installed)
        
        return resolved_packages, orphaned_packages
        
    except Exception as e:
        raise RuntimeError(f"Error processing {pkg_atom_str}: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: ./first-level-runtime.py <category/package>", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  ./first-level-runtime.py sys-apps/portage", file=sys.stderr)
        sys.exit(1)
    
    pkg_atom = sys.argv[1]
    
    try:
        resolved_deps, orphaned_deps = get_package_dependencies_with_versions(pkg_atom)
        
        if orphaned_deps:
            print("\nERROR: The following installed dependencies have no available ebuilds:", file=sys.stderr)
            for orphan in orphaned_deps:
                print(f"  {orphan}", file=sys.stderr)
            print("The old package has been installed, but it has not been upgraded. Please upgrade your package, or maintain its ebuild in your overlay.\n", file=sys.stderr)
            sys.exit(1)
        
        if not resolved_deps and not orphaned_deps:
            print("No installed runtime dependencies found.", file=sys.stderr)
            sys.exit(0)
        
        for dep in resolved_deps:
            print(dep)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()