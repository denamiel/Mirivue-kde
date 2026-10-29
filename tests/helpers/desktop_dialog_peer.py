"""One real-KDE scenario per isolated process; no personal files or session bus."""
import ctypes,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QObject,QSettings,QTimer,QCoreApplication,QEvent,Qt
from PySide6.QtGui import QAction,QKeySequence
from PySide6.QtWidgets import QApplication,QMainWindow,QMenu,QToolBar,QWidget,QHBoxLayout,QToolButton
from PySide6.QtTest import QTest
from mirivue import keyboard
from mirivue.native_shortcuts import create_dialog
from mirivue.menu_visibility import MenuVisibility

app=QApplication([]);app.setOrganizationName('mirivue-tests');app.setApplicationName('mirivue-desktop-peer')
class Call:
 def __call__(self,*args):pass
class Watch:
 mirivue_watch_desktop_shortcuts=Call()
NATIVE={'cut':['Ctrl+X'],'delete-permanent':['Shift+Delete'],'back':['Alt+Left'],
        'tab-next':['Ctrl+PageDown'],'tab-previous':['Ctrl+PageUp'],
        'select-all':['Ctrl+A'],'refresh':['F5'],'zoom-in':['Ctrl++','Ctrl+=']}
class KeysOwner(QMainWindow):
 def __init__(self):
  super().__init__();self.settings=QSettings(os.environ['XDG_CONFIG_HOME']+'/mirivue.ini',QSettings.IniFormat);self.closing=False
  self.shortcut_bindings=[]
  for identifier,title,default in [('select-all','Tout sélectionner','Ctrl+A'),('refresh','Actualiser','F5'),('zoom-in','Agrandir','Ctrl++')]:
   action=QAction(title,self);setattr(self,identifier.replace('-','_')+'_action',action)
   self.shortcut_bindings.append(dict(id=identifier,title=title,default=default,sequence=default,targets=[action]))
  self.apply_shortcut_bindings()
 def apply_shortcut_bindings(self,values=None):
  with patch('mirivue.keyboard._native_defaults',return_value=(dict(NATIVE),Watch())):
   keyboard.apply_bindings(self,values)

def snapshot(settings):settings.sync();return {key:settings.value(key) for key in settings.allKeys()}
def close_dialog(dialog):dialog.close();dialog.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
def shortcut_case(scenario):
 w=KeysOwner()
 if scenario=='alternates':
  w.apply_shortcut_bindings({'zoom-in':['Ctrl+Alt+Z','Ctrl+Alt+Y'],'refresh':[]})
  before=snapshot(w.settings)
  d=create_dialog(w)
  assert d.metaObject().className()=='KShortcutsDialog'
  d.accept();assert snapshot(w.settings)==before
  new=KeysOwner()
  assert [k.toString(QKeySequence.PortableText) for k in new.zoom_in_action.shortcuts()]==['Ctrl+Alt+Z','Ctrl+Alt+Y']
  assert new.refresh_action.shortcuts()==[]
  close_dialog(d);new.close()
 elif scenario=='cancel':
  w.apply_shortcut_bindings({'select-all':'Ctrl+Alt+A','refresh':''})
  before=snapshot(w.settings);d=create_dialog(w);d.restore_defaults();d.reject()
  assert snapshot(w.settings)==before
  assert w.select_all_action.shortcut().toString()=='Ctrl+Alt+A'
  close_dialog(d)
 elif scenario=='defaults':
  w.apply_shortcut_bindings({'select-all':'Ctrl+Alt+A','refresh':''})
  d=create_dialog(w);d.restore_defaults();d.accept()
  assert not w.settings.contains('shortcuts/select-all')
  assert not w.settings.contains('shortcuts/refresh')
  assert [k.toString(QKeySequence.PortableText) for k in w.zoom_in_action.shortcuts()]==['Ctrl++','Ctrl+=']
  close_dialog(d)
 elif scenario=='save-failure':
  w.apply_shortcut_bindings({'select-all':'Ctrl+Alt+A'})
  before=snapshot(w.settings);original=w.apply_shortcut_bindings
  def fail_once(values=None):
   if values is not None:
    w.settings.setValue('shortcuts/select-all','Ctrl+X')
    raise OSError('simulated write failure')
   return original()
  w.apply_shortcut_bindings=fail_once
  d=create_dialog(w);d.restore_defaults()
  with patch('mirivue.native_shortcuts.QMessageBox.warning') as warning:
   d.accept();assert warning.call_count==1
  assert snapshot(w.settings)==before
  assert w.select_all_action.shortcut().toString()=='Ctrl+Alt+A'
  close_dialog(d)
 elif scenario=='modeless':
  d=create_dialog(w);d.show_native();app.processEvents()
  assert d.isVisible() and not d.isModal()
  assert d is create_dialog.__globals__['shiboken6'].wrapInstance(create_dialog.__globals__['shiboken6'].getCppPointer(d)[0],type(d))
  d.reject();close_dialog(d)
 else:raise AssertionError(scenario)
 assert not Path(os.environ['XDG_CONFIG_HOME'],'dolphinrc').exists()
 w.close()

