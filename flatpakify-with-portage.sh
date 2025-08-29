#!/usr/bin/env bash
set -euo pipefail

# flatpakify-with-portage.sh
# Build a Gentoo Portage package into a staging ROOT and repackage it as a Flatpak.
# Requires: sudo, emerge, tar, flatpak, flatpak-builder
# Optional: zstd (preferred), xz (fallback), patchelf (if you later tweak RPATHs)
#
# Example (CLI: jq):
#   ./flatpakify-with-portage.sh \
#     --pkg app-misc/jq \
#     --app-id io.github.jqlang.jq \
#     --command jq \
#     --realbin /usr/bin/jq \
#     --name "jq" \
#     --comment "Command-line JSON processor" \
#     --install
#
# Example (GUI):
#   ./flatpakify-with-portage.sh \
#     --pkg app-editors/helix \
#     --app-id com.example.Helix \
#     --command hx \
#     --realbin /usr/bin/hx \
#     --name "Helix" \
#     --comment "Post-modern modal text editor" \
#     --gui true \
#     --icon ./icon-512.png \
#     --fs xdg-documents \
#     --network \
#     --install

### Defaults
PKG=""
APP_ID=""
COMMAND=""
REALBIN=""
RUNTIME="org.freedesktop.Platform"
SDK="org.freedesktop.Sdk"
RUNTIME_VERSION="24.08"
NAME=""
COMMENT=""
GUI="false"
ICON_PATH=""
ROOT_DEPS="nodeps"
BUNDLE_LIBS="false"
INSTALL="false"
RUN_AFTER="false"
NETWORK="false"
AUDIO="false"
FS_ARGS=()

print_usage() {
  cat <<EOF
Usage:
  $0 --pkg category/name --app-id com.example.App --command cmd --realbin /usr/bin/cmd [options]

Required:
  --pkg category/name     Gentoo package to emerge (e.g. app-misc/jq)
  --app-id ID             Flatpak app-id (e.g. io.github.jqlang.jq)
  --command cmd           Entry command inside Flatpak (wrapper name)
  --realbin /path         Real binary installed by the ebuild (e.g. /usr/bin/jq)

Recommended:
  --name "App Name"       Human-readable name
  --comment "Summary"     One-line summary
  --gui true|false        GUI app? (auto-detected if icon found in /usr/share/pixmaps/)
  --icon ./icon.png       Override icon (otherwise checks PACKAGE.png then BINARY.png)

Runtimes:
  --runtime ID            default: org.freedesktop.Platform
  --sdk ID                default: org.freedesktop.Sdk
  --runtime-version VER   default: 24.08

Behavior:
  --root-deps rdeps|nodeps  emerge runtime deps into staging (default: nodeps)
  --bundle-libs           automatically detect and bundle required libraries
  --fs ARG                add a finish-arg filesystem permission (repeatable), e.g.:
                          --fs host:ro     --fs xdg-documents
  --network               add --share=network permission
  --audio                 add audio permissions: simple PulseAudio socket + device access (auto-enabled for GUI apps)
  --install               Install to current user after build
  --run                   Run the app after (implies --install)
  -h|--help               This help
EOF
}

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not found"; exit 1; }; }

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --pkg) PKG="$2"; shift 2 ;;
    --app-id) APP_ID="$2"; shift 2 ;;
    --command) COMMAND="$2"; shift 2 ;;
    --realbin) REALBIN="$2"; shift 2 ;;
    --runtime) RUNTIME="$2"; shift 2 ;;
    --sdk) SDK="$2"; shift 2 ;;
    --runtime-version) RUNTIME_VERSION="$2"; shift 2 ;;
    --name) NAME="$2"; shift 2 ;;
    --comment) COMMENT="$2"; shift 2 ;;
    --gui) GUI="$2"; shift 2 ;;
    --icon) ICON_PATH="$2"; shift 2 ;;
    --root-deps) ROOT_DEPS="$2"; shift 2 ;;
    --bundle-libs) BUNDLE_LIBS="true"; shift ;;
    --fs) FS_ARGS+=("$2"); shift 2 ;;
    --network) NETWORK="true"; shift ;;
    --audio) AUDIO="true"; shift ;;
    --install) INSTALL="true"; shift ;;
    --run) RUN_AFTER="true"; INSTALL="true"; shift ;;
    -h|--help) print_usage; exit 0 ;;
    *) echo "Unknown arg: $1"; print_usage; exit 1 ;;
  esac
done

[[ -n "$PKG" && -n "$APP_ID" && -n "$COMMAND" && -n "$REALBIN" ]] || { print_usage; exit 1; }

