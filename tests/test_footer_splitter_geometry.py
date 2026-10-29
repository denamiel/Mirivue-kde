"""Changing file counts and free space must not move the split-pane divider."""

import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QHBoxLayout, QSizePolicy, QSplitter, QVBoxLayout, QWidget
    from mirivue.panes import PaneElidingLabel
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, 'PySide6 indisponible')
class TestFooterSplitterGeometry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication(['Mirivue-test'])

    def test_changing_counts_and_disk_space_keeps_pane_widths(self):
        splitter = QSplitter()
        footers = []
        for _ in range(2):
            pane = QWidget()
            pane.setMinimumWidth(120)
            layout = QVBoxLayout(pane)
            footer = QWidget(pane)
            row = QHBoxLayout(footer)
            labels = []
            for stretch in (4, 2, 4):
                label = PaneElidingLabel(footer)
                label.setMinimumWidth(0)
                label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                row.addWidget(label, stretch)
                labels.append(label)
            layout.addWidget(footer)
            splitter.addWidget(pane)
            footers.append(labels)
        try:
            splitter.resize(660, 250)
            splitter.show()
            splitter.setSizes([320, 320])
            self.application.processEvents()
            before = splitter.sizes()
            footers[0][0].set_full_text('999 dossiers, 999 fichiers (900 Gio)', Qt.TextElideMode.ElideRight)
            footers[0][2].set_full_text('Stockage — 999,9 Gio libres', Qt.TextElideMode.ElideLeft)
            self.application.processEvents()
            self.assertEqual(splitter.sizes(), before)
            footers[0][0].set_full_text('0 élément')
            footers[0][2].set_full_text('Stockage — 0 o libres')
            self.application.processEvents()
            self.assertEqual(splitter.sizes(), before)
        finally:
            splitter.close()


if __name__ == '__main__':
    unittest.main()
