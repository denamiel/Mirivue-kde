import subprocess
import sys
import unittest

from mirivue.inline_rename import selected_name_length


class TestInlineRenameSelection(unittest.TestCase):
    def test_file_name_selection_preserves_last_extension(self):
        self.assertEqual(selected_name_length('film.mkv'), len('film'))
        self.assertEqual(selected_name_length('film.final.mkv'), len('film.final'))
        self.assertEqual(selected_name_length('film.tar.gz', known_suffix='tar.gz'), len('film'))
        self.assertEqual(selected_name_length('.bashrc'), len('.bashrc'))
        self.assertEqual(selected_name_length('film.'), len('film.'))
        self.assertEqual(selected_name_length('film'), len('film'))
        self.assertEqual(selected_name_length('dossier.v1', is_dir=True), len('dossier.v1'))
        self.assertEqual(selected_name_length('🎞film.mkv'), len('🎞film'.encode('utf-16-le')) // 2)

    @unittest.skipUnless(subprocess.run(
        [sys.executable, '-c', 'import PySide6'], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=False).returncode == 0, 'PySide6 indisponible')
    def test_qt_views_select_base_after_editor_receives_focus(self):
        from PySide6.QtGui import QStandardItem, QStandardItemModel
        from PySide6.QtWidgets import QApplication, QTextEdit, QListView
        from mirivue.selection import DetailsView, IconView
        from mirivue.selection import IS_DIRECTORY_ROLE

        application = QApplication.instance() or QApplication([])
        views = (DetailsView(), IconView(), IconView())
        views[1].setViewMode(QListView.ViewMode.IconMode)
        views[2].setViewMode(QListView.ViewMode.ListMode)
        for view in views:
            model = QStandardItemModel(view)
            item = QStandardItem('film.mkv')
            item.setData(False, IS_DIRECTORY_ROLE)
            model.appendRow(item)
            view.setModel(model)
            view.show()
            application.processEvents()
            view.edit(model.index(0, 0))
            application.processEvents()
            editor = view.findChild(QTextEdit)
            self.assertIsNotNone(editor)
            self.assertEqual(editor.toPlainText(), 'film.mkv')
            self.assertEqual(editor.textCursor().selectedText(), 'film')
            editor.insertPlainText('nouveau')
            self.assertEqual(editor.toPlainText(), 'nouveau.mkv')
            view.close()
            application.processEvents()


if __name__ == '__main__':
    unittest.main()
