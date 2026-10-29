"""Popup scope and rename emphasis through real Qt widgets."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, QTimer, Qt, QPoint, QCoreApplication, QEvent
from PySide6.QtGui import QAction
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QLineEdit, QListView, QPushButton, QTableWidget, QComboBox
from mirivue.context_menu_settings import ContextMenuPage, filter_menu, mark_entry, setting_key
from mirivue.rename_ui import show_advanced_rename
from mirivue.metadata import basic_entry
import test_ergonomics_gui as ergonomics


class TestContextMenuGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.owner = QWidget()
        self.owner.settings = QSettings(self.temporary.name+'/settings.ini', QSettings.IniFormat)
        self.calls = []
        self.owner.show_shortcut_configuration = lambda: self.calls.append('shortcuts')

    def tearDown(self):
        self.owner.close()
        self.owner.deleteLater()
        self.application.processEvents()
        self.temporary.cleanup()

    def test_filter_removes_popup_reference_without_hiding_shared_action(self):
        shared = QAction('Copier le chemin', self.owner)
        main = QMenu(self.owner); main.addAction(shared)
        popup = QMenu(self.owner); popup.addSeparator(); popup.addAction(shared); popup.addSeparator()
        keep = popup.addAction('Ouvrir'); popup.addSeparator()
        mark_entry(shared, 'copy_location')
        self.owner.settings.setValue(setting_key('copy_location'), False)
        filter_menu(self.owner, popup)
        self.assertEqual(popup.actions(), [keep])
        self.assertIn(shared, main.actions())
        self.assertTrue(shared.isVisible())
        self.assertTrue(shared.isEnabled())

    def test_native_checklist_search_apply_defaults_and_shortcuts(self):
        page = ContextMenuPage(self.owner)
        self.assertTrue(page.native)
        page.resize(900, 700); page.show(); self.application.processEvents()
        self.assertIn('Copier le chemin', page.searchable_labels())
        search = page.widget.findChild(QLineEdit, 'contextMenuSearch')
        view = page.widget.findChild(QListView, 'contextMenuEntries')
        search.setText('Copier le chemin'); self.application.processEvents()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        draft = json.loads(page.library.mirivue_context_settings_result(page.pointer, 0))
        self.assertFalse(draft['builtins']['copy_location'])
        self.assertFalse(self.owner.settings.contains(setting_key('copy_location')))
        self.assertTrue(page.apply())
        self.assertFalse(self.owner.settings.value(setting_key('copy_location'), type=bool))
        QTest.mouseClick(page.widget.findChild(QPushButton, 'contextMenuDefaults'), Qt.MouseButton.LeftButton)
        self.assertFalse(self.owner.settings.value(setting_key('copy_location'), type=bool))
        self.assertTrue(page.apply())
        self.assertTrue(self.owner.settings.value(setting_key('copy_location'), type=bool))
        QTest.mouseClick(page.widget.findChild(QPushButton, 'contextMenuShortcuts'), Qt.MouseButton.LeftButton)
        self.application.processEvents()
        self.assertEqual(self.calls, ['shortcuts'])

    def test_discarded_draft_does_not_change_preferences(self):
        page = ContextMenuPage(self.owner)
        page.resize(900, 700); page.show(); self.application.processEvents()
        search = page.widget.findChild(QLineEdit, 'contextMenuSearch')
        search.setText('Copier le chemin'); self.application.processEvents()
        view = page.widget.findChild(QListView, 'contextMenuEntries')
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        page.close()
        self.assertFalse(self.owner.settings.contains(setting_key('copy_location')))
        replacement = ContextMenuPage(self.owner)
        result = json.loads(replacement.library.mirivue_context_settings_result(replacement.pointer, 0))
        self.assertTrue(result['builtins']['copy_location'])

    def test_native_service_checkbox_uses_shared_kde_configuration(self):
        import os
        import subprocess
        import sys
        root = Path(self.temporary.name)
        service = root/'data/kio/servicemenus/test.desktop'
        service.parent.mkdir(parents=True)
        service.write_text('[Desktop Entry]\nType=Service\nMimeType=text/plain;\nActions=mirivueTestAction;\n\n[Desktop Action mirivueTestAction]\nName=Service de contrôle Mirivue\nExec=/usr/bin/true %f\n')
        code = r"""
