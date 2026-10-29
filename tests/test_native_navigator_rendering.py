"""Compare real breadcrumb pixels against KF6, in isolated child processes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from support.native_style_checks import available_styles, check_native


class TestNativeNavigatorRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidate = os.environ.get('MIRIVUE_TEST_NAVIGATOR_EXECUTABLE', '')
        if not candidate or not Path(candidate).is_file():
            raise unittest.SkipTest('Valider compile le contrôle natif des fils d’Ariane')
        cls.executable = candidate
        cls.styles = available_styles(candidate)

    def check_native(self, scenario):
        for style in self.styles:
            with self.subTest(style=style):
                check_native(self, self.executable, scenario, style)

    def test_native_palette_and_pixels_follow_light_and_dark_theme(self):
        self.check_native('palette')

    def test_font_changes_keep_the_complete_kde_frame_and_restore_height(self):
        self.check_native('font')

    def test_style_changes_recompute_native_metrics(self):
        self.check_native('style')

    def test_editing_focus_and_return_to_breadcrumb_match_kde(self):
        self.check_native('editor')

    def test_pane_activation_keeps_the_normal_frame(self):
        self.check_native('active')

    def test_toolbar_frame_matches_dolphins_native_container_context(self):
        self.check_native('toolbar')
