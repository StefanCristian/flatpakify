project(
    'flatpakify',
    version : '1.0.1',
    license : 'GPL-2.0-or-later',
    meson_version : '>=0.58.0'
)

py_mod = import('python')
fs = import('fs')
py = py_mod.find_installation()

flatpakify_script = configure_file(
    input : 'flatpakify.py',
    output : 'flatpakify',
    copy : true
)

flatpakify_py_script = configure_file(
    input : 'flatpakify.py',
    output : 'flatpakify.py',
    copy : true
)

install_data(
    flatpakify_script,
    install_dir : get_option('bindir'),
    install_mode : 'rwxr-xr-x'
)

install_data(
    flatpakify_py_script,
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
        install_dir : get_option('datadir') / 'doc' / ('flatpakify-' + meson.project_version())
    )
endif

if fs.exists('INSTALL.md')
    install_data(
        'INSTALL.md',
        install_dir : get_option('datadir') / 'doc' / ('flatpakify-' + meson.project_version())
    )
endif
