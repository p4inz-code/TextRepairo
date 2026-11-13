#!/usr/bin/env bash
# Package dist/TextRepairo (PyInstaller output) as .tar.gz, .deb and .AppImage.
# Usage: scripts/package_linux.sh <version>
set -euo pipefail

VERSION="${1:?version required}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
OUT="$DIST/release"
mkdir -p "$OUT"

# --- tar.gz
tar -C "$DIST" -czf "$OUT/TextRepairo-$VERSION-linux-x64.tar.gz" TextRepairo

# --- .deb
DEB="$ROOT/build/deb"
rm -rf "$DEB"
mkdir -p "$DEB/DEBIAN" "$DEB/opt/textrepairo" "$DEB/usr/bin" "$DEB/usr/share/applications" \
         "$DEB/usr/share/icons/hicolor/512x512/apps" "$DEB/usr/share/doc/textrepairo"
cp -r "$DIST/TextRepairo/." "$DEB/opt/textrepairo/"
ln -s /opt/textrepairo/TextRepairo "$DEB/usr/bin/textrepairo-gui"
ln -s /opt/textrepairo/textrepairo-cli "$DEB/usr/bin/textrepairo"
cp "$ROOT/packaging/icon.png" "$DEB/usr/share/icons/hicolor/512x512/apps/textrepairo.png"
cp "$ROOT/LICENSE" "$DEB/usr/share/doc/textrepairo/copyright"
cat > "$DEB/usr/share/applications/textrepairo.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=TextRepairo
Comment=Fix messy text into proper English, offline
Exec=/opt/textrepairo/TextRepairo
Icon=textrepairo
Terminal=false
Categories=Office;Utility;TextTools;
EOF
cat > "$DEB/DEBIAN/control" <<EOF
Package: textrepairo
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Maintainer: TextRepairo contributors <noreply@users.noreply.github.com>
Homepage: https://github.com/p4inz-code/TextRepairo
Description: Offline text repair with a local AI model
 Turns messy text in any language into proper English (fix, formal,
 friendly, prompt style). Runs entirely on this computer.
EOF
dpkg-deb --build --root-owner-group "$DEB" "$OUT/TextRepairo-$VERSION-linux-amd64.deb"

# --- AppImage (best effort)
APPDIR="$ROOT/build/TextRepairo.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications"
cp -r "$DIST/TextRepairo/." "$APPDIR/usr/bin/"
cp "$ROOT/packaging/icon.png" "$APPDIR/textrepairo.png"
cp "$DEB/usr/share/applications/textrepairo.desktop" "$APPDIR/textrepairo.desktop"
sed -i 's|^Exec=.*|Exec=TextRepairo|' "$APPDIR/textrepairo.desktop"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/TextRepairo" "$@"
EOF
chmod +x "$APPDIR/AppRun"
TOOL="$ROOT/build/appimagetool"
if curl -fsSL -o "$TOOL" "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"; then
  chmod +x "$TOOL"
  ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT/TextRepairo-$VERSION-linux-x64.AppImage" \
    || echo "AppImage build failed; skipping."
else
  echo "Could not download appimagetool; skipping AppImage."
fi
ls -la "$OUT"
