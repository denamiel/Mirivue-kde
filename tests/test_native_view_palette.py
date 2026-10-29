"""Pixel checks of the actual native file viewport against Dolphin's policy."""
import os
from pathlib import Path
import unittest
from support.native_style_checks import available_styles, check_native


class TestNativeViewPalette(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        navigator = Path(os.environ['MIRIVUE_TEST_NAVIGATOR_EXECUTABLE'])
        cls.executable = navigator.with_name('mirivue-view-palette-check')
        if not cls.executable.is_file():
            raise RuntimeError('Valider doit compiler le contrôle de palette des vues')
        cls.styles = available_styles(navigator)

    def check(self, scenario):
        for style in self.styles:
            for scheme in ('light', 'dark'):
                with self.subTest(style=style, scheme=scheme):
                    check_native(self, self.executable, scenario, style, scheme)

    def test_background_matches_dolphin_for_active_and_inactive_panes(self):
        self.check('background')

    def test_window_activation_updates_the_correct_palette_group(self):
        self.check('activation')

    def test_parent_palette_changes_keep_the_kde_view_background(self):
        self.check('themes')

    def test_all_three_layouts_keep_the_native_view_background(self):
        self.check('modes')
