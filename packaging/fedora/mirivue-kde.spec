# SPDX-FileCopyrightText: 2026 Mirivue contributors
# SPDX-License-Identifier: MIT
Name: mirivue-kde
Version: 1.0.0
Release: 0.196.beta1.4%{?dist}
Summary: Gestionnaire de fichiers multimedia pour KDE Plasma
License: GPL-3.0-or-later AND GPL-2.0-or-later AND MIT AND BSD-2-Clause AND CC0-1.0
Source0: Mirivue-1.0.0-beta.1-KDE.tar.gz
Source1: valider-appstream.py
Source2: LICENSE-KIT.txt
ExclusiveArch: x86_64 aarch64
BuildRequires: gcc-c++, cmake, ninja-build, extra-cmake-modules, appstream, desktop-file-utils
BuildRequires: qt6-qtbase-devel
BuildRequires: kf6-kio-devel, kf6-kcolorscheme-devel, kf6-knewstuff-devel
BuildRequires: kf6-kwindowsystem-devel, kf6-kguiaddons-devel
BuildRequires: kf6-kwidgetsaddons-devel, kf6-ktextwidgets-devel, kf6-ki18n-devel
BuildRequires: kf6-kconfig-devel, kf6-kcoreaddons-devel, kf6-kiconthemes-devel
BuildRequires: kf6-kjobwidgets-devel, kf6-kxmlgui-devel, kf6-kconfigwidgets-devel
BuildRequires: kf6-kservice-devel, kf6-kparts-devel, python3-devel
Requires: python3 >= 3.11
Requires: python3 < 3.15
Requires: python3-pyside6 >= 6.8
Requires: python3-pyside6 < 7
Requires: python3-shiboken6, python3-pillow, python3-mutagen
Requires: qt6-qtmultimedia, qt6-qtpdf
Requires: /usr/bin/ffmpeg, /usr/bin/ffprobe
Requires: mediainfo, ark, 7zip, unar, perl-Image-ExifTool
Requires: /usr/bin/mkvpropedit, /usr/bin/mkvextract
Requires: kf6-kio, kdialog, appstream
Recommends: konsole
%global debug_package %{nil}
%global __brp_python_bytecompile %{nil}

%description
Mirivue KDE 1.0.0-beta.1 avec assistants KIO et moteur de vue natif compiles.

%prep
%setup -q -n Mirivue-1.0.0-beta.1-KDE
# Le lanceur doit aussi trouver GStreamer dans le repertoire lib64 de Fedora.
sed -i 's|/usr/lib/qt6/plugins/multimedia/libgstreamermediaplugin.so|%{_libdir}/qt6/plugins/multimedia/libgstreamermediaplugin.so|' Lancer.sh

%build
cmake -S native -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_CXX_FLAGS="%{optflags}"
cmake --build build --parallel %{_smp_build_ncpus}

%install
install -d %{buildroot}%{_libdir}/mirivue-kde/tools %{buildroot}%{_bindir}
cp -a mirivue Lancer.sh %{buildroot}%{_libdir}/mirivue-kde/
chmod 755 %{buildroot}%{_libdir}/mirivue-kde/Lancer.sh
for helper in mirivue-job-progress mirivue-kio-list mirivue-kio-open mirivue-kio-applications mirivue-kio-empty-trash mirivue-kio-places mirivue-kio-preview mirivue-kio-service mirivue-kio-transfer; do
 install -m755 build/$helper %{buildroot}%{_libdir}/mirivue-kde/tools/
done
for lib in libmirivue-kio-places-widget.so libmirivue-item-presentation.so libmirivue-dolphin-view.so; do
 install -m755 build/$lib %{buildroot}%{_libdir}/mirivue-kde/tools/