need sudo; need emerge; need tar; need flatpak; need flatpak-builder
COMP=""; if command -v zstd >/dev/null 2>&1; then COMP="zstd -19 -T0"; elif command -v xz >/dev/null 2>&1; then COMP="xz -9e"; fi

SAFE_ID="${APP_ID//./-}"
WORK_DIR="$(pwd)"
STAGE_DIR="${WORK_DIR}/flat-stage-${SAFE_ID}"
ROOTFS="${STAGE_DIR}/rootfs"
FLATPAK_DIR="${WORK_DIR}/flatpak-${SAFE_ID}"
BUILD_DIR="${WORK_DIR}/builddir-${SAFE_ID}"
REPO_DIR="${WORK_DIR}/repo-${SAFE_ID}"
MANIFEST="${FLATPAK_DIR}/${APP_ID}.yml"
DESKTOP="${FLATPAK_DIR}/${APP_ID}.desktop"
METAINFO="${FLATPAK_DIR}/${APP_ID}.metainfo.xml"
DESKTOP_BASE="$(basename "${DESKTOP}")"
METAINFO_BASE="$(basename "${METAINFO}")"
ICON_DST_DIR="${FLATPAK_DIR}/icons/hicolor/512x512/apps"
ICON_DST="${ICON_DST_DIR}/${APP_ID}.png"
TARBALL_NAME="${SAFE_ID}-rootfs.tar.${COMP:+zst}"
TARBALL="${STAGE_DIR}/${TARBALL_NAME}"

mkdir -p "${ROOTFS}" "${FLATPAK_DIR}" "${BUILD_DIR}" "${REPO_DIR}"

if [[ "${ROOT_DEPS}" == "rdeps" ]]; then
  sudo emerge -v1 \
    --root="${ROOTFS}" \
    --root-deps="${ROOT_DEPS}" \
    --ask=n \
    ${PKG}
else
  sudo emerge -v1 \
    --root="${ROOTFS}" \
    --nodeps \
    --ask=n \
    ${PKG}
fi

sudo rm -rf "${ROOTFS}/etc" "${ROOTFS}/var/run" "${ROOTFS}/var/tmp" 2>/dev/null || true

