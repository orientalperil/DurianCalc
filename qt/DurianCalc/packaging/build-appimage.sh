#!/usr/bin/env bash
# Builds dist/DurianCalc-x86_64.AppImage from the current source tree.
#
# Strategy: PyInstaller freezes the app into a self-contained onedir bundle
# (its PySide6 hook already knows how to collect Qt's shared libraries and
# platform plugins), which is then wrapped in a standard AppDir and handed
# to appimagetool. See ../PORTING.md section 6 for why this beats a
# python-appimage base image or linuxdeploy-plugin-qt (aimed at C++ Qt
# builds, and it fights with PyInstaller's own bundling).
#
# IMPORTANT: build this on the OLDEST glibc you intend to support (e.g. an
# Ubuntu 22.04 container). AppImages are forward-compatible, never
# backward — a binary built on a rolling-release host will only run on
# rolling-release hosts. Do not run this script as your one-and-only build
# on a bleeding-edge dev machine and call it a release.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"
APP_NAME="DurianCalc"
BIN_NAME="duriancalc"
DIST_DIR="$ROOT/dist"
BUILD_DIR="$ROOT/build"
APPDIR="$BUILD_DIR/AppDir"
APPIMAGETOOL="$BUILD_DIR/appimagetool-x86_64.AppImage"

echo "==> Installing dependencies (including the PyInstaller dev group)"
poetry install

echo "==> Freezing with PyInstaller"
rm -rf "$BUILD_DIR/pyinstaller" "$DIST_DIR/$BIN_NAME"
poetry run pyinstaller \
    --name "$BIN_NAME" \
    --windowed \
    --noconfirm \
    --clean \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR/pyinstaller" \
    --specpath "$BUILD_DIR" \
    "duriancalc/__main__.py"

echo "==> Assembling AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp -r "$DIST_DIR/$BIN_NAME/." "$APPDIR/usr/bin/"
cp "packaging/$BIN_NAME.desktop" "$APPDIR/$BIN_NAME.desktop"
cp "packaging/$BIN_NAME.png" "$APPDIR/$BIN_NAME.png"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
# The AppImage runtime already exports APPDIR (and APPIMAGE, the path of
# the .AppImage file itself), but only when the app is launched through
# that runtime -- running AppRun directly out of an extracted AppDir, as
# `--appimage-extract` users and this script's own smoke test do, leaves
# it unset. Exporting it here means duriancalc/desktop_integration.py
# has one dependable way to find the bundled icon either way.
export APPDIR="$HERE"
exec "$HERE/usr/bin/duriancalc" "$@"
EOF
chmod +x "$APPDIR/AppRun"

echo "==> Fetching appimagetool"
if [ ! -x "$APPIMAGETOOL" ]; then
    mkdir -p "$BUILD_DIR"
    curl -fsSL -o "$APPIMAGETOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x "$APPIMAGETOOL"
fi

echo "==> Building AppImage"
# --appimage-extract-and-run sidesteps requiring FUSE2 on the build host
# (common in containers / CI images that don't ship it).
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run \
    "$APPDIR" "$DIST_DIR/$APP_NAME-x86_64.AppImage"

echo "==> Done: $DIST_DIR/$APP_NAME-x86_64.AppImage"
echo "Verify it on a clean container of your oldest supported distro, under"
echo "both X11 and Wayland, before calling this a release build."