from pathlib import Path
import os
from PySide6.QtWidgets import QApplication,QWidget,QLineEdit,QListView
from PySide6.QtCore import QSettings,Qt,QPoint
from PySide6.QtTest import QTest
from mirivue.context_menu_settings import ContextMenuPage,service_enabled
app=QApplication([])
w=QWidget(); w.settings=QSettings(os.environ['XDG_CONFIG_HOME']+'/mirivue.ini',QSettings.IniFormat)
w.show_shortcut_configuration=lambda:None
p=ContextMenuPage(w); p.resize(900,700); p.show(); app.processEvents()
assert p.native and 'Service de contrôle Mirivue' in p.searchable_labels()
assert not any('mirivueTestAction' in label or ' — test' in label for label in p.searchable_labels())
p.widget.findChild(QLineEdit,'contextMenuSearch').setText('Service de contrôle Mirivue'); app.processEvents()
v=p.widget.findChild(QListView,'contextMenuEntries')
QTest.mouseClick(v.viewport(),Qt.MouseButton.LeftButton,pos=QPoint(10,10))
assert service_enabled('mirivueTestAction')
assert p.apply()
assert not service_enabled('mirivueTestAction')
config=Path(os.environ['XDG_CONFIG_HOME'])/'kservicemenurc'
assert 'mirivueTestAction=false' in config.read_text()
assert not w.settings.contains('context-menu/mirivueTestAction')
"""
        config = root/'config'; config.mkdir()
        environment = dict(os.environ, XDG_CONFIG_HOME=str(config), XDG_DATA_HOME=str(root/'data'))
        result = subprocess.run([sys.executable, '-c', code], env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)


class TestRenameEmphasisGui(unittest.TestCase):
    setUpClass = classmethod(ergonomics.TestErgonomicsGui.setUpClass.__func__)
    setUp = ergonomics.TestErgonomicsGui.setUp
    tearDown = ergonomics.TestErgonomicsGui.tearDown

    def test_popup_preferences_work_in_all_three_views(self):
        row = ergonomics.TestErgonomicsGui.choose(self, 'document.txt', 'other')
        for mode in (0, 1, 2):
            self.window.change_view(mode)
            self.window.settings.setValue(setting_key('copy_location'), True)
            menu = self.window.file_context_menu(row)
            self.assertTrue(any(a.property('_mirivue_context_id') == 'copy_location' for a in menu.actions()))
            self.window.settings.setValue(setting_key('copy_location'), False)
            filtered = self.window.file_context_menu(row)
            self.assertFalse(any(a.property('_mirivue_context_id') == 'copy_location' for a in filtered.actions()))
            self.assertTrue(any(a.text() == 'Copier' for a in filtered.actions()))
            self.assertTrue(self.window.transfer_actions['Copier'].isVisible())
            menu.deleteLater(); filtered.deleteLater()

    def test_discarded_menu_does_not_leave_deleted_shift_action(self):
        row = ergonomics.TestErgonomicsGui.choose(self, 'document.txt', 'other')
        menu = self.window.file_context_menu(row)
        self.assertTrue(self.window._dynamic_trash_actions)
        menu.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertFalse(self.window._dynamic_trash_actions)

    def test_only_valid_changed_proposals_are_bold_and_reset_live(self):
        rows = []
        for name in ('film.mkv', 'audio.flac'):
            path = self.root/name; path.write_bytes(b'fixture')
            rows.append(basic_entry(path))
        observed = []
        def exercise():
            dialog = self.application.activeModalWidget()
            try:
                table = dialog.findChild(QTableWidget, 'renamePreview')
                proposed = table.item(0, 1)
                self.assertIsNone(proposed.data(Qt.ItemDataRole.FontRole))
                proposed.setText('nouveau.mkv')
                self.assertTrue(proposed.font().bold())
                self.assertIsNone(table.item(0, 0).data(Qt.ItemDataRole.FontRole))
                self.assertIsNone(table.item(1, 1).data(Qt.ItemDataRole.FontRole))
                for role in (Qt.ItemDataRole.ForegroundRole, Qt.ItemDataRole.BackgroundRole):
                    self.assertIsNone(proposed.data(role))
                proposed.setText('film.mkv')
                self.assertIsNone(proposed.data(Qt.ItemDataRole.FontRole))
                proposed.setText('audio.flac')
                self.assertIsNone(proposed.data(Qt.ItemDataRole.FontRole))
                self.assertNotEqual(proposed.toolTip(), 'Nom inchangé.')
                proposed.setText('valide.mkv')
                self.assertTrue(proposed.font().bold())
                observed.append(True)
            except Exception as error:
                observed.append(error)
            finally:
                dialog.reject()
        QTimer.singleShot(0, exercise)
        show_advanced_rename(self.window, rows)
        self.assertEqual(observed, [True])
        self.assertTrue(all(row.path.exists() for row in rows))

    def test_automatic_rule_marks_changed_new_name_only(self):
        path = self.root/'film.mkv'; path.write_bytes(b'fixture')
        observed = []
        def exercise():
            dialog = self.application.activeModalWidget()
            try:
                rules = dialog.findChild(QComboBox, 'batch-rename-method')
                first = dialog.findChild(QLineEdit, 'batch-rename-primary')
                table = dialog.findChild(QTableWidget, 'renamePreview')
                rules.setCurrentIndex(rules.findData('prefix'))
                first.setText('Titre - ')
                self.assertEqual(table.item(0, 1).text(), 'Titre - film.mkv')
                self.assertTrue(table.item(0, 1).font().bold())
                rules.setCurrentIndex(rules.findData('metadata'))
                first.setText('{unknown}')
                self.assertIsNone(table.item(0, 1).data(Qt.ItemDataRole.FontRole))
                rules.setCurrentIndex(rules.findData('prefix'))
                first.clear()
                self.assertIsNone(table.item(0, 1).data(Qt.ItemDataRole.FontRole))
                observed.append(True)
            except Exception as error:
                observed.append(error)
            finally:
                dialog.reject()
        QTimer.singleShot(0, exercise)
        show_advanced_rename(self.window, [basic_entry(path)])
        self.assertEqual(observed, [True])
