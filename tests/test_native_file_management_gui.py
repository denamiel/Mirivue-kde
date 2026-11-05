"""Real KDE properties, simple rename, native inventory and preserved batch UI."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import faulthandler
faulthandler.enable()
faulthandler.dump_traceback_later(25, repeat=True)
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import shiboken6
from PySide6.QtCore import Qt, QTimer, QItemSelectionModel, QBuffer, QIODevice
from PySide6.QtGui import QImage, QColor
from PySide6.QtWidgets import QDialog, QTabBar, QLabel, QComboBox, QLineEdit, QTableWidget, QAbstractButton
from PySide6.QtTest import QTest
import test_dolphin_parity_gui as parity
from mirivue.app import Scanner
from mirivue.item_presentation import map_file_index
from mirivue.metadata import basic_entry
from mirivue.media import companion
from mirivue.directory_listing import directory_snapshot
from mirivue.native_properties import show_properties
from mirivue.thumbnails import native_preview_data

class TestNativeFileManagement(unittest.TestCase):
    setUpClass = classmethod(parity.TestDolphinParity.setUpClass.__func__)
    setUp = parity.TestDolphinParity.setUp
    new_window = parity.TestDolphinParity.new_window
    settle = parity.TestDolphinParity.settle

    def tearDown(self):
        for dialog in tuple(getattr(self.window, '_native_properties_dialogs', [])):
            if shiboken6.isValid(dialog): dialog.reject()
        self.app.clipboard().clear()
        parity.TestDolphinParity.tearDown(self)

    def wait_for(self, predicate):
        end = time.monotonic()+10
        timed_out = []
        watchdog = QTimer(self.window)
        def unblock():
            modal = self.app.activeModalWidget()
            if time.monotonic() >= end and isinstance(modal, QDialog):
                timed_out.append([label.text() for label in modal.findChildren(QLabel)])
                modal.reject()
        watchdog.timeout.connect(unblock)
        watchdog.start(50)
        try:
            while not predicate() and time.monotonic() < end:
                self.app.processEvents()
                QTest.qWait(10)
        finally:
            watchdog.stop()
        self.assertFalse(timed_out, str(timed_out))
        self.assertTrue(predicate(), 'native operation did not finish')

    def select(self, paths):
        self.window.scan()
        self.settle()
        view = self.window.active_view()
        view.selectionModel().clearSelection()
        for i, row in enumerate(self.window.model.rows):
            if row.path in paths:
                index = map_file_index(self.window.proxy, self.window.model.index(i,0))
                view.selectionModel().select(index, QItemSelectionModel.Select|QItemSelectionModel.Rows)
        self.assertEqual(set(self.window.selected_entries()), set(paths))

    def test_native_properties_permissions_are_applied(self):
        path = self.folders[0]/'note.txt'
        path.chmod(0o600)
        self.select([path])
        dialog = self.window.basic_properties()
        self.assertIsNotNone(dialog)
        self.wait_for(lambda: bool(dialog.findChildren(QTabBar)))
        bar = next(bar for bar in dialog.findChildren(QTabBar)
                   if any('permissions' in bar.tabText(i).replace('&','').lower() for i in range(bar.count())))
        index = next(i for i in range(bar.count()) if 'permissions' in bar.tabText(i).replace('&','').lower())
        QTest.mouseClick(bar, Qt.LeftButton, pos=bar.tabRect(index).center())
        label = next(label for label in dialog.findChildren(QLabel)
                     if label.text().replace('&','').lower().strip() == 'owner:')
        combo = label.buddy()
        self.assertIsInstance(combo, QComboBox)
        self.assertTrue(combo.isEnabled())
        index = next(i for i in range(combo.count()) if combo.itemText(i) == 'Can Only View')
        combo.setCurrentIndex(index)
        combo.activated.emit(index)
        dialog.accept()
        self.wait_for(lambda: (path.stat().st_mode & 0o777) == 0o400)
        self.assertEqual(path.read_text(), 'test')

    def test_native_properties_multi_selection_can_be_cancelled(self):
        paths = [self.folders[0]/'note.txt', self.folders[0]/'other.txt']
        paths[1].write_text('other')
        self.select(paths)
        dialog = self.window.basic_properties()
        self.assertIn('2', dialog.windowTitle())
        dialog.reject()
        self.assertEqual([p.read_text() for p in paths], ['test','other'])

    def png(self, name):
        path = self.folders[0]/name
        image = QImage(8,6,QImage.Format_RGB32)
        image.fill(QColor('red'))
        self.assertTrue(image.save(str(path)))
        companion(path).write_text('<x:xmpmeta xmlns:x="adobe:ns:meta/"/>')
        return path

    def test_properties_keep_media_companion_names_together(self):
        path = self.png('with-sidecar.png')
        self.select([path])
        dialog = self.window.basic_properties()
        edits = [edit for edit in dialog.findChildren(QLineEdit) if edit.text() == path.name]
        self.assertTrue(edits)
        self.assertTrue(all(edit.isReadOnly() for edit in edits))
        dialog.reject()
        self.assertTrue(companion(path).exists())

    def test_single_rename_is_native_and_undoable(self):
        path = self.folders[0]/'note.txt'
        target = path.with_name('renamed.txt')
        self.select([path])
        self.assertTrue(self.window.rename_inline(path, target.name))
        self.wait_for(lambda: not self.window.pending_transfers() and target.exists())
        self.assertFalse(path.exists())
        self.assertEqual(target.read_text(), 'test')
        self.assertEqual(self.window.file_undo_history()[-1][0], 'kio')
        self.window.undo_remote_transfer()
        self.wait_for(lambda: getattr(self.window, 'kio_undo_worker', None) is None and path.exists())
        self.assertFalse(target.exists())

    def test_single_rename_with_xmp_retains_the_specialised_transaction(self):
        path = self.png('paired.png')
        target = path.with_name('paired-new.png')
        self.select([path])
        self.assertTrue(self.window.rename_inline(path, target.name))
        self.assertTrue(target.exists())
        self.assertTrue(companion(target).exists())
        self.assertFalse(companion(path).exists())
        self.assertEqual(self.window.file_undo_history()[-1][0], 'rename')
        self.window.undo_remote_transfer()
        self.assertTrue(path.exists())
        self.assertTrue(companion(path).exists())

    def test_batch_numbering_ui_and_companions_are_preserved(self):
        paths = [self.png('first.png'), self.png('second.png')]
        original = {p.name:p.read_bytes() for p in paths}
        self.select(paths)
        timer = QTimer(self.window)
        acted, errors = [], []
        deadline = time.monotonic()+12
        def drive():
            dialog = self.app.activeModalWidget()
            if not isinstance(dialog, QDialog): return
            if time.monotonic() > deadline:
                errors.append('Timed out: '+repr([label.text() for label in dialog.findChildren(QLabel)]))
                dialog.reject()
                return
            method = dialog.findChild(QComboBox, 'batch-rename-method')
            if not method:
                errors.append('Unexpected dialog: '+repr([label.text() for label in dialog.findChildren(QLabel)]))
                dialog.reject()
                return
            if acted: return
            try:
                method.setCurrentIndex(method.findData('number'))
                dialog.findChild(QLineEdit,'batch-rename-primary').setText('Lot')
                self.assertEqual(dialog.findChild(QTableWidget).rowCount(), 2)
                acted.append(True)
                dialog.accept()
            except Exception as error:
                errors.append(repr(error))
                dialog.reject()
        timer.timeout.connect(drive)
        timer.start(20)
        try:
            self.window.rename_f2()  # Multiple selected entries must open the bulk tool.
        finally:
            timer.stop()
        self.assertEqual(errors, [])
        self.assertTrue(acted)
        for index, source in enumerate(paths,1):
            target = source.with_name(f'Lot {index:03d}.png')
            self.assertEqual(target.read_bytes(), original[source.name])
            self.assertTrue(companion(target).exists())
            self.assertFalse(source.exists())
        self.window.undo_remote_transfer()
        self.assertTrue(all(p.exists() and companion(p).exists() for p in paths))

    def test_native_inventory_hidden_and_same_size_modification(self):
        root = self.folders[0]
        (root/'.hidden').write_text('note.txt\n')
        scanner = Scanner(str(root), False, False)
        rows = []
        scanner.initial.connect(rows.extend)
        scanner.run()
        self.assertEqual(rows, [])
        (root/'.hidden').unlink()
        before = directory_snapshot(root)
        path = root/'note.txt'
        old = path.stat()
        path.write_text('next')
        os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns + 1234567))
        after = directory_snapshot(root)
        self.assertNotEqual(before[path], after[path])
        self.assertEqual(after[path][1], path.stat().st_mtime_ns)

    def test_native_video_fallback_without_a_thumbnail_plugin(self):
        import subprocess
        import tempfile
        video = self.root/'preview.mkv'
        subprocess.run(['ffmpeg','-v','error','-nostdin','-f','lavfi','-i',
                        'testsrc2=size=64x48:rate=5','-t','1','-c:v','ffv1',str(video)],check=True,timeout=15)
        with tempfile.TemporaryDirectory() as config:
            (Path(config)/'dolphinrc').write_text('[PreviewSettings]\nPlugins=mirivue-no-plugin\n')
            with patch.dict(os.environ, XDG_CONFIG_HOME=config):
                data = native_preview_data(video, video_fallback=True)
        self.assertFalse(QImage.fromData(data).isNull())
