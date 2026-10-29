from .i18n import tr, trf
tr('Clipboard, duplicate and drop actions; all writes use the checked transfer worker.')
import os
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt, QMimeData, QUrl, QPoint
from PySide6.QtGui import QPixmap, QImage, QPainter, QPalette, QCursor, QIcon, QAction
from PySide6.QtWidgets import QApplication, QMenu, QLineEdit, QMessageBox, QInputDialog
from .file_moves import normalize_sources, exists
from .platform_services import services
from .locations import Location
from .iconography import set_themed_action_icon
from .context_menu_settings import mark_entry
from .paste_behavior import paste_action_label, local_clipboard_kind

class TransferMixin:

    def init_transfers(self, file_menu):
        self.transfer_actions = {}
        for title, icon, shortcut, callback in [(tr('Couper'), tr('edit-cut'), tr('Ctrl+X'), lambda: self.copy_selection(True)), (tr('Copier'), tr('edit-copy'), tr('Ctrl+C'), lambda: self.copy_selection(False)), (tr('Coller'), tr('edit-paste'), tr('Ctrl+V'), self.paste_selection), (tr('Dupliquer'), tr('edit-copy'), tr('Ctrl+D'), self.duplicate_selection)]:
            action = file_menu.addAction(title, callback)
            self.transfer_actions[title] = action
            set_themed_action_icon(action, icon)
            action.setShortcut(services.shortcut(shortcut))
            self.addAction(action)
            if title == tr('Coller'):
                self.paste_action = action
        file_menu.aboutToShow.connect(self.update_paste_action)
        QApplication.clipboard().dataChanged.connect(self.update_paste_action)
        self.update_paste_action()
        file_menu.addSeparator()
        self.kio_undo_action = file_menu.addAction(tr('Annuler'), self.undo_remote_transfer)
        set_themed_action_icon(self.kio_undo_action, tr('edit-undo'))
        self.kio_undo_action.setShortcut(services.shortcut(tr('Ctrl+Z')))
        self.kio_undo_action.setEnabled(services._kio_undo_available)
        services.kio_events.undo_state_changed.connect(self.update_kio_undo_action)
        self.kio_redo_action = file_menu.addAction(tr('Rétablir'), self.redo_kio_operation)
        set_themed_action_icon(self.kio_redo_action, tr('edit-redo'))
        self.kio_redo_action.setShortcut(services.shortcut(tr('Ctrl+Shift+Z')))
        self.kio_redo_action.setEnabled(services._kio_redo_available)
        services.kio_events.redo_state_changed.connect(self.update_kio_redo_action)

    def decorate_drag(self, drag, paths):
        pix = QPixmap(220, 60)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        color = palette.color(QPalette.ColorRole.Base)
        color.setAlpha(225)
        painter.setBrush(color)
        painter.setPen(palette.color(QPalette.ColorRole.Highlight))
        painter.drawRoundedRect(1, 1, 218, 58, 6, 6)
        row = next((r for r in self.model.rows if r.path == paths[0]), None)
        icon = self.model.thumbnails.get(paths[0]) if row and self.model.show_thumbnails else None
        icon = icon or QIcon.fromTheme(tr('folder') if paths[0].is_dir() else tr('video-x-generic'), self.windowIcon())
        icon.paint(painter, 8, 10, 40, 40)
        text = paths[0].name if len(paths) == 1 else trf('\x1f0\x1f éléments', len(paths))
        painter.setPen(palette.color(QPalette.ColorRole.Text))
        painter.drawText(56, 0, 155, 60, Qt.AlignmentFlag.AlignVCenter, self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideMiddle, 150))
        painter.end()
        drag.setPixmap(pix)
        drag.setHotSpot(QPoint(20, 30))

    def drop_choices(self, paths, destination, operation=None, place_metadata=None):
        place_metadata = place_metadata if isinstance(place_metadata, dict) else {}
        if place_metadata.get('setupNeeded'):
            self.show_activity_message(tr('Préparation du périphérique…'))

            def mounted(ok, error):
                self.reload_places()
                if not ok:
                    QMessageBox.warning(self, tr('Périphérique indisponible'), error or tr('Impossible de préparer ce périphérique.'))
                    return
                self.drop_choices(paths, destination, operation, {})

            if not services.setup_place(str(destination), mounted):
                QMessageBox.warning(self, tr('Périphérique indisponible'), tr('Impossible de préparer ce périphérique.'))
            return
        if str(destination) == tr('trash:/'):
            self.drop_operation(paths, destination, tr('trash'))
            return
        if operation in (tr('move'), tr('copy'), tr('link')):
            self.drop_operation(paths, destination, operation)
            return
        menu = QMenu(self)
        move = menu.addAction(tr('Déplacer ici') + tr('\tMaj'))
        set_themed_action_icon(move, tr('edit-move'))
        copy = menu.addAction(tr('Copier ici') + tr('\tCtrl'))
        set_themed_action_icon(copy, tr('edit-copy'))
        link = menu.addAction(tr('Créer un lien ici') + tr('\tCtrl+Maj'))
        set_themed_action_icon(link, tr('insert-link'))
        menu.addSeparator()
        cancel = menu.addAction(tr('Annuler') + tr('\tÉchap'))
        selected = menu.exec(QCursor.pos())
        if selected is move:
            self.drop_operation(paths, destination, tr('move'))
        elif selected is copy:
            self.drop_operation(paths, destination, tr('copy'))
        elif selected is link:
            self.drop_operation(paths, destination, tr('link'))

    def copy_selection(self, cut=False):
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            focus.cut() if cut else focus.copy()
            return
        paths = self.selected_entries()
        if not paths:
            return
        paths = self.choose_associated_entries(paths, tr('copie') if not cut else tr('déplacement'))
        if paths is None:
            return
        mime = QMimeData()
        mime.setUrls([QUrl(str(p)) if Location.from_value(p).is_uri
                      else QUrl.fromLocalFile(str(p)) for p in paths])
        mime.setData(tr('application/x-kde-cutselection'), b'1' if cut else b'0')
        mime.setData(tr('x-special/gnome-copied-files'), ((tr('cut') if cut else tr('copy')) + tr('\n') + tr('\n').join((u.toString() for u in mime.urls()))).encode())
        QApplication.clipboard().setMimeData(mime)
        self.show_activity_message(trf('\x1f0\x1f élément(s) prêt(s) à ', len(paths)) + (tr('déplacer.') if cut else tr('copier.')), 5000)

    def clipboard_paste_info(self):
        """Return clipboard URLs, a Dolphin-style label and transfer kind."""
        mime = QApplication.clipboard().mimeData()
        if not mime or not mime.hasUrls():
            return ([], tr('Coller'), False)
        urls = [url for url in mime.urls() if url.isValid() and (url.isLocalFile() or url.scheme())]
        if not urls:
            return ([], tr('Coller'), False)
        label = paste_action_label(len(urls), local_clipboard_kind(urls))
        cut = bytes(mime.data(tr('application/x-kde-cutselection'))) == b'1' or bytes(mime.data(tr('x-special/gnome-copied-files'))).startswith(b'cut\n')
        return (urls, tr(label), cut)

    def paste_available(self, destination):
        """Whether the current URL clipboard can be pasted into destination."""
        urls, _label, _cut = self.clipboard_paste_info()
        mime = QApplication.clipboard().mimeData()
        if not destination or self.scanning:
            return False
        location = Location.from_value(destination)
        if location.is_uri:
            if location.value.startswith((tr('trash:'), tr('zip:'), tr('tar:'), tr('sevenz:'), tr('ar:'))):
                return False
        else:
            folder = location.path
            if not folder or not folder.is_dir() or not os.access(folder, os.W_OK | os.X_OK):
                return False
        if not urls:
            return bool(mime and (mime.hasImage() or mime.hasText()) and not location.is_uri)
        needs_kio = location.is_uri or any((not url.isLocalFile() for url in urls))
        return not needs_kio or bool(services.tool_path(tr('mirivue-kio-service')))

    def update_paste_action(self):
        action = getattr(self, tr('paste_action'), None)
        if action is None:
            return
        _urls, label, _cut = self.clipboard_paste_info()
        action.setText(label)
        action.setEnabled(self.paste_available(self.folder))

    def paste_selection(self, destination=None):
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            focus.paste()
            return
        destination = self.folder if destination is None else destination
        mime = QApplication.clipboard().mimeData()
        urls, _label, cut = self.clipboard_paste_info()
        if not mime or not destination:
            return
        if not self.paste_available(destination):
            return
        if not urls:
            self.paste_clipboard_content(Path(destination), mime)
            return
        needs_kio = Location.from_value(destination).is_uri or any((not url.isLocalFile() for url in urls))
        if needs_kio and not services.tool_path(tr('mirivue-kio-service')):
            QMessageBox.information(self, tr('Collage indisponible'), tr('La copie ou le déplacement vers cet emplacement n’est pas disponible sur ce système.'))
            return
        local_paths = normalize_sources([u.toLocalFile() for u in urls if u.isLocalFile()])
        local_set = set(local_paths)
        # Preserve remote URLs for the KIO transfer path, while retaining the
        # local parent/child de-duplication used by Mirivue's safe worker.
        paths = []
        seen_remote = set()
        for url in urls:
            if url.isLocalFile():
                path = Path(url.toLocalFile()).absolute()
                if path in local_set:
                    paths.append(path)
            elif url.isValid() and url.scheme():
                value = url.toString()
                if value not in seen_remote:
                    paths.append(value)
                    seen_remote.add(value)
        if not paths:
            return
        clipboard_guard = self.clipboard_signature() if cut else None
        destination = destination if Location.from_value(destination).is_uri else Path(destination)
        # Choosing Cut and then Paste is explicit intent to move. Do not ask
        # the user to confirm the same move again; direct move commands retain
        # their existing confirmation.
        self.move_entries(paths, destination, confirmed=cut, copy_only=not cut, clipboard_guard=clipboard_guard)

    def paste_clipboard_content(self, destination, mime):
        """Create a named file from clipboard text or image without replacing one."""
        image = mime.imageData() if mime.hasImage() else None
        if isinstance(image, QPixmap):
            image = image.toImage()
        is_image = isinstance(image, QImage) and not image.isNull()
        if not is_image and not mime.hasText():
            return
        payload = b'' if is_image else mime.text().encode('utf-8')
        default = tr('Image collée.png') if is_image else tr('Texte collé.txt')
        while True:
            name, accepted = QInputDialog.getText(self, tr('Coller dans un nouveau fichier'),
                                                   tr('Nom du fichier :'), text=default)
            if not accepted:
                return
            if (reason := services.validate_portable_name(name)):
                QMessageBox.warning(self, tr('Nom de fichier invalide'), reason)
                continue
            target = destination / name
            if target.exists() or target.is_symlink():
                QMessageBox.warning(self, tr('Nom déjà utilisé'), trf('« \x1f0\x1f » existe déjà.', name))
                default = name
                continue
            break
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(prefix='.mirivue-paste-', dir=destination,
                                             delete=False) as stream:
                temporary = Path(stream.name)
                if not is_image:
                    stream.write(payload)
            if is_image and not image.save(str(temporary), 'PNG'):
                raise OSError(tr('Impossible d’enregistrer l’image.'))
            # link() fails atomically if another process created this name.
            os.link(temporary, target)
        except OSError as error:
            QMessageBox.warning(self, tr('Collage impossible'), str(error))
            return
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.refresh_kio_panes()

    def clipboard_signature(self):
        mime = QApplication.clipboard().mimeData()
        if not mime:
            return None
        return (
            tuple(url.toString() for url in mime.urls()),
            bytes(mime.data(tr('application/x-kde-cutselection'))),
            bytes(mime.data(tr('x-special/gnome-copied-files'))),
        )

    def clear_cut_clipboard(self, expected):
        if not expected or self.clipboard_signature() != expected:
            return False
        cut = expected[1] == b'1' or expected[2].startswith(b'cut\n')
        if cut:
            QApplication.clipboard().clear()
            return True
        return False

    def duplicate_selection(self):
        paths = self.selected_entries()
        if not paths or not self.folder:
            return
        paths = self.choose_associated_entries(paths, tr('duplication'))
        if paths is None:
            return
        plans = []
        reserved = set()
        for source in paths:
            suffix = source.suffix if source.is_file() else ''
            stem = source.name[:-len(suffix)] if suffix else source.name
            number = 1
            while True:
                candidate = source.with_name(stem + tr(' — copie') + (trf(' \x1f0\x1f', number) if number > 1 else '') + suffix)
                if not exists(candidate) and candidate not in reserved:
                    break
                number += 1
            plans.append((source, candidate))
            reserved.add(candidate)
        self.move_entries(paths, Path(self.folder), copy_only=True, plans_override=plans)

    def add_transfer_menu(self, menu, selection=True, paste_destination=None):
        if selection:
            cut = menu.addAction(tr('Couper'), lambda: self.copy_selection(True))
            set_themed_action_icon(cut, tr('edit-cut'))
            copy = menu.addAction(tr('Copier'), lambda: self.copy_selection(False))
            set_themed_action_icon(copy, tr('edit-copy'))
            paths = menu.addAction(tr('Copier le chemin'), self.copy_selected_paths)
            set_themed_action_icon(paths, tr('edit-copy-path'))
            mark_entry(paths, 'copy_location')
            paths.setEnabled(bool(self.selected_indexes()))
        if paste_destination is not None and self.paste_available(paste_destination):
            _urls, label, _cut = self.clipboard_paste_info()
            paste = menu.addAction(label, lambda: self.paste_selection(paste_destination))
            set_themed_action_icon(paste, tr('edit-paste'))
        if selection:
            duplicate = menu.addAction(tr('Dupliquer'), self.duplicate_selection)
            set_themed_action_icon(duplicate, tr('edit-copy'))
            mark_entry(duplicate, 'duplicate')
            if self.split_enabled:
                self.update_main_menu_states()
                menu.addAction(self.copy_to_inactive_action)
                mark_entry(self.copy_to_inactive_action, 'copy_to_inactive')
                menu.addAction(self.move_to_inactive_action)
                mark_entry(self.move_to_inactive_action, 'move_to_inactive')
        menu.addSeparator()

    def copy_selected_paths(self):
        paths = [str(self.row(index).path) for index in self.selected_indexes()]
        if paths:
            QApplication.clipboard().setText(tr('\n').join(paths))