done
ln -s ../%{_lib}/mirivue-kde/Lancer.sh %{buildroot}%{_bindir}/mirivue-kde
install -Dm644 mirivue/icons/mirivue-256.png %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/org.pdenams.Mirivue.Qt.png
install -Dm644 mirivue/icons/mirivue.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/org.pdenams.Mirivue.Qt.svg
install -d %{buildroot}%{_datadir}/applications
cat > %{buildroot}%{_datadir}/applications/org.pdenams.Mirivue.Qt.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Version=1.0
Name=Mirivue KDE
GenericName=Gestionnaire de fichiers
Comment=Parcourir, organiser et analyser les fichiers
Exec=/usr/bin/mirivue-kde %U
TryExec=/usr/bin/mirivue-kde
Icon=org.pdenams.Mirivue.Qt
Terminal=false
StartupNotify=true
StartupWMClass=org.pdenams.Mirivue.Qt
Categories=Qt;KDE;System;FileTools;FileManager;
MimeType=inode/directory;
DESKTOP
install -d %{buildroot}%{_datadir}/licenses/%{name}/dolphin-engine
cp -a LICENSE LICENSES LICENCES-TIERS.md %{buildroot}%{_datadir}/licenses/%{name}/
cp -a native/dolphin-engine/LICENSES native/dolphin-engine/UPSTREAM.json native/dolphin-engine/README.md %{buildroot}%{_datadir}/licenses/%{name}/dolphin-engine/
cp native/*UPSTREAM.json %{buildroot}%{_datadir}/licenses/%{name}/

install -Dm644 packaging/org.pdenams.Mirivue.Qt.metainfo.xml %{buildroot}%{_datadir}/metainfo/org.pdenams.Mirivue.Qt.metainfo.xml
install -Dm644 packaging/mirivue-local.xml %{buildroot}%{_datadir}/swcatalog/xml/mirivue-local.xml

install -m644 %{SOURCE2} %{buildroot}%{_datadir}/licenses/%{name}/LICENSE-KIT.txt
install -m644 mirivue/icons/NOTICE.md %{buildroot}%{_datadir}/licenses/%{name}/NOTICE-ICONES.md
install -m644 MENTIONS-RC195-r3.md %{buildroot}%{_datadir}/licenses/%{name}/MENTIONS-RC195-r3.md

install -m644 VERIFICATION-KDE-r4.md %{buildroot}%{_datadir}/licenses/%{name}/VERIFICATION-KDE-r4.md
cp -a packaging/preuves-kde %{buildroot}%{_datadir}/licenses/%{name}/
install -d %{buildroot}%{_datadir}/licenses/%{name}/notices-kde
cp native/dolphin-engine/settings/*.license mirivue/servicemenu.knsrc.license %{buildroot}%{_datadir}/licenses/%{name}/notices-kde/

bash packaging/install_docs.sh "%{buildroot}%{_docdir}/%{name}"

%check
python3 "%{SOURCE1}" --self-test
appstreamcli validate --no-net packaging/org.pdenams.Mirivue.Qt.metainfo.xml
appstreamcli validate --no-net packaging/mirivue-local.xml
desktop-file-validate %{buildroot}%{_datadir}/applications/org.pdenams.Mirivue.Qt.desktop
python3 -m compileall -q mirivue
for helper in mirivue-kio-service mirivue-kio-list; do
 test -x build/$helper
 ! ldd build/$helper | grep -q 'not found'
done

%files
%doc %{_docdir}/%{name}/
%{_bindir}/mirivue-kde
%{_libdir}/mirivue-kde/
%{_datadir}/applications/org.pdenams.Mirivue.Qt.desktop
%{_datadir}/icons/hicolor/256x256/apps/org.pdenams.Mirivue.Qt.png
%{_datadir}/icons/hicolor/scalable/apps/org.pdenams.Mirivue.Qt.svg
%license %{_datadir}/licenses/%{name}/

%{_datadir}/metainfo/org.pdenams.Mirivue.Qt.metainfo.xml
%{_datadir}/swcatalog/xml/mirivue-local.xml

%changelog
* Sat Oct 31 2026 Mirivue contributors - 1.0.0-0.196.beta1.3
- Ship and verify updated installation and publication guides.

* Thu Oct 29 2026 Pascal Denamiel - 1.0.0-0.196.beta1.2
- Verify upstream KDE REUSE declarations; preserve licensing evidence.

* Thu Oct 29 2026 Pascal Denamiel - 1.0.0-0.196.beta1.2
- Clarify packaging, icon and metadata licenses; keep unresolved provenance documented.

* Thu Oct 29 2026 Pascal Denamiel - 1.0.0-0.196.beta1.2
- Include validator as Source1; make SRPM self-contained.

* Thu Oct 29 2026 Pascal Denamiel - 1.0.0-0.195.rc195
- Add AppStream metadata and local catalog; avoid blocking GUI smoke test.
