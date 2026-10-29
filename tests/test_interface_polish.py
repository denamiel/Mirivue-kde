"""Real Qt controls and XMLGUI adapter; native editor has separate KF6 tests."""
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, QObject, Qt, QCoreApplication, QEvent
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication,QMainWindow,QToolBar,QWidget,QHBoxLayout,
                              QMenu,QGroupBox,QToolButton)
from PySide6.QtTest import QSignalSpy
from mirivue.configuration import ConfigurationDialog
from mirivue.menu_visibility import MenuVisibility
from mirivue import library
from mirivue.desktop import TOOLBAR,DEFAULT_TOOLBAR_ORDER,DEFAULT_TOOLBAR_HIDDEN,DEFAULT_TOOLBAR_BEFORE_PATHS
from test_date_style_configuration import Owner,ContextFixture


class TestInterfacePolish(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.settings=QSettings(self.temp.name+'/settings.ini',QSettings.Format.IniFormat)
        self.owner=Owner(self.settings);self.dialogs=[]
    def tearDown(self):
        for widget in self.dialogs:
            if hasattr(widget,'search_timer'):widget.search_timer.stop()
            widget.close();widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
        self.owner.close();self.app.processEvents();self.temp.cleanup()
    def dialog(self):
        with patch('mirivue.context_menu_settings.ContextMenuPage',ContextFixture):dialog=ConfigurationDialog(self.owner)
        self.dialogs.append(dialog);return dialog
    def test_settings_groups_follow_the_controls_purpose(self):
        d=self.dialog();page=d.pages.widget(0)
        groups={g.title():g for g in page.findChildren(QGroupBox)}
        self.assertEqual(set(groups),{'Démarrage','Affichage','Fermeture','Navigation','Onglets','Confidentialité'})
        for name in ('remember_folder_sort','sort_mode','hidden_last','folders_first','folder_size_display','date_relative'):
            self.assertTrue(groups['Affichage'].isAncestorOf(getattr(d,name)),name)
        for name in ('tabs_after_last','always_show_tabs','close_buttons_on_tabs'):
            self.assertTrue(groups['Onglets'].isAncestorOf(getattr(d,name)),name)
        self.assertTrue(groups['Navigation'].isAncestorOf(d.empty_double_click_up))
    def test_profile_page_title_matches_view_menu_without_changing_profiles(self):
        d=self.dialog()
        self.assertEqual(d.categories.item(1).text(),'Configurations de colonnes')
        self.assertEqual(d._edited_profiles,{'Test':{0,1}})
        d.reject();self.assertIsNone(self.settings.value('profiles'))
    def test_menu_help_tracks_changed_and_cleared_shortcuts(self):
        window=QMainWindow();self.dialogs.append(window);window.settings=self.settings
        toolbar=QToolBar(window);container=QWidget();layout=QHBoxLayout(container);menu=QMenu(window)
        with patch('mirivue.native_events.install_event_gate',return_value=QObject(window)):
            visibility=MenuVisibility(window,toolbar,layout,menu)
        visibility.open_action.setShortcut(QKeySequence('Ctrl+Alt+M'))
        visibility.action.setShortcut(QKeySequence('Ctrl+Alt+B'))
        hint=visibility.button.toolTip()
        self.assertIn(QKeySequence('Ctrl+Alt+M').toString(QKeySequence.NativeText),hint)
        self.assertIn(QKeySequence('Ctrl+Alt+B').toString(QKeySequence.NativeText),hint)
        self.assertNotIn('F10',hint)
        visibility.open_action.setShortcuts([]);visibility.action.setShortcuts([])
        self.assertEqual(visibility.button.toolTip(),'Ouvrir les menus — Afficher la barre de menus')
        self.assertNotIn('(F10)',dict(TOOLBAR)['menu_button'])
        visibility.detach();container.close()
    def test_disabled_reason_is_available_as_native_help_and_cleared_on_enable(self):
        from mirivue.action_feedback import set_action_enabled
        action=QAction('Modifier',self.owner);action.setToolTip('Aide initiale')
        set_action_enabled(action,False,'Fichier utilisé par une opération.')
        self.assertFalse(action.isEnabled())
        for text in (action.toolTip(),action.statusTip(),action.whatsThis()):self.assertEqual(text,'Fichier utilisé par une opération.')
        set_action_enabled(action,True)
        self.assertEqual(action.toolTip(),'Aide initiale');self.assertEqual(action.statusTip(),'');self.assertTrue(action.isEnabled())
    def test_legacy_toolbar_migration_keeps_order_visibility_and_path_side(self):
        from mirivue.toolbar_xml import encode_legacy,decode
        known=dict(TOOLBAR);order=list(reversed(DEFAULT_TOOLBAR_ORDER));hidden=['home','search_button']
        before={'up','menu_button','search_button'}
        document=encode_legacy(order,hidden,before,known);bars,properties=decode(document,known)
        self.assertEqual([n for k,n in bars['before_paths']],[n for n in order if n in before and n not in hidden])
        self.assertEqual([n for k,n in bars['after_paths']],[n for n in order if n not in before and n not in hidden])
        self.assertEqual(properties,{})
        self.assertFalse(self.settings.contains('library-v1/toolbar'))
    def test_xml_preserves_separators_spacers_duplicates_and_action_properties(self):
        from mirivue.toolbar_xml import decode
        xml='<gui><ToolBar name="before_paths"><Action name="up"/><Separator/><Spacer/></ToolBar><ToolBar name="after_paths"><Action name="up"/></ToolBar><ActionProperties><Action name="up" icon="folder" iconText="Parent personnalisé" priority="0"/></ActionProperties></gui>'
        library.write(self.settings,'toolbar',{'xml':xml})
        restored=QSettings(self.settings.fileName(),QSettings.Format.IniFormat)
        self.assertEqual(library.read(restored,'toolbar',{})['xml'],xml)
        bars,properties=decode(xml,dict(TOOLBAR))
        self.assertEqual(bars['before_paths'],[('action','up'),('separator',''),('spacer','')])
        self.assertEqual(bars['after_paths'],[('action','up')])
        self.assertEqual(properties['up'],{'icon':'folder','iconText':'Parent personnalisé','priority':'0'})
    def test_toolbar_mirrors_execute_once_and_follow_checked_and_enabled_state(self):
        from mirivue.toolbar_xml import render
        window=QMainWindow();self.dialogs.append(window)
        window.navigation_bar=QToolBar(window)
        window.left_toolbar_layout=QHBoxLayout();window.right_toolbar_layout=QHBoxLayout()
        for name,label in TOOLBAR:
            button=QToolButton(window);button.setText(label);setattr(window,name,button)
        window.up.setCheckable(True)
        spy=QSignalSpy(window.up.clicked)
        render(window,{'before_paths':[('action','up'),('separator',''),('spacer','')],
                       'after_paths':[('action','up')]},{'up':{'iconText':'Parent'}})
        mirror=window.right_toolbar_layout.itemAt(0).widget()
        self.assertIsNot(mirror,window.up);self.assertEqual(mirror.text(),'Parent')
        mirror.click();self.assertEqual(spy.count(),1);self.assertTrue(window.up.isChecked());self.assertTrue(mirror.isChecked())
        window.up.setEnabled(False);self.assertFalse(mirror.isEnabled())
        self.assertEqual(window.left_toolbar_layout.count(),3)
    def test_invalid_toolbar_xml_is_rejected_without_executing_actions(self):
        from mirivue.toolbar_xml import decode
        import xml.etree.ElementTree as ET
        for xml in ('bad','<gui>', '<foreign/>', 'x'*(1024*1024+1)):
            with self.subTest(xml=xml[:20]):
                with self.assertRaises((ValueError,ET.ParseError)):decode(xml,dict(TOOLBAR))

    def test_pending_category_resize_is_cancelled_when_dialog_is_destroyed(self):
        dialog=self.dialog()
        errors=[]
        with patch.object(sys,'excepthook',lambda *args:errors.append(args)):
            dialog.categories.changeEvent(QEvent(QEvent.Type.FontChange))
            dialog.search_timer.stop()
            dialog.close();dialog.deleteLater()
            self.dialogs.remove(dialog)
            QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
            self.app.processEvents()
        self.assertEqual(errors,[])