class MenuOwner(QMainWindow):
 def __init__(self):
  super().__init__();self.resize(900,500)
  self.settings=QSettings(os.environ['XDG_CONFIG_HOME']+'/mirivue.ini',QSettings.IniFormat)
  self.main_menus={name:self.menuBar().addMenu(title) for name,title in [('file','Fichier'),('edit','Édition'),('view','Affichage'),('go','Aller'),('tools','Outils'),('settings','Configuration'),('help','Aide')]}
  titles={'rename_action':'Renommer','delete_button':'Mettre à la corbeille','properties_action':'Propriétés',
          'new_folder_action':'Nouveau dossier','kio_undo_action':'Annuler','kio_redo_action':'Rétablir',
          'search_action':'Rechercher','quick_filter_action':'Filtrer','new_window_action':'Nouvelle fenêtre',
          'new_tab_action':'Nouvel onglet','reopen_tab_action':'Rouvrir','open_terminal_action':'Terminal',
          'hidden_action':'Éléments cachés','configure_shortcuts_action':'Raccourcis',
          'toolbar_action':'Configurer la barre','configure_action':'Configurer Mirivue',
          'refresh':'Actualiser','details_view_action':'Détaillée','icons_view_action':'Icônes',
          'compact_view_action':'Compacte','split_action':'Scinder','preview_action':'Miniatures',
          'preview_panel_action':'Aperçu'}
  for name,title in titles.items():setattr(self,name,QAction(title,self))
  self.reopen_tab_action.setEnabled(False)
  self.transfer_actions={title:QAction(title,self) for title in ['Couper','Copier','Coller']}
  self.dolphin_shortcuts={name:QAction(name,self) for name in ['back','forward','parent','home']}
  for name,title in [('view_mode_menu','Mode'),('sort_menu','Trier'),('extra_info_menu','Informations'),
                     ('panels_menu','Panneaux'),('recently_closed_tabs_menu','Onglets fermés'),('rename_menu','Renommer et organiser')]:
   setattr(self,name,QMenu(title,self))
  self.advanced=self.rename_menu.addAction('Renommage avancé…')
  self.main_menus['tools'].addMenu(self.rename_menu)
  self.main_menus['file'].addActions([self.new_folder_action,self.properties_action])
  self.main_menus['edit'].addActions([self.search_action,*self.transfer_actions.values()])
  self.main_menus['help'].addAction('Guide')
  self.navigation_bar=QToolBar(self);self.addToolBar(self.navigation_bar)
  holder=QWidget();self.navigation_bar.addWidget(holder);layout=QHBoxLayout(holder)
  with patch('mirivue.native_events.install_event_gate',return_value=QObject(self)):
   self.menu_visibility=MenuVisibility(self,self.navigation_bar,layout,self.main_menus['view'])
  for name in ['back','forward','up','home','refresh_button','details_button','icons_button','compact_button',
               'view_mode_button','split_button','hidden','preview_button','preview_panel_button','search_button']:
   button=QToolButton();button.setText(name);setattr(self,name,button);layout.addWidget(button)
   if name!='search_button':button.hide()
  self._toolbar_xml_widgets=[]
 def update_main_menu_states(self,**kwargs):pass
 def active_view(self):return self

def all_actions(menu,seen=None):
 seen=set() if seen is None else seen
 for action in menu.actions():
  if action in seen:continue
  seen.add(action)
  if action.menu() is not None:all_actions(action.menu(),seen)
 return seen

