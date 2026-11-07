"""Regressions C1, H1 and H2: KIO acts on exactly the item the user selected.

C1  A name ending with Unicode whitespace was trimmed by QUrl::fromUserInput()
    in the native helpers, so KIO trashed, deleted, renamed or listed another
    item ("photo " -> "photo").
H1  Sources dropped on Trash, or sent to a URI destination, were resolved with
    Path.resolve(): the symlink target was trashed or copied instead of the link.
H2  Deleting a non-local KIO row (sftp, smb, trash, desktop...) raised
    AttributeError before any KIO request.  Like Dolphin, Move to Trash is
    only offered for items with a local path; it never becomes a deletion.
C1  The same trimming affected the breadcrumb, Places captions and bookmarks.

The real window methods and the real native KIO service are used, with only the
selection and job bookkeeping replaced by a small harness.  Every operation runs
on disposable files.  HOME, XDG_* and kiorc are redirected to a temporary
directory so that Trash and KDE confirmations never involve the user's session.
Remote hosts use the reserved .invalid domain and are recorded, never contacted.
"""
import os
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMessageBox

from mirivue import app as mirivue_app
from mirivue.background_transfers import BackgroundTransfers
from mirivue.directory_listing import local_entries
from mirivue.extensions import fingerprint
from mirivue.metadata import remote_entry
from mirivue.movement import MovementMixin, kio_source_url
from mirivue.platform_services import services
from mirivue.transfers import TransferMixin

TRANSFER_DEADLINE = 60
ISOLATED_VARIABLES = ('HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME')


class Harness:
    """Real file-management methods bound to a minimal window."""
    delete_selected = mirivue_app.Window.delete_selected
    confirm_delete = mirivue_app.Window.confirm_delete
    rename_inline = mirivue_app.Window.rename_inline
    refresh_delete_availability = mirivue_app.Window.refresh_delete_availability
    is_trash_view = mirivue_app.Window.is_trash_view
    delete_selected_from_trash = mirivue_app.Window.delete_selected_from_trash
    selected_entries = MovementMixin.selected_entries
    choose_associated_entries = MovementMixin.choose_associated_entries
    associated_entries = MovementMixin.associated_entries
    movement_locked = MovementMixin.movement_locked
    drop_operation = MovementMixin.drop_operation
    move_entries = MovementMixin.move_entries
    allow_place_drop = MovementMixin.allow_place_drop
    drop_choices = TransferMixin.drop_choices
    transfers_locked = BackgroundTransfers.transfers_locked
    pending_transfers = BackgroundTransfers.pending_transfers
    selection_supports_trash = staticmethod(mirivue_app.Window.selection_supports_trash)
    add_place = mirivue_app.Window.add_place

    def __init__(self, rows=(), folder='', record_only=False):
        self.rows = list(rows)
        self.folder = folder
        self.record_only = record_only
        self.model = types.SimpleNamespace(rows=self.rows)
        self.scanning = False
        self.move_worker = None
        self.active_job = None
        self.job_queue = []
        self.transfer_history = []
        self.requests = []
        self.delete_button = QAction()
        self.permanent_delete_action = QAction()
        self.bound_pane = types.SimpleNamespace(_closed=False)
        self.messages = []
        self.deadline = TRANSFER_DEADLINE

    def is_archive_view(self): return False
    def selected_indexes(self): return list(range(len(self.rows)))
    def row(self, index): return self.rows[index]
    def paths_locked(self, _paths): return False
    def reload_places(self): pass
    def update_renamed_rows(self, *_args, **_kwargs): pass
    def show_activity_message(self, message, *_args): self.messages.append(message)

    def start_kio_transfer(self, sources, destination, move=False, clipboard_guard=None,
                           operation=None, on_success=None, before_refresh=None):
        # Same call as KioTransferWorker.run(), bounded so a test never hangs.
        operation = operation or ('move' if move else 'copy')
        request = {'sources': list(sources), 'destination': str(destination), 'operation': operation}
        if self.record_only:
            request['ok'], request['error'] = None, 'recorded only'
        else:
            deadline = time.monotonic() + self.deadline
            request['ok'], request['error'] = services.transfer_kio(
                list(sources), str(destination), move, None,
                lambda: time.monotonic() > deadline, operation=operation)
        self.requests.append(request)
        return object()


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def local_row(path):
    path = Path(path)
    return types.SimpleNamespace(path=path, is_dir=path.is_dir(), file_signature=fingerprint(path))