if [[ "${BUNDLE_LIBS}" == "true" ]]; then
  
  STAGED_BINARY=""
  if [[ -f "${ROOTFS}${REALBIN}" ]]; then
    STAGED_BINARY="${ROOTFS}${REALBIN}"
  else
    STAGED_BINARY=$(find "${ROOTFS}" -name "$(basename "${REALBIN}")" -type f -executable 2>/dev/null | head -n1)
  fi
  
  if [[ -n "${STAGED_BINARY}" && -f "${STAGED_BINARY}" ]]; then
    
    LIBS_TO_BUNDLE=()
    while IFS= read -r lib_line; do
      if [[ "$lib_line" =~ "=>"[[:space:]]*(/[^[:space:]]+) ]]; then
        lib_path="${BASH_REMATCH[1]}"
        lib_name=$(basename "$lib_path")
        
        if [[ ! "$lib_path" =~ ^/(lib|lib64|usr/lib|usr/lib64)/(ld-|libc\.|libm\.|libpthread\.|libdl\.|librt\.|libresolv\.|libnss_|libutil\.|libcrypt\.|libgcc_s\.|libstdc\+\+\.) ]] && \
           [[ ! "$lib_path" =~ ^/usr/lib.*/gcc/ ]] && \
           [[ ! "$lib_path" =~ ^/(lib|lib64|usr/lib|usr/lib64)/(libX|libwayland|libxcb) ]] && \
           [[ ! "$lib_path" =~ ^/(lib|lib64|usr/lib|usr/lib64)/(libasound|libpulse|libpipewire|libopenal) ]] && \
           [[ "$lib_path" != *"linux-vdso"* ]]; then
          LIBS_TO_BUNDLE+=("$lib_path")
        else
          echo "  -> Skipping system lib: $lib_name"
        fi
      fi
    done < <(ldd "${STAGED_BINARY}" 2>/dev/null || true)
    
    if [[ ${#LIBS_TO_BUNDLE[@]} -gt 0 ]]; then
      sudo mkdir -p "${ROOTFS}/usr/lib64"
      
      for lib_path in "${LIBS_TO_BUNDLE[@]}"; do
        if [[ -f "$lib_path" ]]; then
          sudo cp -L "$lib_path" "${ROOTFS}/usr/lib64/"
        fi
      done
    else
      echo "==> No additional libraries to bundle"
    fi
  else
    echo "WARNING: Could not find staged binary for dependency analysis"
    echo "  Searched for: ${REALBIN}"
  fi
fi

pushd "${ROOTFS}" >/dev/null
if [[ -n "$COMP" && "$COMP" == zstd* ]]; then
  sudo tar -I "$COMP" -cf "${TARBALL}" .
elif [[ -n "$COMP" ]]; then
  sudo tar -I "$COMP" -cf "${TARBALL/.zst/.xz}" .
  TARBALL="${TARBALL/.zst/.xz}"
  TARBALL_NAME="${TARBALL_NAME/.zst/.xz}"
else
  sudo tar -cf "${TARBALL/.zst/.tar}" .
  TARBALL="${TARBALL/.zst/.tar}"
  TARBALL_NAME="${TARBALL_NAME/.zst/.tar}"
fi
sudo chown "$(id -u)":"$(id -g)" "${TARBALL}"
popd >/dev/null

PACKAGE_NAME="${PKG##*/}"
BINARY_NAME="$(basename "${REALBIN}")"
AUTO_ICON_PACKAGE="${ROOTFS}/usr/share/pixmaps/${PACKAGE_NAME}.png"
AUTO_ICON_BINARY="${ROOTFS}/usr/share/pixmaps/${BINARY_NAME}.png"

AUTO_ICON_PATH=""
if [[ -f "${AUTO_ICON_PACKAGE}" ]]; then
  AUTO_ICON_PATH="${AUTO_ICON_PACKAGE}"
elif [[ -f "${AUTO_ICON_BINARY}" ]]; then
  AUTO_ICON_PATH="${AUTO_ICON_BINARY}"
fi

if [[ "${GUI}" == "true" ]] || [[ -n "${AUTO_ICON_PATH}" ]]; then
  GUI="true"
  [[ -n "${NAME}" ]] || NAME="${APP_ID##*.}"
  [[ -n "${COMMENT}" ]] || COMMENT="Packaged from Gentoo via Flatpak"
  
  mkdir -p "${ICON_DST_DIR}"
  
  if [[ -n "${ICON_PATH}" && -f "${ICON_PATH}" ]]; then
    cp -f "${ICON_PATH}" "${ICON_DST}"
  elif [[ -n "${AUTO_ICON_PATH}" ]]; then
    cp -f "${AUTO_ICON_PATH}" "${ICON_DST}"
  else
    echo "ERROR: GUI app requested but no icon found"
    echo "Checked: ${AUTO_ICON_PACKAGE}"
    echo "Checked: ${AUTO_ICON_BINARY}"
    echo "Please provide --icon path/to/icon.png or place icon at standard location"
    exit 1
  fi
  
  cat > "${DESKTOP}" <<EOF
[Desktop Entry]
Name=${NAME}
Comment=${COMMENT}
Exec=${COMMAND}
Icon=${APP_ID}
Terminal=false
Type=Application
Categories=Utility;
EOF

  TODAY="$(date +%Y-%m-%d)"
  cat > "${METAINFO}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>${APP_ID}</id>
  <name>${NAME}</name>
  <summary>${COMMENT}</summary>
  <description>
    <p>${COMMENT}</p>
  </description>
  <launchable type="desktop-id">${APP_ID}.desktop</launchable>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>LicenseRef-proprietary</project_license>
  <content_rating type="oars-1.1"/>
  <releases>
    <release version="1.0.0" date="${TODAY}"/>
  </releases>
</component>
EOF
fi

FIN_LINES=()
if [[ "${GUI}" == "true" ]]; then
  FIN_LINES+=("--socket=wayland" "--socket=fallback-x11" "--device=dri")
  FIN_LINES+=("--socket=pulseaudio" "--device=all")
fi
if [[ "${NETWORK}" == "true" ]]; then
  FIN_LINES+=("--share=network")
fi
if [[ "${AUDIO}" == "true" ]] || [[ "${GUI}" == "true" ]]; then
  if [[ ! " ${FIN_LINES[*]} " =~ " --socket=pulseaudio " ]]; then
    FIN_LINES+=("--socket=pulseaudio" "--device=all")
  fi
fi
for fs in "${FS_ARGS[@]}"; do 
  if [[ -n "$fs" ]]; then
    FIN_LINES+=("--filesystem=${fs}")
  fi
done

FINISH_ARGS_YML=""
if [[ ${#FIN_LINES[@]} -gt 0 ]]; then
  FINISH_ARGS_YML=$'\n'"finish-args:"
  for l in "${FIN_LINES[@]}"; do
    FINISH_ARGS_YML+=$'\n'"  - ${l}"
  done
fi

cat > "${MANIFEST}" <<EOF
app-id: ${APP_ID}
runtime: ${RUNTIME}
runtime-version: "${RUNTIME_VERSION}"
sdk: ${SDK}
command: ${COMMAND}${FINISH_ARGS_YML}
modules:
  - name: ${SAFE_ID}-repackage
    buildsystem: simple
    sources:
      - type: file
        path: $(basename "${TARBALL_NAME}")
    build-commands:
      # 1) Unpack staged payload
      - mkdir _payload
      - tar -C _payload --no-same-owner --no-same-permissions -xaf $(basename "${TARBALL_NAME}")
      # 2) Relocate /usr -> /app
      - install -d /app
      - if [ -d _payload/usr ]; then cp -a _payload/usr/. /app/; fi
      # 3) Drop /etc (avoid overriding host configs)
      - rm -rf /app/etc || true
      # 4) Create wrapper script
      - install -d /app/bin
      - |
        cat > /app/bin/${COMMAND} << 'WRAP'
        #!/usr/bin/env sh
        export LD_LIBRARY_PATH="/app/lib:/app/lib64:\${LD_LIBRARY_PATH}"
        export XDG_DATA_DIRS="/app/share:\${XDG_DATA_DIRS}"
        
        # Audio: Force PulseAudio directly, bypass ALSA complications
        #unset ALSA_CONFIG_PATH
        #unset ALSA_CONFIG_DIR
        export PULSE_RUNTIME_PATH="/run/flatpak/pulse"

        
        # Uncomment if your app needs them:
        # export GSETTINGS_SCHEMA_DIR="/app/share/glib-2.0/schemas"
        # export QT_PLUGIN_PATH="/app/lib/qt/plugins:/app/lib64/qt/plugins:\${QT_PLUGIN_PATH}"
        exec /app/bin/${COMMAND}-real "\$@"
        WRAP
      - chmod +x /app/bin/${COMMAND}
      # 5) Wire wrapper to real binary from Gentoo payload
      - if [ -f "/app${REALBIN}" ]; then mv "/app${REALBIN}" "/app/bin/${COMMAND}-real"; \
        elif [ -f "_payload${REALBIN}" ]; then mv "_payload${REALBIN}" "/app/bin/${COMMAND}-real"; \
        elif [ -f "/app/bin/${COMMAND}" ]; then mv "/app/bin/${COMMAND}" "/app/bin/${COMMAND}-real"; \
        else CAND="\$(find /app/bin -maxdepth 1 -type f -perm -u+x | head -n1 || true)"; \
             if [ -n "\$CAND" ]; then mv "\$CAND" "/app/bin/${COMMAND}-real"; else echo "No real binary found; check --realbin"; exit 1; fi; fi
EOF

if [[ "${GUI}" == "true" ]]; then
cat >> "${MANIFEST}" <<EOF
  - name: desktop-files
    buildsystem: simple
    sources:
      - type: dir
        path: .
        dest: _desk
    build-commands:
      - install -Dm644 _desk/${DESKTOP_BASE} /app/share/applications/${DESKTOP_BASE}
      - install -Dm644 _desk/${METAINFO_BASE} /app/share/metainfo/${METAINFO_BASE}
      - if [ -d _desk/icons ]; then mkdir -p /app/share/icons && cp -a _desk/icons/. /app/share/icons/; fi
EOF
fi

cp -f "${TARBALL}" "${FLATPAK_DIR}/"

flatpak-builder --force-clean "${BUILD_DIR}" "${MANIFEST}"

flatpak-builder --repo="${REPO_DIR}" --force-clean "${BUILD_DIR}" "${MANIFEST}"
BUNDLE="${SAFE_ID}.flatpak"
flatpak build-bundle "${REPO_DIR}" "${BUNDLE}" "${APP_ID}"

if [[ "${INSTALL}" == "true" ]]; then
  flatpak-builder --user --install --force-clean "${BUILD_DIR}" "${MANIFEST}"
fi

if [[ "${RUN_AFTER}" == "true" ]]; then
  flatpak run "${APP_ID}"
fi

cat <<EOF

Artifacts:
- Manifest:        ${MANIFEST}
- Repo (local):    ${REPO_DIR}
- Bundle:          ${BUNDLE}

Tips if it fails to run:
- Your binary may depend on libs not in the runtime. Bundle them by adding
  another module that copies required .so files into /app/lib or /app/lib64.
- Check deps on Gentoo:
    ldd ${REALBIN}    # or: lddtree (from app-misc/pax-utils)
- Debug inside sandbox:
    flatpak run --command=sh --devel ${APP_ID}

EOF