def inspect_popup(w, inspect, button=None):
 # QToolButton::showMenu is allowed to run a nested event loop (Qt 6.11).
 # Inspect and close from that loop, not after a blocking press has returned.
 state={'done':False,'error':None}
 poll=QTimer(w);poll.setInterval(1)
 deadline=QTimer(w);deadline.setSingleShot(True)
 def close_popups():
  for widget in app.topLevelWidgets():
   if isinstance(widget,QMenu) and widget.isVisible():widget.close()
 def finish(error=None):
  state.update(done=True,error=error);poll.stop();deadline.stop();close_popups()
 def examine():
  popup=button.menu() if button is not None else w.menu_visibility.popup
  if popup is None or not popup.isVisible():return
  try:inspect(popup)
  except Exception as error:finish(error)
  else:finish()
 poll.timeout.connect(examine)
 deadline.timeout.connect(lambda:finish(AssertionError('Native menu did not become visible within 3 seconds')))
 poll.start();deadline.start(3000)
 try:
  if button is None:w.menu_visibility.open_popup()
  else:QTest.mousePress(button,Qt.LeftButton)
  while not state['done']:QTest.qWait(1)
 finally:
  poll.stop();deadline.stop();close_popups();poll.deleteLater();deadline.deleteLater()
 if state['error'] is not None:raise state['error']


def menu_case(scenario):
 w=MenuOwner();w.show();w.activateWindow();app.processEvents()
 m=w.menu_visibility
 assert m.native and m.open_action.metaObject().className()=='KHamburgerMenu'
 if scenario=='visibility':
  assert not w.menuBar().isVisible() and m.button.isVisible()
  m.action.setChecked(True);app.processEvents();assert w.menuBar().isVisible() and not m.button.isVisible()
  m.open_action.trigger();app.processEvents();assert w.menuBar().activeAction() is not None
  m.action.setChecked(False);app.processEvents();assert m.button.isVisible()
 elif scenario=='curated':
  def visible_search(popup):
   assert w.search_action not in popup.actions(),[a.text() for a in popup.actions()]
   assert w.advanced in all_actions(popup)
  inspect_popup(w,visible_search)
  w.search_button.hide();app.processEvents()
  def hidden_search(popup):assert w.search_action in popup.actions()
  inspect_popup(w,hidden_search)
 elif scenario=='borrowed-actions':
  # Production creates these actions with QMenu.addAction(text, callback),
  # unlike QAction(parent) fixtures. PySide clear() invalidates such wrappers.
  original=w.properties_action
  w.main_menus['file'].removeAction(original)
  hits=[]
  w.properties_action=w.main_menus['file'].addAction('Propriétés',lambda:hits.append('properties'))
  w.toolbar_action=w.main_menus['settings'].addAction('Configurer la barre',lambda:hits.append('toolbar'))
  refs=[w.properties_action,w.toolbar_action]
  for _ in range(4):
   QTest.keyClick(w.menu_button,Qt.Key_Tab);app.processEvents()
   assert all(__import__('shiboken6').isValid(action) for action in refs)
   def preserved(popup):assert w.properties_action in all_actions(popup)
   inspect_popup(w,preserved);app.processEvents()
  w.properties_action.trigger();w.toolbar_action.trigger()
  assert hits==['properties','toolbar']
  assert w.properties_action in w.main_menus['file'].actions()
 elif scenario=='clone':
  clone=m.open_action.requestWidget(w)
  m.button.parentWidget().layout().addWidget(clone);clone.show();app.processEvents()
  assert clone.defaultAction() is m.open_action
  def specialised(popup):assert w.advanced in all_actions(popup)
  inspect_popup(w,specialised,button=clone)
  QTest.mouseRelease(clone,Qt.LeftButton);m.open_action.releaseWidget(clone)
  QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
  inspect_popup(w,specialised)
 elif scenario=='context':
  w.navigation_bar.hide();app.processEvents()
  context=QMenu(w);context.addAction('Propriétés');m.add_to_context_menu(context)
  context.popup(w.mapToGlobal(w.rect().center()));app.processEvents()
  candidates=[a for a in context.actions() if a.menu() is m.popup]
  assert len(candidates)==1 and candidates[0].isVisible()
  assert context.actions()[0] is candidates[0]
  assert w.advanced in all_actions(m.popup)
  context.close()
 else:raise AssertionError(scenario)
 m.detach();w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

scenario=sys.argv[1]
if scenario in ('alternates','cancel','defaults','modeless','save-failure'):shortcut_case(scenario)
else:menu_case(scenario)
print(json.dumps({'scenario':scenario,'ok':True}))
