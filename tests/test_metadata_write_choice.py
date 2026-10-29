from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestMetadataWriteChoice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_ui = (ROOT / 'mirivue' / 'media_ui.py').read_text(encoding='utf-8')
        cls.configuration = (ROOT / 'mirivue' / 'configuration.py').read_text(encoding='utf-8')
        cls.iconography = (ROOT / 'mirivue' / 'iconography.py').read_text(encoding='utf-8')

    def test_configuration_has_no_metadata_storage_page(self):
        self.assertNotIn('def _metadata_page', self.configuration)
        self.assertNotIn('self._metadata_page()', self.configuration)
        self.assertNotIn("tr('Métadonnées'): tr('document-properties')", self.configuration)

    def test_choice_is_contextual_and_defaults_to_embedded_writing(self):
        self.assertIn("QCheckBox(tr('Enregistrer dans le fichier lorsque le format le permet'))", self.media_ui)
        self.assertIn('write_in_file.setChecked(True)', self.media_ui)
        self.assertIn("native_route(row) if write_in_file.isChecked() else tr('xmp')", self.media_ui)

    def test_suggestion_button_and_checkbox_share_a_compact_row(self):
        self.assertIn('suggestion_button.setSizePolicy(QSizePolicy.Policy.Maximum', self.media_ui)
        self.assertIn('options.addWidget(suggestion_button)', self.media_ui)
        self.assertIn('options.addStretch(1)', self.media_ui)
        self.assertIn('options.addWidget(write_in_file)', self.media_ui)

    def test_context_help_is_native_and_keyboard_accessible(self):
        self.assertIn('def context_help_button', self.iconography)
        self.assertIn('QIcon.fromTheme', self.iconography)
        self.assertIn('Qt.FocusPolicy.StrongFocus', self.iconography)
        self.assertIn('QMessageBox.information', self.iconography)


if __name__ == '__main__':
    unittest.main()
