from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestInstallerDependencies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.installer = (ROOT / 'Installer.sh').read_text(encoding='utf-8')
        cls.updater = (ROOT / 'Mettre-a-jour-Mirivue-vers-1.0.0-RC194.sh').read_text(encoding='utf-8')

    def test_read_only_dependency_check_precedes_installation(self):
        check = self.installer.index("if [[ \"${1:-}\" == '--check-dependencies' ]]")
        staging = self.installer.index('staging="$(mktemp -d', check)
        self.assertLess(check, staging)

    def test_system_package_cannot_be_shadowed_by_user_installation(self):
        self.assertIn('pacman -Qq mirivue-kde', self.installer)
        self.assertIn('créerait une seconde copie', self.installer)
        package_guard = self.installer.index('pacman -Qq mirivue-kde')
        staging = self.installer.index('staging="$(mktemp -d', package_guard)
        self.assertLess(package_guard, staging)

    def test_running_application_blocks_update_before_dependencies_and_staging(self):
        read_only = self.installer.index("if [[ \"${1:-}\" == '--check-dependencies' ]]")
        running = self.installer.index('if mirivue_is_running; then', read_only)
        dependencies = self.installer.index('if ! check_dependencies; then', running)
        staging = self.installer.index('staging="$(mktemp -d', dependencies)
        self.assertLess(read_only, running)
        self.assertLess(running, dependencies)
        self.assertLess(dependencies, staging)
        self.assertIn("arguments[index]}\" == '-m'", self.installer)
        self.assertIn("arguments[index + 1]}\" == 'mirivue'", self.installer)
        self.assertIn('La version installée n’a pas été modifiée.', self.installer)

    def test_all_python_runtime_modules_are_checked(self):
        for module in ('QtWidgets', 'QtDBus', 'QtMultimedia', 'QtMultimediaWidgets', 'QtPdf', 'shiboken6', 'PIL', 'mutagen'):
            self.assertIn(module, self.installer)
        self.assertIn('(3, 11) <= sys.version_info[:2] < (3, 15)', self.installer)
        self.assertIn('(6, 8) <= v < (7, 0)', self.installer)

    def test_external_tools_and_kio_libraries_are_checked(self):
        for component in ('ffmpeg', 'ffprobe', 'mediainfo', 'ark', '7z', '7zz', 'unar', 'unrar', 'exiftool', 'mkvpropedit', 'mkvextract'):
            self.assertIn(component, self.installer)
        self.assertIn('cmake -S "$source_dir/native" -B "$native_check_dir"', self.installer)
        self.assertIn('rm -rf -- "$native_check_dir"', self.installer)
        self.assertIn("runtime_helper='/usr/lib/mirivue-kde/tools/mirivue-kio-service'", self.installer)
        self.assertNotIn('"$source_dir/tools/mirivue-kio-service"', self.installer)

    def test_supported_distributions_have_explicit_packages(self):
        for package in ('qt6-multimedia', 'qt6-webengine', 'python-pillow', 'python-mutagen', 'kio',
                        'qt6-qtmultimedia', 'qt6-qtpdf', 'python3-pillow', 'python3-mutagen', 'kf6-kio'):
            self.assertIn(package, self.installer)

    def test_graphical_updater_never_fails_silently(self):
        self.assertIn('Installer.sh est introuvable', self.updater)
        self.assertIn('derniere-mise-a-jour.log', self.updater)
        self.assertIn('La version déjà installée a été conservée', self.updater)
        self.assertIn('/usr/bin/bash "$installer"', self.updater)
        self.assertIn('QMessageBox.critical', self.updater)

    def test_update_has_graphical_smoke_test_and_rollback(self):
        self.assertIn('QT_QPA_PLATFORM=offscreen', self.installer)
        self.assertIn('-m mirivue --smoke-test', self.installer)
        self.assertIn("[[ \"${1:-}\" == '--rollback' ]]", self.installer)
        self.assertIn('mirivue-kde-previous', self.installer)
        self.assertIn('Keep one known-good version', self.installer)

    def test_missing_dependencies_are_reported_without_package_transactions(self):
        self.assertIn('report_missing_dependencies', self.installer)
        self.assertIn('sudo pacman -Syu --needed', self.installer)
        self.assertNotIn('pkexec', self.installer)
        self.assertNotIn('--noconfirm', self.installer)
        self.assertIn('show_error "$(dependency_report)$instructions"', self.installer)
        in_app = (ROOT / 'mirivue' / 'actions_extra.py').read_text(encoding='utf-8')
        self.assertIn('sudo pacman -Syu --needed ', in_app)
        self.assertNotIn('pkexec', in_app)
        self.assertNotIn('--noconfirm', in_app)

    def test_post_installation_verifier_checks_identity_and_real_window(self):
        verifier = (ROOT / 'Verifier-installation-RC194.sh').read_text(encoding='utf-8')
        self.assertIn("expected='1.0.0-rc194'", verifier)
        self.assertIn('Icon=org.pdenams.Mirivue.Qt', verifier)
        self.assertIn('--check-dependencies', verifier)
        self.assertIn('--smoke-test', verifier)
        self.assertIn('--ui-contract', verifier)
        self.assertIn('pacman -Qq mirivue-kde', verifier)
        self.assertIn("target='/usr/lib/mirivue-kde'", verifier)
        self.assertIn("launcher='/usr/bin/mirivue-kde'", verifier)
        self.assertIn('un lanceur utilisateur masque encore', verifier)
        self.assertIn('Exec=/usr/bin/mirivue-kde %U', verifier)
        self.assertIn('MimeType=inode/directory;', verifier)
        self.assertIn('desktop-file-validate', verifier)
        self.assertIn('mimeinfo.cache', verifier)
        self.assertIn('org\\.pdenams\\.Mirivue\\.Qt\\.desktop', verifier)
        self.assertIn('ensure_user_activation', verifier)
        self.assertIn('org.freedesktop.FileManager1.service', verifier)
        for helper in ('list', 'places', 'preview', 'service', 'transfer'):
            self.assertIn(helper, verifier)


if __name__ == '__main__':
    unittest.main()
