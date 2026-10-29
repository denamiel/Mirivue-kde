"""Run genuine KDE desktop adapters on disposable XDG paths, one process per case."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path

class TestNativeDesktopDialogs(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  path=os.environ.get('MIRIVUE_TEST_PLACES_LIBRARY','')
  if not path or not Path(path).is_file():raise unittest.SkipTest('Valider builds the native desktop adapters')
 def scenario(self,name):
  with tempfile.TemporaryDirectory(prefix='mirivue-desktop-test-') as directory:
   env=dict(os.environ,QT_QPA_PLATFORM='offscreen')
   # Script execution puts helpers/, not the project root, on sys.path.
   root=str(Path(__file__).resolve().parents[1])
   env['PYTHONPATH']=root+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
   for key,part in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('XDG_STATE_HOME','state')]:
    path=Path(directory,part);path.mkdir();env[key]=str(path)
   try:
    result=subprocess.run([sys.executable,str(Path(__file__).parent/'helpers/desktop_dialog_peer.py'),name],env=env,capture_output=True,text=True,timeout=20)
   except subprocess.TimeoutExpired as error:
    def decoded(value):return value.decode(errors='replace') if isinstance(value,bytes) else value or ''
    self.fail('Desktop scenario '+name+' timed out after 20 seconds\n'+decoded(error.stdout)+'\n'+decoded(error.stderr))
   self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
   self.assertTrue(json.loads(result.stdout.splitlines()[-1])['ok'])
 def test_secondary_keys_and_disabled_keys_survive_acceptance_and_reopening(self):self.scenario('alternates')
 def test_cancel_does_not_change_mirivue_shortcuts(self):self.scenario('cancel')
 def test_kde_default_restoration_updates_only_mirivue(self):self.scenario('defaults')
 def test_native_shortcut_dialog_remains_modeless(self):self.scenario('modeless')
 def test_native_menu_and_menubar_visibility_stay_accessible(self):self.scenario('visibility')
 def test_curated_menu_avoids_visible_duplicates_and_preserves_specialised_actions(self):self.scenario('curated')
 def test_native_context_menu_keeps_access_when_the_button_is_hidden(self):self.scenario('context')
 def test_a_secondary_native_menu_button_survives_creation_and_removal(self):self.scenario('clone')
 def test_shortcut_write_failure_restores_the_original_keys(self):self.scenario('save-failure')
 def test_menu_rebuild_keeps_actions_created_by_other_menus_alive(self):self.scenario('borrowed-actions')
