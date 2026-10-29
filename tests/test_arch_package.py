from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestArchPackage(unittest.TestCase):
    def test_local_package_declares_runtime_and_desktop_identity(self):
        template = (ROOT / 'packaging' / 'PKGBUILD.template').read_text(encoding='utf-8')
        builder = (ROOT / 'Construire-paquet-CachyOS.sh').read_text(encoding='utf-8')
        for dependency in ('pyside6', 'qt6-base', 'qt6-multimedia', 'qt6-webengine', 'kio', 'ffmpeg', 'mediainfo'):
            self.assertIn("'" + dependency, template)
        self.assertIn('org.pdenams.Mirivue.Qt.desktop', template)
        self.assertIn('GenericName=Gestionnaire de fichiers', template)
        self.assertIn('Exec=/usr/bin/mirivue-kde %U', template)
        self.assertIn('Categories=Qt;KDE;System;FileTools;FileManager;', template)
        self.assertIn('MimeType=inode/directory;', template)
        self.assertIn('makepkg --clean --force', builder)
        self.assertIn("--exclude='Mirivue-1.0.0-RC194-KDE/tests'", builder)
        self.assertIn("'python<3.15'", template)
        self.assertIn("'pyside6<7'", template)
        self.assertNotIn("'pyside6<6.12'", template)
        for dependency in ('cmake', 'ninja', 'extra-cmake-modules'):
            self.assertIn("'" + dependency + "'", template)
        self.assertIn('cmake -S "$root/native"', template)
        for helper in ('list', 'places', 'preview', 'service', 'transfer'):
            self.assertIn('mirivue-kio-' + helper, template)
        self.assertIn('install -m0755 "$srcdir/build/$helper"', template)
        self.assertNotIn('"$srcdir/build"/mirivue-kio-*', template)
        self.assertNotIn('cp -a "$root/mirivue" "$root/tools"', template)
        self.assertIn('pkgname=mirivue-kde\n', template)
        self.assertIn("-name 'mirivue-kde-*.pkg.tar.*'", builder)
        self.assertIn('for command in cmake ninja', builder)


if __name__ == '__main__':
    unittest.main()
