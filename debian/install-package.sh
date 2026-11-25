#!/usr/bin/env bash
set -euo pipefail
dest=$1
app=org.pdenams.Mirivue.Qt
lib="$dest/usr/lib/mirivue-kde"
doc="$dest/usr/share/doc/mirivue-kde"
install -d "$lib/tools" "$dest/usr/bin" "$doc/dolphin-engine" "$doc/notices-kde"
cp -a mirivue "$lib/"
find "$lib/mirivue" -type d -name __pycache__ -prune -exec rm -r -- {} +
install -m755 Lancer.sh "$lib/Lancer.sh"
ln -s ../lib/mirivue-kde/Lancer.sh "$dest/usr/bin/mirivue-kde"
multiarch=$(dpkg-architecture -qDEB_HOST_MULTIARCH)
sed -i "s|/usr/lib/qt6/plugins/|/usr/lib/$multiarch/qt6/plugins/|" "$lib/Lancer.sh"
revision=$(dpkg-parsechangelog -S Version)
sed -i "s/^BUILD_REVISION = .*/BUILD_REVISION = '$revision (deb)'/" "$lib/mirivue/__init__.py"
helpers=(
  mirivue-job-progress mirivue-kio-list mirivue-kio-open mirivue-kio-applications
  mirivue-kio-empty-trash mirivue-kio-places mirivue-kio-preview mirivue-kio-service
  mirivue-kio-transfer libmirivue-kio-places-widget.so libmirivue-item-presentation.so
  libmirivue-dolphin-view.so
)
for helper in "${helpers[@]}"; do
  install -m755 "debian/build/$helper" "$lib/tools/$helper"
done
install -Dm644 mirivue/icons/mirivue-256.png "$dest/usr/share/icons/hicolor/256x256/apps/$app.png"
install -Dm644 mirivue/icons/mirivue.svg "$dest/usr/share/icons/hicolor/scalable/apps/$app.svg"
install -Dm644 "packaging/$app.metainfo.xml" "$dest/usr/share/metainfo/$app.metainfo.xml"
install -Dm644 debian/mirivue-kde.desktop "$dest/usr/share/applications/$app.desktop"
desktop-file-validate "$dest/usr/share/applications/$app.desktop"
cp -a LICENSE LICENSES LICENCES-TIERS.md packaging/preuves-kde "$doc/"
cp -a native/dolphin-engine/LICENSES native/dolphin-engine/UPSTREAM.json native/dolphin-engine/README.md "$doc/dolphin-engine/"
cp native/*UPSTREAM.json "$doc/"
cp native/dolphin-engine/settings/*.license mirivue/servicemenu.knsrc.license "$doc/notices-kde/"
install -m644 packaging/fedora/LICENSE-KIT.txt MENTIONS-RC195-r3.md VERIFICATION-KDE-r4.md "$doc/"
install -m644 mirivue/icons/NOTICE.md "$doc/NOTICE-ICONES.md"
bash packaging/install_docs.sh "$doc"