def state(path):
    if path.is_symlink():
        return 'link->' + os.readlink(path)
    if path.is_dir():
        return 'directory'
    return path.read_text() if path.is_file() else 'ABSENT'


class IsolatedKioTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['Mirivue-C1-H1-H2'])
        if not services.tool_path('mirivue-kio-service'):
            raise unittest.SkipTest('Compiled mirivue-kio-service required')
        # A service started earlier in this process inherited the real session.
        services.shutdown_kio_service()
        cls._session = tempfile.TemporaryDirectory(prefix='mirivue-c1h1h2-')
        root = Path(cls._session.name)
        cls._saved_environment = {name: os.environ.get(name) for name in ISOLATED_VARIABLES}
        for name, folder in zip(ISOLATED_VARIABLES, ('home', 'data', 'config', 'cache', 'state')):
            (root / folder).mkdir()
            os.environ[name] = str(root / folder)
        (root / 'config' / 'kiorc').write_text(
            '[Confirmations]\nConfirmTrash=false\nConfirmDelete=false\nConfirmEmptyTrash=false\n')
        cls.trash = root / 'data' / 'Trash'
        cls.work = root / 'work'
        cls.work.mkdir()

    @classmethod
    def tearDownClass(cls):
        services.shutdown_kio_service()
        for name, value in cls._saved_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        cls._session.cleanup()

    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix=self._testMethodName[:40] + '-', dir=self.work))
        self._trash_before = set(self._trash_entries())
        # An unexpected modal dialog must fail the test instead of freezing it.
        for name in ('warning', 'information', 'question', 'critical'):
            patcher = patch.object(QMessageBox, name, side_effect=AssertionError(f'unexpected QMessageBox.{name}'))
            patcher.start()
            self.addCleanup(patcher.stop)

    def _trash_entries(self):
        info = self.trash / 'info'
        if not info.is_dir():
            return []
        return [unquote(line.split('=', 1)[1]) for entry in sorted(info.glob('*.trashinfo'))
                for line in entry.read_text().splitlines() if line.startswith('Path=')]

    def trashed(self):
        """Entries added to the isolated Trash during this test."""
        return [entry for entry in self._trash_entries() if entry not in self._trash_before]


