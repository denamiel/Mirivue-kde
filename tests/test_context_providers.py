"""Provider identities, independent service insertion and native KIO actions."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMenu, QWidget
from mirivue.context_menu_settings import ContextMenuMixin, mark_entry, setting_key, entry_enabled
import test_ergonomics_gui as ergonomics

class Owner(ContextMenuMixin, QWidget):
    pass

class TestContextProviders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.owner = Owner()
        self.owner.settings = QSettings(self.temp.name+'/settings.ini', QSettings.IniFormat)
        self.menu = QMenu(self.owner)
        self.native = QMenu(self.menu)
        self.properties = self.menu.addAction('Propriétés')
        self.properties.setProperty('_mirivue_context_properties', True)

    def tearDown(self):
        self.owner.close(); self.owner.deleteLater(); self.app.processEvents(); self.temp.cleanup()

    def test_services_are_inserted_without_organize_group(self):
        action = self.native.addAction('Service KDE')
        self.owner.settings.setValue(setting_key('organize'), False)
        self.owner.merge_kde_context_menu(self.menu, self.native)
        self.assertIn(action, self.menu.actions())
        self.assertEqual(self.menu.actions()[-1], self.properties)

    def test_identical_labels_are_not_used_as_action_identity(self):
        own = self.menu.addAction('Même texte'); mark_entry(own, 'run_in_konsole')
        other = self.native.addAction('Même texte'); other.setProperty('_mirivue_kde_id', 'unrelated')
        self.owner.merge_kde_context_menu(self.menu, self.native)
        self.assertIn(own, self.menu.actions()); self.assertIn(other, self.menu.actions())

    def test_native_konsole_replaces_only_its_own_fallback(self):
        own = self.menu.addAction('Un libellé différent'); mark_entry(own, 'run_in_konsole')
        actual = self.native.addAction('Localized native action'); actual.setProperty('_mirivue_kde_id', 'runInKonsole')
        self.owner.merge_kde_context_menu(self.menu, self.native)
        self.assertNotIn(own, self.menu.actions()); self.assertIn(actual, self.menu.actions())

    def test_archive_providers_replace_fallbacks_by_id_in_nested_menu(self):
        group = self.menu.addMenu('Organiser')
        own = group.addAction('Créer une archive'); mark_entry(own, 'create_archive')
        extract = self.menu.addMenu('Secours'); extract.menuAction().setProperty('_mirivue_archive_extract', True)
        for provider in ('compressfileitemaction', 'extractfileitemaction'):
            action = self.native.addAction(provider); action.setProperty('_mirivue_kde_id', provider)
        self.owner.merge_kde_context_menu(self.menu, self.native)
        self.assertNotIn(own, group.actions()); self.assertNotIn(extract.menuAction(), self.menu.actions())

    def test_fallback_is_kept_without_a_native_menu(self):
        action = self.menu.addAction('Secours'); mark_entry(action, 'create_archive')
        self.owner.merge_kde_context_menu(self.menu, None)
        self.assertIn(action, self.menu.actions())

    def test_fallback_obeys_the_installed_provider_disabled_preference(self):
        with patch('mirivue.context_menu_settings.service_catalog', return_value=[{'id':'runInKonsole'}]), patch('mirivue.context_menu_settings.service_enabled', return_value=False):
            self.assertFalse(entry_enabled(self.owner.settings, 'run_in_konsole'))

    def test_native_catalog_and_menu_share_one_konsole_checkbox(self):
        root = Path(self.temp.name)
        data = root/'data/kio/servicemenus'; data.mkdir(parents=True)
        (data/'konsolerun.desktop').write_text('[Desktop Entry]\nType=Service\nMimeType=text/plain;\nActions=runInKonsole;\n[Desktop Action runInKonsole]\nName=Lancer dans Konsole\nExec=/usr/bin/true %f\n')
        (data/'ambiguous.desktop').write_text('[Desktop Entry]\nType=Service\nName=Fournisseur de contrôle\nMimeType=text/plain;\nActions=first;second;\n[Desktop Action first]\nName=Installer…\nExec=/usr/bin/true %f\n[Desktop Action second]\nName=Installer…\nExec=/usr/bin/true %f\n')
        config = root/'config'; config.mkdir()
        target=root/'test.txt';target.write_text('test')
        script=r'''
import ctypes,json,os,sys
import shiboken6
from pathlib import Path
from PySide6.QtWidgets import QApplication,QWidget,QMenu,QLineEdit,QListView
from PySide6.QtCore import QSettings,Qt,QPoint
from PySide6.QtTest import QTest
from mirivue.context_menu_settings import ContextMenuPage,entry_enabled
app=QApplication([])
pluginroot=Path(os.environ['MIRIVUE_TEST_PLACES_LIBRARY']).parent/'test-plugins'
assert pluginroot.is_dir(),pluginroot
app.addLibraryPath(str(pluginroot))
w=QWidget();w.settings=QSettings(os.environ['XDG_CONFIG_HOME']+'/mirivue.ini',QSettings.IniFormat);w.show_shortcut_configuration=lambda:None
p=ContextMenuPage(w);assert p.native
labels=p.searchable_labels()
assert labels.count('Installer…') == 2,labels
assert not any('[first]' in label or '[second]' in label for label in labels),labels
assert all(key in json.loads(p.library.mirivue_context_settings_result(p.pointer,0))['services'] for key in ('first','second'))
assert sum('Compresser' == label for label in labels)==1,labels
assert sum('Déplacer vers un nouveau dossier' in label for label in labels)==1,labels
assert sum('Lancer dans Konsole' in label for label in labels)==1,labels
result=json.loads(p.library.mirivue_context_settings_result(p.pointer,0))
assert 'run_in_konsole' not in result['builtins'] and result['services']['runInKonsole']
lib=p.library
lib.mirivue_service_actions_create.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p];lib.mirivue_service_actions_create.restype=ctypes.c_void_p
pointer=lib.mirivue_service_actions_create(shiboken6.getCppPointer(w)[0],shiboken6.getCppPointer(w)[0],json.dumps([Path(sys.argv[1]).as_uri()]).encode())
assert pointer
menu=shiboken6.wrapInstance(pointer,QMenu)
def all_actions(menu):
 for action in menu.actions():
  yield action
  if action.menu():yield from all_actions(action.menu())
ids=[a.property('_mirivue_kde_id') for a in all_actions(menu)]
for provider in ('runInKonsole','compressfileitemaction','extractfileitemaction'):
 assert ids.count(provider)==1,(provider,ids)
assert 'movetonewfolderitemaction' not in ids
assert 'create_archive' not in result['builtins']
p.resize(900,700);p.show();app.processEvents()
p.widget.findChild(QLineEdit,'contextMenuSearch').setText('Lancer dans Konsole');app.processEvents()
v=p.widget.findChild(QListView,'contextMenuEntries');QTest.mouseClick(v.viewport(),Qt.LeftButton,pos=QPoint(10,10))
assert p.apply();assert not entry_enabled(w.settings,'run_in_konsole')
assert 'runInKonsole=false' in (Path(os.environ['XDG_CONFIG_HOME'])/'kservicemenurc').read_text()
p.widget.findChild(QLineEdit,'contextMenuSearch').setText('Compresser');app.processEvents()
QTest.mouseClick(v.viewport(),Qt.LeftButton,pos=QPoint(10,10));assert p.apply()
assert not entry_enabled(w.settings,'create_archive')
pointer2=lib.mirivue_service_actions_create(shiboken6.getCppPointer(w)[0],shiboken6.getCppPointer(w)[0],json.dumps([Path(sys.argv[1]).as_uri()]).encode())
menu2=shiboken6.wrapInstance(pointer2,QMenu)
assert not any(a.property('_mirivue_kde_id')=='compressfileitemaction' for a in all_actions(menu2))
'''
        result=subprocess.run([sys.executable,'-c',script,str(target)],env=dict(os.environ,XDG_DATA_HOME=str(root/'data'),XDG_CONFIG_HOME=str(config)),capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

class TestActualContextComposition(unittest.TestCase):
    setUpClass=classmethod(ergonomics.TestErgonomicsGui.setUpClass.__func__)
    setUp=ergonomics.TestErgonomicsGui.setUp
    tearDown=ergonomics.TestErgonomicsGui.tearDown

    def test_hiding_organize_and_media_keeps_kde_actions_in_every_view(self):
        row=ergonomics.TestErgonomicsGui.choose(self,'document.txt','other')
        self.window.settings.setValue(setting_key('organize'),False)
        self.window.settings.setValue(setting_key('media'),False)
        for mode in (0,1,2):
            self.window.change_view(mode)
            menu=self.window.file_context_menu(row)
            self.assertFalse(any(a.property('_mirivue_extra_actions') for a in menu.actions()))
            native=QMenu(menu);action=native.addAction('Commande KDE')
            self.window.merge_kde_context_menu(menu,native)
            self.assertIn(action,menu.actions())
            self.assertEqual(menu.actions()[-1].text(),'Propriétés')
            menu.deleteLater()

    def test_one_file_can_move_to_a_new_folder_through_the_undo_service(self):
        row=ergonomics.TestErgonomicsGui.choose(self,'document.txt','other')
        self.window.folder=self.root
        menu=self.window.file_context_menu(row)
        group=next(a.menu() for a in menu.actions() if a.property('_mirivue_context_id')=='organize')
        action=next(a for a in group.actions() if a.property('_mirivue_context_id')=='move_to_new_folder')
        with patch('mirivue.movement.QInputDialog.getText',return_value=('Nouveau dossier',True)), patch('mirivue.movement.services.create_directory',return_value=(True,'')) as create, patch.object(self.window,'record_kio_history') as record, patch.object(self.window,'move_entries') as move:
            action.trigger()
            create.assert_called_once_with(self.root,'Nouveau dossier',require_undo=True)
            record.assert_called_once()
            move.assert_called_once_with([row.path],self.root/'Nouveau dossier',confirmed=True)
        self.assertTrue(row.path.exists())
