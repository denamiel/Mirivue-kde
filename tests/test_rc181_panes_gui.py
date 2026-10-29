"""Late deliveries after real deferred destruction, including split tabs."""
import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from PySide6.QtCore import QTimer,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from mirivue.app import Window
import test_remaining_parity_gui as remaining

class TestRC181PaneRetirement(unittest.TestCase):
 setUpClass=classmethod(remaining.TestRemainingParity.setUpClass.__func__)
 setUp=remaining.TestRemainingParity.setUp
 tearDown=remaining.TestRemainingParity.tearDown
 new_window=remaining.TestRemainingParity.new_window
 settle=remaining.TestRemainingParity.settle
 delayed_tab=remaining.TestRemainingParity.delayed_tab
 def test_closed_native_canvas_wrapper_is_invalidated(self):
  from shiboken6 import isValid
  pane=self.window.open_new_tab(str(self.folders[1]),active=False)
  canvas=pane.table._backend.canvas
  self.assertTrue(isValid(canvas))
  self.window.close_tab(1)
  QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
  self.assertFalse(isValid(canvas),'C++ viewport was deleted but its Python wrapper remains valid')
 def test_ten_closed_loading_tabs_reject_late_commands_after_cpp_destruction(self):
  errors=[];previous=sys.excepthook
  sys.excepthook=lambda kind,value,tb:errors.append(str(value))
  try:
   for i in range(10):
    pane,worker=self.delayed_tab(True)
    if i%2==0:self.window.set_split_view(True,navigate_new=False)
    targets=list(self.window.panes);calls=[]
    for target in targets:QTimer.singleShot(0,lambda p=target:self.window.pane_command(p,lambda:calls.append(True)))
    self.window.close_tab(1)
    QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    worker.release.set();worker.wait(2000);QTest.qWait(30)
    self.assertEqual(calls,[]);self.assertEqual(errors,[])
    self.assertTrue(any(self.window.bound_pane is p for t in self.window._tabs for p in t.panes))
    self.assertFalse(getattr(self.window.bound_pane,'_closed',False))
  finally:sys.excepthook=previous

class TestQuickLookupRetirement(unittest.TestCase):
 def test_finished_lookup_does_not_restart_a_closed_pane(self):
  class Connection:
   def connect(self,fn):self.callback=fn
  class Worker:
   def __init__(self,paths,pane_id,visible,parent):
    self.found=Connection();self.finished=Connection();self.queue=NS(drain=lambda:list(paths))
   def isInterruptionRequested(self):return False
   def deleteLater(self):pass
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'media.mp4';path.write_bytes(b'x');calls=[]
   pane=NS(_closed=False)
   owner=NS(_duration_workers=[],closing=False,visible_duration_paths=lambda *a:[],start_runtime_worker=lambda *a:None,start_duration_lookup=lambda *a:calls.append(a))
   with patch('mirivue.app.DurationLookupWorker',Worker):Window.start_duration_lookup(owner,pane,[path])
   worker=owner._duration_workers[0];pane._closed=True;worker.finished.callback()
   self.assertEqual(calls,[])
if __name__=='__main__':unittest.main(verbosity=2)
