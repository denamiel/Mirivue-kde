from __future__ import annotations
from .i18n import tr
tr('System application associations, isolated behind a platform-aware menu.')
import json
import subprocess
from dataclasses import dataclass
from PySide6.QtCore import QThread, QMimeDatabase, QProcess
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox
from .platform_services import services

@dataclass(frozen=True)
class Application:
    identifier: str
    name: str
    desktop_file: str
    icon: str = tr('application-x-executable')

class ApplicationLookup(QThread):

    def __init__(self, paths):
        super().__init__()
        self.paths = paths
        self.apps = []
        self.error = ''

    def run(self):
        if services.name != tr('linux'):
            return
        try:
            database = QMimeDatabase()
            types = set()
            for path in self.paths:
                if self.isInterruptionRequested():
                    return
                types.add(database.mimeTypeForFile(str(path)).name())
            helper = services.tool_path('mirivue-kio-applications')
            if not helper:
                self.error = tr('Assistant KIO indisponible')
                return
            result = subprocess.run([helper, '--list', *sorted(types)], capture_output=True, text=True, timeout=15, check=True)
            self.apps = [Application(item['identifier'], item['name'], item['identifier'], item['icon']) for item in json.loads(result.stdout)]
        except (OSError, AttributeError, ValueError, KeyError, subprocess.SubprocessError) as error:
            self.error = str(error)

def open_default(paths):
    return all(services.open_default_file(path) for path in paths)

def open_native_chooser(window, paths):
    tr('Ask the system to choose an application where that API is available.')
    paths = tuple(paths)
    if services.name == tr('windows'):
        result = QProcess.startDetached(tr('rundll32.exe'), [tr('shell32.dll,OpenAs_RunDLL'), str(paths[0])])
        return result[0] if isinstance(result, tuple) else bool(result)
    QMessageBox.information(window, tr('Choisir une application'), tr('Utilisez « Ouvrir avec » dans Finder pour choisir une application sur macOS. Mirivue conservera ce choix comme application par défaut du système.'))
    return False

def populate_menu(window, menu, paths):
    paths = tuple(paths)
    if services.name != tr('linux'):
        default = menu.addAction(tr('Application par défaut'))
        default.triggered.connect(lambda: open_default(paths))
        chooser = menu.addAction(tr('Choisir une application…'))
        chooser.triggered.connect(lambda: open_native_chooser(window, paths))
        return
    workers = getattr(window, tr('_app_lookups'), None)
    if workers is None:
        window._app_lookups = []
        workers = window._app_lookups
    placeholder = menu.addAction(tr('Recherche des applications…'))
    placeholder.setEnabled(False)
    worker = ApplicationLookup(paths)
    workers.append(worker)
    alive = [True]
    menu.destroyed.connect(lambda: alive.__setitem__(0, False))

    def finish():
        if alive[0]:
            menu.clear()
            if worker.error or not services.tool_path('mirivue-kio-applications'):
                menu.addAction(tr('Associations du système indisponibles')).setEnabled(False)
            elif not worker.apps:
                menu.addAction(tr('Aucune application commune à la sélection')).setEnabled(False)
            else:
                for application in worker.apps:
                    action = menu.addAction(QIcon.fromTheme(application.icon), application.name)
                    action.triggered.connect(lambda checked=False, app=application: launch(window, app, paths))
        workers.remove(worker)
        worker.deleteLater()
    worker.finished.connect(finish)
    window.start_runtime_worker(worker, tr('Recherche des applications'))

def launch(window, application, paths):
    if services.name != tr('linux'):
        QMessageBox.warning(window, tr('Ouverture impossible'), tr('Cette application n’est plus disponible.'))
        return
    process = QProcess(window)
    process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)

    def failure(message):
        QMessageBox.warning(window, tr('Ouverture impossible'), message)

    def finished(code, status):
        if code:
            failure(bytes(process.readAll()).decode(tr('utf-8'), tr('replace')) or tr('L’application n’a pas pu être lancée.'))
        process.deleteLater()
    process.finished.connect(finished)
    process.errorOccurred.connect(lambda *_: failure(process.errorString()))
    helper = services.tool_path('mirivue-kio-applications')
    if not helper:
        failure(tr('Assistant KIO indisponible'))
        process.deleteLater()
        return
    process.start(helper, ['--launch', application.identifier, *map(str, paths)])


def add_native_open_with(window, menu, paths):
    """Let KIO build and execute the common Open With actions for this selection."""
    import ctypes
    import shiboken6
    from PySide6.QtCore import QUrl
    from .locations import Location
    from .native_desktop_dialogs import load
    try:
        library = load()
        insert = library.mirivue_open_with_actions
        insert.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]
        insert.restype = ctypes.c_int
        urls = [str(path) if Location.from_value(path).is_uri
                else QUrl.fromLocalFile(str(path)).toString(QUrl.ComponentFormattingOption.FullyEncoded)
                for path in paths]
        handled = bool(insert(shiboken6.getCppPointer(menu)[0], shiboken6.getCppPointer(window)[0],
                              json.dumps(urls, ensure_ascii=False).encode('utf-8')))
        if handled:
            menu._mirivue_open_with_library = library
        return handled
    except (OSError, AttributeError):
        return False
