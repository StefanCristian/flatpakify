#!/usr/bin/env python3

import sys
import portage
from portage.dep import Atom
from portage.exception import InvalidAtom, InvalidDependString

def get_package_dependencies_with_versions(pkg_atom_str):
    """
    Get first-level runtime dependencies with their specific versions.
    Returns a list of =category/package-version strings ready for emerge.
    """
    try:
        portdb = portage.db[portage.root]["porttree"].dbapi
        
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
            """Recursively extract atoms from dependency list"""
            for item in dep_list:
                if isinstance(item, Atom):
                    dependency_atoms.append(item)
                elif isinstance(item, list):
                    extract_atoms(item)
        
        extract_atoms(deps)
        
        resolved_packages = []
        seen = set()
        
        for dep_atom in dependency_atoms:
            if str(dep_atom) in seen:
                continue
            seen.add(str(dep_atom))
            
            best_dep_match = portdb.xmatch("bestmatch-visible", dep_atom)
            if best_dep_match:
                resolved_packages.append(f"={best_dep_match}")
            else:
                matches = portdb.xmatch("match-all", dep_atom)
                if matches:
                    resolved_packages.append(f"={matches[-1]}")
        
        return resolved_packages
        
    except Exception as e:
        raise RuntimeError(f"Error processing {pkg_atom_str}: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: ./first-level-runtime.py <category/package> or <package>", file=sys.stderr)
        print("Examples:", file=sys.stderr)
        print("  ./first-level-runtime.py sys-apps/portage", file=sys.stderr)
        print("  ./first-level-runtime.py firefox", file=sys.stderr)
        sys.exit(1)
    
    pkg_atom = sys.argv[1]
    
    try:
        resolved_deps = get_package_dependencies_with_versions(pkg_atom)
        
        if not resolved_deps:
            sys.exit(0)
        
        for dep in resolved_deps:
            print(dep)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
