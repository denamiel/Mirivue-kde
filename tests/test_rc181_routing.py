"""Async routing deadlines/receipts; all transports and folders disposable."""
import json,time,unittest
from PySide6.QtCore import QTimer,QEventLoop
from PySide6.QtWidgets import QApplication
from mirivue.launch_targets import LaunchRequest
from mirivue import window_instances as wi

class TestAsyncRouting(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
 def run_job(self,scenario,count=2,budget=100):
  requests=[LaunchRequest('smb://audit/share/'+str(i)) for i in range(count)]
  names=[wi.PREFIX+str(i) for i in range(count)]
  class FakeBus:
   def isConnected(self):return True
  class Job(wi.WindowRoute):
   def call(self,name,method,arguments,callback,**kw):
    i=names.index(name) if name in names else -1
    if method=='ListNames':value,error=names,''
    elif scenario=='blocked' and i%2==0:return
    elif method=='Locations':value,error=json.dumps([requests[i].folder]),''
    elif method=='Active':value,error=i==0,''
    elif method=='Dispatch':
     if scenario=='partial' and i==1:value,error=None,'org.freedesktop.DBus.Error.ServiceUnknown'
     elif scenario=='uncertain' and i==1:
      QTimer.singleShot(0,self,self.expire)
      return
     else:value,error=True,''
    # Immediate fake replies isolate delivery bookkeeping from unrelated GUI
    # paints. The blocked-peer test separately measures the real Qt deadline.
    if not self.done:callback(value,error)
  # Finish paints/deferred work left by earlier GUI tests before measuring
  # this transport. The measured budget and heartbeat assertions are unchanged.
  from PySide6.QtTest import QTest
  QTest.qWait(50)
  job=Job(requests,bus=FakeBus(),budget_ms=budget);loop=QEventLoop();results=[];beats=[]
  beat=QTimer();beat.setInterval(2);beat.timeout.connect(lambda:beats.append(time.monotonic()));beat.start()
  job.finished.connect(lambda r:(results.append(r),loop.quit()))
  started=time.monotonic();QTimer.singleShot(0,job,job.start);loop.exec();elapsed=time.monotonic()-started;beat.stop()
  job.deleteLater();return results[0],elapsed,beats,requests
 def test_twenty_blocked_peers_keep_qt_running_and_respect_global_budget(self):
  result,elapsed,beats,requests=self.run_job('blocked',20)
  self.assertLess(elapsed,.6);self.assertGreater(len(beats),5);self.assertEqual(result.remaining,requests)
 def test_partial_delivery_retries_only_definitely_undelivered(self):
  result,_,_,requests=self.run_job('partial')
  self.assertEqual(result.delivered,[requests[0]]);self.assertEqual(result.remaining,[requests[1]]);self.assertEqual(result.uncertain,[])
 def test_lost_dispatch_reply_is_never_retransmitted(self):
  result,_,_,requests=self.run_job('uncertain')
  self.assertEqual(result.delivered,[requests[0]]);self.assertEqual(result.uncertain,[requests[1]]);self.assertEqual(result.remaining,[])
 def test_async_receive_rejects_raw_invalid_payload_without_opening(self):
  from mirivue.external_locations import ExternalLocationsMixin
  from types import SimpleNamespace
  calls=[];owner=SimpleNamespace(open_external_locations=lambda *a,**kw:calls.append(a))
  ExternalLocationsMixin.receive_launch_payload(owner,{'locations':None})
  self.assertEqual(calls,[])
 def test_startup_flushes_its_completed_job_before_returning(self):
  from unittest.mock import patch
  from shiboken6 import isValid
  jobs=[]
  class Immediate(wi.WindowRoute):
   def start(self):
    jobs.append(self);self.consume(self.requests);self.finish()
  with patch.object(wi,'WindowRoute',Immediate):
   self.assertTrue(wi.route_to_windows([LaunchRequest('/tmp')]))
  self.assertFalse(isValid(jobs[0]))
if __name__=='__main__':unittest.main(verbosity=2)
