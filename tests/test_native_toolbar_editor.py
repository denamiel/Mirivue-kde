"""Real KEditToolBar controls, Apply/Cancel and disposable XMLGUI configuration."""
import os
import time
from pathlib import Path
import tempfile
import unittest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import (QApplication,QMainWindow,QToolBar,QToolButton,
                              QListWidget,QDialogButtonBox)
from mirivue.desktop import DesktopMixin,TOOLBAR
from mirivue import library
from mirivue.toolbar_xml import edit,decode


class Owner(QMainWindow):
    toolbar_state=DesktopMixin.toolbar_state
    def __init__(self,settings):
        super().__init__();self.settings=settings;self.apply_count=0
        self.navigation_bar=QToolBar(self)
        for name,title in TOOLBAR:
            button=QToolButton(self);button.setText(title);setattr(self,name,button)
    def apply_toolbar(self):self.apply_count+=1


class TestNativeToolbarEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        path=os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY','')
        if not path or not Path(path).is_file():
            raise unittest.SkipTest('Valider compile le pont KDE pour ce contrôle réel')
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.settings=QSettings(self.temp.name+'/settings.ini',QSettings.Format.IniFormat)
        self.owner=Owner(self.settings)
    def tearDown(self):
        self.owner.close();self.owner.deleteLater();self.app.processEvents();self.temp.cleanup()
    def run_editor(self,apply):
        observed=[]
        def exercise():
            dialog=self.app.activeModalWidget()
            try:
                self.assertIsNotNone(dialog)
                self.assertEqual(dialog.metaObject().className(),'KEditToolBar')
                self.assertEqual(dialog.objectName(),'mirivueNativeToolbarEditor')
                lists=dialog.findChildren(QListWidget)
                self.assertEqual(len(lists),2)
                active=lists[-1]
                self.assertGreater(active.count(),1)
                before=[active.item(i).text() for i in range(active.count())]
                active.setCurrentRow(1)
                arrows=sorted((b for b in dialog.findChildren(QToolButton) if b.autoRepeat()),key=lambda b:b.geometry().y())
                self.assertEqual(len(arrows),2)
                self.assertTrue(arrows[0].isEnabled())
                arrows[0].click()
                after=[active.item(i).text() for i in range(active.count())]
                self.assertEqual(after,[before[1],before[0],*before[2:]])
                if apply:
                    buttons=dialog.findChild(QDialogButtonBox)
                    buttons.button(QDialogButtonBox.Apply).click()
                    self.assertGreater(self.owner.apply_count,0)
                observed.append(True)
            except Exception as error:observed.append(error)
            finally:
                if dialog is not None:dialog.reject()
        timer=QTimer(self.owner);timer.setSingleShot(True)
        timer.timeout.connect(exercise);timer.start(0)
        try:edit(self.owner)
        finally:timer.stop()
        self.assertEqual(observed,[True])
    def test_cancel_preserves_legacy_profile_exactly(self):
        original={'order':['up','back','forward','refresh_button','home','menu_button'],
                  'hidden':['home'],'before_paths':['up','back','forward','refresh_button']}
        library.write(self.settings,'toolbar',original)
        self.run_editor(False)
        self.assertEqual(library.read(self.settings,'toolbar',{}),original)
        self.assertEqual(self.owner.apply_count,0)
    def test_apply_is_saved_even_if_followed_by_cancel_and_survives_reopening(self):
        self.run_editor(True)
        saved=library.read(self.settings,'toolbar',{})
        bars,_properties=decode(saved['xml'],dict(TOOLBAR))
        self.assertEqual([name for kind,name in bars['before_paths'] if kind=='action'][:2],['forward','back'])
        reopened=QSettings(self.settings.fileName(),QSettings.Format.IniFormat)
        self.assertEqual(library.read(reopened,'toolbar',{}),saved)
        self.run_editor(False)
        self.assertEqual(library.read(self.settings,'toolbar',{}),saved)

    def test_restore_defaults_applies_the_default_source_not_the_current_profile(self):
        from mirivue.toolbar_xml import encode_legacy
        current=encode_legacy(['up','back'],[],{'up','back'},dict(TOOLBAR))
        library.write(self.settings,'toolbar',{'xml':current,'order':['up','back'],
                                              'hidden':[],'before_paths':['up','back']})
        observed=[]
        started=[0.0]
        editor=[None]
        previous_windows=[]
        def confirm():
            candidates=[popup for popup in self.app.topLevelWidgets()
                        if popup.isVisible() and hasattr(popup,'reject')
                        and popup not in previous_windows]
            if not candidates and time.monotonic()-started[0]<2:
                QTimer.singleShot(10,confirm)
                return
            warning=candidates[0] if candidates else None
            try:
                self.assertIsNotNone(warning)
                box=warning.findChild(QDialogButtonBox)
                candidates=[button for button in box.buttons()
                            if box.buttonRole(button) in (QDialogButtonBox.AcceptRole,QDialogButtonBox.YesRole)]
                self.assertEqual(len(candidates),1)
                candidates[0].click()
            except Exception as error:
                observed.append(error)
                for popup in self.app.topLevelWidgets():
                    if (popup is editor[0] or popup not in previous_windows) and hasattr(popup,'reject'): popup.reject()
        def reset():
            dialog=self.app.activeModalWidget()
            editor[0]=dialog
            try:
                box=dialog.findChild(QDialogButtonBox)
                previous_windows[:]=self.app.topLevelWidgets()
                started[0]=time.monotonic()
                QTimer.singleShot(0,confirm)
                box.button(QDialogButtonBox.RestoreDefaults).click()
                self.assertGreater(self.owner.apply_count,0)
                bars,_properties=decode(library.read(self.settings,'toolbar',{})['xml'],dict(TOOLBAR))
                self.assertEqual([name for kind,name in bars['before_paths'] if kind=='action'],
                                 ['back','forward','up','refresh_button'])
                observed.append(True)
            except Exception as error:observed.append(error)
            finally:
                if dialog is not None:dialog.reject()
        timer=QTimer(self.owner);timer.setSingleShot(True);timer.timeout.connect(reset);timer.start(0)
        try:edit(self.owner)
        finally:timer.stop()
        self.assertEqual(observed,[True])
