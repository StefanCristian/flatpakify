project(
    'flatpakify',
    version : '1.0.5',
    license : 'GPL-2.0-or-later',
    meson_version : '>=0.58.0'
)

pv_result = run_command('sh', '-c', 'echo ${PV}', check: false)
if pv_result.returncode() == 0 and pv_result.stdout().strip() != ''
    project_version = pv_result.stdout().strip()
else
    project_version = meson.project_version()
endif

py_mod = import('python')
fs = import('fs')
py = py_mod.find_installation()

epython_result = run_command('sh', '-c', 'echo ${EPYTHON}', check: false)
if epython_result.returncode() == 0 and epython_result.stdout().strip() != ''
    epython = epython_result.stdout().strip()
    eprefix_result = run_command('sh', '-c', 'echo ${EPREFIX}', check: false)
    if eprefix_result.returncode() == 0 and eprefix_result.stdout().strip() != ''
        eprefix = eprefix_result.stdout().strip()
    else
        eprefix = ''
    endif
    python_shebang_fix_available = true
else
    python_shebang_fix_available = false
endif

flatpakify_script = configure_file(
    input : 'flatpakify.py',
    output : 'flatpakify',
    copy : true
)

install_data(
    flatpakify_script,
    install_dir : get_option('bindir'),
    install_mode : 'rwxr-xr-x'
)

additional_scripts = [
    'flatpakify-check-rdeps.py',
    'flatpakify-clean-precompiled.py'
]

foreach script : additional_scripts
    if fs.exists(script)
        script_configured = configure_file(
            input : script,
            output : fs.stem(script),
            copy : true
        )
        install_data(
            script_configured,
            install_dir : get_option('bindir'),
            install_mode : 'rwxr-xr-x'
        )
    endif
endforeach

if fs.exists('README.md')
    install_data(
        'README.md',
        install_dir : get_option('datadir') / 'doc' / ('flatpakify-' + project_version)
    )
endif

if fs.exists('INSTALL.md')
    install_data(
        'INSTALL.md',
        install_dir : get_option('datadir') / 'doc' / ('flatpakify-' + project_version)
    )
endif

if python_shebang_fix_available
    shebang_fix_script = '''
    EPYTHON="''' + epython + '''"
    EPREFIX="''' + eprefix + '''"
    BINDIR="$MESON_INSTALL_DESTDIR_PREFIX/''' + get_option('bindir') + '''"
    
    for script in flatpakify flatpakify-check-rdeps flatpakify-clean-precompiled; do
        if [ -f "$BINDIR/$script" ]; then
            shebang=$(head -n1 "$BINDIR/$script")
            case "$shebang" in
                "#!"*python*|"#!"*env*python*)
                    sed -i "1s|^#!.*|#!${EPREFIX}/usr/bin/${EPYTHON}|" "$BINDIR/$script"
                    ;;
                *)
                    echo "Skipping $script - not a Python script"
                    ;;
            esac
        fi
    done
    '''
    
    meson.add_install_script('sh', '-c', shebang_fix_script)
endif
