"""Opening section of the actual menu; KDE applications are selected by KIO."""
import ast,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from PySide6.QtCore import QMimeDatabase,QUrl
from PySide6.QtWidgets import QApplication,QMenu,QWidget
from mirivue.i18n import tr,trf
from mirivue import open_with
ROOT=Path(__file__).resolve().parents[1]

def opening_function():
    text=(ROOT/'mirivue/app.py').read_text()
    first=text.index('    def file_context_menu(self, row):')
    last=text.index('        if executable_text and services.tool_path',first)
    block=text[first:last]+'        return menu\n'
    namespace=dict(__name__='mirivue.app',__package__='mirivue',tr=tr,trf=trf,QMenu=QMenu,Path=Path,QMimeDatabase=QMimeDatabase,
                   FileSortProxy=SimpleNamespace(media_is_incomplete=lambda row:False),
                   set_themed_action_icon=lambda *args:None,archive_protocol=lambda path:None,
                   is_executable_text_file=lambda *args:False)
    exec(compile(''.join(line[4:] if line.startswith('    ') else line for line in block.splitlines(True)),'actual-menu-opening','exec'),namespace)
    return namespace['file_context_menu']

class Owner(QWidget):
    def __init__(self,count=3,directories=False):
        super().__init__()
        self.rows=[SimpleNamespace(path=Path('/dossier')/f'film {i}.mkv',is_dir=directories,
                                  is_video=not directories,media_type='video') for i in range(count)]
        self.open_selected=Mock();self.add_context_folder_actions=Mock()
    def selected_indexes(self):return range(len(self.rows))
    def row(self,index):return self.rows[index]

class TestMultipleOpening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def menu(self,owner):return opening_function()(owner,owner.rows[0])
    def test_native_opening_replaces_the_generic_multi_file_command(self):
        owner=Owner()
        def native(window,menu,paths):
            menu.addAction('Application A');menu.addAction('Application B');menu.addMenu('Open with')
            self.assertEqual(paths,[row.path for row in owner.rows]);return True
        try:
            with patch.object(open_with,'add_native_open_with',side_effect=native,create=True) as insert:
                menu=self.menu(owner)
            insert.assert_called_once()
            self.assertEqual([a.text() for a in menu.actions()],['Application A','Application B','Open with'])
            owner.open_selected.assert_not_called()
        finally:owner.close()
    def test_kiosk_empty_native_result_does_not_restore_generic_open(self):
        owner=Owner()
        try:
            with patch.object(open_with,'add_native_open_with',return_value=True,create=True) as insert:
                menu=self.menu(owner)
            insert.assert_called_once();self.assertEqual(menu.actions(),[])
        finally:owner.close()
    def test_missing_component_keeps_the_previous_fallback(self):
        owner=Owner()
        try:
            with patch.object(open_with,'add_native_open_with',return_value=False,create=True):menu=self.menu(owner)
            self.assertEqual(len(menu.actions()),2)
            menu.actions()[0].trigger();owner.open_selected.assert_called_once()
        finally:owner.close()
    def test_single_files_and_directories_keep_their_existing_commands(self):
        for count,directories in [(1,False),(3,True)]:
            owner=Owner(count,directories)
            try:
                with patch.object(open_with,'add_native_open_with',return_value=True,create=True) as insert:menu=self.menu(owner)
                insert.assert_not_called();self.assertEqual(len(menu.actions()),2)
                self.assertIsNotNone(menu.actions()[1].menu())
            finally:owner.close()
    def test_native_bridge_receives_every_encoded_url(self):
        owner=Owner();menu=QMenu(owner);function=Mock(return_value=1)
        library=SimpleNamespace(mirivue_open_with_actions=function)
        paths=[Path('/tmp/un nom é.mkv'),Path('/tmp/a:b.mkv'),'smb://server/share/video.mkv']
        try:
            with patch('mirivue.native_desktop_dialogs.load',return_value=library):
                self.assertTrue(open_with.add_native_open_with(owner,menu,paths))
            values=json.loads(function.call_args.args[2])
            self.assertEqual(values,[QUrl.fromLocalFile(str(path)).toString(QUrl.FullyEncoded) for path in paths[:2]]+[paths[2]])
        finally:owner.close()
    def test_unavailable_native_bridge_is_reported_as_unhandled(self):
        owner=Owner();menu=QMenu(owner)
        try:
            with patch('mirivue.native_desktop_dialogs.load',side_effect=OSError('absent')):
                self.assertFalse(open_with.add_native_open_with(owner,menu,[row.path for row in owner.rows]))
        finally:owner.close()

class TestKIOOpeningReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('MIRIVUE_TEST_OPEN_WITH_REFERENCE'):
            raise unittest.SkipTest('Valider builds the independent KIO reference')
    def test_native_menu_matches_dolphins_kio_call_for_every_selection(self):
        with tempfile.TemporaryDirectory(prefix='mirivue-open-with-') as directory:
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_MENU_PREFIX='mirivue-test-')
            env['PYTHONPATH']=str(ROOT)+(os.pathsep+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
            for variable,part in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_CACHE_HOME','cache'),('XDG_STATE_HOME','state')]:
                path=Path(directory,part);path.mkdir();env[variable]=str(path)
            result=subprocess.run([sys.executable,str(ROOT/'tests/helpers/open_with_peer.py')],env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
            self.assertIn('KIO_REFERENCE_OK',result.stdout)
