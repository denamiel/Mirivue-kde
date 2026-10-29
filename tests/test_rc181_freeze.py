"""RC181 regressions: exercise real methods with disposable data."""
import json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from PySide6.QtCore import QSettings,Qt,QTimer,QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QWidget,QScrollArea,QTabBar
from mirivue.app import Window,FileSortProxy,VideoModel
from mirivue.metadata import Video,remote_entry

class FreezeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def test_closed_pane_commands_and_activation_are_silent(self):
  pane=NS(_closed=True)
  owner=NS(bound_pane=object(),capture_pane=lambda:self.fail('retired pane activated'),activate_pane=lambda p:self.fail('retired pane activated'))
  calls=[]
  Window.pane_command(owner,pane,lambda:calls.append(1))
  Window.activate_pane(owner,pane)
  self.assertEqual(calls,[])
 def test_retirement_stops_column_timer(self):
  from mirivue.panes import PaneMixin
  timer=QTimer();timer.start(10000)
  pane=NS(column_save_timer=timer,model=NS(pending_preliminary=[1],pending_resolved=[1]))
  owner=NS(cancel_duration_lookups=lambda p:None)
  PaneMixin.retire_pane(owner,pane)
  self.assertFalse(timer.isActive())
 def test_deleted_fallback_scroll_is_safe(self):
  from mirivue import panes
  reveal_breadcrumb_end = getattr(panes, 'reveal_breadcrumb_end', lambda scroll: scroll.horizontalScrollBar().setValue(scroll.horizontalScrollBar().maximum()))
  w=QScrollArea();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
  try:reveal_breadcrumb_end(w) # deleted wrapper must be ignored
  except RuntimeError as error:self.fail('A queued reveal touches a deleted C++ widget: '+str(error))
 def test_strict_payload_rejects_bad_types_and_limits(self):
  from mirivue.window_instances import WindowEndpoint
  receiver=QWidget();receiver.receive_launch_payload=lambda p:self.fail('Rejected input reached the window')
  endpoint=WindowEndpoint(receiver)
  for raw in ('{"locations":null}', '{"locations":[{"folder":"smb://["}]}'):
   try:self.assertFalse(endpoint.Dispatch(raw))
   except Exception as error:self.fail('Invalid request escaped validation: '+repr(error))
  from mirivue.window_instances import normalize_payload,decode_payload,MAX_MESSAGE_BYTES,MAX_STRING_LENGTH
  good={'locations':[{'folder':'/tmp','files':[]} ]}
  self.assertIsNotNone(normalize_payload(good))
  invalid=[{'locations':None},{'locations':1},{'locations':'x'},{'locations':[{'folder':1}]},{'locations':[{'folder':'smb://['}]},{'locations':[{'folder':'/tmp','files':'x'}]},{'locations':[{'folder':'/tmp','files':[1]}]},dict(good,detached_tab={})]
  for key in ('split','force_tabs','properties','activate_first'):invalid.append(dict(good,**{key:'false'}))
  invalid += [dict(good,activation_token=12),dict(good,activation_token='x'*(MAX_STRING_LENGTH+1)),{'locations':good['locations']*101}]
  for value in invalid:
   with self.subTest(value=str(value)[:60]):self.assertIsNone(normalize_payload(value))
  self.assertIsNone(decode_payload('['*1200+'0'+']'*1200))
  self.assertIsNone(decode_payload(' '*MAX_MESSAGE_BYTES+'{}'))
  self.assertIsNotNone(decode_payload(json.dumps(good)+' '*(MAX_MESSAGE_BYTES-len(json.dumps(good)))))
  self.assertIsNotNone(normalize_payload({'locations':good['locations']*100}))
  self.assertIsNotNone(normalize_payload(dict(good,activation_token='x'*MAX_STRING_LENGTH)))
  self.assertIsNone(normalize_payload(dict(good,activation_token='é'*MAX_STRING_LENGTH)))
  self.assertIsNotNone(normalize_payload({'locations':[{'folder':'/tmp','files':['/tmp/a']*10000}]}))
  self.assertIsNone(normalize_payload({'locations':[{'folder':'/tmp','files':['/tmp/a']*10001}]}))
 def test_session_keeps_101_tabs_and_checks_sync(self):
  from mirivue.session_state import SessionMixin
  class Harness(SessionMixin):
   def __init__(self,s):
    self.settings=s;self._tabs=[];self._active_tab=0;self.add('/tmp');self.tab_bar=NS(setCurrentIndex=self.select)
   def add(self,folder):
    p=NS(folder=folder,identity=object());t=NS(panes=[p],bound=p,split=False,splitter_sizes=[300,700],custom_title='',location=folder)
    self._tabs.append(t);self._active_tab=len(self._tabs)-1;self.bind_pane(p)
   def select(self,i):self._active_tab=i;self.bind_pane(self._tabs[i].bound)
   def bind_pane(self,p):self.bound_pane=p;self.panes=self._tabs[self._active_tab].panes;self.split_enabled=self._tabs[self._active_tab].split
   def open_new_tab(self,folder,**kw):self.add(folder)
   def prime_startup_pane(self,p,folder):p.folder=folder
   def startup_location_or(self,v,f):return v
   def set_split_view(self,*a,**kw):
    t=self._tabs[self._active_tab];t.split=True;t.panes.append(NS(folder='/tmp',identity=object()));self.panes=t.panes;self.split_enabled=True
   def capture_pane(self):pass
   def save_pane_splitter_sizes(self):pass
   def refresh_tab_title(self,*a):pass
   def restore_tab_splitter_sizes(self,*a):pass
   def sync_pane_path_bars(self):pass
   def sync_pane_controls(self):pass
   def show_activity_message(self,*a):pass
  with tempfile.TemporaryDirectory() as d:
   s=QSettings(str(Path(d)/'settings.ini'),QSettings.Format.IniFormat);s.setValue('startup/location','session')
   for n in (100,101):
    tabs=[dict(locations=['/tmp','/tmp'],active=i%2,split=True,widths=[300+i,700+i],title='Titre '+str(i)) for i in range(n)]
    original=dict(version=1,tabs=tabs,active=n-1);s.setValue('session/tabs-v1',json.dumps(original))
    for repeat in range(2):
     h=Harness(s);self.assertTrue(h.restore_tab_session());self.assertEqual(h.session_snapshot(),original);self.assertTrue(h.save_tab_session())
   h.settings=NS(setValue=lambda *a:None,sync=lambda:None,status=lambda:QSettings.Status.AccessError)
   self.assertFalse(h.save_tab_session())
 def sorted_names(self,rows,c,order=Qt.SortOrder.AscendingOrder):
  # No presentation bridge needed for the comparator; the real model is used.
  m=VideoModel();m.rows=rows;p=FileSortProxy();p.setSourceModel(m);p.sort(c,order)
  return [p.index(i,0).data() for i in range(p.rowCount())]
 def test_sort_track_resolution_author_empty_and_real_name(self):
  def row(name,c,value):
   r=Video(Path('/tmp')/name);r.values[0]=name;r.values[c]=value;return r
  a,b=row('a',21,'10'),row('b',21,'2/12')
  self.assertEqual(self.sorted_names([a,b],21),['b','a'])
  unknown=row('unknown',21,'')
  self.assertEqual(self.sorted_names([a,b,unknown],21),['unknown','b','a'])
  self.assertEqual(self.sorted_names([a,b,unknown],21,Qt.SortOrder.DescendingOrder),['a','b','unknown'])
  a,b=row('a',3,'1920 × 1080'),row('b',3,'1600 × 1600')
  a.sort_values[3]=1920*1080;b.sort_values[3]=1600*1600
  self.assertEqual(self.sorted_names([a,b],3),['b','a'])
  a,b=row('a',28,'auteur 2'),row('b',28,'auteur 10')
  self.assertEqual(self.sorted_names([a,b],28),['b','a'])
  a,b=row('a',18,''),row('b',18,'titre')
  self.assertEqual(self.sorted_names([a,b],18),['b','a']);self.assertEqual(self.sorted_names([a,b],18,Qt.SortOrder.DescendingOrder),['a','b'])
  a,b=remote_entry('trash:/name2','Same'),remote_entry('trash:/name10','Same')
  p=FileSortProxy();m=VideoModel();m.rows=[a,b];p.setSourceModel(m)
  self.assertTrue(p.lessThan(p.sourceModel().index(0,0),p.sourceModel().index(1,0)))
 def test_titles_use_rsqueeze_ascii_dots(self):
  def visible(title,custom='',split=False):
   pane=NS(folder=title);other=NS(folder='second')
   panes=[pane,other] if split else [pane]
   tab=NS(bound=pane,panes=panes,split=split,location=title,custom_title=custom)
   bar=QTabBar();bar.addTab('')
   owner=NS(_tabs=[tab],_active_tab=0,panes=panes,bound_pane=pane,folder=title,split_enabled=split,
    tab_title=lambda text:text,location_identity=lambda text:(text,'folder'),tab_bar=bar)
   Window.refresh_tab_title(owner,0);return bar.tabText(0)
  self.assertEqual(visible('x'*50),'x'*37+'...')
  self.assertEqual(visible('x'*50,custom='custom'*20),'custom'*20)
  self.assertEqual(visible('left'*12,split=True),('left'*12+' | (second)')[:37]+'...')
  from mirivue.places import automatic_tab_text
  for n in (39,40,41,50):self.assertEqual(automatic_tab_text('x'*n),'x'*n if n<=40 else 'x'*37+'...')
  self.assertEqual(automatic_tab_text('a'*36+'&'+'b'*10),'a'*36+'&...')
  self.assertEqual(automatic_tab_text('😀'*10+'x'*30),'😀'*10+'x'*17+'...')
  # This cut falls between the UTF-16 surrogate units of an emoji. The exact
  # native QString, like Dolphin's, must still contain 37 units plus 3 dots.
  import ctypes,os,shiboken6
  library=ctypes.CDLL(os.environ['MIRIVUE_TEST_PLACES_LIBRARY'])
  library.mirivue_tab_set_text.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_char_p]
  library.mirivue_tab_set_text.restype=ctypes.c_int
  bar=QTabBar();bar.addTab('')
  self.assertEqual(library.mirivue_tab_set_text(shiboken6.getCppPointer(bar)[0],0,('😀'*21).encode()),40)

 def test_python_provenance_and_native_mit_index(self):
  root=Path(__import__('mirivue').__file__).parent.parent
  for name in ('session_state.py','window_instances.py','view_policy.py','external_locations.py'):
   self.assertIn('SPDX-License-Identifier:',(root/'mirivue'/name).read_text())
  index=(root/'LICENCES-TIERS.md').read_text()
  for f in (root/'native').rglob('*'):
   if f.is_file() and 'SPDX-License-Identifier: MIT' in f.read_text(errors='ignore'):self.assertIn(str(f.relative_to(root)),index)
if __name__=='__main__':unittest.main(verbosity=2)