class TestC1WhitespaceIsPreserved(IsolatedKioTestCase):
    def deletion(self, name, mode):
        target, other = write(self.directory / name, 'TARGET'), write(self.directory / 'photo', 'OTHER')
        harness = Harness([local_row(target)], str(self.directory))
        harness.delete_selected(mode)
        request = harness.requests[-1]
        self.assertTrue(request['ok'], request)
        self.assertEqual(state(other), 'OTHER', 'another item was affected')
        self.assertEqual(state(target), 'ABSENT')
        return harness

    def test_control_trash_without_trailing_whitespace(self):
        target, other = write(self.directory / 'photo', 'TARGET'), write(self.directory / 'photo2', 'OTHER')
        Harness([local_row(target)], str(self.directory)).delete_selected('trash')
        self.assertEqual((state(target), state(other)), ('ABSENT', 'OTHER'))
        self.assertEqual(self.trashed(), [str(target)])

    def test_trash_name_with_trailing_space(self):
        self.deletion('photo ', 'trash')
        self.assertEqual(self.trashed(), [str(self.directory / 'photo ')])

    def test_permanent_deletion_name_with_trailing_space(self):
        self.deletion('photo ', 'permanent')
        self.assertEqual(self.trashed(), [])

    def test_trash_name_with_trailing_no_break_space(self):
        self.deletion('photo ', 'trash')

    def test_trash_name_with_trailing_ideographic_space(self):
        self.deletion('photo　', 'trash')

    def test_trash_name_with_trailing_space_without_homonym(self):
        target = write(self.directory / 'photo ', 'TARGET')
        harness = Harness([local_row(target)], str(self.directory))
        harness.delete_selected('trash')
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertEqual(state(target), 'ABSENT')

    def test_inline_rename_of_name_with_trailing_space(self):
        target, other = write(self.directory / 'photo ', 'TARGET'), write(self.directory / 'photo', 'OTHER')
        harness = Harness([local_row(target)], str(self.directory))
        harness.rename_inline(target, 'renamed')
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertEqual(state(self.directory / 'renamed'), 'TARGET')
        self.assertEqual((state(target), state(other)), ('ABSENT', 'OTHER'))

    def test_copy_into_destination_with_trailing_space(self):
        source = write(self.directory / 'source.txt', 'SOURCE')
        (self.directory / 'Folder ').mkdir()
        (self.directory / 'Folder').mkdir()
        harness = Harness([local_row(source)], str(self.directory))
        harness.move_entries([source], self.directory / 'Folder ', confirmed=True, copy_only=True)
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertEqual(os.listdir(self.directory / 'Folder '), ['source.txt'])
        self.assertEqual(os.listdir(self.directory / 'Folder'), [])

    def test_inventory_of_folder_with_trailing_space(self):
        write(self.directory / 'Folder ' / 'expected.txt', '1')
        write(self.directory / 'Folder' / 'intruder.txt', '2')
        listed = sorted(str(path.relative_to(self.directory))
                        for path, _is_dir, _hidden in local_entries(self.directory / 'Folder '))
        self.assertEqual(listed, ['Folder /expected.txt'])

    def test_fallback_transfer_helper_keeps_trailing_space(self):
        import subprocess
        tool = services.tool_path('mirivue-kio-transfer')
        if not tool:
            self.skipTest('Compiled mirivue-kio-transfer required')
        write(self.directory / 'photo ', 'TARGET')
        write(self.directory / 'photo', 'OTHER')
        (self.directory / 'destination').mkdir()
        result = subprocess.run([tool, 'copy', QUrl.fromLocalFile(str(self.directory / 'photo ')).toString(),
                                 QUrl.fromLocalFile(str(self.directory / 'destination')).toString()],
                                capture_output=True, text=True, timeout=TRANSFER_DEADLINE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        copied = {name: (self.directory / 'destination' / name).read_text()
                  for name in os.listdir(self.directory / 'destination')}
        self.assertEqual(copied, {'photo ': 'TARGET'})

    SPECIAL_NAMES = ('a#b', 'x%41', 'q?r', 'middle space', 'été', 'two  spaces', '[brackets]', 'tab\tname', ' leading')

    def test_copy_of_special_names_is_unchanged(self):
        (self.directory / 'source').mkdir()
        (self.directory / 'destination').mkdir()
        sources = [write(self.directory / 'source' / name, name) for name in self.SPECIAL_NAMES]
        harness = Harness([local_row(path) for path in sources], str(self.directory / 'source'))
        harness.move_entries(sources, self.directory / 'destination', confirmed=True, copy_only=True)
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        copied = {name: (self.directory / 'destination' / name).read_text()
                  for name in os.listdir(self.directory / 'destination')}
        self.assertEqual(copied, {name: name for name in self.SPECIAL_NAMES})

    def test_inventory_of_special_names_is_unchanged(self):
        folder = self.directory / 'F#older %41'
        for name in self.SPECIAL_NAMES:
            write(folder / name, name)
        listed = sorted(path.name for path, _is_dir, _hidden in local_entries(folder))
        self.assertEqual(listed, sorted(self.SPECIAL_NAMES))


class TestH1SymlinkSourcesAreNotResolved(IsolatedKioTestCase):
    def file_link(self):
        target = write(self.directory / 'target.txt', 'TARGET')
        link = self.directory / 'link.txt'
        link.symlink_to('target.txt')
        return target, link

    def directory_link(self):
        write(self.directory / 'Photos' / 'a.jpg', 'A')
        write(self.directory / 'Photos' / 'b.jpg', 'B')
        link = self.directory / 'Shortcut'
        link.symlink_to('Photos')
        return self.directory / 'Photos', link

    def drop_on_trash(self, target, link):
        harness = Harness([], str(self.directory))
        harness.drop_choices([link], 'trash:/')      # pane drop on a Trash view
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertNotEqual(state(target), 'ABSENT', 'the symlink target was trashed')
        self.assertFalse(link.is_symlink() or link.exists())
        self.assertEqual(self.trashed(), [str(link)])

    def test_control_delete_key_on_symlink_trashes_the_link(self):
        target, link = self.file_link()
        Harness([types.SimpleNamespace(path=link, is_dir=False)], str(self.directory)).delete_selected('trash')
        self.assertEqual((state(target), state(link)), ('TARGET', 'ABSENT'))

    def test_drop_file_symlink_on_trash(self):
        self.drop_on_trash(*self.file_link())

    def test_drop_directory_symlink_on_trash(self):
        self.drop_on_trash(*self.directory_link())

    def test_drop_dangling_symlink_on_trash(self):
        link = self.directory / 'dangling'
        link.symlink_to('missing-target')
        harness = Harness([], str(self.directory))
        harness.drop_choices([link], 'trash:/')
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertFalse(link.is_symlink())
        self.assertEqual(self.trashed(), [str(link)])

    def test_copy_symlink_to_uri_destination_copies_the_link(self):
        # A file:// destination string takes move_entries' URI branch, using
        # only workers shipped with KIO core (no Plasma desktop:/ worker).
        target, link = self.file_link()
        inside = self.directory / 'inside'
        inside.mkdir()
        harness = Harness([], str(self.directory))
        harness.move_entries([link], QUrl.fromLocalFile(str(inside)).toString(), confirmed=True, copy_only=True)
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertEqual(harness.requests[-1]['sources'], [QUrl.fromLocalFile(str(link)).toString()])
        self.assertTrue((inside / 'link.txt').is_symlink())
        self.assertFalse((inside / 'target.txt').exists())
        self.assertEqual(state(target), 'TARGET')

    def test_drop_move_of_symlink_moves_the_link_only(self):
        target, link = self.file_link()
        (self.directory / 'inside').mkdir()
        harness = Harness([], str(self.directory))
        harness.drop_operation([link], self.directory / 'inside', 'move')
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertEqual(state(self.directory / 'inside' / 'link.txt'), 'link->target.txt')
        self.assertEqual((state(target), state(link)), ('TARGET', 'ABSENT'))

    def test_drop_copy_of_symlink_copies_the_link_only(self):
        target, link = self.file_link()
        (self.directory / 'inside').mkdir()
        harness = Harness([], str(self.directory))
        harness.drop_operation([link], self.directory / 'inside', 'copy')
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertTrue((self.directory / 'inside' / 'link.txt').is_symlink())
        self.assertEqual((state(target), state(link)), ('TARGET', 'link->target.txt'))

    def test_drop_link_of_symlink_points_to_the_link(self):
        target, link = self.file_link()
        (self.directory / 'inside').mkdir()
        harness = Harness([], str(self.directory))
        harness.drop_operation([link], self.directory / 'inside', 'link')
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertEqual(os.readlink(self.directory / 'inside' / 'link.txt'), str(link))
        self.assertEqual(state(target), 'TARGET')

    def test_source_url_keeps_symlink_and_uri_values(self):
        _target, link = self.file_link()
        self.assertEqual(kio_source_url(link), QUrl.fromLocalFile(str(link)).toString())
        self.assertEqual(kio_source_url('sftp://example.invalid/a b'), 'sftp://example.invalid/a b')


class TestH2RemoteRowsCanBeDeleted(IsolatedKioTestCase):
    def remote(self, uri, folder, mode='trash'):
        harness = Harness([remote_entry(uri, uri.rsplit('/', 1)[-1])], folder, record_only=True)
        harness.refresh_delete_availability()
        harness.delete_selected(mode)                 # must not raise AttributeError
        return harness

    def test_trash_of_sftp_row_is_refused_without_any_request(self):
        # KIO::trash() rejects remote URLs; like Dolphin, Move to Trash is
        # unavailable and is never turned into a permanent deletion.
        harness = self.remote('sftp://example.invalid/share/file.txt', 'sftp://example.invalid/share')
        self.assertFalse(harness.delete_button.isEnabled())
        self.assertTrue(harness.permanent_delete_action.isEnabled())
        self.assertEqual(harness.requests, [])
        self.assertEqual(len(harness.messages), 1)

    def test_trash_of_kio_row_with_local_path_sends_the_unchanged_url(self):
        uri = 'desktop:/file.txt'
        row = remote_entry(uri, 'file.txt', local_path=str(self.directory / 'file.txt'))
        harness = Harness([row], 'desktop:/', record_only=True)
        harness.refresh_delete_availability()
        self.assertTrue(harness.delete_button.isEnabled())
        harness.delete_selected('trash')
        self.assertEqual([(r['sources'], r['operation']) for r in harness.requests], [([uri], 'trash')])

    def test_trash_support_follows_local_paths(self):
        supports = mirivue_app.Window.selection_supports_trash
        self.assertTrue(supports([types.SimpleNamespace(path=self.directory / 'a')]))
        self.assertTrue(supports([remote_entry('desktop:/a', 'a', local_path='/tmp/a')]))
        self.assertFalse(supports([remote_entry('smb://example.invalid/s/a', 'a')]))
        self.assertFalse(supports([types.SimpleNamespace(path=self.directory / 'a'),
                                   remote_entry('sftp://example.invalid/a', 'a')]))

    def test_permanent_deletion_of_smb_row_sends_the_unchanged_url(self):
        uri = 'smb://example.invalid/share/file.txt'
        harness = self.remote(uri, 'smb://example.invalid/share', 'permanent')
        self.assertEqual([(r['sources'], r['operation']) for r in harness.requests], [([uri], 'delete')])

    def test_delete_key_in_trash_view_does_nothing_and_is_disabled(self):
        harness = self.remote('trash:/0-file.txt', 'trash:/')
        self.assertEqual(harness.requests, [])
        self.assertFalse(harness.delete_button.isEnabled())
        self.assertTrue(harness.permanent_delete_action.isEnabled())

    def test_shift_delete_in_trash_view_deletes_permanently(self):
        harness = self.remote('trash:/0-file.txt', 'trash:/', 'permanent')
        self.assertEqual([(r['sources'], r['operation']) for r in harness.requests],
                         [(['trash:/0-file.txt'], 'delete')])

    def test_permanent_deletion_of_trash_row_end_to_end(self):
        # Real non-file KIO row, provided by KIO core's trash worker.
        name = f'to-delete-{self.directory.name}.txt'
        victim = write(self.directory / name, 'X')
        ok, error = services._kio_service_request('trash', sources=[victim.as_uri()], timeout=TRANSFER_DEADLINE)
        self.assertTrue(ok, error)
        trashed = self.trash / 'files' / name
        self.assertTrue(trashed.exists(), 'the isolated Trash was not used')
        harness = Harness([remote_entry('trash:/0-' + name, name)], 'trash:/')
        harness.delete_selected('permanent')
        self.assertTrue(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertEqual(harness.requests[-1]['operation'], 'delete')
        self.assertFalse(trashed.exists())
        self.assertFalse((self.trash / 'info' / (name + '.trashinfo')).exists())


class TestPlacesAndNavigationKeepTrailingSpaces(IsolatedKioTestCase):
    """Absolute folder paths reach the Places and breadcrumb widgets untrimmed."""

    def setUp(self):
        super().setUp()
        (self.directory / 'Folder').mkdir()
        (self.directory / 'Folder ').mkdir()
        self.places_file = Path(os.environ['XDG_DATA_HOME']) / 'user-places.xbel'
        self.places_file.write_text('<xbel><bookmark href="' + (self.directory / 'Folder').as_uri() + '">'
                                    '<title>Bookmark without space</title></bookmark></xbel>')
        self.addCleanup(self.places_file.unlink, missing_ok=True)

    def test_places_identity_and_breadcrumb_use_the_folder_with_trailing_space(self):
        import json
        import subprocess
        import sys
        library = services.tool_path('libmirivue-kio-places-widget.so')
        if not library:
            self.skipTest('Compiled libmirivue-kio-places-widget.so required')
        script = """import ctypes, json, sys
import shiboken6
from PySide6.QtWidgets import QApplication, QWidget, QAbstractButton, QVBoxLayout
app = QApplication(['Mirivue-navigation-test'])
library = ctypes.CDLL(sys.argv[1]); location = sys.argv[2].encode()
parent = QWidget()
parent.resize(1600, 80)
library.mirivue_places_create.argtypes = [ctypes.c_void_p] * 10 + [ctypes.c_char_p]
library.mirivue_places_create.restype = ctypes.c_void_p
places = library.mirivue_places_create(shiboken6.getCppPointer(parent)[0], *([None] * 9), b'Split')
library.mirivue_places_location_identity.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
library.mirivue_places_location_identity.restype = ctypes.c_char_p
callback = ctypes.CFUNCTYPE(None, ctypes.c_char_p)
callbacks = [callback(lambda raw: None) for _ in range(6)]
library.mirivue_navigator_create.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p] + [callback] * 6
library.mirivue_navigator_create.restype = ctypes.c_void_p
navigator = library.mirivue_navigator_create(shiboken6.getCppPointer(parent)[0], places, b'/', *callbacks)
widget = shiboken6.wrapInstance(navigator, QWidget)
QVBoxLayout(parent).addWidget(widget)
library.mirivue_navigator_set_url.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
library.mirivue_navigator_set_url(navigator, location)
parent.show()                   # breadcrumb buttons exist once laid out
for _ in range(10):
    app.processEvents()
buttons = []
for button in widget.findChildren(QAbstractButton):
    try:
        if button.metaObject().className() == 'KDEPrivate::KUrlNavigatorButton' and button.isVisible():
            buttons.append(button.text())
    except RuntimeError:        # breadcrumb buttons are rebuilt asynchronously
        pass
print(json.dumps({'identity': json.loads(library.mirivue_places_location_identity(places, location)),
                  'last_button': buttons[-1] if buttons else None}))
"""
        result = subprocess.run([sys.executable, '-B', '-c', script, library, str(self.directory / 'Folder ')],
                                capture_output=True, text=True, timeout=TRANSFER_DEADLINE)
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(observed['identity']['name'], 'Folder ')
        self.assertEqual(observed['last_button'], 'Folder ')

    def test_add_place_keeps_the_trailing_space(self):
        harness = Harness([], str(self.directory))
        harness.reload_places = lambda: None
        with patch.object(services, 'change_place', return_value=(True, '')) as change_place:
            self.assertTrue(harness.add_place(self.directory / 'Folder '))
        operation, _label, url, _icon = change_place.call_args.args
        self.assertEqual(operation, 'add')
        self.assertEqual(QUrl(url).toLocalFile(), str(self.directory / 'Folder '))

    def test_places_helper_adds_the_folder_with_trailing_space(self):
        import json
        import subprocess
        helper = services.tool_path('mirivue-kio-places')
        if not helper:
            self.skipTest('Compiled mirivue-kio-places required')
        target = self.directory / 'Folder '
        added = subprocess.run([helper, 'add', 'With space', str(target), 'folder'],
                               capture_output=True, text=True, timeout=TRANSFER_DEADLINE)
        self.assertEqual(added.returncode, 0, added.stdout + added.stderr)
        listed = subprocess.run([helper, 'list'], capture_output=True, text=True, timeout=TRANSFER_DEADLINE)
        places = {QUrl(place['url']).toLocalFile(): place for place in json.loads(listed.stdout)['places']
                  if QUrl(place['url']).isLocalFile()}
        self.assertIn(str(target), places)
        self.assertEqual(places[str(self.directory / 'Folder')]['name'], 'Bookmark without space')

    def test_inventory_of_absolute_path_with_trailing_space(self):
        import json
        import subprocess
        tool = services.tool_path('mirivue-kio-list')
        write(self.directory / 'Folder ' / 'expected.txt', '1')
        write(self.directory / 'Folder' / 'intruder.txt', '2')
        result = subprocess.run([tool, str(self.directory / 'Folder ')], capture_output=True, text=True,
                                timeout=TRANSFER_DEADLINE)
        self.assertEqual(result.returncode, 0, result.stderr)
        names = sorted(entry['name'] for entry in json.loads(result.stdout.splitlines()[-1])['entries'])
        self.assertEqual(names, ['expected.txt'])


class TestKdeConfirmationsAreRespected(IsolatedKioTestCase):
    """With KDE confirmations enabled, nothing is removed without an answer."""

    def confirmations(self, trash, delete):
        kiorc = Path(os.environ['XDG_CONFIG_HOME']) / 'kiorc'
        previous = kiorc.read_text()
        services.shutdown_kio_service()
        kiorc.write_text(f'[Confirmations]\nConfirmTrash={str(trash).lower()}\nConfirmDelete={str(delete).lower()}\n')
        self.addCleanup(services.shutdown_kio_service)
        self.addCleanup(kiorc.write_text, previous)

    def unanswered(self, mode):
        target = write(self.directory / 'keep.txt', 'KEEP')
        harness = Harness([local_row(target)], str(self.directory))
        harness.deadline = 4          # nobody answers the native dialog
        harness.delete_selected(mode)
        self.assertFalse(harness.requests[-1]['ok'], harness.requests[-1])
        self.assertEqual(state(target), 'KEEP')
        self.assertEqual(self.trashed(), [])

    def test_unanswered_permanent_deletion_keeps_the_file(self):
        self.confirmations(trash=False, delete=True)
        self.unanswered('permanent')

    def test_unanswered_trash_confirmation_keeps_the_file(self):
        self.confirmations(trash=True, delete=True)
        self.unanswered('trash')


class TestNativeHelpersRejectIncompleteUrls(IsolatedKioTestCase):
    def request(self, command, sources=(), destination=''):
        return services._kio_service_request(command, sources=sources, destination=destination, timeout=15)

    def test_service_rejects_a_bare_path_source(self):
        source = write(self.directory / 'file', 'KEEP')
        ok, error = self.request('trash', [str(source)])
        self.assertFalse(ok)
        self.assertIn('invalide', error)
        self.assertEqual(state(source), 'KEEP')

    def test_service_rejects_a_mixed_selection_entirely(self):
        first, second = write(self.directory / 'first', '1'), write(self.directory / 'second', '2')
        ok, error = self.request('trash', [first.as_uri(), str(second)])
        self.assertFalse(ok)
        self.assertIn('invalide', error)
        self.assertEqual((state(first), state(second)), ('1', '2'))
        self.assertEqual(self.trashed(), [])

    def test_service_rejects_a_malformed_url(self):
        source = write(self.directory / 'file', 'KEEP')
        ok, _error = self.request('trash', [source.as_uri(), 'file://[broken'])
        self.assertFalse(ok)
        self.assertEqual(state(source), 'KEEP')

    def test_service_rejects_a_bare_path_destination(self):
        source = write(self.directory / 'file', 'KEEP')
        (self.directory / 'destination').mkdir()
        ok, error = self.request('copy', [source.as_uri()], str(self.directory / 'destination'))
        self.assertFalse(ok)
        self.assertIn('invalide', error)
        self.assertEqual(os.listdir(self.directory / 'destination'), [])

    def test_service_rejects_a_bare_path_for_folder_creation(self):
        ok, _error = self.request('mkdir', destination=str(self.directory / 'new'))
        self.assertFalse(ok)
        self.assertFalse((self.directory / 'new').exists())

    def test_service_error_is_a_complete_message(self):
        missing = self.directory / 'missing.txt'
        (self.directory / 'destination').mkdir()
        ok, error = self.request('copy', [missing.as_uri()], (self.directory / 'destination').as_uri())
        self.assertFalse(ok)
        self.assertIn(str(missing), error)
        self.assertNotEqual(error.strip(), str(missing), 'a bare path is not an explicit error')
        self.assertNotEqual(error.strip(), missing.as_uri(), 'a bare URL is not an explicit error')

    def test_fallback_helper_rejects_bare_paths(self):
        import json
        import subprocess
        tool = services.tool_path('mirivue-kio-transfer')
        if not tool:
            self.skipTest('Compiled mirivue-kio-transfer required')
        source = write(self.directory / 'file', 'KEEP')
        (self.directory / 'destination').mkdir()
        for arguments in ([str(source), (self.directory / 'destination').as_uri()],
                          [source.as_uri(), str(self.directory / 'destination')],
                          [source.as_uri(), str(source), (self.directory / 'destination').as_uri()]):
            with self.subTest(arguments=arguments):
                result = subprocess.run([tool, 'copy', *arguments], capture_output=True, text=True,
                                        timeout=TRANSFER_DEADLINE)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse(json.loads(result.stdout.splitlines()[-1])['ok'])
                self.assertEqual(os.listdir(self.directory / 'destination'), [])
        self.assertEqual(state(source), 'KEEP')


if __name__ == '__main__':
    unittest.main()
